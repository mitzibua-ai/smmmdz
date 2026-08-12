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
  if (typeof useSupabaseDirect === "function" && useSupabaseDirect()) {
    return supabaseRpc("verify_pin_rpc", { p_pin: pin });
  }
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

function staticExeDownloadUrl() {
  const rel = window.SITE_CONFIG?.pcCheckToolUrl || "/downloads/dotx-pc-check.exe";
  return new URL(rel, window.location.origin).href;
}

async function downloadPinBrandedExe(pin, branding) {
  const baseUrl = staticExeDownloadUrl();
  if (typeof fetchExeBytes !== "function" || typeof stampExeBytes !== "function") {
    window.location.href = baseUrl;
    return;
  }
  const stamp = {
    supabaseUrl: window.SITE_CONFIG?.supabaseUrl || "",
    supabaseAnonKey: window.SITE_CONFIG?.supabaseAnonKey || "",
    branding: branding || null,
  };
  const raw = await fetchExeBytes(baseUrl);
  const stamped = stampExeBytes(raw, stamp);
  if (typeof downloadStampedExe === "function") {
    downloadStampedExe(stamped, "dotx-pc-check.exe");
  } else {
    window.location.href = baseUrl;
  }
}

function normalizePinBranding(data) {
  const b = data?.branding;
  if (!b || typeof b !== "object") return null;
  return {
    showDiscordAvatar: b.showDiscordAvatar !== false,
    username: String(b.username || "").slice(0, 64),
    discordId: String(b.discordId || ""),
    avatarUrl: String(b.avatarUrl || "").slice(0, 500),
    customImage: b.customImage || null,
  };
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

  let verifyData;
  try {
    verifyData = await verifyPin(pin);
  } catch {
    hide("download-loading");
    $("download-error-title").textContent = "PIN not found";
    $("download-error-detail").textContent =
      "This PIN is not registered. Ask your screener to generate a new PIN from their dotx panel.";
    show("download-error");
    return;
  }

  const branding = normalizePinBranding(verifyData);
  $("download-pin-label").textContent = pin;
  const btn = $("download-btn");
  if (btn) {
    btn.removeAttribute("href");
    btn.addEventListener("click", async (e) => {
      e.preventDefault();
      btn.classList.add("is-busy");
      try {
        await downloadPinBrandedExe(pin, branding);
      } catch {
        window.location.href = staticExeDownloadUrl();
      } finally {
        btn.classList.remove("is-busy");
      }
    });
  }

  hide("download-loading");
  show("download-ready");
  show("download-smartscreen");

  window.setTimeout(() => {
    downloadPinBrandedExe(pin, branding).catch(() => {
      window.location.href = staticExeDownloadUrl();
    });
  }, 800);
}

document.addEventListener("DOMContentLoaded", initDownloadPage);
