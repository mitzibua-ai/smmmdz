import { createClient } from "https://esm.sh/@supabase/supabase-js@2.49.1";

const DEFAULT_SUPABASE_URL = "https://bumuisxrzbteeymzeidh.supabase.co";
const DEFAULT_GUILD = "1519369196188733440";
const DEFAULT_CUSTOMER_ROLE = "1519527288503275641";
const DEFAULT_OWNERS = new Set(["1284140942764539985"]);
const PANEL_ROLES = new Set(["member", "staff", "admin", "owner"]);
const ROLE_RANK: Record<string, number> = { member: 1, staff: 2, admin: 3, owner: 4 };
const CORS_ORIGINS = [
  "https://dotx.store",
  "https://www.dotx.store",
  "https://mitzibua-ai.github.io",
  "http://127.0.0.1:8080",
  "http://localhost:8080",
];
const SITE_TOKEN_EXEMPT = new Set([
  "/api/health",
  "/api/scans/submit",
  "/api/tool-config",
  "/api/site-config",
  "/api/users/register",
  "/api/users/branding",
]);
const DOTX_CONFIG_MARKER = "DOTXCONFIG";

type Json = Record<string, unknown>;

function env(name: string, fallback = ""): string {
  return (Deno.env.get(name) || fallback).trim();
}

function brandingFromUser(row: Json | null | undefined): Json | null {
  if (!row) return null;
  const stored = row.tool_branding;
  if (stored && typeof stored === "object") {
    return stored as Json;
  }
  const discordId = String(row.discord_id || "");
  const hash = String(row.avatar_hash || "");
  let avatarUrl = "";
  if (discordId && hash) {
    avatarUrl = `https://cdn.discordapp.com/avatars/${discordId}/${hash}.png?size=128`;
  } else if (discordId) {
    try {
      const idx = Number((BigInt(discordId) >> 22n) % 6n);
      avatarUrl = `https://cdn.discordapp.com/embed/avatars/${idx}.png`;
    } catch {
      avatarUrl = "https://cdn.discordapp.com/embed/avatars/0.png";
    }
  }
  return {
    showDiscordAvatar: true,
    username: String(row.username || ""),
    discordId,
    avatarUrl,
    customImage: null,
  };
}

function supabase() {
  const url = env("SUPABASE_URL", DEFAULT_SUPABASE_URL);
  const key = env("SUPABASE_SERVICE_ROLE_KEY");
  if (!key) throw new Error("SUPABASE_SERVICE_ROLE_KEY missing");
  return createClient(url, key, { auth: { persistSession: false } });
}

function apiPath(req: Request): string {
  const url = new URL(req.url);
  const raw = url.pathname;
  const idx = raw.indexOf("/api/");
  if (idx >= 0) return raw.slice(idx).split("?")[0].replace(/\/$/, "") || "/api";
  return raw.split("?")[0].replace(/\/$/, "") || "/api";
}

function corsOrigin(req: Request): string {
  const origin = (req.headers.get("Origin") || "").replace(/\/$/, "");
  if (!origin) return CORS_ORIGINS[0];
  const candidates = new Set([origin]);
  if (origin.startsWith("https://www.")) candidates.add(origin.replace("https://www.", "https://"));
  else if (origin.startsWith("https://")) candidates.add(origin.replace("https://", "https://www."));
  for (const allowed of CORS_ORIGINS) {
    if (candidates.has(allowed)) return origin;
  }
  if (origin.endsWith(".github.io")) return origin;
  return CORS_ORIGINS[0];
}

function corsHeaders(req: Request): HeadersInit {
  return {
    "Access-Control-Allow-Origin": corsOrigin(req),
    "Access-Control-Allow-Headers":
      "Content-Type, X-Discord-Token, X-Site-Token, Accept, Cache-Control, Pragma, Authorization, apikey",
    "Access-Control-Allow-Methods": "GET, POST, DELETE, OPTIONS",
    "Access-Control-Max-Age": "86400",
    Vary: "Origin",
  };
}

function jsonResponse(req: Request, payload: Json, status = 200): Response {
  return new Response(JSON.stringify(payload), {
    status,
    headers: { "Content-Type": "application/json", "Cache-Control": "no-store", ...corsHeaders(req) },
  });
}

function errorResponse(req: Request, message: string, status = 400): Response {
  return jsonResponse(req, { error: message }, status);
}

