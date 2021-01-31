import sqlite3
from typing import *

import discord
from discord.ext import commands

from . import balance
from . import database


cursor = database.connection.cursor()
database.initialize(cursor)


def determine_prefix(_, message: discord.Message) -> str:
    cursor.execute("SELECT prefix FROM guilds WHERE id = ?;", (message.guild.id, ))
    guild_row: Optional[tuple[str]] = cursor.fetchone()
    if guild_row is None:
        return "b$"
    else:
        return guild_row[0]

bot = commands.Bot(command_prefix=determine_prefix)


@bot.event
async def on_ready():
    print("Ready.")

@bot.event
async def on_command_error(ctx: commands.Context, error: commands.CommandError):
    await ctx.send(f"**Error:** {error}")
    raise error


def author_can_manage_guild(ctx: commands.Context) -> bool:
    return cast(ctx.author.permissions_in(ctx.channel).manage_guild, bool)

def author_has_admin_role(ctx: commands.Context) -> bool:
    cursor.execute("SELECT admin_role FROM guilds WHERE id = ?;", (ctx.guild.id, ))
    row: tuple[Optional[int]] = cursor.fetchone() or (None, )
    admin_role = ctx.guild.get_role(row[0])
    if admin_role is not None:
        return admin_role in ctx.author.roles
    else:
        return author_can_manage_guild(ctx)

@bot.group()
@commands.guild_only()
async def config(ctx: commands.Context):
    if ctx.invoked_subcommand is None:
        raise commands.CommandError("Please specify an option to configure.")

@config.command(name="prefix")
@commands.check(author_can_manage_guild)
async def config_prefix(ctx: commands.Context, new_prefix: str):
    cursor.execute("""
        INSERT INTO guilds(id, prefix) VALUES(?, ?)
            ON CONFLICT(id) DO UPDATE SET prefix = excluded.prefix;
    """, (ctx.guild.id, new_prefix))
    database.connection.commit()
    await ctx.send(f"Updated prefix to `{new_prefix}`.")

@config.command(name="admin_role")
@commands.check(author_has_admin_role)
async def config_admin_role(ctx: commands.Context, role: discord.Role):
    cursor.execute("""
        INSERT INTO guilds(id, admin_role) VALUES(?, ?)
            ON CONFLICT(id) DO UPDATE SET admin_role = excluded.admin_role;
    """, (ctx.guild.id, role.id))
    database.connection.commit()
    await ctx.send(f"Set admin role to {role.mention}.")


@bot.group()
@commands.guild_only()
async def bal(ctx: commands.Context):
    if ctx.invoked_subcommand is None:
        await bal_check(ctx)

# TODO: Generate bobux memes to show balance.
@bal.command(name="check")
async def bal_check(ctx: commands.Context, target: Optional[discord.Member] = None):
    target = target or ctx.author

    amount, spare_change = balance.get(target)

    if spare_change:
        await ctx.send(f"{target.mention}: {amount} bobux and some spare change")
    else:
        await ctx.send(f"{target.mention}: {amount} bobux")

@bal.command(name="set")
@commands.check(author_has_admin_role)
async def bal_set(ctx: commands.Context, target: discord.Member, amount: float):
    amount, spare_change = balance.from_float(amount)
    balance.set(target, amount, spare_change)
    database.connection.commit()

    if spare_change:
        await ctx.send(f"{target.mention}: {amount} bobux and some spare change")
    else:
        await ctx.send(f"{target.mention}: {amount} bobux")

@bal.command(name="add")
@commands.check(author_has_admin_role)
async def bal_add(ctx: commands.Context, target: discord.Member, amount: float):
    balance.add(target, *balance.from_float(amount))
    database.connection.commit()

    await bal_check(ctx, target)

@bal.command(name="sub")
@commands.check(author_has_admin_role)
async def bal_sub(ctx: commands.Context, target: discord.Member, amount: float):
    balance.subtract(target, *balance.from_float(amount))
    database.connection.commit()

    await bal_check(ctx, target)


@bot.command()
@commands.guild_only()
async def pay(ctx: commands.Context, recipient: discord.Member, amount: float):
    try:
        amount, spare_change = balance.from_float(amount)
        balance.subtract(ctx.author, amount, spare_change)
        balance.add(recipient, amount, spare_change)
    except sqlite3.Error:
        database.connection.rollback()
        raise
    else:
        database.connection.commit()

    await bal_check(ctx)
    await bal_check(ctx, recipient)


try:
    with open("token.txt", "r") as token_file:
        token = token_file.read()
        bot.run(token)
except KeyboardInterrupt:
    print("Stopping...")
    database.connection.close()
