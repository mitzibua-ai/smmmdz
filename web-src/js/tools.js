/** Dot X Free Tools page */
(function () {
  const PANEL_URL = "/downloads/dotx-free-tools-panel.zip";
  const TOOLS_BASE = "/downloads/free-tools/";

  const TOOLS = [
    { id: "autoruns", name: "Autoruns++", tag: "Startup", file: "autoruns.zip", description: "Enhanced startup monitor with USN journal tracking, signature checks, and anomaly filters." },
    { id: "string-explorer", name: "StringExplorer++", tag: "PE Analysis", file: "string-explorer.zip", description: "Navigate executable strings, entropy, compile timestamps, and VirusTotal links." },
    { id: "prefetch", name: "WinPrefetchView++", tag: "Prefetch", file: "prefetch.zip", description: "Prefetch viewer with bypass detections, YARA rules, and pink USN modification flags." },
    { id: "usbdeview", name: "USBDeview++", tag: "USB / DMA", file: "usbdeview.zip", description: "Cross-reference USB logs, flag unverified firmware, and uncover cleaned device traces." },
    { id: "saved-files", name: "SavedFilesViewer++", tag: "Downloads", file: "saved-files.zip", description: "Local artifact viewer for files saved to disk with cleaner detections built in." },
    { id: "powershell", name: "PowerShellParser++", tag: "PowerShell", file: "powershell.zip", description: "Deep PowerShell history scraping with bypass filters and integrated protections." },
    { id: "paths", name: "PathsParser++", tag: "Paths", file: "paths.zip", description: "Multi-input path parser with YARA imports and visual USN journal highlighting." },
    { id: "mft", name: "MFTExplorer++", tag: "MFT", file: "mft.zip", description: "MFT viewer for ADS streams and historical file presence verification." },
    { id: "kernel-dump", name: "KernelLiveDump++", tag: "Memory", file: "kernel-dump.zip", description: "Kernel and user-mode RAM dumps with suspicious string toggles and custom search." },
    { id: "journal", name: "JournalTrace++", tag: "USN Journal", file: "journal.zip", description: "USN journal analysis with reason-code filters and bypass detections." },
    { id: "crash", name: "CrashedFileViewer++", tag: "Crash Logs", file: "crash.zip", description: "Unified Windows crash artifacts with USN highlights and log-clearing detection." },
    { id: "browser-history", name: "BrowsingHistoryView++", tag: "Browser", file: "browser-history.zip", description: "Multi-browser history with suspicious domain flags and VirusTotal integration." },
    { id: "browser-downloads", name: "BrowserDownloadsView++", tag: "Browser", file: "browser-downloads.zip", description: "Aggregated browser downloads with USN modification tracking and YARA scans." },
    { id: "bam", name: "BamParser++", tag: "Execution", file: "bam.zip", description: "BAM execution history with YARA engine, USN flags, and tamper detections." },
    { id: "amcache", name: "AmcacheParser++", tag: "Amcache", file: "amcache.zip", description: "High-performance Amcache parser with YARA, SHA1 filters, and VT integration." },
    { id: "srum", name: "SRUMExplorer++", tag: "Network", file: "srum.zip", description: "SRUM network usage mapping with YARA matching and USN journal tracking." },
  ];

  function escapeHtml(text) {
    return String(text)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function renderTools() {
    const grid = document.getElementById("tools-grid");
    const countEl = document.getElementById("tools-count");
    if (!grid) return;

    if (countEl) countEl.textContent = String(TOOLS.length);

    grid.innerHTML = TOOLS.map(function (tool, i) {
      const num = String(i + 1).padStart(2, "0");
      const url = TOOLS_BASE + tool.file;
      return (
        '<article class="tool-card" data-id="' + escapeHtml(tool.id) + '">' +
          '<div class="tool-card__num">' + num + " · dotx</div>" +
          '<span class="tool-card__tag">' + escapeHtml(tool.tag) + "</span>" +
          "<h3>" + escapeHtml(tool.name) + "</h3>" +
          "<p>" + escapeHtml(tool.description) + "</p>" +
          '<div class="tool-card__actions">' +
            '<a class="tool-card__btn" href="' + escapeHtml(url) + '" download>Download</a>' +
            '<a class="tool-card__btn tool-card__btn--panel" href="' + PANEL_URL + '" download>Via Panel</a>' +
          "</div>" +
        "</article>"
      );
    }).join("");
  }

  function bindPanel() {
    var panelBtn = document.getElementById("download-panel-btn");
    if (panelBtn) {
      panelBtn.href = PANEL_URL;
      panelBtn.setAttribute("download", "");
    }
  }

  document.addEventListener("DOMContentLoaded", function () {
    renderTools();
    bindPanel();
  });
})();
