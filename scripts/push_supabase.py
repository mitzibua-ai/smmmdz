"""Push dotx to Supabase (schema data + edge API) and GitHub Pages (website + exe)."""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEPLOY_CONFIG = ROOT / "deploy.config.json"
CONFIG_JS = ROOT / "web" / "js" / "config.js"
DEFAULT_SUPABASE_URL = "https://bumuisxrzbteeymzeidh.supabase.co"
DEFAULT_API_SUFFIX = "/functions/v1/dotx"


def _run(cmd: list[str], *, cwd: Path | None = None, input_text: str | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(
        cmd,
        cwd=cwd or ROOT,
        text=True,
        capture_output=True,
        input=input_text,
        check=False,
    )


def _load_deploy() -> dict:
    if not DEPLOY_CONFIG.is_file():
        return {}
    try:
        return json.loads(DEPLOY_CONFIG.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def api_base_url(deploy: dict | None = None) -> str:
    data = deploy or _load_deploy()
    supabase = str(data.get("supabaseUrl", DEFAULT_SUPABASE_URL)).strip().rstrip("/")
    if not supabase:
        supabase = DEFAULT_SUPABASE_URL
    return f"{supabase}{DEFAULT_API_SUFFIX}"


def _sync_config_js() -> None:
    if not CONFIG_JS.is_file():
        return
    deploy = _load_deploy()
    text = CONFIG_JS.read_text(encoding="utf-8")
    api_url = api_base_url(deploy)
    text, _ = re.subn(r'(apiBaseUrl:\s*")[^"]*(")', rf'\1{api_url}\2', text, count=1)
    site_token = str(deploy.get("siteApiToken", "")).strip()
    if site_token and not site_token.startswith("YOUR_"):
        text, _ = re.subn(r'(apiToken:\s*")[^"]*(")', rf'\1{site_token}\2', text, count=1)
    text = re.sub(
        r"// Railway API URL.*?\n\s*//.*?\n\s*//.*?\n",
        "// Supabase Edge API (pins, scans, licenses, stamped exe download)\n",
        text,
        count=1,
    )
    text = text.replace(
        "// Site API security token — must match Railway SITE_API_TOKEN",
        "// Site API security token — must match Supabase secret SITE_API_TOKEN",
    )
    CONFIG_JS.write_text(text, encoding="utf-8")
    print(f"Updated web/js/config.js apiBaseUrl -> {api_url}")


def _export_supabase_env(deploy: dict) -> None:
    os.environ.setdefault("SUPABASE_URL", str(deploy.get("supabaseUrl", DEFAULT_SUPABASE_URL)).strip())
    key = str(deploy.get("supabaseServiceRoleKey", "")).strip()
    if key:
        os.environ["SUPABASE_SERVICE_ROLE_KEY"] = key


def _migrate_data() -> int:
    deploy = _load_deploy()
    _export_supabase_env(deploy)
    if not os.getenv("SUPABASE_SERVICE_ROLE_KEY", "").strip():
        print("[SKIP] Data migrate — add supabaseServiceRoleKey to deploy.config.json")
        return 0
    print("Migrating store.json -> Supabase...")
    return subprocess.call([sys.executable, str(ROOT / "scripts" / "migrate_store_to_supabase.py")])


def _supabase_cli() -> str:
    for name in ("supabase", "supabase.cmd"):
        found = shutil.which(name)
        if found:
            return found
    return "supabase"


def _deploy_edge_function(deploy: dict) -> int:
    cli = _supabase_cli()
    if not shutil.which(cli) and cli == "supabase":
        print("[SKIP] Edge function deploy — install Supabase CLI: npm i -g supabase")
        print("       Then run: supabase login && supabase functions deploy dotx --project-ref bumuisxrzbteeymzeidh")
        return 0

    print("Deploying Supabase Edge Function (dotx)...")

    secrets = {
        "SITE_API_TOKEN": str(deploy.get("siteApiToken", "")).strip(),
        "PUBLIC_URL": str(deploy.get("customSiteUrl", "https://dotx.store")).strip().rstrip("/"),
        "CUSTOM_SITE_URL": str(deploy.get("customSiteUrl", "https://dotx.store")).strip().rstrip("/"),
        "PUBLIC_EXE_URL": f"{str(deploy.get('customSiteUrl', 'https://dotx.store')).rstrip('/')}/downloads/dotx-pc-check.exe",
        "DISCORD_GUILD_ID": "1519369196188733440",
        "DISCORD_CUSTOMER_ROLE_ID": "1519527288503275641",
        "OWNER_DISCORD_IDS": "1284140942764539985",
    }
    bot_config = ROOT / "discord_bot" / "config.json"
    if bot_config.is_file():
        try:
            raw = json.loads(bot_config.read_text(encoding="utf-8"))
            token = str(raw.get("token", "")).strip()
            if token:
                secrets["DISCORD_BOT_TOKEN"] = token
            owner_ids = raw.get("owner_discord_ids") or []
            if isinstance(owner_ids, list) and owner_ids:
                secrets["OWNER_DISCORD_IDS"] = ",".join(str(x) for x in owner_ids)
        except (json.JSONDecodeError, OSError):
            pass

    for key, value in secrets.items():
        if not value or value.startswith("YOUR_"):
            continue
        print(f"Setting secret {key}...")
        set_cmd = [cli, "secrets", "set", f"{key}={value}", "--project-ref", "bumuisxrzbteeymzeidh"]
        set_result = _run(set_cmd)
        if set_result.returncode != 0 and set_result.stderr:
            print(set_result.stderr.rstrip())

    deploy_cmd = [
        cli,
        "functions",
        "deploy",
        "dotx",
        "--project-ref",
        "bumuisxrzbteeymzeidh",
    ]
    result = _run(deploy_cmd)
    if result.stdout:
        print(result.stdout.rstrip())
    if result.returncode != 0:
        if result.stderr:
            print(result.stderr.rstrip())
        print("[WARN] Edge function deploy failed. Set secrets in Supabase dashboard, then redeploy.")
        return result.returncode

    print("[OK] Supabase Edge Function deployed.")
    return 0


def _push_github() -> int:
    return subprocess.call([sys.executable, str(ROOT / "scripts" / "push_github.py")])


def main() -> int:
    print()
    print(" dotx - Push to Supabase + GitHub")
    print(" =================================")
    print()
    print(" Supabase  = database + API (pins, scans, licenses)")
    print(" GitHub    = website + PC Check exe download")
    print()

    deploy = _load_deploy()
    _sync_config_js()
    code = _migrate_data()
    if code != 0:
        return code
    edge = _deploy_edge_function(deploy)
    github = _push_github()
    print()
    if github == 0:
        print("[OK] Website pushed to GitHub Pages.")
    print(f"API URL: {api_base_url(deploy)}")
    print("Health:  {}/api/health".format(api_base_url(deploy)))
    if edge != 0:
        return edge
    return github


if __name__ == "__main__":
    sys.exit(main())