async function readJson(req: Request): Promise<Json> {
  try {
    const data = await req.json();
    return data && typeof data === "object" ? (data as Json) : {};
  } catch {
    return {};
  }
}

function siteTokenFrom(req: Request, body: Json): string {
  return (
    req.headers.get("X-Site-Token")?.trim() ||
    String(body.siteToken || "").trim() ||
    new URL(req.url).searchParams.get("siteToken")?.trim() ||
    ""
  );
}

function siteTokenOk(req: Request, path: string, body: Json): boolean {
  const required = env("SITE_API_TOKEN");
  if (!required) return true;
  if (SITE_TOKEN_EXEMPT.has(path)) return true;
  if (path.startsWith("/api/download/")) return true;
  if (path.startsWith("/api/pins/verify/")) return true;
  return siteTokenFrom(req, body) === required;
}

function userFromRow(row: Json): Json {
  return {
    discordId: row.discord_id,
    username: row.username || "Unknown",
    avatarHash: row.avatar_hash || "",
    userToken: row.user_token || "",
    panelRole: row.panel_role || "member",
    licensedStatus: row.licensed_status || "Standard",
    firstSeen: row.first_seen,
    joinedAt: row.joined_at || row.first_seen,
    lastSeen: row.last_seen,
    loginCount: Number(row.login_count || 0),
    licenseExpiresAt: row.license_expires_at,
    licenseKeyId: row.license_key_id,
    licenseGrantedAt: row.license_granted_at,
    licenseRevokedAt: row.license_revoked_at,
    licenseRevokedBy: row.license_revoked_by,
    promotedAt: row.promoted_at,
  };
}

function pinFromRow(row: Json): Json {
  return {
    id: row.id,
    pin: row.pin,
    discordId: row.discord_id,
    playerName: row.player_name || "—",
    game: row.game || "FiveM",
    status: row.status || "pending",
    result: row.result || "Pending",
    date: row.date,
    scanId: row.scan_id,
  };
}

function scanFromRow(row: Json): Json {
  return {
    id: row.id,
    discordId: row.discord_id,
    pinId: row.pin_id,
    pin: row.pin,
    date: row.date,
    playerName: row.player_name || "—",
    verdict: row.verdict || "review",
    threats: Number(row.threats || 0),
    warnings: Number(row.warnings || 0),
    summary: row.summary || "",
    reportText: row.report_text || "",
    hostname: row.hostname || "",
    username: row.username || "",
  };
}

function parseIso(value: unknown): Date | null {
  const raw = String(value || "").trim();
  if (!raw) return null;
  const d = new Date(raw);
  return Number.isNaN(d.getTime()) ? null : d;
}

async function getActiveSiteLicense(discordId: string): Promise<Json | null> {
  const sb = supabase();
  const { data } = await sb.from("site_users").select("*").eq("discord_id", discordId).maybeSingle();
  if (!data) return null;
  const expires = parseIso(data.license_expires_at);
  if (!expires || expires <= new Date()) return null;
  return {
    discordId,
    licenseExpiresAt: expires.toISOString(),
    licenseGrantedAt: data.license_granted_at,
    licenseKeyId: data.license_key_id,
    licensedStatus: "Customer",
  };
}

async function discordRequest(url: string, auth: string): Promise<{ code: number; data: Json | string }> {
  const res = await fetch(url, {
    headers: { Authorization: auth, "User-Agent": "DiscordBot (https://discord.com, 10)" },
  });
  const text = await res.text();
  try {
    return { code: res.status, data: JSON.parse(text) };
  } catch {
    return { code: res.status, data: text };
  }
}

function ownerIds(): Set<string> {
  const ids = new Set(DEFAULT_OWNERS);
  for (const part of env("OWNER_DISCORD_IDS").split(",")) {
    const v = part.trim();
    if (v) ids.add(v);
  }
  return ids;
}

function roleRank(role: string): number {
  return ROLE_RANK[String(role || "member").toLowerCase()] || 0;
}

function resolvePanelRole(userId: string, roles: string[] | null): string {
  if (ownerIds().has(userId)) return "owner";
  const sbRole = ""; // filled from DB in enrichLicense
  void sbRole;
  const stored = ""; // caller merges stored role
  void stored;
  if (Array.isArray(roles)) {
    // guild owner check skipped in edge — owner ids env covers panel owner
  }
  return "member";
}

