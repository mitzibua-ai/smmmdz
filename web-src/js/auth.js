const STORAGE_KEY = "dotx_account_v1";

function getAccount() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
}

function saveAccount(account) {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(account));
}

function createDiscordAccount(profile) {
  const existing = getAccount();
  if (
    existing?.oauthLinked &&
    existing.discordId &&
    profile.discordId &&
    existing.discordId !== profile.discordId
  ) {
    throw new Error(
      "This browser already has a dotx account on a different Discord. Log out first."
    );
  }

  const account = {
    ...profile,
    locked: true,
    oauthLinked: true,
    licensedStatus: profile.licensedStatus || profile.plan || "Standard",
    plan: profile.plan || profile.licensedStatus || "Standard",
    createdAt: existing?.createdAt || Date.now(),
    profileSyncedAt: profile.profileSyncedAt || Date.now(),
  };

  saveAccount(account);
  return account;
}

function logout() {
  localStorage.removeItem(STORAGE_KEY);
}

function loginWithDiscord() {
  const existing = getAccount();
  if (existing?.oauthLinked && existing?.discordAccessToken) {
    window.location.href = "/dashboard/";
    return Promise.resolve();
  }
  if (existing && !existing.oauthLinked) {
    logout();
  }
  const forceConsent = Boolean(existing?.oauthLinked && !existing?.discordAccessToken);
  return startDiscordOAuth({ forceConsent });
}
