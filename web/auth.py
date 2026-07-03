from __future__ import annotations

import os
import secrets
import time
import urllib.parse

import requests
from itsdangerous import BadSignature, URLSafeSerializer


DISCORD_API = "https://discord.com/api"


def _env(name: str) -> str:
    v = os.getenv(name)
    if not v:
        raise RuntimeError(f"Missing required env var: {name}")
    return v


def discord_authorize_url(*, state: str) -> str:
    params = {
        "client_id": _env("DISCORD_CLIENT_ID"),
        "redirect_uri": _env("DISCORD_REDIRECT_URI"),
        "response_type": "code",
        "scope": "identify offline_access",
        "state": state,
        "prompt": "consent",
    }
    return f"{DISCORD_API}/oauth2/authorize?{urllib.parse.urlencode(params)}"


def exchange_code_for_token(*, code: str) -> dict:
    data = {
        "client_id": _env("DISCORD_CLIENT_ID"),
        "client_secret": _env("DISCORD_CLIENT_SECRET"),
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": _env("DISCORD_REDIRECT_URI"),
    }
    r = requests.post(f"{DISCORD_API}/oauth2/token", data=data, timeout=15)
    r.raise_for_status()
    payload = r.json()
    token = payload.get("access_token")
    if not token:
        raise RuntimeError("Discord token exchange failed (no access_token).")
    return payload


def refresh_discord_token(*, refresh_token: str) -> dict:
    data = {
        "client_id": _env("DISCORD_CLIENT_ID"),
        "client_secret": _env("DISCORD_CLIENT_SECRET"),
        "grant_type": "refresh_token",
        "refresh_token": refresh_token,
    }
    r = requests.post(f"{DISCORD_API}/oauth2/token", data=data, timeout=15)
    r.raise_for_status()
    payload = r.json()
    token = payload.get("access_token")
    if not token:
        raise RuntimeError("Discord refresh failed (no access_token).")
    return payload


def fetch_discord_user(*, access_token: str) -> dict:
    r = requests.get(
        f"{DISCORD_API}/users/@me",
        headers={"Authorization": f"Bearer {access_token}"},
        timeout=15,
    )
    r.raise_for_status()
    return r.json()


def avatar_url_for(user: dict) -> str | None:
    avatar = user.get("avatar")
    user_id = user.get("id")
    if not avatar or not user_id:
        return None
    ext = "gif" if avatar.startswith("a_") else "png"
    return f"https://cdn.discordapp.com/avatars/{user_id}/{avatar}.{ext}?size=128"


def new_state() -> str:
    return secrets.token_urlsafe(24)


def _serializer() -> URLSafeSerializer:
    secret = _env("SESSION_SECRET")
    return URLSafeSerializer(secret_key=secret, salt="discord-session-v1")


def sign_session(*, discord_id: str) -> str:
    # We intentionally only store discord_id. “Ownership transfer” is impossible
    # because the only way to obtain this session again is logging into the same Discord account.
    now = int(time.time())
    return _serializer().dumps({"v": 1, "discord_id": str(discord_id), "iat": now})


def unsign_session(value: str) -> str | None:
    try:
        data = _serializer().loads(value)
    except BadSignature:
        return None
    if not isinstance(data, dict):
        return None
    if data.get("v") != 1:
        return None
    discord_id = data.get("discord_id")
    if not discord_id:
        return None
    return str(discord_id)
