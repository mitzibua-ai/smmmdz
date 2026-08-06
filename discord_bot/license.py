from __future__ import annotations

import asyncio
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING

import discord
from discord import app_commands
from discord.ext import commands, tasks

if TYPE_CHECKING:
    from discord_bot.bot import DotxBot

REPO_ROOT = Path(__file__).resolve().parents[1]
WEB_DIR = REPO_ROOT / "web"
if str(WEB_DIR) not in sys.path:
    sys.path.insert(0, str(WEB_DIR))

from data_store import (
    create_license_key,
    duration_to_seconds,
    expire_site_licenses,
    format_duration,
    is_lifetime_key,
    redeem_license_key,
    revoke_site_license,
)
from discord_bot.tickets import _is_ticket_staff

UNIT_CHOICES = ["lifetime", "months", "days"]
UNIT_ALIASES = {
    "lifetime": "lifetime",
    "life": "lifetime",
    "permanent": "lifetime",
    "perm": "lifetime",
    "month": "months",
    "months": "months",
    "mo": "months",
    "day": "days",
    "days": "days",
    "d": "days",
}
DEFAULT_OWNER_IDS = {"1284140942764539985"}
DEFAULT_PURCHASE_LOG_CHANNEL_ID = 1521165512820916304
_owner_cache: set[str] | None = None
_owner_cache_mtime: float = -1.0


def _normalize_unit(raw: str) -> str | None:
    key = str(raw or "").strip().lower()
    mapped = UNIT_ALIASES.get(key)
    return mapped if mapped in UNIT_CHOICES else None


def _owner_ids() -> set[str]:
    global _owner_cache, _owner_cache_mtime
    owners_path = WEB_DIR / "data" / "owners.json"
    try:
        mtime = owners_path.stat().st_mtime if owners_path.is_file() else 0.0
    except OSError:
        mtime = 0.0
    if _owner_cache is not None and mtime == _owner_cache_mtime:
        return _owner_cache

    ids = set(DEFAULT_OWNER_IDS)
    ids.update(part.strip() for part in os.getenv("OWNER_DISCORD_IDS", "").split(",") if part.strip())
    if owners_path.is_file():
        try:
            data = json.loads(owners_path.read_text(encoding="utf-8"))
            for item in data.get("discordIds", []):
                value = str(item).strip()
                if value:
                    ids.add(value)
        except (json.JSONDecodeError, OSError):
            pass
    _owner_cache = ids
    _owner_cache_mtime = mtime
    return ids


def _customer_role_id(bot: DotxBot) -> int:
    configured = int(getattr(bot.cfg, "customer_role_id", 0) or 0)
    if configured:
        return configured
    raw = os.getenv("DISCORD_CUSTOMER_ROLE_ID", "1519527288503275641").strip()
    try:
        return int(raw)
    except ValueError:
        return 0


def _purchase_log_channel_id(bot: DotxBot) -> int:
    configured = int(getattr(bot.cfg, "purchase_log_channel_id", 0) or 0)
    if configured:
        return configured
    raw = os.getenv("DISCORD_PURCHASE_LOG_CHANNEL_ID", str(DEFAULT_PURCHASE_LOG_CHANNEL_ID)).strip()
    try:
        return int(raw) if raw else DEFAULT_PURCHASE_LOG_CHANNEL_ID
    except ValueError:
        return DEFAULT_PURCHASE_LOG_CHANNEL_ID


def _format_utc(iso_value: str | None) -> str:
    if not iso_value:
        return "—"
    try:
        dt = datetime.fromisoformat(str(iso_value).replace("Z", "+00:00"))
        return dt.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    except ValueError:
        return str(iso_value)


def _display_name(user: discord.abc.User | None, fallback_id: str) -> str:
    if user is None:
        return f"Unknown ({fallback_id})"
    global_name = getattr(user, "global_name", None)
    if global_name:
        return f"{global_name} ({user.name})"
    return str(user)


