/** PC Check EXE branding — Account settings + download stamp helpers. */
const TOOL_BRANDING_KEY = "dotx_tool_branding_v1";
const MAX_BRAND_IMAGE_CHARS = 280_000;
const MAX_BRAND_EDGE = 720;

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

    // Keep GIFs as-is when small enough (animation preserved for web preview; EXE shows first frame)
    if (file.type === "image/gif" && file.size <= 220_000) {
      const reader = new FileReader();
      reader.onload = () => {
        const dataUrl = String(reader.result || "");
        if (dataUrl.length > MAX_BRAND_IMAGE_CHARS) {
          reject(new Error("GIF is too large after encoding. Try a smaller GIF."));
          return;
        }
        resolve({ dataUrl, name: file.name });
      };
      reader.onerror = () => reject(new Error("Could not read file."));
      reader.readAsDataURL(file);
      return;
    }

    const url = URL.createObjectURL(file);
    const img = new Image();
    img.onload = () => {
      try {
        const scale = Math.min(1, MAX_BRAND_EDGE / Math.max(img.width, img.height, 1));
        const w = Math.max(1, Math.round(img.width * scale));
        const h = Math.max(1, Math.round(img.height * scale));
        const canvas = document.createElement("canvas");
        canvas.width = w;
        canvas.height = h;
        const ctx = canvas.getContext("2d");
        ctx.clearRect(0, 0, w, h);
        ctx.drawImage(img, 0, 0, w, h);
        // PNG only — the EXE UI (tkinter) cannot load JPEG without Pillow.
        let dataUrl = canvas.toDataURL("image/png");
        if (dataUrl.length > MAX_BRAND_IMAGE_CHARS) {
          const w2 = Math.max(1, Math.round(w * 0.7));
          const h2 = Math.max(1, Math.round(h * 0.7));
          canvas.width = w2;
          canvas.height = h2;
          ctx.clearRect(0, 0, w2, h2);
          ctx.drawImage(img, 0, 0, w2, h2);
          dataUrl = canvas.toDataURL("image/png");
        }
        URL.revokeObjectURL(url);
        if (dataUrl.length > MAX_BRAND_IMAGE_CHARS) {
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
  // Strip previous stamp if present
  let end = exeBytes.length;
  const hay = exeBytes;
  for (let i = hay.length - marker.length; i >= 0; i -= 1) {
    let ok = true;
    for (let j = 0; j < marker.length; j += 1) {
      if (hay[i + j] !== marker[j]) {
        ok = false;
        break;
      }
    }
    if (ok) {
      end = i;
      break;
    }
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

async function downloadBrandedPcCheckExe(options = {}) {
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
  const stamped = stampExeBytes(raw, stamp);
  downloadStampedExe(stamped, options.filename || "dotx-pc-check.exe");
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
    downloadStampedExe(stamped, options.filename || "dotx-free-tools.exe");
    return true;
  } catch {
    window.location.href = baseUrl;
    return false;
  }
}

async function syncToolBrandingToServer(branding) {
  if (typeof apiRequest !== "function") return null;
  const acc = typeof getAccount === "function" ? getAccount() : null;
  if (!acc?.discordId) return null;
  const payload = brandingStampPayload(branding, acc);
  try {
    return await apiRequest("/api/users/branding", {
      method: "POST",
      body: {
        discordId: acc.discordId,
        branding: payload,
      },
    });
  } catch {
    return null;
  }
}
