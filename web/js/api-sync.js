const API_BASE = apiBaseUrl;

async function apiRequest(path, options = {}) {
  const res = await fetch(`${API_BASE()}${path}`, {
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
    ...options,
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    throw new Error(data.error || data.message || `Request failed (${res.status})`);
  }
  return data;
}

async function registerPinOnServer(pin) {
  return apiRequest("/api/pins", {
    method: "POST",
    body: JSON.stringify(pin),
  });
}

async function fetchPinsFromServer(discordId) {
  const data = await apiRequest(`/api/pins/${encodeURIComponent(discordId)}`);
  return data.pins || [];
}

async function deletePinOnServer(discordId, pinId) {
  return apiRequest(`/api/pins/${encodeURIComponent(pinId)}`, {
    method: "DELETE",
    body: JSON.stringify({ discordId }),
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
  try {
    const [pins, scans] = await Promise.all([
      fetchPinsFromServer(discordId),
      fetchScansFromServer(discordId),
    ]);
    mergePinsLocal(discordId, pins);
    mergeScansLocal(discordId, scans);
    return { pins, scans };
  } catch {
    return { pins: getPins(discordId), scans: getScans(discordId) };
  }
}
