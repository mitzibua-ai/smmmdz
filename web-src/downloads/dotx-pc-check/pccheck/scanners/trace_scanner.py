from __future__ import annotations

import os
from pathlib import Path

from pccheck.data.trace_db import TraceEntry, load_traces
from pccheck.models import Finding, ScanResult, Severity
from pccheck.signatures import SCAN_EXTENSIONS
from pccheck.utils.match import is_whitelisted_path
from pccheck.utils.walk import iter_files_limited

MAX_FILES = 600
MAX_DEPTH = 4
TRACE_TEXT_EXTENSIONS = {".lua", ".js", ".txt", ".cfg", ".ini", ".log", ".bat", ".ps1", ".vbs", ".json", ".xml", ".exe", ".dll"}
MAX_TRACE_BYTES = 512 * 1024
MAX_PATTERNS = 3000


def _deep_roots() -> list[Path]:
    home = Path.home()
    temp = Path(os.environ.get("TEMP", str(home / "AppData" / "Local" / "Temp")))
    return [
        p
        for p in [
            home / "Downloads",
            home / "Desktop",
            home / "Documents",
            temp,
            home / "AppData" / "Local" / "Temp",
            home / "AppData" / "Roaming",
            home / "AppData" / "Roaming" / "discord",
            home / "AppData" / "Roaming" / "discordcanary",
            home / "AppData" / "Roaming" / "discordptb",
            Path(r"C:\Cheats"),
            Path(r"C:\Bypass"),
            Path(r"C:\Tools"),
        ]
        if p.exists()
    ]


def _content_trace_pool() -> tuple[TraceEntry, ...]:
    pool = [
        e
        for e in load_traces()
        if len(e.pattern) >= 10
        and e.severity in {Severity.CRITICAL, Severity.HIGH}
    ]
    pool.sort(key=lambda e: (-len(e.pattern), e.pattern))
    return tuple(pool[:MAX_PATTERNS])


def _read_snippet(path: Path) -> str:
    try:
        if path.stat().st_size > MAX_TRACE_BYTES:
            return ""
        return path.read_bytes()[:MAX_TRACE_BYTES].decode("utf-8", errors="ignore").lower()
    except (OSError, PermissionError):
        return ""


class TraceScanner:
    """Deep content scan against 29k trace DB (top 3000 high-confidence patterns)."""

    name = "Deep Trace Scanner"

    def scan(self, result: ScanResult) -> None:
        traces = load_traces()
        if not traces:
            result.errors.append("Trace database not loaded")
            return

        patterns = _content_trace_pool()
        seen: set[str] = set()

        for root in _deep_roots():
            per_root = MAX_FILES // max(len(_deep_roots()), 1)
            try:
                for path in iter_files_limited(root, max_files=per_root, max_depth=MAX_DEPTH):
                    if is_whitelisted_path(path):
                        continue
                    if path.suffix and path.suffix.lower() not in SCAN_EXTENSIONS:
                        continue

                    ext = path.suffix.lower()
                    if ext not in TRACE_TEXT_EXTENSIONS:
                        continue

                    content = _read_snippet(path)
                    if len(content) < 10:
                        continue

                    lower_path = str(path).lower()
                    for entry in patterns:
                        if entry.pattern not in content:
                            continue
                        key = f"{entry.pattern}:{lower_path}"
                        if key in seen:
                            continue
                        seen.add(key)
                        result.add(
                            Finding(
                                title=entry.name,
                                description=entry.description or "Matched trace database",
                                severity=entry.severity,
                                category=entry.category,
                                evidence=f"Trace: '{entry.pattern}'",
                                path=str(path),
                                signature=entry.pattern[:64],
                            )
                        )
            except (OSError, PermissionError) as exc:
                result.errors.append(f"Trace scan error in {root}: {exc}")