async function storedPanelRole(userId: string): Promise<string> {
  const sb = supabase();
  const { data } = await sb.from("site_users").select("panel_role").eq("discord_id", userId).maybeSingle();
  const role = String(data?.panel_role || "member").toLowerCase();
  return PANEL_ROLES.has(role) ? role : "member";
}

async function resolveEffectiveRole(userId: string, roles: string[] | null): Promise<string> {
  if (ownerIds().has(userId)) return "owner";
  const stored = await storedPanelRole(userId);
  if (stored !== "member") return stored;
  return resolvePanelRole(userId, roles);
}

async function membershipStatus(userId: string, roles: string[] | null): Promise<string> {
  if (await getActiveSiteLicense(userId)) return "Customer";
  const customerRole = env("DISCORD_CUSTOMER_ROLE_ID", DEFAULT_CUSTOMER_ROLE);
  if (customerRole && Array.isArray(roles) && roles.map(String).includes(customerRole)) return "Customer";
  return "Standard";
}

async function checkLicenseOAuth(userId: string, accessToken: string): Promise<Json> {
  const guild = env("DISCORD_GUILD_ID", DEFAULT_GUILD);
  const { code, data } = await discordRequest(
    `https://discord.com/api/v10/users/@me/guilds/${guild}/member`,
    `Bearer ${accessToken}`,
  );
  if (code === 200 && typeof data === "object") {
    const memberUser = String((data.user as Json)?.id || "");
    if (memberUser && memberUser !== userId) return { status: "Standard", error: "token_user_mismatch" };
    const roles = Array.isArray(data.roles) ? data.roles.map(String) : [];
    const active = await getActiveSiteLicense(userId);
    const payload: Json = { status: await membershipStatus(userId, roles), roles, method: "oauth" };
    if (active) {
      payload.licenseExpiresAt = active.licenseExpiresAt;
      payload.licenseGrantedAt = active.licenseGrantedAt;
      payload.licenseSource = "site_key";
    }
    return payload;
  }
  if (code === 401) return { status: "Standard", error: "oauth_expired", message: "Sign out and log in again." };
  if (code === 404) return { status: "Standard", error: "not_in_guild", message: "You are not in the dotx Discord server." };
  if (code === 403) {
    return { status: "Standard", error: "oauth_forbidden", message: "Re-login to allow dotx to read your server roles." };
  }
  const message = typeof data === "object" ? String((data as Json).message || "") : String(data).slice(0, 200);
  return { status: "Standard", error: `discord_${code}`, message };
}

async function checkLicenseBot(userId: string): Promise<Json> {
  const bot = env("DISCORD_BOT_TOKEN");
  const guild = env("DISCORD_GUILD_ID", DEFAULT_GUILD);
  if (!bot) {
    const active = await getActiveSiteLicense(userId);
    if (active) {
      return {
        status: "Customer",
        roles: [],
        method: "site_key",
        licenseExpiresAt: active.licenseExpiresAt,
        licenseGrantedAt: active.licenseGrantedAt,
        licenseSource: "site_key",
      };
    }
    return { status: "Standard", error: "bot_not_configured", message: "Discord bot token not configured." };
  }
  const { code, data } = await discordRequest(
    `https://discord.com/api/v10/guilds/${guild}/members/${userId}`,
    `Bot ${bot}`,
  );
  if (code === 200 && typeof data === "object") {
    const roles = Array.isArray(data.roles) ? data.roles.map(String) : [];
    const active = await getActiveSiteLicense(userId);
    const payload: Json = { status: await membershipStatus(userId, roles), roles, method: "bot" };
    if (active) {
      payload.licenseExpiresAt = active.licenseExpiresAt;
      payload.licenseGrantedAt = active.licenseGrantedAt;
      payload.licenseSource = "site_key";
    }
    return payload;
  }
  if (code === 404) {
    return {
      status: "Standard",
      error: "not_in_guild",
      message: "Enable Server Members Intent on your bot, or sign out and log in again.",
    };
  }
  const message = typeof data === "object" ? String((data as Json).message || "") : String(data).slice(0, 200);
  return { status: "Standard", error: `discord_${code}`, message };
}

