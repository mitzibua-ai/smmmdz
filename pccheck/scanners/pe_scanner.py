from __future__ import annotations

import os
from datetime import datetime, timedelta
from pathlib import Path

from pccheck.models import Category, Finding, ScanResult, Severity
from pccheck.utils.pe import (
    KNOWN_CHEAT_SHA256,
    analyze_pe,
    is_random_cheat_filename,
    is_whitelisted_path,
)
from pccheck.utils.walk import iter_files_limited


def _scan_roots() -> list[Path]:
    home = Path.home()
    temp = Path(os.environ.get("TEMP", str(home / "AppData" / "Local" / "Temp")))
    return [
        p
        for p in [
            home / "Downloads",
            home / "Desktop",
            home / "Documents",
            temp,
            home / "AppData" / "Local" / "Temp",
            home / "AppData" / "Roaming",
            home / "AppData" / "Local",
        ]
        if p.exists()
    ]


class PEScanner:
    """
    Detect cheats that rename on every run by analyzing:
    - SHA256 hash (same binary = same hash even if renamed)
    - PE packer sections (Themida, VMProtect, etc.)
    - Random short filenames (sz05e.exe, k4m2p.exe)
    - Large suspicious executables in user folders
    """

    name = "PE / Hash Scanner"

    def scan(self, result: ScanResult) -> None:
        seen_hashes: set[str] = set()
        recent_cutoff = datetime.now() - timedelta(days=14)

        for root in _scan_roots():
            try:
                for path in iter_files_limited(root, max_files=400, max_depth=5):
                    if path.suffix.lower() != ".exe":
                        continue
                    if is_whitelisted_path(path):
                        continue

                    analysis = analyze_pe(path)
                    if not analysis or not analysis.is_pe:
                        continue

                    # 1) Exact hash match — works even if renamed every run
                    if analysis.sha256 in KNOWN_CHEAT_SHA256:
                        if analysis.sha256 not in seen_hashes:
                            seen_hashes.add(analysis.sha256)
                            desc = KNOWN_CHEAT_SHA256[analysis.sha256]
                            result.add(
                                Finding(
                                    title="Known cheat hash (rename-proof)",
                                    description=desc,
                                    severity=Severity.CRITICAL,
                                    category=Category.CHEAT,
                                    evidence=f"SHA256: {analysis.sha256}",
                                    path=str(path),
                                    signature=analysis.sha256[:16],
                                )
                            )
                        continue

                    name_random = is_random_cheat_filename(path.name)
                    try:
                        mtime = datetime.fromtimestamp(path.stat().st_mtime)
                        is_recent = mtime >= recent_cutoff
                    except OSError:
                        is_recent = False

                    # 2) Themida + random name = very strong cheat indicator
                    if analysis.has_themida and name_random:
                        key = f"themida-random:{analysis.sha256}"
                        if key not in seen_hashes:
                            seen_hashes.add(key)
                            result.add(
                                Finding(
                                    title="Themida-packed random-name executable",
                                    description=(
                                        "Cheat loaders often use Themida protection + random names "
                                        "like sz05e.exe that change every run"
                                    ),
                                    severity=Severity.CRITICAL,
                                    category=Category.CHEAT,
                                    evidence=(
                                        f"File: {path.name}, size: {analysis.size // (1024*1024)}MB, "
                                        f"sections: {', '.join(analysis.sections)}"
                                    ),
                                    path=str(path),
                                    signature="themida+random_name",
                                )
                            )

                    # 3) Themida + large file in Downloads/Temp (even if name not random)
                    elif analysis.has_themida and analysis.size > 40 * 1024 * 1024:
                        loc = str(path.parent).lower()
                        if any(x in loc for x in ("download", "temp", "desktop", "document")):
                            key = f"themida-large:{analysis.sha256}"
                            if key not in seen_hashes:
                                seen_hashes.add(key)
                                result.add(
                                    Finding(
                                        title="Large Themida-packed executable",
                                        description="Protected loader commonly used by FiveM cheats",
                                        severity=Severity.CRITICAL,
                                        category=Category.CHEAT,
                                        evidence=f"{path.name} — {analysis.size // (1024*1024)}MB, Themida packed",
                                        path=str(path),
                                        signature="themida+large",
                                    )
                                )

                    # 4) Random short name + recent + suspicious size (5-100MB)
                    elif name_random and is_recent and 3 * 1024 * 1024 < analysis.size < 100 * 1024 * 1024:
                        key = f"random-recent:{analysis.sha256}"
                        if key not in seen_hashes:
                            seen_hashes.add(key)
                            result.add(
                                Finding(
                                    title="Random-name executable (rename cheat pattern)",
                                    description=(
                                        "Short random filename (e.g. sz05e.exe) — "
                                        "typical of cheats that rename each run"
                                    ),
                                    severity=Severity.HIGH,
                                    category=Category.CHEAT,
                                    evidence=f"{path.name} ({analysis.size // (1024*1024)}MB, modified recently)",
                                    path=str(path),
                                    signature="random_name_exe",
                                )
                            )

                    # 5) Internal cheat strings in binary
                    if analysis.suspicious_strings:
                        key = f"strings:{analysis.sha256}"
                        if key not in seen_hashes:
                            seen_hashes.add(key)
                            result.add(
                                Finding(
                                    title="Cheat strings inside executable",
                                    description="Binary contains FiveM/cheat-related strings",
                                    severity=Severity.HIGH,
                                    category=Category.CHEAT,
                                    evidence="; ".join(analysis.suspicious_strings[:3]),
                                    path=str(path),
                                    signature="pe_strings",
                                )
                            )

                    # 6) Other packers + random name
                    if analysis.packers and name_random and not analysis.has_themida:
                        packer = analysis.packers[0]
                        key = f"packer-random:{analysis.sha256}"
                        if key not in seen_hashes:
                            seen_hashes.add(key)
                            result.add(
                                Finding(
                                    title=f"{packer}-packed random-name executable",
                                    description="Packed binary with random filename — common cheat pattern",
                                    severity=Severity.HIGH,
                                    category=Category.CHEAT,
                                    evidence=f"{path.name} packed with {packer}",
                                    path=str(path),
                                    signature=f"{packer.lower()}+random",
                                )
                            )

            except (OSError, PermissionError) as exc:
                result.errors.append(f"PE scan error in {root}: {exc}")
