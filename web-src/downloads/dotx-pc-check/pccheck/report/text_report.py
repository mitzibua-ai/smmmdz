from __future__ import annotations

from datetime import datetime, timezone

from pccheck.models import ScanResult, Severity


def build_text(result: ScanResult) -> str:
    data = result.to_dict()
    lines: list[str] = []
    sep = "=" * 62
    thin = "-" * 62

    lines.append(sep)
    lines.append("           FIVEM PC CHECK - SCAN RESULT")
    lines.append(sep)
    lines.append("")
    lines.append(f"Date/Time   : {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}")
    lines.append(f"Computer    : {data['hostname']}")
    lines.append(f"User        : {data['username']}")
    lines.append(f"Scan Time   : {data['scan_duration_sec']} seconds")
    lines.append(f"Modules Run : {', '.join(data['modules_run'])}")
    lines.append("")
    lines.append(sep)
    lines.append(f"  VERDICT     : {data['verdict']}")
    lines.append(f"  RISK SCORE  : {data['score']} / 100")
    lines.append(f"  FINDINGS    : {data['finding_count']}")
    lines.append(sep)
    lines.append("")

    if not result.findings:
        lines.append("No threats detected. System appears clean.")
    else:
        lines.append("DETECTIONS:")
        lines.append(thin)
        order = list(Severity)
        for i, finding in enumerate(
            sorted(result.findings, key=lambda f: order.index(f.severity)), start=1
        ):
            lines.append("")
            lines.append(f"[{i}] [{finding.severity.value.upper()}] {finding.title}")
            lines.append(f"    Category    : {finding.category.value}")
            lines.append(f"    Description : {finding.description}")
            lines.append(f"    Evidence    : {finding.evidence}")
            if finding.path:
                lines.append(f"    Path        : {finding.path}")
            if finding.signature:
                lines.append(f"    Signature   : {finding.signature}")

    if result.errors:
        lines.append("")
        lines.append(thin)
        lines.append("SCAN WARNINGS (some checks may need Admin):")
        for err in result.errors:
            lines.append(f"  - {err}")

    lines.append("")
    lines.append(sep)
    lines.append("Run as Administrator for full Prefetch / BAM / Registry access.")
    lines.append(sep)
    return "\r\n".join(lines) + "\r\n"
