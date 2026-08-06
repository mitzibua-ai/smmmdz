"""Product listing commands — smky product (prefix + slash)."""

from __future__ import annotations

import re
import uuid
from datetime import datetime, timezone
from typing import Any

import discord
from discord import app_commands
from discord.ext import commands

from discord_bot.bot import DotxBot
from discord_bot.license import _owner_ids
from discord_bot.tickets import _is_ticket_staff
from discord_bot.welcome_embed import _embed_color

PRODUCTS_STATE_KEY = "products"
EDIT_BUTTON_PREFIX = "dotx:product:edit:"
REMOVE_BUTTON_PREFIX = "dotx:product:remove:"

PLAN_LABELS = ("Monthly", "Yearly", "Lifetime")

_PENDING: dict[int, dict[str, Any]] = {}


def _is_product_staff(bot: DotxBot, member: discord.Member | discord.User | None) -> bool:
    if member is None:
        return False
    if str(member.id) in _owner_ids():
        return True
    if isinstance(member, discord.Member) and member.guild_permissions.administrator:
        return True
    if isinstance(member, discord.Member):
        return _is_ticket_staff(bot, member)
    return False


def _default_channel_ids(bot: DotxBot) -> list[int]:
    return list(bot.cfg.product_channel_ids)


def _channel_prompt_text(guild: discord.Guild | None, bot: DotxBot) -> str:
    defaults = _default_channel_ids(bot)
    if defaults and guild:
        mentions = ", ".join(f"<#{cid}>" for cid in defaults if guild.get_channel(cid))
        if mentions:
            return f"Suggested sell channels: {mentions}"
    return "Mention the channel like `#products` or paste the channel ID."


def _image_from_message(message: discord.Message) -> str | None:
    """Return image URL, empty string for skip, or None if input is invalid."""
    content = message.content.strip()
    if content.lower() == "skip":
        return ""

    if message.attachments:
        att = message.attachments[0]
        if att.content_type and att.content_type.startswith("image/"):
            return att.url
        if att.filename.lower().endswith((".png", ".jpg", ".jpeg", ".gif", ".webp")):
            return att.url

    if not content:
        return None

    if content.startswith("http://") or content.startswith("https://"):
        return content

    return None


def _resolve_post_channel(
    message: discord.Message,
    content: str,
) -> discord.TextChannel | discord.Thread | None:
    text = content.strip()
    if not text:
        return None

    if message.guild is None:
        return None

    match = re.search(r"<#(\d+)>", text)
    if match:
        ch = message.guild.get_channel(int(match.group(1)))
        if isinstance(ch, (discord.TextChannel, discord.Thread)):
            return ch

    if text.isdigit():
        ch = message.guild.get_channel(int(text))
        if isinstance(ch, (discord.TextChannel, discord.Thread)):
            return ch

    return None


def _products(bot: DotxBot) -> dict[str, dict[str, Any]]:
    state = bot.state.setdefault(PRODUCTS_STATE_KEY, {})
    if not isinstance(state, dict):
        state = {}
        bot.state[PRODUCTS_STATE_KEY] = state
    return state


def _short_id(product_id: str) -> str:
    return product_id[:8]


def _parse_price(text: str) -> str:
    cleaned = text.strip()
    if not cleaned:
        return "Contact for price"
    return cleaned


def _parse_plan(text: str) -> str | None:
    value = text.strip().lower()
    if value in {"monthly", "month", "m"}:
        return "Monthly"
    if value in {"yearly", "year", "y", "annual"}:
        return "Yearly"
    if value in {"lifetime", "life", "l", "permanent", "forever"}:
        return "Lifetime"
    return None


def _plan_prompt() -> str:
    return "What **plan** is this? Reply: `monthly`, `yearly`, or `lifetime`."


def _build_product_embed(product: dict[str, Any], *, bot: DotxBot) -> discord.Embed:
    embed = discord.Embed(
        title=product.get("title") or "Product",
        description=product.get("description") or "No description.",
        color=_embed_color(bot.cfg.brand),
        timestamp=datetime.now(timezone.utc),
    )
    plan = product.get("plan")
    if plan:
        embed.add_field(name="Plan", value=plan, inline=True)
    price = product.get("price")
    if price:
        embed.add_field(name="Price", value=price, inline=True)
    footer = product.get("footer") or "dotx.store"
    embed.set_footer(text=footer)
    image_url = product.get("image_url")
    if image_url:
        embed.set_image(url=image_url)
    return embed


