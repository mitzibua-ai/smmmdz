"""Sync config to Railway and deploy the bot."""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "discord_bot" / "config.json"
RAILWAY_PATHS = [
    "web/serve.py",
    "web/data_store.py",
    "web/data",
    "discord_bot",
    "start_dotx.py",
    "Procfile",
    "nixpacks.toml",
    "requirements.txt",
    "scripts/railway_sync_env.py",
]
SERVICE_NAME = "proactive-nourishment"
PROJECT_ID = "1913f1ed-7bb3-443a-a7ec-8d9fc5c88d4f"


def _extend_path() -> None:
    extra = [
        Path(os.environ.get("APPDATA", "")) / "npm",
        Path("C:/Program Files/nodejs"),
        Path(os.environ.get("LOCALAPPDATA", "")) / "Python" / "bin",
        Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "Python",
    ]
    for base in extra:
        if base.is_dir():
            os.environ["PATH"] = f"{base};{os.environ.get('PATH', '')}"


def _railway_cmd() -> str:
    if sys.platform == "win32":
        cmd = shutil.which("railway.cmd")
        if cmd:
            return cmd
    return shutil.which("railway") or "railway"


def _python_cmd() -> str:
    return shutil.which("python") or shutil.which("py") or sys.executable


def _run(cmd: list[str], *, input_text: str | None = None) -> int:
    result = subprocess.run(
        cmd,
        cwd=ROOT,
        input=input_text,
        text=True,
        capture_output=True,
        check=False,
    )
    if result.stdout:
        print(result.stdout.rstrip())
    if result.returncode != 0 and result.stderr:
        print(result.stderr.rstrip(), file=sys.stderr)
    return result.returncode


def _railway_json(args: list[str]) -> dict:
    railway = _railway_cmd()
    result = subprocess.run(
        [railway, *args, "--json"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0 or not result.stdout.strip():
        return {}
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError:
        return {}


def _ensure_linked() -> bool:
    railway = _railway_cmd()
    if not shutil.which("railway.cmd") and not shutil.which("railway"):
        print("[ERROR] Railway CLI not found.")
        print("Install: npm install -g @railway/cli")
        return False

    whoami = subprocess.run([railway, "whoami"], cwd=ROOT, capture_output=True, text=True)
    if whoami.returncode != 0:
        print("[ERROR] Not logged into Railway. Run: railway login")
        return False

    status = _railway_json(["status"])
    if not status.get("id"):
        print(f"Linking project {PROJECT_ID}...")
        code = _run([railway, "link", "-p", PROJECT_ID, "-s", SERVICE_NAME])
        if code != 0:
            print("[ERROR] Could not link Railway project.")
            return False
        return True

    services = status.get("services", {}).get("edges", [])
    linked = False
    for edge in services:
        node = edge.get("node") or {}
        if node.get("name") == SERVICE_NAME:
            linked = True
            break

    link_file = ROOT / ".railway" / "config.json"
    if not linked and not link_file.exists():
        print(f"Linking service {SERVICE_NAME}...")
        code = _run([railway, "service", "link", SERVICE_NAME])
        if code != 0:
            code = _run([railway, "link", "-p", PROJECT_ID, "-s", SERVICE_NAME])
            if code != 0:
                print("[WARN] Could not link service; deploy will use --service flag.")

    return True


def _sync_env() -> bool:
    sync_script = ROOT / "scripts" / "railway_sync_env.py"
    python = _python_cmd()
    print("Syncing config.json to Railway...")
    code = subprocess.call([python, str(sync_script)], cwd=ROOT)
    if code != 0:
        print("[FAILED] Could not sync settings to Railway.")
        return False
    return True


def _deploy() -> bool:
    railway = _railway_cmd()
    print()
    print("Uploading and deploying API + bot...")
    print()

    code = _run([railway, "up", "--detach", "-y", "--service", SERVICE_NAME])
    if code != 0:
        code = _run([railway, "up", "--detach", "-y"])
    if code != 0:
        print("[FAILED] Deploy did not start.")
        return False

    print()
    print("[OK] Deploy started on Railway.")
    print("    Dashboard: railway open")
    print("    Logs:      railway logs")
    return True


def main() -> int:
    _extend_path()

    print()
    print(" dotx API + Discord Bot - Railway Deploy")
    print(" =======================================")
    print()
    print(" Railway stores your data (pins, scans, users) and runs the bot.")
    print(" The public website is on GitHub Pages — use push-github.bat for that.")
    print()

    if not CONFIG_PATH.is_file():
        print(f"[ERROR] Missing {CONFIG_PATH}")
        return 1

    if not _ensure_linked():
        return 1
    if not _sync_env():
        return 1
    if not _deploy():
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
