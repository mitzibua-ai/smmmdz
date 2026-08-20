/** Dotx public Free Tools page — no login required */
(function () {
  const PANEL_EXE_URL = "/downloads/dotx-free-tools.exe";
  const PANEL_ZIP_URL = "/downloads/dotx-free-tools-panel.zip";
  const CATALOG_URL = "/downloads/free-tools/catalog.json";

  function escapeHtml(text) {
    return String(text)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function toolDownloadUrl(tool) {
    return tool.downloadUrl || tool.externalUrl || "";
  }

  function openDownload(url) {
    if (!url) return;
    if (/^https?:\/\//i.test(url)) {
      window.open(url, "_blank", "noopener,noreferrer");
      return;
    }
    const link = document.createElement("a");
    link.href = url;
    link.download = "";
    link.rel = "noopener";
    document.body.appendChild(link);
    link.click();
    link.remove();
  }

  function renderTools(tools) {
    const grid = document.getElementById("tools-grid");
    const countEl = document.getElementById("tools-count");
    const countLabel = document.getElementById("tools-count-label");
    if (!grid) return;

    if (countEl) countEl.textContent = String(tools.length);
    if (countLabel) countLabel.textContent = `${tools.length} tools`;

    grid.innerHTML = tools
      .map(function (tool, i) {
        const num = String(i + 1).padStart(2, "0");
        const featured = tool.badge === "SUITE" ? " tool-card--featured" : "";
        const url = toolDownloadUrl(tool);
        const badge = tool.badge
          ? `<span class="tool-card__tag" style="color:#fbbf24;background:rgba(245,158,11,0.15)">${escapeHtml(tool.badge)}</span>`
          : `<span class="tool-card__tag">${escapeHtml(tool.tag || "")}</span>`;
        const homepage = tool.homepage
          ? `<a class="tool-card__btn tool-card__btn--panel" href="${escapeHtml(tool.homepage)}" target="_blank" rel="noopener noreferrer">Official site</a>`
          : "";
        return (
          `<article class="tool-card${featured}" data-id="${escapeHtml(tool.id)}">` +
          `<div class="tool-card__num">${num} · Free Tools</div>` +
          badge +
          `<h3>${escapeHtml(tool.name)}</h3>` +
          `<p>${escapeHtml(tool.description || "")}</p>` +
          `<div class="tool-card__actions">` +
          `<a class="tool-card__btn" href="${escapeHtml(url)}" data-tool-url="${escapeHtml(url)}" target="_blank" rel="noopener noreferrer">Download</a>` +
          homepage +
          `</div></article>`
        );
      })
      .join("");

    grid.querySelectorAll("[data-tool-url]").forEach((link) => {
      link.addEventListener("click", (e) => {
        const url = link.getAttribute("data-tool-url") || "";
        if (!url) return;
        e.preventDefault();
        openDownload(url);
      });
    });
  }

  function bindPanel() {
    const panelBtn = document.getElementById("download-panel-btn");
    if (panelBtn) panelBtn.href = PANEL_EXE_URL;

    const zipBtn = document.getElementById("download-panel-zip");
    if (zipBtn) {
      zipBtn.href = PANEL_ZIP_URL;
      zipBtn.setAttribute("download", "");
    }
  }

  async function init() {
    bindPanel();
    try {
      const res = await fetch(CATALOG_URL, { cache: "no-store" });
      if (!res.ok) throw new Error("catalog unavailable");
      const data = await res.json();
      renderTools(Array.isArray(data.tools) ? data.tools : []);
    } catch {
      const grid = document.getElementById("tools-grid");
      if (grid) {
        grid.innerHTML =
          '<p class="tools-note">Could not load tools. <a href="/downloads/dotx-free-tools.exe">Download the panel EXE</a> instead.</p>';
      }
    }
  }

  document.addEventListener("DOMContentLoaded", init);
})();
