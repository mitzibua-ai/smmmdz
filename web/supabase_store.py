from __future__ import annotations

import os
import secrets
import threading
from datetime import datetime, timedelta, timezone

from db_common import (
    PANEL_ROLES,
    ROLE_RANK,
    activity_for_user,
    duration_to_seconds,
    enrich_site_user,
    format_duration,
    generate_license_code,
    generate_user_token,
    hash_license_code,
    is_lifetime_key,
    map_scanner_verdict,
    now_iso,
    parse_iso,
    verdict_totals,
)

_lock = threading.RLock()
_client = None
DEFAULT_SUPABASE_URL = "https://bumuisxrzbteeymzeidh.supabase.co"


def _supabase_url() -> str:
    return os.getenv("SUPABASE_URL", DEFAULT_SUPABASE_URL).strip() or DEFAULT_SUPABASE_URL


def _use_supabase() -> bool:
    return bool(_supabase_url() and os.getenv("SUPABASE_SERVICE_ROLE_KEY", "").strip())


def _client_or_raise():
    global _client
    if _client is None:
        from supabase import create_client

        url = _supabase_url()
        key = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "").strip()
        if not url or not key:
            raise RuntimeError("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY are required")
        _client = create_client(url, key)
    return _client


def _ts(value: str | None) -> str | None:
    if not value:
        return None
    return str(value).strip() or None


def _user_to_row(user: dict) -> dict:
    return {
        "discord_id": user["discordId"],
        "username": user.get("username") or "Unknown",
        "avatar_hash": user.get("avatarHash") or "",
        "user_token": user.get("userToken") or generate_user_token(),
        "panel_role": user.get("panelRole") or "member",
        "licensed_status": user.get("licensedStatus") or "Standard",
        "first_seen": _ts(user.get("firstSeen")),
        "joined_at": _ts(user.get("joinedAt") or user.get("firstSeen")),
        "last_seen": _ts(user.get("lastSeen")),
        "login_count": int(user.get("loginCount") or 0),
        "license_expires_at": _ts(user.get("licenseExpiresAt")),
        "license_key_id": user.get("licenseKeyId"),
        "license_granted_at": _ts(user.get("licenseGrantedAt")),
        "license_revoked_at": _ts(user.get("licenseRevokedAt")),
        "license_revoked_by": user.get("licenseRevokedBy"),
        "promoted_at": _ts(user.get("promotedAt")),
        "tool_branding": user.get("toolBranding"),
    }


def _user_from_row(row: dict) -> dict:
    return {
        "discordId": row["discord_id"],
        "username": row.get("username") or "Unknown",
        "avatarHash": row.get("avatar_hash") or "",
        "userToken": row.get("user_token") or "",
        "panelRole": row.get("panel_role") or "member",
        "licensedStatus": row.get("licensed_status") or "Standard",
        "firstSeen": row.get("first_seen"),
        "joinedAt": row.get("joined_at") or row.get("first_seen"),
        "lastSeen": row.get("last_seen"),
        "loginCount": int(row.get("login_count") or 0),
        "licenseExpiresAt": row.get("license_expires_at"),
        "licenseKeyId": row.get("license_key_id"),
        "licenseGrantedAt": row.get("license_granted_at"),
        "licenseRevokedAt": row.get("license_revoked_at"),
        "licenseRevokedBy": row.get("license_revoked_by"),
        "promotedAt": row.get("promoted_at"),
        "toolBranding": row.get("tool_branding"),
    }


def _pin_to_row(pin: dict) -> dict:
    return {
        "id": pin["id"],
        "pin": pin["pin"],
        "discord_id": pin["discordId"],
        "player_name": pin.get("playerName") or "—",
        "game": pin.get("game") or "FiveM",
        "status": pin.get("status") or "pending",
        "result": pin.get("result") or "Pending",
        "date": _ts(pin.get("date")),
        "scan_id": pin.get("scanId"),
    }


def _pin_from_row(row: dict) -> dict:
    return {
        "id": row["id"],
        "pin": row["pin"],
        "discordId": row["discord_id"],
        "playerName": row.get("player_name") or "—",
        "game": row.get("game") or "FiveM",
        "status": row.get("status") or "pending",
        "result": row.get("result") or "Pending",
        "date": row.get("date"),
        "scanId": row.get("scan_id"),
    }


