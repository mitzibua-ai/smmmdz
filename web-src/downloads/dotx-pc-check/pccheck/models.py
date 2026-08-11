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
    def correlation_findings(self) -> list[Finding]:
        return [f for f in self.findings if (f.signature or "").startswith("corr_")]

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
        correlations = self.correlation_findings
        strong_corr = [
            f
            for f in correlations
            if f.severity == Severity.CRITICAL
            and f.signature
            in {
                "corr_cleaner_plus_cheat",
                "corr_wipe_plus_cheat",
                "corr_multi_source_brand",
                "corr_exec_and_disk",
                "corr_injection_cover",
                "corr_cleaner_exec_remnant",
            }
        ]

        # Cross-scanner correlations are high-confidence cheating / cover-up
        if strong_corr:
            return "CHEATING LIKELY"

        # Strong cheat / known cleaner brand hits
        strong = [
            f
            for f in criticals
            if f.category in {Category.CHEAT, Category.INJECTION}
            or any(
                tok in (f.signature or "").lower() + (f.evidence or "").lower()
                for tok in (
                    "9zcleaner",
                    "susano",
                    "eulen",
                    "macho",
                    "skript",
                    "gosth",
                    "redengine",
                    "corr_cleaner_plus_cheat",
                    "corr_wipe_plus_cheat",
                )
            )
        ]

        if strong:
            return "CHEATING LIKELY"

        # Multiple independent critical signals
        if len(criticals) >= 2:
            return "CHEATING LIKELY"

        # Any correlation (even HIGH) escalates review
        if correlations and Severity.HIGH in severities:
            return "SUSPICIOUS"

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
        base = sum(weights[f.severity] for f in self.findings if not (f.signature or "").startswith("corr_"))
        # Correlations add confidence without fully double-counting raw hits
        corr_bonus = sum(
            18 if f.severity == Severity.CRITICAL else 10 if f.severity == Severity.HIGH else 5
            for f in self.correlation_findings
        )
        return min(100, base + corr_bonus)

    def add(self, finding: Finding) -> None:
        self.findings.append(finding)

    def to_dict(self) -> dict[str, Any]:
        return {
            "verdict": self.verdict,
            "score": self.score,
            "finding_count": len(self.findings),
            "correlation_count": len(self.correlation_findings),
            "findings": [f.to_dict() for f in self.findings],
            "modules_run": self.modules_run,
            "errors": self.errors,
            "scan_duration_sec": round(self.scan_duration_sec, 2),
            "hostname": self.hostname,
            "username": self.username,
        }
