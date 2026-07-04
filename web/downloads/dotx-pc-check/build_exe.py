#!/usr/bin/env python3
"""Build dotx-pc-check.exe for the player download package."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DIST_EXE = ROOT / "dist" / "dotx-pc-check.exe"
OUTPUT_EXE = ROOT / "dotx-pc-check.exe"
DEPLOY_EXE = ROOT / "dotx.exe"
ICON = ROOT / "assets" / "dotx.ico"
VERSION_FILE = ROOT / "assets" / "version_info.txt"


def ensure_icon() -> None:
    logo = ROOT / "assets" / "logo.png"
    if not logo.exists():
        return
    if ICON.exists() and ICON.stat().st_mtime >= logo.stat().st_mtime:
        return
    try:
        from PIL import Image
    except ImportError:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "pillow"])
        from PIL import Image
    img = Image.open(logo)
    img.save(
        ICON,
        format="ICO",
        sizes=[(256, 256), (128, 128), (64, 64), (48, 48), (32, 32), (16, 16)],
    )


def main() -> int:
    ensure_icon()
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
    if ICON.exists():
        cmd.extend(["--icon", str(ICON)])
    if VERSION_FILE.exists():
        cmd.extend(["--version-file", str(VERSION_FILE)])
    if assets.exists():
        cmd.extend(["--add-data", f"{assets}{';' if sys.platform == 'win32' else ':'}assets"])
    cmd.append(str(ROOT / "gui_app.py"))
    print("Building dotx-pc-check.exe...")
    subprocess.check_call(cmd, cwd=ROOT)

    if not DIST_EXE.exists():
        print("Build failed: exe not found.")
        return 1

    shutil.copy2(DIST_EXE, OUTPUT_EXE)

    try:
        from sign_exe import sign_exe

        sign_exe(OUTPUT_EXE)
    except Exception as exc:
        print(f"Note: exe not signed ({exc}). Windows may show SmartScreen until you add a code signing cert.")

    shutil.copy2(OUTPUT_EXE, DEPLOY_EXE)

    print(f"Built: {OUTPUT_EXE}")
    print(f"Deploy copy: {DEPLOY_EXE}")
    if not os.environ.get("CODE_SIGN_PFX") and not os.environ.get("CODE_SIGN_THUMBPRINT"):
        print(
            "SmartScreen warning: unsigned exe. Purchase an Authenticode certificate and set "
            "CODE_SIGN_PFX + CODE_SIGN_PASSWORD, then rebuild."
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