def _scan_to_row(scan: dict) -> dict:
    return {
        "id": scan["id"],
        "discord_id": scan["discordId"],
        "pin_id": scan.get("pinId"),
        "pin": scan["pin"],
        "date": _ts(scan.get("date")),
        "player_name": scan.get("playerName") or "—",
        "verdict": scan.get("verdict") or "review",
        "threats": int(scan.get("threats") or 0),
        "warnings": int(scan.get("warnings") or 0),
        "summary": scan.get("summary") or "",
        "report_text": scan.get("reportText") or "",
        "hostname": scan.get("hostname") or "",
        "username": scan.get("username") or "",
    }


def _scan_from_row(row: dict) -> dict:
    return {
        "id": row["id"],
        "discordId": row["discord_id"],
        "pinId": row.get("pin_id"),
        "pin": row["pin"],
        "date": row.get("date"),
        "playerName": row.get("player_name") or "—",
        "verdict": row.get("verdict") or "review",
        "threats": int(row.get("threats") or 0),
        "warnings": int(row.get("warnings") or 0),
        "summary": row.get("summary") or "",
        "reportText": row.get("report_text") or "",
        "hostname": row.get("hostname") or "",
        "username": row.get("username") or "",
    }


def _license_to_row(key: dict) -> dict:
    return {
        "id": key["id"],
        "code_hash": key["codeHash"],
        "created_by": key["createdBy"],
        "created_at": _ts(key.get("createdAt")),
        "duration_seconds": int(key.get("durationSeconds") or 0),
        "duration_label": key.get("durationLabel") or "",
        "status": key.get("status") or "active",
        "redeemed_by": key.get("redeemedBy"),
        "redeemed_at": _ts(key.get("redeemedAt")),
        "license_expires_at": _ts(key.get("licenseExpiresAt")),
        "ticket_channel_id": key.get("ticketChannelId"),
        "ticket_ref": key.get("ticketRef"),
        "redeemed_by_staff": key.get("redeemedByStaff"),
        "revoked_at": _ts(key.get("revokedAt")),
        "revoked_by": key.get("revokedBy"),
    }


def _license_from_row(row: dict) -> dict:
    return {
        "id": row["id"],
        "codeHash": row["code_hash"],
        "createdBy": row.get("created_by"),
        "createdAt": row.get("created_at"),
        "durationSeconds": int(row.get("duration_seconds") or 0),
        "durationLabel": row.get("duration_label") or "",
        "status": row.get("status") or "active",
        "redeemedBy": row.get("redeemed_by"),
        "redeemedAt": row.get("redeemed_at"),
        "licenseExpiresAt": row.get("license_expires_at"),
        "ticketChannelId": row.get("ticket_channel_id"),
        "ticketRef": row.get("ticket_ref"),
        "redeemedByStaff": row.get("redeemed_by_staff"),
        "revokedAt": row.get("revoked_at"),
        "revokedBy": row.get("revoked_by"),
    }


def _fetch_all_users() -> list[dict]:
    res = _client_or_raise().table("site_users").select("*").execute()
    return [_user_from_row(row) for row in (res.data or [])]


def _fetch_user(discord_id: str) -> dict | None:
    res = (
        _client_or_raise()
        .table("site_users")
        .select("*")
        .eq("discord_id", str(discord_id).strip())
        .limit(1)
        .execute()
    )
    rows = res.data or []
    return _user_from_row(rows[0]) if rows else None


def _upsert_user(user: dict) -> dict:
    row = _user_to_row(user)
    res = _client_or_raise().table("site_users").upsert(row, on_conflict="discord_id").execute()
    rows = res.data or [row]
    return _user_from_row(rows[0])


def _fetch_all_pins() -> list[dict]:
    res = _client_or_raise().table("pins").select("*").order("date", desc=True).execute()
    return [_pin_from_row(row) for row in (res.data or [])]


def _fetch_all_scans() -> list[dict]:
    res = _client_or_raise().table("scans").select("*").order("date", desc=True).execute()
    return [_scan_from_row(row) for row in (res.data or [])]


