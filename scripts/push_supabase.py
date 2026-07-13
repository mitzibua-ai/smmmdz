"""Push dotx to Supabase (database RPC) and GitHub Pages (website + exe)."""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEPLOY_CONFIG = ROOT / "deploy.config.json"
CONFIG_JS = ROOT / "web" / "js" / "config.js"
DEFAULT_SUPABASE_URL = "https://bumuisxrzbteeymzeidh.supabase.co"


def _load_deploy() -> dict:
    if not DEPLOY_CONFIG.is_file():
        return {}
    try:
        return json.loads(DEPLOY_CONFIG.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def _sync_config_js() -> None:
    if not CONFIG_JS.is_file():
        return
    deploy = _load_deploy()
    text = CONFIG_JS.read_text(encoding="utf-8")
    supabase_url = str(deploy.get("supabaseUrl", DEFAULT_SUPABASE_URL)).strip().rstrip("/")
    if supabase_url and "supabaseUrl:" in text:
        text, _ = re.subn(r'(supabaseUrl:\s*")[^"]*(")', rf'\1{supabase_url}\2', text, count=1)
        print(f"Updated web/js/config.js supabaseUrl -> {supabase_url}")
    anon_key = str(deploy.get("supabaseAnonKey", "")).strip()
    if anon_key and not anon_key.startswith("YOUR_"):
        if "supabaseAnonKey:" in text:
            text, _ = re.subn(r'(supabaseAnonKey:\s*")[^"]*(")', rf'\1{anon_key}\2', text, count=1)
        else:
            text = text.replace(
                "supabaseUrl:",
                f'supabaseAnonKey: "{anon_key}",\n\n  supabaseUrl:',
                1,
            )
        print("Updated web/js/config.js supabaseAnonKey")
    site_token = str(deploy.get("siteApiToken", "")).strip()
    if site_token and not site_token.startswith("YOUR_"):
        text, _ = re.subn(r'(apiToken:\s*")[^"]*(")', rf'\1{site_token}\2', text, count=1)
    CONFIG_JS.write_text(text, encoding="utf-8")


def _export_supabase_env(deploy: dict) -> None:
    os.environ.setdefault("SUPABASE_URL", str(deploy.get("supabaseUrl", DEFAULT_SUPABASE_URL)).strip())
    key = str(deploy.get("supabaseServiceRoleKey", "")).strip()
    if key:
        os.environ["SUPABASE_SERVICE_ROLE_KEY"] = key


def _migrate_data() -> int:
    deploy = _load_deploy()
    _export_supabase_env(deploy)
    if not os.getenv("SUPABASE_SERVICE_ROLE_KEY", "").strip():
        print("[SKIP] Data migrate — add supabaseServiceRoleKey to deploy.config.json (optional)")
        return 0
    print("Migrating store.json -> Supabase...")
    return subprocess.call([sys.executable, str(ROOT / "scripts" / "migrate_store_to_supabase.py")])


def _test_supabase_rpc(deploy: dict) -> bool:
    url = str(deploy.get("supabaseUrl", DEFAULT_SUPABASE_URL)).strip().rstrip("/")
    key = str(deploy.get("supabaseAnonKey", "")).strip()
    if not url or not key or key.startswith("YOUR_"):
        print("[WARN] Add supabaseAnonKey to deploy.config.json")
        return False
    endpoint = f"{url}/rest/v1/rpc/api_health"
    req = urllib.request.Request(
        endpoint,
        data=b"{}",
        method="POST",
        headers={
            "apikey": key,
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            body = json.loads(resp.read().decode("utf-8"))
            if body.get("ok") is True:
                print(f"[OK] Supabase API online ({url})")
                return True
    except urllib.error.HTTPError as err:
        detail = err.read().decode("utf-8", errors="replace")[:200]
        print(f"[WARN] Supabase RPC check failed ({err.code}): {detail}")
    except OSError as err:
        print(f"[WARN] Supabase RPC check failed: {err}")
    print("  Run supabase/schema.sql and supabase/rpc.sql in Supabase SQL Editor if you have not yet.")
    return False


def _push_github() -> int:
    return subprocess.call([sys.executable, str(ROOT / "scripts" / "push_github.py")])


def main() -> int:
    print()
    print(" dotx - Push to Supabase + GitHub")
    print(" =================================")
    print()
    print(" Supabase  = database API (pins, scans, licenses)")
    print(" GitHub    = website + PC Check exe download")
    print()

    deploy = _load_deploy()
    _sync_config_js()
    code = _migrate_data()
    if code != 0:
        return code

    rpc_ok = _test_supabase_rpc(deploy)
    github = _push_github()

    print()
    if github == 0:
        print("[OK] Website pushed to GitHub Pages (dotx.store).")
    if rpc_ok:
        print("[OK] Pins and scans will use Supabase directly — no Edge Function needed.")
    else:
        print("[ACTION] Open setup-supabase.bat or run schema.sql + rpc.sql in Supabase SQL Editor.")

    if github != 0:
        return github
    return 0 if rpc_ok else 1


if __name__ == "__main__":
    sys.exit(main())
