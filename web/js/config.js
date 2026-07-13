window.SITE_CONFIG = {
  name: "dotx",
  tagline: "FiveM PC Check Tool",
  version: "1.0",

  discordClientId: "1519618635054841867",

  // Your Discord server ID (Developer Mode → right-click server → Copy Server ID)
  discordGuildId: "1519369196188733440",

  // Customer role ID (Server Settings → Roles → right-click role → Copy Role ID)
  customerRoleId: "1519527288503275641",

  // Panel owner — always has Owner dashboard access
  ownerDiscordIds: ["1284140942764539985"],
  ownerRoleIds: [],

  // Supabase Edge API (pins, scans, licenses, stamped exe download)
  apiBaseUrl: "https://bumuisxrzbteeymzeidh.supabase.co/functions/v1/dotx",

  // Site API security token — must match Supabase secret SITE_API_TOKEN
  apiToken: "CghI7o7bKeoevRU074_kPm08OrDq6EqcQVsCGX3xBnQ",

  // Leave empty — OAuth uses your GitHub Pages domain automatically
  oauthRedirectUri: "",

  // How often to re-check license while the panel is open (milliseconds)
  licensePollMs: 1000,

  // Fast polling while waiting for a license (milliseconds)
  licenseBurstMs: 500,

  pcCheckToolName: "dotx PC Check Tool",
  pcCheckToolUrl: "/downloads/dotx-pc-check.exe",
  dataSyncPollMs: 3000,
};
