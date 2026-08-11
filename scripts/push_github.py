"""Commit source to main, build encrypted site, deploy gh-pages for dotx.store."""
from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SITE_DIR = ROOT / "_site"
DEPLOY_CONFIG = ROOT / "deploy.config.json"
CONFIG_JS = ROOT / "web" / "js" / "config.js"
OBFUSCATE_SCRIPT = ROOT / "scripts" / "obfuscate_web.py"
DEFAULT_API_SUFFIX = "/functions/v1/dotx"
DEFAULT_SUPABASE_URL = "https://bumuisxrzbteeymzeidh.supabase.co"
PAGES_BRANCH = "gh-pages"

WEB_PATHS = [
    "web",
    "supabase",
    ".github/workflows",
    "DEPLOY.md",
    "deploy.config.json.example",
    "scripts/push_github.py",
    "scripts/obfuscate_web.py",
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


def _api_base_url(data: dict) -> str:
    supabase = str(data.get("supabaseUrl", DEFAULT_SUPABASE_URL)).strip().rstrip("/")
    return f"{supabase or DEFAULT_SUPABASE_URL}{DEFAULT_API_SUFFIX}"


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


def _deploy_gh_pages(site_dir: Path, remote_url: str) -> int:
    print(f"Deploying encrypted site to origin/{PAGES_BRANCH}...")
    with tempfile.TemporaryDirectory(prefix="dotx-pages-") as tmp:
        tmp_path = Path(tmp)
        shutil.copytree(site_dir, tmp_path, dirs_exist_ok=True)

        steps: list[tuple[list[str], str]] = [
            (["git", "init"], "init"),
            (["git", "checkout", "-B", PAGES_BRANCH], "checkout"),
            (["git", "add", "-A"], "add"),
            (["git", "commit", "-m", "Deploy encrypted dotx site"], "commit"),
            (["git", "remote", "add", "origin", remote_url], "remote"),
            (["git", "push", "-f", "origin", PAGES_BRANCH], "push"),
        ]

        for cmd, label in steps:
            result = _run(cmd, cwd=tmp_path, check=False)
            if result.returncode != 0 and label == "commit":
                print("[WARN] No page changes since last deploy.")
                return 0
            if result.returncode != 0:
                if result.stdout:
                    print(result.stdout.rstrip())
                if result.stderr:
                    print(result.stderr.rstrip())
                print(f"[FAILED] gh-pages deploy step failed: {label}")
                return result.returncode

    print(f"[OK] Pushed encrypted site to origin/{PAGES_BRANCH}")
    return 0


def _push_main() -> int:
    for rel in WEB_PATHS:
        path = ROOT / rel
        if path.exists():
            _run(["git", "add", rel], check=False)

    staged = _run(["git", "diff", "--cached", "--name-only"], check=False)
    if staged.stdout.strip():
        print("Committing source changes:")
        for line in staged.stdout.strip().splitlines():
            print(f"  {line}")
        commit = _run(
            ["git", "commit", "-m", "Update dotx website source and encryption build"],
            check=False,
        )
        if commit.returncode != 0:
            print(commit.stderr or commit.stdout)
            print("[FAILED] Could not commit.")
            return commit.returncode
    else:
        print("[OK] Source on main is already committed.")

    ahead = _run(["git", "rev-list", "--count", "origin/main..HEAD"], check=False)
    if ahead.returncode != 0:
        ahead = _run(["git", "rev-list", "--count", "@{u}..HEAD"], check=False)
    if ahead.returncode == 0 and ahead.stdout.strip() not in {"", "0"}:
        print("Pushing main to GitHub...")
        push = _run(["git", "push", "origin", "HEAD"], check=False)
        if push.stdout:
            print(push.stdout.rstrip())
        if push.returncode != 0:
            if push.stderr:
                print(push.stderr.rstrip())
            print("[FAILED] git push failed.")
            return push.returncode
        print("[OK] Pushed main.")
    else:
        print("[OK] Main branch is up to date on GitHub.")

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

    _sync_api_url()

    remote = _run(["git", "remote", "get-url", "origin"], check=False)
    if remote.returncode != 0:
        print("[ERROR] No git remote named 'origin'.")
        return 1
    remote_url = remote.stdout.strip()

    if _push_main() != 0:
        return 1

    if _build_encrypted_site() != 0:
        return 1

    if _deploy_gh_pages(SITE_DIR, remote_url) != 0:
        return 1

    print()
    print("[OK] Encrypted site deployed.")
    print("    GitHub repo -> Settings -> Pages -> Source:")
    print(f"      Branch: {PAGES_BRANCH}   Folder: / (root)")
    print("    If dotx.store still shows plain HTML, switch Pages to gh-pages and wait ~2 min.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
