/**
 * Client-side deterrents for dotx panel pages.
 * Cannot fully stop DevTools or script copying — server auth + Supabase RLS are the real security.
 */
(function siteGuard() {
  "use strict";

  var cfg = window.SITE_GUARD || {};
  var level = String(cfg.level || "strict").toLowerCase();
  if (level === "off") return;

  var host = String(location.hostname || "").toLowerCase();
  if ((host === "localhost" || host === "127.0.0.1") && cfg.allowLocalhost !== false) {
    return;
  }

  var blockedKeys = {
    F12: 1,
    "123": 1,
  };

  function isBlockedShortcut(event) {
    var key = String(event.key || "");
    var code = String(event.keyCode || event.which || "");
    var ctrl = event.ctrlKey || event.metaKey;
    var shift = event.shiftKey;
    var alt = event.altKey;

    if (key === "F12" || code === "123") return true;
    if (ctrl && shift && /^(I|J|C|K)$/i.test(key)) return true;
    if (ctrl && /^(U|S|P)$/i.test(key)) return true;
    if (alt && key === "F4") return true;
    return false;
  }

  function blockEvent(event) {
    event.preventDefault();
    event.stopPropagation();
    event.stopImmediatePropagation();
    return false;
  }

  document.addEventListener(
    "contextmenu",
    function (event) {
      if (level === "light" && event.target && event.target.closest("input, textarea, [contenteditable='true']")) {
        return;
      }
      return blockEvent(event);
    },
    true
  );

  document.addEventListener(
    "keydown",
    function (event) {
      if (isBlockedShortcut(event)) return blockEvent(event);
    },
    true
  );

  document.addEventListener(
    "keyup",
    function (event) {
      if (blockedKeys[event.key] || blockedKeys[String(event.keyCode || "")]) return blockEvent(event);
    },
    true
  );

  if (level === "strict") {
    document.addEventListener(
      "copy",
      function (event) {
        if (event.target && event.target.closest("input, textarea, [data-allow-copy]")) return;
        return blockEvent(event);
      },
      true
    );

    document.addEventListener(
      "cut",
      function (event) {
        if (event.target && event.target.closest("input, textarea, [data-allow-copy]")) return;
        return blockEvent(event);
      },
      true
    );

    document.addEventListener(
      "dragstart",
      function (event) {
        if (event.target && event.target.closest("input, textarea, [data-allow-copy]")) return;
        return blockEvent(event);
      },
      true
    );

    document.documentElement.classList.add("site-protect");
  }

  function overlayMessage() {
    var existing = document.getElementById("site-guard-overlay");
    if (existing) return existing;
    var node = document.createElement("div");
    node.id = "site-guard-overlay";
    node.setAttribute("role", "alert");
    node.innerHTML =
      "<div class='site-guard-overlay__card'>" +
      "<strong>Protected area</strong>" +
      "<p>Close developer tools to continue using dotx.</p>" +
      "</div>";
    (document.body || document.documentElement).appendChild(node);
    return node;
  }

  function hideOverlay() {
    var node = document.getElementById("site-guard-overlay");
    if (node) node.remove();
  }

  var devtoolsOpen = false;
  var threshold = Number(cfg.devtoolsThreshold || 160);

  function probeDevtools() {
    var widthGap = Math.abs(window.outerWidth - window.innerWidth);
    var heightGap = Math.abs(window.outerHeight - window.innerHeight);
    var opened = widthGap > threshold || heightGap > threshold;

    if (opened && !devtoolsOpen) {
      devtoolsOpen = true;
      overlayMessage();
      document.documentElement.classList.add("site-protect--blocked");
    } else if (!opened && devtoolsOpen) {
      devtoolsOpen = false;
      hideOverlay();
      document.documentElement.classList.remove("site-protect--blocked");
    }
  }

  window.addEventListener("resize", probeDevtools);
  setInterval(probeDevtools, 800);

  if (cfg.lockConsole !== false && level === "strict") {
    var noop = function () {};
    var methods = ["log", "debug", "info", "warn", "error", "table", "trace", "dir", "clear"];
    for (var i = 0; i < methods.length; i += 1) {
      try {
        console[methods[i]] = noop;
      } catch (_err) {
        /* ignore */
      }
    }
  }

  if (cfg.antiDebug !== false && level === "strict") {
    setInterval(function () {
      var start = Date.now();
      debugger;
      if (Date.now() - start > 120) {
        devtoolsOpen = true;
        overlayMessage();
      }
    }, 3000);
  }
})();
