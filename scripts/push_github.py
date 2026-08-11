"""Build encrypted site and deploy it to main/web (what GitHub Pages serves)."""
from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WEB_DIR = ROOT / "web"
SITE_DIR = ROOT / "_site"
DEPLOY_CONFIG = ROOT / "deploy.config.json"
CONFIG_JS = WEB_DIR / "js" / "config.js"
OBFUSCATE_SCRIPT = ROOT / "scripts" / "obfuscate_web.py"
DEFAULT_API_SUFFIX = "/functions/v1/dotx"
DEFAULT_SUPABASE_URL = "https://bumuisxrzbteeymzeidh.supabase.co"

WEB_PATHS = [
    "web",
    "supabase",
    ".github/workflows",
    "DEPLOY.md",
    "deploy.config.json.example",
    "scripts/push_github.py",
    "scripts/obfuscate_web.py",
    "scripts/html-bootstrap.js",
    "scripts/js-obfuscator.json",
    "build-web.bat",
    "push-github.bat",
    "scripts/push_all.py",
    "scripts/push_supabase.py",
    "scripts/migrate_store_to_supabase.py",
    "setup-supabase.bat",
    "setup-railway-bot.bat",
    "start_dotx.py",
    "discord_bot",
    "requirements.txt",
]


def _run(cmd: list[str], *, cwd: Path | None = None, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, cwd=cwd or ROOT, text=True, capture_output=True, check=check)