class ProductEditModal(discord.ui.Modal, title="Edit product listing"):
    title_input = discord.ui.TextInput(
        label="Title",
        placeholder="Product name",
        max_length=256,
        required=True,
    )
    description_input = discord.ui.TextInput(
        label="Description",
        style=discord.TextStyle.paragraph,
        placeholder="Describe the product (supports Discord markdown)",
        max_length=4000,
        required=True,
    )
    price_input = discord.ui.TextInput(
        label="Price",
        placeholder="e.g. $25 / 500 PHP / Contact for price",
        max_length=120,
        required=False,
    )
    plan_input = discord.ui.TextInput(
        label="Plan",
        placeholder="Monthly, Yearly, or Lifetime",
        max_length=32,
        required=True,
    )
    image_input = discord.ui.TextInput(
        label="Image URL (optional)",
        placeholder="https://...",
        max_length=500,
        required=False,
    )
    footer_input = discord.ui.TextInput(
        label="Footer (optional)",
        placeholder="dotx.store",
        max_length=120,
        required=False,
    )

    def __init__(self, bot: DotxBot, product_id: str) -> None:
        super().__init__()
        self.bot = bot
        self.product_id = product_id
        products = _products(bot)
        product = products.get(product_id, {})
        self.title_input.default = product.get("title", "")
        self.description_input.default = product.get("description", "")
        self.price_input.default = product.get("price", "")
        self.plan_input.default = product.get("plan", "Monthly")
        self.image_input.default = product.get("image_url", "")
        self.footer_input.default = product.get("footer", "dotx.store")

    async def on_submit(self, interaction: discord.Interaction) -> None:
        if not _is_product_staff(self.bot, interaction.user):
            await interaction.response.send_message("Only staff can edit listings.", ephemeral=True)
            return

        products = _products(self.bot)
        product = products.get(self.product_id)
        if not product:
            await interaction.response.send_message("Listing not found.", ephemeral=True)
            return

        product["title"] = str(self.title_input.value).strip()
        product["description"] = str(self.description_input.value).strip()
        product["price"] = _parse_price(str(self.price_input.value or ""))
        plan = _parse_plan(str(self.plan_input.value or ""))
        if not plan:
            await interaction.response.send_message(
                "Plan must be **monthly**, **yearly**, or **lifetime**.",
                ephemeral=True,
            )
            return
        product["plan"] = plan
        image = str(self.image_input.value or "").strip()
        product["image_url"] = image if image.startswith("http") else ""
        footer = str(self.footer_input.value or "").strip()
        product["footer"] = footer or "dotx.store"
        product["updated_at"] = datetime.now(timezone.utc).isoformat()
        self.bot.save_state()

        await interaction.response.send_message(
            f"Updated listing `{_short_id(self.product_id)}`. Refreshing channel post…",
            ephemeral=True,
        )
        await refresh_product_message(self.bot, self.product_id)


