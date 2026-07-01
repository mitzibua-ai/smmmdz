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
              last_login INTEGER NOT NULL
            )
            """
        )
        con.commit()


def upsert_user(*, discord_id: str, username: str, avatar_url: str | None) -> User:
    now = int(time.time())
    with connect() as con:
        row = con.execute(
            "SELECT discord_id, username, avatar_url, created_at, last_login FROM users WHERE discord_id = ?",
            (discord_id,),
        ).fetchone()
        if row is None:
            con.execute(
                "INSERT INTO users(discord_id, username, avatar_url, created_at, last_login) VALUES(?,?,?,?,?)",
                (discord_id, username, avatar_url, now, now),
            )
            con.commit()
            return User(discord_id=discord_id, username=username, avatar_url=avatar_url, created_at=now, last_login=now)

        con.execute(
            "UPDATE users SET username = ?, avatar_url = ?, last_login = ? WHERE discord_id = ?",
            (username, avatar_url, now, discord_id),
        )
        con.commit()
        return User(
            discord_id=row["discord_id"],
            username=username,
            avatar_url=avatar_url,
            created_at=int(row["created_at"]),
            last_login=now,
        )


def get_user(discord_id: str) -> User | None:
    with connect() as con:
        row = con.execute(
            "SELECT discord_id, username, avatar_url, created_at, last_login FROM users WHERE discord_id = ?",
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
        )
