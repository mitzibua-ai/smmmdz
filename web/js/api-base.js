/** API base URL — Railway stores data; GitHub Pages hosts the site. */
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