async def _resolve_ticket_channel(
    guild: discord.Guild,
    ticket_ref: str,
    *,
    ticket_category_id: int,
) -> discord.TextChannel | None:
    ref = str(ticket_ref or "").strip()
    if not ref:
        return None

    mention = re.fullmatch(r"<#(\d+)>", ref)
    if mention:
        channel = guild.get_channel(int(mention.group(1)))
        return channel if isinstance(channel, discord.TextChannel) else None

    if ref.isdigit() and len(ref) >= 17:
        channel = guild.get_channel(int(ref))
        return channel if isinstance(channel, discord.TextChannel) else None

    number_match = re.search(r"(\d{4,})", ref)
    if number_match:
        ticket_no = number_match.group(1)
        prefix = f"ticket-{ticket_no}"
        for channel in guild.text_channels:
            if channel.name.startswith(prefix):
                return channel

    lowered = ref.lower()
    for channel in guild.text_channels:
        if channel.name.lower() == lowered or channel.name.lower().startswith(lowered):
            if ticket_category_id and channel.category_id == ticket_category_id:
                return channel
            if not ticket_category_id:
                return channel
    return None


def _license_embed(bot: DotxBot, *, title: str, description: str, color: int = 0x00D4AA) -> discord.Embed:
    accent = bot.cfg.brand.accent_hex
    if accent.startswith("#"):
        color = int(accent.replace("#", ""), 16)
    embed = discord.Embed(title=title, description=description, color=color)
    embed.set_footer(text=bot.cfg.brand.footer_text or "dotx licensing")
    return embed


async def _grant_customer_role(bot: DotxBot, guild: discord.Guild, member: discord.Member) -> bool:
    role_id = _customer_role_id(bot)
    if not role_id:
        return False
    role = guild.get_role(role_id)
    if not role:
        return False
    if role in member.roles:
        return True
    bot_member = guild.me
    if not bot_member or role >= bot_member.top_role:
        return False
    try:
        await member.add_roles(role, reason="dotx license key redeemed")
        return True
    except (discord.Forbidden, discord.HTTPException):
        return False


async def _revoke_customer_role(
    bot: DotxBot,
    guild: discord.Guild,
    member: discord.Member,
    *,
    reason: str = "dotx license revoked",
) -> bool:
    role_id = _customer_role_id(bot)
    if not role_id:
        return False
    role = guild.get_role(role_id)
    if not role or role not in member.roles:
        return True
    bot_member = guild.me
    if not bot_member or role >= bot_member.top_role:
        return False
    try:
        await member.remove_roles(role, reason=reason)
        return True
    except (discord.Forbidden, discord.HTTPException):
        return False


async def _post_purchase_log(
    bot: DotxBot,
    guild: discord.Guild,
    *,
    buyer: discord.abc.User | None,
    buyer_id: str,
    staff: discord.abc.User,
    license_key: str,
    purchased_at: str | None,
    expires_at: str | None,
    duration_label: str | None = None,
) -> None:
    channel_id = _purchase_log_channel_id(bot)
    if not channel_id:
        return
    channel = guild.get_channel(channel_id) or bot.get_channel(channel_id)
    if channel is None:
        try:
            channel = await bot.fetch_channel(channel_id)
        except (discord.NotFound, discord.Forbidden, discord.HTTPException):
            print(f"[dotx] purchase log channel {channel_id} not found")
            return
    if not isinstance(channel, discord.TextChannel):
        return

    buy_label = _format_utc(purchased_at) if purchased_at else _format_utc(datetime.now(timezone.utc).isoformat())
    plan = str(duration_label or "").strip() or "Timed"
    lifetime = plan.lower() == "lifetime" or not expires_at
    if lifetime and plan.lower() != "lifetime":
        plan = "Lifetime"
    exp_label = "Never (Lifetime)" if lifetime else _format_utc(expires_at)
    buyer_name = _display_name(buyer, buyer_id)
    staff_name = _display_name(staff, str(staff.id))

    embed = _license_embed(
        bot,
        title="Transaction receipt",
        description=(
            f"**Buyer:** {buyer_name}\n"
            f"**Buyer ID:** `{buyer_id}` · <@{buyer_id}>\n"
            f"**Activated by:** {staff_name}\n"
            f"**Staff ID:** `{staff.id}` · {staff.mention}\n"
            f"**Plan:** {plan}\n"
            f"**Expiration:** {exp_label}\n"
            f"**License key:** `{license_key}`\n"
            f"**Purchased:** {buy_label}"
        ),
        color=0xFFD700,
    )
    try:
        await channel.send(embed=embed)
    except (discord.Forbidden, discord.HTTPException) as exc:
        print(f"[dotx] failed to post purchase log: {exc!r}")


