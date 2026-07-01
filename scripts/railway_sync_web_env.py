"""Push web/.env values to Railway (dotx website service)."""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

WEB = Path(__file__).resolve().parents[1] / "web"
ENV_PATH = WEB / ".env"
SERVICE_NAME = "dotx-web"


def _extend_path() -> None:
    extra = [
        Path(os.environ.get("APPDATA", "")) / "npm",
        Path("C:/Program Files/nodejs"),
        Path(os.environ.get("LOCALAPPDATA", "")) / "Python" / "bin",
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


def _parse_env(path: Path) -> dict[str, str]:
    if not path.is_file():
        return {}
    values: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def _linked_service_id() -> str:
    railway = _railway_cmd()
    result = subprocess.run(
        [railway, "status", "--json"],
        cwd=WEB,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0 or not result.stdout.strip():
        return ""
    import json

    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError:
        return ""
    service = data.get("service") or {}
    service_id = str(service.get("id", "")).strip()
    if service_id:
        return service_id
    for edge in data.get("services", {}).get("edges", []):
        node = edge.get("node") or {}
        if node.get("name") == SERVICE_NAME:
            return str(node.get("id", "")).strip()
    return ""


def _set_variable(service_id: str, key: str, value: str) -> int:
    railway = _railway_cmd()
    base_cmd = [railway, "variable", "set", key, "--stdin", "--skip-deploys"]
    if service_id:
        base_cmd.extend(["--service", service_id])
    result = subprocess.run(
        base_cmd,
        cwd=WEB,
        input=value,
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        err = (result.stderr or result.stdout or "").strip()
        if err:
            print(err)
    return result.returncode


def main() -> int:
    _extend_path()
    env = _parse_env(ENV_PATH)

    bot_config = Path(__file__).resolve().parents[1] / "discord_bot" / "config.json"
    if bot_config.is_file():
        import json

        try:
            raw = json.loads(bot_config.read_text(encoding="utf-8"))
            env.setdefault("DISCORD_BOT_TOKEN", str(raw.get("token", "")).strip())
            env.setdefault("DISCORD_GUILD_ID", str(raw.get("guild_id", "")))
        except json.JSONDecodeError:
            pass

    pairs = {
        "DISCORD_CLIENT_ID": env.get("DISCORD_CLIENT_ID", "1519618635054841867"),
        "DISCORD_BOT_TOKEN": env.get("DISCORD_BOT_TOKEN", ""),
        "DISCORD_GUILD_ID": env.get("DISCORD_GUILD_ID", ""),
        "DISCORD_CUSTOMER_ROLE_ID": env.get("DISCORD_CUSTOMER_ROLE_ID", ""),
        "HOST": "0.0.0.0",
        "DATA_DIR": "/data",
        "DATA_PATH": "/data/store.json",
    }

    optional = {"OWNER_DISCORD_IDS", "DISCORD_OWNER_ROLE_IDS", "PUBLIC_URL"}
    for key in optional:
        if env.get(key):
            pairs[key] = env[key]

    missing = [k for k, v in pairs.items() if k in {"DISCORD_BOT_TOKEN", "DISCORD_GUILD_ID"} and not v]
    if missing:
        print(f"Missing in web/.env: {', '.join(missing)}")
        print("Copy web/.env.example to web/.env and fill in values.")
        return 1

    service = _linked_service_id()
    for key, value in pairs.items():
        if not value and key not in {"PUBLIC_URL"}:
            continue
        print(f"Setting {key}...")
        if _set_variable(service, key, value) != 0:
            print(f"Failed to set {key}.")
            return 1

    print("Railway web variables updated.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
