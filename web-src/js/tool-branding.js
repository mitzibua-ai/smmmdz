/** PC Check EXE branding — Account settings + download stamp helpers. */
const TOOL_BRANDING_KEY = "dotx_tool_branding_v1";
/** Keep under every backend limit (RPC 320k, edge/legacy 200k). Base64 expands ~4/3. */
const MAX_BRAND_IMAGE_CHARS = 180_000;
const MAX_BRAND_EDGE = 640;

function defaultToolBranding(acc = typeof getAccount === "function" ? getAccount() : null) {
  return {
    customImage: null,
    customImageName: "",
    showDiscordAvatar: true,
    username: acc?.username || "",
    discordId: acc?.discordId || "",
    avatarUrl: acc?.avatar || "",
    updatedAt: Date.now(),
  };
}

function loadToolBranding(acc = typeof getAccount === "function" ? getAccount() : null) {
  try {
    const raw = localStorage.getItem(TOOL_BRANDING_KEY);
    if (!raw) return defaultToolBranding(acc);
    const data = JSON.parse(raw);
    const base = defaultToolBranding(acc);
    return {
      ...base,
      ...data,
      username: acc?.username || data.username || base.username,
      discordId: acc?.discordId || data.discordId || base.discordId,
      avatarUrl: acc?.avatar || data.avatarUrl || base.avatarUrl,
      showDiscordAvatar: data.showDiscordAvatar !== false,
    };
  } catch {
    return defaultToolBranding(acc);
  }
}

function saveToolBranding(branding) {
  const payload = {
    customImage: branding.customImage || null,
    customImageName: branding.customImageName || "",
    showDiscordAvatar: branding.showDiscordAvatar !== false,
    username: branding.username || "",
    discordId: branding.discordId || "",
    avatarUrl: branding.avatarUrl || "",
    updatedAt: Date.now(),
  };
  localStorage.setItem(TOOL_BRANDING_KEY, JSON.stringify(payload));
  return payload;
}

function clearToolCustomImage() {
  const branding = loadToolBranding();
  branding.customImage = null;
  branding.customImageName = "";
  return saveToolBranding(branding);
}

function compressImageFile(file) {
  return new Promise((resolve, reject) => {
    if (!file || !file.type.startsWith("image/")) {
      reject(new Error("Choose an image or GIF file."));
      return;
    }
    if (file.size > 4 * 1024 * 1024) {
      reject(new Error("Image must be under 4 MB."));
      return;
    }

    // Always rasterize to PNG (first GIF frame). Raw GIFs blow past sync limits and
    // animated GIFs often fail in the tkinter EXE — PNG stamps reliably into the panel.
    const url = URL.createObjectURL(file);
    const img = new Image();
    img.onload = () => {
      try {
        const canvas = document.createElement("canvas");
        const ctx = canvas.getContext("2d");
        let edge = MAX_BRAND_EDGE;
        let dataUrl = "";
        for (let attempt = 0; attempt < 8; attempt += 1) {
          const scale = Math.min(1, edge / Math.max(img.width, img.height, 1));
          const w = Math.max(1, Math.round(img.width * scale));
          const h = Math.max(1, Math.round(img.height * scale));
          canvas.width = w;
          canvas.height = h;
          ctx.clearRect(0, 0, w, h);
          ctx.drawImage(img, 0, 0, w, h);
          // PNG only — the EXE UI (tkinter) cannot load JPEG without Pillow.
          dataUrl = canvas.toDataURL("image/png");
          if (dataUrl.length <= MAX_BRAND_IMAGE_CHARS) break;
          edge = Math.max(160, Math.round(edge * 0.72));
        }
        URL.revokeObjectURL(url);
        if (!dataUrl || dataUrl.length > MAX_BRAND_IMAGE_CHARS) {
          reject(new Error("Image is still too large. Use a smaller file."));
          return;
        }
        resolve({ dataUrl, name: file.name });
      } catch (err) {
        URL.revokeObjectURL(url);
        reject(err);
      }
    };
    img.onerror = () => {
      URL.revokeObjectURL(url);
      reject(new Error("Could not load image."));
    };
    img.src = url;
  });
}

function brandingStampPayload(branding, acc = typeof getAccount === "function" ? getAccount() : null) {
  const b = branding || loadToolBranding(acc);
  return {
    showDiscordAvatar: b.showDiscordAvatar !== false,
    username: (acc?.username || b.username || "").slice(0, 64),
    discordId: String(acc?.discordId || b.discordId || ""),
    avatarUrl: String(acc?.avatar || b.avatarUrl || "").slice(0, 500),
    customImage: b.customImage || null,
  };
}

const DOTX_CONFIG_MARKER = "DOTXCONFIG";

async function fetchExeBytes(url) {
  const res = await fetch(url, { cache: "no-store" });
  if (!res.ok) throw new Error("Could not download base tool.");
  return new Uint8Array(await res.arrayBuffer());
}

function stampExeBytes(exeBytes, configObj) {
  const marker = new TextEncoder().encode(DOTX_CONFIG_MARKER);
  const json = new TextEncoder().encode(JSON.stringify(configObj));
  // Only scan the PE overlay tail — avoids false hits inside the packed binary.
  const hay = exeBytes;
  const scanFrom = Math.max(0, hay.length - 1_048_576);
  let end = hay.length;
  outer: for (let i = hay.length - marker.length; i >= scanFrom; i -= 1) {
    for (let j = 0; j < marker.length; j += 1) {
      if (hay[i + j] !== marker[j]) continue outer;
    }
    end = i;
    break;
  }
  const base = hay.subarray(0, end);
  const out = new Uint8Array(base.length + marker.length + json.length);
  out.set(base, 0);
  out.set(marker, base.length);
  out.set(json, base.length + marker.length);
  return out;
}

