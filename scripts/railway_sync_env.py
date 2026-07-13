"""Push discord_bot/config.json values to Railway environment variables."""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "discord_bot" / "config.json"
DEPLOY_CONFIG_PATH = ROOT / "deploy.config.json"


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


def _linked_service_id() -> str:
    try:
        result = subprocess.run(
            [_railway_cmd(), "status", "--json"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0 or not result.stdout.strip():
            return ""
        data = json.loads(result.stdout)
        service = data.get("service") or {}
        service_id = str(service.get("id", "")).strip()
        if service_id:
            return service_id

        for edge in data.get("services", {}).get("edges", []):
            node = edge.get("node") or {}
            if node.get("name") == "proactive-nourishment":
                return str(node.get("id", "")).strip()
        return ""
    except (json.JSONDecodeError, OSError):
        return ""


def _set_variable(service_id: str, key: str, value: str) -> int:
    railway = _railway_cmd()
    base_cmd = [railway, "variable", "set", key, "--stdin", "--skip-deploys"]
    if service_id:
        base_cmd.extend(["--service", service_id])

    result = subprocess.run(
        base_cmd,
        cwd=ROOT,
        input=value,
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        stderr = (result.stderr or result.stdout or "").strip()
        if stderr:
            print(stderr)
    return result.returncode


def _origin_from_url(raw: str) -> str:
    value = str(raw or "").strip().rstrip("/")
    if not value:
        return ""
    parsed = urlparse(value if "://" in value else f"https://{value}")
    if parsed.scheme and parsed.netloc:
        return f"{parsed.scheme}://{parsed.netloc}"
    return value


def _site_cors_origins() -> str:
    origins: list[str] = []
    if DEPLOY_CONFIG_PATH.is_file():
        try:
            data = json.loads(DEPLOY_CONFIG_PATH.read_text(encoding="utf-8"))
            for key in ("githubPagesUrl", "customSiteUrl", "siteUrl"):
                origin = _origin_from_url(str(data.get(key, "")).strip())
                if origin and origin not in origins:
                    origins.append(origin)
                if origin.startswith("https://") and not origin.startswith("https://www."):
                    www = origin.replace("https://", "https://www.", 1)
                    if www not in origins:
                        origins.append(www)
        except (json.JSONDecodeError, OSError):
            pass

    # Always allow dotx.store even if deploy.config.json is missing.
    for fallback in (
        "https://dotx.store",
        "https://www.dotx.store",
        "https://mitzibua-ai.github.io",
        "https://www.mitzibua-ai.github.io",
    ):
        if fallback not in origins:
            origins.append(fallback)

    return ",".join(origins)


def _github_cors_origin() -> str:
    return _site_cors_origins()


def _deploy_site_token() -> str:
    if not DEPLOY_CONFIG_PATH.is_file():
        return ""
    try:
        data = json.loads(DEPLOY_CONFIG_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return ""
    return str(data.get("siteApiToken", "")).strip()


def main() -> int:
    _extend_path()

    if not CONFIG_PATH.is_file():
        print(f"Missing {CONFIG_PATH}")
        print("Copy discord_bot/config.example.json to discord_bot/config.json and fill it in.")
        return 1

    raw = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    staff_ids = raw.get("ticket_staff_role_ids") or []
    if isinstance(staff_ids, list):
        staff_value = ",".join(str(x) for x in staff_ids)
    else:
        staff_value = str(staff_ids)

    auto_ids = raw.get("auto_role_ids") or []
    if not auto_ids and raw.get("auto_role_id"):
        auto_ids = [raw.get("auto_role_id")]
    if isinstance(auto_ids, list):
        auto_value = ",".join(str(x) for x in auto_ids)
    else:
        auto_value = str(auto_ids)

    owner_ids = raw.get("owner_discord_ids") or []
    if isinstance(owner_ids, list):
        owner_value = ",".join(str(x) for x in owner_ids)
    else:
        owner_value = str(owner_ids)

    brand = raw.get("brand", {}) or {}
    banner_url = str(brand.get("banner_url", "")).strip()
    if not banner_url:
        banner_path = str(brand.get("banner_path", "")).strip()
        if banner_path.lower().startswith(("http://", "https://")):
            banner_url = banner_path

    logo_url = str(brand.get("logo_url", "")).strip()
    if not logo_url:
        logo_path = str(brand.get("logo_path", "")).strip()
        if logo_path.lower().startswith(("http://", "https://")):
            logo_url = logo_path

    pairs = {
        "DISCORD_BOT_TOKEN": str(raw.get("token", "")).strip(),
        "DISCORD_GUILD_ID": str(raw.get("guild_id", "")),
        "DISCORD_WELCOME_CHANNEL_ID": str(raw.get("welcome_channel_id", "")),
        "DISCORD_LEAVE_CHANNEL_ID": str(raw.get("leave_channel_id", "")),
        "DISCORD_TICKET_CATEGORY_ID": str(raw.get("ticket_category_id", "")),
        "DISCORD_TICKET_STAFF_ROLE_IDS": staff_value,
        "DISCORD_TICKET_LOG_CHANNEL_ID": str(raw.get("ticket_log_channel_id", "")),
        "DISCORD_AUTO_ROLE_IDS": auto_value,
        "BOT_STATE_PATH": "/tmp/state.json",
        "BRAND_SERVER_NAME": str(brand.get("server_name", "Dot X")),
        "BRAND_ACCENT_HEX": str(brand.get("accent_hex", "#FFD700")),
        "BRAND_BANNER_URL": banner_url,
        "BRAND_LOGO_URL": logo_url,
        "DISCORD_CLIENT_ID": "1519618635054841867",
        "DISCORD_CUSTOMER_ROLE_ID": "1519527288503275641",
        "OWNER_DISCORD_IDS": owner_value,
        "HOST": "0.0.0.0",
        "DATA_DIR": "/data",
        "DATA_PATH": "/data/store.json",
        "API_ONLY": "1",
    }

    cors_origin = _github_cors_origin()
    if cors_origin:
        pairs["CORS_ORIGINS"] = cors_origin

    site_token = _deploy_site_token()
    if site_token and not site_token.startswith("YOUR_"):
        pairs["SITE_API_TOKEN"] = site_token

    missing = [
        k
        for k, v in pairs.items()
        if k
        not in {
            "BOT_STATE_PATH",
            "BRAND_BANNER_URL",
            "BRAND_LOGO_URL",
            "BRAND_ACCENT_HEX",
            "DISCORD_AUTO_ROLE_IDS",
            "API_ONLY",
            "CORS_ORIGINS",
            "OWNER_DISCORD_IDS",
            "SITE_API_TOKEN",
        }
        and not v
    ]
    if missing:
        print("These values are empty in config.json:", ", ".join(missing))
        return 1

    service = _linked_service_id()

    optional_keys = {
        "BRAND_BANNER_URL",
        "BRAND_LOGO_URL",
        "DISCORD_AUTO_ROLE_IDS",
        "CORS_ORIGINS",
        "OWNER_DISCORD_IDS",
        "SITE_API_TOKEN",
    }

    for key, value in pairs.items():
        if not value and key in optional_keys:
            print(f"Skipping {key} (empty).")
            continue
        print(f"Setting {key}...")
        code = _set_variable(service, key, value)
        if code != 0:
            print(f"Failed to set {key}. Is this folder linked? Run setup-railway.bat first.")
            return code

    print("Railway variables updated from config.json.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
