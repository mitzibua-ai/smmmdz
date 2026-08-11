#!/usr/bin/env python3
"""Build dotx-pc-check.exe for the player download package."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO_ROOT = ROOT.parents[2]
PCCHECK_SRC = REPO_ROOT / "pccheck"
PCCHECK_DST = ROOT / "pccheck"
BUILD_SIGNATURES = REPO_ROOT / "scripts" / "build_signature_db.py"
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


def sync_pccheck() -> None:
    """Copy root pccheck package into the exe bundle folder."""
    if not PCCHECK_SRC.is_dir():
        print(f"Warning: source pccheck not found at {PCCHECK_SRC}")
        return
    if PCCHECK_DST.exists():
        shutil.rmtree(PCCHECK_DST)
    shutil.copytree(
        PCCHECK_SRC,
        PCCHECK_DST,
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc", ".pytest_cache"),
    )
    print(f"Synced pccheck -> {PCCHECK_DST}")


def build_trace_db() -> None:
    if BUILD_SIGNATURES.is_file():
        subprocess.check_call([sys.executable, str(BUILD_SIGNATURES)])
    else:
        print("Warning: build_signature_db.py not found — trace DB may be missing")
    import_script = REPO_ROOT / "scripts" / "import_detections.py"
    if import_script.is_file():
        subprocess.check_call([sys.executable, str(import_script)])


def main() -> int:
    sync_pccheck()
    build_trace_db()
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
    traces = ROOT / "pccheck" / "data" / "traces.jsonl"
    if traces.exists():
        sep = ";" if sys.platform == "win32" else ":"
        cmd.extend(["--add-data", f"{traces}{sep}pccheck/data"])
    domains = ROOT / "pccheck" / "data" / "cheat_domains.txt"
    if domains.exists():
        sep = ";" if sys.platform == "win32" else ":"
        cmd.extend(["--add-data", f"{domains}{sep}pccheck/data"])
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
