from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path


def app_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


def collect_trace_paths() -> list[Path]:
    paths: list[Path] = []

    if getattr(sys, "frozen", False):
        paths.append(Path(sys.executable).resolve())
        meipass = getattr(sys, "_MEIPASS", None)
        if meipass:
            paths.append(Path(meipass))

    base = app_dir()
    for name in ("dotx.config.json", "PC_CHECK_RESULT.txt"):
        paths.append(base / name)

    reports = base / "reports"
    if reports.exists():
        paths.append(reports)

    temp_dir = Path(tempfile.gettempdir())
    paths.extend(temp_dir.glob("pccheck_hist_*.db"))
    paths.extend(temp_dir.glob("dotx_cleanup_*.cmd"))

    unique: list[Path] = []
    seen: set[str] = set()
    for path in paths:
        key = str(path.resolve()) if path.exists() or not path.is_absolute() else str(path)
        if key not in seen:
            seen.add(key)
            unique.append(path)
    return unique


def schedule_self_delete(extra_paths: list[Path] | None = None) -> None:
    if sys.platform != "win32":
        return

    targets: list[Path] = collect_trace_paths()
    if extra_paths:
        targets.extend(extra_paths)

    existing: list[Path] = []
    seen: set[str] = set()
    for path in targets:
        resolved = path.resolve()
        key = str(resolved)
        if key in seen:
            continue
        seen.add(key)
        if resolved.exists():
            existing.append(resolved)

    if not existing:
        return

    script_path = Path(tempfile.gettempdir()) / f"dotx_cleanup_{os.getpid()}.cmd"
    lines = ["@echo off", "timeout /t 2 /nobreak >nul", "set tries=0", ":retry"]
    for path in existing:
        if path.is_dir():
            lines.append(f'rd /s /q "{path}" 2>nul')
        else:
            lines.append(f'del /f /q "{path}" 2>nul')
    lines.extend(
        [
            "set /a tries+=1",
            "if %tries% lss 20 goto retry",
            f'del /f /q "{script_path}" 2>nul',
        ]
    )
    script_path.write_text("\r\n".join(lines), encoding="utf-8")

    creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    subprocess.Popen(
        ["cmd", "/c", str(script_path)],
        creationflags=creationflags,
        close_fds=True,
    )
