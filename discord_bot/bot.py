from __future__ import annotations

import json
import os
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import discord
from discord.ext import commands

ROOT = Path(__file__).resolve().parent
REPO_ROOT = ROOT.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from discord_bot.tickets import TicketCloseView, TicketCog, TicketPanelView
from discord_bot.welcome_embed import Brand, build_leave_message, build_welcome_message


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _save_json(path: Path, data: dict[str, Any]) -> None:
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")


def _env_int(name: str, default: int = 0) -> int:
    raw = os.getenv(name, "").strip()
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def _env_list_int(name: str) -> list[int]:
    raw = os.getenv(name, "").strip()
    if not raw:
        return []
    values: list[int] = []
    for part in raw.split(","):
        part = part.strip()
        if not part:
            continue
        try:
            values.append(int(part))
        except ValueError:
            continue
    return values


def _is_url(value: str) -> bool:
    return value.strip().lower().startswith(("http://", "https://"))


def _brand_paths(
    config_path: Path,
    brand_raw: dict[str, Any],
    *,
    prefer_file: bool,
) -> tuple[str, str, str, str]:
    banner_url_file = str(brand_raw.get("banner_url", "")).strip()
    logo_url_file = str(brand_raw.get("logo_url", "")).strip()
    banner_url_env = os.getenv("BRAND_BANNER_URL", "").strip()
    logo_url_env = os.getenv("BRAND_LOGO_URL", "").strip()

    banner_path_raw = str(brand_raw.get("banner_path", "")).strip()
    logo_path_raw = str(brand_raw.get("logo_path", "")).strip()

    if prefer_file and banner_url_file:
        banner_url = banner_url_file
    elif banner_url_env:
        banner_url = banner_url_env
    else:
        banner_url = banner_url_file

    if prefer_file and logo_url_file:
        logo_url = logo_url_file
    elif logo_url_env:
        logo_url = logo_url_env
    else:
        logo_url = logo_url_file

    if not banner_url and _is_url(banner_path_raw):
        banner_url = banner_path_raw
        banner_path_raw = ""
    if not logo_url and _is_url(logo_path_raw):
        logo_url = logo_path_raw
        logo_path_raw = ""

    banner_path = (
        str((config_path.parent / banner_path_raw).resolve())
        if banner_path_raw and not _is_url(banner_path_raw)
        else ""
    )
    logo_path = (
        str((config_path.parent / logo_path_raw).resolve())
        if logo_path_raw and not _is_url(logo_path_raw)
        else ""
    )

    return banner_url, banner_path, logo_url, logo_path


@dataclass
class BotConfig:
    token: str
    guild_id: int
    welcome_channel_id: int
    leave_channel_id: int
    ticket_category_id: int
    ticket_staff_role_ids: list[int]
    ticket_log_channel_id: int
    auto_role_ids: list[int]
    brand: Brand


def load_config(config_path: Path) -> BotConfig:
    raw = _load_json(config_path)
    brand_raw = raw.get("brand", {}) or {}

    token = os.getenv("DISCORD_BOT_TOKEN", "").strip() or str(raw.get("token", ""))
    guild_id = _env_int("DISCORD_GUILD_ID", int(raw.get("guild_id", 0)))
    welcome_channel_id = _env_int("DISCORD_WELCOME_CHANNEL_ID", int(raw.get("welcome_channel_id", 0)))
    leave_channel_id = _env_int("DISCORD_LEAVE_CHANNEL_ID", int(raw.get("leave_channel_id", 0)))
    ticket_category_id = _env_int("DISCORD_TICKET_CATEGORY_ID", int(raw.get("ticket_category_id", 0)))
    ticket_log_channel_id = _env_int("DISCORD_TICKET_LOG_CHANNEL_ID", int(raw.get("ticket_log_channel_id", 0)))

    staff_from_env = _env_list_int("DISCORD_TICKET_STAFF_ROLE_IDS")
    staff_from_file = [int(x) for x in (raw.get("ticket_staff_role_ids") or [])]
    ticket_staff_role_ids = staff_from_env or staff_from_file

    prefer_file = config_path.name == "config.json"

    auto_from_env = _env_list_int("DISCORD_AUTO_ROLE_IDS")
    auto_from_file = [int(x) for x in (raw.get("auto_role_ids") or [])]
    if not auto_from_file and raw.get("auto_role_id"):
        auto_from_file = [int(raw.get("auto_role_id"))]
    if prefer_file:
        auto_role_ids = auto_from_file or auto_from_env
    else:
        auto_role_ids = auto_from_env or auto_from_file

    banner_url, banner_path, logo_url, logo_path = _brand_paths(
        config_path,
        brand_raw,
        prefer_file=prefer_file,
    )

    return BotConfig(
        token=token,
        guild_id=guild_id,
        welcome_channel_id=welcome_channel_id,
        leave_channel_id=leave_channel_id,
        ticket_category_id=ticket_category_id,
        ticket_staff_role_ids=ticket_staff_role_ids,
        ticket_log_channel_id=ticket_log_channel_id,
        auto_role_ids=auto_role_ids,
        brand=Brand(
            server_name=os.getenv("BRAND_SERVER_NAME", "").strip()
            or str(brand_raw.get("server_name", "Dot X")),
            accent_hex=(
                str(brand_raw.get("accent_hex", "#FFD700"))
                if prefer_file and brand_raw.get("accent_hex")
                else os.getenv("BRAND_ACCENT_HEX", "").strip()
                or str(brand_raw.get("accent_hex", "#FFD700"))
            ),
            footer_text=str(brand_raw.get("footer_text", "")),
            banner_url=banner_url,
            banner_path=banner_path,
            logo_url=logo_url,
            logo_path=logo_path,
        ),
    )


