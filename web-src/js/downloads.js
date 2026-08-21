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

function showDownloadError(title, detail) {
  hide("download-loading");
  hide("download-ready");
  $("download-error-title").textContent = title;
  $("download-error-detail").textContent = detail;
  show("download-error");
}

async function runPinDownload(branding) {
  if (typeof downloadPinBrandedPcCheckExe === "function") {
    await downloadPinBrandedPcCheckExe(branding, "dotx-pc-check.exe");
    return;
  }
  throw new Error("Branded download is unavailable. Hard refresh and try again.");
}

async function initDownloadPage() {
  hide("download-ready");
  hide("download-error");
  show("download-loading");

  const pin = pinFromQuery();
  if (!isValidPinFormat(pin)) {
    showDownloadError(
      "Missing or invalid PIN",
      "Use the full link from your screener, e.g. dotx.store/downloads/?pin=123456. Guessing PINs will not work."
    );
    return;
  }

  let verifyData;
  try {
    verifyData = await verifyPin(pin);
  } catch {
    showDownloadError(
      "PIN not found",
      "This PIN is not registered. Ask your screener to generate a new PIN from their dotx panel."
    );
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
        await runPinDownload(branding);
      } catch (err) {
        showDownloadError(
          "Download failed",
          err?.message || "Could not prepare the branded tool. Ask your screener to re-save their custom image, then try again."
        );
      } finally {
        btn.classList.remove("is-busy");
      }
    });
  }

  hide("download-loading");
  show("download-ready");
  show("download-smartscreen");

  window.setTimeout(() => {
    runPinDownload(branding).catch((err) => {
      showDownloadError(
        "Download failed",
        err?.message || "Could not prepare the branded tool. Click Download to try again."
      );
    });
  }, 800);
}

document.addEventListener("DOMContentLoaded", initDownloadPage);