def get_active_site_license(discord_id: str) -> dict | None:
    user = get_site_user(discord_id)
    if not user:
        return None
    expires = parse_iso(str(user.get("licenseExpiresAt", "")))
    if not expires:
        # Lifetime: Customer with a redeemed key and no expiry timestamp
        if (
            str(user.get("licensedStatus") or "").lower() == "customer"
            and user.get("licenseKeyId")
        ):
            return {
                "discordId": str(discord_id),
                "licenseExpiresAt": None,
                "licenseGrantedAt": user.get("licenseGrantedAt"),
                "licenseKeyId": user.get("licenseKeyId"),
                "licensedStatus": "Customer",
                "lifetime": True,
            }
        return None
    if expires.tzinfo is None:
        expires = expires.replace(tzinfo=timezone.utc)
    now = datetime.now(timezone.utc)
    if expires <= now:
        return None
    return {
        "discordId": str(discord_id),
        "licenseExpiresAt": expires.isoformat(),
        "licenseGrantedAt": user.get("licenseGrantedAt"),
        "licenseKeyId": user.get("licenseKeyId"),
        "licensedStatus": "Customer",
        "lifetime": False,
    }


def expire_site_licenses() -> list[dict]:
    """Mark expired timed licenses as Standard. Returns cleared user records."""
    now = datetime.now(timezone.utc)
    now_iso = now.isoformat()
    client = _client_or_raise()
    res = (
        client.table("site_users")
        .select("*")
        .not_.is_("license_expires_at", "null")
        .lte("license_expires_at", now_iso)
        .execute()
    )
    expired: list[dict] = []
    for row in res.data or []:
        user = _user_from_row(row)
        user["licensedStatus"] = "Standard"
        user["licenseExpiresAt"] = None
        user["licenseKeyId"] = None
        _upsert_user(user)
        expired.append(user)
    return expired


def create_license_key(*, created_by: str, amount: int, unit: str) -> dict:
    seconds = duration_to_seconds(amount, unit)
    code = generate_license_code()
    now = datetime.now(timezone.utc)
    entry = {
        "id": f"lk_{int(now.timestamp() * 1000)}_{secrets.token_hex(3)}",
        "codeHash": hash_license_code(code),
        "createdBy": str(created_by).strip(),
        "createdAt": now.isoformat(),
        "durationSeconds": seconds,
        "durationLabel": format_duration(amount, unit),
        "status": "active",
        "redeemedBy": None,
        "redeemedAt": None,
        "licenseExpiresAt": None,
        "ticketChannelId": None,
        "ticketRef": None,
        "redeemedByStaff": None,
    }
    with _lock:
        _client_or_raise().table("license_keys").insert(_license_to_row(entry)).execute()
    return {**entry, "code": code}


def _find_license_key(code: str) -> dict | None:
    code_hash = hash_license_code(code)
    res = (
        _client_or_raise()
        .table("license_keys")
        .select("*")
        .eq("code_hash", code_hash)
        .limit(1)
        .execute()
    )
    rows = res.data or []
    return _license_from_row(rows[0]) if rows else None


def redeem_license_key(
    *,
    code: str,
    target_discord_id: str,
    staff_id: str,
    ticket_channel_id: str | None = None,
    ticket_ref: str | None = None,
) -> dict:
    target_id = str(target_discord_id).strip()
    if not target_id.isdigit():
        raise ValueError("invalid_discord_id")

    with _lock:
        key_entry = _find_license_key(code)
        if not key_entry:
            raise LookupError("invalid_key")
        if str(key_entry.get("status")) != "active":
            raise LookupError("key_used")

        now = datetime.now(timezone.utc)
        lifetime = is_lifetime_key(key_entry)
        if lifetime:
            expires_iso = None
        else:
            expires = now + timedelta(seconds=int(key_entry.get("durationSeconds") or 0))
            expires_iso = expires.isoformat()

        key_entry["status"] = "redeemed"
        key_entry["redeemedBy"] = target_id
        key_entry["redeemedAt"] = now.isoformat()
        key_entry["licenseExpiresAt"] = expires_iso
        key_entry["ticketChannelId"] = str(ticket_channel_id or "").strip() or None
        key_entry["ticketRef"] = str(ticket_ref or "").strip() or None
        key_entry["redeemedByStaff"] = str(staff_id).strip()

        _client_or_raise().table("license_keys").upsert(
            _license_to_row(key_entry), on_conflict="id"
        ).execute()

        user = _fetch_user(target_id)
        if user:
            user["licensedStatus"] = "Customer"
            user["licenseExpiresAt"] = expires_iso
            user["licenseKeyId"] = key_entry.get("id")
            user["licenseGrantedAt"] = now.isoformat()
            _upsert_user(user)
        else:
            _upsert_user(
                {
                    "discordId": target_id,
                    "username": "Unknown",
                    "avatarHash": "",
                    "userToken": generate_user_token(),
                    "panelRole": "member",
                    "licensedStatus": "Customer",
                    "licenseExpiresAt": expires_iso,
                    "licenseKeyId": key_entry.get("id"),
                    "licenseGrantedAt": now.isoformat(),
                    "firstSeen": now.isoformat(),
                    "joinedAt": now.isoformat(),
                    "lastSeen": now.isoformat(),
                    "loginCount": 0,
                }
            )

        return {
            "key": dict(key_entry),
            "targetDiscordId": target_id,
            "licenseExpiresAt": expires_iso,
            "durationLabel": key_entry.get("durationLabel"),
            "lifetime": lifetime,
        }