class DotxBot(commands.Bot):
    def __init__(self, *, cfg: BotConfig, state_path: Path):
        intents = discord.Intents.default()
        intents.members = True
        intents.message_content = True

        super().__init__(command_prefix="!", intents=intents)
        self.cfg = cfg
        self.state_path = state_path
        self.state = _load_json(state_path) or {}

    def save_state(self) -> None:
        _save_json(self.state_path, self.state)

    async def setup_hook(self) -> None:
        self.add_view(TicketPanelView())
        self.add_view(TicketCloseView())
        await self.add_cog(TicketCog(self))
        if self.cfg.guild_id:
            guild = discord.Object(id=self.cfg.guild_id)
            self.tree.copy_global_to(guild=guild)
            synced = await self.tree.sync(guild=guild)
            print(f"[{_now()}] Synced {len(synced)} slash command(s)")

    async def on_ready(self) -> None:
        print(f"[{_now()}] Logged in as {self.user} (guild={self.cfg.guild_id})")
        if self.cfg.auto_role_ids:
            print(f"[{_now()}] Auto-role enabled for role ID(s): {self.cfg.auto_role_ids}")
        else:
            print(f"[{_now()}] Auto-role disabled (no role IDs configured)")

    async def _send_welcome_leave(self, member: discord.Member, *, kind: str) -> None:
        channel_id = self.cfg.welcome_channel_id if kind == "welcome" else self.cfg.leave_channel_id
        channel = self.get_channel(channel_id)
        if not isinstance(channel, discord.TextChannel):
            return

        if kind == "welcome":
            content, embed, files = build_welcome_message(brand=self.cfg.brand, member=member)
        else:
            content, embed, files = build_leave_message(brand=self.cfg.brand, member=member)

        await channel.send(content=content, embed=embed, files=files)

    async def _assign_auto_roles(self, member: discord.Member) -> None:
        if not self.cfg.auto_role_ids:
            return

        guild = member.guild
        bot_member = guild.me
        if not bot_member or not bot_member.guild_permissions.manage_roles:
            print(f"[{_now()}] Auto-role skipped: bot needs Manage Roles permission")
            return

        roles_to_add: list[discord.Role] = []
        for role_id in self.cfg.auto_role_ids:
            role = guild.get_role(role_id)
            if role is None:
                print(f"[{_now()}] Auto-role skipped: role {role_id} not found")
                continue
            if role >= bot_member.top_role:
                print(f"[{_now()}] Auto-role skipped: {role.name} is above the bot's role")
                continue
            if role not in member.roles:
                roles_to_add.append(role)

        if not roles_to_add:
            return

        try:
            await member.add_roles(*roles_to_add, reason="Auto-role on join")
            names = ", ".join(r.name for r in roles_to_add)
            print(f"[{_now()}] Gave {member} auto-role(s): {names}")
        except discord.Forbidden:
            print(f"[{_now()}] Auto-role failed for {member}: forbidden")
        except discord.HTTPException as exc:
            print(f"[{_now()}] Auto-role failed for {member}: {exc}")

    async def on_member_join(self, member: discord.Member) -> None:
        await self._assign_auto_roles(member)
        await self._send_welcome_leave(member, kind="welcome")

    async def on_member_remove(self, member: discord.Member) -> None:
        await self._send_welcome_leave(member, kind="leave")


def main() -> None:
    config_path = ROOT / "config.json"
    if not config_path.exists():
        config_path = ROOT / "config.example.json"
        if not os.getenv("DISCORD_BOT_TOKEN"):
            raise SystemExit(
                "Missing discord_bot/config.json or DISCORD_BOT_TOKEN. "
                "Copy config.example.json to config.json or set Railway env vars."
            )

    cfg = load_config(config_path)
    if not cfg.token:
        raise SystemExit("Bot token missing. Set DISCORD_BOT_TOKEN or config.json token.")

    state_path = Path(os.getenv("BOT_STATE_PATH", str(ROOT / "state.json")))
    bot = DotxBot(cfg=cfg, state_path=state_path)
    bot.run(cfg.token)


if __name__ == "__main__":
    main()
