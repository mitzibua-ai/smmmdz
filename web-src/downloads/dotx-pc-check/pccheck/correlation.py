"""Cross-finding correlation engine — links cleaner, cheat, and wipe signals."""
from __future__ import annotations

import re
from dataclasses import dataclass

from pccheck.models import Category, Finding, ScanResult, Severity

# Brand / family tokens used to group findings across scanners
CHEAT_BRANDS = (
    "susano",
    "eulen",
    "macho",
    "skript",
    "gosth",
    "redengine",
    "hxsoftware",
    "hxcheats",
    "tzproject",
    "brutan",
    "lumia",
    "kekhack",
    "degeo",
    "nexus",
    "keyser",
    "phantom",
    "nightfall",
    "softaim",
    "ragebot",
)

CLEANER_BRANDS = (
    "9zcleaner",
    "ninez",
    "prefetchcleaner",
    "prefetchwiper",
    "bamcleaner",
    "damcleaner",
    "usnclean",
    "usndelete",
    "evidencewiper",
    "stringcleaner",
    "byte cleaner",
    "pc check bypass",
    "screenshare",
)

WIPE_SIGNATURES = {
    "correlated_cleaner",
    "cleaner_command",
    "ps_cleaner",
    "cleaner_script",
    "cleaner_prefetch",
    "empty_prefetch",
    "prefetch_cleared",
    "prefetch_clearing",
    "security_log_cleared",
    "event_log_gap",
}

EXECUTION_HINTS = (
    "prefetch",
    "bam",
    "dam",
    "process",
    "running",
    "executed",
    "launch",
)

BROWSER_HINTS = ("browser", "history", "visited", "domain", "url")

FILE_HINTS = ("file", "path", "pe_", "hash", "themida", "rpf", "dll", "lua", "archive")


@dataclass(frozen=True)
class _RuleHit:
    title: str
    description: str
    severity: Severity
    category: Category
    evidence: str
    signature: str


def _blob(finding: Finding) -> str:
    return " ".join(
        [
            finding.title or "",
            finding.description or "",
            finding.evidence or "",
            finding.signature or "",
            finding.path or "",
            finding.category.value,
        ]
    ).lower()


def _has_any(text: str, tokens: tuple[str, ...] | set[str]) -> bool:
    return any(tok in text for tok in tokens)


def _brands_in(text: str, brands: tuple[str, ...]) -> set[str]:
    return {b for b in brands if b in text}


def _is_cleaner(f: Finding) -> bool:
    if f.category in {Category.CLEANER, Category.BYPASS}:
        return True
    blob = _blob(f)
    return _has_any(blob, CLEANER_BRANDS) or (f.signature or "").lower() in WIPE_SIGNATURES


def _is_cheat(f: Finding) -> bool:
    if f.category in {Category.CHEAT, Category.INJECTION, Category.FIVEM}:
        return True
    blob = _blob(f)
    return _has_any(blob, CHEAT_BRANDS)


def _is_wipe_signal(f: Finding) -> bool:
    sig = (f.signature or "").lower()
    if sig in WIPE_SIGNATURES:
        return True
    blob = _blob(f)
    wipe_words = (
        "prefetch cleared",
        "empty prefetch",
        "wevtutil",
        "usn delete",
        "deletejournal",
        "security.evtx",
        "powershell history",
        "history cleared",
        "bam deleted",
        "evidence wiped",
        "anti-forensic",
        "forensic cleaner",
    )
    return _has_any(blob, wipe_words)


def _is_execution(f: Finding) -> bool:
    sig = (f.signature or "").lower()
    if any(h in sig for h in ("prefetch", "bam", "dam", "process")):
        return True
    return _has_any(_blob(f), EXECUTION_HINTS)


def _is_browser(f: Finding) -> bool:
    sig = (f.signature or "").lower()
    if "browser" in sig or "domain" in sig:
        return True
    return _has_any(_blob(f), BROWSER_HINTS)


def _is_file_artifact(f: Finding) -> bool:
    sig = (f.signature or "").lower()
    if any(h in sig for h in ("pe_", "hash", "rpf", "file", "trace", "archive")):
        return True
    return bool(f.path) or _has_any(_blob(f), FILE_HINTS)


def _stem_tokens(path: str) -> set[str]:
    if not path:
        return set()
    name = path.replace("\\", "/").split("/")[-1].lower()
    stem = re.sub(r"\.(exe|dll|pf|lnk|bat|ps1|lua|rpf)$", "", name)
    stem = re.sub(r"[^a-z0-9]+", " ", stem)
    parts = {p for p in stem.split() if len(p) >= 4}
    if stem and len(stem) >= 4:
        parts.add(stem.replace(" ", ""))
    return parts


