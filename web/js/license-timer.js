const LICENSE_TIMER_META_KEY = "dotx_license_timer_meta_v1";

function padTimerUnit(value) {
  return String(Math.max(0, value)).padStart(2, "0");
}

function getLicenseExpiryMs(acc) {
  const meta = readTimerMeta();
  const fromAccount = acc?.licenseExpiresAt;
  const fromMeta =
    meta?.discordId === String(acc?.discordId) ? meta?.expiresAt : null;
  const raw = fromAccount || fromMeta;
  if (!raw) return null;
  const ms = new Date(raw).getTime();
  return Number.isNaN(ms) ? null : ms;
}

function readTimerMeta() {
  try {
    return JSON.parse(localStorage.getItem(LICENSE_TIMER_META_KEY) || "null");
  } catch {
    return null;
  }
}

function writeTimerMeta(acc) {
  if (!acc?.discordId || !acc?.licenseExpiresAt || !isLicenseActive(acc)) return;
  const meta = {
    discordId: String(acc.discordId),
    expiresAt: acc.licenseExpiresAt,
    grantedAt: acc.licenseGrantedAt || readTimerMeta()?.grantedAt || new Date().toISOString(),
    savedAt: Date.now(),
  };
  localStorage.setItem(LICENSE_TIMER_META_KEY, JSON.stringify(meta));
}

function getLicenseStartMs(acc) {
  const granted = acc?.licenseGrantedAt;
  if (granted) {
    const ms = new Date(granted).getTime();
    if (!Number.isNaN(ms)) return ms;
  }
  const meta = readTimerMeta();
  if (meta?.discordId === String(acc?.discordId) && meta.grantedAt) {
    const ms = new Date(meta.grantedAt).getTime();
    if (!Number.isNaN(ms)) return ms;
  }
  return null;
}

function formatTimerStamp(iso) {
  if (!iso) return "—";
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return "—";
  return date.toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" });
}

function computeLicenseCountdown(acc = getAccount()) {
  const expiryMs = getLicenseExpiryMs(acc);
  if (!expiryMs) return null;

  const remainingMs = Math.max(0, expiryMs - Date.now());
  const expired = expiryMs <= Date.now();

  const days = Math.floor(remainingMs / 86_400_000);
  const hours = Math.floor((remainingMs % 86_400_000) / 3_600_000);
  const minutes = Math.floor((remainingMs % 3_600_000) / 60_000);
  const seconds = Math.floor((remainingMs % 60_000) / 1000);

  const startMs = getLicenseStartMs(acc);
  let progressPct = null;
  if (startMs && expiryMs > startMs) {
    const duration = expiryMs - startMs;
    const elapsed = Date.now() - startMs;
    progressPct = Math.min(100, Math.max(0, (elapsed / duration) * 100));
  }

  const remainingPct = progressPct == null ? null : Math.max(0, Math.min(100, 100 - progressPct));
  const urgency =
    remainingMs <= 86_400_000 ? "critical" : remainingMs <= 3 * 86_400_000 ? "urgent" : "normal";

  return {
    days,
    hours,
    minutes,
    seconds,
    expired,
    expiryMs,
    startMs,
    progressPct,
    remainingPct,
    remainingMs,
    urgency,
    expiresLabel: formatLicenseExpiry(acc),
    grantedLabel: formatTimerStamp(acc?.licenseGrantedAt || readTimerMeta()?.grantedAt),
  };
}

function buildTimerDigit(name, value, { accent = false } = {}) {
  return `
    <div class="license-timer__unit ${accent ? "license-timer__unit--accent" : ""}">
      <span class="license-timer__num" data-timer-part="${name}">${value}</span>
      <span class="license-timer__label">${name}</span>
    </div>
  `;
}

