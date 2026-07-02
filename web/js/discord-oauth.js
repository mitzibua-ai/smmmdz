const DISCORD_API = "https://discord.com/api";
const DISCORD_AUTH = "https://discord.com/oauth2/authorize";
const PKCE_KEY = "dotx_pkce_verifier";
const REDIRECT_KEY = "dotx_oauth_redirect";

function getDiscordClientId() {
  const id = window.SITE_CONFIG?.discordClientId;
  if (!id || id === "YOUR_DISCORD_CLIENT_ID") return null;
  return String(id);
}

function getRedirectUri() {
  const configured = window.SITE_CONFIG?.oauthRedirectUri;
  if (configured && String(configured).trim()) return configured;
  if (window.location.protocol === "http:" || window.location.protocol === "https:") {
    return new URL("/callback/", window.location.origin).href;
  }
  return "http://127.0.0.1:8080/callback/";
}

function loginUrlForRedirect(redirectUri) {
  return redirectUri.replace(/callback\/?(\?.*)?$/i, "login/");
}

function randomUrlSafe(len) {
  const bytes = new Uint8Array(len);
  crypto.getRandomValues(bytes);
  return btoa(String.fromCharCode(...bytes))
    .replace(/\+/g, "-")
    .replace(/\//g, "_")
    .replace(/=+$/g, "");
}

function encodeOAuthState(verifier, redirectUri) {
  return btoa(JSON.stringify({ v: verifier, r: redirectUri, t: Date.now() }))
    .replace(/\+/g, "-")
    .replace(/\//g, "_")
    .replace(/=+$/g, "");
}

function decodeOAuthState(state) {
  try {
    const json = atob(state.replace(/-/g, "+").replace(/_/g, "/"));
    return JSON.parse(json);
  } catch {
    return null;
  }
}

function startDiscordOAuth(options = {}) {
  const clientId = getDiscordClientId();
  const redirectUri = getRedirectUri();
  const forceConsent = Boolean(options.forceConsent);

  if (!clientId) {
    throw new Error("Add your Discord Client ID in js/config.js");
  }

  const verifier = randomUrlSafe(32);
  sessionStorage.setItem(PKCE_KEY, verifier);
  sessionStorage.setItem(REDIRECT_KEY, redirectUri);

  return sha256Base64Url(verifier).then((challenge) => {
    const state = encodeOAuthState(verifier, redirectUri);
    const params = new URLSearchParams({
      client_id: clientId,
      redirect_uri: redirectUri,
      response_type: "code",
      scope: "identify guilds.members.read",
      code_challenge: challenge,
      code_challenge_method: "S256",
      state,
    });
    if (forceConsent) {
      params.set("prompt", "consent");
    }
    window.location.href = `${DISCORD_AUTH}?${params.toString()}`;
  });
}

function getVerifierForCallback(state) {
  let verifier = sessionStorage.getItem(PKCE_KEY);
  let redirectUri = sessionStorage.getItem(REDIRECT_KEY) || getRedirectUri();

  if (!verifier && state) {
    const decoded = decodeOAuthState(state);
    if (decoded?.v) {
      verifier = decoded.v;
      redirectUri = decoded.r || redirectUri;
    }
  }

  return { verifier, redirectUri };
}

async function exchangeCodeForToken(code, state) {
  const clientId = getDiscordClientId();
  const { verifier, redirectUri } = getVerifierForCallback(state);

  if (!clientId || !verifier || !redirectUri) {
    throw new Error("Login expired. Go back to login and try again.");
  }

  const body = new URLSearchParams({
    client_id: clientId,
    grant_type: "authorization_code",
    code,
    redirect_uri: redirectUri,
    code_verifier: verifier,
  });

  const res = await fetch(`${DISCORD_API}/oauth2/token`, {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body,
  });

  sessionStorage.removeItem(PKCE_KEY);
  sessionStorage.removeItem(REDIRECT_KEY);

  if (!res.ok) {
    const err = await res.text();
    throw new Error("Discord login failed. Add this redirect URL in Discord Developer Portal: " + redirectUri);
  }

  const data = await res.json();
  if (!data.access_token) {
    throw new Error("Discord did not return a token.");
  }
  return data;
}

async function fetchDiscordMe(accessToken) {
  const res = await fetch(`${DISCORD_API}/users/@me`, {
    headers: { Authorization: `Bearer ${accessToken}` },
  });
  if (!res.ok) {
    throw new Error("Could not load your Discord profile.");
  }
  return res.json();
}

function profileFromDiscordUser(user) {
  const decorationData = user.avatar_decoration_data || null;
  return {
    discordId: user.id,
    username: displayName(user),
    globalName: user.global_name || null,
    discordUsername: user.username,
    discriminator: user.discriminator || "0",
    tag: displayTag(user),
    avatar: discordAvatarUrl(user.id, user.avatar, 256),
    avatarHash: user.avatar || null,
    banner: discordBannerUrl(user.id, user.banner, 600),
    accentColor: user.accent_color || null,
    decorationUrl: discordDecorationUrl(decorationData),
    licensedStatus: "Standard",
    plan: "Standard",
    locked: true,
    oauthLinked: true,
    createdAt: Date.now(),
    profileSyncedAt: Date.now(),
  };
}

async function completeDiscordOAuth(code, state) {
  const tokenData = await exchangeCodeForToken(code, state);
  const user = await fetchDiscordMe(tokenData.access_token);

  let profile = profileFromDiscordUser(user);
  profile = storeDiscordTokens(profile, tokenData);

  try {
    const extra = await fetchDiscordProfile(user.id);
    profile = {
      ...profile,
      username: displayName(extra),
      globalName: extra.globalName,
      discordUsername: extra.username,
      tag: extra.tag,
      avatar: extra.avatar,
      avatarHash: extra.avatarHash,
      banner: extra.banner || profile.banner,
      accentColor: extra.accentColor || profile.accentColor,
      decorationUrl: extra.decorationUrl || profile.decorationUrl,
      profileSyncedAt: Date.now(),
    };
  } catch {
    // @me is enough
  }

  const account = createDiscordAccount(profile);
  return applyLicensedStatus(account);
}
