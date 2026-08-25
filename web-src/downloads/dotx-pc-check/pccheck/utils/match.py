from __future__ import annotations

import re
from pathlib import Path

TEXT_EXTENSIONS = {".lua", ".js", ".txt", ".bat", ".cmd", ".ps1", ".vbs", ".cfg", ".ini", ".json", ".log", ".xml", ".md"}
BINARY_EXTENSIONS = {".exe", ".dll", ".sys", ".zip", ".rar", ".7z", ".bin", ".dat"}

# Paths where generic keywords should not trigger (reduces false positives)
WHITELIST_PATH_PARTS = {
    "program files",
    "program files (x86)",
    "windows",
    "windowsapps",
    "microsoft",
    "dotnet",
    "node_modules",
    ".venv",
    "venv",
    "site-packages",
    "python",
    "google",
    "mozilla",
    "nvidia",
    "amd",
    "intel",
    "steam",
    "epic games",
    "cursor",
    "vscode",
    "visual studio",
}

# Legitimate tools that contain cleaner-like names
LEGIT_CLEANER_NAMES = {
    "ccleaner",
    "bleachbit",
    "glaryutilities",
    "wise care",
    "revouninstaller",
    "windowsdefender",
    "msmpeng",
    "cleanmgr",
    "dism",
}

# Ambiguous short keywords — require word boundary in filenames
BOUNDARY_KEYWORDS = frozenset(
    {"esp", "hack", "9z", "bam", "dam", "usn", "log", "trace", "ice", "fox", "bolt", "wave"}
)


def is_whitelisted_path(path: Path | str) -> bool:
    parts = {p.lower() for p in Path(path).parts}
    return bool(parts & WHITELIST_PATH_PARTS)


def is_legit_cleaner_name(name: str) -> bool:
    lower = name.lower()
    return any(legit in lower for legit in LEGIT_CLEANER_NAMES)


def _word_boundary_match(keyword: str, text: str) -> bool:
    if keyword not in BOUNDARY_KEYWORDS:
        return keyword in text
    return re.search(rf"(^|[^a-z0-9]){re.escape(keyword)}([^a-z0-9]|$)", text) is not None


def match_path(pattern: str, path: Path | str) -> bool:
    """Match cheat/cleaner patterns in file paths and names (registry, prefetch, filenames)."""
    pl = pattern.lower().strip()
    if len(pl) < 3:
        return False
    path_obj = Path(path)
    if is_whitelisted_path(path_obj):
        return False
    blob = f"{path_obj.name.lower()} {str(path_obj).lower()}"
    if len(pl) <= 4:
        return _word_boundary_match(pl, blob)
    return pl in blob


def pattern_matches(pattern: str, path: Path, content: str) -> bool:
    """
    Match signatures in files without false positives from binary noise.
    """
    if match_path(pattern, path):
        return True

    if not content:
        return False

    pl = pattern.lower().strip()
    length = len(pl)
    if length <= 4:
        return False

    ext = path.suffix.lower()
    if is_whitelisted_path(path):
        return False

    if ext in TEXT_EXTENSIONS and length >= 5:
        return pl in content.lower()

    if ext in BINARY_EXTENSIONS and length >= 10:
        return pl in content.lower()

    return False


def suspicious_filename(name: str, keyword: str) -> bool:
    """Flag suspicious filenames only for executable/script types with safe matching."""
    lower = name.lower()
    if not lower.endswith(
        (".exe", ".dll", ".bat", ".cmd", ".ps1", ".vbs", ".lua", ".js", ".asi", ".zip", ".rar", ".7z")
    ):
        return False
    kw = keyword.lower()
    if kw in {"esp", "9z", "bam"}:
        return _word_boundary_match(kw, lower)
    if len(kw) <= 3:
        return _word_boundary_match(kw, lower)
    return kw in lower


def match_process_name(exe_name: str, pattern: str) -> bool:
    """Match running process names — avoid matching system processes."""
    lower = exe_name.lower()
    if lower in {
        "searchindexer.exe",
        "securityhealthsystray.exe",
        "smartscreen.exe",
        "dllhost.exe",
    }:
        return False
    pl = pattern.lower()
    if pl in {"injector", "loader", "cheat", "hack"}:
        return False
    if len(pl) <= 4:
        return _word_boundary_match(pl, lower)
    return pl in lower
