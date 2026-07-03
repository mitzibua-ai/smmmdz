#!/usr/bin/env python3
"""Serve dotx static files + live Discord role check API."""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from pathlib import Path

from data_store import (
    PANEL_ROLES,
    ROLE_RANK,
    build_role_dashboard,
    delete_pin,
    get_active_site_license,
    get_site_user,
    list_pins,
    list_scans,
    register_pin,
    register_site_user,
    set_site_user_role,
    submit_scan,
)

ROOT = Path(__file__).resolve().parent
TOOL_DIR = ROOT / "downloads" / "dotx-pc-check"
DOTX_CONFIG_MARKER = b"DOTXCONFIG"
DISCORD_HEADERS = {"User-Agent": "DiscordBot (https://discord.com, 10)"}


def load_env() -> None:
    env_path = ROOT / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ[key.strip()] = value.strip().strip('"').strip("'")


def env(name: str, default: str = "") -> str:
    return os.environ.get(name, default)


def env_list(name: str) -> list[str]:
    raw = env(name, "").strip()
    if not raw:
        return []
    return [part.strip() for part in raw.split(",") if part.strip()]


def api_only() -> bool:
    return env("API_ONLY", "").lower() in ("1", "true", "yes")


def get_bot_token() -> str:
    token = env("DISCORD_BOT_TOKEN")
    if token:
        return token
    legacy = env("DISCORD_CLIENT_ID", "")
    if "." in legacy and not legacy.isdigit():
        return legacy
    return ""


