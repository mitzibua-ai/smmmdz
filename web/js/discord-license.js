function discordApiUrl(path) {
  return `https://discord.com/api${path}`;
}

function getGuildConfig() {
  const guildId = window.SITE_CONFIG?.discordGuildId;
  const roleId = window.SITE_CONFIG?.customerRoleId;
  if (!guildId || !roleId) return null;
  if (String(guildId).startsWith("YOUR_") || String(roleId).startsWith("YOUR_")) return null;
  return { guildId: String(guildId), roleId: String(roleId) };
}

function configOwnerIds() {
  const ids = window.SITE_CONFIG?.ownerDiscordIds;
  if (!Array.isArray(ids)) return [];
  return ids.map((id) => String(id).trim()).filter(Boolean);
}

function isConfigOwner(acc = getAccount()) {
  const id = String(acc?.discordId || "").trim();
  return id && configOwnerIds().includes(id);
}

function applyConfigOwnerFlags(acc) {
  if (!isConfigOwner(acc)) return acc;
  return {
    ...acc,
    isOwner: true,
    isAdmin: true,
    isStaff: true,
    panelRole: "owner",
    licensedStatus: acc.licensedStatus === "Customer" ? "Customer" : acc.licensedStatus || acc.plan || "Standard",
  };
}

function getLicensePollMs() {
  const ms = Number(window.SITE_CONFIG?.licensePollMs);
  return ms > 0 ? ms : 1000;
}

function getLicenseBurstMs() {
  const ms = Number(window.SITE_CONFIG?.licenseBurstMs);
  return ms > 0 ? ms : 500;
}

function hasRole(member, customerRoleId) {
  if (!member?.roles) return false;
  const target = String(customerRoleId);
  return member.roles.some((roleId) => String(roleId) === target);
}

function hasValidLicenseExpiry(expiresAt) {
  if (!expiresAt) return false;
  const exp = new Date(expiresAt);
  return !Number.isNaN(exp.getTime()) && exp.getTime() > Date.now();
}

function isLicenseActive(acc = getAccount()) {
  if (!acc) return false;
  if (acc.licenseActive === true) return true;
  if (hasValidLicenseExpiry(acc.licenseExpiresAt)) return true;
  return (acc.licensedStatus || acc.plan) === "Customer";
}

function isNonAuthoritativeLicenseError(server) {
  if (!server?.error) return false;
  return (
    server.error === "wrong_server" ||
    server.error === "bot_not_configured" ||
    server.error === "discord_403" ||
    server.error === "not_in_guild" ||
    server.unreachable === true
  );
}

function preserveCustomerState(account, previous) {
  if (!isLicenseActive(account)) return null;
  const updated = {
    ...account,
    licensedStatus: "Customer",
    plan: "Customer",
    licenseActive: true,
    licenseSyncedAt: Date.now(),
  };
  saveAccount(updated);
  updated._licenseChanged = previous !== "Customer";
  updated._licenseActivated = false;
  return applyConfigOwnerFlags(updated);
}

function licensedStatusFromMember(member, customerRoleId) {
  const acc = getAccount();
  if (isLicenseActive(acc)) {
    return "Customer";
  }
  return hasRole(member, customerRoleId) ? "Customer" : "Standard";
}

async function fetchLicenseFromServer(discordId) {
  if (!window.location.protocol.startsWith("http")) return null;

  const stored = getAccount();

  try {
    const res = await fetch(apiUrlWithToken(`/api/license/${encodeURIComponent(discordId)}?t=${Date.now()}`), {
      method: "GET",
      mode: "cors",
      cache: "no-store",
    });

    if (res.status === 404) {
      if (!isExternalApiConfigured() && /\.github\.io$/i.test(window.location.hostname)) {
        return null;
      }
      return {
        status: "Standard",
        licenseActive: false,
        error: "wrong_server",
        message: "Set apiBaseUrl in config.js to your Railway API domain.",
        source: "none",
      };
    }

    if (res.status === 401) {
      return {
        status: stored?.licensedStatus || "Standard",
        licenseActive: isLicenseActive(stored),
        error: "invalid_site_token",
        unreachable: true,
        source: "none",
      };
    }

    if (!res.ok) {
      return {
        status: stored?.licensedStatus || "Standard",
        licenseActive: isLicenseActive(stored),
        unreachable: true,
        source: "none",
      };
    }

    const data = await res.json();
    if (!data || typeof data.status !== "string") {
      return { unreachable: true, licenseActive: isLicenseActive(stored), source: "none" };
    }

    const licenseActive = data.licenseActive === true || data.status === "Customer";
    return {
      status: licenseActive ? "Customer" : "Standard",
      licenseActive,
      isOwner: data.isOwner === true,
      isAdmin: data.isAdmin === true,
      isStaff: data.isStaff === true,
      panelRole: data.panelRole || (data.isOwner ? "owner" : data.isAdmin ? "admin" : data.isStaff ? "staff" : "member"),
      licenseExpiresAt: data.licenseExpiresAt || null,
      licenseGrantedAt: data.licenseGrantedAt || null,
      licenseSource: data.licenseSource || data.method || null,
      error: data.error || null,
      message: data.message || null,
      source: data.method || data.licenseSource || "bot",
      unreachable: false,
    };
  } catch {
    return {
      unreachable: true,
      licenseActive: isLicenseActive(stored),
      status: stored?.licensedStatus || "Standard",
      source: "none",
    };
  }
}

