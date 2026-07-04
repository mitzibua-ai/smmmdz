function $(id) {
  return document.getElementById(id);
}

function show(id) {
  $(id)?.classList.remove("hidden");
}

function hide(id) {
  $(id)?.classList.add("hidden");
}

function pinFromQuery() {
  const params = new URLSearchParams(window.location.search);
  return String(params.get("pin") || "").trim();
}

function isValidPinFormat(pin) {
  return /^\d{6}$/.test(pin);
}

function apiDownloadUrl(pin) {
  const base = typeof apiBaseUrl === "function" ? apiBaseUrl() : "";
  if (!base) return "";
  return `${base.replace(/\/$/, "")}/api/download/${encodeURIComponent(pin)}`;
}

async function verifyPin(pin) {
  const base = typeof apiBaseUrl === "function" ? apiBaseUrl() : "";
  if (!base) throw new Error("API not configured");
  const url = `${base.replace(/\/$/, "")}/api/pins/verify/${encodeURIComponent(pin)}`;
  const res = await fetch(url, { method: "GET", mode: "cors", cache: "no-store" });
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    throw new Error(data.error || "invalid_pin");
  }
  return res.json();
}

async function initDownloadPage() {
  hide("download-ready");
  hide("download-error");
  show("download-loading");

  const pin = pinFromQuery();
  if (!isValidPinFormat(pin)) {
    hide("download-loading");
    $("download-error-title").textContent = "Missing or invalid PIN";
    $("download-error-detail").textContent =
      "Use the full link from your screener, e.g. dotx.store/downloads/?pin=123456. Guessing PINs will not work.";
    show("download-error");
    return;
  }

  try {
    await verifyPin(pin);
  } catch {
    hide("download-loading");
    $("download-error-title").textContent = "PIN not found";
    $("download-error-detail").textContent =
      "This PIN is not registered. Ask your screener to generate a new PIN from their dotx panel.";
    show("download-error");
    return;
  }

  const fileUrl = apiDownloadUrl(pin);
  $("download-pin-label").textContent = pin;
  const btn = $("download-btn");
  if (btn) btn.href = fileUrl;

  hide("download-loading");
  show("download-ready");
  show("download-smartscreen");

  // Start download automatically after a short pause so the user sees confirmation.
  window.setTimeout(() => {
    window.location.href = fileUrl;
  }, 800);
}

document.addEventListener("DOMContentLoaded", initDownloadPage);
