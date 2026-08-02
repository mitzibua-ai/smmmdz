const API_BASE = apiBaseUrl;

function apiAuthHeaders(extra = {}, method = "GET") {
  const acc = getAccount();
  const headers = { ...extra };
  if (String(method).toUpperCase() !== "GET") {
    headers["Content-Type"] = "application/json";
  }
  const siteToken = typeof siteApiToken === "function" ? siteApiToken() : "";
  if (siteToken) {
    headers["X-Site-Token"] = siteToken;
  }
  if (acc?.discordAccessToken) {
    headers["X-Discord-Token"] = acc.discordAccessToken;
  }
  return headers;
}

function apiAuthBody(payload = {}) {
  const acc = getAccount();
  const body = { ...payload };
  const siteToken = typeof siteApiToken === "function" ? siteApiToken() : "";
  if (siteToken && !body.siteToken) {
    body.siteToken = siteToken;
  }
  if (acc?.discordId && !body.discordId) {
    body.discordId = acc.discordId;
  }
  if (acc?.discordAccessToken && !body.accessToken) {
    body.accessToken = acc.discordAccessToken;
  }
  return body;
}

async function apiRequest(path, options = {}) {
  if (typeof useSupabaseDirect === "function" && useSupabaseDirect()) {
    return supabaseApiRequest(path, options);
  }

  const method = String(options.method || "GET").toUpperCase();
  const headers = apiAuthHeaders(options.headers || {}, method);
  let body = options.body;
  if (body && typeof body === "object" && !(body instanceof FormData)) {
    body = JSON.stringify(apiAuthBody(body));
  }

  const init = { ...options, headers, mode: "cors", cache: "no-store" };
  if (body !== undefined && String(options.method || "GET").toUpperCase() !== "GET") {
    init.body = body;
  } else {
    delete init.body;
  }

  const url = typeof apiUrlWithToken === "function" ? apiUrlWithToken(path) : `${API_BASE()}${path}`;
  const res = await fetch(url, init);
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    const err = new Error(data.error || data.message || `Request failed (${res.status})`);
    err.code = data.error || null;
    err.status = res.status;
    throw err;
  }
  return data;
}

function apiFetchErrorMessage(err) {
  const msg = String(err?.message || "");
  if (msg === "Failed to fetch" || err?.name === "TypeError" || err?.name === "AbortError") {
    if (typeof useSupabaseDirect === "function" && !useSupabaseDirect()) {
      return "Add supabaseAnonKey to config.js (Supabase → Settings → API → anon public key), then run push-supabase.bat.";
    }
    if (typeof useSupabaseDirect === "function" && useSupabaseDirect()) {
      return "Could not reach Supabase. Run supabase/schema.sql and supabase/rpc.sql in your Supabase SQL Editor.";
    }
    if (typeof siteApiToken === "function" && !siteApiToken()) {
      return "Could not reach the API. Set apiToken in config.js (must match Supabase SITE_API_TOKEN).";
    }
    const api = typeof apiBaseUrl === "function" ? apiBaseUrl() : "";
    return (
      "Supabase API is offline. Check your Edge Function is deployed (push-supabase.bat). " +
      (api ? `API: ${api}` : "")
    );
  }
  if (err?.code === "invalid_site_token" || err?.status === 401) {
    return "API security token mismatch. Update apiToken in config.js to match Supabase SITE_API_TOKEN.";
  }
  return msg || "Request failed.";
}

async function registerPinOnServer(pin) {
  return apiRequest("/api/pins", {
    method: "POST",
    body: apiAuthBody(pin),
  });
}

async function fetchPinsFromServer(discordId) {
  const data = await apiRequest(`/api/pins/${encodeURIComponent(discordId)}`);
  return data.pins || [];
}

async function deletePinOnServer(discordId, pinId) {
  return apiRequest(`/api/pins/${encodeURIComponent(pinId)}`, {
    method: "DELETE",
    body: apiAuthBody({ discordId }),
  });
}

