"""
Discord school project bot — interactive setup via .bat prompts.

Run: double-click school-discord-bot.bat (or set env vars and run this module).
"""

from __future__ import annotations

import asyncio
import os
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

import discord
from discord.ext import commands

ROOT = Path(__file__).resolve().parent


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")


def _extract_invite_code(link: str) -> str:
    link = link.strip()
    if not link:
        return ""
    if re.fullmatch(r"[A-Za-z0-9-]+", link):
        return link
    parsed = urlparse(link if "://" in link else f"https://{link}")
    path = parsed.path.strip("/")
    if path.lower().startswith("invite/"):
        return path.split("/", 1)[1]
    if path:
        return path.split("/")[-1]
    return ""


def _safe_channel_name(name: str) -> str:
    return name.strip().lower().replace(" ", "-")[:100]


@dataclass
class SchoolConfig:
    token: str
    invite_link: str
    guild_id: int
    server_name: str
    channel_name: str
    channels: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not self.channels and self.channel_name.strip():
            self.channels = [self.channel_name.strip()]


def load_config_from_env() -> SchoolConfig:
    token = os.getenv("DISCORD_BOT_TOKEN", "").strip()
    invite_link = os.getenv("DISCORD_INVITE_LINK", "").strip()
    guild_raw = os.getenv("DISCORD_GUILD_ID", "").strip()
    server_name = os.getenv("SCHOOL_SERVER_NAME", "").strip()
    channel_name = os.getenv("SCHOOL_CHANNEL_NAME", "").strip()

    try:
        guild_id = int(guild_raw)
    except ValueError:
        guild_id = 0

    return SchoolConfig(
        token=token,
        invite_link=invite_link,
        guild_id=guild_id,
        server_name=server_name,
        channel_name=channel_name,
    )


def _bot_invite_url(client_id: int, guild_id: int) -> str:
    perms = discord.Permissions(
        manage_guild=True,
        manage_channels=True,
        send_messages=True,
        read_message_history=True,
    )
    return discord.utils.oauth_url(
        client_id,
        permissions=perms,
        scopes=["bot"],
        guild=discord.Object(id=guild_id),
        disable_guild_select=True,
    )


class SchoolBot(commands.Bot):
    def __init__(self, *, cfg: SchoolConfig):
        intents = discord.Intents.default()
        intents.guilds = True
        super().__init__(command_prefix="!", intents=intents)
        self.cfg = cfg
        self.setup_done = asyncio.Event()
        self.setup_results: list[str] = []

    async def validate_invite(self) -> tuple[bool, str]:
        code = _extract_invite_code(self.cfg.invite_link)
        if not code:
            return False, f"Could not read invite link: {self.cfg.invite_link}"

        try:
            invite = await self.fetch_invite(code, with_counts=True)
        except discord.NotFound:
            return False, "Invite link is invalid or expired."
        except discord.HTTPException as exc:
            return False, f"Could not fetch invite: {exc}"

        if invite.guild is None:
            return False, "That invite is not for a server."

        if invite.guild.id != self.cfg.guild_id:
            return (
                False,
                f"Invite server ID ({invite.guild.id}) does not match "
                f"your server ID ({self.cfg.guild_id}).",
            )

        return True, f"Invite matches server: {invite.guild.name}"

    async def run_setup(self, guild: discord.Guild) -> list[str]:
        results: list[str] = []

        me = guild.me
        if me is None:
            me = await guild.fetch_member(self.user.id)  # type: ignore[union-attr]

        if self.cfg.server_name:
            if not me.guild_permissions.manage_guild:
                results.append("Cannot rename server — bot needs Manage Server permission.")
            elif guild.name != self.cfg.server_name:
                try:
                    await guild.edit(name=self.cfg.server_name, reason="School bot setup")
                    results.append(f"Renamed server to: {self.cfg.server_name}")
                except discord.Forbidden:
                    results.append("Failed to rename server — no permission.")
                except discord.HTTPException as exc:
                    results.append(f"Failed to rename server: {exc}")
            else:
                results.append(f"Server already named: {self.cfg.server_name}")

        if self.cfg.channels:
            if not me.guild_permissions.manage_channels:
                results.append("Cannot create channel — bot needs Manage Channels permission.")
            else:
                existing = {c.name.lower() for c in guild.channels if isinstance(c, discord.TextChannel)}
                for raw_name in self.cfg.channels:
                    safe_name = _safe_channel_name(raw_name)
                    if not safe_name:
                        continue
                    if safe_name in existing:
                        results.append(f"Channel #{safe_name} already exists.")
                        continue
                    try:
                        await guild.create_text_channel(safe_name, reason="School bot setup")
                        existing.add(safe_name)
                        results.append(f"Created channel: #{safe_name}")
                    except discord.Forbidden:
                        results.append(f"Failed to create #{safe_name} — no permission.")
                    except discord.HTTPException as exc:
                        results.append(f"Failed to create #{safe_name}: {exc}")

        return results or ["Nothing to change."]

    async def _finish_setup(self, guild: discord.Guild) -> None:
        if self.setup_done.is_set():
            return

        print(f"[{_now()}] Running setup on: {guild.name}")
        self.setup_results = await self.run_setup(guild)
        for line in self.setup_results:
            print(f"[{_now()}]   {line}")

        print(f"[{_now()}] Done! You can close this window.")
        self.setup_done.set()
        await self.close()

    async def on_ready(self) -> None:
        assert self.user is not None
        print(f"[{_now()}] Logged in as {self.user.name}")
        print(f"[{_now()}] Server ID: {self.cfg.guild_id}")

        ok, message = await self.validate_invite()
        if ok:
            print(f"[{_now()}] {message}")
        else:
            print(f"[{_now()}] ERROR: {message}")
            await self.close()
            return

        guild = self.get_guild(self.cfg.guild_id)
        if guild is not None:
            await self._finish_setup(guild)
            return

        invite_url = _bot_invite_url(self.user.id, self.cfg.guild_id)
        print()
        print("=" * 60)
        print("  Bot is NOT in your server yet.")
        print("  Open this link in your browser and add the bot:")
        print()
        print(f"  {invite_url}")
        print()
        print("  Waiting up to 5 minutes for you to add it...")
        print("=" * 60)
        print()

        async def _wait_timeout() -> None:
            await asyncio.sleep(300)
            if not self.setup_done.is_set():
                print(f"[{_now()}] Timed out — add the bot with the link above and run again.")
                await self.close()

        self.loop.create_task(_wait_timeout())

    async def on_guild_join(self, guild: discord.Guild) -> None:
        if guild.id != self.cfg.guild_id:
            return
        ok, message = await self.validate_invite()
        print(f"[{_now()}] Bot joined server. {message}")
        await self._finish_setup(guild)


def _validate_cfg(cfg: SchoolConfig) -> None:
    missing: list[str] = []
    if not cfg.token:
        missing.append("Discord bot token")
    if not cfg.invite_link:
        missing.append("Discord server invite link")
    if not cfg.guild_id:
        missing.append("Discord server ID")
    if not cfg.server_name:
        missing.append("New server name")
    if not cfg.channel_name:
        missing.append("Channel name")
    if missing:
        raise SystemExit("Missing: " + ", ".join(missing))


def main() -> None:
    cfg = load_config_from_env()
    _validate_cfg(cfg)

    print()
    print("=" * 60)
    print("  Discord School Bot — starting...")
    print("=" * 60)
    print()

    bot = SchoolBot(cfg=cfg)
    bot.run(cfg.token)


if __name__ == "__main__":
    main()
