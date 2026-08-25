from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from pccheck.correlation import apply_correlations
from pccheck.models import ScanResult
from pccheck.scanners import (
    ArchiveScanner,
    BrowserScanner,
    CleanerScanner,
    FileScanner,
    FiveMScanner,
    PEScanner,
    PrefetchScanner,
    ProcessScanner,
    RegistryScanner,
    RpfScanner,
    TraceScanner,
)

ALL_SCANNERS = [
    ProcessScanner(),
    PrefetchScanner(),
    RegistryScanner(),
    PEScanner(),
    RpfScanner(),
    FileScanner(),
    ArchiveScanner(),
    TraceScanner(),
    FiveMScanner(),
    BrowserScanner(),
    CleanerScanner(),
]

REPORT_FILENAME = "PC_CHECK_RESULT.txt"


class ScanEngine:
    def __init__(self, scanners=None):
        self.scanners = scanners or ALL_SCANNERS

    def run(self) -> ScanResult:
        result = ScanResult(
            hostname=socket.gethostname(),
            username=os.environ.get("USERNAME", "unknown"),
        )
        start = time.perf_counter()

        for scanner in self.scanners:
            result.modules_run.append(scanner.name)
            print(f"  Running: {scanner.name}...", flush=True)
            try:
                scanner.scan(result)
            except Exception as exc:
                result.errors.append(f"{scanner.name} failed: {exc}")

        print("  Running: Correlation Engine...", flush=True)
        try:
            correlated = apply_correlations(result)
            if correlated:
                print(f"    -> {len(correlated)} correlation hit(s)", flush=True)
        except Exception as exc:
            result.errors.append(f"Correlation Engine failed: {exc}")

        result.scan_duration_sec = time.perf_counter() - start
        return result

    def save_report(self, result: ScanResult, output_dir: Path) -> Path:
        """Save plain-text report and return its path."""
        from pccheck.report.text_report import build_text

        output_dir.mkdir(parents=True, exist_ok=True)
        txt_path = output_dir / REPORT_FILENAME
        txt_path.write_text(build_text(result), encoding="utf-8")

        # Also save timestamped JSON backup for staff records
        stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        json_path = output_dir / f"scan_{stamp}.json"
        json_path.write_text(json.dumps(result.to_dict(), indent=2), encoding="utf-8")

        return txt_path.resolve()


def open_in_notepad(report_path: Path) -> None:
    """Open the report file in Windows Notepad."""
    path = str(report_path)
    if sys.platform == "win32":
        os.startfile(path)  # noqa: S606 - opens with default .txt handler (Notepad)
    else:
        subprocess.Popen(["notepad.exe", path])  # noqa: S603
