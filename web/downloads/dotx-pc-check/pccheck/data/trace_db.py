from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from pccheck.models import Category, Severity


@dataclass(frozen=True)
class TraceEntry:
    pattern: str
    name: str
    severity: Severity
    category: Category
    description: str
    match_mode: str  # path | content | both


def _traces_file() -> Path:
    bundled = Path(getattr(sys, "_MEIPASS", "")) / "pccheck" / "data" / "traces.jsonl"
    if bundled.is_file():
        return bundled
    return Path(__file__).resolve().parent / "traces.jsonl"


def _parse_category(raw: str) -> Category:
    try:
        return Category(str(raw).lower())
    except ValueError:
        return Category.SUSPICIOUS


def _parse_severity(raw: str) -> Severity:
    try:
        return Severity(str(raw).lower())
    except ValueError:
        return Severity.MEDIUM


@lru_cache(maxsize=1)
def load_traces() -> tuple[TraceEntry, ...]:
    path = _traces_file()
    if not path.is_file():
        return ()

    rows: list[TraceEntry] = []
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            data = json.loads(line)
            pattern = str(data.get("pattern", "")).strip().lower()
            if len(pattern) < 4:
                continue
            rows.append(
                TraceEntry(
                    pattern=pattern,
                    name=str(data.get("name", "Trace match")),
                    severity=_parse_severity(data.get("severity", "medium")),
                    category=_parse_category(data.get("category", "suspicious")),
                    description=str(data.get("description", "")),
                    match_mode=str(data.get("match_mode", "content")),
                )
            )
    except (OSError, json.JSONDecodeError):
        return ()
    return tuple(rows)


def path_traces() -> tuple[TraceEntry, ...]:
    return tuple(t for t in load_traces() if t.match_mode in {"path", "both"})


def content_traces() -> tuple[TraceEntry, ...]:
    return tuple(t for t in load_traces() if t.match_mode in {"content", "both"})


def trace_count() -> int:
    return len(load_traces())
