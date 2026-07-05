from __future__ import annotations

import os
import re
from datetime import datetime, timedelta
from pathlib import Path

from pccheck.models import Category, Finding, ScanResult, Severity
from pccheck.signatures import CLEANER_COMMANDS, CLEANER_FILE_SIGNATURES
from pccheck.utils.match import is_legit_cleaner_name, is_whitelisted_path, match_path
from pccheck.utils.walk import iter_files_limited

CLEANER_PATH_INDICATORS: tuple[tuple[str, str, Severity], ...] = (
    ("9zcleaner", "9z cleaner artifacts", Severity.CRITICAL),
    ("ninez", "9z cleaner variant", Severity.CRITICAL),
    ("prefetchcleaner", "Prefetch cleaner tool", Severity.CRITICAL),
    ("prefetchwiper", "Prefetch wiper tool", Severity.CRITICAL),
    ("usnjournal", "USN journal tool", Severity.CRITICAL),
    ("bamcleaner", "BAM registry cleaner", Severity.CRITICAL),
    ("pccheck_bypass", "PC check bypass tool", Severity.CRITICAL),
    ("ss_bypass", "Screenshare bypass tool", Severity.CRITICAL),
    ("evidencewiper", "Evidence wiper tool", Severity.HIGH),
    ("traceclean", "Trace removal tool", Severity.HIGH),
    ("forensiccleanup", "Forensic cleanup tool", Severity.HIGH),
)

RECYCLE_BIN = Path(r"C:\$Recycle.Bin")
EVENT_LOG_DIR = Path(r"C:\Windows\System32\winevt\Logs")
PS_HISTORY = Path(os.environ.get("APPDATA", "")) / "Microsoft/Windows/PowerShell/PSReadLine/ConsoleHost_history.txt"


