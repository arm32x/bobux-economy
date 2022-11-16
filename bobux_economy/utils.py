from contextlib import closing
import sqlite3
from typing import Callable, Optional, TypeVar

import disnake
from disnake.ext import commands
from disnake.ui import ActionRow, MessageUIComponent

from bobux_economy.bot import BobuxEconomyBot

T = TypeVar("T")


async def wait_for_component(
    client: disnake.Client, action_row: ActionRow[MessageUIComponent]
) -> disnake.MessageInteraction:
    """
    Waits for a component interaction. Only accepts interactions based
    on the custom ID of the component.

    Adapted from the implementation in interactions.py legacy-v3.
    """

    custom_ids = [c.custom_id for c in action_row.children if c.custom_id is not None]

    def _check(ctx: disnake.MessageInteraction):
        return ctx.data.custom_id in custom_ids

    return await client.wait_for("message_interaction", check=_check)


def get_admin_role_id(
    db_connection: sqlite3.Connection, guild_id: int
) -> Optional[int]:
    with closing(db_connection.cursor()) as db_cursor:
        db_cursor.execute("SELECT admin_role FROM guilds WHERE id = ?", (guild_id,))

        row: Optional[sqlite3.Row] = db_cursor.fetchone()
        if row is None:
            return None

        admin_role_id = row["admin_role"]
        if admin_role_id is None:
            return None

        return int(admin_role_id)


def has_admin_role() -> Callable[[T], T]:
    def predicate(ctx: commands.context.AnyContext) -> bool:
        # These checks are here to aid type checking.
        if ctx.guild is None or not isinstance(ctx.author, disnake.Member):
            raise commands.errors.NoPrivateMessage()
        if not isinstance(ctx.bot, BobuxEconomyBot):
            raise TypeError(f"Bot type must be BobuxEconomyBot, not '{type(ctx.bot).__name__}'")

        admin_role_id = get_admin_role_id(ctx.bot.db_connection, ctx.guild.id)
        if admin_role_id is not None:
            return any(r.id == admin_role_id for r in ctx.author.roles)
        else:
            return ctx.author.guild_permissions.manage_guild

    return commands.check(predicate)
