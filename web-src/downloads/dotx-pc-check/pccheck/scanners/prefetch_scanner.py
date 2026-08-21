from __future__ import annotations

import winreg
from pathlib import Path

from pccheck.models import Category, Finding, ScanResult, Severity
from pccheck.signatures import CHEAT_FILE_SIGNATURES, CLEANER_FILE_SIGNATURES, SUSPICIOUS_FILENAMES
from pccheck.utils.pe import is_random_cheat_filename

PREFETCH_DIR = Path(r"C:\Windows\Prefetch")


def _prefetch_enabled() -> bool:
    try:
        with winreg.OpenKey(
            winreg.HKEY_LOCAL_MACHINE,
            r"SYSTEM\CurrentControlSet\Control\Session Manager\Memory Management\PrefetchParameters",
        ) as key:
            val, _ = winreg.QueryValueEx(key, "EnablePrefetcher")
            return int(val) != 0
    except OSError:
        return True  # assume enabled if we cannot read


class PrefetchScanner:
    name = "Prefetch Scanner"

    def scan(self, result: ScanResult) -> None:
        if not PREFETCH_DIR.exists():
            result.errors.append("Prefetch directory not accessible")
            return

        try:
            pf_files = list(PREFETCH_DIR.glob("*.pf"))
        except (OSError, PermissionError) as exc:
            result.errors.append(f"Prefetch read error: {exc}")
            return

        if len(pf_files) < 5 and _prefetch_enabled():
            result.add(
                Finding(
                    title="Prefetch folder suspiciously empty",
                    description="Very few Prefetch files — may indicate prefetch clearing (anti-forensic)",
                    severity=Severity.HIGH,
                    category=Category.CLEANER,
                    evidence=f"Only {len(pf_files)} .pf files found in {PREFETCH_DIR}",
                    path=str(PREFETCH_DIR),
                    signature="prefetch_clearing",
                )
            )

        seen: set[str] = set()
        all_sigs = CHEAT_FILE_SIGNATURES + CLEANER_FILE_SIGNATURES

        for pf in pf_files:
            lower = pf.name.lower()
            # Random-name prefetch (SZ05E.EXE-*.pf) — survives cheat rename at runtime
            base = lower.split("-")[0] if "-" in lower else lower.replace(".pf", "")
            if base.endswith(".exe") and is_random_cheat_filename(base):
                if pf.name not in seen:
                    seen.add(pf.name)
                    result.add(
                        Finding(
                            title="Random-name executable was run (Prefetch)",
                            description=(
                                "Prefetch proves a random-name exe (e.g. sz05e.exe) was executed — "
                                "cheats rename each run but Prefetch keeps the name used at launch"
                            ),
                            severity=Severity.CRITICAL,
                            category=Category.CHEAT,
                            evidence=pf.name,
                            path=str(pf),
                            signature="random_name_prefetch",
                        )
                    )

            for sig in all_sigs:
                for pattern in sig.patterns:
                    if pattern.lower() in lower and pf.name not in seen:
                        seen.add(pf.name)
                        result.add(
                            Finding(
                                title=f"Prefetch hit: {sig.name}",
                                description=f"Program was executed — Prefetch evidence for {sig.description}",
                                severity=sig.severity,
                                category=sig.category,
                                evidence=f"Prefetch file: {pf.name}",
                                path=str(pf),
                                signature=pattern,
                            )
                        )
                        break

            for sus in SUSPICIOUS_FILENAMES:
                if sus in lower and pf.name not in seen:
                    seen.add(pf.name)
                    result.add(
                        Finding(
                            title="Suspicious Prefetch entry",
                            description="Prefetch file name matches suspicious keyword",
                            severity=Severity.MEDIUM,
                            category=Category.SUSPICIOUS,
                            evidence=pf.name,
                            path=str(pf),
                            signature=sus,
                        )
                    )
                    break

        cleaner_hits = [
            f for f in pf_files
            if any(kw in f.name.lower() for kw in ("clean", "wiper", "9z", "bypass", "clear"))
        ]
        for pf in cleaner_hits:
            if pf.name not in seen:
                seen.add(pf.name)
                result.add(
                    Finding(
                        title="Cleaner tool in Prefetch",
                        description="A cleaner/bypass tool was executed on this system",
                        severity=Severity.CRITICAL,
                        category=Category.CLEANER,
                        evidence=pf.name,
                        path=str(pf),
                        signature="cleaner_prefetch",
                    )
                )