async def _get_guild_member(guild: discord.Guild, user_id: int) -> discord.Member | None:
    member = guild.get_member(user_id)
    if isinstance(member, discord.Member):
        return member
    try:
        return await guild.fetch_member(user_id)
    except (discord.NotFound, discord.HTTPException):
        return None


def _key_generated_embed(bot: DotxBot, created: dict, *, amount: int, unit: str) -> discord.Embed:
    label = created.get("durationLabel") or format_duration(amount, unit)
    return _license_embed(
        bot,
        title="License key generated",
        description=(
            f"**Plan:** {label}\n"
            f"**Key:** `{created['code']}`\n\n"
            "Save this key - it is shown once."
        ),
        color=0xFFD700,
    )


class KeyAmountModal(discord.ui.Modal):
    def __init__(self, cog: LicenseCog, author_id: int, unit: str) -> None:
        title = "How many months?" if unit == "months" else "How many days?"
        super().__init__(title=title)
        self.cog = cog
        self.author_id = author_id
        self.unit = unit
        self.amount_input = discord.ui.TextInput(
            label=f"Number of {unit}",
            placeholder="e.g. 1",
            required=True,
            max_length=4,
            min_length=1,
        )
        self.add_item(self.amount_input)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        if interaction.user.id != self.author_id:
            await interaction.response.send_message("This form is not for you.", ephemeral=True)
            return
        raw = str(self.amount_input.value or "").strip()
        if not raw.isdigit():
            await interaction.response.send_message("Enter a whole number (example: `1`).", ephemeral=True)
            return
        amount = int(raw)
        if amount < 1 or amount > 9999:
            await interaction.response.send_message("Amount must be between 1 and 9999.", ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True)
        try:
            created = await asyncio.to_thread(
                create_license_key,
                created_by=str(self.author_id),
                amount=amount,
                unit=self.unit,
            )
        except Exception as exc:
            print(f"[dotx] key generation failed: {exc!r}")
            await interaction.followup.send("Could not generate a key. Try again.", ephemeral=True)
            return
        embed = _key_generated_embed(self.cog.bot, created, amount=amount, unit=self.unit)
        await interaction.followup.send(embed=embed, ephemeral=True)