async function refreshDiscordAccessToken(refreshToken) {
  const clientId = getDiscordClientId();
  if (!clientId || !refreshToken) return null;

  const body = new URLSearchParams({
    client_id: clientId,
    grant_type: "refresh_token",
    refresh_token: refreshToken,
  });

  const res = await fetch(discordApiUrl("/oauth2/token"), {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body,
  });

  if (!res.ok) return null;
  return res.json();
}

function storeDiscordTokens(account, tokenData) {
  if (!tokenData?.access_token) return account;
  return {
    ...account,
    discordAccessToken: tokenData.access_token,
    discordRefreshToken: tokenData.refresh_token || account.discordRefreshToken || null,
    tokenExpiresAt: tokenData.expires_in
      ? Date.now() + tokenData.expires_in * 1000
      : account.tokenExpiresAt || null,
    licenseNeedsReauth: false,
  };
}

async function getValidAccessToken(account) {
  if (!account?.discordAccessToken) return null;

  const stillValid =
    account.tokenExpiresAt && Date.now() < account.tokenExpiresAt - 60_000;

  if (stillValid) return account.discordAccessToken;

  if (account.discordRefreshToken) {
    const data = await refreshDiscordAccessToken(account.discordRefreshToken);
    if (data?.access_token) {
      const updated = storeDiscordTokens(account, data);
      saveAccount(updated);
      return data.access_token;
    }
  }

  return account.discordAccessToken;
}

async function fetchGuildMember(accessToken, guildId) {
  const res = await fetch(discordApiUrl(`/users/@me/guilds/${guildId}/member`), {
    headers: { Authorization: `Bearer ${accessToken}` },
    cache: "no-store",
  });

  if (res.status === 404) return { member: null, unauthorized: false };
  if (res.status === 401) return { member: null, unauthorized: true };
  if (!res.ok) return { member: null, unauthorized: false };
  return { member: await res.json(), unauthorized: false };
}

async function fetchLicenseFromOAuth(account, cfg) {
  let updated = { ...account };
  let token = await getValidAccessToken(updated);
  if (!token) {
    return { status: null, needsReauth: true, account: updated };
  }

  let result = await fetchGuildMember(token, cfg.guildId);

  if (result.unauthorized && updated.discordRefreshToken) {
    const data = await refreshDiscordAccessToken(updated.discordRefreshToken);
    if (data?.access_token) {
      updated = storeDiscordTokens(updated, data);
      token = data.access_token;
      result = await fetchGuildMember(token, cfg.guildId);
    }
  }

  if (result.unauthorized) {
    return { status: null, needsReauth: true, account: updated };
  }

  return {
    status: licensedStatusFromMember(result.member, cfg.roleId),
    needsReauth: false,
    account: updated,
    source: "oauth",
  };
}

function applyServerLicense(account, server, previous) {
  if (server.unreachable || isNonAuthoritativeLicenseError(server)) {
    const kept = preserveCustomerState(account, previous);
    if (kept) return kept;
    return applyConfigOwnerFlags({ ...account, licenseSyncedAt: Date.now() });
  }

  const licenseActive = server.licenseActive === true;
  const status = licenseActive ? "Customer" : "Standard";
  const expiresAt = licenseActive ? server.licenseExpiresAt || account.licenseExpiresAt || null : null;
  const grantedAt = licenseActive
    ? server.licenseGrantedAt || account.licenseGrantedAt || null
    : null;

  const updated = {
    ...account,
    licensedStatus: status,
    plan: status,
    licenseActive,
    isOwner: server.isOwner === true,
    isAdmin: server.isAdmin === true,
    isStaff: server.isStaff === true,
    panelRole: server.panelRole || "member",
    licenseSyncedAt: Date.now(),
    licenseNeedsReauth:
      server.error === "oauth_expired" ||
      server.error === "oauth_forbidden",
    licenseError: server.error || null,
    licenseMessage: server.message || null,
    licenseSource: server.licenseSource || server.source || null,
    licenseExpiresAt: expiresAt,
    licenseGrantedAt: grantedAt,
  };

  saveAccount(updated);
  if (licenseActive && typeof syncLicenseTimerMeta === "function") {
    syncLicenseTimerMeta(updated);
  }
  const becameCustomer = licenseActive && previous !== "Customer";
  const lostCustomer = !licenseActive && previous === "Customer";
  updated._licenseChanged = previous !== status || becameCustomer || lostCustomer;
  updated._licenseActivated = becameCustomer;
  updated._licenseRevoked = lostCustomer;
  return applyConfigOwnerFlags(updated);
}

