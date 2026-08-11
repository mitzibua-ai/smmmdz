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
  if (!acc?.discordId || !acc?.licenseExpiresAt) return;
  if (!isCustomerAccount(acc) && !isLicenseActive(acc)) return;
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

function formatJoinDate(acc) {
  const ts = acc?.createdAt;
  if (!ts) return "—";
  const date = new Date(ts);
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
  };
}

function formatCountdownLabel(cd) {
  if (!cd) return "—";
  if (cd.expired) return "Expired";
  if (cd.days > 0) {
    return `${cd.days}d ${padTimerUnit(cd.hours)}:${padTimerUnit(cd.minutes)}:${padTimerUnit(cd.seconds)}`;
  }
  return `${padTimerUnit(cd.hours)}:${padTimerUnit(cd.minutes)}:${padTimerUnit(cd.seconds)}`;
}

function buildLicenseExpireCountdownHtml(acc = getAccount()) {
  const isCustomer = isCustomerAccount(acc);
  const cd = computeLicenseCountdown(acc);

  if (!isCustomer) {
    return `<span class="account-kv__countdown account-kv__countdown--idle">—</span>`;
  }

  if (!cd) {
    return `<span class="account-kv__countdown account-kv__countdown--idle">No expiry set</span>`;
  }

  const urgencyClass = cd.expired
    ? "is-expired"
    : cd.urgency === "critical"
      ? "is-critical"
      : cd.urgency === "urgent"
        ? "is-urgent"
        : "is-live";

  return `<span class="account-kv__countdown ${urgencyClass}" id="license-expire-countdown" aria-live="polite">${escapeHtml(formatCountdownLabel(cd))}</span>`;
}

let accountLicenseTimer = null;

function updateLicenseTimerDom() {
  const countdownEl = document.getElementById("license-expire-countdown");
  if (!countdownEl) return;

  const acc = getAccount();
  writeTimerMeta(acc);
  const isCustomer = isCustomerAccount(acc);
  const cd = computeLicenseCountdown(acc);

  countdownEl.classList.remove("is-live", "is-urgent", "is-critical", "is-expired", "account-kv__countdown--idle");

  if (!isCustomer) {
    countdownEl.textContent = "—";
    countdownEl.classList.add("account-kv__countdown--idle");
    stopAccountLicenseTimer();
    return;
  }

  if (!cd) {
    countdownEl.textContent = "No expiry set";
    countdownEl.classList.add("account-kv__countdown--idle");
    stopAccountLicenseTimer();
    return;
  }

  countdownEl.textContent = formatCountdownLabel(cd);

  if (cd.expired) {
    countdownEl.classList.add("is-expired");
    stopAccountLicenseTimer();
    return;
  }

  if (cd.urgency === "critical") countdownEl.classList.add("is-critical");
  else if (cd.urgency === "urgent") countdownEl.classList.add("is-urgent");
  else countdownEl.classList.add("is-live");
}

function onLicenseTimerVisibility() {
  if (!document.hidden) updateLicenseTimerDom();
}

function startAccountLicenseTimer() {
  stopAccountLicenseTimer();
  writeTimerMeta(getAccount());
  updateLicenseTimerDom();
  if (!document.getElementById("license-expire-countdown")) return;
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
  if (isCustomerAccount(acc) || isLicenseActive(acc)) {
    writeTimerMeta(acc);
  }
}
