const API_BASE = apiBaseUrl;

function apiAuthHeaders(extra = {}) {
  const acc = getAccount();
  const headers = { "Content-Type": "application/json", ...extra };
  if (acc?.discordAccessToken) {
    headers["X-Discord-Token"] = acc.discordAccessToken;
  }
  return headers;
}

function apiAuthBody(payload = {}) {
  const acc = getAccount();
  const body = { ...payload };
  if (acc?.discordId && !body.discordId) {
    body.discordId = acc.discordId;
  }
  if (acc?.discordAccessToken && !body.accessToken) {
    body.accessToken = acc.discordAccessToken;
  }
  return body;
}

async function apiRequest(path, options = {}) {
  const headers = apiAuthHeaders(options.headers || {});
  let body = options.body;
  if (body && typeof body === "object" && !(body instanceof FormData)) {
    body = JSON.stringify(apiAuthBody(body));
  }

  const init = { ...options, headers };
  if (body !== undefined && String(options.method || "GET").toUpperCase() !== "GET") {
    init.body = body;
  } else {
    delete init.body;
  }

  const res = await fetch(`${API_BASE()}${path}`, init);
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    const err = new Error(data.error || data.message || `Request failed (${res.status})`);
    err.code = data.error || null;
    err.status = res.status;
    throw err;
  }
  return data;
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

function mergePinsLocal(discordId, serverPins) {
  const local = getPins(discordId);
  const byId = new Map(local.map((p) => [p.id, p]));
  for (const pin of serverPins) {
    byId.set(pin.id, { ...byId.get(pin.id), ...pin });
  }
  const merged = Array.from(byId.values()).sort(
    (a, b) => new Date(b.date) - new Date(a.date)
  );
  savePins(discordId, merged);
  return merged;
}

function mergeScansLocal(discordId, serverScans) {
  const local = getScans(discordId);
  const byId = new Map(local.map((s) => [s.id, s]));
  for (const scan of serverScans) {
    byId.set(scan.id, { ...byId.get(scan.id), ...scan });
  }
  const merged = Array.from(byId.values()).sort(
    (a, b) => new Date(b.date) - new Date(a.date)
  );
  saveScans(discordId, merged);
  return merged;
}

async function syncDashboardData(discordId) {
  if (!isCustomerAccount(getAccount())) {
    return { pins: [], scans: [] };
  }
  try {
    const [pins, scans] = await Promise.all([
      fetchPinsFromServer(discordId),
      fetchScansFromServer(discordId),
    ]);
    mergePinsLocal(discordId, pins);
    mergeScansLocal(discordId, scans);
    return { pins, scans };
  } catch (err) {
    if (err?.code === "license_required" || err?.status === 403) {
      return { pins: [], scans: [] };
    }
    return { pins: getPins(discordId), scans: getScans(discordId) };
  }
}