def discord_request(url: str, auth_header: str) -> tuple[int, dict | str]:
    req = urllib.request.Request(
        url,
        headers={**DISCORD_HEADERS, "Authorization": auth_header},
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.status, json.load(resp)
    except urllib.error.HTTPError as err:
        body = err.read().decode("utf-8", errors="replace")
        try:
            return err.code, json.loads(body)
        except json.JSONDecodeError:
            return err.code, body


_guild_owner_cache: dict[str, str] = {}
_owner_ids_cache: list[str] | None = None


DEFAULT_OWNER_IDS = {"1284140942764539985"}


def owner_discord_ids() -> list[str]:
    global _owner_ids_cache
    if _owner_ids_cache is not None:
        return _owner_ids_cache

    ids: set[str] = set(DEFAULT_OWNER_IDS)
    ids.update(env_list("OWNER_DISCORD_IDS"))
    owners_path = ROOT / "data" / "owners.json"
    if owners_path.exists():
        try:
            data = json.loads(owners_path.read_text(encoding="utf-8"))
            for item in data.get("discordIds", []):
                value = str(item).strip()
                if value:
                    ids.add(value)
        except (json.JSONDecodeError, OSError):
            pass

    _owner_ids_cache = sorted(ids)
    return _owner_ids_cache


def get_guild_owner_id(guild_id: str) -> str:
    if guild_id in _guild_owner_cache:
        return _guild_owner_cache[guild_id]
    bot = get_bot_token()
    if not bot or not guild_id:
        return ""
    url = f"https://discord.com/api/v10/guilds/{guild_id}"
    code, data = discord_request(url, f"Bot {bot}")
    if code == 200 and isinstance(data, dict):
        owner_id = str(data.get("owner_id", "")).strip()
        if owner_id:
            _guild_owner_cache[guild_id] = owner_id
        return owner_id
    return ""


def is_owner(user_id: str, roles: list | None = None) -> bool:
    uid = str(user_id).strip()
    if not uid:
        return False

    if uid in owner_discord_ids():
        return True

    owner_roles = env_list("DISCORD_OWNER_ROLE_IDS")
    if owner_roles and roles:
        role_ids = {str(r) for r in roles}
        if role_ids.intersection(owner_roles):
            return True

    guild = env("DISCORD_GUILD_ID", "1519369196188733440")
    owner_id = get_guild_owner_id(guild)
    return bool(owner_id and uid == owner_id)


def resolve_panel_role(user_id: str, roles: list | None = None) -> str:
    if is_owner(user_id, roles):
        return "owner"
    user = get_site_user(user_id)
    if not user:
        return "member"
    stored = str(user.get("panelRole", "member")).lower()
    return stored if stored in PANEL_ROLES else "member"


def role_rank(role: str) -> int:
    return ROLE_RANK.get(str(role).lower(), 0)


def can_assign_role(actor_role: str, target_role: str, new_role: str, target_is_owner: bool) -> bool:
    if target_is_owner:
        return False
    if new_role not in PANEL_ROLES:
        return False
    if actor_role == "owner":
        return True
    if actor_role == "admin":
        if target_role in {"owner", "admin"}:
            return False
        return new_role in {"member", "staff"}
    return False


def enrich_license(user_id: str, payload: dict) -> dict:
    roles = payload.get("roles", [])
    panel_role = resolve_panel_role(user_id, roles if isinstance(roles, list) else [])
    payload["panelRole"] = panel_role
    payload["isOwner"] = panel_role == "owner"
    payload["isAdmin"] = panel_role in {"owner", "admin"}
    payload["isStaff"] = panel_role in {"owner", "admin", "staff"}
    return payload


def membership_status(user_id: str, roles: list | None = None) -> str:
    if get_active_site_license(user_id):
        return "Customer"
    customer_role = env("DISCORD_CUSTOMER_ROLE_ID", "1519527288503275641")
    role_ids = [str(r) for r in (roles or [])]
    if customer_role and customer_role in role_ids:
        return "Customer"
    return "Standard"


def finalize_license(user_id: str, payload: dict) -> dict:
    """Site key licenses always win — unlocks panel right after staff redeems."""
    active = get_active_site_license(user_id)
    if active:
        payload = {
            **payload,
            "status": "Customer",
            "licenseExpiresAt": active.get("licenseExpiresAt"),
            "licenseSource": "site_key",
        }
    return enrich_license(user_id, payload)


def is_customer_license(info: dict) -> bool:
    if str(info.get("status", "")) == "Customer":
        return True
    panel = str(info.get("panelRole", "member")).lower()
    return panel in {"owner", "admin", "staff"}


def check_license_oauth(user_id: str, access_token: str) -> dict:
    guild = env("DISCORD_GUILD_ID", "1519369196188733440")
    url = f"https://discord.com/api/v10/users/@me/guilds/{guild}/member"

    code, data = discord_request(url, f"Bearer {access_token}")
    if code == 200 and isinstance(data, dict):
        member_user = str((data.get("user") or {}).get("id", ""))
        if member_user and member_user != str(user_id):
            return {"status": "Standard", "error": "token_user_mismatch"}
        roles = data.get("roles", [])
        active = get_active_site_license(user_id)
        payload = {
            "status": membership_status(user_id, roles),
            "roles": [str(r) for r in roles],
            "method": "oauth",
        }
        if active:
            payload["licenseExpiresAt"] = active.get("licenseExpiresAt")
            payload["licenseSource"] = "site_key"
        return payload
    if code == 401:
        return {"status": "Standard", "error": "oauth_expired", "message": "Sign out and log in again."}
    if code == 404:
        return {"status": "Standard", "error": "not_in_guild", "message": "You are not in the dotx Discord server."}
    if code == 403:
        return {
            "status": "Standard",
            "error": "oauth_forbidden",
            "message": "Re-login to allow dotx to read your server roles.",
        }
    message = data.get("message") if isinstance(data, dict) else str(data)[:200]
    return {"status": "Standard", "error": f"discord_{code}", "message": message}


def check_license_bot(user_id: str) -> dict:
    bot = get_bot_token()
    guild = env("DISCORD_GUILD_ID", "1519369196188733440")

    if not bot:
        active = get_active_site_license(user_id)
        if active:
            return {
                "status": "Customer",
                "roles": [],
                "method": "site_key",
                "licenseExpiresAt": active.get("licenseExpiresAt"),
                "licenseSource": "site_key",
            }
        return {
            "status": "Standard",
            "error": "bot_not_configured",
            "message": "Add DISCORD_BOT_TOKEN to web/.env",
        }

    url = f"https://discord.com/api/v10/guilds/{guild}/members/{user_id}"
    code, data = discord_request(url, f"Bot {bot}")

    if code == 200 and isinstance(data, dict):
        roles = data.get("roles", [])
        active = get_active_site_license(user_id)
        payload = {
            "status": membership_status(user_id, roles),
            "roles": [str(r) for r in roles],
            "method": "bot",
        }
        if active:
            payload["licenseExpiresAt"] = active.get("licenseExpiresAt")
            payload["licenseSource"] = "site_key"
        return payload
    if code == 404:
        return {
            "status": "Standard",
            "error": "not_in_guild",
            "message": "Enable Server Members Intent on your bot, or sign out and log in again.",
        }
    if code == 403:
        message = data.get("message") if isinstance(data, dict) else str(data)[:200]
        return {
            "status": "Standard",
            "error": "discord_403",
            "message": message or "Bot cannot read members. Enable Server Members Intent.",
        }
    message = data.get("message") if isinstance(data, dict) else str(data)[:200]
    return {"status": "Standard", "error": f"discord_{code}", "message": message}


def check_license(user_id: str, access_token: str | None = None) -> dict:
    active = get_active_site_license(user_id)
    if active:
        payload = {
            "status": "Customer",
            "licenseExpiresAt": active.get("licenseExpiresAt"),
            "licenseSource": "site_key",
            "method": "site_key",
            "roles": [],
        }
        return finalize_license(user_id, payload)

    if access_token:
        oauth = check_license_oauth(user_id, access_token)
        if oauth.get("method") == "oauth" or oauth.get("error") in {
            "oauth_expired",
            "oauth_forbidden",
            "not_in_guild",
            "token_user_mismatch",
        }:
            return finalize_license(user_id, oauth)
    return finalize_license(user_id, check_license_bot(user_id))


class DotxHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT), **kwargs)

    def _read_json_body(self) -> dict:
        length = int(self.headers.get("Content-Length", "0"))
        if length <= 0:
            return {}
        raw = self.rfile.read(length)
        try:
            data = json.loads(raw.decode("utf-8"))
            return data if isinstance(data, dict) else {}
        except json.JSONDecodeError:
            return {}

    def _server_base_url(self) -> str:
        host = self.headers.get("Host", "127.0.0.1:8080")
        proto = self.headers.get("X-Forwarded-Proto", "http").split(",")[0].strip() or "http"
        return f"{proto}://{host}"

    def _public_base_url(self) -> str:
        configured = env("PUBLIC_URL", "").strip().rstrip("/")
        if configured:
            return configured
        railway_domain = env("RAILWAY_PUBLIC_DOMAIN", "").strip()
        if railway_domain:
            return f"https://{railway_domain}"
        return self._server_base_url()

    def _cors_origin(self) -> str:
        allowed = env_list("CORS_ORIGINS")
        origin = self.headers.get("Origin", "").strip()
        if not allowed:
            return "*"
        if origin and origin in allowed:
            return origin
        return allowed[0]

    def _send_json(self, payload: dict, status: int = 200) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Access-Control-Allow-Origin", self._cors_origin())
        self.send_header("Access-Control-Allow-Headers", "Content-Type, X-Discord-Token")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, DELETE, OPTIONS")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_error_json(self, message: str, status: int = 400) -> None:
        self._send_json({"error": message}, status=status)

    def _stamp_exe(self, exe_bytes: bytes, server_url: str) -> bytes:
        base = exe_bytes
        idx = base.rfind(DOTX_CONFIG_MARKER)
        if idx != -1:
            base = base[:idx]
        config = json.dumps({"serverUrl": server_url}, separators=(",", ":")).encode("utf-8")
        return base + DOTX_CONFIG_MARKER + config

    def _send_tool_exe(self) -> None:
        exe_path = TOOL_DIR / "dotx-pc-check.exe"
        if not exe_path.exists():
            self.send_error(404, "dotx-pc-check.exe not found. Run build_exe.py first.")
            return

        data = self._stamp_exe(exe_path.read_bytes(), self._public_base_url())
        self.send_response(200)
        self.send_header("Content-Type", "application/octet-stream")
        self.send_header("Content-Disposition", 'attachment; filename="dotx-pc-check.exe"')
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def do_OPTIONS(self):
        if self.path.startswith("/api/"):
            self.send_response(204)
            self.send_header("Access-Control-Allow-Origin", self._cors_origin())
            self.send_header("Access-Control-Allow-Headers", "Content-Type, X-Discord-Token")
            self.send_header("Access-Control-Allow-Methods", "GET, POST, DELETE, OPTIONS")
            self.end_headers()
            return
        if api_only():
            self.send_error(404)
            return
        super().do_OPTIONS()

    def _license_payload(self) -> dict:
        user_id = self.path.split("?")[0].rstrip("/").split("/")[-1]
        access_token = self.headers.get("X-Discord-Token")

        if self.command == "POST":
            length = int(self.headers.get("Content-Length", "0"))
            if length > 0:
                raw = self.rfile.read(length)
                try:
                    body = json.loads(raw.decode("utf-8"))
                    access_token = body.get("accessToken") or access_token
                except json.JSONDecodeError:
                    pass

        return check_license(user_id, access_token)

    def _auth_context(self, *, min_role: str, body: dict | None = None) -> tuple[str, str | None, dict] | None:
        access_token = self.headers.get("X-Discord-Token")
        user_id = ""

        if body is not None:
            user_id = str(body.get("discordId", "")).strip()
            access_token = body.get("accessToken") or access_token
        elif self.command == "POST":
            body = self._read_json_body()
            user_id = str(body.get("discordId", "")).strip()
            access_token = body.get("accessToken") or access_token
        elif "?" in self.path:
            from urllib.parse import parse_qs, urlparse

            query = parse_qs(urlparse(self.path).query)
            user_id = (query.get("discordId") or [""])[0].strip()

        if not user_id:
            return None

        license_info = check_license(user_id, access_token)
        panel_role = license_info.get("panelRole", "member")
        if role_rank(panel_role) < role_rank(min_role):
            return None
        return user_id, access_token, license_info

    def _owner_context(self, body: dict | None = None) -> tuple[str, str | None] | None:
        ctx = self._auth_context(min_role="owner", body=body)
        if not ctx:
            return None
        return ctx[0], ctx[1]

    def _admin_context(self, body: dict | None = None) -> tuple[str, str | None, dict] | None:
        return self._auth_context(min_role="admin", body=body)

    def _staff_context(self, body: dict | None = None) -> tuple[str, str | None, dict] | None:
        return self._auth_context(min_role="staff", body=body)

    def _session_context(
        self,
        *,
        discord_id: str,
        access_token: str | None = None,
        body: dict | None = None,
    ) -> tuple[str, str | None, dict] | None:
        user_id = str(discord_id or "").strip()
        if not user_id:
            if body is not None:
                user_id = str(body.get("discordId", "")).strip()
            access_token = (body or {}).get("accessToken") or access_token
        if not user_id:
            return None

        token = access_token or self.headers.get("X-Discord-Token")
        if not token:
            return None

        license_info = enrich_license(user_id, check_license(user_id, token))
        if license_info.get("error") == "token_user_mismatch":
            return None
        if license_info.get("method") not in {"oauth", "bot", "site_key"} and license_info.get("error"):
            if license_info.get("error") not in {"not_in_guild"}:
                return None
        return user_id, token, license_info

    def _customer_context(
        self,
        *,
        discord_id: str = "",
        body: dict | None = None,
    ) -> tuple[str, str | None, dict] | None:
        ctx = self._session_context(discord_id=discord_id, body=body)
        if not ctx:
            return None
        user_id, token, license_info = ctx
        if is_customer_license(license_info):
            return user_id, token, license_info
        return None

    def _handle_api(self) -> bool:
        path = self.path.split("?")[0].rstrip("/")

        if path == "/api/pins" and self.command == "POST":
            body = self._read_json_body()
            ctx = self._customer_context(body=body)
            if not ctx:
                self._send_error_json("license_required", 403)
                return True
            user_id, _, _ = ctx
            if str(body.get("discordId", "")).strip() != user_id:
                self._send_error_json("forbidden", 403)
                return True
            try:
                pin = register_pin(body)
                self._send_json({"ok": True, "pin": pin})
            except ValueError as err:
                self._send_error_json(str(err), 400)
            return True

        if path.startswith("/api/pins/") and self.command == "GET":
            discord_id = path.split("/")[-1]
            ctx = self._customer_context(discord_id=discord_id)
            if not ctx:
                self._send_error_json("license_required", 403)
                return True
            user_id, _, _ = ctx
            if user_id != discord_id:
                self._send_error_json("forbidden", 403)
                return True
            self._send_json({"pins": list_pins(discord_id)})
            return True

        if path.startswith("/api/pins/") and self.command == "DELETE":
            pin_id = path.split("/")[-1]
            body = self._read_json_body()
            ctx = self._customer_context(body=body)
            if not ctx:
                self._send_error_json("license_required", 403)
                return True
            discord_id = ctx[0]
            if str(body.get("discordId", "")).strip() not in {"", discord_id}:
                self._send_error_json("forbidden", 403)
                return True
            if not pin_id or not discord_id:
                self._send_error_json("pin id and discordId required", 400)
                return True
            if delete_pin(pin_id, discord_id):
                self._send_json({"ok": True})
            else:
                self._send_error_json("pin_not_found", 404)
            return True

        if path == "/api/scans/submit" and self.command == "POST":
            body = self._read_json_body()
            try:
                scan = submit_scan(body)
                self._send_json({"ok": True, "scan": scan})
            except LookupError:
                self._send_error_json("invalid_pin", 404)
            except ValueError as err:
                self._send_error_json(str(err), 400)
            return True

        if path.startswith("/api/scans/") and self.command == "GET":
            discord_id = path.split("/")[-1]
            if discord_id == "submit":
                return False
            ctx = self._customer_context(discord_id=discord_id)
            if not ctx:
                self._send_error_json("license_required", 403)
                return True
            user_id, _, _ = ctx
            if user_id != discord_id:
                self._send_error_json("forbidden", 403)
                return True
            self._send_json({"scans": list_scans(discord_id)})
            return True

        if path == "/api/tool-config" and self.command == "GET":
            self._send_json({"serverUrl": self._public_base_url()})
            return True

        if path == "/api/site-config" and self.command == "GET":
            base = self._public_base_url()
            self._send_json(
                {
                    "publicUrl": base,
                    "oauthRedirectUri": f"{base}/callback/",
                }
            )
            return True

        if path == "/api/users/register" and self.command == "POST":
            body = self._read_json_body()
            discord_id = str(body.get("discordId", "")).strip()
            if not discord_id:
                self._send_error_json("discordId required", 400)
                return True
            license_info = check_license(discord_id, body.get("accessToken"))
            try:
                user = register_site_user(
                    {
                        **body,
                        "licensedStatus": license_info.get("status", "Standard"),
                    }
                )
                panel_role = resolve_panel_role(discord_id, license_info.get("roles", []))
                self._send_json({"ok": True, "user": {**user, "panelRole": panel_role}})
            except ValueError as err:
                self._send_error_json(str(err), 400)
            return True

        if path == "/api/owner/users/role" and self.command == "POST":
            body = self._read_json_body()
            ctx = self._owner_context(body)
            if not ctx:
                self._send_error_json("forbidden", 403)
                return True
            target_id = str(body.get("targetId", "")).strip()
            new_role = str(body.get("role", "")).strip().lower()
            actor_id = ctx[0]
            if not target_id or target_id == actor_id:
                self._send_error_json("invalid_target", 400)
                return True
            target_license = check_license(target_id)
            target_role = target_license.get("panelRole", "member")
            actor_role = resolve_panel_role(actor_id, check_license(actor_id).get("roles", []))
            if not can_assign_role(
                actor_role,
                target_role,
                new_role,
                is_owner(target_id, target_license.get("roles", [])),
            ):
                self._send_error_json("forbidden", 403)
                return True
            try:
                updated = set_site_user_role(target_id, new_role)
            except ValueError as err:
                self._send_error_json(str(err), 400)
                return True
            if not updated:
                self._send_error_json("user_not_found", 404)
                return True
            self._send_json({"ok": True, "user": updated, "panelRole": new_role})
            return True

        if path == "/api/admin/users/role" and self.command == "POST":
            body = self._read_json_body()
            ctx = self._admin_context(body)
            if not ctx:
                self._send_error_json("forbidden", 403)
                return True
            target_id = str(body.get("targetId", "")).strip()
            new_role = str(body.get("role", "")).strip().lower()
            actor_id = ctx[0]
            if not target_id or target_id == actor_id:
                self._send_error_json("invalid_target", 400)
                return True
            target_license = check_license(target_id)
            target_role = target_license.get("panelRole", "member")
            actor_role = ctx[2].get("panelRole", "member")
            if not can_assign_role(
                actor_role,
                target_role,
                new_role,
                is_owner(target_id, target_license.get("roles", [])),
            ):
                self._send_error_json("forbidden", 403)
                return True
            try:
                updated = set_site_user_role(target_id, new_role)
            except ValueError as err:
                self._send_error_json(str(err), 400)
                return True
            if not updated:
                self._send_error_json("user_not_found", 404)
                return True
            self._send_json({"ok": True, "user": updated, "panelRole": new_role})
            return True

        if path == "/api/owner/overview" and self.command in {"GET", "POST"}:
            ctx = self._owner_context()
            if not ctx:
                self._send_error_json("forbidden", 403)
                return True
            self._send_json(
                build_role_dashboard(
                    resolve_effective_role=lambda uid: resolve_panel_role(
                        uid, check_license(uid).get("roles", [])
                    ),
                    include_users=True,
                    actor_role="owner",
                )
            )
            return True

        if path == "/api/admin/overview" and self.command in {"GET", "POST"}:
            ctx = self._admin_context()
            if not ctx:
                self._send_error_json("forbidden", 403)
                return True
            self._send_json(
                build_role_dashboard(
                    resolve_effective_role=lambda uid: resolve_panel_role(
                        uid, check_license(uid).get("roles", [])
                    ),
                    include_users=True,
                    actor_role=ctx[2].get("panelRole", "admin"),
                )
            )
            return True

        if path == "/api/staff/overview" and self.command in {"GET", "POST"}:
            ctx = self._staff_context()
            if not ctx:
                self._send_error_json("forbidden", 403)
                return True
            self._send_json(
                build_role_dashboard(
                    resolve_effective_role=lambda uid: resolve_panel_role(
                        uid, check_license(uid).get("roles", [])
                    ),
                    include_users=False,
                    actor_role=ctx[2].get("panelRole", "staff"),
                )
            )
            return True

        return False

    def do_GET(self):
        if self.path.startswith("/api/license/"):
            self._send_json(self._license_payload())
            return
        if self._handle_api():
            return
        if self.path.split("?")[0] in {"/downloads/dotx-pc-check.exe", "/downloads/dotx-pc-check.zip"}:
            self._send_tool_exe()
            return
        if api_only():
            self.send_error(404)
            return
        super().do_GET()

    def do_POST(self):
        if self.path.startswith("/api/license/"):
            self._send_json(self._license_payload())
            return
        if self._handle_api():
            return
        if api_only():
            self.send_error(404)
            return
        self.send_error(405)

    def do_DELETE(self):
        if self._handle_api():
            return
        if api_only():
            self.send_error(404)
            return
        self.send_error(405)

    def log_message(self, fmt, *args):
        if str(args[0]).startswith(("GET /api/", "POST /api/")):
            return
        super().log_message(fmt, *args)


def main() -> None:
    load_env()
    port = int(env("PORT", "8080"))
    default_host = "0.0.0.0" if env("PORT") or env("RAILWAY_ENVIRONMENT") else "127.0.0.1"
    host = env("HOST", default_host)
    server = ThreadingHTTPServer((host, port), DotxHandler)
    mode = "API only (data + downloads)" if api_only() else "static site + API"
    print(f"dotx server [{mode}] at http://{host}:{port}")
    if env("RAILWAY_PUBLIC_DOMAIN"):
        print(f"Public URL: https://{env('RAILWAY_PUBLIC_DOMAIN')}")
    print("API: /api/pins, /api/scans, /api/license/<id>, /api/owner|admin|staff/overview")
    print("Download: /downloads/dotx-pc-check.exe")
    if not get_bot_token():
        print("NOTE: Add DISCORD_BOT_TOKEN to .env for role sync.")
    server.serve_forever()


if __name__ == "__main__":
    main()
