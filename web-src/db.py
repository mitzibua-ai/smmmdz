from __future__ import annotations

import os
import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class User:
    discord_id: str
    username: str
    avatar_url: str | None
    created_at: int
    last_login: int
    access_token: str | None = None
    refresh_token: str | None = None
    expires_at: int | None = None


def _db_path() -> Path:
    p = os.getenv("DB_PATH")
    if p:
        return Path(p)
    return Path(__file__).resolve().parent / "data" / "app.db"


def connect() -> sqlite3.Connection:
    path = _db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(str(path))
    con.row_factory = sqlite3.Row
    return con


def init_db() -> None:
    with connect() as con:
        con.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
              discord_id TEXT PRIMARY KEY,
              username TEXT NOT NULL,
              avatar_url TEXT,
              created_at INTEGER NOT NULL,
              last_login INTEGER NOT NULL,
              access_token TEXT,
              refresh_token TEXT,
              expires_at INTEGER
            )
            """
        )
        existing = con.execute("PRAGMA table_info(users)").fetchall()
        columns = {row[1] for row in existing}
        if "access_token" not in columns:
            con.execute("ALTER TABLE users ADD COLUMN access_token TEXT")
        if "refresh_token" not in columns:
            con.execute("ALTER TABLE users ADD COLUMN refresh_token TEXT")
        if "expires_at" not in columns:
            con.execute("ALTER TABLE users ADD COLUMN expires_at INTEGER")
        con.commit()


def upsert_user(
    *,
    discord_id: str,
    username: str,
    avatar_url: str | None,
    access_token: str | None = None,
    refresh_token: str | None = None,
    expires_at: int | None = None,
) -> User:
    now = int(time.time())
    with connect() as con:
        row = con.execute(
            "SELECT discord_id, username, avatar_url, created_at, last_login, access_token, refresh_token, expires_at FROM users WHERE discord_id = ?",
            (discord_id,),
        ).fetchone()
        if row is None:
            con.execute(
                "INSERT INTO users(discord_id, username, avatar_url, created_at, last_login, access_token, refresh_token, expires_at) VALUES(?,?,?,?,?,?,?,?)",
                (discord_id, username, avatar_url, now, now, access_token, refresh_token, expires_at),
            )
            con.commit()
            return User(
                discord_id=discord_id,
                username=username,
                avatar_url=avatar_url,
                created_at=now,
                last_login=now,
                access_token=access_token,
                refresh_token=refresh_token,
                expires_at=expires_at,
            )

        current_access_token = access_token if access_token is not None else row["access_token"]
        current_refresh_token = refresh_token if refresh_token is not None else row["refresh_token"]
        current_expires_at = expires_at if expires_at is not None else row["expires_at"]

        con.execute(
            "UPDATE users SET username = ?, avatar_url = ?, last_login = ?, access_token = ?, refresh_token = ?, expires_at = ? WHERE discord_id = ?",
            (username, avatar_url, now, current_access_token, current_refresh_token, current_expires_at, discord_id),
        )
        con.commit()
        return User(
            discord_id=row["discord_id"],
            username=username,
            avatar_url=avatar_url,
            created_at=int(row["created_at"]),
            last_login=now,
            access_token=current_access_token,
            refresh_token=current_refresh_token,
            expires_at=current_expires_at,
        )


def get_user(discord_id: str) -> User | None:
    with connect() as con:
        row = con.execute(
            "SELECT discord_id, username, avatar_url, created_at, last_login, access_token, refresh_token, expires_at FROM users WHERE discord_id = ?",
            (discord_id,),
        ).fetchone()
        if row is None:
            return None
        return User(
            discord_id=row["discord_id"],
            username=row["username"],
            avatar_url=row["avatar_url"],
            created_at=int(row["created_at"]),
            last_login=int(row["last_login"]),
            access_token=row["access_token"],
            refresh_token=row["refresh_token"],
            expires_at=int(row["expires_at"]) if row["expires_at"] is not None else None,
        )