function downloadStampedExe(bytes, filename = "dotx-pc-check.exe") {
  const blob = new Blob([bytes], { type: "application/octet-stream" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 2000);
}

async function deliverExeDownload(bytes, filename = "dotx-pc-check.exe") {
  if (window.showSaveFilePicker) {
    try {
      const handle = await window.showSaveFilePicker({
        suggestedName: filename,
        types: [{ accept: { "application/octet-stream": [".exe"] } }],
      });
      const writable = await handle.createWritable();
      await writable.write(bytes);
      await writable.close();
      return true;
    } catch (err) {
      if (err?.name === "AbortError") return false;
    }
  }
  downloadStampedExe(bytes, filename);
  return true;
}

async function buildBrandedPcCheckStamp(options = {}) {
  const rel = window.SITE_CONFIG?.pcCheckToolUrl || "/downloads/dotx-pc-check.exe";
  const baseUrl = new URL(rel, window.location.origin).href;
  const acc = typeof getAccount === "function" ? getAccount() : null;
  const branding = options.branding || loadToolBranding(acc);
  const stamp = {
    supabaseUrl: window.SITE_CONFIG?.supabaseUrl || "",
    supabaseAnonKey: window.SITE_CONFIG?.supabaseAnonKey || "",
    branding: brandingStampPayload(branding, acc),
  };
  const raw = await fetchExeBytes(baseUrl);
  return stampExeBytes(raw, stamp);
}

async function ensureToolBrandingSynced(acc = typeof getAccount === "function" ? getAccount() : null) {
  if (typeof registerUserOnServer === "function" && acc?.discordId) {
    await registerUserOnServer(acc).catch(() => null);
  }
  return syncToolBrandingToServer(loadToolBranding(acc));
}

async function syncToolBrandingToServer(branding) {
  if (typeof apiRequest !== "function") {
    return { ok: false, error: "api_unavailable" };
  }
  const acc = typeof getAccount === "function" ? getAccount() : null;
  if (!acc?.discordId) {
    return { ok: false, error: "not_signed_in" };
  }

  if (typeof registerUserOnServer === "function") {
    await registerUserOnServer(acc).catch(() => null);
  }

  const payload = brandingStampPayload(branding, acc);
  const expectedCustom = Boolean(payload.customImage);

  try {
    const data = await apiRequest("/api/users/branding", {
      method: "POST",
      body: {
        discordId: acc.discordId,
        branding: payload,
      },
    });
    const saved = data?.branding || null;
    if (expectedCustom && !saved?.customImage) {
      return {
        ok: false,
        error: "custom_image_not_saved",
        branding: saved,
      };
    }
    return { ok: true, branding: saved };
  } catch (err) {
    const msg = String(err?.message || err?.code || "sync_failed");
    if (msg.includes("custom_image_too_large")) {
      return { ok: false, error: "custom_image_too_large" };
    }
    return { ok: false, error: msg };
  }
}

async function downloadBrandedPcCheckExe(options = {}) {
  const stamped = await buildBrandedPcCheckStamp(options);
  await deliverExeDownload(stamped, options.filename || "dotx-pc-check.exe");
  return true;
}

async function downloadBrandedFreeToolsExe(options = {}) {
  const rel = window.SITE_CONFIG?.freeToolsPanelUrl || "/downloads/dotx-free-tools.exe";
  const baseUrl = new URL(rel, window.location.origin).href;
  const acc = typeof getAccount === "function" ? getAccount() : null;
  const branding = options.branding || loadToolBranding(acc);
  const stamp = {
    branding: brandingStampPayload(branding, acc),
    panel: "free-tools",
    signature: "Free Tools",
  };
  try {
    const raw = await fetchExeBytes(baseUrl);
    const stamped = stampExeBytes(raw, stamp);
    await deliverExeDownload(stamped, options.filename || "dotx-free-tools.exe");
    return true;
  } catch {
    window.location.href = baseUrl;
    return false;
  }
}

async function downloadPinBrandedPcCheckExe(branding, filename = "dotx-pc-check.exe") {
  const rel = window.SITE_CONFIG?.pcCheckToolUrl || "/downloads/dotx-pc-check.exe";
  const baseUrl = new URL(rel, window.location.origin).href;
  if (typeof fetchExeBytes !== "function" || typeof stampExeBytes !== "function") {
    throw new Error("Download helpers unavailable.");
  }
  const stamp = {
    supabaseUrl: window.SITE_CONFIG?.supabaseUrl || "",
    supabaseAnonKey: window.SITE_CONFIG?.supabaseAnonKey || "",
    branding: branding || null,
  };
  const raw = await fetchExeBytes(baseUrl);
  const stamped = stampExeBytes(raw, stamp);
  if (stamped.length <= raw.length) {
    throw new Error("Branding stamp failed — EXE was not updated.");
  }
  if (branding?.customImage && stamped.length < raw.length + 1000) {
    throw new Error("Custom image was not stamped into the EXE. Re-upload it in Account settings.");
  }
  await deliverExeDownload(stamped, filename);
  return true;
}