def revoke_site_license(*, discord_id: str, staff_id: str) -> dict:
    target_id = str(discord_id).strip()
    if not target_id.isdigit():
        raise ValueError("invalid_discord_id")

    with _lock:
        user = _fetch_user(target_id)
        if not user:
            raise LookupError("user_not_found")

        now = now_iso()
        key_id = user.get("licenseKeyId")
        if key_id:
            res = (
                _client_or_raise()
                .table("license_keys")
                .select("*")
                .eq("id", str(key_id))
                .limit(1)
                .execute()
            )
            rows = res.data or []
            if rows:
                key_entry = _license_from_row(rows[0])
                if str(key_entry.get("redeemedBy")) == target_id:
                    key_entry["status"] = "revoked"
                    key_entry["revokedAt"] = now
                    key_entry["revokedBy"] = str(staff_id).strip()
                    _client_or_raise().table("license_keys").upsert(
                        _license_to_row(key_entry), on_conflict="id"
                    ).execute()

        user["licensedStatus"] = "Standard"
        user["licenseExpiresAt"] = None
        user["licenseKeyId"] = None
        user["licenseRevokedAt"] = now
        user["licenseRevokedBy"] = str(staff_id).strip()
        return _upsert_user(user)


def list_license_keys(*, limit: int = 25) -> list[dict]:
    res = (
        _client_or_raise()
        .table("license_keys")
        .select("*")
        .order("created_at", desc=True)
        .limit(limit)
        .execute()
    )
    safe = []
    for row in res.data or []:
        item = _license_from_row(row)
        item.pop("codeHash", None)
        safe.append(item)
    return safe


def register_site_user(payload: dict) -> dict:
    with _lock:
        discord_id = str(payload.get("discordId", "")).strip()
        if not discord_id:
            raise ValueError("discordId required")

        username = str(payload.get("username") or "Unknown").strip() or "Unknown"
        avatar_hash = str(payload.get("avatarHash") or "").strip()
        licensed_status = str(payload.get("licensedStatus") or "Standard").strip() or "Standard"
        active = get_active_site_license(discord_id)
        if active:
            licensed_status = "Customer"
        elif licensed_status == "Customer":
            licensed_status = "Standard"
        now = now_iso()

        existing = _fetch_user(discord_id)
        if existing:
            if not str(existing.get("userToken") or "").strip():
                existing["userToken"] = generate_user_token()
            preserved_first_seen = existing.get("firstSeen")
            existing.update(
                {
                    "username": username,
                    "avatarHash": avatar_hash or existing.get("avatarHash", ""),
                    "licensedStatus": licensed_status,
                    "lastSeen": now,
                    "loginCount": int(existing.get("loginCount") or 0) + 1,
                }
            )
            if preserved_first_seen:
                existing["firstSeen"] = preserved_first_seen
                existing["joinedAt"] = preserved_first_seen
            if active:
                existing["licenseExpiresAt"] = active["licenseExpiresAt"]
                if active.get("licenseKeyId"):
                    existing["licenseKeyId"] = active["licenseKeyId"]
            elif licensed_status == "Standard":
                existing.pop("licenseExpiresAt", None)
                existing.pop("licenseKeyId", None)
            return _upsert_user(existing)

        entry = {
            "discordId": discord_id,
            "username": username,
            "avatarHash": avatar_hash,
            "userToken": generate_user_token(),
            "panelRole": "member",
            "licensedStatus": licensed_status,
            "firstSeen": now,
            "joinedAt": now,
            "lastSeen": now,
            "loginCount": 1,
        }
        return _upsert_user(entry)