async function enrichLicense(userId: string, payload: Json): Promise<Json> {
  const roles = Array.isArray(payload.roles) ? (payload.roles as string[]) : [];
  const panelRole = await resolveEffectiveRole(userId, roles);
  return {
    ...payload,
    panelRole,
    isOwner: panelRole === "owner",
    isAdmin: panelRole === "owner" || panelRole === "admin",
    isStaff: panelRole === "owner" || panelRole === "admin" || panelRole === "staff",
  };
}

async function checkLicense(userId: string, accessToken?: string | null): Promise<Json> {
  const active = await getActiveSiteLicense(userId);
  if (active) {
    return enrichLicense(userId, {
      status: "Customer",
      licenseExpiresAt: active.licenseExpiresAt,
      licenseGrantedAt: active.licenseGrantedAt,
      licenseSource: "site_key",
      licenseActive: true,
      method: "site_key",
      roles: [],
    });
  }
  if (accessToken) {
    const oauth = await checkLicenseOAuth(userId, accessToken);
    if (
      oauth.method === "oauth" ||
      ["oauth_expired", "oauth_forbidden", "not_in_guild", "token_user_mismatch"].includes(String(oauth.error || ""))
    ) {
      return enrichLicense(userId, { ...oauth, licenseActive: false });
    }
  }
  const bot = await checkLicenseBot(userId);
  return enrichLicense(userId, { ...bot, licenseActive: (await getActiveSiteLicense(userId)) !== null });
}

function isCustomerLicense(info: Json): boolean {
  if (String(info.status || "") === "Customer") return true;
  const panel = String(info.panelRole || "member").toLowerCase();
  return panel === "owner" || panel === "admin" || panel === "staff";
}

async function customerContext(
  req: Request,
  body: Json,
  discordId = "",
): Promise<{ userId: string; token: string | null; license: Json } | null> {
  const userId = String(discordId || body.discordId || "").trim();
  const token = String(body.accessToken || req.headers.get("X-Discord-Token") || "").trim() || null;
  if (!userId || !token) return null;
  const license = await checkLicense(userId, token);
  if (license.error === "token_user_mismatch") return null;
  if (!isCustomerLicense(license)) return null;
  return { userId, token, license };
}

function mapScannerVerdict(verdict: string): [string, string, string] {
  const value = String(verdict || "").toUpperCase();
  if (value === "CLEAN") return ["passed", "Clean", "finished"];
  if (value === "REVIEW NEEDED") return ["review", "Review", "finished"];
  if (value === "SUSPICIOUS") return ["suspicious", "Suspicious", "cheated"];
  if (value === "CHEATING LIKELY") return ["failed", "Cheated", "cheated"];
  return ["review", "Review", "finished"];
}

function publicBaseUrl(req: Request): string {
  return env("PUBLIC_URL", env("CUSTOM_SITE_URL", "https://dotx.store")).replace(/\/$/, "");
}

function apiBaseForTool(req: Request): string {
  const url = new URL(req.url);
  const idx = url.pathname.indexOf("/functions/v1/");
  if (idx >= 0) {
    const prefix = url.pathname.slice(0, idx + "/functions/v1/dotx".length);
    return `${url.origin}${prefix}`;
  }
  return `${DEFAULT_SUPABASE_URL}/functions/v1/dotx`;
}

function stampExe(bytes: Uint8Array, serverUrl: string): Uint8Array {
  const marker = new TextEncoder().encode(DOTX_CONFIG_MARKER);
  let end = bytes.length;
  for (let i = bytes.length - marker.length; i >= 0; i--) {
    let ok = true;
    for (let j = 0; j < marker.length; j++) {
      if (bytes[i + j] !== marker[j]) {
        ok = false;
        break;
      }
    }
    if (ok) {
      end = i;
      break;
    }
  }
  const config = new TextEncoder().encode(JSON.stringify({ serverUrl }));
  const out = new Uint8Array(end + marker.length + config.length);
  out.set(bytes.slice(0, end), 0);
  out.set(marker, end);
  out.set(config, end + marker.length);
  return out;
}

