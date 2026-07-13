/** Direct Supabase REST/RPC calls — works without Edge Functions. */
function supabaseUrl() {
  const configured = window.SITE_CONFIG?.supabaseUrl;
  if (configured && String(configured).trim()) {
    return String(configured).trim().replace(/\/$/, "");
  }
  return "https://bumuisxrzbteeymzeidh.supabase.co";
}

function supabaseAnonKey() {
  const key = window.SITE_CONFIG?.supabaseAnonKey;
  if (!key || String(key).startsWith("YOUR_")) return "";
  return String(key).trim();
}

function useSupabaseDirect() {
  return !!(supabaseUrl() && supabaseAnonKey());
}

function supabaseHeaders() {
  const key = supabaseAnonKey();
  return {
    apikey: key,
    Authorization: `Bearer ${key}`,
    "Content-Type": "application/json",
    Accept: "application/json",
  };
}

async function supabaseRpc(fn, args = {}) {
  const url = `${supabaseUrl()}/rest/v1/rpc/${fn}`;
  const res = await fetch(url, {
    method: "POST",
    mode: "cors",
    cache: "no-store",
    headers: supabaseHeaders(),
    body: JSON.stringify(args),
  });
  const text = await res.text();
  let data = {};
  try {
    data = text ? JSON.parse(text) : {};
  } catch {
    data = { message: text };
  }
  if (!res.ok) {
    const msg = data.message || data.error || data.hint || `Request failed (${res.status})`;
    const err = new Error(msg);
    err.code = data.code || data.error || msg;
    err.status = res.status;
    throw err;
  }
  return data;
}

function siteTokenArg() {
  return typeof siteApiToken === "function" ? siteApiToken() : "";
}

async function supabaseApiRequest(path, options = {}) {
  const method = String(options.method || "GET").toUpperCase();
  let body = options.body;
  if (body && typeof body === "object" && !(body instanceof FormData)) {
    body = typeof apiAuthBody === "function" ? apiAuthBody(body) : body;
  }

  const token = siteTokenArg();
  const discordId = String(body?.discordId || "").trim();

  if (path === "/api/health" && method === "GET") {
    return supabaseRpc("api_health");
  }

  if (path === "/api/pins" && method === "POST") {
    const data = await supabaseRpc("register_pin_rpc", {
      p_site_token: token,
      p_discord_id: discordId,
      p_pin: String(body.pin || ""),
      p_player_name: body.playerName || "—",
      p_game: body.game || "FiveM",
      p_id: body.id || null,
      p_date: body.date || null,
    });
    return data;
  }

  if (path.startsWith("/api/pins/") && method === "GET") {
    const id = decodeURIComponent(path.split("/").pop() || "");
    return supabaseRpc("list_pins_rpc", { p_site_token: token, p_discord_id: id });
  }

  if (path.startsWith("/api/pins/") && method === "DELETE") {
    const pinId = decodeURIComponent(path.split("/").pop() || "");
    return supabaseRpc("delete_pin_rpc", {
      p_site_token: token,
      p_discord_id: discordId,
      p_pin_id: pinId,
    });
  }

  if (path.startsWith("/api/pins/verify/") && method === "GET") {
    const pin = decodeURIComponent(path.split("/").pop() || "");
    return supabaseRpc("verify_pin_rpc", { p_pin: pin });
  }

  if (path.startsWith("/api/scans/") && method === "GET") {
    const id = decodeURIComponent(path.split("/").pop() || "");
    return supabaseRpc("list_scans_rpc", { p_site_token: token, p_discord_id: id });
  }

  if (path === "/api/scans/submit" && method === "POST") {
    return supabaseRpc("submit_scan_rpc", {
      p_pin: String(body.pin || ""),
      p_verdict: body.verdict || "",
      p_player_name: body.playerName || null,
      p_threats: Number(body.threats || 0),
      p_warnings: Number(body.warnings || 0),
      p_summary: body.summary || "",
      p_report_text: body.reportText || "",
      p_hostname: body.hostname || "",
      p_username: body.username || "",
      p_id: body.id || null,
      p_date: body.date || null,
    });
  }

  if (path === "/api/users/register" && method === "POST") {
    return supabaseRpc("register_user_rpc", {
      p_site_token: token,
      p_discord_id: discordId,
      p_username: body.username || "Unknown",
      p_avatar_hash: body.avatarHash || "",
      p_licensed_status: body.licensedStatus || "Standard",
    });
  }

  if (path.startsWith("/api/license/") && (method === "GET" || method === "POST")) {
    const userId = decodeURIComponent(path.split("/").pop()?.split("?")[0] || "");
    return supabaseRpc("get_license_rpc", { p_discord_id: userId });
  }

  throw new Error(`not_found: ${path}`);
}