async function deletePinEverywhere(discordId, pinId) {
  deletePin(discordId, pinId);
  try {
    await deletePinOnServer(discordId, pinId);
  } catch {
    // Pin may only exist locally if it was never synced.
  }
}

async function fetchScansFromServer(discordId) {
  const data = await apiRequest(`/api/scans/${encodeURIComponent(discordId)}`);
  return data.scans || [];
}

function pinCodeKey(pin) {
  return String(pin?.pin || "").trim();
}

function verdictToPinFields(verdict) {
  const v = String(verdict || "").toLowerCase();
  if (v === "failed" || v === "suspicious") {
    return {
      status: "cheated",
      result: v === "failed" ? "Cheated" : "Suspicious",
    };
  }
  if (v === "passed") return { status: "finished", result: "Clean" };
  if (v === "review") return { status: "finished", result: "Review" };
  return { status: "finished", result: "Review" };
}

function mergePinsLocal(discordId, serverPins) {
  const local = getPins(discordId);
  const byCode = new Map();

  for (const pin of local) {
    const code = pinCodeKey(pin);
    if (!code) continue;
    byCode.set(code, { ...pin });
  }

  for (const pin of serverPins || []) {
    const code = pinCodeKey(pin);
    if (!code) continue;
    const prev = byCode.get(code) || {};
    byCode.set(code, {
      ...prev,
      ...pin,
      // Server row is source of truth for result linkage after a scan uploads
      id: pin.id || prev.id,
      status: pin.status || prev.status || "pending",
      result: pin.result || prev.result || "Pending",
      scanId: pin.scanId || pin.scan_id || prev.scanId || null,
    });
  }

  const merged = Array.from(byCode.values()).sort(
    (a, b) => new Date(b.date) - new Date(a.date)
  );
  savePins(discordId, merged);
  return merged;
}

function mergeScansLocal(discordId, serverScans) {
  const local = getScans(discordId);
  const byId = new Map(local.map((s) => [s.id, s]));
  for (const scan of serverScans || []) {
    byId.set(scan.id, { ...byId.get(scan.id), ...scan });
  }
  const merged = Array.from(byId.values()).sort(
    (a, b) => new Date(b.date) - new Date(a.date)
  );
  saveScans(discordId, merged);
  applyScansToPins(discordId, merged);
  return merged;
}

function applyScansToPins(discordId, scans) {
  const pins = getPins(discordId);
  let changed = false;
  for (const scan of scans || []) {
    const code = String(scan.pin || "").trim();
    if (!code || !scan.id) continue;
    const idx = pins.findIndex((p) => pinCodeKey(p) === code);
    if (idx === -1) continue;
    const mapped = verdictToPinFields(scan.verdict);
    const next = {
      ...pins[idx],
      scanId: scan.id,
      status:
        pins[idx].status && pins[idx].status !== "pending"
          ? pins[idx].status
          : mapped.status,
      result:
        pins[idx].result && String(pins[idx].result).toLowerCase() !== "pending"
          ? pins[idx].result
          : mapped.result,
    };
    if (
      next.scanId !== pins[idx].scanId ||
      next.status !== pins[idx].status ||
      next.result !== pins[idx].result
    ) {
      pins[idx] = next;
      changed = true;
    }
  }
  if (changed) savePins(discordId, pins);
  return pins;
}

async function syncDashboardData(discordId) {
  if (!isCustomerAccount(getAccount())) {
    return { pins: getPins(discordId), scans: getScans(discordId) };
  }
  try {
    const [pins, scans] = await Promise.all([
      fetchPinsFromServer(discordId),
      fetchScansFromServer(discordId),
    ]);
    const mergedPins = mergePinsLocal(discordId, pins);
    const mergedScans = mergeScansLocal(discordId, scans);
    return { pins: mergedPins, scans: mergedScans };
  } catch (err) {
    if (err?.code === "license_required" || err?.status === 403) {
      return { pins: getPins(discordId), scans: getScans(discordId) };
    }
    return { pins: getPins(discordId), scans: getScans(discordId) };
  }
}