def get_site_user(discord_id: str) -> dict | None:
    return _fetch_user(discord_id)


def save_tool_branding(discord_id: str, branding: dict) -> dict:
    user = _fetch_user(discord_id)
    if not user:
        raise ValueError("user_not_found")
    clean = {
        "showDiscordAvatar": branding.get("showDiscordAvatar") is not False,
        "username": str(branding.get("username") or user.get("username") or "")[:64],
        "discordId": str(discord_id).strip(),
        "avatarUrl": str(branding.get("avatarUrl") or "")[:500],
        "customImage": branding.get("customImage")
        if isinstance(branding.get("customImage"), str) and len(branding.get("customImage") or "") <= 200000
        else None,
    }
    user["toolBranding"] = clean
    _upsert_user(user)
    return clean


def branding_for_user(user: dict | None) -> dict | None:
    if not user:
        return None
    stored = user.get("toolBranding")
    if isinstance(stored, dict) and stored:
        return dict(stored)
    discord_id = str(user.get("discordId") or "")
    hash_ = str(user.get("avatarHash") or "")
    if discord_id and hash_:
        avatar_url = f"https://cdn.discordapp.com/avatars/{discord_id}/{hash_}.png?size=128"
    elif discord_id:
        try:
            idx = (int(discord_id) >> 22) % 6
        except ValueError:
            idx = 0
        avatar_url = f"https://cdn.discordapp.com/embed/avatars/{idx}.png"
    else:
        avatar_url = ""
    return {
        "showDiscordAvatar": True,
        "username": user.get("username") or "",
        "discordId": discord_id,
        "avatarUrl": avatar_url,
        "customImage": None,
    }


def list_site_users() -> list[dict]:
    return _fetch_all_users()


def set_site_user_role(target_id: str, role: str) -> dict | None:
    role = str(role).strip().lower()
    if role not in PANEL_ROLES:
        raise ValueError("invalid_role")

    with _lock:
        user = _fetch_user(target_id)
        if not user:
            now = now_iso()
            user = {
                "discordId": str(target_id).strip(),
                "username": "Unknown",
                "avatarHash": "",
                "userToken": generate_user_token(),
                "panelRole": role,
                "licensedStatus": "Standard",
                "firstSeen": now,
                "lastSeen": now,
                "loginCount": 0,
                "promotedAt": now,
            }
            return _upsert_user(user)

        user["panelRole"] = role
        user["promotedAt"] = now_iso()
        return _upsert_user(user)


def register_pin(payload: dict) -> dict:
    with _lock:
        pin_code = str(payload.get("pin", "")).strip()
        discord_id = str(payload.get("discordId", "")).strip()
        if not pin_code or not discord_id:
            raise ValueError("pin and discordId required")

        res = (
            _client_or_raise()
            .table("pins")
            .select("*")
            .eq("pin", pin_code)
            .limit(1)
            .execute()
        )
        rows = res.data or []
        if rows:
            item = _pin_from_row(rows[0])
            item.update(
                {
                    "discordId": discord_id,
                    "playerName": payload.get("playerName") or item.get("playerName") or "—",
                    "game": payload.get("game") or item.get("game") or "FiveM",
                    "id": payload.get("id") or item.get("id"),
                    "date": payload.get("date") or item.get("date") or now_iso(),
                }
            )
            updated = (
                _client_or_raise()
                .table("pins")
                .upsert(_pin_to_row(item), on_conflict="pin")
                .execute()
            )
            out_rows = updated.data or [_pin_to_row(item)]
            return _pin_from_row(out_rows[0])

        entry = {
            "id": payload.get("id") or f"pin_{int(datetime.now().timestamp() * 1000)}",
            "pin": pin_code,
            "discordId": discord_id,
            "playerName": payload.get("playerName") or "—",
            "game": payload.get("game") or "FiveM",
            "status": "pending",
            "result": "Pending",
            "date": payload.get("date") or now_iso(),
            "scanId": None,
        }
        inserted = _client_or_raise().table("pins").insert(_pin_to_row(entry)).execute()
        out_rows = inserted.data or [_pin_to_row(entry)]
        return _pin_from_row(out_rows[0])


