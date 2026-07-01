"""First-time: link this project to your GitHub repo and push."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def run(cmd: list[str], *, check: bool = True) -> subprocess.CompletedProcess:
    print("+", " ".join(cmd))
    return subprocess.run(cmd, cwd=ROOT, text=True, check=check)


def main() -> int:
    print()
    print(" dotx - First GitHub Push")
    print(" ========================")
    print()

    if len(sys.argv) < 2:
        print("Usage:")
        print('  setup-github.bat "https://github.com/YOUR-USER/YOUR-REPO.git"')
        print()
        print("Copy the URL from GitHub:")
        print("  Your repo -> green Code button -> HTTPS -> copy")
        return 1

    repo_url = sys.argv[1].strip().strip('"')
    if not repo_url.startswith("https://github.com/") and not repo_url.startswith("git@github.com:"):
        print("[ERROR] That does not look like a GitHub repo URL.")
        print('  Example: https://github.com/MyName/fivem-pc-check.git')
        return 1

    if not (ROOT / ".git").is_dir():
        print("Creating git repo in project folder...")
        run(["git", "init"])
        run(["git", "branch", "-M", "main"])
    else:
        run(["git", "branch", "-M", "main"], check=False)

    remote = subprocess.run(
        ["git", "remote", "get-url", "origin"],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    if remote.returncode != 0:
        run(["git", "remote", "add", "origin", repo_url])
    else:
        current = remote.stdout.strip()
        if current != repo_url:
            print(f"Updating origin: {current} -> {repo_url}")
            run(["git", "remote", "set-url", "origin", repo_url])

    run(["git", "add", "."])
    status = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    if not status.stdout.strip():
        print("[OK] Everything already committed.")
    else:
        run(["git", "commit", "-m", "Initial dotx project (website + bot + API)"])

    print()
    print("Pushing to GitHub (you may be asked to log in)...")
    push = subprocess.run(
        ["git", "push", "-u", "origin", "main"],
        cwd=ROOT,
        text=True,
    )
    if push.returncode != 0:
        print()
        print("[FAILED] Push did not work.")
        print("  - Make sure the repo on GitHub is EMPTY (no README) when first pushing")
        print("  - Or use GitHub Desktop / sign in with: git config credential.helper manager")
        return push.returncode

    print()
    print("[OK] Code is on GitHub!")
    print()
    print("NEXT:")
    print("  1. GitHub repo -> Settings -> Pages -> Source: GitHub Actions")
    print("  2. Copy deploy.config.json.example -> deploy.config.json and fill URLs")
    print("  3. After changes, use push-github.bat or push-all.bat")
    return 0


if __name__ == "__main__":
    sys.exit(main())
