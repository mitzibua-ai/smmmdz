from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, Request, Response
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from auth import (
    avatar_url_for,
    discord_authorize_url,
    exchange_code_for_token,
    fetch_discord_user,
    new_state,
    sign_session,
    unsign_session,
)
from db import get_user, init_db, upsert_user


ROOT = Path(__file__).resolve().parent
load_dotenv(ROOT / ".env")
templates = Jinja2Templates(directory=str(ROOT / "templates"))


def _env(name: str, default: str | None = None) -> str:
    v = os.getenv(name, default)
    if v is None or v == "":
        raise RuntimeError(f"Missing required env var: {name}")
    return v


def site_name() -> str:
    return os.getenv("SITE_NAME", "async.ac")


app = FastAPI(title=f"{site_name()} dashboard")
app.mount("/static", StaticFiles(directory=str(ROOT / "static")), name="static")


@app.on_event("startup")
def _startup() -> None:
    init_db()


def current_user(request: Request):
    cookie = request.cookies.get("session")
    if not cookie:
        return None
    discord_id = unsign_session(cookie)
    if not discord_id:
        return None
    return get_user(discord_id)


def require_user(request: Request):
    user = current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=302)
    return user


@app.get("/", response_class=HTMLResponse)
def root(request: Request):
    if current_user(request):
        return RedirectResponse(url="/dashboard", status_code=302)
    return RedirectResponse(url="/login", status_code=302)


@app.get("/login", response_class=HTMLResponse)
def login(request: Request):
    user = current_user(request)
    if user:
        return RedirectResponse(url="/dashboard", status_code=302)
    return templates.TemplateResponse(
        "login.html",
        {"request": request, "site_name": site_name()},
    )


@app.get("/logout")
def logout(response: Response):
    r = RedirectResponse(url="/login", status_code=302)
    r.delete_cookie("session", path="/")
    return r


@app.get("/auth/discord")
def auth_discord(request: Request):
    state = new_state()
    r = RedirectResponse(url=discord_authorize_url(state=state), status_code=302)
    r.set_cookie(
        "oauth_state",
        state,
        httponly=True,
        secure=False,
        samesite="lax",
        path="/",
        max_age=10 * 60,
    )
    return r


@app.get("/auth/discord/callback")
def auth_discord_callback(request: Request, code: str | None = None, state: str | None = None):
    expected_state = request.cookies.get("oauth_state")
    if not code or not state or not expected_state or state != expected_state:
        return RedirectResponse(url="/login?error=oauth_state", status_code=302)

    token = exchange_code_for_token(code=code)
    du = fetch_discord_user(access_token=token)

    discord_id = str(du.get("id") or "")
    if not discord_id:
        return RedirectResponse(url="/login?error=discord_user", status_code=302)

    username = du.get("global_name") or du.get("username") or f"discord:{discord_id}"
    avatar_url = avatar_url_for(du)
    upsert_user(discord_id=discord_id, username=username, avatar_url=avatar_url)

    r = RedirectResponse(url="/dashboard", status_code=302)
    r.delete_cookie("oauth_state", path="/")
    r.set_cookie(
        "session",
        sign_session(discord_id=discord_id),
        httponly=True,
        secure=False,
        samesite="lax",
        path="/",
        max_age=60 * 60 * 24 * 365 * 5,  # 5 years (effectively permanent)
    )
    return r


@app.get("/dashboard", response_class=HTMLResponse)
def dashboard(request: Request):
    user = require_user(request)
    if not hasattr(user, "discord_id"):
        return user

    # Placeholder stats; wire these to real scan data later.
    stats = {
        "total_scans": 0,
        "detections": 0,
        "flagged": 0,
        "clean_rate": "0%",
    }
    verdicts = {"clean": 0, "suspicious": 0, "cheating": 0}
    recent_scans = []

    return templates.TemplateResponse(
        "dashboard.html",
        {
            "request": request,
            "site_name": site_name(),
            "user": user,
            "stats": stats,
            "verdicts": verdicts,
            "recent_scans": recent_scans,
        },
    )

