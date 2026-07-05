from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class Severity(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


class Category(str, Enum):
    CHEAT = "cheat"
    CLEANER = "cleaner"
    BYPASS = "bypass"
    INJECTION = "injection"
    ARTIFACT = "artifact"
    FIVEM = "fivem"
    SUSPICIOUS = "suspicious"


@dataclass
class Finding:
    title: str
    description: str
    severity: Severity
    category: Category
    evidence: str
    path: str = ""
    signature: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "title": self.title,
            "description": self.description,
            "severity": self.severity.value,
            "category": self.category.value,
            "evidence": self.evidence,
            "path": self.path,
            "signature": self.signature,
        }


@dataclass
class ScanResult:
    findings: list[Finding] = field(default_factory=list)
    modules_run: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    scan_duration_sec: float = 0.0
    hostname: str = ""
    username: str = ""

    @property
    def verdict(self) -> str:
        if not self.findings:
            return "CLEAN"

        # Ignore INFO-only noise
        actionable = [f for f in self.findings if f.severity != Severity.INFO]
        if not actionable:
            return "CLEAN"

        severities = {f.severity for f in actionable}
        criticals = [f for f in actionable if f.severity == Severity.CRITICAL]

        # Strong cheat / known cleaner brand hits
        strong = [
            f
            for f in criticals
            if f.category in {Category.CHEAT, Category.INJECTION}
            or any(
                tok in (f.signature or "").lower() + (f.evidence or "").lower()
                for tok in ("9zcleaner", "susano", "eulen", "macho", "skript", "gosth", "redengine")
            )
        ]

        if strong:
            return "CHEATING LIKELY"

        # Multiple independent critical signals
        if len(criticals) >= 2:
            return "CHEATING LIKELY"

        # Single critical cleaner heuristic without brand proof → suspicious not cheating
        if Severity.CRITICAL in severities:
            return "SUSPICIOUS"

        if Severity.HIGH in severities:
            return "SUSPICIOUS"

        if Severity.MEDIUM in severities:
            return "REVIEW NEEDED"

        return "CLEAN"

    @property
    def score(self) -> int:
        weights = {
            Severity.CRITICAL: 40,
            Severity.HIGH: 25,
            Severity.MEDIUM: 12,
            Severity.LOW: 5,
            Severity.INFO: 0,
        }
        return min(100, sum(weights[f.severity] for f in self.findings))

    def add(self, finding: Finding) -> None:
        self.findings.append(finding)

    def to_dict(self) -> dict[str, Any]:
        return {
            "verdict": self.verdict,
            "score": self.score,
            "finding_count": len(self.findings),
            "findings": [f.to_dict() for f in self.findings],
            "modules_run": self.modules_run,
            "errors": self.errors,
            "scan_duration_sec": round(self.scan_duration_sec, 2),
            "hostname": self.hostname,
            "username": self.username,
        }
