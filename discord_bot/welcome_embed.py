from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import discord


@dataclass(frozen=True)
class Brand:
    server_name: str
    accent_hex: str = "#FFD700"
    footer_text: str = ""
    banner_url: str = ""
    banner_path: str = ""
    logo_url: str = ""
    logo_path: str = ""


def _embed_color(brand: Brand) -> int:
    value = brand.accent_hex.strip().lstrip("#")
    if len(value) != 6:
        return 0xFFD700
    return int(value, 16)


def _apply_banner(embed: discord.Embed, brand: Brand) -> list[discord.File]:
    if brand.banner_url:
        embed.set_image(url=brand.banner_url)
        return []

    if brand.banner_path:
        path = Path(brand.banner_path)
        if path.is_file():
            banner = discord.File(str(path), filename="banner.png")
            embed.set_image(url="attachment://banner.png")
            return [banner]

    return []


def build_welcome_message(
    *,
    brand: Brand,
    member: discord.Member | discord.User,
) -> tuple[str, discord.Embed, list[discord.File]]:
    name = brand.server_name
    content = f"Welcome to **{name}** {member.mention},"

    embed = discord.Embed(
        title=f"Welcome to {name}",
        description=(
            f"Welcome to **{name}**!\n"
            "We're glad to have you here. We are Selling Cheap and High-Quality Tools."
        ),
        color=_embed_color(brand),
    )
    embed.set_author(name=member.display_name, icon_url=member.display_avatar.url)
    embed.set_thumbnail(url=member.display_avatar.url)
    files = _apply_banner(embed, brand)

    return content, embed, files


def build_leave_message(
    *,
    brand: Brand,
    member: discord.Member | discord.User,
) -> tuple[str, discord.Embed, list[discord.File]]:
    name = brand.server_name
    content = f"Farewell from **{name}** {member.mention}! Wishing you all the best!"

    embed = discord.Embed(
        title=f"Goodbye to {name}",
        description=(
            f"{member.mention} has left **{name}**. "
            "Hope to see you again someday!"
        ),
        color=_embed_color(brand),
    )
    embed.set_author(name=member.display_name, icon_url=member.display_avatar.url)
    embed.set_thumbnail(url=member.display_avatar.url)
    files = _apply_banner(embed, brand)

    return content, embed, files
