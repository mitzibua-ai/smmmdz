const PINS_KEY = "dotx_pins_v1";

function getPinsKey(discordId) {
  return `${PINS_KEY}_${discordId}`;
}

function getPins(discordId) {
  try {
    const raw = localStorage.getItem(getPinsKey(discordId));
    return raw ? JSON.parse(raw) : [];
  } catch {
    return [];
  }
}

function savePins(discordId, pins) {
  localStorage.setItem(getPinsKey(discordId), JSON.stringify(pins));
}

function generatePinCode(discordId) {
  const used = new Set(getPins(discordId).map((p) => p.pin));
  let pin = "";
  for (let i = 0; i < 50; i++) {
    pin = String(Math.floor(100000 + Math.random() * 900000));
    if (!used.has(pin)) return pin;
  }
  return pin;
}

function addPin(discordId, data) {
  if (typeof isCustomerAccount === "function" && !isCustomerAccount()) {
    throw new Error("license_required");
  }
  const pins = getPins(discordId);
  const pin = {
    id: `pin_${Date.now()}`,
    pin: generatePinCode(discordId),
    playerName: data.playerName?.trim() || "—",
    game: data.game || "FiveM",
    status: "pending",
    result: "Pending",
    date: new Date().toISOString(),
    notes: "",
  };
  pins.unshift(pin);
  savePins(discordId, pins);
  return pin;
}

function getPin(discordId, pinId) {
  return getPins(discordId).find((p) => p.id === pinId) || null;
}

function updatePin(discordId, pinId, patch) {
  const pins = getPins(discordId);
  const idx = pins.findIndex((p) => p.id === pinId);
  if (idx === -1) return null;
  pins[idx] = { ...pins[idx], ...patch };
  savePins(discordId, pins);
  return pins[idx];
}

function deletePin(discordId, pinId) {
  const pins = getPins(discordId);
  const next = pins.filter((p) => p.id !== pinId);
  if (next.length === pins.length) return false;
  savePins(discordId, next);
  return true;
}

function computePinStats(pins) {
  let pending = 0;
  let finished = 0;
  let cheated = 0;

  for (const p of pins) {
    if (p.status === "cheated") cheated++;
    else if (p.status === "finished") finished++;
    else pending++;
  }

  return { total: pins.length, pending, finished, cheated };
}

function pinResultClass(result) {
  const lower = String(result).toLowerCase();
  if (lower.includes("cheat") || lower === "failed") return "pin-tag--cheated";
  if (lower.includes("clean") || lower.includes("pass") || lower === "finished") return "pin-tag--finished";
  return "pin-tag--pending";
}

function getPinShareUrl(pinCode) {
  const base = window.location.origin.replace(/\/$/, "");
  const code = String(pinCode || "").trim();
  if (!/^\d{6}$/.test(code)) return `${base}/downloads/`;
  return `${base}/downloads/?pin=${encodeURIComponent(code)}`;
}

function getPcCheckToolDownloadUrl(pinCode) {
  const code = String(pinCode || "").trim();
  if (/^\d{6}$/.test(code)) {
    return getPinShareUrl(code);
  }
  return getPinShareUrl("");
}

function getPcCheckToolDirectUrl(pinCode) {
  const code = String(pinCode || "").trim();
  const base = apiBaseUrl();
  if (base && /^\d{6}$/.test(code)) {
    return `${base.replace(/\/$/, "")}/api/download/${encodeURIComponent(code)}`;
  }
  return getPinShareUrl(code);
}

function copyText(text) {
  if (navigator.clipboard?.writeText) {
    return navigator.clipboard.writeText(text);
  }
  const ta = document.createElement("textarea");
  ta.value = text;
  document.body.appendChild(ta);
  ta.select();
  document.execCommand("copy");
  ta.remove();
  return Promise.resolve();
}

function copyPinCode(pin) {
  return copyText(pin);
}

function copyPinShareLink(pinCode) {
  return copyText(getPinShareUrl(pinCode));
}