class CleanerScanner:
    name = "Cleaner / Anti-Forensic Scanner"

    def scan(self, result: ScanResult) -> None:
        self._check_recent_deletions(result)
        self._check_suspicious_paths(result)
        self._check_powershell_history(result)
        self._check_script_artifacts(result)
        self._check_event_log_gaps(result)

    def _check_recent_deletions(self, result: ScanResult) -> None:
        if not RECYCLE_BIN.exists():
            return
        try:
            cutoff = datetime.now() - timedelta(hours=72)
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
                if is_legit_cleaner_name(lower):
                    continue
                for keyword, desc, severity in CLEANER_PATH_INDICATORS:
                    if keyword in lower:
                        result.add(
                            Finding(
                                title=f"Recently deleted: {desc}",
                                description="Suspicious file in Recycle Bin — may have been deleted before PC check",
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
        home = Path.home()
        hide_spots = [
            home / "AppData" / "Local" / "Temp",
            home / "Downloads",
            home / "Desktop",
            Path(r"C:\Tools"),
            Path(r"C:\Cheats"),
            Path(r"C:\Bypass"),
        ]

        cleaner_names = tuple(
            p for sig in CLEANER_FILE_SIGNATURES for p in sig.patterns if len(p) >= 5
        )

        seen: set[str] = set()
        for spot in hide_spots:
            if not spot.exists():
                continue
            try:
                for path in iter_files_limited(spot, max_files=600, max_depth=4):
                    if is_whitelisted_path(path):
                        continue
                    if path.suffix.lower() not in (".exe", ".bat", ".cmd", ".ps1", ".vbs", ""):
                        continue
                    if is_legit_cleaner_name(path.name):
                        continue
                    lower = path.name.lower()
                    for name in cleaner_names:
                        if match_path(name, path) and str(path) not in seen:
                            seen.add(str(path))
                            result.add(
                                Finding(
                                    title=f"Cleaner/bypass file: {path.name}",
                                    description="Executable matching known cleaner or bypass pattern",
                                    severity=Severity.CRITICAL,
                                    category=Category.CLEANER,
                                    evidence=f"Matched '{name}'",
                                    path=str(path),
                                    signature=name,
                                )
                            )
                            break
            except (OSError, PermissionError):
                continue

    def _check_powershell_history(self, result: ScanResult) -> None:
        if not PS_HISTORY.is_file():
            return
        try:
            content = PS_HISTORY.read_text(encoding="utf-8", errors="ignore").lower()
        except OSError:
            return

        for cmd in CLEANER_COMMANDS:
            if cmd in content:
                result.add(
                    Finding(
                        title="Cleaner command in PowerShell history",
                        description="PowerShell history contains evidence-wiping command",
                        severity=Severity.CRITICAL,
                        category=Category.CLEANER,
                        evidence=cmd[:80],
                        path=str(PS_HISTORY),
                        signature="cleaner_command",
                    )
                )
                break

        # Extra patterns for trace cleaning
        extra = (
            r"remove-item.*prefetch",
            r"clear-eventlog",
            r"wevtutil\s+cl",
            r"deletejournal",
            r"clear-history",
        )
        for pattern in extra:
            if re.search(pattern, content):
                result.add(
                    Finding(
                        title="Anti-forensic PowerShell activity",
                        description="PowerShell history shows trace or log cleaning",
                        severity=Severity.HIGH,
                        category=Category.CLEANER,
                        evidence=pattern,
                        path=str(PS_HISTORY),
                        signature="ps_cleaner",
                    )
                )
                break

    def _check_script_artifacts(self, result: ScanResult) -> None:
        """Scan recent scripts in Temp/Downloads for cleaner commands."""
        roots = [
            Path(os.environ.get("TEMP", "")),
            Path.home() / "Downloads",
        ]
        cutoff = datetime.now() - timedelta(days=7)
        seen: set[str] = set()

        for root in roots:
            if not root.exists():
                continue
            try:
                for path in iter_files_limited(root, max_files=200, max_depth=3):
                    if path.suffix.lower() not in (".ps1", ".bat", ".cmd", ".vbs"):
                        continue
                    try:
                        if datetime.fromtimestamp(path.stat().st_mtime) < cutoff:
                            continue
                    except OSError:
                        continue
                    try:
                        text = path.read_text(encoding="utf-8", errors="ignore").lower()[:500_000]
                    except OSError:
                        continue
                    for cmd in CLEANER_COMMANDS:
                        if cmd in text and str(path) not in seen:
                            seen.add(str(path))
                            result.add(
                                Finding(
                                    title=f"Cleaner script: {path.name}",
                                    description="Script contains evidence-wiping commands",
                                    severity=Severity.CRITICAL,
                                    category=Category.CLEANER,
                                    evidence=cmd[:60],
                                    path=str(path),
                                    signature="cleaner_script",
                                )
                            )
                            break
            except (OSError, PermissionError):
                continue

    def _check_event_log_gaps(self, result: ScanResult) -> None:
        security_log = EVENT_LOG_DIR / "Security.evtx"
        ps_missing = not PS_HISTORY.exists()

        if not security_log.exists():
            result.add(
                Finding(
                    title="Security event log missing",
                    description="Windows Security event log not found — possible log clearing",
                    severity=Severity.HIGH if ps_missing else Severity.MEDIUM,
                    category=Category.CLEANER,
                    evidence=str(security_log),
                    path=str(EVENT_LOG_DIR),
                    signature="log_clearing",
                )
            )
            return

        try:
            size = security_log.stat().st_size
            if size < 32 * 1024 and ps_missing:
                result.add(
                    Finding(
                        title="Security log small + PS history cleared",
                        description="Correlated anti-forensic signals — logs and PowerShell history may have been wiped",
                        severity=Severity.HIGH,
                        category=Category.CLEANER,
                        evidence=f"Security.evtx {size} bytes; PS history missing",
                        path=str(security_log),
                        signature="correlated_cleaner",
                    )
                )
        except OSError as exc:
            result.errors.append(f"Event log check: {exc}")
