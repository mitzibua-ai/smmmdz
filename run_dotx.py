"""Run Discord bot — licenses/users go to Supabase (not local store.json)."""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _load_deploy_env() -> None:
    deploy_path = ROOT / "deploy.config.json"
    if not deploy_path.is_file():
        return
    try:
        import json

        data = json.loads(deploy_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return
    url = str(data.get("supabaseUrl", "")).strip()
    if url:
        os.environ.setdefault("SUPABASE_URL", url)
    key = str(data.get("supabaseServiceRoleKey", "")).strip()
    if key and not key.startswith("YOUR_"):
        os.environ.setdefault("SUPABASE_SERVICE_ROLE_KEY", key)


def main() -> int:
    _load_deploy_env()
    os.environ.setdefault("SUPABASE_URL", "https://bumuisxrzbteeymzeidh.supabase.co")
    os.environ.setdefault("BOT_STATE_PATH", str(ROOT / "discord_bot" / "state.json"))

    service_key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "").strip()
    if not service_key or service_key.startswith("YOUR_"):
        print(
            "[ERROR] Supabase service role key missing.\n"
            "  1. Supabase Dashboard → Settings → API → service_role\n"
            "  2. Paste into deploy.config.json as supabaseServiceRoleKey\n"
            "  Without this, licenses never reach the website database.",
            flush=True,
        )
        return 1

    web_dir = ROOT / "web"
    if str(web_dir) not in sys.path:
        sys.path.insert(0, str(web_dir))

    print("[dotx] Discord bot → Supabase database", flush=True)
    print(f"[dotx] SUPABASE_URL={os.environ.get('SUPABASE_URL', '')}", flush=True)

    from discord_bot.bot import main as bot_main

    bot_main()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
