from __future__ import annotations

import hashlib
import json
import os
import secrets
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DATA_DIR = Path(os.getenv("DATA_DIR", str(ROOT / "data")))
STORE_PATH = Path(os.getenv("DATA_PATH", str(DATA_DIR / "store.json")))

_lock = threading.Lock()
PANEL_ROLES = {"member", "staff", "admin", "owner"}
ROLE_RANK = {"member": 1, "staff": 2, "admin": 3, "owner": 4}
KEY_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _default_store() -> dict:
    return {"pins": [], "scans": [], "siteUsers": [], "licenseKeys": []}


def load_store() -> dict:
    STORE_PATH.parent.mkdir(parents=True, exist_ok=True)
    if not STORE_PATH.exists():
        return _default_store()
    try:
        data = json.loads(STORE_PATH.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            return _default_store()
        data.setdefault("pins", [])
        data.setdefault("scans", [])
        data.setdefault("siteUsers", [])
        data.setdefault("licenseKeys", [])
        return data
    except (json.JSONDecodeError, OSError):
        return _default_store()


def save_store(data: dict) -> None:
    STORE_PATH.parent.mkdir(parents=True, exist_ok=True)
    STORE_PATH.write_text(json.dumps(data, indent=2), encoding="utf-8")


def _find_site_user(store: dict, discord_id: str) -> dict | None:
    target = str(discord_id).strip()
    for user in store.get("siteUsers", []):
        if str(user.get("discordId")) == target:
            return user
    return None


def _parse_iso(value: str) -> datetime | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    try:
        if raw.endswith("Z"):
            raw = raw[:-1] + "+00:00"
        return datetime.fromisoformat(raw)
    except ValueError:
        return None


def _hash_license_code(code: str) -> str:
    normalized = str(code or "").strip().upper().replace(" ", "")
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def generate_license_code() -> str:
    part = lambda: "".join(secrets.choice(KEY_ALPHABET) for _ in range(4))
    return f"SMKY-{part()}-{part()}"


def duration_to_seconds(amount: int, unit: str) -> int:
    value = max(1, int(amount))
    unit_key = str(unit or "").strip().lower().rstrip("s")
    if unit_key in {"month", "mo"}:
        return value * 30 * 86400
    if unit_key in {"day", "d"}:
        return value * 86400
    if unit_key in {"hour", "hr", "h"}:
        return value * 3600
    if unit_key in {"minute", "min", "m"}:
        return value * 60
    raise ValueError("invalid_unit")


def format_duration(amount: int, unit: str) -> str:
    value = max(1, int(amount))
    unit_key = str(unit or "").strip().lower().rstrip("s")
    labels = {
        "month": ("month", "months"),
        "mo": ("month", "months"),
        "day": ("day", "days"),
        "d": ("day", "days"),
        "hour": ("hour", "hours"),
        "hr": ("hour", "hours"),
        "h": ("hour", "hours"),
        "minute": ("minute", "minutes"),
        "min": ("minute", "minutes"),
        "m": ("minute", "minutes"),
    }
    singular, plural = labels.get(unit_key, ("unit", "units"))
    return f"{value} {singular if value == 1 else plural}"


def get_active_site_license(discord_id: str) -> dict | None:
    user = get_site_user(discord_id)
    if not user:
        return None
    expires = _parse_iso(str(user.get("licenseExpiresAt", "")))
    if not expires:
        return None
    if expires.tzinfo is None:
        expires = expires.replace(tzinfo=timezone.utc)
    now = datetime.now(timezone.utc)
    if expires <= now:
        return None
    return {
        "discordId": str(discord_id),
        "licenseExpiresAt": expires.isoformat(),
        "licenseKeyId": user.get("licenseKeyId"),
        "licensedStatus": "Customer",
    }


def create_license_key(*, created_by: str, amount: int, unit: str) -> dict:
    seconds = duration_to_seconds(amount, unit)
    code = generate_license_code()
    now = datetime.now(timezone.utc)
    entry = {
        "id": f"lk_{int(now.timestamp() * 1000)}_{secrets.token_hex(3)}",
        "codeHash": _hash_license_code(code),
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
        store = load_store()
        store.setdefault("licenseKeys", []).insert(0, entry)
        save_store(store)
    return {**entry, "code": code}


def _find_license_key(store: dict, code: str) -> dict | None:
    code_hash = _hash_license_code(code)
    for item in store.get("licenseKeys", []):
        if str(item.get("codeHash")) == code_hash:
            return item
    return None


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
        store = load_store()
        key_entry = _find_license_key(store, code)
        if not key_entry:
            raise LookupError("invalid_key")
        if str(key_entry.get("status")) != "active":
            raise LookupError("key_used")

        now = datetime.now(timezone.utc)
        expires = now + timedelta(seconds=int(key_entry.get("durationSeconds") or 0))
        expires_iso = expires.isoformat()

        key_entry["status"] = "redeemed"
        key_entry["redeemedBy"] = target_id
        key_entry["redeemedAt"] = now.isoformat()
        key_entry["licenseExpiresAt"] = expires_iso
        key_entry["ticketChannelId"] = str(ticket_channel_id or "").strip() or None
        key_entry["ticketRef"] = str(ticket_ref or "").strip() or None
        key_entry["redeemedByStaff"] = str(staff_id).strip()

        user = _find_site_user(store, target_id)
        if user:
            user["licensedStatus"] = "Customer"
            user["licenseExpiresAt"] = expires_iso
            user["licenseKeyId"] = key_entry.get("id")
            user["licenseGrantedAt"] = now.isoformat()
        else:
            store["siteUsers"].insert(
                0,
                {
                    "discordId": target_id,
                    "username": "Unknown",
                    "avatarHash": "",
                    "panelRole": "member",
                    "licensedStatus": "Customer",
                    "licenseExpiresAt": expires_iso,
                    "licenseKeyId": key_entry.get("id"),
                    "licenseGrantedAt": now.isoformat(),
                    "firstSeen": now.isoformat(),
                    "lastSeen": now.isoformat(),
                    "loginCount": 0,
                },
            )

        save_store(store)
        return {
            "key": dict(key_entry),
            "targetDiscordId": target_id,
            "licenseExpiresAt": expires_iso,
            "durationLabel": key_entry.get("durationLabel"),
        }


def list_license_keys(*, limit: int = 25) -> list[dict]:
    store = load_store()
    keys = list(store.get("licenseKeys", []))
    safe = []
    for item in keys[:limit]:
        copy = dict(item)
        copy.pop("codeHash", None)
        safe.append(copy)
    return safe


def register_site_user(payload: dict) -> dict:
    with _lock:
        store = load_store()
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
        now = _now()

        existing = _find_site_user(store, discord_id)
        if existing:
            existing.update(
                {
                    "username": username,
                    "avatarHash": avatar_hash or existing.get("avatarHash", ""),
                    "licensedStatus": licensed_status,
                    "lastSeen": now,
                    "loginCount": int(existing.get("loginCount") or 0) + 1,
                }
            )
            if active:
                existing["licenseExpiresAt"] = active["licenseExpiresAt"]
                if active.get("licenseKeyId"):
                    existing["licenseKeyId"] = active["licenseKeyId"]
            save_store(store)
            return dict(existing)

        entry = {
            "discordId": discord_id,
            "username": username,
            "avatarHash": avatar_hash,
            "panelRole": "member",
            "licensedStatus": licensed_status,
            "firstSeen": now,
            "lastSeen": now,
            "loginCount": 1,
        }
        store["siteUsers"].insert(0, entry)
        save_store(store)
        return dict(entry)


def get_site_user(discord_id: str) -> dict | None:
    store = load_store()
    user = _find_site_user(store, discord_id)
    return dict(user) if user else None


def list_site_users() -> list[dict]:
    store = load_store()
    return [dict(u) for u in store.get("siteUsers", [])]


def set_site_user_role(target_id: str, role: str) -> dict | None:
    role = str(role).strip().lower()
    if role not in PANEL_ROLES:
        raise ValueError("invalid_role")

    with _lock:
        store = load_store()
        user = _find_site_user(store, target_id)
        if not user:
            now = _now()
            user = {
                "discordId": str(target_id).strip(),
                "username": "Unknown",
                "avatarHash": "",
                "panelRole": role,
                "licensedStatus": "Standard",
                "firstSeen": now,
                "lastSeen": now,
                "loginCount": 0,
                "promotedAt": now,
            }
            store["siteUsers"].insert(0, user)
            save_store(store)
            return dict(user)

        user["panelRole"] = role
        user["promotedAt"] = _now()
        save_store(store)
        return dict(user)


def _activity_for_user(discord_id: str, pins: list, scans: list) -> dict:
    uid = str(discord_id)
    user_pins = [p for p in pins if str(p.get("discordId")) == uid]
    user_scans = [s for s in scans if str(s.get("discordId")) == uid]
    return {
        "pins": len(user_pins),
        "scans": len(user_scans),
    }


def _enrich_site_user(user: dict, pins: list, scans: list, effective_role: str) -> dict:
    activity = _activity_for_user(user.get("discordId", ""), pins, scans)
    return {
        **user,
        "panelRole": effective_role,
        "storedRole": user.get("panelRole", "member"),
        "pins": activity["pins"],
        "scans": activity["scans"],
    }


def register_pin(payload: dict) -> dict:
    with _lock:
        store = load_store()
        pin_code = str(payload.get("pin", "")).strip()
        discord_id = str(payload.get("discordId", "")).strip()
        if not pin_code or not discord_id:
            raise ValueError("pin and discordId required")

        for item in store["pins"]:
            if item.get("pin") == pin_code:
                item.update(
                    {
                        "discordId": discord_id,
                        "playerName": payload.get("playerName") or item.get("playerName") or "—",
                        "game": payload.get("game") or item.get("game") or "FiveM",
                        "id": payload.get("id") or item.get("id"),
                        "date": payload.get("date") or item.get("date") or _now(),
                    }
                )
                save_store(store)
                return item

        entry = {
            "id": payload.get("id") or f"pin_{int(datetime.now().timestamp() * 1000)}",
            "pin": pin_code,
            "discordId": discord_id,
            "playerName": payload.get("playerName") or "—",
            "game": payload.get("game") or "FiveM",
            "status": "pending",
            "result": "Pending",
            "date": payload.get("date") or _now(),
            "scanId": None,
        }
        store["pins"].insert(0, entry)
        save_store(store)
        return entry


def list_pins(discord_id: str) -> list[dict]:
    store = load_store()
    return [p for p in store["pins"] if str(p.get("discordId")) == str(discord_id)]


def delete_pin(pin_id: str, discord_id: str) -> bool:
    with _lock:
        store = load_store()
        before = len(store["pins"])
        store["pins"] = [
            p
            for p in store["pins"]
            if not (str(p.get("id")) == str(pin_id) and str(p.get("discordId")) == str(discord_id))
        ]
        if len(store["pins"]) == before:
            return False
        save_store(store)
        return True


def find_pin_by_code(pin_code: str) -> dict | None:
    store = load_store()
    for item in store["pins"]:
        if str(item.get("pin")) == str(pin_code):
            return item
    return None


def map_scanner_verdict(verdict: str) -> tuple[str, str, str]:
    value = str(verdict or "").upper()
    if value == "CLEAN":
        return "passed", "Clean", "finished"
    if value == "REVIEW NEEDED":
        return "review", "Review", "finished"
    if value == "SUSPICIOUS":
        return "suspicious", "Suspicious", "cheated"
    if value == "CHEATING LIKELY":
        return "failed", "Cheated", "cheated"
    return "review", "Review", "finished"


def submit_scan(payload: dict) -> dict:
    with _lock:
        store = load_store()
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
            "date": payload.get("date") or _now(),
            "playerName": player_name,
            "verdict": verdict,
            "threats": int(payload.get("threats") or 0),
            "warnings": int(payload.get("warnings") or 0),
            "summary": payload.get("summary") or "",
            "reportText": payload.get("reportText") or "",
            "hostname": payload.get("hostname") or "",
            "username": payload.get("username") or "",
        }
        store["scans"].insert(0, scan)

        for idx, item in enumerate(store["pins"]):
            if str(item.get("pin")) == pin_code:
                store["pins"][idx] = {
                    **item,
                    "status": pin_status,
                    "result": result_label,
                    "scanId": scan_id,
                }
                break

        save_store(store)
        return scan


def list_scans(discord_id: str) -> list[dict]:
    store = load_store()
    return [s for s in store["scans"] if str(s.get("discordId")) == str(discord_id)]


def _verdict_totals(scans: list) -> dict:
    verdicts = {"passed": 0, "review": 0, "suspicious": 0, "failed": 0}
    for scan in scans:
        key = str(scan.get("verdict", "review"))
        verdicts[key] = verdicts.get(key, 0) + 1
    return verdicts


def build_role_dashboard(
    *,
    resolve_effective_role,
    include_users: bool = True,
    actor_role: str = "owner",
) -> dict:
    store = load_store()
    pins = list(store.get("pins", []))
    scans = list(store.get("scans", []))
    site_users = list(store.get("siteUsers", []))

    enriched_users = []
    role_counts = {"owner": 0, "admin": 0, "staff": 0, "member": 0}
    for user in site_users:
        effective = resolve_effective_role(str(user.get("discordId", "")))
        role_counts[effective] = role_counts.get(effective, 0) + 1
        if include_users:
            enriched_users.append(_enrich_site_user(user, pins, scans, effective))

    enriched_users.sort(
        key=lambda u: (ROLE_RANK.get(u.get("panelRole", "member"), 0), u.get("lastSeen", "")),
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
        "verdicts": _verdict_totals(scans),
        "siteUsers": enriched_users,
        "recentPins": pins[:15],
        "recentScans": scans[:15],
    }