async function buildRoleDashboard(includeUsers: boolean, actorRole: string): Promise<Json> {
  const sb = supabase();
  const [{ data: users }, { data: pins }, { data: scans }] = await Promise.all([
    sb.from("site_users").select("*"),
    sb.from("pins").select("*").order("date", { ascending: false }),
    sb.from("scans").select("*").order("date", { ascending: false }),
  ]);
  const pinRows = (pins || []).map(pinFromRow);
  const scanRows = (scans || []).map(scanFromRow);
  const roleCounts: Record<string, number> = { owner: 0, admin: 0, staff: 0, member: 0 };
  const enriched: Json[] = [];
  for (const row of users || []) {
    const user = userFromRow(row as Json);
    const effective = await resolveEffectiveRole(String(user.discordId), null);
    roleCounts[effective] = (roleCounts[effective] || 0) + 1;
    if (includeUsers) {
      const uid = String(user.discordId);
      enriched.push({
        ...user,
        panelRole: effective,
        storedRole: user.panelRole,
        pins: pinRows.filter((p) => String(p.discordId) === uid).length,
        scans: scanRows.filter((s) => String(s.discordId) === uid).length,
      });
    }
  }
  enriched.sort(
    (a, b) =>
      (ROLE_RANK[String(b.panelRole || "member")] || 0) - (ROLE_RANK[String(a.panelRole || "member")] || 0),
  );
  const verdicts: Record<string, number> = { passed: 0, review: 0, suspicious: 0, failed: 0 };
  for (const scan of scanRows) {
    const key = String(scan.verdict || "review");
    verdicts[key] = (verdicts[key] || 0) + 1;
  }
  return {
    actorRole,
    totals: {
      siteUsers: (users || []).length,
      pins: pinRows.length,
      scans: scanRows.length,
      staff: roleCounts.staff || 0,
      admins: roleCounts.admin || 0,
      members: roleCounts.member || 0,
    },
    roleCounts,
    verdicts,
    siteUsers: enriched,
    recentPins: pinRows.slice(0, 15),
    recentScans: scanRows.slice(0, 15),
  };
}

