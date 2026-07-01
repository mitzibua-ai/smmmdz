const JAPI_USER = "https://japi.rest/discord/v1/user";

function isDiscordSnowflake(id) {
  return /^\d{17,20}$/.test(String(id).trim());
}

function discordAvatarUrl(discordId, avatarHash, size = 128) {
  if (avatarHash && typeof avatarHash === "string" && !avatarHash.startsWith("http")) {
    const ext = avatarHash.startsWith("a_") ? "gif" : "png";
    return `https://cdn.discordapp.com/avatars/${discordId}/${avatarHash}.${ext}?size=${size}`;
  }
  if (avatarHash && avatarHash.startsWith("http")) {
    return avatarHash;
  }
  const index = Number(BigInt(discordId) % 6n);
  return `https://cdn.discordapp.com/embed/avatars/${index}.png`;
}

function discordBannerUrl(discordId, bannerHash, size = 512) {
  if (!bannerHash) return null;
  if (bannerHash.startsWith("http")) return bannerHash;
  const ext = bannerHash.startsWith("a_") ? "gif" : "png";
  return `https://cdn.discordapp.com/banners/${discordId}/${bannerHash}.${ext}?size=${size}`;
}

function discordDecorationUrl(decorationData) {
  if (!decorationData || !decorationData.asset) return null;
  const asset = decorationData.asset;
  return `https://cdn.discordapp.com/avatar-decoration-presets/${asset}.png?size=240&passthrough=false`;
}

function displayName(data) {
  return data.global_name || data.globalName || data.username || "discord_user";
}

function displayTag(data) {
  if (data.tag) return data.tag;
  if (data.discriminator && data.discriminator !== "0") {
    return `${data.username}#${data.discriminator}`;
  }
  return `@${data.username || "user"}`;
}

async function fetchDiscordProfile(discordId) {
  const id = String(discordId).trim();
  if (!isDiscordSnowflake(id)) {
    throw new Error("Invalid Discord User ID.");
  }

  const res = await fetch(`${JAPI_USER}/${id}`);
  if (!res.ok) {
    throw new Error("Could not load Discord profile. Check your User ID.");
  }

  const json = await res.json();
  const data = json.data || json;
  if (!data || !data.id) {
    throw new Error("Discord profile not found.");
  }

  const decorationData = data.avatar_decoration_data || data.avatarDecorationData || null;

  return {
    id: data.id,
    username: data.username,
    globalName: data.global_name || data.globalName || null,
    discriminator: data.discriminator || "0",
    tag: data.tag || displayTag(data),
    avatarHash: data.avatar || null,
    avatar: data.avatarURL || discordAvatarUrl(data.id, data.avatar, 256),
    banner: data.bannerURL || discordBannerUrl(data.id, data.banner, 600),
    accentColor: data.accent_color || data.banner_color || null,
    decorationUrl: discordDecorationUrl(decorationData),
    decorationData,
    publicFlags: data.public_flags || data.publicFlags || 0,
  };
}

function profileFromApi(api) {
  return {
    discordId: api.id,
    username: displayName(api),
    globalName: api.globalName,
    discordUsername: api.username,
    discriminator: api.discriminator,
    tag: api.tag,
    avatar: api.avatar,
    avatarHash: api.avatarHash,
    banner: api.banner,
    accentColor: api.accentColor,
    decorationUrl: api.decorationUrl,
    plan: "Standard",
    locked: true,
    createdAt: Date.now(),
    profileSyncedAt: Date.now(),
  };
}

function mergeProfile(account, api) {
  return {
    ...account,
    username: displayName(api),
    globalName: api.globalName,
    discordUsername: api.username,
    discriminator: api.discriminator,
    tag: api.tag,
    avatar: api.avatar,
    avatarHash: api.avatarHash,
    banner: api.banner,
    accentColor: api.accentColor,
    decorationUrl: api.decorationUrl,
    profileSyncedAt: Date.now(),
  };
}

function buildDiscordAvatarHtml(account, size = "md") {
  const cls = `discord-avatar-wrap discord-avatar-wrap--${size}`;
  const avatar = account.avatar || discordAvatarUrl(account.discordId, account.avatarHash, 128);
  const deco = account.decorationUrl
    ? `<img class="discord-avatar-wrap__deco" src="${account.decorationUrl}" alt="" />`
    : "";

  return `
    <div class="${cls}">
      <img class="discord-avatar-wrap__img" src="${avatar}" alt="" />
      ${deco}
    </div>
  `;
}

function buildDiscordProfileCard(account, { compact = false } = {}) {
  const name = escapeHtml(account.username);
  const tag = escapeHtml(account.tag || `@${account.discordUsername || "user"}`);
  const bannerStyle = account.banner
    ? `background-image:url('${account.banner}')`
    : account.accentColor
      ? `background-color:#${Number(account.accentColor).toString(16).padStart(6, "0")}`
      : "background:linear-gradient(135deg,#1a2230,#0d121c)";

  const avatarSize = compact ? "md" : "lg";
  const licensedStatus = account.licensedStatus || account.plan || "Standard";
  const isCustomer = licensedStatus === "Customer";

  return `
    <div class="discord-profile-card ${compact ? "discord-profile-card--compact" : ""}">
      <div class="discord-profile-card__banner" style="${bannerStyle}"></div>
      <div class="discord-profile-card__body">
        ${buildDiscordAvatarHtml(account, avatarSize)}
        <div class="discord-profile-card__name">${name}</div>
        <div class="discord-profile-card__tag">${tag}</div>
        <div class="discord-profile-card__status-row">
          <div class="discord-profile-card__status">
            <span class="status-dot"></span> Connected via Discord
          </div>
          <div class="discord-profile-card__license">
            <span class="discord-profile-card__license-label">Licensed Status</span>
            <span class="discord-profile-card__license-badge ${isCustomer ? "is-customer" : "is-standard"}">${escapeHtml(licensedStatus)}</span>
          </div>
        </div>
      </div>
    </div>
  `;
}

function escapeHtml(s) {
  return String(s)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

async function refreshDiscordProfile(account) {
  const api = await fetchDiscordProfile(account.discordId);
  const updated = mergeProfile(account, api);
  saveAccount(updated);
  return updated;
}
