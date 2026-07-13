from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timezone

PANEL_ROLES = {"member", "staff", "admin", "owner"}
ROLE_RANK = {"member": 1, "staff": 2, "admin": 3, "owner": 4}
KEY_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def parse_iso(value: str) -> datetime | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    try:
        if raw.endswith("Z"):
            raw = raw[:-1] + "+00:00"
        return datetime.fromisoformat(raw)
    except ValueError:
        return None


def hash_license_code(code: str) -> str:
    normalized = str(code or "").strip().upper().replace(" ", "")
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def generate_user_token() -> str:
    raw = secrets.token_hex(4).upper()
    return f"DX-{raw[:4]}-{raw[4:8]}"


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


def verdict_totals(scans: list) -> dict:
    verdicts = {"passed": 0, "review": 0, "suspicious": 0, "failed": 0}
    for scan in scans:
        key = str(scan.get("verdict", "review"))
        verdicts[key] = verdicts.get(key, 0) + 1
    return verdicts


def activity_for_user(discord_id: str, pins: list, scans: list) -> dict:
    uid = str(discord_id)
    user_pins = [p for p in pins if str(p.get("discordId")) == uid]
    user_scans = [s for s in scans if str(s.get("discordId")) == uid]
    return {"pins": len(user_pins), "scans": len(user_scans)}


def enrich_site_user(user: dict, pins: list, scans: list, effective_role: str) -> dict:
    activity = activity_for_user(user.get("discordId", ""), pins, scans)
    first_seen = user.get("firstSeen") or user.get("joinedAt")
    return {
        **user,
        "panelRole": effective_role,
        "storedRole": user.get("panelRole", "member"),
        "firstSeen": first_seen,
        "joinedAt": first_seen,
        "pins": activity["pins"],
        "scans": activity["scans"],
    }
