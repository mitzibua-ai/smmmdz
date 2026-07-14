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
    const raw = String(data.message || data.error || data.hint || `Request failed (${res.status})`);
    const lower = raw.toLowerCase();
    let code = data.code || null;
    if (lower.includes("invalid_site_token")) code = "invalid_site_token";
    else if (lower.includes("license_required")) code = "license_required";
    else if (lower.includes("forbidden")) code = "forbidden";
    else if (lower.includes("invalid_pin")) code = "invalid_pin";
    else if (lower.includes("not_found") || lower.includes("user_not_found")) code = "not_found";
    const err = new Error(code || raw);
    err.code = code || raw;
    err.status =
      code === "invalid_site_token"
        ? 401
        : code === "license_required" || code === "forbidden"
          ? 403
          : code === "not_found" || code === "invalid_pin"
            ? 404
            : res.status;
    throw err;
  }
  return data;
}

function siteTokenArg() {
  return typeof siteApiToken === "function" ? siteApiToken() : "";
}

function pathOnly(path) {
  return String(path || "").split("?")[0].replace(/\/$/, "") || "/";
}

async function supabaseApiRequest(path, options = {}) {
  const method = String(options.method || "GET").toUpperCase();
  const clean = pathOnly(path);
  let body = options.body;
  if (body && typeof body === "object" && !(body instanceof FormData)) {
    body = typeof apiAuthBody === "function" ? apiAuthBody(body) : { ...body };
  } else {
    body = body || {};
  }

  const token = siteTokenArg();
  const query = new URLSearchParams(String(path || "").includes("?") ? String(path).split("?")[1] : "");
  const discordId = String(body.discordId || query.get("discordId") || "").trim();
  const actorId = discordId;

  if (clean === "/api/health" && method === "GET") {
    return supabaseRpc("api_health");
  }

  if (clean === "/api/pins" && method === "POST") {
    return supabaseRpc("register_pin_rpc", {
      p_site_token: token,
      p_discord_id: discordId,
      p_pin: String(body.pin || ""),
      p_player_name: body.playerName || "—",
      p_game: body.game || "FiveM",
      p_id: body.id || null,
      p_date: body.date || null,
    });
  }

  if (clean.startsWith("/api/pins/verify/") && method === "GET") {
    const pin = decodeURIComponent(clean.split("/").pop() || "");
    return supabaseRpc("verify_pin_rpc", { p_pin: pin });
  }

  if (clean.startsWith("/api/pins/") && method === "GET") {
    const id = decodeURIComponent(clean.split("/").pop() || "");
    return supabaseRpc("list_pins_rpc", { p_site_token: token, p_discord_id: id });
  }

  if (clean.startsWith("/api/pins/") && method === "DELETE") {
    const pinId = decodeURIComponent(clean.split("/").pop() || "");
    return supabaseRpc("delete_pin_rpc", {
      p_site_token: token,
      p_discord_id: discordId,
      p_pin_id: pinId,
    });
  }

  if (clean.startsWith("/api/scans/") && method === "GET" && clean !== "/api/scans/submit") {
    const id = decodeURIComponent(clean.split("/").pop() || "");
    return supabaseRpc("list_scans_rpc", { p_site_token: token, p_discord_id: id });
  }

  if (clean === "/api/scans/submit" && method === "POST") {
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

  if (clean === "/api/users/register" && method === "POST") {
    return supabaseRpc("register_user_rpc", {
      p_site_token: token,
      p_discord_id: discordId,
      p_username: body.username || "Unknown",
      p_avatar_hash: body.avatarHash || "",
      p_licensed_status: body.licensedStatus || "Standard",
    });
  }

  if (clean.startsWith("/api/license/") && (method === "GET" || method === "POST")) {
    const userId = decodeURIComponent(clean.split("/").pop() || "");
    return supabaseRpc("get_license_rpc", { p_discord_id: userId });
  }

  if (
    (clean === "/api/owner/overview" || clean === "/api/admin/overview" || clean === "/api/staff/overview") &&
    (method === "GET" || method === "POST")
  ) {
    const kind = clean.split("/")[2];
    return supabaseRpc("overview_rpc", {
      p_site_token: token,
      p_discord_id: actorId,
      p_kind: kind,
    });
  }

  if ((clean === "/api/owner/users/role" || clean === "/api/admin/users/role") && method === "POST") {
    return supabaseRpc("set_role_rpc", {
      p_site_token: token,
      p_actor_id: actorId,
      p_target_id: String(body.targetId || "").trim(),
      p_role: String(body.role || "").trim(),
    });
  }

  if (clean === "/api/owner/users/revoke-license" && method === "POST") {
    return supabaseRpc("revoke_license_rpc", {
      p_site_token: token,
      p_actor_id: actorId,
      p_target_id: String(body.targetId || "").trim(),
    });
  }

  const err = new Error(`not_found: ${clean}`);
  err.code = "not_found";
  err.status = 404;
  throw err;
}
