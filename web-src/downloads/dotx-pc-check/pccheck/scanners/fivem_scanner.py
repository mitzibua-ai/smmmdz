from __future__ import annotations

import os
from pathlib import Path

from pccheck.models import Category, Finding, ScanResult, Severity
from pccheck.signatures import CHEAT_FILE_SIGNATURES, MAX_CONTENT_SCAN_BYTES, SCAN_EXTENSIONS
from pccheck.utils.walk import iter_files_limited

FIVEM_LUA_PATTERNS: tuple[tuple[str, str, Severity], ...] = (
    ("loadstring", "Obfuscated Lua execution (loadstring)", Severity.HIGH),
    ("performhttprequest", "Remote code fetch via HTTP", Severity.HIGH),
    ("citizen.invoke", "Native function abuse", Severity.MEDIUM),
    ("triggerServerEvent", "Suspicious server event trigger", Severity.MEDIUM),
    ("giveweapon", "Weapon spawn script", Severity.MEDIUM),
    ("setentityhealth", "God mode pattern", Severity.MEDIUM),
    ("networkresurrectlocalplayer", "Revive/godmode exploit", Severity.HIGH),
    ("addmoney", "Money injection pattern", Severity.HIGH),
    ("noclip", "Noclip cheat script", Severity.MEDIUM),
    ("aimbot", "Aimbot script", Severity.HIGH),
    ("triggerbot", "Triggerbot script", Severity.HIGH),
)

FIVEM_SUBDIRS = ("mods", "citizen", "plugins")
SKIP_FIVEM_DIR_NAMES = {"server-cache", "server-cache-priv", "cache", "logs"}


class FiveMScanner:
    name = "FiveM Folder Scanner"

    def scan(self, result: ScanResult) -> None:
        local = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData/Local"))
        fivem_roots = [
            local / "FiveM",
            local / "FiveM Application Data",
            Path.home() / "Documents" / "FiveM",
        ]

        found_any = False
        for root in fivem_roots:
            if not root.exists():
                continue
            found_any = True
            self._scan_root(root, result)

        if not found_any:
            result.add(
                Finding(
                    title="FiveM data folder not found",
                    description="No standard FiveM installation paths detected",
                    severity=Severity.INFO,
                    category=Category.FIVEM,
                    evidence="Checked %LOCALAPPDATA%\\FiveM and related paths",
                )
            )

    def _scan_root(self, root: Path, result: ScanResult) -> None:
        seen: set[str] = set()

        targets: list[Path] = []
        for name in FIVEM_SUBDIRS:
            sub = root / name
            if sub.exists():
                targets.append(sub)
        if not targets:
            targets = [root]

        for target in targets:
            for path in iter_files_limited(target, max_files=1500, max_depth=8):
                if any(skip in path.parts for skip in SKIP_FIVEM_DIR_NAMES):
                    continue
                if path.suffix.lower() not in SCAN_EXTENSIONS and path.suffix:
                    continue

                lower_path = str(path).lower()
                for sig in CHEAT_FILE_SIGNATURES:
                    for pattern in sig.patterns:
                        if pattern.lower() in lower_path and lower_path not in seen:
                            seen.add(lower_path)
                            result.add(
                                Finding(
                                    title=f"FiveM artifact: {sig.name}",
                                    description=sig.description,
                                    severity=sig.severity,
                                    category=Category.FIVEM,
                                    evidence=f"Path matched '{pattern}'",
                                    path=str(path),
                                    signature=pattern,
                                )
                            )
                            break

                if path.suffix.lower() in (".lua", ".js"):
                    self._scan_script(path, result, seen)

                if path.suffix.lower() == ".dll" and "mods" in lower_path:
                    dll_name = path.name.lower()
                    if any(kw in dll_name for kw in ("cheat", "inject", "hook", "eulen", "susano", "macho")):
                        key = str(path)
                        if key not in seen:
                            seen.add(key)
                            result.add(
                                Finding(
                                    title="Suspicious FiveM mod DLL",
                                    description="DLL in FiveM mods folder with cheat-related name",
                                    severity=Severity.HIGH,
                                    category=Category.FIVEM,
                                    evidence=path.name,
                                    path=str(path),
                                )
                            )

    def _scan_script(self, path: Path, result: ScanResult, seen: set[str]) -> None:
        try:
            text = path.read_bytes()[:MAX_CONTENT_SCAN_BYTES].decode("utf-8", errors="ignore").lower()
        except (OSError, PermissionError):
            return

        for pattern, desc, severity in FIVEM_LUA_PATTERNS:
            if pattern.lower() in text:
                key = f"{path}:{pattern}"
                if key in seen:
                    continue
                seen.add(key)
                result.add(
                    Finding(
                        title=f"Suspicious FiveM script: {pattern}",
                        description=desc,
                        severity=severity,
                        category=Category.FIVEM,
                        evidence=f"Found '{pattern}' in script",
                        path=str(path),
                        signature=pattern,
                    )
                )
