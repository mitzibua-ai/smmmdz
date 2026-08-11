#!/usr/bin/env python3
"""Obfuscate web/js/*.js and encrypt HTML for production (GitHub Pages). Source stays readable in repo."""

from __future__ import annotations

import base64
import re
import secrets
import shutil
import subprocess
import sys
import platform
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WEB_SRC = ROOT / "web-src" if (ROOT / "web-src").is_dir() else ROOT / "web"
JS_DIR = WEB_SRC / "js"
OUT_DIR = JS_DIR / "obf"
OBF_CONFIG = ROOT / "scripts" / "js-obfuscator.json"
HTML_OBF_CONFIG = ROOT / "scripts" / "js-obfuscator-html.json"
BOOTSTRAP_TEMPLATE = ROOT / "scripts" / "html-bootstrap.js"
HTML_DIR = WEB_SRC
IS_WINDOWS = platform.system() == "Windows"


def _run(cmd: list[str]) -> None:
    printable = " ".join(cmd)
    print(">", printable)
    subprocess.run(
        cmd,
        cwd=ROOT,
        check=True,
        shell=IS_WINDOWS,
    )


def _node_available() -> bool:
    for cmd in (["node", "--version"], ["npx", "--version"]):
        try:
            subprocess.run(
                cmd,
                capture_output=True,
                check=True,
                shell=IS_WINDOWS,
            )
            return True
        except (OSError, subprocess.CalledProcessError):
            continue
    return False


def _xor_encrypt(plaintext: str) -> tuple[str, str]:
    key = secrets.token_bytes(32)
    data = plaintext.encode("utf-8")
    xored = bytes(b ^ key[i % len(key)] for i, b in enumerate(data))
    return base64.b64encode(xored).decode("ascii"), base64.b64encode(key).decode("ascii")


def _python_obfuscate_text(source: str) -> str:
    payload, key = _xor_encrypt(source)
    return (
        "(function(){"
        f'var k=atob("{key}"),d=atob("{payload}"),o=new Uint8Array(d.length);'
        "for(var i=0;i<d.length;i++)o[i]=d.charCodeAt(i)^k.charCodeAt(i%k.length);"
        "try{eval(new TextDecoder('utf-8').decode(o));}catch(e){}"
        "})();"
    )


def _python_obfuscate(src: Path, dest: Path) -> None:
    """Fallback when Node is unavailable — weaker than javascript-obfuscator."""
    dest.write_text(_python_obfuscate_text(src.read_text(encoding="utf-8")), encoding="utf-8")


def obfuscate_js() -> int:
    if not JS_DIR.is_dir():
        print(f"[ERROR] Missing {JS_DIR}")
        return 1
    if not OBF_CONFIG.is_file():
        print(f"[ERROR] Missing {OBF_CONFIG}")
        return 1
    if not _node_available():
        print("[WARN] Node.js/npx not found — using Python fallback obfuscation.")
        print("       Install Node.js for maximum protection: https://nodejs.org/")

    sources = sorted(p for p in JS_DIR.glob("*.js") if p.is_file())
    if not sources:
        print("[ERROR] No .js files found in web/js/")
        return 1

    if OUT_DIR.exists():
        shutil.rmtree(OUT_DIR)
    OUT_DIR.mkdir(parents=True)

    for src in sources:
        dest = OUT_DIR / src.name
        if _node_available():
            _run(
                [
                    "npx",
                    "--yes",
                    "javascript-obfuscator",
                    str(src),
                    "--output",
                    str(dest),
                    "--config",
                    str(OBF_CONFIG),
                ]
            )
        else:
            print(f"[WARN] Node/npx missing — using Python fallback for {src.name}")
            _python_obfuscate(src, dest)

    print(f"[OK] Obfuscated {len(sources)} files -> {OUT_DIR.relative_to(ROOT)}")
    return 0


def minify_html_text(text: str) -> str:
    """Strip HTML comments and collapse extra whitespace for production."""
    text = re.sub(r"<!--(?!.*\[if).*?-->", "", text, flags=re.DOTALL)
    text = re.sub(r">\s+<", "><", text)
    return text.strip()


_BOOTSTRAP_PLACEHOLDER_PAYLOAD = "__PAYLOAD__"
_BOOTSTRAP_PLACEHOLDER_KEY = "__KEY__"

_SHELL_SKIP_HEAD = re.compile(
    r"<script[^>]*src=[\"'][^\"']*site-guard\.js[\"'][^>]*>\s*</script>",
    re.IGNORECASE,
)
_SHELL_SKIP_SITE_GUARD_INLINE = re.compile(
    r"<script[^>]*>\s*window\.SITE_GUARD\s*=.*?</script>",
    re.IGNORECASE | re.DOTALL,
)
_SHELL_SKIP_META = re.compile(
    r"<meta[^>]+(?:charset|name=[\"']viewport[\"']|http-equiv=[\"'](?:X-Content-Type-Options|Referrer-Policy)[\"'])[^>]*>",
    re.IGNORECASE,
)


