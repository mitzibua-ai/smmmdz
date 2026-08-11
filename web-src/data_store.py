"""Data store — Supabase when configured, otherwise local store.json."""
from __future__ import annotations

import os

from db_common import (
    KEY_ALPHABET,
    PANEL_ROLES,
    ROLE_RANK,
    duration_to_seconds,
    format_duration,
    generate_license_code,
    generate_user_token,
    is_lifetime_key,
    map_scanner_verdict,
)

SUPABASE_URL = "https://bumuisxrzbteeymzeidh.supabase.co"


def _use_supabase() -> bool:
    url = os.getenv("SUPABASE_URL", SUPABASE_URL).strip() or SUPABASE_URL
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "").strip()
    if key:
        os.environ.setdefault("SUPABASE_URL", url)
    return bool(url and key)


if _use_supabase():
    from supabase_store import (  # noqa: F401
        branding_for_user,
        build_role_dashboard,
        create_license_key,
        delete_pin,
        expire_site_licenses,
        find_pin_by_code,
        get_active_site_license,
        get_site_user,
        list_license_keys,
        list_pins,
        list_scans,
        list_site_users,
        redeem_license_key,
        register_pin,
        register_site_user,
        revoke_site_license,
        save_tool_branding,
        set_site_user_role,
        submit_scan,
    )
else:
    from json_store import (  # noqa: F401
        branding_for_user,
        build_role_dashboard,
        create_license_key,
        delete_pin,
        expire_site_licenses,
        find_pin_by_code,
        get_active_site_license,
        get_site_user,
        list_license_keys,
        list_pins,
        list_scans,
        list_site_users,
        redeem_license_key,
        register_pin,
        register_site_user,
        revoke_site_license,
        save_tool_branding,
        set_site_user_role,
        submit_scan,
    )

__all__ = [
    "PANEL_ROLES",
    "ROLE_RANK",
    "KEY_ALPHABET",
    "duration_to_seconds",
    "format_duration",
    "generate_license_code",
    "generate_user_token",
    "is_lifetime_key",
    "map_scanner_verdict",
    "branding_for_user",
    "build_role_dashboard",
    "create_license_key",
    "delete_pin",
    "expire_site_licenses",
    "find_pin_by_code",
    "get_active_site_license",
    "get_site_user",
    "list_license_keys",
    "list_pins",
    "list_scans",
    "list_site_users",
    "redeem_license_key",
    "register_pin",
    "register_site_user",
    "revoke_site_license",
    "save_tool_branding",
    "set_site_user_role",
    "submit_scan",
]