def _sync_api_url() -> None:
    if not DEPLOY_CONFIG.is_file() or not CONFIG_JS.is_file():
        return
    try:
        data = json.loads(DEPLOY_CONFIG.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return
    text = CONFIG_JS.read_text(encoding="utf-8")
    supabase_url = str(data.get("supabaseUrl", DEFAULT_SUPABASE_URL)).strip().rstrip("/")
    if supabase_url and "supabaseUrl:" in text:
        text, count = re.subn(
            r'(supabaseUrl:\s*")[^"]*(")',
            rf'\1{supabase_url}\2',
            text,
            count=1,
        )
        if count:
            print(f"Updated web/js/config.js supabaseUrl -> {supabase_url}")
    anon_key = str(data.get("supabaseAnonKey", "")).strip()
    if anon_key and not anon_key.startswith("YOUR_") and "supabaseAnonKey:" in text:
        text, count = re.subn(
            r'(supabaseAnonKey:\s*")[^"]*(")',
            rf'\1{anon_key}\2',
            text,
            count=1,
        )
        if count:
            print("Updated web/js/config.js supabaseAnonKey")
        text, count = re.subn(r'(apiBaseUrl:\s*")[^"]*(")', r'\1\2', text, count=1)
        if count:
            print("Cleared web/js/config.js apiBaseUrl (using Supabase direct)")
    site_token = str(data.get("siteApiToken", "")).strip()
    if site_token and not site_token.startswith("YOUR_"):
        text, count = re.subn(
            r'(apiToken:\s*")[^"]*(")',
            rf'\1{site_token}\2',
            text,
            count=1,
        )
        if count:
            print("Updated web/js/config.js apiToken")
    CONFIG_JS.write_text(text, encoding="utf-8")


def _git_available() -> bool:
    try:
        return _run(["git", "--version"], check=False).returncode == 0
    except OSError:
        return False


def _build_encrypted_site() -> int:
    if not OBFUSCATE_SCRIPT.is_file():
        print(f"[ERROR] Missing {OBFUSCATE_SCRIPT}")
        return 1
    print("Building encrypted production site...")
    build = subprocess.run(
        [sys.executable, str(OBFUSCATE_SCRIPT), "--site"],
        cwd=ROOT,
        check=False,
    )
    if build.returncode != 0:
        print("[FAILED] Could not build encrypted site. Install Node.js from https://nodejs.org/")
        return build.returncode
    if not SITE_DIR.is_dir() or not (SITE_DIR / "index.html").is_file():
        print(f"[ERROR] Build did not produce {SITE_DIR / 'index.html'}")
        return 1
    sample = (SITE_DIR / "index.html").read_text(encoding="utf-8")
    if 'class="header"' in sample or 'class="hero"' in sample or "dotx-payload" in sample:
        print("[ERROR] Built index.html is not fully obfuscated.")
        return 1
    if "<script" not in sample or "<!DOCTYPE html>" not in sample:
        print("[ERROR] Built index.html has unexpected format.")
        return 1
    print(f"[OK] Encrypted site ready in {SITE_DIR.relative_to(ROOT)}")
    return 0


def _backup_readable_web(backup_dir: Path) -> None:
    backup_dir.mkdir(parents=True, exist_ok=True)
    for html in WEB_DIR.rglob("*.html"):
        rel = html.relative_to(WEB_DIR)
        dest = backup_dir / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(html, dest)
    js_src = WEB_DIR / "js"
    if js_src.is_dir():
        shutil.copytree(
            js_src,
            backup_dir / "js",
            ignore=shutil.ignore_patterns("obf", "obf/*"),
            dirs_exist_ok=True,
        )


def _overlay_site_to_web(site_dir: Path) -> None:
    for html in site_dir.rglob("*.html"):
        rel = html.relative_to(site_dir)
        dest = WEB_DIR / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(html, dest)
    site_js = site_dir / "js"
    web_js = WEB_DIR / "js"
    if web_js.is_dir():
        shutil.rmtree(web_js)
    shutil.copytree(site_js, web_js)


def _restore_readable_web(backup_dir: Path) -> None:
    for html in backup_dir.rglob("*.html"):
        rel = html.relative_to(backup_dir)
        if rel.parts[:1] == ("js",):
            continue
        dest = WEB_DIR / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(html, dest)
    backup_js = backup_dir / "js"
    web_js = WEB_DIR / "js"
    if web_js.is_dir():
        shutil.rmtree(web_js)
    if backup_js.is_dir():
        shutil.copytree(backup_js, web_js)


def _commit_and_push_encrypted_web() -> int:
    for rel in WEB_PATHS:
        path = ROOT / rel
        if path.exists():
            _run(["git", "add", rel], check=False)

    staged = _run(["git", "diff", "--cached", "--name-only"], check=False)
    if not staged.stdout.strip():
        print("[WARN] No deploy changes detected after encryption overlay.")
        return 0

    print("Committing encrypted website for GitHub Pages:")
    for line in staged.stdout.strip().splitlines():
        print(f"  {line}")

    commit = _run(
        ["git", "commit", "-m", "Deploy encrypted dotx website (GitHub Pages)"],
        check=False,
    )
    if commit.returncode != 0:
        print(commit.stderr or commit.stdout)
        print("[FAILED] Could not commit encrypted deploy.")
        return commit.returncode

    print("Pushing encrypted site to GitHub (main/web)...")
    push = _run(["git", "push", "origin", "HEAD"], check=False)
    if push.stdout:
        print(push.stdout.rstrip())
    if push.returncode != 0:
        if push.stderr:
            print(push.stderr.rstrip())
        print("[FAILED] git push failed.")
        return push.returncode

    print("[OK] Encrypted site is live on main/web.")
    return 0


def main() -> int:
    print()
    print(" dotx Website - Encrypted GitHub Pages Deploy")
    print(" ============================================")
    print()

    if not _git_available():
        print("[ERROR] Git is not installed.")
        return 1

    if not (ROOT / ".git").is_dir():
        print("[ERROR] This folder is not a git repo yet.")
        return 1

    remote = _run(["git", "remote", "get-url", "origin"], check=False)
    if remote.returncode != 0:
        print("[ERROR] No git remote named 'origin'.")
        return 1

    _sync_api_url()

    if _build_encrypted_site() != 0:
        return 1

    with tempfile.TemporaryDirectory(prefix="dotx-web-src-") as tmp:
        backup_dir = Path(tmp)
        _backup_readable_web(backup_dir)
        _overlay_site_to_web(SITE_DIR)
        try:
            if _commit_and_push_encrypted_web() != 0:
                return 1
        finally:
            print("Restoring readable web/ sources for local editing...")
            _restore_readable_web(backup_dir)

    print()
    print("[OK] dotx.store will serve obfuscated HTML from main/web in ~1-2 minutes.")
    print("    Your local web/ folder stays readable for editing.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
