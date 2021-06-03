"""
bobux economy v0.3.1
  - fix removing votes not updating balances

bobux economy v0.3.0
  - fix upvote and downvote reactions not appearing outside of the test server
  - upvote and downvote reactions now use unicode emojis
  - fixed issue where removing votes would generate infinite bobux
  - the bot no longer adds vote reactions to its own messages

bobux economy v0.2.0
  - add upvote and downvote buttons on messages in the memes channel
  - bobux are rewarded for upvotes and for voting on other people's posts
  - bobux are removed for receiving downvotes
  - negative balances are now allowed under certain circumstances

bobux economy v0.1.3
  - fix normal users being allowed to change prefix

bobux economy v0.1.2
  - fix -0.5 being interpreted as 0.5

bobux economy v0.1.1
  - fix theft by paying negative amounts
  - add help information to commands
  - add version information and changelog

bobux economy v0.1.0
  - initial release
"""

import logging
import sqlite3
from typing import *

import discord
from discord.ext import commands

import balance
import database
from database import connection as db
from globals import bot
import upvotes

logging.basicConfig(format="%(levelname)8s [%(name)s] %(message)s", level=logging.DEBUG)

logging.debug("Initializing...")
database.migrate()

@bot.event
async def on_ready():
    logging.info("Synchronizing votes...")
    await upvotes.sync_votes()
    logging.info("Done!")

@bot.event
async def on_message(message: discord.Message):
    if message.author == bot.user:
        return

    c = db.cursor()
    c.execute("SELECT memes_channel FROM guilds WHERE id = ?;", (message.guild.id, ))
    memes_channel_id = (c.fetchone() or (None, ))[0]
    if memes_channel_id is not None and message.channel.id == memes_channel_id:
        await upvotes.add_reactions(message)
        c.execute("""
            INSERT INTO guilds(id, last_memes_message) VALUES (?, ?)
                ON CONFLICT(id) DO UPDATE SET last_memes_message = excluded.last_memes_message;
        """, (message.guild.id, message.id))
        db.commit()

    # This is required or else the entire bot ceases to function.
    await bot.process_commands(message)

@bot.event
async def on_raw_reaction_add(payload: discord.RawReactionActionEvent):
    if payload.user_id == bot.user.id:
        # This reaction was added by the bot, ignore it.
        return

    if payload.member is not None:
        c = db.cursor()
        c.execute("SELECT memes_channel FROM guilds WHERE id = ?;", (payload.guild_id, ))
        memes_channel_id = (c.fetchone() or (None, ))[0]

        if payload.channel_id == memes_channel_id:
            vote = None
            if payload.emoji.name == upvotes.UPVOTE_EMOJI:
                vote = upvotes.Vote.UPVOTE
            elif payload.emoji.name == upvotes.DOWNVOTE_EMOJI:
                vote = upvotes.Vote.DOWNVOTE

            if vote is not None:
                message = await bot.get_channel(payload.channel_id).fetch_message(payload.message_id)

                if payload.user_id == message.author.id:
                    # The poster voted on their own message.
                    await upvotes.remove_extra_reactions(message, payload.member, None)
                    return

                await upvotes.record_vote(payload.message_id, payload.channel_id, payload.member.id, vote)
                await upvotes.remove_extra_reactions(message, payload.member, vote)

@bot.event
async def on_raw_reaction_remove(payload: discord.RawReactionActionEvent):
    if payload.user_id == bot.user.id:
        # The removed reaction was from the bot.
        return

    if payload.guild_id is not None:
        c = db.cursor()
        c.execute("SELECT memes_channel FROM guilds WHERE id = ?;", (payload.guild_id, ))
        memes_channel_id = (c.fetchone() or (None, ))[0]

        if payload.channel_id == memes_channel_id:
            vote = None
            if payload.emoji.name == upvotes.UPVOTE_EMOJI:
                vote = upvotes.Vote.UPVOTE
            elif payload.emoji.name == upvotes.DOWNVOTE_EMOJI:
                vote = upvotes.Vote.DOWNVOTE

            if vote is not None:
                if (payload.message_id, vote, payload.user_id) in upvotes.recently_removed_reactions:
                    upvotes.recently_removed_reactions.remove((payload.message_id, vote, payload.user_id))
                    return

                message = await bot.get_channel(payload.channel_id).fetch_message(payload.message_id)
                await upvotes.delete_vote(payload.message_id, payload.channel_id, payload.user_id, check_equal_to=vote)
                user = bot.get_user(payload.user_id)
                if user is None:
                    user = await bot.fetch_user(payload.user_id)
                await upvotes.remove_extra_reactions(message, user, None)

@bot.event
async def on_command_error(ctx: commands.Context, error: commands.CommandError):
    await ctx.send(f"**Error:** {error}")
    raise error


def author_can_manage_guild(ctx: commands.Context) -> bool:
    return bool(ctx.author.permissions_in(ctx.channel).manage_guild)

