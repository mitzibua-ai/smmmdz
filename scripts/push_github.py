"""Commit and push website files to GitHub (triggers GitHub Pages deploy)."""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEPLOY_CONFIG = ROOT / "deploy.config.json"
CONFIG_JS = ROOT / "web" / "js" / "config.js"

WEB_PATHS = [
    "web",
    ".github/workflows",
    "DEPLOY.md",
    "deploy.config.json.example",
    "scripts/push_github.py",
    "scripts/push_all.py",
    "scripts/push_railway.py",
    "scripts/railway_sync_env.py",
]


def _run(cmd: list[str], *, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, cwd=ROOT, text=True, capture_output=True, check=check)


def _sync_api_url() -> None:
    if not DEPLOY_CONFIG.is_file() or not CONFIG_JS.is_file():
        return
    try:
        data = json.loads(DEPLOY_CONFIG.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return
    text = CONFIG_JS.read_text(encoding="utf-8")
    api_url = str(data.get("railwayApiUrl", "")).strip().rstrip("/")
    if api_url and "YOUR-RAILWAY" not in api_url:
        text, count = re.subn(
            r'(apiBaseUrl:\s*")[^"]*(")',
            rf'\1{api_url}\2',
            text,
            count=1,
        )
        if count:
            print(f"Updated web/js/config.js apiBaseUrl -> {api_url}")
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
        elif 'apiToken:' not in text:
            text = text.replace(
                'apiBaseUrl:',
                f'apiToken: "{site_token}",\n\n  apiBaseUrl:',
                1,
            )
            print("Added web/js/config.js apiToken")
    CONFIG_JS.write_text(text, encoding="utf-8")


def _git_available() -> bool:
    try:
        return _run(["git", "--version"], check=False).returncode == 0
    except OSError:
        return False


def main() -> int:
    print()
    print(" dotx Website - GitHub Push")
    print(" ==========================")
    print()

    if not _git_available():
        print("[ERROR] Git is not installed.")
        return 1

    if not (ROOT / ".git").is_dir():
        print("[ERROR] This folder is not a git repo yet.")
        print("  1. Create a repo on github.com")
        print("  2. Run: git init")
        print("  3. Run: git remote add origin https://github.com/YOU/REPO.git")
        print("  4. Run: git branch -M main")
        return 1

    _sync_api_url()

    remote = _run(["git", "remote", "get-url", "origin"], check=False)
    if remote.returncode != 0:
        print("[ERROR] No git remote named 'origin'.")
        print("  git remote add origin https://github.com/YOU/REPO.git")
        return 1

    for rel in WEB_PATHS:
        path = ROOT / rel
        if path.exists():
            _run(["git", "add", rel], check=False)

    staged = _run(["git", "diff", "--cached", "--name-only"], check=False)
    if not staged.stdout.strip():
        print("[OK] Nothing new to push (website already up to date).")
        return 0

    print("Committing:")
    for line in staged.stdout.strip().splitlines():
        print(f"  {line}")

    commit = _run(
        ["git", "commit", "-m", "Update dotx website (GitHub Pages)"],
        check=False,
    )
    if commit.returncode != 0:
        print(commit.stderr or commit.stdout)
        print("[FAILED] Could not commit.")
        return commit.returncode

    print("Pushing to GitHub...")
    push = _run(["git", "push", "origin", "HEAD"], check=False)
    if push.stdout:
        print(push.stdout.rstrip())
    if push.returncode != 0:
        if push.stderr:
            print(push.stderr.rstrip())
        print("[FAILED] git push failed.")
        return push.returncode

    print()
    print("[OK] Pushed to GitHub.")
    print("    GitHub Actions will deploy the site from the web/ folder.")
    print("    Repo -> Settings -> Pages -> Source: GitHub Actions")
    return 0


if __name__ == "__main__":
    sys.exit(main())
