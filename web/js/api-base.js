/** API base URL — Supabase Edge Function; GitHub Pages hosts the site. */
function apiBaseUrl() {
  const configured = window.SITE_CONFIG?.apiBaseUrl;
  if (configured && String(configured).trim()) {
    return String(configured).trim().replace(/\/$/, "");
  }
  if (window.location.protocol === "http:" || window.location.protocol === "https:") {
    return window.location.origin;
  }
  return "";
}

function isExternalApiConfigured() {
  if (typeof useSupabaseDirect === "function" && useSupabaseDirect()) {
    return true;
  }
  const configured = window.SITE_CONFIG?.apiBaseUrl;
  return !!(configured && String(configured).trim());
}

function siteApiToken() {
  const token = window.SITE_CONFIG?.apiToken;
  if (!token || String(token).startsWith("YOUR_")) return "";
  return String(token).trim();
}

function apiUrl(path) {
  const base = apiBaseUrl();
  const p = path.startsWith("/") ? path : `/${path}`;
  return base ? `${base}${p}` : p;
}

function apiUrlWithToken(path) {
  const url = apiUrl(path);
  const token = siteApiToken();
  if (!token) return url;
  const sep = url.includes("?") ? "&" : "?";
  return `${url}${sep}siteToken=${encodeURIComponent(token)}`;
}

/** Simple GET — routes through Supabase when configured. */
async function apiGet(path) {
  if (typeof useSupabaseDirect === "function" && useSupabaseDirect()) {
    return supabaseApiRequest(path, { method: "GET" });
  }
  const res = await fetch(apiUrlWithToken(path), {
    method: "GET",
    mode: "cors",
    cache: "no-store",
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    const err = new Error(data.error || data.message || `Request failed (${res.status})`);
    err.code = data.error || null;
    err.status = res.status;
    throw err;
  }
  return data;
}

/** Returns true when Supabase API responds. */
async function checkApiOnline() {
  if (typeof useSupabaseDirect === "function" && useSupabaseDirect()) {
    try {
      const data = await supabaseRpc("api_health");
      return data?.ok === true;
    } catch {
      return false;
    }
  }
  if (!isExternalApiConfigured()) return false;
  try {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), 8000);
    const res = await fetch(apiUrlWithToken("/api/health"), {
      method: "GET",
      mode: "cors",
      cache: "no-store",
      signal: controller.signal,
    });
    clearTimeout(timer);
    if (!res.ok) return false;
    const data = await res.json().catch(() => ({}));
    return data.ok === true;
  } catch {
    return false;
  }
}