def list_pins(discord_id: str) -> list[dict]:
    res = (
        _client_or_raise()
        .table("pins")
        .select("*")
        .eq("discord_id", str(discord_id))
        .order("date", desc=True)
        .execute()
    )
    return [_pin_from_row(row) for row in (res.data or [])]


def delete_pin(pin_id: str, discord_id: str) -> bool:
    with _lock:
        res = (
            _client_or_raise()
            .table("pins")
            .delete()
            .eq("id", str(pin_id))
            .eq("discord_id", str(discord_id))
            .execute()
        )
        return bool(res.data)


def find_pin_by_code(pin_code: str) -> dict | None:
    res = (
        _client_or_raise()
        .table("pins")
        .select("*")
        .eq("pin", str(pin_code))
        .limit(1)
        .execute()
    )
    rows = res.data or []
    return _pin_from_row(rows[0]) if rows else None


def submit_scan(payload: dict) -> dict:
    with _lock:
        pin_code = str(payload.get("pin", "")).strip()
        pin_entry = find_pin_by_code(pin_code)
        if not pin_entry:
            raise LookupError("invalid_pin")

        verdict, result_label, pin_status = map_scanner_verdict(payload.get("verdict", ""))
        scan_id = payload.get("id") or f"scan_{int(datetime.now().timestamp() * 1000)}"
        player_name = payload.get("playerName") or pin_entry.get("playerName") or "—"

        scan = {
            "id": scan_id,
            "discordId": pin_entry["discordId"],
            "pinId": pin_entry.get("id"),
            "pin": pin_code,
            "date": payload.get("date") or now_iso(),
            "playerName": player_name,
            "verdict": verdict,
            "threats": int(payload.get("threats") or 0),
            "warnings": int(payload.get("warnings") or 0),
            "summary": payload.get("summary") or "",
            "reportText": payload.get("reportText") or "",
            "hostname": payload.get("hostname") or "",
            "username": payload.get("username") or "",
        }
        _client_or_raise().table("scans").insert(_scan_to_row(scan)).execute()

        pin_entry = {
            **pin_entry,
            "status": pin_status,
            "result": result_label,
            "scanId": scan_id,
        }
        _client_or_raise().table("pins").upsert(_pin_to_row(pin_entry), on_conflict="pin").execute()
        return scan


def list_scans(discord_id: str) -> list[dict]:
    res = (
        _client_or_raise()
        .table("scans")
        .select("*")
        .eq("discord_id", str(discord_id))
        .order("date", desc=True)
        .execute()
    )
    return [_scan_from_row(row) for row in (res.data or [])]


def build_role_dashboard(
    *,
    resolve_effective_role,
    include_users: bool = True,
    actor_role: str = "owner",
) -> dict:
    pins = _fetch_all_pins()
    scans = _fetch_all_scans()
    site_users = _fetch_all_users()

    enriched_users = []
    role_counts = {"owner": 0, "admin": 0, "staff": 0, "member": 0}
    for user in site_users:
        effective = resolve_effective_role(str(user.get("discordId", "")))
        role_counts[effective] = role_counts.get(effective, 0) + 1
        if include_users:
            enriched_users.append(enrich_site_user(user, pins, scans, effective))

    enriched_users.sort(
        key=lambda u: (ROLE_RANK.get(u.get("panelRole", "member"), 0), u.get("firstSeen", "")),
        reverse=True,
    )

    return {
        "actorRole": actor_role,
        "totals": {
            "siteUsers": len(site_users),
            "pins": len(pins),
            "scans": len(scans),
            "staff": role_counts.get("staff", 0),
            "admins": role_counts.get("admin", 0),
            "members": role_counts.get("member", 0),
        },
        "roleCounts": role_counts,
        "verdicts": verdict_totals(scans),
        "siteUsers": enriched_users,
        "recentPins": pins[:15],
        "recentScans": scans[:15],
    }
