/**
 * Production-only: decrypt and mount page HTML from build-time payload.
 * Source pages stay readable in the repo; _site/ ships encrypted shells.
 */
(function dotxHtmlLoader() {
  "use strict";

  var node = document.getElementById("dotx-payload");
  if (!node || !node.textContent) return;

  var packet;
  try {
    packet = JSON.parse(node.textContent);
  } catch (_err) {
    return;
  }

  if (!packet || !packet.d || !packet.k) return;

  function decodeBase64(value) {
    var binary = atob(value);
    var out = new Uint8Array(binary.length);
    for (var i = 0; i < binary.length; i += 1) {
      out[i] = binary.charCodeAt(i);
    }
    return out;
  }

  function decrypt(dataB64, keyB64) {
    var key = decodeBase64(keyB64);
    var raw = decodeBase64(dataB64);
    var out = new Uint8Array(raw.length);
    for (var i = 0; i < raw.length; i += 1) {
      out[i] = raw[i] ^ key[i % key.length];
    }
    return new TextDecoder("utf-8").decode(out);
  }

  function cloneScript(old) {
    var script = document.createElement("script");
    for (var i = 0; i < old.attributes.length; i += 1) {
      var attr = old.attributes[i];
      script.setAttribute(attr.name, attr.value);
    }
    if (old.src) {
      script.src = old.src;
    } else {
      script.text = old.text || old.textContent || "";
    }
    return script;
  }

  function mount(html) {
    var doc = new DOMParser().parseFromString(
      "<!doctype html><html>" + html + "</html>",
      "text/html"
    );

    if (doc.title) {
      document.title = doc.title;
    }

    var lang = doc.documentElement.getAttribute("lang");
    if (lang) {
      document.documentElement.setAttribute("lang", lang);
    }

    var headNodes = doc.head ? doc.head.childNodes : [];
    for (var h = 0; h < headNodes.length; h += 1) {
      var headNode = headNodes[h];
      if (headNode.nodeType !== 1) continue;
      var tag = headNode.tagName.toLowerCase();
      if (tag === "script") continue;
      if (tag === "meta") {
        var httpEquiv = (headNode.getAttribute("http-equiv") || "").toLowerCase();
        var name = (headNode.getAttribute("name") || "").toLowerCase();
        if (headNode.hasAttribute("charset") || name === "viewport") continue;
        if (httpEquiv === "x-content-type-options" || httpEquiv === "referrer-policy") continue;
      }
      document.head.appendChild(document.importNode(headNode, true));
    }

    document.body.innerHTML = doc.body ? doc.body.innerHTML : "";

    var scripts = document.body.querySelectorAll("script");
    for (var s = 0; s < scripts.length; s += 1) {
      var oldScript = scripts[s];
      oldScript.parentNode.replaceChild(cloneScript(oldScript), oldScript);
    }
  }

  try {
    mount(decrypt(packet.d, packet.k));
  } catch (_err) {
    /* ignore */
  }
})();
