function escapeHtml(s) {
  return String(s)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function scanDisplayName(scan) {
  if (scan?.playerName && scan.playerName !== "—") return scan.playerName;
  const meta = parseReportMeta(scan?.reportText || "");
  if (meta.username && meta.username.toLowerCase() !== "unknown") return meta.username;
  if (scan?.hostname) return scan.hostname;
  if (scan?.username) return scan.username;
  if (meta.hostname) return meta.hostname;
  return "Unknown player";
}

function parseReportMeta(reportText) {
  const meta = {};
  if (!reportText) return meta;
  const pick = (re) => {
    const m = reportText.match(re);
    return m ? m[1].trim() : "";
  };
  meta.hostname = pick(/Computer\s*:\s*(.+)/i) || pick(/Hostname\s*:\s*(.+)/i);
  meta.username = pick(/User\s*:\s*(.+)/i) || pick(/Username\s*:\s*(.+)/i);
  meta.verdict = pick(/VERDICT\s*:\s*(.+)/i);
  meta.score = pick(/RISK SCORE\s*:\s*(\d+)/i);
  meta.findingCount = pick(/FINDINGS\s*:\s*(\d+)/i);
  meta.scanTime = pick(/Scan Time\s*:\s*(.+)/i);
  meta.modules = pick(/Modules Run\s*:\s*(.+)/i);
  meta.pin = pick(/dotx PIN:\s*(\d{6})/i);
  return meta;
}

function parseReportFindings(reportText) {
  if (!reportText) return [];
  const lines = reportText.split(/\r?\n/);
  const findings = [];
  let current = null;

  for (const line of lines) {
    const head = line.match(/^\[(\d+)\]\s*\[(CRITICAL|HIGH|MEDIUM|LOW)\]\s*(.+)$/i);
    if (head) {
      if (current) findings.push(current);
      current = {
        index: head[1],
        severity: head[2].toUpperCase(),
        title: head[3].trim(),
        category: "",
        description: "",
        evidence: "",
        path: "",
        signature: "",
      };
      continue;
    }
    if (!current) continue;
    const field = line.match(/^\s{4}([\w ]+?)\s*:\s*(.+)$/);
    if (!field) continue;
    const key = field[1].trim().toLowerCase();
    const value = field[2].trim();
    if (key === "category") current.category = value;
    else if (key === "description") current.description = value;
    else if (key === "evidence") current.evidence = value;
    else if (key === "path") current.path = value;
    else if (key === "signature") current.signature = value;
  }
  if (current) findings.push(current);
  return findings;
}

function findingSeverityClass(severity) {
  const s = String(severity).toUpperCase();
  if (s === "CRITICAL" || s === "HIGH") return "finding-card--high";
  if (s === "MEDIUM") return "finding-card--medium";
  return "finding-card--low";
}

function reportVerdictTone(verdict) {
  if (verdict === "passed" || verdict === "clean") return "report-hero--pass";
  if (verdict === "review" || verdict === "suspicious") return "report-hero--warn";
  return "report-hero--fail";
}

function buildReportDetailHtml(scan) {
  const name = scanDisplayName(scan);
  const meta = parseReportMeta(scan.reportText || "");
  const findings = parseReportFindings(scan.reportText || "");
  const threats = scan.threats ?? 0;
  const warnings = scan.warnings ?? 0;
  const hostname = scan.hostname || meta.hostname || "—";
  const username = scan.username || meta.username || "—";
  const score = meta.score || "—";
  const pin = scan.pin || meta.pin || "—";

  const findingsHtml = findings.length
    ? findings
        .map(
          (f) => `
        <article class="finding-card ${findingSeverityClass(f.severity)}">
          <div class="finding-card__head">
            <span class="finding-card__index">#${escapeHtml(f.index)}</span>
            <span class="finding-card__severity">${escapeHtml(f.severity)}</span>
            <h4 class="finding-card__title">${escapeHtml(f.title)}</h4>
          </div>
          ${f.category ? `<div class="finding-card__row"><span>Category</span><span>${escapeHtml(f.category)}</span></div>` : ""}
          ${f.description ? `<div class="finding-card__row"><span>Description</span><span>${escapeHtml(f.description)}</span></div>` : ""}
          ${f.evidence ? `<div class="finding-card__row finding-card__row--mono"><span>Evidence</span><span>${escapeHtml(f.evidence)}</span></div>` : ""}
          ${f.path ? `<div class="finding-card__row finding-card__row--mono"><span>Path</span><span>${escapeHtml(f.path)}</span></div>` : ""}
          ${f.signature ? `<div class="finding-card__row"><span>Signature</span><span>${escapeHtml(f.signature)}</span></div>` : ""}
        </article>
      `
        )
        .join("")
    : `<div class="report-empty-findings">No structured findings in this report.</div>`;

  return `
    <div class="report-hero ${reportVerdictTone(scan.verdict)}">
      <div class="report-hero__main">
        <div class="report-hero__eyebrow">PC Check Result</div>
        <h2 class="report-hero__name">${escapeHtml(name)}</h2>
        <div class="report-hero__meta">
          <span>PIN <code>${escapeHtml(pin)}</code></span>
          <span>${escapeHtml(formatDate(scan.date))}</span>
        </div>
      </div>
      <div class="report-hero__verdict">
        <span class="tag ${verdictClass(scan.verdict)} tag--lg">${escapeHtml(verdictLabel(scan.verdict))}</span>
        <div class="report-hero__score">Risk ${escapeHtml(String(score))}<span>/100</span></div>
      </div>
    </div>

    <div class="report-stats">
      <div class="report-stat report-stat--danger">
        <div class="report-stat__value">${threats}</div>
        <div class="report-stat__label">Threats</div>
      </div>
      <div class="report-stat report-stat--warn">
        <div class="report-stat__value">${warnings}</div>
        <div class="report-stat__label">Warnings</div>
      </div>
      <div class="report-stat">
        <div class="report-stat__value">${findings.length || meta.findingCount || 0}</div>
        <div class="report-stat__label">Findings</div>
      </div>
      <div class="report-stat">
        <div class="report-stat__value report-stat__value--sm">${escapeHtml(hostname)}</div>
        <div class="report-stat__label">Computer · ${escapeHtml(username)}</div>
      </div>
    </div>

    ${
      scan.summary
        ? `<div class="report-summary">${escapeHtml(scan.summary)}</div>`
        : ""
    }

    <div class="report-findings-head">
      <h3>Detections</h3>
      <span>${findings.length} item${findings.length === 1 ? "" : "s"}</span>
    </div>
    <div class="report-findings">${findingsHtml}</div>

    <details class="report-raw">
      <summary>View raw report</summary>
      <pre class="report-raw__body">${escapeHtml(scan.reportText || scan.summary || "No report text.")}</pre>
    </details>
  `;
}
