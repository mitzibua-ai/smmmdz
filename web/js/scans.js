const SCANS_KEY = "dotx_scans_v1";

function getScansKey(discordId) {
  return `${SCANS_KEY}_${discordId}`;
}

function getScans(discordId) {
  try {
    const raw = localStorage.getItem(getScansKey(discordId));
    return raw ? JSON.parse(raw) : [];
  } catch {
    return [];
  }
}

function saveScans(discordId, scans) {
  localStorage.setItem(getScansKey(discordId), JSON.stringify(scans));
}

function addScan(discordId, scan) {
  const scans = getScans(discordId);
  scans.unshift({
    id: `scan_${Date.now()}`,
    date: new Date().toISOString(),
    ...scan,
  });
  saveScans(discordId, scans);
  return scans;
}

function getScan(discordId, scanId) {
  return getScans(discordId).find((s) => s.id === scanId) || null;
}

function computeStats(scans) {
  const total = scans.length;
  let threats = 0;
  let warnings = 0;
  const verdicts = { passed: 0, review: 0, failed: 0 };

  for (const s of scans) {
    threats += s.threats || 0;
    warnings += s.warnings || 0;
    if (s.verdict === "passed" || s.verdict === "clean") verdicts.passed++;
    else if (s.verdict === "review" || s.verdict === "suspicious") verdicts.review++;
    else verdicts.failed++;
  }

  const passRate = total ? Math.round((verdicts.passed / total) * 100) : null;

  return { total, threats, warnings, verdicts, passRate };
}

function verdictLabel(v) {
  const map = {
    passed: "Passed",
    clean: "Clean",
    review: "Review",
    suspicious: "Suspicious",
    failed: "Failed",
  };
  return map[v] || v;
}

function verdictClass(v) {
  if (v === "passed" || v === "clean") return "tag--pass";
  if (v === "review" || v === "suspicious") return "tag--warn";
  return "tag--fail";
}

function formatDate(iso) {
  const d = new Date(iso);
  return d.toLocaleDateString(undefined, {
    month: "short",
    day: "numeric",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function simulateScan(playerName) {
  const outcomes = [
    { verdict: "passed", threats: 0, warnings: 0, summary: "No significant findings. System appears clean." },
    { verdict: "review", threats: 0, warnings: 2, summary: "Minor items flagged for manual review." },
    { verdict: "suspicious", threats: 1, warnings: 3, summary: "High-severity artifacts detected. Review recommended." },
    { verdict: "failed", threats: 3, warnings: 1, summary: "Critical cheat signatures found." },
  ];
  const pick = outcomes[Math.floor(Math.random() * outcomes.length)];
  return {
    playerName: playerName || "Unknown Player",
    verdict: pick.verdict,
    threats: pick.threats,
    warnings: pick.warnings,
    summary: pick.summary,
    reportText: `dotx PC Check Report\nPlayer: ${playerName || "Unknown"}\nVerdict: ${verdictLabel(pick.verdict)}\nThreats: ${pick.threats}\nWarnings: ${pick.warnings}\n\n${pick.summary}`,
  };
}

function parseImportedReport(text, playerName) {
  const lower = text.toLowerCase();
  let verdict = "review";
  if (lower.includes("cheating likely") || lower.includes("critical")) verdict = "failed";
  else if (lower.includes("suspicious")) verdict = "suspicious";
  else if (lower.includes("clean")) verdict = "passed";
  else if (lower.includes("review")) verdict = "review";

  const threatMatch = text.match(/critical|high/gi);
  const threats = threatMatch ? Math.min(threatMatch.length, 10) : 0;
  const warnMatch = text.match(/medium|warning/gi);
  const warnings = warnMatch ? Math.min(warnMatch.length, 10) : 0;

  return {
    playerName: playerName || "Imported scan",
    verdict,
    threats,
    warnings,
    summary: "Imported from scanner report file.",
    reportText: text,
  };
}
