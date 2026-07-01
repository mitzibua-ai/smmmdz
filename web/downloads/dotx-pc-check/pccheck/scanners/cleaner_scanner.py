from __future__ import annotations

import os
from datetime import datetime, timedelta
from pathlib import Path

from pccheck.models import Category, Finding, ScanResult, Severity

# Paths and patterns associated with anti-forensic / cleaner activity
CLEANER_PATH_INDICATORS: tuple[tuple[str, str, Severity], ...] = (
    ("9z", "9z cleaner artifacts", Severity.CRITICAL),
    ("cleaner", "Generic cleaner tool path", Severity.HIGH),
    ("wiper", "Evidence wiper tool", Severity.HIGH),
    ("bypass", "Screenshare bypass tool", Severity.HIGH),
    ("spoofer", "HWID spoofer", Severity.HIGH),
    ("prefetch", "Prefetch manipulation tool", Severity.CRITICAL),
    ("usn", "USN journal tool", Severity.CRITICAL),
    ("bam", "BAM registry cleaner", Severity.CRITICAL),
    ("trace", "Trace removal tool", Severity.HIGH),
    ("evidence", "Evidence removal tool", Severity.HIGH),
)

RECYCLE_BIN = Path(r"C:\$Recycle.Bin")
EVENT_LOG_DIR = Path(r"C:\Windows\System32\winevt\Logs")


class CleanerScanner:
    name = "Cleaner / Anti-Forensic Scanner"

    def scan(self, result: ScanResult) -> None:
        self._check_recent_deletions(result)
        self._check_suspicious_paths(result)
        self._check_event_log_gaps(result)

    def _check_recent_deletions(self, result: ScanResult) -> None:
        """Look for recently deleted suspicious files in Recycle Bin."""
        if not RECYCLE_BIN.exists():
            return
        try:
            cutoff = datetime.now() - timedelta(hours=48)
            for item in RECYCLE_BIN.rglob("*"):
                if not item.is_file():
                    continue
                try:
                    mtime = datetime.fromtimestamp(item.stat().st_mtime)
                except OSError:
                    continue
                if mtime < cutoff:
                    continue
                lower = item.name.lower()
                for keyword, desc, severity in CLEANER_PATH_INDICATORS:
                    if keyword in lower:
                        result.add(
                            Finding(
                                title=f"Recently deleted: {desc}",
                                description="File in Recycle Bin — may have been deleted before PC check",
                                severity=severity,
                                category=Category.CLEANER,
                                evidence=item.name,
                                path=str(item),
                                signature=keyword,
                            )
                        )
                        break
        except (OSError, PermissionError) as exc:
            result.errors.append(f"Recycle bin scan: {exc}")

    def _check_suspicious_paths(self, result: ScanResult) -> None:
        """Scan common hiding spots for cleaner executables."""
        home = Path.home()
        hide_spots = [
            home / "AppData" / "Local" / "Temp",
            home / "Downloads",
            home / "Desktop",
            Path(r"C:\Tools"),
            Path(r"C:\Cheats"),
            Path(r"C:\Bypass"),
        ]

        from pccheck.utils.walk import iter_files_limited

        cleaner_names = (
            "9z", "cleaner", "wiper", "bypass", "spoofer",
            "prefetch_clean", "usn_clean", "bam_clean", "trace_clean",
            "evidence_clean", "ss_bypass", "pccheck_bypass",
        )

        seen: set[str] = set()
        for spot in hide_spots:
            if not spot.exists():
                continue
            try:
                for path in iter_files_limited(spot, max_files=500, max_depth=4):
                    if path.suffix.lower() not in (".exe", ".bat", ".cmd", ".ps1", ".vbs", ""):
                        continue
                    lower = path.name.lower()
                    for name in cleaner_names:
                        if name in lower and str(path) not in seen:
                            seen.add(str(path))
                            result.add(
                                Finding(
                                    title=f"Cleaner/bypass file: {path.name}",
                                    description="Executable matching cleaner or bypass naming pattern",
                                    severity=Severity.CRITICAL,
                                    category=Category.CLEANER,
                                    evidence=f"Filename contains '{name}'",
                                    path=str(path),
                                    signature=name,
                                )
                            )
                            break
            except (OSError, PermissionError):
                continue

    def _check_event_log_gaps(self, result: ScanResult) -> None:
        """Very small or missing security logs can indicate clearing."""
        security_log = EVENT_LOG_DIR / "Security.evtx"
        if not security_log.exists():
            result.add(
                Finding(
                    title="Security event log missing",
                    description="Windows Security event log not found — possible log clearing",
                    severity=Severity.MEDIUM,
                    category=Category.CLEANER,
                    evidence=str(security_log),
                    path=str(EVENT_LOG_DIR),
                    signature="log_clearing",
                )
            )
            return

        try:
            size = security_log.stat().st_size
            if size < 64 * 1024:  # < 64 KB is unusually small
                result.add(
                    Finding(
                        title="Security event log suspiciously small",
                        description="Security.evtx is very small — may have been cleared",
                        severity=Severity.MEDIUM,
                        category=Category.CLEANER,
                        evidence=f"File size: {size} bytes",
                        path=str(security_log),
                        signature="log_clearing",
                    )
                )
        except OSError as exc:
            result.errors.append(f"Event log check: {exc}")

        # Check if PowerShell history was cleared
        ps_hist = Path(os.environ.get("APPDATA", "")) / "Microsoft/Windows/PowerShell/PSReadLine/ConsoleHost_history.txt"
        if not ps_hist.exists():
            result.add(
                Finding(
                    title="PowerShell history missing",
                    description="No PSReadLine history — may have been deleted to hide commands",
                    severity=Severity.LOW,
                    category=Category.CLEANER,
                    evidence="ConsoleHost_history.txt not found",
                    path=str(ps_hist.parent),
                    signature="ps_history_clear",
                )
            )