def _extract_encryptable_html(text: str) -> tuple[str, str]:
    text = minify_html_text(text)
    lang_match = re.search(r"<html[^>]*\blang=[\"']([^\"']+)[\"']", text, re.IGNORECASE)
    lang = lang_match.group(1) if lang_match else "en"

    head_match = re.search(r"<head[^>]*>(.*?)</head>", text, re.IGNORECASE | re.DOTALL)
    body_match = re.search(r"<body[^>]*>(.*?)</body>", text, re.IGNORECASE | re.DOTALL)
    head_inner = head_match.group(1) if head_match else ""
    body_inner = body_match.group(1) if body_match else ""

    head_inner = _SHELL_SKIP_HEAD.sub("", head_inner)
    head_inner = _SHELL_SKIP_SITE_GUARD_INLINE.sub("", head_inner)
    head_inner = _SHELL_SKIP_META.sub("", head_inner)

    fragment = f"<head>{head_inner.strip()}</head><body>{body_inner.strip()}</body>"
    return lang, fragment


def _build_bootstrap(payload: str, key: str) -> str:
    if not BOOTSTRAP_TEMPLATE.is_file():
        raise FileNotFoundError(f"Missing bootstrap template: {BOOTSTRAP_TEMPLATE}")
    template = BOOTSTRAP_TEMPLATE.read_text(encoding="utf-8")
    return (
        template.replace(_BOOTSTRAP_PLACEHOLDER_PAYLOAD, payload)
        .replace(_BOOTSTRAP_PLACEHOLDER_KEY, key)
    )


def _obfuscate_js_text(source: str) -> str:
    if not _node_available():
        print("[WARN] Node.js/npx not found — using Python fallback for HTML bootstrap.")
        return _python_obfuscate_text(source)

    with tempfile.TemporaryDirectory(prefix="dotx-html-") as tmp:
        src = Path(tmp) / "bootstrap.js"
        dest = Path(tmp) / "bootstrap.obf.js"
        src.write_text(source, encoding="utf-8")
        subprocess.run(
            [
                "npx",
                "--yes",
                "javascript-obfuscator",
                str(src),
                "--output",
                str(dest),
                "--config",
                str(HTML_OBF_CONFIG if HTML_OBF_CONFIG.is_file() else OBF_CONFIG),
            ],
            cwd=ROOT,
            check=True,
            shell=IS_WINDOWS,
        )
        return dest.read_text(encoding="utf-8").strip()


def _obfuscated_html_shell(obfuscated_js: str) -> str:
    return (
        "<!DOCTYPE html>\n"
        "<html><head><meta charset=\"UTF-8\" />"
        f"<script>{obfuscated_js}</script>"
        "</head></html>\n"
    )


def encrypt_html_files(out_dir: Path) -> None:
    count = 0
    for path in sorted(out_dir.rglob("*.html")):
        original = path.read_text(encoding="utf-8")
        _lang, fragment = _extract_encryptable_html(original)
        payload, key = _xor_encrypt(fragment)
        bootstrap = _build_bootstrap(payload, key)
        obfuscated = _obfuscate_js_text(bootstrap)
        path.write_text(_obfuscated_html_shell(obfuscated), encoding="utf-8")
        count += 1
        print(f"  [OK] Obfuscated HTML -> {path.relative_to(out_dir)}")
    print(f"[OK] Obfuscated {count} HTML files in {out_dir.relative_to(ROOT)}")


def build_production_site(out_dir: Path) -> int:
    if obfuscate_js() != 0:
        return 1

    if out_dir.exists():
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True)

    for name in ("index.html", "404.html", "login.html", "callback.html", "dashboard.html"):
        src = HTML_DIR / name
        if src.is_file():
            shutil.copy2(src, out_dir / name)

    for folder in ("css", "static", "login", "callback", "dashboard", "downloads"):
        src = HTML_DIR / folder
        if src.is_dir():
            shutil.copytree(src, out_dir / folder)

    shutil.copytree(OUT_DIR, out_dir / "js")
    if (HTML_DIR / "_headers").is_file():
        shutil.copy2(HTML_DIR / "_headers", out_dir / "_headers")
    if (HTML_DIR / ".nojekyll").is_file():
        shutil.copy2(HTML_DIR / ".nojekyll", out_dir / ".nojekyll")
    else:
        (out_dir / ".nojekyll").write_text("", encoding="utf-8")

    cname = HTML_DIR / "CNAME"
    if cname.is_file():
        shutil.copy2(cname, out_dir / "CNAME")
    else:
        (out_dir / "CNAME").write_text("dotx.store\n", encoding="utf-8")

    downloads = out_dir / "downloads"
    downloads.mkdir(parents=True, exist_ok=True)
    for candidate in (
        HTML_DIR / "downloads" / "dotx-pc-check.exe",
        HTML_DIR / "downloads" / "dotx-pc-check" / "dotx-pc-check.exe",
        HTML_DIR / "downloads" / "dotx-pc-check" / "dotx.exe",
    ):
        if candidate.is_file():
            shutil.copy2(candidate, downloads / "dotx-pc-check.exe")
            break
    nested = downloads / "dotx-pc-check"
    if nested.is_dir():
        shutil.rmtree(nested)

    encrypt_html_files(out_dir)
    print(f"[OK] Production site ready at {out_dir.relative_to(ROOT)}")
    return 0


def main() -> int:
    if len(sys.argv) > 1 and sys.argv[1] == "--site":
        out = ROOT / "_site"
        return build_production_site(out)
    return obfuscate_js()


if __name__ == "__main__":
    raise SystemExit(main())