function buildLicenseTimerHtml(acc = getAccount()) {
  const active = isLicenseActive(acc);
  const hasExpiry = Boolean(acc?.licenseExpiresAt || readTimerMeta()?.expiresAt);
  const cd = computeLicenseCountdown(acc);

  if (!active || !hasExpiry || !cd) {
    return `
      <section class="account-license account-license--idle" id="license-live-timer">
        <div class="account-license__aurora" aria-hidden="true"></div>
        <div class="account-license__scanlines" aria-hidden="true"></div>
        <div class="account-license__inner account-license__inner--idle">
          <div class="account-license__vault-icon" aria-hidden="true">
            <span class="account-license__vault-ring"></span>
            <span class="account-license__vault-core">🔒</span>
          </div>
          <div class="account-license__idle-copy">
            <div class="account-license__header">
              <span class="account-license__eyebrow">License vault</span>
              <span class="account-license__pill account-license__pill--standard">${escapeHtml(acc?.licensedStatus || acc?.plan || "Standard")}</span>
            </div>
            <h2 class="account-license__title">No active license yet</h2>
            <p class="account-license__sub">When staff activates your key, a live countdown unlocks here — it keeps running in real time even if you close the browser and come back later.</p>
            <div class="account-license__idle-steps">
              <div class="account-license__idle-step"><span>1</span> Open a ticket in Discord</div>
              <div class="account-license__idle-step"><span>2</span> Staff runs <code>smky license</code></div>
              <div class="account-license__idle-step"><span>3</span> Timer + perks appear instantly</div>
            </div>
          </div>
        </div>
      </section>
    `;
  }

  const ringOffset = cd.remainingPct == null ? 0 : 283 - (283 * cd.remainingPct) / 100;

  return `
    <section class="account-license account-license--active account-license--${cd.urgency} ${cd.expired ? "is-expired" : ""}" id="license-live-timer">
      <div class="account-license__aurora" aria-hidden="true"></div>
      <div class="account-license__scanlines" aria-hidden="true"></div>
      <div class="account-license__grid">
        <div class="account-license__visual">
          <div class="account-license__orbit account-license__orbit--a" aria-hidden="true"></div>
          <div class="account-license__orbit account-license__orbit--b" aria-hidden="true"></div>
          <svg class="account-license__ring" viewBox="0 0 100 100" aria-hidden="true">
            <circle class="account-license__ring-track" cx="50" cy="50" r="45"></circle>
            <circle
              class="account-license__ring-fill"
              cx="50"
              cy="50"
              r="45"
              style="stroke-dashoffset:${ringOffset}"
            ></circle>
          </svg>
          <div class="account-license__ring-center">
            <span class="account-license__ring-pct" data-timer-part="remaining-pct">${cd.remainingPct == null ? "—" : `${Math.round(cd.remainingPct)}%`}</span>
            <span class="account-license__ring-label">time left</span>
          </div>
          <div class="account-license__pulse" aria-hidden="true"></div>
        </div>

        <div class="account-license__content">
          <div class="account-license__header">
            <span class="account-license__eyebrow">Live license timer</span>
            <span class="account-license__pill account-license__pill--live">
              <span class="account-license__live-dot"></span>
              Real-time · persists offline
            </span>
          </div>
          <h2 class="account-license__title">Customer access unlocked</h2>
          <p class="account-license__sub">Synced to your Discord ID. Close this tab, shut the browser, come back tomorrow — the countdown picks up exactly where it should.</p>

          <div class="license-timer__digits" aria-live="polite" aria-atomic="true">
            ${buildTimerDigit("days", padTimerUnit(cd.days))}
            <span class="license-timer__sep">:</span>
            ${buildTimerDigit("hours", padTimerUnit(cd.hours))}
            <span class="license-timer__sep">:</span>
            ${buildTimerDigit("mins", padTimerUnit(cd.minutes))}
            <span class="license-timer__sep">:</span>
            ${buildTimerDigit("secs", padTimerUnit(cd.seconds), { accent: true })}
          </div>

          <div class="account-license__timeline">
            <div class="account-license__timeline-node">
              <span class="account-license__timeline-dot"></span>
              <div>
                <span class="account-license__meta-k">Activated</span>
                <span class="account-license__meta-v" data-timer-part="granted">${escapeHtml(cd.grantedLabel)}</span>
              </div>
            </div>
            <div class="account-license__timeline-line" aria-hidden="true"></div>
            <div class="account-license__timeline-node">
              <span class="account-license__timeline-dot account-license__timeline-dot--end"></span>
              <div>
                <span class="account-license__meta-k">Expires</span>
                <span class="account-license__meta-v" data-timer-part="expires">${escapeHtml(cd.expiresLabel || "—")}</span>
              </div>
            </div>
          </div>

          <div class="account-license__progress">
            <div class="account-license__progress-fill" data-timer-part="progress" style="width:${cd.remainingPct == null ? 0 : cd.remainingPct}%"></div>
          </div>
          <div class="account-license__progress-labels">
            <span>Session independent</span>
            <span data-timer-part="remaining-pct-label">${cd.remainingPct == null ? "—" : `${Math.round(cd.remainingPct)}% remaining`}</span>
          </div>
        </div>
      </div>
    </section>
  `;
}

