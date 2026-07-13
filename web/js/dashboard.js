const cfg = window.SITE_CONFIG || { name: "dotx", tagline: "FiveM PC Check Platform", version: "1.0" };

let account = null;
let currentView = "overview";
let dataSyncTimer = null;
let lastGeneratedPin = null;
let pinModalBound = false;
let deletePinModalBound = false;
let pendingDeletePinId = null;
let selectedReportId = null;

function isPinModalOpen() {
  const pin = $("pin-modal");
  const del = $("delete-pin-modal");
  return (
    (pin && !pin.classList.contains("hidden")) ||
    (del && !del.classList.contains("hidden"))
  );
}

function refreshViewIfAllowed(view = currentView) {
  if (isPinModalOpen()) return;
  renderView(view);
}

function updatePinModalDownloadUrl(pinCode) {
  const shareUrl = getPinShareUrl(pinCode || lastGeneratedPin?.pin || "");
  const link = $("pin-modal-download");
  if (link) {
    link.href = shareUrl;
    link.textContent = shareUrl.replace(/^https?:\/\//, "");
  }
}

function openPinModal() {
  if (!isCustomerAccount(account)) return;
  updatePinModalDownloadUrl();
  $("pin-modal")?.classList.remove("hidden");
  $("pin-generated-box")?.classList.add("hidden");
  $("pin-modal-create")?.classList.remove("hidden");
  if ($("pin-player-name")) $("pin-player-name").value = "";
  if ($("pin-modal-title")) $("pin-modal-title").textContent = "Generate PIN";
  if ($("pin-modal-sub")) {
    $("pin-modal-sub").textContent = "Create a 6-digit PIN for a player PC check.";
  }
  lastGeneratedPin = null;
}

function closePinModal(refreshPins = false) {
  $("pin-modal")?.classList.add("hidden");
  if (refreshPins && lastGeneratedPin) {
    refreshViewIfAllowed("checks");
  }
}

function bindPinModalEvents() {
  if (pinModalBound) return;
  pinModalBound = true;

  $("pin-modal-card")?.addEventListener("click", (e) => e.stopPropagation());
  $("pin-modal-backdrop")?.addEventListener("click", () => closePinModal(true));
  $("pin-modal-close")?.addEventListener("click", () => closePinModal(true));

  $("pin-modal-create")?.addEventListener("click", async () => {
    if (!isCustomerAccount(account)) return;
    const playerName = $("pin-player-name")?.value.trim() || "—";
    const game = $("pin-game")?.value || "FiveM";
    const pin = addPin(account.discordId, { playerName, game });
    lastGeneratedPin = pin;

    try {
      await registerPinOnServer({
        id: pin.id,
        pin: pin.pin,
        discordId: account.discordId,
        playerName: pin.playerName,
        game: pin.game,
        date: pin.date,
      });
    } catch (err) {
      deletePin(account.discordId, pin.id);
      if (err?.code === "license_required") {
        alert("Customer license required to generate PINs.");
      } else {
        alert(apiFetchErrorMessage(err));
      }
      return;
    }

    $("pin-generated-code").textContent = pin.pin;
    $("pin-generated-box")?.classList.remove("hidden");
    $("pin-modal-create")?.classList.add("hidden");
    if ($("pin-modal-title")) $("pin-modal-title").textContent = "New PIN generated";
    if ($("pin-modal-sub")) {
      $("pin-modal-sub").textContent = "Send the player this download link. It only works with this PIN.";
    }
    updatePinModalDownloadUrl(pin.pin);
  });

  $("pin-modal-copy")?.addEventListener("click", () => {
    if (!lastGeneratedPin) return;
    copyPinCode(lastGeneratedPin.pin).then(() => {
      $("pin-modal-copy").textContent = "Copied!";
      setTimeout(() => { $("pin-modal-copy").textContent = "Copy PIN"; }, 1500);
    });
  });

  $("pin-modal-copy-link")?.addEventListener("click", () => {
    if (!lastGeneratedPin) return;
    copyPinShareLink(lastGeneratedPin.pin).then(() => {
      $("pin-modal-copy-link").textContent = "Copied!";
      setTimeout(() => { $("pin-modal-copy-link").textContent = "Copy link"; }, 1500);
    });
  });
}

function openDeletePinModal(pin) {
  pendingDeletePinId = pin.id;
  if ($("delete-pin-code")) $("delete-pin-code").textContent = pin.pin;
  const err = $("delete-pin-error");
  if (err) {
    err.textContent = "";
    err.classList.add("hidden");
  }
  const confirmBtn = $("delete-pin-confirm");
  if (confirmBtn) {
    confirmBtn.disabled = false;
    confirmBtn.textContent = "Delete PIN";
  }
  $("delete-pin-modal")?.classList.remove("hidden");
  closeAllActionMenus();
}

function closeDeletePinModal() {
  pendingDeletePinId = null;
  $("delete-pin-modal")?.classList.add("hidden");
}

function bindDeletePinModalEvents() {
  if (deletePinModalBound) return;
  deletePinModalBound = true;

  $("delete-pin-card")?.addEventListener("click", (e) => e.stopPropagation());
  $("delete-pin-backdrop")?.addEventListener("click", closeDeletePinModal);
  $("delete-pin-cancel")?.addEventListener("click", closeDeletePinModal);

  $("delete-pin-confirm")?.addEventListener("click", async () => {
    const pinId = pendingDeletePinId;
    if (!pinId) return;
    const btn = $("delete-pin-confirm");
    const errEl = $("delete-pin-error");
    if (btn) {
      btn.disabled = true;
      btn.textContent = "Deleting…";
    }
    try {
      const deletedCode = $("delete-pin-code")?.textContent;
      await deletePinEverywhere(account.discordId, pinId);
      closeDeletePinModal();
      if ($("pin-detail-code")?.textContent === deletedCode) {
        $("pin-detail")?.classList.add("hidden");
        $("pin-dropzone")?.classList.remove("hidden");
      }
      renderView("checks");
    } catch (err) {
      if (errEl) {
        errEl.textContent = err.message || "Could not delete pin.";
        errEl.classList.remove("hidden");
      }
      if (btn) {
        btn.disabled = false;
        btn.textContent = "Delete PIN";
      }
    }
  });
}

function $(id) {
  return document.getElementById(id);
}

function escapeHtml(s) {
  return String(s)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function isOwnerAccount(acc = account) {
  return typeof panelRole === "function" ? panelRole(acc) === "owner" : acc?.isOwner === true;
}

function updateOwnerNav(acc = account) {
  if (typeof updateRoleNav === "function") updateRoleNav(acc);
}

function renderProfile() {
  const status = isCustomerAccount(account) ? "Customer" : account.licensedStatus || account.plan || "Standard";
  const badge =
    status === "Customer"
      ? `<div class="profile__badge profile__badge--customer">${escapeHtml(status)}</div>`
      : `<div class="profile__badge">${escapeHtml(status)}</div>`;

  const role = typeof panelRole === "function" ? panelRole(account) : "member";
  const roleBadge =
    role !== "member"
      ? `<div class="profile__badge profile__badge--${role}">${escapeHtml(roleLabel ? roleLabel(role) : role)}</div>`
      : "";

  $("sidebar-user").innerHTML = `
    ${buildDiscordAvatarHtml(account, "sm")}
    <div class="profile__info">
      <div class="profile__name">${escapeHtml(account.username)}</div>
      <div class="profile__badges">${badge}${roleBadge}</div>
    </div>
  `;
}

function showLicenseActivatedToast(expiresLabel = "") {
  let toast = document.getElementById("license-activated-toast");
  if (!toast) {
    toast = document.createElement("div");
    toast.id = "license-activated-toast";
    toast.className = "license-toast";
    toast.innerHTML = `
      <div class="license-toast__icon">✓</div>
      <div class="license-toast__body">
        <div class="license-toast__title">Customer license active</div>
        <div class="license-toast__sub">Pins and Reports are unlocked.</div>
        <div class="license-toast__expiry"></div>
      </div>
    `;
    document.body.appendChild(toast);
  }
  const expiryEl = toast.querySelector(".license-toast__expiry");
  if (expiryEl) {
    expiryEl.textContent = expiresLabel ? `Valid until ${expiresLabel}` : "";
  }
  toast.classList.add("is-visible");
  window.clearTimeout(showLicenseActivatedToast._timer);
  showLicenseActivatedToast._timer = window.setTimeout(() => {
    toast.classList.remove("is-visible");
  }, 8000);
}

function handleLicenseUpdate(updated) {
  const prev = account?.licensedStatus;
  const prevRole = typeof panelRole === "function" ? panelRole(account) : account?.panelRole;
  const wasCustomer = isCustomerAccount(account);
  account = updated;

  if (account.licenseNeedsReauth) {
    showReauthBanner();
  } else {
    hideReauthBanner();
  }

  renderProfile();
  updateRoleNav(updated);
  updateLicenseNav(updated);

  const isCustomerNow = isCustomerAccount(account);
  const becameCustomer = isCustomerNow && !wasCustomer;
  const lostCustomer = !isCustomerNow && wasCustomer;

  if (becameCustomer) {
    if (typeof syncLicenseTimerMeta === "function") syncLicenseTimerMeta(account);
    showLicenseActivatedToast(formatLicenseExpiry(account));
    if (currentView === "account" && typeof startAccountLicenseTimer === "function") {
      startAccountLicenseTimer();
    }
    syncDashboardData(account.discordId)
      .then(() => {
        if (!isPinModalOpen()) renderView(currentView);
      })
      .catch(() => {});
  }

  if (lostCustomer && updated._licenseRevoked && account?.discordId) {
    account.licenseExpiresAt = null;
    account.licenseGrantedAt = null;
    account.licenseActive = false;
    saveAccount(account);
    localStorage.removeItem("dotx_license_timer_meta_v1");
    savePins(account.discordId, []);
    saveScans(account.discordId, []);
  }

  const requestedView = window.location.hash.replace("#", "") || currentView;
  if (requestedView !== currentView && ROLE_VIEWS.has(requestedView) && canAccessView(requestedView, account)) {
    renderView(requestedView);
    return;
  }

  if (ROLE_VIEWS.has(currentView) && !canAccessView(currentView, account)) {
    renderView("overview");
    return;
  }

  const roleChanged = (typeof panelRole === "function" ? panelRole(account) : account.panelRole) !== prevRole;
  if (ROLE_VIEWS.has(currentView)) {
    return;
  }

  if ((becameCustomer || lostCustomer || account.licensedStatus !== prev || updated._licenseChanged || roleChanged) && !isPinModalOpen()) {
    renderView(currentView);
  }
}

function showReauthBanner() {
  if (document.getElementById("license-reauth-banner")) return;

  const isBotMissing = account?.licenseError === "bot_not_configured";
  const isWrongServer = account?.licenseError === "wrong_server";
  const needsLogin =
    account?.licenseError === "oauth_expired" || account?.licenseError === "oauth_forbidden";
  const message = isWrongServer
    ? "Role sync needs serve.py. In the web folder run: python serve.py"
    : isBotMissing
      ? "Role sync needs a Discord bot. Add DISCORD_BOT_TOKEN to web/.env and run: python serve.py"
      : needsLogin
        ? account?.licenseMessage || "Sign out and log in again so dotx can read your Discord roles."
        : account?.licenseMessage || "Discord role sync needs a fresh login.";

  const banner = document.createElement("div");
  banner.id = "license-reauth-banner";
  banner.className = "license-reauth-banner";
  banner.innerHTML = `
    ${message}
    <button type="button" class="btn btn--ghost btn--small" id="license-reauth-btn">${isWrongServer || isBotMissing ? "OK" : "Sign in again"}</button>
  `;
  document.querySelector(".main")?.prepend(banner);
  document.getElementById("license-reauth-btn")?.addEventListener("click", () => {
    if (isWrongServer || isBotMissing) {
      banner.remove();
      return;
    }
    logout();
    window.location.href = "/login/";
  });
}

function hideReauthBanner() {
  document.getElementById("license-reauth-banner")?.remove();
}

function setActiveNav(view) {
  document.querySelectorAll(".nav__item").forEach((btn) => {
    const isActive = btn.dataset.view === view;
    btn.classList.toggle("is-active", isActive);
    btn.querySelector(".nav__icon").textContent = isActive ? "◆" : "◇";
  });
}

function barWidth(count, total) {
  if (!total) return "0%";
  return `${Math.round((count / total) * 100)}%`;
}

function licenseLockShell(contentHtml, { title = "Customer license required", hint = "Open a ticket in Discord. After payment, staff activates your key with smky license." } = {}) {
  if (isCustomerAccount(account)) return contentHtml;
  const expiry = formatLicenseExpiry(account);
  return `
    <div class="license-lock">
      <div class="license-lock__blur" inert>${contentHtml}</div>
      <div class="license-lock__gate">
        <div class="license-lock__shield" aria-hidden="true">🔒</div>
        <h2 class="license-lock__title">${escapeHtml(title)}</h2>
        <p class="license-lock__text">${escapeHtml(hint)}</p>
        <div class="license-lock__meta">
          <span class="badge badge--muted">${escapeHtml(account?.licensedStatus || account?.plan || "Standard")}</span>
          ${expiry ? `<span class="license-lock__expiry">Expired ${escapeHtml(expiry)}</span>` : ""}
        </div>
        
      </div>
    </div>
  `;
}

function renderOverview() {
  const unlocked = isCustomerAccount(account);
  const scans = unlocked ? getScans(account.discordId) : [];
  const stats = computeStats(scans);
  const recent = scans.slice(0, 5);

  return `
    <header class="page-header">
      <div>
        <h1>Hey, ${escapeHtml(account.username)}</h1>
        <p>Here’s what’s happening on your dotx panel today.</p>
      </div>
      <span class="badge">Build ${cfg.version}</span>
    </header>

    <section class="metrics">
      <div class="metric"><div class="metric__label">Checks run</div><div class="metric__value">${stats.total}</div></div>
      <div class="metric"><div class="metric__label">Threats found</div><div class="metric__value">${stats.threats}</div></div>
      <div class="metric"><div class="metric__label">Warnings</div><div class="metric__value">${stats.warnings}</div></div>
      <div class="metric"><div class="metric__label">Pass rate</div><div class="metric__value">${stats.passRate !== null ? stats.passRate + "%" : "—"}</div></div>
    </section>

    <section class="panels">
      <div class="panel">
        <div class="panel__head"><div><div class="panel__title">Check results</div><div class="panel__sub">Breakdown by outcome</div></div></div>
        <div class="panel__body">
          <div class="results">
            <div class="result-row">
              <span class="result-row__label">Passed</span>
              <div class="result-bar"><div class="result-bar__fill result-bar__fill--pass" style="width:${barWidth(stats.verdicts.passed, stats.total)}"></div></div>
              <span class="result-row__num">${stats.verdicts.passed}</span>
            </div>
            <div class="result-row">
              <span class="result-row__label">Review</span>
              <div class="result-bar"><div class="result-bar__fill result-bar__fill--warn" style="width:${barWidth(stats.verdicts.review, stats.total)}"></div></div>
              <span class="result-row__num">${stats.verdicts.review}</span>
            </div>
            <div class="result-row">
              <span class="result-row__label">Failed</span>
              <div class="result-bar"><div class="result-bar__fill result-bar__fill--fail" style="width:${barWidth(stats.verdicts.failed, stats.total)}"></div></div>
              <span class="result-row__num">${stats.verdicts.failed}</span>
            </div>
          </div>
        </div>
      </div>
      <div class="panel">
        <div class="panel__head"><div><div class="panel__title">Quick actions</div><div class="panel__sub">Start working</div></div></div>
        <div class="panel__body action-list">
          <button class="btn btn--primary action-btn${unlocked ? "" : " is-locked"}" data-goto="checks" ${unlocked ? "" : "disabled"}>Generate PIN</button>
          <button class="btn action-btn${unlocked ? "" : " is-locked"}" data-goto="reports" ${unlocked ? "" : "disabled"}>View Reports</button>
          <button class="btn btn--ghost action-btn" data-goto="account">My Discord profile</button>
        </div>
      </div>
    </section>

    <section class="panels panels--bottom">
      <div class="panel">
        <div class="panel__head"><div><div class="panel__title">Recent checks</div><div class="panel__sub">Latest sessions</div></div></div>
        ${unlocked
          ? (recent.length ? `<div class="scan-table">${recent.map(renderScanRow).join("")}</div>` : `<div class="empty-state">No checks yet. Go to PC Checks to start one.</div>`)
          : `<div class="license-lock license-lock--inline"><div class="license-lock__gate license-lock__gate--compact"><div class="license-lock__shield">🔒</div><p>Recent checks unlock with a Customer license.</p></div></div>`
        }
      </div>
      <div class="panel">
        <div class="panel__head"><div><div class="panel__title">Discord profile</div><div class="panel__sub">Linked account</div></div></div>
        <div class="discord-card">
          ${buildDiscordProfileCard(account, { compact: true })}
        </div>
      </div>
    </section>
  `;
}

function renderScanRow(scan) {
  const pinLabel = scan.pin ? ` · PIN ${escapeHtml(scan.pin)}` : "";
  return `
    <div class="scan-row scan-row--clickable" data-scan-id="${scan.id}">
      <div>
        <div class="scan-row__name">${escapeHtml(scan.playerName)}</div>
        <div class="scan-row__date">${formatDate(scan.date)}${pinLabel}</div>
      </div>
      <span class="tag ${verdictClass(scan.verdict)}">${verdictLabel(scan.verdict)}</span>
    </div>
  `;
}

function openReportDetail(scanId) {
  const scan = getScan(account.discordId, scanId);
  if (!scan) return null;
  selectedReportId = scanId;

  document.querySelectorAll(".report-item").forEach((el) => {
    el.classList.toggle("is-active", el.dataset.reportId === scanId);
  });

  const empty = $("report-detail-empty");
  const content = $("report-detail-content");
  if (empty) empty.classList.add("hidden");
  if (content) {
    content.classList.remove("hidden");
    content.innerHTML = buildReportDetailHtml(scan);
  }
  return scan;
}

function clearReportDetail() {
  selectedReportId = null;
  document.querySelectorAll(".report-item").forEach((el) => el.classList.remove("is-active"));
  $("report-detail-empty")?.classList.remove("hidden");
  $("report-detail-content")?.classList.add("hidden");
  if ($("report-detail-content")) $("report-detail-content").innerHTML = "";
}

function renderReportItem(scan, active) {
  const name = scanDisplayName(scan);
  return `
    <button type="button" class="report-item${active ? " is-active" : ""}" data-report-id="${scan.id}">
      <div class="report-item__row">
        <span class="report-item__name">${escapeHtml(name)}</span>
        <span class="tag ${verdictClass(scan.verdict)}">${escapeHtml(verdictLabel(scan.verdict))}</span>
      </div>
      <div class="report-item__meta">${formatDate(scan.date)} · PIN ${escapeHtml(scan.pin || "—")}</div>
      <div class="report-item__counts">
        <span class="report-item__count report-item__count--danger">${scan.threats || 0} threats</span>
        <span class="report-item__count">${scan.warnings || 0} warnings</span>
      </div>
    </button>
  `;
}

function renderChecks() {
  const unlocked = isCustomerAccount(account);
  const pins = unlocked ? getPins(account.discordId) : [];
  const stats = computePinStats(pins);

  return licenseLockShell(`
    <nav class="breadcrumb">
      <a href="#overview" data-goto="overview">dashboard</a>
      <span class="breadcrumb__sep">›</span>
      <span>pins</span>
    </nav>

    <header class="page-header page-header--pins">
      <div>
        <h1>All your generated pins</h1>
        <p>Generate PINs for screenshares and track scan results.</p>
      </div>
    </header>

    <section class="pin-metrics">
      <div class="pin-metric">
        <div class="pin-metric__icon pin-metric__icon--total">▣</div>
        <div>
          <div class="pin-metric__label">Total</div>
          <div class="pin-metric__value">${stats.total}</div>
        </div>
      </div>
      <div class="pin-metric">
        <div class="pin-metric__icon pin-metric__icon--pending">◷</div>
        <div>
          <div class="pin-metric__label">Pending</div>
          <div class="pin-metric__value">${stats.pending}</div>
        </div>
      </div>
      <div class="pin-metric">
        <div class="pin-metric__icon pin-metric__icon--finished">✓</div>
        <div>
          <div class="pin-metric__label">Finished</div>
          <div class="pin-metric__value">${stats.finished}</div>
        </div>
      </div>
      <div class="pin-metric">
        <div class="pin-metric__icon pin-metric__icon--cheated">!</div>
        <div>
          <div class="pin-metric__label">Cheated</div>
          <div class="pin-metric__value">${stats.cheated}</div>
        </div>
      </div>
    </section>

    <section class="pin-layout">
      <div class="panel pin-table-panel">
        <div class="panel__head pin-table-panel__head">
          <div><div class="panel__title">All Pins</div></div>
          <div class="pin-filters">
            <input class="form__input form__input--inline" id="pin-search" type="search" placeholder="Search..." />
            <select class="form__input form__input--inline" id="pin-filter-status">
              <option value="all">All statuses</option>
              <option value="pending">Pending</option>
              <option value="finished">Finished</option>
              <option value="cheated">Cheated</option>
            </select>
            <select class="form__input form__input--inline" id="pin-filter-game">
              <option value="all">All games</option>
              <option value="FiveM">FiveM</option>
            </select>
          </div>
        </div>

        <div class="pin-table-wrap">
          <table class="pin-table">
            <thead>
              <tr>
                <th>Scanned user</th>
                <th>PIN</th>
                <th>Result</th>
                <th>Game</th>
                <th>Created <span class="pin-sort">↕</span></th>
                <th>Action</th>
              </tr>
            </thead>
            <tbody id="pin-table-body">
              ${pins.length ? pins.map(renderPinRow).join("") : `
                <tr><td colspan="6" class="pin-table__empty">No pins found matching your filters.</td></tr>
              `}
            </tbody>
          </table>
        </div>

        <div class="pin-table-footer">
          <span id="pin-count-label">Showing ${pins.length ? `1 to ${pins.length}` : "0 to 0"} of ${pins.length} pins</span>
        </div>
      </div>

      <aside class="panel pin-quick-actions">
        <div class="panel__head">
          <div><div class="panel__title">Quick Actions</div></div>
        </div>
        <div class="panel__body pin-quick-actions__body">
          <button type="button" class="btn btn--primary btn--block" id="generate-pin-btn">Generate New PIN</button>

          <div class="pin-dropzone" id="pin-dropzone">
            <div class="pin-dropzone__text">
              Double click a PIN to view its detailed scan results
              <span>OR DRAG AND DROP IT HERE</span>
            </div>
          </div>

          <div id="pin-detail" class="pin-detail hidden">
            <div class="pin-detail__label">Selected PIN</div>
            <div class="pin-detail__code" id="pin-detail-code">—</div>
            <div class="pin-detail__meta" id="pin-detail-meta"></div>
            <div class="pin-detail__actions">
              <button type="button" class="btn btn--ghost btn--small" id="pin-copy-btn">Copy PIN</button>
              <button type="button" class="btn btn--primary btn--small hidden" id="pin-view-result-btn">View result</button>
              <a class="btn btn--small pin-download-link" id="pin-download-btn" href="/downloads/" target="_blank" rel="noopener">Open download link</a>
            </div>
          </div>
        </div>
      </aside>
    </section>
  `, {
    title: "locked",
    hint: "",
  });
}

function renderPinRow(pin) {
  const shareUrl = getPinShareUrl(pin.pin);
  const resultItem = pin.scanId
    ? `<button type="button" class="action-menu__item pin-result-action" data-scan-id="${escapeHtml(pin.scanId)}" role="menuitem">View result</button>`
    : "";
  return `
    <tr class="pin-row" data-pin-id="${pin.id}" data-status="${pin.status}" data-game="${escapeHtml(pin.game)}">
      <td>${escapeHtml(pin.playerName)}</td>
      <td><code class="pin-code">${escapeHtml(pin.pin)}</code></td>
      <td><span class="pin-tag ${pinResultClass(pin.result)}">${escapeHtml(pin.result)}</span></td>
      <td>${escapeHtml(pin.game)}</td>
      <td>${formatDate(pin.date)}</td>
      <td class="pin-actions">
        <div class="action-menu">
          <button type="button" class="action-menu__trigger" aria-label="Pin actions" aria-haspopup="true" aria-expanded="false">
            <span class="action-menu__dots" aria-hidden="true"><span></span><span></span><span></span></span>
          </button>
          <div class="action-menu__dropdown hidden" role="menu">
            <button type="button" class="action-menu__item pin-copy-action" data-pin="${escapeHtml(pin.pin)}" role="menuitem">Copy PIN</button>
            <a class="action-menu__item pin-download-link" href="${escapeHtml(shareUrl)}" target="_blank" rel="noopener" role="menuitem">Open download link</a>
            ${resultItem}
            <div class="action-menu__sep"></div>
            <button type="button" class="action-menu__item action-menu__item--danger pin-delete-action" data-pin-id="${escapeHtml(pin.id)}" role="menuitem">Delete</button>
          </div>
        </div>
      </td>
    </tr>
  `;
}

function closeAllActionMenus() {
  document.querySelectorAll(".action-menu__dropdown").forEach((menu) => menu.classList.add("hidden"));
  document.querySelectorAll(".action-menu__trigger").forEach((trigger) => {
    trigger.setAttribute("aria-expanded", "false");
  });
}

function renderReports() {
  const unlocked = isCustomerAccount(account);
  const scans = unlocked ? getScans(account.discordId) : [];
  const stats = computeStats(scans);
  if (!selectedReportId && scans.length) {
    selectedReportId = scans[0].id;
  }
  if (selectedReportId && !scans.some((s) => s.id === selectedReportId)) {
    selectedReportId = scans[0]?.id || null;
  }

  return licenseLockShell(`
    <header class="page-header page-header--reports">
      <div>
        <h1>Reports</h1>
        <p>View scan results, detections, and download full reports.</p>
      </div>
    </header>

    <section class="report-metrics">
      <div class="pin-metric">
        <div class="pin-metric__icon pin-metric__icon--total">▣</div>
        <div>
          <div class="pin-metric__label">Total scans</div>
          <div class="pin-metric__value">${stats.total}</div>
        </div>
      </div>
      <div class="pin-metric">
        <div class="pin-metric__icon pin-metric__icon--finished">✓</div>
        <div>
          <div class="pin-metric__label">Passed</div>
          <div class="pin-metric__value">${stats.verdicts.passed}</div>
        </div>
      </div>
      <div class="pin-metric">
        <div class="pin-metric__icon pin-metric__icon--pending">◷</div>
        <div>
          <div class="pin-metric__label">Review</div>
          <div class="pin-metric__value">${stats.verdicts.review}</div>
        </div>
      </div>
      <div class="pin-metric">
        <div class="pin-metric__icon pin-metric__icon--cheated">!</div>
        <div>
          <div class="pin-metric__label">Failed</div>
          <div class="pin-metric__value">${stats.verdicts.failed}</div>
        </div>
      </div>
    </section>

    <section class="reports-layout">
      <aside class="panel reports-list">
        <div class="panel__head reports-list__head">
          <div><div class="panel__title">All reports</div><div class="panel__sub">${scans.length} saved</div></div>
          <input class="form__input form__input--inline" id="report-search" type="search" placeholder="Search..." />
        </div>
        ${
          scans.length
            ? `<div class="reports-list__items" id="report-list">${scans
                .map((s) => renderReportItem(s, s.id === selectedReportId))
                .join("")}</div>`
            : `<div class="empty-state">No reports yet. Run a PC check first.</div>`
        }
      </aside>

      <div class="panel reports-detail" id="report-detail">
        <div class="reports-detail__toolbar">
          <div class="reports-detail__toolbar-title">Report details</div>
          <div class="reports-detail__toolbar-actions">
            <button type="button" class="btn btn--ghost btn--small" id="download-report" ${scans.length ? "" : "disabled"}>Download</button>
            <button type="button" class="btn btn--ghost btn--small" id="close-report" ${scans.length ? "" : "disabled"}>Clear</button>
          </div>
        </div>
        <div class="reports-detail__body">
          <div id="report-detail-empty" class="report-detail-empty${scans.length && selectedReportId ? " hidden" : ""}">
            <div class="report-detail-empty__icon">◇</div>
            <h3>No report selected</h3>
            <p>Choose a scan from the list to view detections and verdict details.</p>
          </div>
          <div id="report-detail-content" class="report-detail-content${scans.length && selectedReportId ? "" : " hidden"}"></div>
        </div>
      </div>
    </section>
  `, {
    title: "LOCKED",
    hint: "",
  });
}

function formatMemberSince(acc) {
  const ts = acc?.createdAt;
  if (!ts) return "—";
  const date = new Date(ts);
  if (Number.isNaN(date.getTime())) return "—";
  return date.toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" });
}

function accountRoleLabel(acc = account) {
  const role = typeof panelRole === "function" ? panelRole(acc) : acc?.panelRole || "member";
  const map = {
    owner: "Owner",
    admin: "Admin",
    staff: "Staff",
    member: "Member",
  };
  return map[role] || "Member";
}

function renderAccount() {
  const acc = account;

  return `
    <div class="account-page">
      <section class="account-panels account-panels--premium">
        <div class="account-panel account-panel--profile">
          <div class="account-panel__head">
            <div>
              <div class="account-panel__title">Discord profile</div>
              <div class="account-panel__sub">Live avatar, banner, and decoration</div>
            </div>
            <button type="button" class="btn btn--ghost btn--small" id="refresh-profile">Refresh</button>
          </div>
          <div class="account-panel__body account-panel__body--flush">
            ${buildDiscordProfileCard(acc)}
          </div>
        </div>

        <div class="account-panel account-panel--security">
          <div class="account-panel__head">
            <div>
              <div class="account-panel__title">Security & sync</div>
              <div class="account-panel__sub">One Discord · server-backed license</div>
            </div>
            <button type="button" class="btn btn--ghost btn--small" id="copy-discord-id">Copy Discord ID</button>
          </div>
          <div class="account-panel__body">
            <div class="account-kv">
              <div class="account-kv__row">
                <span class="account-kv__k">Discord ID</span>
                <span class="account-kv__v mono" id="account-discord-id">${escapeHtml(acc.discordId)}</span>
              </div>
              <div class="account-kv__row">
                <span class="account-kv__k">Join</span>
                <span class="account-kv__v account-kv__v--join">${escapeHtml(formatJoinDate(acc))}</span>
              </div>
              <div class="account-kv__row">
                <span class="account-kv__k">License expire in</span>
                <span class="account-kv__v">${buildLicenseExpireCountdownHtml(acc)}</span>
              </div>
            </div>
            <p class="account-panel__note">Join date is permanent from your first login. The license countdown runs in real time from the server expiry — close the browser and it stays accurate when you return.</p>
          </div>
        </div>
      </section>
    </div>
  `;
}

function renderPlaceholder(title, desc) {
  return `
    <header class="page-header">
      <div><h1>${title}</h1><p>${desc}</p></div>
    </header>
    <div class="panel"><div class="empty-state">Coming soon.</div></div>
  `;
}

function renderView(view) {
  if (currentView === "account" && view !== "account") {
    stopAccountLicenseTimer();
  }

  if (!canAccessView(view, account)) {
    view = "overview";
    window.location.hash = "overview";
  }

  currentView = view;
  setActiveNav(view);

  const views = {
    overview: renderOverview,
    checks: renderChecks,
    reports: renderReports,
    account: renderAccount,
    owner: () => renderTeamView("owner"),
    admin: () => renderTeamView("admin"),
    staff: () => renderTeamView("staff"),
    signatures: () => renderPlaceholder("Signatures", "Manage cheat detection signatures."),
    help: () => renderPlaceholder("Help", "Guides and support for dotx."),
    billing: () => renderPlaceholder("Billing", "Plans and payments."),
  };

  $("main-content").innerHTML = (views[view] || views.overview)();
  bindViewEvents(view);

  if (view === "owner") initTeamView("owner");
  if (view === "admin") initTeamView("admin");
  if (view === "staff") initTeamView("staff");

  if (view === "account" || view === "overview") {
    applyLicensedStatus(getAccount()).then(handleLicenseUpdate).catch(() => {});
  }

  if (view === "account") {
    startAccountLicenseTimer();
  }
}

function bindViewEvents(view) {
  document.querySelectorAll("[data-goto]").forEach((btn) => {
    btn.addEventListener("click", () => {
      window.location.hash = btn.dataset.goto;
      renderView(btn.dataset.goto);
    });
  });

  if (view === "checks") bindChecksEvents();
  if (view === "reports") bindReportsEvents();
  if (view === "account") bindAccountEvents();
}

function bindAccountEvents() {
  $("refresh-profile")?.addEventListener("click", async () => {
    const btn = $("refresh-profile");
    btn.disabled = true;
    btn.textContent = "Refreshing…";
    try {
      account = await refreshDiscordProfile(account);
      handleLicenseUpdate(await applyLicensedStatus(account));
      renderView("account");
    } catch (err) {
      alert(err.message || "Could not refresh profile.");
      btn.disabled = false;
      btn.textContent = "Refresh";
    }
  });

  $("copy-discord-id")?.addEventListener("click", async () => {
    const id = account?.discordId;
    if (!id) return;
    try {
      await navigator.clipboard.writeText(id);
      const btn = $("copy-discord-id");
      if (btn) {
        btn.textContent = "Copied!";
        setTimeout(() => { btn.textContent = "Copy Discord ID"; }, 1500);
      }
    } catch {
      alert(id);
    }
  });
}

function bindChecksEvents() {
  let selectedPinId = null;

  function showPinDetail(pin) {
    if (!pin) return;
    selectedPinId = pin.id;
    $("pin-detail")?.classList.remove("hidden");
    $("pin-dropzone")?.classList.add("hidden");
    $("pin-detail-code").textContent = pin.pin;
    $("pin-detail-meta").innerHTML = `
      <div><strong>User:</strong> ${escapeHtml(pin.playerName)}</div>
      <div><strong>Result:</strong> ${escapeHtml(pin.result)}</div>
      <div><strong>Game:</strong> ${escapeHtml(pin.game)}</div>
      <div><strong>Created:</strong> ${formatDate(pin.date)}</div>
    `;
    const resultBtn = $("pin-view-result-btn");
    if (resultBtn) {
      if (pin.scanId) {
        resultBtn.classList.remove("hidden");
        resultBtn.dataset.scanId = pin.scanId;
      } else {
        resultBtn.classList.add("hidden");
        delete resultBtn.dataset.scanId;
      }
    }
    const downloadBtn = $("pin-download-btn");
    if (downloadBtn) {
      downloadBtn.href = getPinShareUrl(pin.pin);
    }
  }

  function filterPins() {
    const q = ($("pin-search")?.value || "").toLowerCase();
    const status = $("pin-filter-status")?.value || "all";
    const game = $("pin-filter-game")?.value || "all";
    let visible = 0;

    document.querySelectorAll(".pin-row").forEach((row) => {
      const text = row.textContent.toLowerCase();
      const rowStatus = row.dataset.status;
      const rowGame = row.dataset.game;
      const match =
        text.includes(q) &&
        (status === "all" || rowStatus === status) &&
        (game === "all" || rowGame === game);
      row.style.display = match ? "" : "none";
      if (match) visible++;
    });

    if ($("pin-count-label")) {
      const total = document.querySelectorAll(".pin-row").length;
      $("pin-count-label").textContent =
        total === 0
          ? "Showing 0 to 0 of 0 pins"
          : `Showing 1 to ${visible} of ${total} pins`;
    }
  }

  $("pin-search")?.addEventListener("input", filterPins);
  $("pin-filter-status")?.addEventListener("change", filterPins);
  $("pin-filter-game")?.addEventListener("change", filterPins);

  $("generate-pin-btn")?.addEventListener("click", openPinModal);

  $("pin-copy-btn")?.addEventListener("click", () => {
    const pin = getPin(account.discordId, selectedPinId);
    if (!pin) return;
    copyPinCode(pin.pin);
  });

  document.querySelectorAll(".pin-row").forEach((row) => {
    row.addEventListener("dblclick", () => {
      const pin = getPin(account.discordId, row.dataset.pinId);
      showPinDetail(pin);
    });
  });

  document.querySelectorAll(".action-menu__trigger").forEach((btn) => {
    btn.addEventListener("click", (e) => {
      e.stopPropagation();
      const dropdown = btn.closest(".action-menu")?.querySelector(".action-menu__dropdown");
      const wasOpen = dropdown && !dropdown.classList.contains("hidden");
      closeAllActionMenus();
      if (!wasOpen && dropdown) {
        dropdown.classList.remove("hidden");
        btn.setAttribute("aria-expanded", "true");
      }
    });
  });

  document.querySelectorAll(".pin-copy-action").forEach((btn) => {
    btn.addEventListener("click", (e) => {
      e.stopPropagation();
      copyPinCode(btn.dataset.pin);
      closeAllActionMenus();
    });
  });

  document.querySelectorAll(".pin-result-action").forEach((btn) => {
    btn.addEventListener("click", (e) => {
      e.stopPropagation();
      closeAllActionMenus();
      window.location.hash = "reports";
      renderView("reports");
      openReportDetail(btn.dataset.scanId);
    });
  });

  document.querySelectorAll(".pin-delete-action").forEach((btn) => {
    btn.addEventListener("click", (e) => {
      e.stopPropagation();
      const pin = getPin(account.discordId, btn.dataset.pinId);
      if (!pin) return;
      openDeletePinModal(pin);
    });
  });

  $("pin-view-result-btn")?.addEventListener("click", () => {
    const scanId = $("pin-view-result-btn")?.dataset.scanId;
    if (!scanId) return;
    window.location.hash = "reports";
    renderView("reports");
    openReportDetail(scanId);
  });

  const dropzone = $("pin-dropzone");
  dropzone?.addEventListener("dragover", (e) => {
    e.preventDefault();
    dropzone.classList.add("is-dragover");
  });
  dropzone?.addEventListener("dragleave", () => dropzone.classList.remove("is-dragover"));
  dropzone?.addEventListener("drop", (e) => {
    e.preventDefault();
    dropzone.classList.remove("is-dragover");
    const pinId = e.dataTransfer.getData("text/pin-id");
    if (pinId) showPinDetail(getPin(account.discordId, pinId));
  });

  document.querySelectorAll(".pin-row").forEach((row) => {
    row.setAttribute("draggable", "true");
    row.addEventListener("dragstart", (e) => {
      e.dataTransfer.setData("text/pin-id", row.dataset.pinId);
    });
  });

  filterPins();
}

function bindReportsEvents() {
  const search = $("report-search");
  const list = $("report-list");

  if (selectedReportId) {
    openReportDetail(selectedReportId);
  }

  search?.addEventListener("input", () => {
    const q = search.value.toLowerCase();
    list?.querySelectorAll(".report-item").forEach((row) => {
      const text = row.textContent.toLowerCase();
      row.style.display = text.includes(q) ? "" : "none";
    });
  });

  list?.querySelectorAll(".report-item").forEach((row) => {
    row.addEventListener("click", () => openReportDetail(row.dataset.reportId));
  });

  $("close-report")?.addEventListener("click", () => clearReportDetail());

  $("download-report")?.addEventListener("click", () => {
    const scan = getScan(account.discordId, selectedReportId);
    if (!scan) return;
    const name = scanDisplayName(scan).replace(/[^\w.-]+/g, "_");
    const blob = new Blob([scan.reportText || scan.summary || ""], { type: "text/plain" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = `dotx_report_${name}_${scan.id}.txt`;
    a.click();
    URL.revokeObjectURL(a.href);
  });
}

function showApiOfflineBanner() {
  const main = $("main-content");
  if (!main || document.getElementById("api-offline-banner")) return;
  const api = typeof apiBaseUrl === "function" ? apiBaseUrl() : "";
  const banner = document.createElement("div");
  banner.id = "api-offline-banner";
  banner.className = "alert";
  banner.innerHTML =
    "<strong>Supabase API is offline.</strong> Pins, scans, and downloads will not work until the Edge Function is deployed. " +
    "Run <code>push-supabase.bat</code> to deploy the API and sync your database." +
    (api ? `<br><span style="opacity:0.85">API: ${api}</span>` : "");
  main.prepend(banner);
}

function hideApiOfflineBanner() {
  document.getElementById("api-offline-banner")?.remove();
}

async function verifyApiStatus() {
  if (typeof checkApiOnline !== "function" || !isExternalApiConfigured()) return;
  const online = await checkApiOnline();
  if (online) {
    hideApiOfflineBanner();
  } else {
    showApiOfflineBanner();
  }
}

async function init() {
  document.title = `${cfg.name} — Panel`;
  account = getAccount();
  if (typeof hydrateLicenseTimerFromAccount === "function") {
    hydrateLicenseTimerFromAccount(account);
  }

  if (!account || !account.oauthLinked) {
    window.location.href = "/login/";
    return;
  }

  document.querySelectorAll(".nav__item[data-view]").forEach((btn) => {
    btn.addEventListener("click", () => {
      window.location.hash = btn.dataset.view;
      renderView(btn.dataset.view);
    });
  });

  $("logout-btn").addEventListener("click", () => {
    logout();
    window.location.href = "/login/";
  });

  renderProfile();
  updateRoleNav();
  updateLicenseNav();
  const hash = window.location.hash.replace("#", "");
  const initialView = canAccessView(hash, account) ? hash || "overview" : "overview";
  if (hash && !canAccessView(hash, account) && !ROLE_VIEWS.has(hash)) {
    window.location.hash = "overview";
  }
  renderView(initialView);

  bindPinModalEvents();
  bindDeletePinModalEvents();
  document.addEventListener("click", (e) => {
    if (!e.target.closest(".action-menu")) closeAllActionMenus();
  });
  refreshDashboardData().catch(() => {});
  registerUserOnServer(account).catch(() => {});
  verifyApiStatus();
  startDataSync();
  startLicenseSync(handleLicenseUpdate);
}

async function refreshDashboardData() {
  if (isDiscordSnowflake(account.discordId)) {
    try {
      account = await refreshDiscordProfile(account);
    } catch {
      if (!account.avatar) {
        account.avatar = discordAvatarUrl(account.discordId, account.avatarHash, 128);
        saveAccount(account);
      }
    }
  }

  try {
    handleLicenseUpdate(await applyLicensedStatus(account));
  } catch {
    // keep cached license status
  }

  await syncDashboardData(account.discordId);
  if (!ROLE_VIEWS.has(currentView)) {
    refreshViewIfAllowed(currentView);
  }
}

function startDataSync() {
  stopDataSync();
  const interval = cfg.dataSyncPollMs || 5000;
  dataSyncTimer = setInterval(async () => {
    const beforePins = JSON.stringify(getPins(account.discordId));
    const beforeScans = JSON.stringify(getScans(account.discordId));
    await syncDashboardData(account.discordId);
    const changed =
      beforePins !== JSON.stringify(getPins(account.discordId)) ||
      beforeScans !== JSON.stringify(getScans(account.discordId));
    if (changed && ["checks", "reports", "overview"].includes(currentView) && !ROLE_VIEWS.has(currentView)) {
      refreshViewIfAllowed(currentView);
    }
  }, interval);
}

function stopDataSync() {
  if (dataSyncTimer) {
    clearInterval(dataSyncTimer);
    dataSyncTimer = null;
  }
}

document.addEventListener("DOMContentLoaded", init);
