from __future__ import annotations

import re
from typing import TYPE_CHECKING

import discord
from discord import app_commands
from discord.ext import commands

if TYPE_CHECKING:
    from discord_bot.bot import DotxBot

OPEN_TICKET_ID = "dotx:ticket:open"
CLOSE_TICKET_ID = "dotx:ticket:close"
_TICKET_NAME_RE = re.compile(r"^ticket-(\d+)", re.IGNORECASE)


def _ticket_state(bot: DotxBot) -> dict:
    tickets = bot.state.setdefault("tickets", {})
    if not isinstance(tickets, dict):
        tickets = {}
        bot.state["tickets"] = tickets
    return tickets


def _ticket_number_from_name(name: str) -> int | None:
    match = _TICKET_NAME_RE.match(str(name or "").strip())
    if not match:
        return None
    try:
        return int(match.group(1))
    except ValueError:
        return None


def _highest_ticket_number(bot: DotxBot, guild: discord.Guild | None = None) -> int:
    """Highest ticket number from saved counter + existing ticket channel names."""
    stored = int(bot.state.get("ticket_counter", 0) or 0)
    highest = stored

    if guild is None and bot.cfg.guild_id:
        guild = bot.get_guild(bot.cfg.guild_id)

    if isinstance(guild, discord.Guild):
        channels = list(guild.text_channels)
        category_id = int(bot.cfg.ticket_category_id or 0)
        if category_id:
            category = guild.get_channel(category_id)
            if isinstance(category, discord.CategoryChannel):
                channels = list(category.text_channels) + channels

        seen: set[int] = set()
        for channel in channels:
            if channel.id in seen:
                continue
            seen.add(channel.id)
            number = _ticket_number_from_name(channel.name)
            if number is not None and number > highest:
                highest = number

    return highest


def sync_ticket_counter(bot: DotxBot, guild: discord.Guild | None = None) -> int:
    """Ensure ticket_counter never goes backwards. Returns the synced value."""
    highest = _highest_ticket_number(bot, guild)
    current = int(bot.state.get("ticket_counter", 0) or 0)
    if highest > current:
        bot.state["ticket_counter"] = highest
        bot.save_state()
        return highest
    if "ticket_counter" not in bot.state:
        bot.state["ticket_counter"] = current
        bot.save_state()
    return current


def _next_ticket_number(bot: DotxBot, guild: discord.Guild | None = None) -> int:
    # Always continue from the highest known number (saved or live channels).
    base = sync_ticket_counter(bot, guild)
    counter = base + 1
    bot.state["ticket_counter"] = counter
    bot.save_state()
    return counter


def _find_open_ticket(bot: DotxBot, user_id: int) -> int | None:
    channel_id = _ticket_state(bot).get(str(user_id))
    return int(channel_id) if channel_id else None


