from __future__ import annotations

from pathlib import Path

SKIP_DIR_NAMES = {
    "node_modules",
    ".git",
    "cache",
    "caches",
    "cache2",
    "code cache",
    "gpucache",
    "shadercache",
    "packages",
    "microsoft",
    "google",
    "mozilla",
    "steam",
    "nvidia",
    "amd",
    "windowsapps",
    "winsxs",
    "program files",
    "program files (x86)",
    "application data",
}


def iter_files_limited(root: Path, max_files: int = 2000, max_depth: int = 6):
    """Yield files under root, skipping heavy dirs, with caps."""
    if not root.exists():
        return

    count = 0
    stack: list[tuple[Path, int]] = [(root, 0)]

    while stack and count < max_files:
        current, depth = stack.pop()
        if depth > max_depth:
            continue
        try:
            entries = list(current.iterdir())
        except (OSError, PermissionError):
            continue

        for entry in entries:
            if count >= max_files:
                return
            try:
                if entry.is_dir():
                    if entry.name.lower() not in SKIP_DIR_NAMES:
                        stack.append((entry, depth + 1))
                elif entry.is_file():
                    count += 1
                    yield entry
            except (OSError, PermissionError):
                continue
