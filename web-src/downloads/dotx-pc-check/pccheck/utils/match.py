from __future__ import annotations

from pathlib import Path

TEXT_EXTENSIONS = {".lua", ".js", ".txt", ".bat", ".cmd", ".ps1", ".vbs", ".cfg", ".ini", ".json", ".log"}


def pattern_matches(pattern: str, path: Path, content: str) -> bool:
    """
    Match cheat signatures without false positives from binary noise.
    - Short patterns (<=4 chars): filename/path only
    - Medium patterns: filename + text file content
    - Long patterns (>=8 chars): filename + any file content
    """
    pl = pattern.lower()
    name_blob = f"{path.name.lower()} {str(path).lower()}"

    if pl in name_blob:
        return True

    if not content:
        return False

    ext = path.suffix.lower()
    length = len(pl)

    if length <= 4:
        return False

    if ext in TEXT_EXTENSIONS and length >= 5:
        return pl in content

    if ext in {".exe", ".dll", ".sys", ".zip", ".rar", ".7z"} and length >= 10:
        return pl in content

    return False
