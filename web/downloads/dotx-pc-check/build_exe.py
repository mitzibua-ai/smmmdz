#!/usr/bin/env python3
"""Build dotx-pc-check.exe for the player download package."""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DIST_EXE = ROOT / "dist" / "dotx-pc-check.exe"
OUTPUT_EXE = ROOT / "dotx-pc-check.exe"


def main() -> int:
    try:
        import PyInstaller  # noqa: F401
    except ImportError:
        print("Installing PyInstaller...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "pyinstaller"])

    assets = ROOT / "assets"
    cmd = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--onefile",
        "--windowed",
        "--name",
        "dotx-pc-check",
        "--paths",
        str(ROOT),
        "--hidden-import",
        "pccheck",
        "--hidden-import",
        "pccheck.engine",
        "--hidden-import",
        "pccheck.models",
        "--hidden-import",
        "pccheck.report.text_report",
        "--collect-submodules",
        "pccheck",
    ]
    if assets.exists():
        cmd.extend(["--add-data", f"{assets}{';' if sys.platform == 'win32' else ':'}assets"])
    cmd.append(str(ROOT / "gui_app.py"))
    print("Building dotx-pc-check.exe...")
    subprocess.check_call(cmd, cwd=ROOT)

    if not DIST_EXE.exists():
        print("Build failed: exe not found.")
        return 1

    shutil.copy2(DIST_EXE, OUTPUT_EXE)
    print(f"Built: {OUTPUT_EXE}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