async function applyLicensedStatus(account) {
  const cfg = getGuildConfig();
  const apiConfigured = typeof isExternalApiConfigured === "function" && isExternalApiConfigured();
  let updated = { ...account };
  const previous = updated.licensedStatus || "Standard";

  const server = await fetchLicenseFromServer(updated.discordId);
  if (server) {
    return applyServerLicense(updated, server, previous);
  }

  if (apiConfigured) {
    const kept = preserveCustomerState(updated, previous);
    if (kept) return kept;
    return applyConfigOwnerFlags(updated);
  }

  if (isLicenseActive(updated)) {
    updated = {
      ...updated,
      licensedStatus: "Customer",
      plan: "Customer",
      licenseActive: true,
      licenseSyncedAt: Date.now(),
    };
    saveAccount(updated);
    updated._licenseChanged = previous !== "Customer";
    return applyConfigOwnerFlags(updated);
  }

  if (!cfg) {
    updated.licensedStatus = "Standard";
    updated.plan = "Standard";
    updated.licenseActive = false;
    updated.isOwner = false;
    updated.isAdmin = false;
    updated.isStaff = false;
    updated.panelRole = "member";
    saveAccount(updated);
    return applyConfigOwnerFlags(updated);
  }

  const oauth = await fetchLicenseFromOAuth(updated, cfg);
  updated = oauth.account;

  if (oauth.needsReauth || !oauth.status) {
    updated.licenseNeedsReauth = true;
    updated.licenseError = "oauth_reauth_required";
    return applyConfigOwnerFlags(updated);
  }

  const status = oauth.status;
  updated = {
    ...updated,
    licensedStatus: status,
    plan: status,
    licenseActive: status === "Customer",
    isOwner: false,
    isAdmin: false,
    isStaff: false,
    panelRole: "member",
    licenseSyncedAt: Date.now(),
    licenseNeedsReauth: false,
    licenseError: null,
    licenseSource: oauth.source,
  };
  saveAccount(updated);
  updated._licenseChanged = previous !== status;
  return applyConfigOwnerFlags(updated);
}

function isCustomerAccount(acc = getAccount()) {
  if (!acc) return false;
  if (isLicenseActive(acc)) return true;
  if (typeof isOwnerAccount === "function" && isOwnerAccount(acc)) return true;
  if (typeof isAdminAccount === "function" && isAdminAccount(acc)) return true;
  if (typeof isStaffAccount === "function" && isStaffAccount(acc)) return true;
  return false;
}

function formatLicenseExpiry(acc = getAccount()) {
  const raw = acc?.licenseExpiresAt;
  if (!raw) return "";
  const date = new Date(raw);
  if (Number.isNaN(date.getTime())) return "";
  return date.toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" });
}

function startLicenseSync(onUpdate) {
  let busy = false;
  let lastTick = 0;
  const minGapMs = 1200;

  async function tick() {
    if (busy) return;
    const now = Date.now();
    if (now - lastTick < minGapMs) return;

    const current = getAccount();
    if (!current?.oauthLinked || !current?.discordId) return;

    busy = true;
    lastTick = now;
    try {
      const updated = await applyLicensedStatus(current);
      if (onUpdate) onUpdate(updated);
    } catch {
      // keep last known status
    } finally {
      busy = false;
    }
  }

  const intervalMs = Math.max(getLicensePollMs(), 1500);
  const timer = setInterval(tick, intervalMs);

  function onVisible() {
    if (!document.hidden) tick();
  }

  document.addEventListener("visibilitychange", onVisible);
  window.addEventListener("focus", tick);

  tick();

  return function stopLicenseSync() {
    clearInterval(timer);
    document.removeEventListener("visibilitychange", onVisible);
    window.removeEventListener("focus", tick);
  };
}