class CorrelationEngine:
    """Second-pass analysis that combines independent scanner findings."""

    name = "Correlation Engine"

    def apply(self, result: ScanResult) -> list[Finding]:
        if len(result.findings) < 2:
            return []

        hits = self._evaluate(result.findings)
        added: list[Finding] = []
        existing_sigs = {(f.signature or "").lower() for f in result.findings}

        for hit in hits:
            if hit.signature.lower() in existing_sigs:
                continue
            finding = Finding(
                title=hit.title,
                description=hit.description,
                severity=hit.severity,
                category=hit.category,
                evidence=hit.evidence,
                signature=hit.signature,
            )
            result.add(finding)
            added.append(finding)
            existing_sigs.add(hit.signature.lower())

        if added:
            result.modules_run.append(self.name)
        return added

    def _evaluate(self, findings: list[Finding]) -> list[_RuleHit]:
        hits: list[_RuleHit] = []

        cleaners = [f for f in findings if _is_cleaner(f)]
        cheats = [f for f in findings if _is_cheat(f)]
        wipes = [f for f in findings if _is_wipe_signal(f)]
        executions = [f for f in findings if _is_execution(f)]
        browsers = [f for f in findings if _is_browser(f) and _is_cheat(f)]
        files = [f for f in findings if _is_file_artifact(f) and _is_cheat(f)]
        bypasses = [f for f in findings if f.category == Category.BYPASS]

        # 1) Cleaner tool + cheat residue = classic pre-check wipe pattern
        if cleaners and cheats:
            c_titles = ", ".join(sorted({f.title for f in cleaners})[:4])
            t_titles = ", ".join(sorted({f.title for f in cheats})[:4])
            hits.append(
                _RuleHit(
                    title="Correlated: cleaner activity + cheat residue",
                    description=(
                        "Anti-forensic / cleaner signals appear together with cheat indicators. "
                        "This pattern is commonly used to hide FiveM cheats before a PC check."
                    ),
                    severity=Severity.CRITICAL,
                    category=Category.CHEAT,
                    evidence=f"Cleaner side: {c_titles} || Cheat side: {t_titles}",
                    signature="corr_cleaner_plus_cheat",
                )
            )

        # 2) Wipe heuristics (empty prefetch / cleared logs / wipe cmds) + cheat
        if wipes and cheats:
            hits.append(
                _RuleHit(
                    title="Correlated: evidence wipe + cheat traces",
                    description=(
                        "System shows log/prefetch/history clearing alongside cheat-related findings. "
                        "Strong indicator the user tried to erase cheat evidence."
                    ),
                    severity=Severity.CRITICAL,
                    category=Category.CLEANER,
                    evidence=(
                        f"Wipe signals ({len(wipes)}): "
                        + ", ".join(sorted({f.signature or f.title for f in wipes})[:5])
                        + f" | Cheat findings: {len(cheats)}"
                    ),
                    signature="corr_wipe_plus_cheat",
                )
            )

        # 3) Same cheat brand across multiple evidence sources
        brand_sources: dict[str, set[str]] = {}
        for f in findings:
            blob = _blob(f)
            brands = _brands_in(blob, CHEAT_BRANDS)
            if not brands:
                continue
            source = "other"
            if _is_execution(f):
                source = "execution"
            elif _is_browser(f):
                source = "browser"
            elif _is_file_artifact(f):
                source = "file"
            elif _is_cleaner(f):
                source = "cleaner"
            for brand in brands:
                brand_sources.setdefault(brand, set()).add(source)

        multi_brand = {b: srcs for b, srcs in brand_sources.items() if len(srcs) >= 2}
        if multi_brand:
            detail = "; ".join(
                f"{brand} via {', '.join(sorted(srcs))}" for brand, srcs in sorted(multi_brand.items())[:5]
            )
            hits.append(
                _RuleHit(
                    title="Correlated: same cheat brand across multiple sources",
                    description=(
                        "The same cheat family appears in more than one evidence type "
                        "(execution, files, browser, or cleaner). Harder to dismiss as coincidence."
                    ),
                    severity=Severity.CRITICAL,
                    category=Category.CHEAT,
                    evidence=detail,
                    signature="corr_multi_source_brand",
                )
            )

        # 4) Execution evidence (prefetch/BAM/process) but file artifact also present for same token
        #    OR execution for a name that looks deleted (execution without matching file path)
        exec_tokens: set[str] = set()
        file_tokens: set[str] = set()
        for f in executions:
            exec_tokens |= _brands_in(_blob(f), CHEAT_BRANDS)
            exec_tokens |= _stem_tokens(f.path)
            exec_tokens |= _stem_tokens(f.evidence)
        for f in files:
            file_tokens |= _brands_in(_blob(f), CHEAT_BRANDS)
            file_tokens |= _stem_tokens(f.path)

        shared = {t for t in exec_tokens & file_tokens if len(t) >= 4}
        # Prefer brand overlaps for this rule
        shared_brands = shared & set(CHEAT_BRANDS)
        if shared_brands:
            hits.append(
                _RuleHit(
                    title="Correlated: cheat executed and still present on disk",
                    description=(
                        "Prefetch/BAM/process evidence matches on-disk cheat artifacts for the same brand."
                    ),
                    severity=Severity.CRITICAL,
                    category=Category.CHEAT,
                    evidence="Brands: " + ", ".join(sorted(shared_brands)[:6]),
                    signature="corr_exec_and_disk",
                )
            )

        # 5) Browser cheat site + packed/random PE or file hit
        if browsers and files:
            hits.append(
                _RuleHit(
                    title="Correlated: cheat website visit + on-disk loader",
                    description=(
                        "Browser history shows a known cheat provider and matching or suspicious "
                        "loader/files were found on disk."
                    ),
                    severity=Severity.HIGH,
                    category=Category.CHEAT,
                    evidence=(
                        f"Sites/visits: {len(browsers)} | Disk/PE/RPF hits: {len(files)}"
                    ),
                    signature="corr_browser_plus_disk",
                )
            )

        # 6) Bypass/spoofer + cleaner cluster (screenshare / HWID wipe before check)
        if bypasses and (cleaners or wipes):
            hits.append(
                _RuleHit(
                    title="Correlated: bypass/spoofer + cleaner toolkit",
                    description=(
                        "Bypass or spoofer tools appear together with cleaner/wipe activity — "
                        "typical anti-PC-check toolkit."
                    ),
                    severity=Severity.HIGH,
                    category=Category.BYPASS,
                    evidence=(
                        f"Bypass findings: {len(bypasses)} | "
                        f"Cleaner/wipe findings: {len(cleaners) + len(wipes)}"
                    ),
                    signature="corr_bypass_cleaner_kit",
                )
            )

        # 7) Multiple independent wipe signals (even without named cheat)
        if len(wipes) >= 2:
            hits.append(
                _RuleHit(
                    title="Correlated: multiple anti-forensic wipe signals",
                    description=(
                        "Several independent wipe/clear indicators were found "
                        "(prefetch, event logs, PowerShell history, or wipe commands)."
                    ),
                    severity=Severity.HIGH,
                    category=Category.CLEANER,
                    evidence=", ".join(sorted({f.signature or f.title for f in wipes})[:6]),
                    signature="corr_multi_wipe",
                )
            )

        # 8) Cleaner brand executed (prefetch) + recycle bin / hide-spot cleaner file
        cleaner_exec = [f for f in cleaners if _is_execution(f)]
        cleaner_files = [f for f in cleaners if _is_file_artifact(f) or "recycle" in _blob(f)]
        if cleaner_exec and cleaner_files:
            hits.append(
                _RuleHit(
                    title="Correlated: cleaner tool executed + cleaner remnants",
                    description=(
                        "A cleaner/bypass tool was executed and leftover cleaner files/artifacts remain."
                    ),
                    severity=Severity.CRITICAL,
                    category=Category.CLEANER,
                    evidence=(
                        f"Executed: {cleaner_exec[0].title} | Remnants: {cleaner_files[0].title}"
                    ),
                    signature="corr_cleaner_exec_remnant",
                )
            )

        # 9) Injection + FiveM context + any wipe/cleaner
        injections = [f for f in findings if f.category == Category.INJECTION]
        fivem_hits = [f for f in findings if f.category == Category.FIVEM]
        if injections and (cleaners or wipes or fivem_hits):
            hits.append(
                _RuleHit(
                    title="Correlated: injection technique + cover-up or FiveM context",
                    description=(
                        "Injection/mapper indicators appear with FiveM artifacts and/or cleaner activity."
                    ),
                    severity=Severity.CRITICAL,
                    category=Category.INJECTION,
                    evidence=(
                        f"Injection: {len(injections)} | FiveM: {len(fivem_hits)} | "
                        f"Cleaner/wipe: {len(cleaners) + len(wipes)}"
                    ),
                    signature="corr_injection_cover",
                )
            )

        return hits


def apply_correlations(result: ScanResult) -> list[Finding]:
    """Public helper used by ScanEngine."""
    return CorrelationEngine().apply(result)