let accountLicenseTimer = null;
let lastTimerParts = {};

function setTimerPart(root, name, value, { animate = true } = {}) {
  root.querySelectorAll(`[data-timer-part="${name}"]`).forEach((el) => {
    if (el.textContent === value) return;
    if (animate) {
      el.classList.remove("license-timer__num--flip");
      void el.offsetWidth;
      el.classList.add("license-timer__num--flip");
    }
    el.textContent = value;
  });
}

function updateLicenseTimerDom() {
  const root = document.getElementById("license-live-timer");
  if (!root) return;

  const acc = getAccount();
  writeTimerMeta(acc);
  const cd = computeLicenseCountdown(acc);
  if (!cd || !isLicenseActive(acc)) {
    stopAccountLicenseTimer();
    return;
  }

  root.classList.toggle("is-expired", cd.expired);
  root.classList.remove("account-license--normal", "account-license--urgent", "account-license--critical");
  root.classList.add(`account-license--${cd.urgency}`);

  setTimerPart(root, "days", padTimerUnit(cd.days));
  setTimerPart(root, "hours", padTimerUnit(cd.hours));
  setTimerPart(root, "mins", padTimerUnit(cd.minutes));
  setTimerPart(root, "secs", padTimerUnit(cd.seconds), { animate: true });
  setTimerPart(root, "expires", cd.expiresLabel || "—", { animate: false });
  setTimerPart(root, "granted", cd.grantedLabel, { animate: false });
  setTimerPart(root, "remaining-pct", cd.remainingPct == null ? "—" : `${Math.round(cd.remainingPct)}%`, {
    animate: false,
  });
  setTimerPart(
    root,
    "remaining-pct-label",
    cd.remainingPct == null ? "—" : `${Math.round(cd.remainingPct)}% remaining`,
    { animate: false },
  );

  const progress = root.querySelector('[data-timer-part="progress"]');
  if (progress && cd.remainingPct != null) {
    progress.style.width = `${cd.remainingPct}%`;
  }

  const ring = root.querySelector(".account-license__ring-fill");
  if (ring && cd.remainingPct != null) {
    ring.style.strokeDashoffset = String(283 - (283 * cd.remainingPct) / 100);
  }

  lastTimerParts = {
    days: cd.days,
    hours: cd.hours,
    minutes: cd.minutes,
    seconds: cd.seconds,
  };

  if (cd.expired) {
    stopAccountLicenseTimer();
  }
}

function onLicenseTimerVisibility() {
  if (!document.hidden) updateLicenseTimerDom();
}

function startAccountLicenseTimer() {
  stopAccountLicenseTimer();
  writeTimerMeta(getAccount());
  updateLicenseTimerDom();
  accountLicenseTimer = window.setInterval(updateLicenseTimerDom, 1000);
  document.addEventListener("visibilitychange", onLicenseTimerVisibility);
  window.addEventListener("focus", updateLicenseTimerDom);
}

function stopAccountLicenseTimer() {
  if (accountLicenseTimer) {
    window.clearInterval(accountLicenseTimer);
    accountLicenseTimer = null;
  }
  document.removeEventListener("visibilitychange", onLicenseTimerVisibility);
  window.removeEventListener("focus", updateLicenseTimerDom);
}

function syncLicenseTimerMeta(acc) {
  writeTimerMeta(acc);
}

function hydrateLicenseTimerFromAccount(acc = getAccount()) {
  if (!acc?.discordId) return;
  const meta = readTimerMeta();
  if (meta?.discordId === String(acc.discordId) && meta.expiresAt && !acc.licenseExpiresAt) {
    acc.licenseExpiresAt = meta.expiresAt;
    if (!acc.licenseGrantedAt && meta.grantedAt) {
      acc.licenseGrantedAt = meta.grantedAt;
    }
    saveAccount(acc);
  }
  if (isLicenseActive(acc)) {
    writeTimerMeta(acc);
  }
}