class KeyPlanSelect(discord.ui.Select):
    def __init__(self, cog: LicenseCog, author_id: int) -> None:
        self.cog = cog
        self.author_id = author_id
        options = [
            discord.SelectOption(label="Lifetime", value="lifetime", description="Never expires"),
            discord.SelectOption(label="Months", value="months", description="Then ask how many months"),
            discord.SelectOption(label="Days", value="days", description="Then ask how many days"),
        ]
        super().__init__(
            placeholder="Pick a plan...",
            min_values=1,
            max_values=1,
            options=options,
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        if interaction.user.id != self.author_id:
            await interaction.response.send_message("This menu is not for you.", ephemeral=True)
            return
        plan = self.values[0]
        if plan in {"months", "days"}:
            await interaction.response.send_modal(KeyAmountModal(self.cog, self.author_id, plan))
            return

        await interaction.response.defer(ephemeral=True)
        try:
            created = await asyncio.to_thread(
                create_license_key,
                created_by=str(self.author_id),
                amount=1,
                unit="lifetime",
            )
        except Exception as exc:
            print(f"[dotx] key generation failed: {exc!r}")
            await interaction.followup.send("Could not generate a key. Try again.", ephemeral=True)
            return
        embed = _key_generated_embed(self.cog.bot, created, amount=1, unit="lifetime")
        await interaction.followup.send(embed=embed, ephemeral=True)


class KeyPlanView(discord.ui.View):
    def __init__(self, cog: LicenseCog, author_id: int) -> None:
        super().__init__(timeout=120)
        self.add_item(KeyPlanSelect(cog, author_id))


class LicenseCog(commands.Cog):
    def __init__(self, bot: DotxBot) -> None:
        self.bot = bot
        self._pending: dict[int, dict] = {}
        self.expire_licenses_loop.start()

    def cog_unload(self) -> None:
        self.expire_licenses_loop.cancel()

    @tasks.loop(minutes=1.0)
    async def expire_licenses_loop(self) -> None:
        try:
            expired = await asyncio.to_thread(expire_site_licenses)
        except Exception as exc:
            print(f"[dotx] license expiry sweep failed: {exc!r}")
            return
        if not expired:
            return

        guild = self.bot.get_guild(self.bot.cfg.guild_id) if self.bot.cfg.guild_id else None
        for user in expired:
            discord_id = str(user.get("discordId") or "").strip()
            if not discord_id.isdigit():
                continue
            if not isinstance(guild, discord.Guild):
                print(f"[dotx] license expired for {discord_id} (no guild to strip role)")
                continue
            member = await _get_guild_member(guild, int(discord_id))
            if isinstance(member, discord.Member):
                removed = await _revoke_customer_role(
                    self.bot,
                    guild,
                    member,
                    reason="dotx license expired",
                )
                print(
                    f"[dotx] license expired for {member} - role removed={removed}; "
                    "Pins/Reports locked"
                )
            else:
                print(f"[dotx] license expired for {discord_id} (member not in guild)")

    @expire_licenses_loop.before_loop
    async def before_expire_licenses_loop(self) -> None:
        await self.bot.wait_until_ready()

    async def _finalize_license_grant(
        self,
        *,
        guild: discord.Guild,
        staff: discord.abc.User,
        target_id: str,
        license_key: str,
        result: dict,
        ticket_channel: discord.TextChannel | None = None,
    ) -> tuple[bool, str]:
        member = await _get_guild_member(guild, int(target_id))
        role_granted = False
        if isinstance(member, discord.Member):
            role_granted = await _grant_customer_role(self.bot, guild, member)

        expires = result.get("licenseExpiresAt")
        lifetime = bool(result.get("lifetime")) or is_lifetime_key(result.get("key")) or not expires
        exp_label = "Never (Lifetime)" if lifetime else _format_utc(expires)
        purchased_at = (result.get("key") or {}).get("redeemedAt") or datetime.now(timezone.utc).isoformat()
        duration_label = result.get("durationLabel") or ("Lifetime" if lifetime else "Timed")

        buyer_user: discord.abc.User | None = member
        if buyer_user is None:
            try:
                buyer_user = await self.bot.fetch_user(int(target_id))
            except (discord.NotFound, discord.HTTPException):
                buyer_user = None

        await _post_purchase_log(
            self.bot,
            guild,
            buyer=buyer_user,
            buyer_id=target_id,
            staff=staff,
            license_key=license_key.strip().upper(),
            purchased_at=purchased_at,
            expires_at=expires,
            duration_label=duration_label,
        )

        if ticket_channel is not None:
            receipt = _license_embed(
                self.bot,
                title="License activated",
                description=(
                    f"**Customer:** <@{target_id}>\n"
                    f"**Plan:** {duration_label}\n"
                    f"**Expires:** {exp_label}\n"
                    f"**Activated by:** {staff.mention}\n"
                    f"**Discord role:** {'Granted' if role_granted else 'Not granted (check bot role hierarchy)'}\n\n"
                    "You have license now - check [dotx.store](https://dotx.store)"
                ),
                color=0x22C55E,
            )
            await ticket_channel.send(embed=receipt)

        return role_granted, exp_label

    async def _reply_ephemeral(self, ctx: commands.Context, *args, view: discord.ui.View | None = None, **kwargs) -> None:
        kwargs.setdefault("ephemeral", True)
        if view is not None:
            kwargs["view"] = view
        if ctx.interaction:
            if ctx.interaction.response.is_done():
                await ctx.interaction.followup.send(*args, **kwargs)
            else:
                await ctx.interaction.response.send_message(*args, **kwargs)
            return
        kwargs.pop("ephemeral", None)
        kwargs.pop("view", None)
        await ctx.reply(*args, mention_author=False, **kwargs)

    async def _defer_slash(self, ctx: commands.Context) -> None:
        if ctx.interaction and not ctx.interaction.response.is_done():
            await ctx.interaction.response.defer(ephemeral=True)

    def _is_license_staff(self, member: discord.Member) -> bool:
        if str(member.id) in _owner_ids():
            return True
        if member.guild_permissions.administrator or member.guild_permissions.manage_guild:
            return True
        return _is_ticket_staff(self.bot, member)

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        if message.author.bot:
            return
        if not isinstance(message.author, discord.Member):
            return

        pending = self._pending.get(message.author.id)
        if pending and message.channel.id == pending.get("channel_id"):
            if not self._is_license_staff(message.author):
                self._pending.pop(message.author.id, None)
                return
            try:
                flow = pending.get("flow")
                if flow == "key_unit":
                    await self._key_after_unit(message, pending)
                elif flow == "key_amount":
                    await self._key_after_amount(message, pending)
                elif flow == "license_id":
                    await self._license_after_id(message, pending)
                elif flow == "license_key":
                    await self._license_after_key(message, pending)
                elif flow == "license_ticket":
                    await self._license_after_ticket(message, pending)
                elif flow == "revoke_id":
                    await self._revoke_after_id(message, pending)
            except Exception as exc:
                self._pending.pop(message.author.id, None)
                await message.channel.send(f"License flow failed: {exc}")
            return

        lower = message.content.strip().lower()
        if lower in {"smky key", "smky license", "smky revoke"}:
            if lower == "smky key":
                await self._start_key_flow_message(message)
            elif lower == "smky license":
                await self._start_license_flow_message(message)
            else:
                await self._start_revoke_flow_message(message)

    async def _start_key_flow_message(self, message: discord.Message) -> None:
        if not isinstance(message.author, discord.Member) or not self._is_license_staff(message.author):
            await message.reply("Only dotx staff can generate license keys.", mention_author=False)
            return
        self._pending[message.author.id] = {"flow": "key_unit", "channel_id": message.channel.id}
        await message.reply(
            "Pick a plan. Reply with: **Lifetime**, **Months**, or **Days**.",
            mention_author=False,
        )

    async def _start_license_flow_message(self, message: discord.Message) -> None:
        if not isinstance(message.author, discord.Member) or not self._is_license_staff(message.author):
            await message.reply("Only dotx staff can grant licenses.", mention_author=False)
            return
        self._pending[message.author.id] = {"flow": "license_id", "channel_id": message.channel.id}
        await message.reply(
            "Send the customer's **Discord user ID** (Developer Mode → right-click user → Copy User ID).",
            mention_author=False,
        )

    async def _start_revoke_flow_message(self, message: discord.Message) -> None:
        if not isinstance(message.author, discord.Member) or not self._is_license_staff(message.author):
            await message.reply("Only dotx staff can revoke licenses.", mention_author=False)
            return
        self._pending[message.author.id] = {"flow": "revoke_id", "channel_id": message.channel.id}
        await message.reply(
            "Send the **Discord user ID** to revoke (removes Customer license + Discord role).",
            mention_author=False,
        )

    async def _revoke_after_id(self, message: discord.Message, pending: dict) -> None:
        if not message.guild:
            self._pending.pop(message.author.id, None)
            return

        target_id = message.content.strip().replace("<@", "").replace("!", "").replace(">", "")
        if not target_id.isdigit():
            await message.channel.send("Send a valid Discord user ID (numbers only).")
            return

        self._pending.pop(message.author.id, None)
        try:
            revoke_site_license(discord_id=target_id, staff_id=str(message.author.id))
        except LookupError:
            await message.channel.send("That user has no license record on the website.")
            return
        except ValueError:
            await message.channel.send("Invalid Discord ID.")
            return

        member = await _get_guild_member(message.guild, int(target_id))
        role_removed = False
        if isinstance(member, discord.Member):
            role_removed = await _revoke_customer_role(self.bot, message.guild, member)

        await message.channel.send(
            embed=_license_embed(
                self.bot,
                title="License revoked",
                description=(
                    f"**User:** <@{target_id}>\n"
                    f"**Revoked by:** {message.author.mention}\n"
                    f"**Discord role removed:** {'Yes' if role_removed else 'No / not present'}\n\n"
                    "Website access (**Pins** / **Reports**) is locked again."
                ),
                color=0xF87171,
            )
        )

    async def _key_after_unit(self, message: discord.Message, pending: dict) -> None:
        unit = _normalize_unit(message.content)
        if not unit:
            await message.channel.send("Use **Lifetime**, **Months**, or **Days**.")
            return
        if unit == "lifetime":
            self._pending.pop(message.author.id, None)
            created = create_license_key(
                created_by=str(message.author.id),
                amount=1,
                unit="lifetime",
            )
            embed = _key_generated_embed(self.bot, created, amount=1, unit="lifetime")
            await message.channel.send(embed=embed)
            return
        pending["unit"] = unit
        pending["flow"] = "key_amount"
        await message.channel.send(f"How many **{unit}**? (example: `1`)")

    async def _key_after_amount(self, message: discord.Message, pending: dict) -> None:
        raw = message.content.strip()
        if not raw.isdigit():
            await message.channel.send("Reply with a whole number (example: `1`).")
            return
        amount = int(raw)
        if amount < 1 or amount > 9999:
            await message.channel.send("Amount must be between 1 and 9999.")
            return

        self._pending.pop(message.author.id, None)
        try:
            duration_to_seconds(amount, pending["unit"])
        except ValueError:
            await message.channel.send("Invalid plan.")
            return

        created = create_license_key(
            created_by=str(message.author.id),
            amount=amount,
            unit=pending["unit"],
        )
        embed = _key_generated_embed(self.bot, created, amount=amount, unit=pending["unit"])
        await message.channel.send(embed=embed)

    async def _license_after_id(self, message: discord.Message, pending: dict) -> None:
        target_id = message.content.strip().replace("<@", "").replace("!", "").replace(">", "")
        if not target_id.isdigit():
            await message.channel.send("Send a valid Discord user ID (numbers only).")
            return
        pending["target_id"] = target_id
        pending["flow"] = "license_key"
        await message.channel.send("Paste the **license key** (example: `SMKY-ABCD-1234`).")

    async def _license_after_key(self, message: discord.Message, pending: dict) -> None:
        pending["code"] = message.content.strip().upper()
        pending["flow"] = "license_ticket"
        await message.channel.send(
            "Send the **ticket ID** (channel ID, `#channel` mention, or `ticket-0001`).\n"
            "A receipt will be posted in that ticket."
        )

    async def _license_after_ticket(self, message: discord.Message, pending: dict) -> None:
        if not message.guild:
            self._pending.pop(message.author.id, None)
            return

        ticket_ref = message.content.strip()
        ticket_channel = await _resolve_ticket_channel(
            message.guild,
            ticket_ref,
            ticket_category_id=self.bot.cfg.ticket_category_id,
        )
        if not ticket_channel:
            await message.channel.send("Could not find that ticket channel. Check the ID and try again.")
            return

        self._pending.pop(message.author.id, None)
        try:
            result = redeem_license_key(
                code=pending["code"],
                target_discord_id=pending["target_id"],
                staff_id=str(message.author.id),
                ticket_channel_id=str(ticket_channel.id),
                ticket_ref=ticket_ref,
            )
        except LookupError as err:
            code = str(err)
            if code == "invalid_key":
                await message.channel.send("That key is invalid.")
            else:
                await message.channel.send("That key was already used.")
            return
        except ValueError:
            await message.channel.send("Invalid Discord ID.")
            return

        _role_granted, exp_label = await self._finalize_license_grant(
            guild=message.guild,
            staff=message.author,
            target_id=pending["target_id"],
            license_key=pending["code"],
            result=result,
            ticket_channel=ticket_channel,
        )

        await message.channel.send(
            embed=_license_embed(
                self.bot,
                title="Customer license granted",
                description=(
                    f"<@{pending['target_id']}> is now a **Customer** until **{exp_label}**.\n"
                    f"Receipt posted in {ticket_channel.mention}.\n"
                    f"Purchase logged to <#{_purchase_log_channel_id(self.bot)}>."
                ),
                color=0x22C55E,
            )
        )

    async def _start_key_flow(self, ctx: commands.Context) -> None:
        if not isinstance(ctx.author, discord.Member) or not self._is_license_staff(ctx.author):
            await ctx.reply("Only dotx staff can generate license keys.", mention_author=False)
            return
        self._pending[ctx.author.id] = {"flow": "key_unit", "channel_id": ctx.channel.id}
        await ctx.reply(
            "Pick a plan. Reply with: **Lifetime**, **Months**, or **Days**.",
            mention_author=False,
        )

    async def _start_license_flow(self, ctx: commands.Context) -> None:
        if not isinstance(ctx.author, discord.Member) or not self._is_license_staff(ctx.author):
            await ctx.reply("Only dotx staff can grant licenses.", mention_author=False)
            return
        self._pending[ctx.author.id] = {"flow": "license_id", "channel_id": ctx.channel.id}
        await ctx.reply(
            "Send the customer's **Discord user ID** (Developer Mode → right-click user → Copy User ID).",
            mention_author=False,
        )

    @commands.hybrid_group(name="smky", invoke_without_command=True, description="dotx license management")
    async def smky_group(self, ctx: commands.Context) -> None:
        text = (
            "**smky commands**\n"
            "• `smky key` — generate a license key\n"
            "• `smky license` — activate a customer\n"
            "• `smky revoke` — cancel a customer license\n"
            "• `smky product` — post/edit sell-channel listings\n\n"
            "Slash: `/smky key`, `/smky license`, `/smky revoke`, `/smky product`"
        )
        if ctx.interaction:
            await ctx.interaction.response.send_message(text, ephemeral=True)
        else:
            await ctx.reply(text, mention_author=False)

    @smky_group.command(name="key", description="Generate a license key (Lifetime / Months / Days)")
    @app_commands.describe(
        plan="Lifetime, Months, or Days",
        amount="How many months or days (required for Months/Days)",
    )
    @app_commands.choices(
        plan=[
            app_commands.Choice(name="Lifetime", value="lifetime"),
            app_commands.Choice(name="Months", value="months"),
            app_commands.Choice(name="Days", value="days"),
        ]
    )
    async def smky_key(
        self,
        ctx: commands.Context,
        plan: str | None = None,
        amount: int | None = None,
    ) -> None:
        interaction = ctx.interaction
        is_slash = interaction is not None

        if is_slash:
            if not isinstance(ctx.author, discord.Member) or not self._is_license_staff(ctx.author):
                await interaction.response.send_message(
                    "Only dotx staff can generate keys.",
                    ephemeral=True,
                )
                return

            if plan is None:
                view = KeyPlanView(self, ctx.author.id)
                await interaction.response.send_message(
                    "Pick a plan:",
                    view=view,
                    ephemeral=True,
                )
                return

            plan = str(plan).strip().lower()
            if plan == "lifetime":
                await interaction.response.defer(ephemeral=True)
                try:
                    created = await asyncio.to_thread(
                        create_license_key,
                        created_by=str(ctx.author.id),
                        amount=1,
                        unit="lifetime",
                    )
                except Exception as exc:
                    print(f"[dotx] smky key failed: {exc!r}")
                    await interaction.followup.send(
                        "Could not generate a key. Try again in a moment.",
                        ephemeral=True,
                    )
                    return
                embed = _key_generated_embed(self.bot, created, amount=1, unit="lifetime")
                await interaction.followup.send(embed=embed, ephemeral=True)
                return

            if plan not in {"months", "days"}:
                await interaction.response.send_message(
                    "Plan must be Lifetime, Months, or Days.",
                    ephemeral=True,
                )
                return

            if amount is None:
                await interaction.response.send_modal(KeyAmountModal(self, ctx.author.id, plan))
                return

            if amount < 1 or amount > 9999:
                await interaction.response.send_message(
                    "Amount must be between 1 and 9999.",
                    ephemeral=True,
                )
                return

            await interaction.response.defer(ephemeral=True)
            try:
                created = await asyncio.to_thread(
                    create_license_key,
                    created_by=str(ctx.author.id),
                    amount=amount,
                    unit=plan,
                )
            except Exception as exc:
                print(f"[dotx] smky key failed: {exc!r}")
                await interaction.followup.send(
                    "Could not generate a key. Try again in a moment.",
                    ephemeral=True,
                )
                return
            embed = _key_generated_embed(self.bot, created, amount=amount, unit=plan)
            await interaction.followup.send(embed=embed, ephemeral=True)
            return

        if not isinstance(ctx.author, discord.Member) or not self._is_license_staff(ctx.author):
            await self._reply_ephemeral(ctx, "Only dotx staff can generate keys.")
            return
        await self._start_key_flow(ctx)

    @smky_group.command(name="license", description="Redeem a key for a customer")
    @app_commands.describe(
        discord_id="Customer Discord user ID",
        key="License key (SMKY-XXXX-XXXX)",
        ticket="Ticket channel ID, mention, or ticket-0001",
    )
    async def smky_license(
        self,
        ctx: commands.Context,
        discord_id: str | None = None,
        key: str | None = None,
        ticket: str | None = None,
    ) -> None:
        is_slash = ctx.interaction is not None
        if is_slash:
            await self._defer_slash(ctx)

        if not isinstance(ctx.author, discord.Member) or not self._is_license_staff(ctx.author):
            await self._reply_ephemeral(ctx, "Only dotx staff can grant licenses.")
            return

        if is_slash:
            if not ctx.guild:
                await self._reply_ephemeral(ctx, "Run this in the server.")
                return
            if not discord_id or not key or not ticket:
                await self._reply_ephemeral(ctx, "discord_id, key, and ticket are required.")
                return
            target_id = discord_id.strip()
            if not target_id.isdigit():
                await self._reply_ephemeral(ctx, "Invalid Discord user ID.")
                return

            ticket_channel = await _resolve_ticket_channel(
                ctx.guild,
                ticket,
                ticket_category_id=self.bot.cfg.ticket_category_id,
            )
            if not ticket_channel:
                await self._reply_ephemeral(ctx, "Ticket channel not found.")
                return

            try:
                result = await asyncio.to_thread(
                    redeem_license_key,
                    code=key,
                    target_discord_id=target_id,
                    staff_id=str(ctx.author.id),
                    ticket_channel_id=str(ticket_channel.id),
                    ticket_ref=ticket,
                )
            except LookupError as err:
                msg = "Invalid key." if str(err) == "invalid_key" else "Key already used."
                await self._reply_ephemeral(ctx, msg)
                return
            except Exception as exc:
                print(f"[dotx] smky license failed: {exc!r}")
                await self._reply_ephemeral(ctx, "Could not activate license. Try again.")
                return

            _role_granted, exp_label = await self._finalize_license_grant(
                guild=ctx.guild,
                staff=ctx.author,
                target_id=target_id,
                license_key=key,
                result=result,
                ticket_channel=ticket_channel,
            )
            await self._reply_ephemeral(
                ctx,
                f"Customer license granted for <@{target_id}> until **{exp_label}**.\n"
                f"Receipt posted in {ticket_channel.mention}.\n"
                f"Purchase logged to <#{_purchase_log_channel_id(self.bot)}>.",
            )
            return

        await self._start_license_flow(ctx)

    @smky_group.command(name="revoke", description="Revoke a customer license and remove Discord role")
    @app_commands.describe(discord_id="Customer Discord user ID to revoke")
    async def smky_revoke(self, ctx: commands.Context, discord_id: str | None = None) -> None:
        is_slash = ctx.interaction is not None
        if is_slash:
            await self._defer_slash(ctx)

        if not isinstance(ctx.author, discord.Member) or not self._is_license_staff(ctx.author):
            await self._reply_ephemeral(ctx, "Only dotx staff can revoke licenses.")
            return

        if is_slash:
            if not ctx.guild:
                await self._reply_ephemeral(ctx, "Run this in the server.")
                return
            if not discord_id:
                await self._reply_ephemeral(ctx, "discord_id is required.")
                return
            target_id = discord_id.strip()
            if not target_id.isdigit():
                await self._reply_ephemeral(ctx, "Invalid Discord user ID.")
                return
            try:
                await asyncio.to_thread(
                    revoke_site_license,
                    discord_id=target_id,
                    staff_id=str(ctx.author.id),
                )
            except LookupError:
                await self._reply_ephemeral(ctx, "That user has no license record.")
                return
            except Exception as exc:
                print(f"[dotx] smky revoke failed: {exc!r}")
                await self._reply_ephemeral(ctx, "Could not revoke license. Try again.")
                return
            member = await _get_guild_member(ctx.guild, int(target_id))
            role_removed = False
            if isinstance(member, discord.Member):
                role_removed = await _revoke_customer_role(self.bot, ctx.guild, member)
            await self._reply_ephemeral(
                ctx,
                embed=_license_embed(
                    self.bot,
                    title="License revoked",
                    description=(
                        f"**User:** <@{target_id}>\n"
                        f"**Revoked by:** {ctx.author.mention}\n"
                        f"**Discord role removed:** {'Yes' if role_removed else 'No / not present'}\n\n"
                        "Website **Pins** and **Reports** are locked again."
                    ),
                    color=0xF87171,
                ),
            )
            return

        self._pending[ctx.author.id] = {"flow": "revoke_id", "channel_id": ctx.channel.id}
        await ctx.reply(
            "Send the **Discord user ID** to revoke.",
            mention_author=False,
        )

    @smky_group.error
    async def smky_group_error(self, ctx: commands.Context, error: Exception) -> None:
        print(f"[dotx] smky command error: {error!r}")
        try:
            await self._reply_ephemeral(ctx, f"Command failed: {error}")
        except discord.HTTPException:
            pass


async def setup_license_commands(bot: DotxBot) -> None:
    from discord_bot.products import inject_product_commands, setup_product_commands

    cog = LicenseCog(bot)
    inject_product_commands(cog)
    await bot.add_cog(cog)
    await setup_product_commands(bot)
    print("[dotx] License commands loaded: smky key, smky license, smky revoke, smky product")
