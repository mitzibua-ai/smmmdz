from __future__ import annotations

import argparse
import subprocess
import sys
import traceback
from pathlib import Path

from pccheck import __version__
from pccheck.engine import ScanEngine, open_in_notepad


def _write_error_report(output_dir: Path, message: str) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / "PC_CHECK_RESULT.txt"
    body = (
        "FIVEM PC CHECK - ERROR\r\n"
        "=====================\r\n\r\n"
        "The scan could not finish. Details:\r\n\r\n"
        f"{message}\r\n\r\n"
        "Make sure Python 3.10+ is installed from https://python.org\r\n"
        "Try right-click run_scan.bat -> Run as administrator\r\n"
    )
    path.write_text(body, encoding="utf-8")
    return path.resolve()


def print_banner() -> None:
    print("=" * 60)
    print("  FiveM PC Check Scanner")
    print(f"  v{__version__} - Cheat & Cleaner Detection")
    print("=" * 60)
    print()


def print_results(result) -> None:
    data = result.to_dict()
    print()
    print(f"VERDICT: {data['verdict']}")
    print(
        f"Risk Score: {data['score']}/100  |  "
        f"Findings: {data['finding_count']}  |  "
        f"Time: {data['scan_duration_sec']}s"
    )
    print(f"Host: {data['hostname']}  |  User: {data['username']}")
    print()

    if not result.findings:
        print("No threats detected.")
        return

    print("FINDINGS:")
    print("-" * 60)
    for finding in result.findings:
        print(f"[{finding.severity.value.upper()}] {finding.title}")
        print(f"  {finding.evidence}")
        if finding.path:
            print(f"  Path: {finding.path}")
        print()

    if result.errors:
        print("WARNINGS:")
        for err in result.errors:
            print(f"  - {err}")


def main(argv: list[str] | None = None) -> int:
    script_dir = Path(__file__).resolve().parent
    default_output = script_dir / "reports"

    parser = argparse.ArgumentParser(
        description="FiveM PC Check - detect cheats and cleaners",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=default_output,
        help="Output folder for PC_CHECK_RESULT.txt",
    )
    parser.add_argument(
        "--no-notepad",
        action="store_true",
        help="Do not open Notepad when finished",
    )
    parser.add_argument(
        "--quick",
        action="store_true",
        help="Fast scan - skip deep file walk",
    )
    parser.add_argument(
        "--pin",
        default="",
        help="dotx session PIN from staff",
    )
    args = parser.parse_args(argv)

    try:
        print_banner()
        print("Scanning... please wait.")
        print()

        engine = ScanEngine()
        if args.quick:
            from pccheck.scanners import (
                BrowserScanner,
                PrefetchScanner,
                ProcessScanner,
                RegistryScanner,
            )
            engine.scanners = [
                ProcessScanner(),
                PrefetchScanner(),
                RegistryScanner(),
                BrowserScanner(),
            ]

        result = engine.run()
        print_results(result)

        report_path = engine.save_report(result, args.output)
        if args.pin:
            body = report_path.read_text(encoding="utf-8")
            report_path.write_text(
                f"dotx PIN: {args.pin}\r\n\r\n{body}",
                encoding="utf-8",
            )
        print()
        print(f"Report saved: {report_path}")

        if not args.no_notepad:
            print("Opening result in Notepad...")
            open_in_notepad(report_path)

        return 1 if result.verdict in ("CHEATING LIKELY", "SUSPICIOUS") else 0

    except Exception:
        err = traceback.format_exc()
        print(err, file=sys.stderr)
        report_path = _write_error_report(args.output, err)
        if not args.no_notepad:
            open_in_notepad(report_path)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
