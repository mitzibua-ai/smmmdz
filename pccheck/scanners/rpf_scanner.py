from __future__ import annotations

import os
import winreg
from pathlib import Path

from pccheck.models import Category, Finding, ScanResult, Severity
from pccheck.utils.rpf import RpfVerdict, deep_analyze_rpf, suspicious_rpf_filename
from pccheck.utils.walk import iter_files_limited

FIVEM_MODS_RELATIVE = (
    "FiveM/FiveM.app/mods",
    "FiveM Application Data/mods",
)

MAX_RPF_PER_ROOT = 50


def _gta_mods_folder() -> Path | None:
    keys = [
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Rockstar Games\Grand Theft Auto V", "InstallFolder"),
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Rockstar Games\Grand Theft Auto V", "InstallFolder"),
    ]
    for hive, subkey, value_name in keys:
        try:
            with winreg.OpenKey(hive, subkey) as key:
                val, _ = winreg.QueryValueEx(key, value_name)
                mods = Path(str(val)) / "mods"
                if mods.exists():
                    return mods
        except OSError:
            continue

    for base in (
        Path(r"C:\Program Files\Rockstar Games\Grand Theft Auto V"),
        Path(r"C:\Program Files (x86)\Steam\steamapps\common\Grand Theft Auto V"),
    ):
        mods = base / "mods"
        if mods.exists():
            return mods
    return None


def _fivem_mods_dirs() -> list[Path]:
    local = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData/Local"))
    return [
        local / rel.replace("/", os.sep)
        for rel in FIVEM_MODS_RELATIVE
        if (local / rel.replace("/", os.sep)).exists()
    ]


def _scan_roots() -> list[tuple[Path, str]]:
    roots: list[tuple[Path, str]] = []
    home = Path.home()

    for mods in _fivem_mods_dirs():
        roots.append((mods, "FiveM mods folder"))

    gta_mods = _gta_mods_folder()
    if gta_mods:
        roots.append((gta_mods, "GTA V mods folder"))

    for p in [home / "Downloads", home / "Desktop", home / "Documents"]:
        if p.exists():
            roots.append((p, p.name))

    return roots


class RpfScanner:
    """
    Reads inside each RPF (including nested archives) before flagging.
    Legitimate mods (cars, skins, maps, MLOs) are NOT flagged.
    Only reports when cheat files (weapons.meta, handling.meta, etc.) or cheat strings are found.
    """

    name = "RPF Mod Scanner"

    def scan(self, result: ScanResult) -> None:
        seen: set[str] = set()
        scanned_count = 0
        clean_count = 0

        for root, location_label in _scan_roots():
            try:
                for path in iter_files_limited(root, max_files=MAX_RPF_PER_ROOT, max_depth=6):
                    if path.suffix.lower() != ".rpf":
                        continue
                    key = str(path.resolve())
                    if key in seen:
                        continue
                    seen.add(key)
                    scanned_count += 1

                    if self._analyze_rpf(path, location_label, result):
                        clean_count += 1
            except (OSError, PermissionError) as exc:
                result.errors.append(f"RPF scan error in {root}: {exc}")

        if scanned_count == 0:
            result.add(
                Finding(
                    title="No RPF mod files found",
                    description="No .rpf files in FiveM mods, GTA mods, or user folders",
                    severity=Severity.INFO,
                    category=Category.FIVEM,
                    evidence="Checked FiveM.app/mods, GTA V/mods, Downloads, Desktop",
                )
            )
        elif clean_count == scanned_count:
            result.add(
                Finding(
                    title=f"RPF mods scanned: {scanned_count} clean",
                    description=(
                        "All RPF archives were opened and inspected (including nested files). "
                        "No weapons.meta, handling.meta, or cheat strings found."
                    ),
                    severity=Severity.INFO,
                    category=Category.FIVEM,
                    evidence=f"{clean_count}/{scanned_count} RPF mods contain no cheat content",
                )
            )

    def _analyze_rpf(self, path: Path, location: str, result: ScanResult) -> bool:
        """Returns True if RPF is clean (no cheat content)."""
        analysis = deep_analyze_rpf(path)

        if not analysis or not analysis.valid:
            return True  # unreadable — don't false-positive

        if analysis.verdict == RpfVerdict.UNREADABLE:
            return True  # encrypted/locked — skip, not a cheat verdict

        # Only flag when cheat content was actually found INSIDE the archive
        if analysis.verdict != RpfVerdict.CHEAT:
            return True

        size_mb = analysis.file_size / (1024 * 1024)
        nested_note = ""
        if analysis.nested_scanned:
            nested_note = f" (also scanned inside: {', '.join(analysis.nested_scanned[:4])})"

        for internal_name, reason in analysis.cheat_files:
            result.add(
                Finding(
                    title=f"Cheat content in RPF: {internal_name.rsplit('/', 1)[-1]}",
                    description=reason,
                    severity=Severity.CRITICAL,
                    category=Category.FIVEM,
                    evidence=f"Inside {path.name}{nested_note}: {internal_name}",
                    path=str(path),
                    signature=internal_name.rsplit("/", 1)[-1].lower(),
                )
            )

        if analysis.string_hits:
            result.add(
                Finding(
                    title=f"Cheat strings inside RPF: {path.name}",
                    description="Archive contains known cheat-related strings after full inspection",
                    severity=Severity.CRITICAL,
                    category=Category.FIVEM,
                    evidence=f"{', '.join(analysis.string_hits[:5])}{nested_note}",
                    path=str(path),
                    signature="rpf_cheat_strings",
                )
            )

        # Suspicious filename only matters if cheat content was also found inside
        name_hit = suspicious_rpf_filename(path.name)
        if name_hit and analysis.cheat_files:
            result.add(
                Finding(
                    title=f"Suspicious RPF name + cheat content: {path.name}",
                    description="Filename and internal content both match cheat indicators",
                    severity=Severity.CRITICAL,
                    category=Category.FIVEM,
                    evidence=f"Keyword '{name_hit}' + internal cheat files in {location}",
                    path=str(path),
                    signature=name_hit,
                )
            )

        return False