def author_has_admin_role(ctx: commands.Context) -> bool:
    c = db.cursor()
    c.execute("SELECT admin_role FROM guilds WHERE id = ?;", (ctx.guild.id, ))
    row: Tuple[Optional[int]] = c.fetchone() or (None, )
    admin_role = ctx.guild.get_role(row[0])
    if admin_role is not None:
        return admin_role in ctx.author.roles
    else:
        return author_can_manage_guild(ctx)


@bot.command()
async def version(ctx: commands.Context):
    """Check the version of the bot."""

    if ctx.invoked_subcommand is None:
        await ctx.send(__doc__.strip().partition("\n")[0].strip())

@bot.command()
async def changelog(ctx: commands.Context):
    """Show the changelog of the bot."""

    await ctx.send(f"```{__doc__.strip()}```")


@bot.group()
@commands.guild_only()
async def config(ctx: commands.Context):
    """Change the settings of the bot."""

    if ctx.invoked_subcommand is None:
        raise commands.CommandError("Please specify an option to configure.")

@config.command(name="prefix")
@commands.check(cast("commands._CheckPredicate", author_can_manage_guild))
async def config_prefix(ctx: commands.Context, new_prefix: str):
    """Change the command prefix."""

    c = db.cursor()
    c.execute("""
        INSERT INTO guilds(id, prefix) VALUES(?, ?)
            ON CONFLICT(id) DO UPDATE SET prefix = excluded.prefix;
    """, (ctx.guild.id, new_prefix))
    db.commit()
    await ctx.send(f"Updated prefix to `{new_prefix}`.")

@config.command(name="admin_role")
@commands.check(cast("commands._CheckPredicate", author_has_admin_role))
async def config_admin_role(ctx: commands.Context, role: discord.Role):
    """Change which role is required to modify balances."""

    c = db.cursor()
    c.execute("""
        INSERT INTO guilds(id, admin_role) VALUES(?, ?)
            ON CONFLICT(id) DO UPDATE SET admin_role = excluded.admin_role;
    """, (ctx.guild.id, role.id))
    db.commit()
    await ctx.send(f"Set admin role to {role.mention}.")

@config.command(name="memes_channel")
@commands.check(cast("commands._CheckPredicate", author_can_manage_guild))
async def config_memes_channel(ctx: commands.Context, channel: discord.TextChannel):
    """Set the channel where upvote reactions are enabled."""

    c = db.cursor()
    c.execute("""
        INSERT INTO guilds(id, memes_channel) VALUES(?, ?)
            ON CONFLICT(id) DO UPDATE SET memes_channel = excluded.memes_channel;
    """, (ctx.guild.id, channel.id))
    db.commit()
    await ctx.send(f"Set memes channel to {channel.mention}.")


@bot.group()
@commands.guild_only()
async def bal(ctx: commands.Context):
    """Check your balance."""

    if ctx.invoked_subcommand is None:
        await bal_check(ctx)

# TODO: Generate bobux memes to show balance.
@bal.command(name="check")
async def bal_check(ctx: commands.Context, target: Optional[discord.Member] = None):
    """Check the balance of yourself or someone else."""

    target = target or ctx.author

    amount, spare_change = balance.get(target)
    if spare_change:
        await ctx.send(f"{target.mention}: {amount} bobux and some spare change")
    else:
        await ctx.send(f"{target.mention}: {amount} bobux")

@bal.command(name="set")
@commands.check(cast("commands._CheckPredicate", author_has_admin_role))
async def bal_set(ctx: commands.Context, target: discord.Member, amount: float):
    """Set someone's balance."""

    amount, spare_change = balance.from_float(amount)
    balance.set(target, amount, spare_change)
    db.commit()

    if spare_change:
        await ctx.send(f"{target.mention}: {amount} bobux and some spare change")
    else:
        await ctx.send(f"{target.mention}: {amount} bobux")

@bal.command(name="add")
@commands.check(cast("commands._CheckPredicate", author_has_admin_role))
async def bal_add(ctx: commands.Context, target: discord.Member, amount: float):
    """Add bobux to someone's balance."""

    balance.add(target, *balance.from_float(amount))
    db.commit()

    await bal_check(ctx, target)

@bal.command(name="sub")
@commands.check(cast("commands._CheckPredicate", author_has_admin_role))
async def bal_sub(ctx: commands.Context, target: discord.Member, amount: float):
    """Remove bobux from someone's balance."""

    balance.subtract(target, *balance.from_float(amount), allow_overdraft=True)
    db.commit()

    await bal_check(ctx, target)


@bot.command()
@commands.guild_only()
async def pay(ctx: commands.Context, recipient: discord.Member, amount: float):
    """Pay someone."""

    try:
        amount, spare_change = balance.from_float(amount)
        balance.subtract(ctx.author, amount, spare_change)
        balance.add(recipient, amount, spare_change)
    except sqlite3.Error:
        db.rollback()
        raise
    else:
        db.commit()

    await bal_check(ctx)
    await bal_check(ctx, recipient)


try:
    with open("data/token.txt", "r") as token_file:
        token = token_file.read()
        bot.run(token)
except KeyboardInterrupt:
    print("Stopping...")
    db.close()