class TicketPanelView(discord.ui.View):
    def __init__(self) -> None:
        super().__init__(timeout=None)

    @discord.ui.button(
        label="Open Ticket",
        style=discord.ButtonStyle.primary,
        custom_id=OPEN_TICKET_ID,
        emoji="🎫",
    )
    async def open_ticket(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        bot: DotxBot = interaction.client  # type: ignore[assignment]
        await open_ticket_for_member(bot, interaction)


class TicketCloseView(discord.ui.View):
    def __init__(self) -> None:
        super().__init__(timeout=None)

    @discord.ui.button(
        label="Close Ticket",
        style=discord.ButtonStyle.danger,
        custom_id=CLOSE_TICKET_ID,
        emoji="🔒",
    )
    async def close_ticket(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        bot: DotxBot = interaction.client  # type: ignore[assignment]
        await close_ticket_channel(bot, interaction)


def _is_ticket_staff(bot: DotxBot, member: discord.Member) -> bool:
    if member.guild_permissions.manage_channels or member.guild_permissions.administrator:
        return True
    staff_ids = set(bot.cfg.ticket_staff_role_ids)
    return any(role.id in staff_ids for role in member.roles)


async def open_ticket_for_member(bot: DotxBot, interaction: discord.Interaction) -> None:
    if not interaction.guild or not isinstance(interaction.user, discord.Member):
        await interaction.response.send_message("Tickets only work inside a server.", ephemeral=True)
        return

    if bot.cfg.ticket_category_id == 0:
        await interaction.response.send_message("Ticket category is not configured.", ephemeral=True)
        return

    existing = _find_open_ticket(bot, interaction.user.id)
    if existing:
        channel = interaction.guild.get_channel(existing)
        if isinstance(channel, discord.TextChannel):
            await interaction.response.send_message(
                f"You already have an open ticket: {channel.mention}",
                ephemeral=True,
            )
            return
        _ticket_state(bot).pop(str(interaction.user.id), None)
        bot.save_state()

    category = interaction.guild.get_channel(bot.cfg.ticket_category_id)
    if not isinstance(category, discord.CategoryChannel):
        await interaction.response.send_message("Ticket category was not found.", ephemeral=True)
        return

    await interaction.response.defer(ephemeral=True)

    ticket_no = _next_ticket_number(bot, interaction.guild)
    safe_name = "".join(c for c in interaction.user.name.lower() if c.isalnum())[:12] or "user"
    channel_name = f"ticket-{ticket_no:04d}-{safe_name}"

    overwrites: dict[discord.abc.Snowflake, discord.PermissionOverwrite] = {
        interaction.guild.default_role: discord.PermissionOverwrite(view_channel=False),
        interaction.user: discord.PermissionOverwrite(
            view_channel=True,
            send_messages=True,
            attach_files=True,
            read_message_history=True,
        ),
        interaction.guild.me: discord.PermissionOverwrite(
            view_channel=True,
            send_messages=True,
            manage_channels=True,
            manage_messages=True,
        ),
    }
    for role_id in bot.cfg.ticket_staff_role_ids:
        role = interaction.guild.get_role(role_id)
        if role:
            overwrites[role] = discord.PermissionOverwrite(
                view_channel=True,
                send_messages=True,
                read_message_history=True,
            )

    try:
        channel = await interaction.guild.create_text_channel(
            name=channel_name,
            category=category,
            overwrites=overwrites,
            reason=f"Ticket opened by {interaction.user}",
        )
    except (discord.Forbidden, discord.HTTPException) as exc:
        # Keep the counter advanced so numbering never rewinds.
        await interaction.followup.send(
            f"Could not create ticket channel: {exc}",
            ephemeral=True,
        )
        return

    _ticket_state(bot)[str(interaction.user.id)] = channel.id
    bot.save_state()

    accent = bot.cfg.brand.accent_hex
    color = int(accent.replace("#", ""), 16) if accent.startswith("#") else 0x00D4AA

    embed = discord.Embed(
        title=f"Ticket #{ticket_no:04d}",
        description=(
            f"Thanks {interaction.user.mention} — support will be with you shortly.\n\n"
            "Describe your issue below. Staff can close this ticket when you're done."
        ),
        color=color,
    )
    embed.set_footer(text=bot.cfg.brand.footer_text or "dotx support")

    await channel.send(content=interaction.user.mention, embed=embed, view=TicketCloseView())
    await interaction.followup.send(f"Ticket created: {channel.mention}", ephemeral=True)

    log_channel = interaction.guild.get_channel(bot.cfg.ticket_log_channel_id)
    if isinstance(log_channel, discord.TextChannel):
        log_embed = discord.Embed(
            title="Ticket opened",
            description=f"{interaction.user.mention} opened {channel.mention}",
            color=color,
        )
        await log_channel.send(embed=log_embed)


async def close_ticket_channel(bot: DotxBot, interaction: discord.Interaction) -> None:
    if not interaction.guild or not isinstance(interaction.channel, discord.TextChannel):
        await interaction.response.send_message("This button only works inside a ticket channel.", ephemeral=True)
        return
    if not isinstance(interaction.user, discord.Member):
        await interaction.response.send_message("Could not verify your permissions.", ephemeral=True)
        return

    channel = interaction.channel
    ticket_owner_id = None
    for user_id, channel_id in list(_ticket_state(bot).items()):
        if int(channel_id) == channel.id:
            ticket_owner_id = int(user_id)
            break

    is_owner = ticket_owner_id == interaction.user.id
    if not is_owner and not _is_ticket_staff(bot, interaction.user):
        await interaction.response.send_message("Only ticket staff can close this ticket.", ephemeral=True)
        return

    # Keep numbering continuous even after close — raise counter to this ticket if higher.
    closed_no = _ticket_number_from_name(channel.name)
    if closed_no is not None:
        current = int(bot.state.get("ticket_counter", 0) or 0)
        if closed_no > current:
            bot.state["ticket_counter"] = closed_no
            bot.save_state()

    await interaction.response.send_message("Closing ticket in 3 seconds…", ephemeral=True)

    log_channel = interaction.guild.get_channel(bot.cfg.ticket_log_channel_id)
    if isinstance(log_channel, discord.TextChannel):
        embed = discord.Embed(
            title="Ticket closed",
            description=f"{channel.mention} closed by {interaction.user.mention}",
            color=0xF87171,
        )
        await log_channel.send(embed=embed)

    if ticket_owner_id is not None:
        _ticket_state(bot).pop(str(ticket_owner_id), None)
        bot.save_state()

    await channel.send("🔒 Ticket closed.")
    await channel.delete(reason=f"Ticket closed by {interaction.user}")


class TicketCog(commands.Cog):
    def __init__(self, bot: DotxBot) -> None:
        self.bot = bot

    @commands.Cog.listener()
    async def on_ready(self) -> None:
        guild = self.bot.get_guild(self.bot.cfg.guild_id) if self.bot.cfg.guild_id else None
        synced = sync_ticket_counter(self.bot, guild)
        print(f"[dotx] Ticket counter synced at {synced} (next ticket will be {synced + 1:04d})")

    @app_commands.command(name="ticket-panel", description="Post the support ticket panel in this channel")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def ticket_panel(self, interaction: discord.Interaction) -> None:
        if not isinstance(interaction.channel, discord.TextChannel):
            await interaction.response.send_message("Run this in a text channel.", ephemeral=True)
            return
        accent = self.bot.cfg.brand.accent_hex
        color = int(accent.replace("#", ""), 16) if accent.startswith("#") else 0x00D4AA
        embed = discord.Embed(
            title="Support Tickets",
            description=(
                "Need help with **dotx**, billing, or PC checks?\n\n"
                "Click **Open Ticket** below and our team will assist you in a private channel."
            ),
            color=color,
        )
        embed.set_footer(text=self.bot.cfg.brand.footer_text or "dotx support")
        await interaction.channel.send(embed=embed, view=TicketPanelView())
        await interaction.response.send_message("Ticket panel posted.", ephemeral=True)

    @commands.command(name="ticketpanel")
    @commands.has_permissions(manage_guild=True)
    async def ticket_panel_prefix(self, ctx: commands.Context) -> None:
        if not isinstance(ctx.channel, discord.TextChannel):
            return
        accent = self.bot.cfg.brand.accent_hex
        color = int(accent.replace("#", ""), 16) if accent.startswith("#") else 0x00D4AA
        embed = discord.Embed(
            title="Support Tickets",
            description=(
                "Need help with **dotx**, billing, or PC checks?\n\n"
                "Click **Open Ticket** below and our team will assist you in a private channel."
            ),
            color=color,
        )
        embed.set_footer(text=self.bot.cfg.brand.footer_text or "dotx support")
        await ctx.send(embed=embed, view=TicketPanelView())
