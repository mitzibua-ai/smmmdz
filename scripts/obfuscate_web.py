#!/usr/bin/env python3
"""Obfuscate web/js/*.js and encrypt HTML for production (GitHub Pages). Source stays readable in repo."""

from __future__ import annotations

import base64
import secrets
import shutil
import subprocess
import sys
import platform
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WEB_SRC = ROOT / "web-src" if (ROOT / "web-src").is_dir() else ROOT / "web"
JS_DIR = WEB_SRC / "js"
OUT_DIR = JS_DIR / "obf"
OBF_CONFIG = ROOT / "scripts" / "js-obfuscator.json"
HTML_DIR = WEB_SRC
IS_WINDOWS = platform.system() == "Windows"

sys.path.insert(0, str(ROOT / "scripts"))
from phpkobo_html import build_phpkobo_page, prepare_full_html


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


def encrypt_html_files(out_dir: Path) -> None:
    count = 0
    for path in sorted(out_dir.rglob("*.html")):
        original = path.read_text(encoding="utf-8")
        full_html = prepare_full_html(original)
        path.write_text(
            build_phpkobo_page(full_html, remove_scripts=True, remove_comments=True),
            encoding="utf-8",
        )
        count += 1
        print(f"  [OK] PHPKobo HTML -> {path.relative_to(out_dir)}")
    print(f"[OK] PHPKobo obfuscated {count} HTML files in {out_dir.relative_to(ROOT)}")


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