async function handleApi(req: Request): Promise<Response> {
  const path = apiPath(req);
  const body = req.method === "GET" ? {} : await readJson(req);
  if (!siteTokenOk(req, path, body)) return errorResponse(req, "invalid_site_token", 401);

  if (path === "/api/health" && req.method === "GET") {
    return jsonResponse(req, { ok: true, service: "dotx-api", database: "supabase" });
  }

  if (path === "/api/pins" && req.method === "POST") {
    const ctx = await customerContext(req, body);
    if (!ctx) return errorResponse(req, "license_required", 403);
    if (String(body.discordId || "").trim() !== ctx.userId) return errorResponse(req, "forbidden", 403);
    const pinCode = String(body.pin || "").trim();
    const discordId = String(body.discordId || "").trim();
    if (!pinCode || !discordId) return errorResponse(req, "pin and discordId required", 400);
    const sb = supabase();
    const { data: existing } = await sb.from("pins").select("*").eq("pin", pinCode).maybeSingle();
    const now = new Date().toISOString();
    const row = {
      id: String(body.id || existing?.id || `pin_${Date.now()}`),
      pin: pinCode,
      discord_id: discordId,
      player_name: String(body.playerName || existing?.player_name || "—"),
      game: String(body.game || existing?.game || "FiveM"),
      status: existing?.status || "pending",
      result: existing?.result || "Pending",
      date: String(body.date || existing?.date || now),
      scan_id: existing?.scan_id || null,
    };
    const { data, error } = await sb.from("pins").upsert(row, { onConflict: "pin" }).select().single();
    if (error) return errorResponse(req, error.message, 500);
    return jsonResponse(req, { ok: true, pin: pinFromRow(data as Json) });
  }

  if (path.startsWith("/api/pins/verify/") && req.method === "GET") {
    const pinCode = path.split("/").pop() || "";
    if (!/^\d{6}$/.test(pinCode)) return errorResponse(req, "invalid_pin", 404);
    const sb = supabase();
    const { data } = await sb.from("pins").select("*").eq("pin", pinCode).maybeSingle();
    if (!data) return errorResponse(req, "invalid_pin", 404);
    const { data: owner } = await sb.from("site_users").select("*").eq("discord_id", data.discord_id).maybeSingle();
    return jsonResponse(req, {
      ok: true,
      pin: pinCode,
      game: data.game || "FiveM",
      branding: brandingFromUser(owner as Json | null),
    });
  }

  if (path.startsWith("/api/download/") && req.method === "GET") {
    const pinCode = path.split("/").pop() || "";
    if (!/^\d{6}$/.test(pinCode)) return errorResponse(req, "invalid_pin", 404);
    const sb = supabase();
    const { data } = await sb.from("pins").select("pin").eq("pin", pinCode).maybeSingle();
    if (!data) return errorResponse(req, "invalid_pin", 404);
    const exeUrl = env("PUBLIC_EXE_URL", `${publicBaseUrl(req)}/downloads/dotx-pc-check.exe`);
    const exeRes = await fetch(exeUrl);
    if (!exeRes.ok) return errorResponse(req, "tool_not_built", 503);
    const stamped = stampExe(new Uint8Array(await exeRes.arrayBuffer()), apiBaseForTool(req));
    return new Response(stamped, {
      status: 200,
      headers: {
        "Content-Type": "application/octet-stream",
        "Content-Disposition": 'attachment; filename="dotx-pc-check.exe"',
        "Cache-Control": "no-store",
        ...corsHeaders(req),
      },
    });
  }

  if (path.startsWith("/api/pins/") && req.method === "GET") {
    const discordId = path.split("/").pop() || "";
    const ctx = await customerContext(req, body, discordId);
    if (!ctx || ctx.userId !== discordId) return errorResponse(req, "license_required", 403);
    const sb = supabase();
    const { data } = await sb.from("pins").select("*").eq("discord_id", discordId).order("date", { ascending: false });
    return jsonResponse(req, { pins: (data || []).map((r) => pinFromRow(r as Json)) });
  }

  if (path.startsWith("/api/pins/") && req.method === "DELETE") {
    const pinId = path.split("/").pop() || "";
    const ctx = await customerContext(req, body);
    if (!ctx) return errorResponse(req, "license_required", 403);
    const sb = supabase();
    const { data } = await sb.from("pins").delete().eq("id", pinId).eq("discord_id", ctx.userId).select();
    if (!data?.length) return errorResponse(req, "not_found", 404);
    return jsonResponse(req, { ok: true });
  }

  if (path === "/api/scans/submit" && req.method === "POST") {
    const pinCode = String(body.pin || "").trim();
    const sb = supabase();
    const { data: pinRow } = await sb.from("pins").select("*").eq("pin", pinCode).maybeSingle();
    if (!pinRow) return errorResponse(req, "invalid_pin", 404);
    const [verdict, resultLabel, pinStatus] = mapScannerVerdict(String(body.verdict || ""));
    const scanId = String(body.id || `scan_${Date.now()}`);
    const scanRow = {
      id: scanId,
      discord_id: pinRow.discord_id,
      pin_id: pinRow.id,
      pin: pinCode,
      date: String(body.date || new Date().toISOString()),
      player_name: String(body.playerName || pinRow.player_name || "—"),
      verdict,
      threats: Number(body.threats || 0),
      warnings: Number(body.warnings || 0),
      summary: String(body.summary || ""),
      report_text: String(body.reportText || ""),
      hostname: String(body.hostname || ""),
      username: String(body.username || ""),
    };
    await sb.from("scans").insert(scanRow);
    await sb.from("pins").update({ status: pinStatus, result: resultLabel, scan_id: scanId }).eq("pin", pinCode);
    return jsonResponse(req, { ok: true, scan: scanFromRow(scanRow as unknown as Json) });
  }

  if (path.startsWith("/api/scans/") && req.method === "GET") {
    const discordId = path.split("/").pop() || "";
    if (discordId === "submit") return errorResponse(req, "not_found", 404);
    const ctx = await customerContext(req, body, discordId);
    if (!ctx || ctx.userId !== discordId) return errorResponse(req, "license_required", 403);
    const sb = supabase();
    const { data } = await sb.from("scans").select("*").eq("discord_id", discordId).order("date", { ascending: false });
    return jsonResponse(req, { scans: (data || []).map((r) => scanFromRow(r as Json)) });
  }

  if (path === "/api/tool-config" && req.method === "GET") {
    return jsonResponse(req, { serverUrl: apiBaseForTool(req) });
  }

  if (path === "/api/site-config" && req.method === "GET") {
    const base = publicBaseUrl(req);
    return jsonResponse(req, { publicUrl: base, oauthRedirectUri: `${base}/callback/` });
  }

  if (path === "/api/users/register" && req.method === "POST") {
    const discordId = String(body.discordId || "").trim();
    if (!discordId) return errorResponse(req, "discordId required", 400);
    const license = await checkLicense(discordId, String(body.accessToken || ""));
    const sb = supabase();
    const now = new Date().toISOString();
    const { data: existing } = await sb.from("site_users").select("*").eq("discord_id", discordId).maybeSingle();
    const row = {
      discord_id: discordId,
      username: String(body.username || existing?.username || "Unknown"),
      avatar_hash: String(body.avatarHash || existing?.avatar_hash || ""),
      user_token: existing?.user_token || `DX-${crypto.randomUUID().replace(/-/g, "").slice(0, 8).toUpperCase()}`,
      panel_role: existing?.panel_role || "member",
      licensed_status: String(license.status || "Standard"),
      first_seen: existing?.first_seen || now,
      joined_at: existing?.joined_at || existing?.first_seen || now,
      last_seen: now,
      login_count: Number(existing?.login_count || 0) + 1,
      license_expires_at: license.licenseExpiresAt || existing?.license_expires_at || null,
      license_key_id: existing?.license_key_id || null,
      license_granted_at: existing?.license_granted_at || null,
    };
    const { data, error } = await sb.from("site_users").upsert(row, { onConflict: "discord_id" }).select().single();
    if (error) return errorResponse(req, error.message, 500);
    const user = userFromRow(data as Json);
    user.panelRole = String(license.panelRole || user.panelRole);
    return jsonResponse(req, { ok: true, user });
  }

  if (path === "/api/users/branding" && req.method === "POST") {
    const discordId = String(body.discordId || "").trim();
    if (!discordId) return errorResponse(req, "discordId required", 400);
    const ctx = await customerContext(req, body, discordId);
    if (!ctx || ctx.userId !== discordId) {
      if (!ownerIds().has(discordId)) return errorResponse(req, "license_required", 403);
    }
    const brandingIn = (body.branding && typeof body.branding === "object" ? body.branding : {}) as Json;
    const clean: Json = {
      showDiscordAvatar: brandingIn.showDiscordAvatar !== false,
      username: String(brandingIn.username || "").slice(0, 64),
      discordId,
      avatarUrl: String(brandingIn.avatarUrl || "").slice(0, 500),
      customImage: typeof brandingIn.customImage === "string" && brandingIn.customImage.length <= 200000
        ? brandingIn.customImage
        : null,
    };
    const sb = supabase();
    const { data, error } = await sb
      .from("site_users")
      .update({ tool_branding: clean })
      .eq("discord_id", discordId)
      .select("*")
      .maybeSingle();
    if (error) return errorResponse(req, error.message, 500);
    if (!data) return errorResponse(req, "user_not_found", 404);
    return jsonResponse(req, { ok: true, branding: clean });
  }

  if (path.startsWith("/api/license/") && (req.method === "GET" || req.method === "POST")) {
    const userId = path.split("/").pop() || "";
    const token = String(body.accessToken || req.headers.get("X-Discord-Token") || "");
    return jsonResponse(req, await checkLicense(userId, token || null));
  }

  if (path === "/api/owner/overview" && (req.method === "GET" || req.method === "POST")) {
    const ctx = await customerContext(req, body);
    if (!ctx || String(ctx.license.panelRole) !== "owner") return errorResponse(req, "forbidden", 403);
    return jsonResponse(req, await buildRoleDashboard(true, "owner"));
  }

  if (path === "/api/admin/overview" && (req.method === "GET" || req.method === "POST")) {
    const ctx = await customerContext(req, body);
    const role = String(ctx?.license.panelRole || "");
    if (!ctx || (role !== "owner" && role !== "admin")) return errorResponse(req, "forbidden", 403);
    return jsonResponse(req, await buildRoleDashboard(true, role));
  }

  if (path === "/api/staff/overview" && (req.method === "GET" || req.method === "POST")) {
    const ctx = await customerContext(req, body);
    const role = String(ctx?.license.panelRole || "");
    if (!ctx || !["owner", "admin", "staff"].includes(role)) return errorResponse(req, "forbidden", 403);
    return jsonResponse(req, await buildRoleDashboard(false, role));
  }

  return errorResponse(req, "not_found", 404);
}

Deno.serve(async (req) => {
  if (req.method === "OPTIONS") {
    return new Response(null, { status: 204, headers: corsHeaders(req) });
  }
  try {
    return await handleApi(req);
  } catch (err) {
    const message = err instanceof Error ? err.message : "internal_error";
    return errorResponse(req, message, 500);
  }
});
