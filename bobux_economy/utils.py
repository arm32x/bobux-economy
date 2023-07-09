from contextlib import asynccontextmanager
from typing import AsyncIterator, Callable, TypeVar

import aiosqlite
import disnake
from disnake.ext import commands
from disnake.ui import ActionRow, MessageUIComponent


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


class MissingAdminRole(commands.CheckFailure):
    """
    Exception raised when the command invoker does not have the admin
    role and it is required to run a command.

    This inherits from disnake’s CheckFailure.
    """

    admin_role_id: int

    def __init__(self, admin_role_id: int, *args):
        self.admin_role_id = admin_role_id

        message = f"You are missing <@&{admin_role_id}> role to run this command."
        super().__init__(message, *args)


def has_admin_role() -> Callable[[T], T]:
    # Must be here to prevent circular imports
    from bobux_economy.bot import BobuxEconomyBot

    async def predicate(ctx: commands.context.AnyContext) -> bool:
        # These checks are here to aid type checking.
        if ctx.guild is None or not isinstance(ctx.author, disnake.Member):
            raise commands.errors.NoPrivateMessage()
        if not isinstance(ctx.bot, BobuxEconomyBot):
            raise TypeError(
                f"Bot type must be BobuxEconomyBot, not '{type(ctx.bot).__name__}'"
            )

        admin_role_id = await ctx.bot.guild_config(ctx.guild).admin_role_id.get()
        if admin_role_id is not None:
            if not any(r.id == admin_role_id for r in ctx.author.roles):
                raise MissingAdminRole(admin_role_id)
        else:
            if not ctx.author.guild_permissions.manage_guild:
                raise commands.MissingPermissions(["manage_guild"])

        return True

    return commands.check(predicate)


class UserFacingError(RuntimeError):
    """An Exception type for user errors in commands, such as invalid input"""

    def __init__(self, message: str):
        super().__init__(message)


_transaction_level: int = 0


@asynccontextmanager
async def db_transaction(
    db_connection: aiosqlite.Connection,
) -> AsyncIterator[aiosqlite.Cursor]:
    # Keep track of the number of nested transactions.
    global _transaction_level
    _transaction_level += 1

    try:
        if _transaction_level > 1:
            # Use savepoints for nested transactions.
            await db_connection.execute(
                f"SAVEPOINT nested_transaction_{_transaction_level}"
            )
            async with db_connection.cursor() as db_cursor:
                yield db_cursor
        else:
            # Use regular transactions when no nesting is involved.
            await db_connection.execute("BEGIN")
            async with db_connection.cursor() as db_cursor:
                yield db_cursor
                await db_connection.commit()
    except:
        if _transaction_level > 1:
            await db_connection.execute(
                f"ROLLBACK TO SAVEPOINT nested_transaction_{_transaction_level}"
            )
        else:
            await db_connection.rollback()

        raise
    finally:
        _transaction_level -= 1
