from __future__ import annotations

import html
from pccheck.models import ScanResult, Severity

SEVERITY_COLORS = {
    Severity.CRITICAL: "#dc2626",
    Severity.HIGH: "#ea580c",
    Severity.MEDIUM: "#ca8a04",
    Severity.LOW: "#2563eb",
    Severity.INFO: "#6b7280",
}

VERDICT_COLORS = {
    "CHEATING LIKELY": "#dc2626",
    "SUSPICIOUS": "#ea580c",
    "REVIEW NEEDED": "#ca8a04",
    "CLEAN": "#16a34a",
}


def build_html(result: ScanResult) -> str:
    data = result.to_dict()
    verdict_color = VERDICT_COLORS.get(data["verdict"], "#6b7280")

    rows = ""
    for f in sorted(data["findings"], key=lambda x: list(SEVERITY_COLORS).index(
        next(s for s in Severity if s.value == x["severity"])
    )):
        color = SEVERITY_COLORS.get(Severity(f["severity"]), "#6b7280")
        rows += f"""
        <tr>
          <td><span class="badge" style="background:{color}">{html.escape(f['severity'].upper())}</span></td>
          <td>{html.escape(f['category'])}</td>
          <td><strong>{html.escape(f['title'])}</strong><br><small>{html.escape(f['description'])}</small></td>
          <td><code>{html.escape(f['evidence'][:120])}</code></td>
          <td><small>{html.escape(f.get('path', '')[:80])}</small></td>
        </tr>"""

    errors = "".join(f"<li>{html.escape(e)}</li>" for e in data["errors"])

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>FiveM PC Check Report</title>
  <style>
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{ font-family: 'Segoe UI', system-ui, sans-serif; background: #0f172a; color: #e2e8f0; padding: 2rem; }}
    .container {{ max-width: 1100px; margin: 0 auto; }}
    h1 {{ font-size: 1.8rem; margin-bottom: 0.5rem; }}
    .verdict {{ font-size: 2rem; font-weight: 700; color: {verdict_color}; margin: 1rem 0; }}
    .meta {{ display: flex; gap: 2rem; flex-wrap: wrap; margin: 1.5rem 0; }}
    .meta-card {{ background: #1e293b; border-radius: 8px; padding: 1rem 1.5rem; min-width: 140px; }}
    .meta-card .label {{ font-size: 0.75rem; color: #94a3b8; text-transform: uppercase; }}
    .meta-card .value {{ font-size: 1.4rem; font-weight: 600; margin-top: 0.25rem; }}
    table {{ width: 100%; border-collapse: collapse; margin-top: 1.5rem; }}
    th {{ background: #1e293b; text-align: left; padding: 0.75rem 1rem; font-size: 0.8rem; text-transform: uppercase; color: #94a3b8; }}
    td {{ padding: 0.75rem 1rem; border-bottom: 1px solid #1e293b; vertical-align: top; }}
    tr:hover td {{ background: #1e293b44; }}
    .badge {{ display: inline-block; padding: 2px 8px; border-radius: 4px; font-size: 0.7rem; font-weight: 700; color: white; }}
    code {{ background: #1e293b; padding: 2px 6px; border-radius: 4px; font-size: 0.85rem; }}
    .errors {{ background: #451a1a; border-radius: 8px; padding: 1rem; margin-top: 1.5rem; }}
    .modules {{ color: #94a3b8; font-size: 0.85rem; margin-top: 1rem; }}
  </style>
</head>
<body>
  <div class="container">
    <h1>FiveM PC Check Report</h1>
    <p style="color:#94a3b8">Forensic cheat &amp; cleaner detection scanner</p>
    <div class="verdict">{html.escape(data['verdict'])}</div>
    <div class="meta">
      <div class="meta-card"><div class="label">Risk Score</div><div class="value">{data['score']}/100</div></div>
      <div class="meta-card"><div class="label">Findings</div><div class="value">{data['finding_count']}</div></div>
      <div class="meta-card"><div class="label">Duration</div><div class="value">{data['scan_duration_sec']}s</div></div>
      <div class="meta-card"><div class="label">Host</div><div class="value" style="font-size:1rem">{html.escape(data['hostname'])}</div></div>
      <div class="meta-card"><div class="label">User</div><div class="value" style="font-size:1rem">{html.escape(data['username'])}</div></div>
    </div>
    <table>
      <thead>
        <tr><th>Severity</th><th>Category</th><th>Finding</th><th>Evidence</th><th>Path</th></tr>
      </thead>
      <tbody>{rows if rows else '<tr><td colspan="5" style="text-align:center;padding:2rem;color:#16a34a">No threats detected</td></tr>'}</tbody>
    </table>
    {'<div class="errors"><strong>Scan warnings:</strong><ul>' + errors + '</ul></div>' if errors else ''}
    <p class="modules">Modules: {html.escape(', '.join(data['modules_run']))}</p>
  </div>
</body>
</html>"""