class ProductListingView(discord.ui.View):
    def __init__(self, bot: DotxBot, product_id: str) -> None:
        super().__init__(timeout=None)
        self.bot = bot
        self.product_id = product_id

    @discord.ui.button(
        label="Edit listing",
        style=discord.ButtonStyle.secondary,
        emoji="✏️",
        custom_id=f"{EDIT_BUTTON_PREFIX}placeholder",
        row=0,
    )
    async def edit_button(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        if not _is_product_staff(self.bot, interaction.user):
            await interaction.response.send_message("Only staff can edit this listing.", ephemeral=True)
            return
        await interaction.response.send_modal(ProductEditModal(self.bot, self.product_id))

    @discord.ui.button(
        label="Remove listing",
        style=discord.ButtonStyle.danger,
        emoji="🗑️",
        custom_id=f"{REMOVE_BUTTON_PREFIX}placeholder",
        row=0,
    )
    async def remove_button(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        if not _is_product_staff(self.bot, interaction.user):
            await interaction.response.send_message("Only staff can remove this listing.", ephemeral=True)
            return
        await interaction.response.send_message("Removing listing…", ephemeral=True)
        await delete_product_listing(self.bot, self.product_id)


def product_listing_view(bot: DotxBot, product_id: str) -> ProductListingView:
    view = ProductListingView(bot, product_id)
    for item in view.children:
        if isinstance(item, discord.ui.Button):
            if item.label == "Edit listing":
                item.custom_id = f"{EDIT_BUTTON_PREFIX}{product_id}"
            elif item.label == "Remove listing":
                item.custom_id = f"{REMOVE_BUTTON_PREFIX}{product_id}"
    return view


async def delete_product_listing(bot: DotxBot, product_id: str) -> bool:
    products = _products(bot)
    product = products.get(product_id)
    if not product:
        return False

    message_id = product.get("message_id")
    channel_id = product.get("channel_id")
    if message_id and channel_id:
        channel = bot.get_channel(int(channel_id))
        if channel is None:
            try:
                channel = await bot.fetch_channel(int(channel_id))
            except (discord.HTTPException, discord.NotFound):
                channel = None
        if isinstance(channel, (discord.TextChannel, discord.Thread)):
            try:
                msg = await channel.fetch_message(int(message_id))
                await msg.delete()
            except (discord.HTTPException, discord.NotFound):
                pass

    del products[product_id]
    bot.save_state()
    return True


async def refresh_product_message(bot: DotxBot, product_id: str) -> bool:
    products = _products(bot)
    product = products.get(product_id)
    if not product:
        return False

    channel_id = product.get("channel_id")
    message_id = product.get("message_id")
    if not channel_id or not message_id:
        return False

    channel = bot.get_channel(int(channel_id))
    if channel is None:
        try:
            channel = await bot.fetch_channel(int(channel_id))
        except (discord.HTTPException, discord.NotFound):
            return False

    if not isinstance(channel, (discord.TextChannel, discord.Thread)):
        return False

    try:
        message = await channel.fetch_message(int(message_id))
    except (discord.HTTPException, discord.NotFound):
        return False

    embed = _build_product_embed(product, bot=bot)
    view = product_listing_view(bot, product_id)
    await message.edit(embed=embed, view=view)
    return True


async def post_product_to_channel(
    bot: DotxBot,
    product_id: str,
    channel: discord.abc.MessageableChannel,
) -> discord.Message | None:
    products = _products(bot)
    product = products.get(product_id)
    if not product:
        return None

    embed = _build_product_embed(product, bot=bot)
    view = product_listing_view(bot, product_id)

    existing_message_id = product.get("message_id")
    existing_channel_id = product.get("channel_id")
    if existing_message_id and existing_channel_id and int(existing_channel_id) != channel.id:
        old_channel = bot.get_channel(int(existing_channel_id))
        if isinstance(old_channel, (discord.TextChannel, discord.Thread)):
            try:
                old_msg = await old_channel.fetch_message(int(existing_message_id))
                await old_msg.delete()
            except (discord.HTTPException, discord.NotFound):
                pass

    if existing_message_id and existing_channel_id and int(existing_channel_id) == channel.id:
        try:
            if isinstance(channel, (discord.TextChannel, discord.Thread)):
                message = await channel.fetch_message(int(existing_message_id))
                await message.edit(embed=embed, view=view)
                product["posted_at"] = datetime.now(timezone.utc).isoformat()
                bot.save_state()
                return message
        except (discord.HTTPException, discord.NotFound):
            pass

    message = await channel.send(embed=embed, view=view)

    product["channel_id"] = channel.id
    product["message_id"] = message.id
    product["posted_at"] = datetime.now(timezone.utc).isoformat()
    bot.save_state()
    return message


def _product_help() -> str:
    return (
        "**smky product** — manage sell-channel listings\n"
        "• `smky product list` — your saved listings\n"
        "• `smky product new` — create a listing (title, description, price, plan, image, channel)\n"
        "• `smky product edit <id>` — edit a listing\n"
        "• `smky product post <id> [#channel]` — post or replace listing in a channel\n"
        "• `smky product delete <id>` — remove saved listing"
    )


def _list_products_text(bot: DotxBot) -> str:
    products = _products(bot)
    if not products:
        return "No product listings saved yet. Use `smky product new` to create one."

    lines = ["**Saved listings**"]
    for pid, item in sorted(products.items(), key=lambda x: x[1].get("created_at", ""), reverse=True):
        title = item.get("title") or "Untitled"
        plan = item.get("plan") or "—"
        posted = "posted" if item.get("message_id") else "draft"
        lines.append(f"• `{_short_id(pid)}` — **{title}** ({plan}, {posted})")
    return "\n".join(lines)


async def _resolve_channel(
    ctx: commands.Context,
    channel_text: str | None,
) -> discord.abc.MessageableChannel | None:
    if channel_text:
        match = re.search(r"<#(\d+)>", channel_text)
        if match:
            ch = ctx.guild.get_channel(int(match.group(1))) if ctx.guild else None
            if ch:
                return ch
        if channel_text.isdigit():
            ch = ctx.guild.get_channel(int(channel_text)) if ctx.guild else None
            if ch:
                return ch

    if isinstance(ctx.channel, (discord.TextChannel, discord.Thread)):
        return ctx.channel

    defaults = _default_channel_ids(ctx.bot)
    if defaults and ctx.guild:
        ch = ctx.guild.get_channel(defaults[0])
        if ch:
            return ch
    return None


def _find_product_by_short(bot: DotxBot, short: str) -> tuple[str, dict[str, Any]] | None:
    short = short.strip().lower()
    products = _products(bot)
    for pid, item in products.items():
        if pid.lower().startswith(short) or _short_id(pid).lower() == short:
            return pid, item
    return None


class ProductCog(commands.Cog):
    def __init__(self, bot: DotxBot) -> None:
        self.bot = bot

    async def _handle_prefix_command(self, message: discord.Message) -> bool:
        content = message.content.strip()
        lower = content.lower()
        if not lower.startswith("smky product"):
            return False

        if not _is_product_staff(self.bot, message.author):
            await message.reply("Only staff can manage product listings.", mention_author=False)
            return True

        rest = content[len("smky product") :].strip()
        parts = rest.split() if rest else []
        sub = parts[0].lower() if parts else ""

        if not sub:
            await message.reply(_product_help(), mention_author=False)
            return True

        if sub == "list":
            await message.reply(_list_products_text(self.bot), mention_author=False)
            return True

        if sub == "new":
            _PENDING[message.author.id] = {
                "flow": "new_product",
                "step": "title",
                "channel_id": message.channel.id,
            }
            await message.reply(
                "Creating a new listing.\nSend the **product title** in this channel.",
                mention_author=False,
            )
            return True

        if sub == "edit" and len(parts) >= 2:
            found = _find_product_by_short(self.bot, parts[1])
            if not found:
                await message.reply(f"No listing found for `{parts[1]}`.", mention_author=False)
                return True
            product_id, product = found
            _PENDING[message.author.id] = {
                "flow": "edit_product",
                "product_id": product_id,
                "step": "title",
                "channel_id": message.channel.id,
            }
            await message.reply(
                f"Editing **{product.get('title', 'listing')}** (`{_short_id(product_id)}`).\n"
                "Send new **title** or type `skip` to keep current.",
                mention_author=False,
            )
            return True

        if sub == "post" and len(parts) >= 2:
            found = _find_product_by_short(self.bot, parts[1])
            if not found:
                await message.reply(f"No listing found for `{parts[1]}`.", mention_author=False)
                return True
            product_id, product = found
            channel_hint = " ".join(parts[2:]) if len(parts) > 2 else None
            ctx_channel = message.channel if isinstance(message.channel, (discord.TextChannel, discord.Thread)) else None
            target = None
            if channel_hint:
                match = re.search(r"<#(\d+)>", channel_hint)
                if match and message.guild:
                    target = message.guild.get_channel(int(match.group(1)))
            if target is None:
                target = ctx_channel
            if target is None and message.guild:
                defaults = _default_channel_ids(self.bot)
                if defaults:
                    target = message.guild.get_channel(defaults[0])
            if target is None:
                await message.reply("Could not resolve channel. Mention `#channel` or run in a text channel.", mention_author=False)
                return True
            if product.get("message_id"):
                ok = await refresh_product_message(self.bot, product_id)
                if ok:
                    await message.reply(f"Updated listing in <#{product['channel_id']}>.", mention_author=False)
                    return True
            msg = await post_product_to_channel(self.bot, product_id, target)
            if msg:
                await message.reply(f"Posted **{product.get('title')}** in {target.mention}.", mention_author=False)
            else:
                await message.reply("Failed to post listing.", mention_author=False)
            return True

        if sub == "delete" and len(parts) >= 2:
            found = _find_product_by_short(self.bot, parts[1])
            if not found:
                await message.reply(f"No listing found for `{parts[1]}`.", mention_author=False)
                return True
            product_id, product = found
            if await delete_product_listing(self.bot, product_id):
                await message.reply(f"Removed listing `{_short_id(product_id)}`.", mention_author=False)
            else:
                await message.reply(f"No listing found for `{parts[1]}`.", mention_author=False)
            return True

        await message.reply(_product_help(), mention_author=False)
        return True

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        if message.author.bot or not message.guild:
            return

        if await self._handle_prefix_command(message):
            return

        user_id = message.author.id
        pending = _PENDING.get(user_id)
        if not pending:
            return

        flow_channel_id = pending.get("channel_id")
        if flow_channel_id and message.channel.id != flow_channel_id:
            return

        if not _is_product_staff(self.bot, message.author):
            _PENDING.pop(user_id, None)
            return

        if not pending.get("channel_id"):
            pending["channel_id"] = message.channel.id

        try:
            await self._continue_product_flow(message, pending)
        except Exception as exc:
            print(f"[dotx] product flow error: {exc!r}")
            _PENDING.pop(user_id, None)
            await message.channel.send(
                f"Product flow failed: {exc}\nStart again with `smky product new`.",
                delete_after=20,
            )

    async def _continue_product_flow(self, message: discord.Message, pending: dict[str, Any]) -> None:
        user_id = message.author.id
        flow = pending.get("flow")
        step = pending.get("step")
        content = message.content.strip()

        if flow == "edit_product":
            product_id = pending.get("product_id")
            products = _products(self.bot)
            product = products.get(product_id or "")
            if not product:
                _PENDING.pop(user_id, None)
                await message.channel.send("Listing not found.", delete_after=8)
                return

            if step == "title":
                if content.lower() != "skip":
                    product["title"] = content[:256]
                pending["step"] = "description"
                await message.channel.send(
                    "Send new **description** (type `done` when finished) or `skip`.",
                    delete_after=20,
                )
                return

            if step == "description":
                if content.lower() == "skip":
                    pending["step"] = "price"
                    await message.channel.send("Send new **price** or `skip`.", delete_after=15)
                    return
                if content.lower() == "done":
                    lines = pending.get("description_lines", [])
                    if lines:
                        product["description"] = "\n".join(lines)
                    pending["step"] = "price"
                    await message.channel.send("Send new **price** or `skip`.", delete_after=15)
                    return
                lines = pending.setdefault("description_lines", [])
                lines.append(content)
                return

            if step == "price":
                if content.lower() != "skip":
                    product["price"] = _parse_price(content)
                pending["step"] = "plan"
                await message.channel.send(_plan_prompt(), delete_after=20)
                return

            if step == "plan":
                if content.lower() != "skip":
                    plan = _parse_plan(content)
                    if not plan:
                        await message.channel.send(
                            "Reply with `monthly`, `yearly`, or `lifetime` (or `skip`).",
                            delete_after=15,
                        )
                        return
                    product["plan"] = plan
                pending["step"] = "image"
                await message.channel.send(
                    "Send new **image URL**, **upload an image**, or type `skip`.",
                    delete_after=20,
                )
                return

            if step == "image":
                if content.lower() != "skip":
                    image = _image_from_message(message)
                    if image is None:
                        await message.channel.send(
                            "Send an **image URL**, **upload an image**, or type `skip`.",
                            delete_after=20,
                        )
                        return
                    product["image_url"] = image
                product["updated_at"] = datetime.now(timezone.utc).isoformat()
                self.bot.save_state()
                _PENDING.pop(user_id, None)
                refreshed = await refresh_product_message(self.bot, product_id)
                note = "Channel post updated." if refreshed else "Saved (not posted to a channel yet)."
                await message.channel.send(
                    f"Listing `{_short_id(product_id)}` updated. {note}",
                    delete_after=20,
                )
                return

        if flow != "new_product":
            return

        if step == "title":
            if not content:
                await message.channel.send("Send a product title.", delete_after=8)
                return
            pending["title"] = content[:256]
            pending["step"] = "description"
            await message.channel.send(
                "Send the **description** (supports markdown). Type `done` on a new line when finished.",
                delete_after=20,
            )
            return

        if step == "description":
            if content.lower() == "done":
                lines = pending.get("description_lines", [])
                if not lines:
                    await message.channel.send("Description cannot be empty.", delete_after=8)
                    return
                pending["description"] = "\n".join(lines)
                pending["step"] = "price"
                await message.channel.send("Send the **price** (e.g. `$25` or `500 PHP`).", delete_after=15)
                return
            lines = pending.setdefault("description_lines", [])
            lines.append(content)
            return

        if step == "price":
            pending["price"] = _parse_price(content)
            pending["step"] = "plan"
            await message.channel.send(_plan_prompt(), delete_after=30)
            return

        if step == "plan":
            plan = _parse_plan(content)
            if not plan:
                await message.channel.send(
                    "Reply with `monthly`, `yearly`, or `lifetime`.",
                    delete_after=20,
                )
                return
            pending["plan"] = plan
            pending["step"] = "image"
            await message.channel.send(
                "Send an **image URL**, **upload an image**, or type `skip`.",
                delete_after=30,
            )
            return

        if step == "image":
            image = _image_from_message(message)
            if image is None:
                await message.channel.send(
                    "Send an **image URL**, **upload an image**, or type `skip`.",
                    delete_after=20,
                )
                return
            pending["image_url"] = image
            pending["step"] = "channel"
            await message.channel.send(
                "Which **sell channel** should this listing be posted in?\n"
                f"{_channel_prompt_text(message.guild, self.bot)}",
                delete_after=60,
            )
            return

        if step == "channel":
            channel = _resolve_post_channel(message, content)
            if channel is None:
                await message.channel.send(
                    "Please mention the sell channel (example: `#products`) or paste the channel ID.\n"
                    f"{_channel_prompt_text(message.guild, self.bot)}",
                    delete_after=30,
                )
                return

            product_id = str(uuid.uuid4())
            products = _products(self.bot)
            products[product_id] = {
                "id": product_id,
                "title": pending.get("title", "Product"),
                "description": pending.get("description", ""),
                "price": pending.get("price", ""),
                "plan": pending.get("plan", "Monthly"),
                "image_url": pending.get("image_url", ""),
                "footer": "dotx.store",
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
            self.bot.save_state()
            _PENDING.pop(user_id, None)

            posted = await post_product_to_channel(self.bot, product_id, channel)
            if posted:
                await message.channel.send(
                    f"Posted **{products[product_id]['title']}** in {channel.mention} — ID `{_short_id(product_id)}`.\n"
                    f"Edit anytime: `smky product edit {_short_id(product_id)}`",
                    delete_after=25,
                )
            else:
                await message.channel.send("Failed to post listing.", delete_after=10)


def inject_product_commands(cog: Any) -> None:
    """Attach smky product subcommands to LicenseCog."""

    async def _staff_only(ctx: commands.Context) -> bool:
        if not _is_product_staff(cog.bot, ctx.author):
            await cog._reply_ephemeral(ctx, "Only staff can manage product listings.")
            return False
        return True

    @cog.smky_group.group(
        name="product",
        invoke_without_command=True,
        description="Product listings for sell channels",
    )
    @app_commands.describe(action="list, new, edit, post, or delete")
    async def smky_product_group(ctx: commands.Context) -> None:
        await cog._reply_ephemeral(ctx, _product_help())

    @smky_product_group.command(name="list", description="List saved product listings")
    async def smky_product_list(ctx: commands.Context) -> None:
        if not await _staff_only(ctx):
            return
        await cog._reply_ephemeral(ctx, _list_products_text(cog.bot))

    @smky_product_group.command(name="new", description="Create a new product listing")
    async def smky_product_new(ctx: commands.Context) -> None:
        if not await _staff_only(ctx):
            return
        _PENDING[ctx.author.id] = {
            "flow": "new_product",
            "step": "title",
            "channel_id": ctx.channel.id if ctx.channel else 0,
        }
        await cog._reply_ephemeral(
            ctx,
            "Creating a new listing.\nSend the **product title** in this channel.",
        )

    @smky_product_group.command(name="edit", description="Edit an existing listing")
    @app_commands.describe(listing_id="Short listing ID from smky product list")
    async def smky_product_edit(ctx: commands.Context, listing_id: str) -> None:
        if not await _staff_only(ctx):
            return
        found = _find_product_by_short(cog.bot, listing_id)
        if not found:
            await cog._reply_ephemeral(ctx, f"No listing found for `{listing_id}`.")
            return
        product_id, _ = found
        if ctx.interaction:
            await ctx.interaction.response.send_modal(ProductEditModal(cog.bot, product_id))
        else:
            _PENDING[ctx.author.id] = {
                "flow": "edit_product",
                "product_id": product_id,
                "step": "title",
                "channel_id": ctx.channel.id if ctx.channel else 0,
            }
            await cog._reply_ephemeral(
                ctx,
                f"Editing **{found[1].get('title', 'listing')}**.\n"
                "Send new **title** in this channel or type `skip`.",
            )

    @smky_product_group.command(name="post", description="Post or refresh a listing in a channel")
    @app_commands.describe(
        listing_id="Short listing ID",
        channel="Sell channel (defaults to current or configured channel)",
    )
    async def smky_product_post(
        ctx: commands.Context,
        listing_id: str,
        channel: discord.TextChannel | None = None,
    ) -> None:
        if not await _staff_only(ctx):
            return
        found = _find_product_by_short(cog.bot, listing_id)
        if not found:
            await cog._reply_ephemeral(ctx, f"No listing found for `{listing_id}`.")
            return
        product_id, product = found

        target = channel
        if target is None:
            extra = ctx.message.content if ctx.message else ""
            parts = extra.split()
            channel_hint = parts[3] if len(parts) > 3 else None
            target = await _resolve_channel(ctx, channel_hint)

        if target is None:
            await cog._reply_ephemeral(ctx, "Could not resolve channel. Mention `#channel` or use slash channel option.")
            return

        if product.get("message_id"):
            ok = await refresh_product_message(cog.bot, product_id)
            if ok:
                await cog._reply_ephemeral(ctx, f"Updated listing in <#{product['channel_id']}>.")
                return

        msg = await post_product_to_channel(cog.bot, product_id, target)
        if msg:
            await cog._reply_ephemeral(ctx, f"Posted **{product.get('title')}** in {target.mention}.")
        else:
            await cog._reply_ephemeral(ctx, "Failed to post listing.")

    @smky_product_group.command(name="delete", description="Delete a saved listing")
    @app_commands.describe(listing_id="Short listing ID")
    async def smky_product_delete(ctx: commands.Context, listing_id: str) -> None:
        if not await _staff_only(ctx):
            return
        found = _find_product_by_short(cog.bot, listing_id)
        if not found:
            await cog._reply_ephemeral(ctx, f"No listing found for `{listing_id}`.")
            return
        product_id, product = found

        if await delete_product_listing(cog.bot, product_id):
            await cog._reply_ephemeral(ctx, f"Removed listing `{_short_id(product_id)}`.")
        else:
            await cog._reply_ephemeral(ctx, f"Could not remove listing `{_short_id(product_id)}`.")


async def setup_product_commands(bot: DotxBot) -> None:
    await bot.add_cog(ProductCog(bot))

    for product_id, product in _products(bot).items():
        if product.get("message_id"):
            bot.add_view(product_listing_view(bot, product_id))

    print("[dotx] Product commands loaded: smky product list/new/edit/post/delete")

