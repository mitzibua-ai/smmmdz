from __future__ import annotations

import os
from pathlib import Path

from pccheck.models import Category, Finding, ScanResult, Severity
from pccheck.signatures import (
    CHEAT_FILE_SIGNATURES,
    CLEANER_FILE_SIGNATURES,
    MAX_CONTENT_SCAN_BYTES,
    SCAN_EXTENSIONS,
    SUSPICIOUS_FILENAMES,
)
from pccheck.utils.match import is_whitelisted_path, pattern_matches, suspicious_filename
from pccheck.utils.walk import iter_files_limited

CONTENT_EXTENSIONS = {".exe", ".dll", ".sys", ".bat", ".cmd", ".ps1", ".lua", ".js", ".txt", ".ini", ".cfg"}
MAX_FILES = 2500


def _scan_locations() -> list[Path]:
    home = Path.home()
    temp = Path(os.environ.get("TEMP", str(home / "AppData" / "Local" / "Temp")))

    return [
        p
        for p in [
            home / "Downloads",
            home / "Desktop",
            temp,
            home / "AppData" / "Local" / "Temp",
            Path(r"C:\Cheats"),
            Path(r"C:\Bypass"),
            Path(r"C:\Tools"),
        ]
        if p.exists()
    ]


def _read_sample(path: Path) -> str:
    try:
        if path.stat().st_size > MAX_CONTENT_SCAN_BYTES:
            return ""
        return path.read_bytes()[:MAX_CONTENT_SCAN_BYTES].decode("utf-8", errors="ignore").lower()
    except (OSError, PermissionError):
        return ""


class FileScanner:
    name = "File Scanner"

    def scan(self, result: ScanResult) -> None:
        seen: set[str] = set()
        all_sigs = CHEAT_FILE_SIGNATURES + CLEANER_FILE_SIGNATURES
        files_scanned = 0

        for root in _scan_locations():
            per_root = MAX_FILES // max(len(_scan_locations()), 1)
            try:
                for path in iter_files_limited(root, max_files=per_root, max_depth=5):
                    files_scanned += 1
                    if path.suffix and path.suffix.lower() not in SCAN_EXTENSIONS:
                        continue

                    if is_whitelisted_path(path):
                        continue

                    lower_name = path.name.lower()
                    lower_path = str(path).lower()

                    for sus in SUSPICIOUS_FILENAMES:
                        if suspicious_filename(lower_name, sus) and lower_path not in seen:
                            seen.add(lower_path)
                            result.add(
                                Finding(
                                    title="Suspicious filename",
                                    description=f"Filename contains '{sus}'",
                                    severity=Severity.MEDIUM,
                                    category=Category.SUSPICIOUS,
                                    evidence=path.name,
                                    path=str(path),
                                    signature=sus,
                                )
                            )
                            break

                    ext = path.suffix.lower()
                    content = _read_sample(path) if ext in CONTENT_EXTENSIONS else ""

                    for sig in all_sigs:
                        matched_pat = None
                        for pattern in sig.patterns:
                            if sig.category.value in {"cleaner", "bypass"} and ext == ".txt":
                                if not any(
                                    tok in lower_path
                                    for tok in ("cheat", "bypass", "cleaner", "wiper", "tools", "9z")
                                ):
                                    continue
                            if pattern_matches(pattern, path, content):
                                matched_pat = pattern
                                break
                        if matched_pat and lower_path not in seen:
                            seen.add(lower_path)
                            result.add(
                                Finding(
                                    title=sig.name,
                                    description=sig.description,
                                    severity=sig.severity,
                                    category=sig.category,
                                    evidence=f"Matched pattern: '{matched_pat}'",
                                    path=str(path),
                                    signature=matched_pat,
                                )
                            )
            except (OSError, PermissionError) as exc:
                result.errors.append(f"File scan error in {root}: {exc}")

        if files_scanned == 0:
            result.errors.append("File scanner found no readable files in scan paths")
