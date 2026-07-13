"""Import web/data/store.json into Supabase tables."""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "web"
sys.path.insert(0, str(WEB))

from supabase_store import (  # noqa: E402
    _license_to_row,
    _pin_to_row,
    _scan_to_row,
    _user_to_row,
    _client_or_raise,
)

DEFAULT_STORE = WEB / "data" / "store.json"
DEFAULT_URL = "https://bumuisxrzbteeymzeidh.supabase.co"


def _chunked(rows: list[dict], size: int = 100):
    for i in range(0, len(rows), size):
        yield rows[i : i + size]


def main() -> int:
    store_path = Path(os.getenv("DATA_PATH", str(DEFAULT_STORE)))
    os.environ.setdefault("SUPABASE_URL", DEFAULT_URL)

    if not os.getenv("SUPABASE_SERVICE_ROLE_KEY", "").strip():
        print("Set SUPABASE_SERVICE_ROLE_KEY (Supabase → Settings → API → service_role).")
        return 1

    if not store_path.is_file():
        print(f"Missing {store_path}")
        return 1

    data = json.loads(store_path.read_text(encoding="utf-8"))
    client = _client_or_raise()

    users = [_user_to_row(u) for u in data.get("siteUsers", [])]
    pins = [_pin_to_row(p) for p in data.get("pins", [])]
    scans = [_scan_to_row(s) for s in data.get("scans", [])]
    keys = [_license_to_row(k) for k in data.get("licenseKeys", [])]

    for label, table, rows in (
        ("site users", "site_users", users),
        ("pins", "pins", pins),
        ("scans", "scans", scans),
        ("license keys", "license_keys", keys),
    ):
        if not rows:
            print(f"Skipping {label} (none in store.json).")
            continue
        for batch in _chunked(rows):
            client.table(table).upsert(batch).execute()
        print(f"Imported {len(rows)} {label}.")

    print("Done. Verify rows in Supabase Table Editor.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
