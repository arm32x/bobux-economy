import asyncio
from datetime import datetime, timezone
import logging
import random
import sqlite3
from typing import cast, Dict, List, Optional, Tuple, Union

import disnake as discord
from disnake.ext import commands

from bobux_economy import balance
from bobux_economy import database
from bobux_economy.database import connection as db
from bobux_economy.globals import client, UserFacingError
from bobux_economy import real_estate
from bobux_economy import subscriptions
from bobux_economy import upvotes
from bobux_economy import utils

logging.basicConfig(format="%(levelname)8s [%(name)s] %(message)s", level=logging.INFO)

logging.info("Initializing...")
database.migrate()

client.load_extension("bobux_economy.cogs.bal")
client.load_extension("bobux_economy.cogs.bot_info")
client.load_extension("bobux_economy.cogs.config")
client.load_extension("bobux_economy.cogs.real_estate")
client.load_extension("bobux_economy.cogs.relocate")

@client.event
async def on_ready():
    logging.info("Synchronizing votes...")
    await upvotes.sync_votes()
    logging.info("Starting subscriptions background task...")
    asyncio.create_task(subscriptions.run())
    logging.info("Ready!")

@client.event
async def on_message(message: discord.Message):
    if message.author == client.user or message.guild is None:
        return

    if upvotes.message_eligible(message):
        await upvotes.add_reactions(message)
        c = db.cursor()
        c.execute("""
            INSERT INTO guilds(id, last_memes_message) VALUES (?, ?)
                ON CONFLICT(id) DO UPDATE SET last_memes_message = excluded.last_memes_message;
        """, (message.guild.id, message.id))
        db.commit()

@client.event
async def on_raw_reaction_add(payload: discord.RawReactionActionEvent):
    if payload.user_id == client.user.id:
        # This reaction was added by the bot, ignore it.
        return
    if payload.guild_id is None:
        return

    channel = client.get_channel(payload.channel_id)
    if not isinstance(channel, discord.abc.Messageable):
        logging.error("Reaction added in non-messageable channel (how?)")
        return

    message = await channel.fetch_message(payload.message_id)
    if not upvotes.message_eligible(message):
        return

    if payload.member is None:
        return

    if payload.emoji.name == upvotes.UPVOTE_EMOJI:
        vote = upvotes.Vote.UPVOTE
    elif payload.emoji.name == upvotes.DOWNVOTE_EMOJI:
        vote = upvotes.Vote.DOWNVOTE
    else:
        return

    guild = client.get_guild(payload.guild_id) or message.guild
    if guild is None:
        return

    original_author = await upvotes.get_original_author(message, guild)
    if original_author is None:
        return

    if payload.user_id == original_author.id:
        # The poster voted on their own message.
        await upvotes.remove_extra_reactions(message, payload.member, None)
        return

    await upvotes.record_vote(payload.message_id, payload.channel_id, payload.member.id, vote)
    await upvotes.remove_extra_reactions(message, payload.member, vote)

@client.event
async def on_raw_reaction_remove(payload: discord.RawReactionActionEvent):
    if payload.user_id == client.user.id:
        # The removed reaction was from the bot.
        return

    channel = client.get_channel(payload.channel_id)
    if not isinstance(channel, discord.abc.Messageable):
        logging.error("Reaction removed in non-messageable channel (how?)")
        return
    
    message = await channel.fetch_message(payload.message_id)
    if not upvotes.message_eligible(message):
        return

    if payload.emoji.name == upvotes.UPVOTE_EMOJI:
        vote = upvotes.Vote.UPVOTE
    elif payload.emoji.name == upvotes.DOWNVOTE_EMOJI:
        vote = upvotes.Vote.DOWNVOTE
    else:
        return

    if (payload.message_id, vote, payload.user_id) in upvotes.recently_removed_reactions:
        upvotes.recently_removed_reactions.remove((payload.message_id, vote, payload.user_id))
        return

    await upvotes.delete_vote(payload.message_id, payload.channel_id, payload.user_id, check_equal_to=vote)
    user = client.get_user(payload.user_id) or await client.fetch_user(payload.user_id)
    await upvotes.remove_extra_reactions(message, user, None)

async def handle_interaction_error(ctx: discord.Interaction, ex: Exception):
    if isinstance(ex, commands.CommandInvokeError):
        ex = ex.original
    if isinstance(ex, (UserFacingError, commands.CommandError)):
        await ctx.send(f"**Error:** {ex}", ephemeral=True)
    else:
        error_id = random.randint(0, 65535)
        logging.error(f"Internal error {error_id}: {ex}", exc_info=ex)
        await ctx.send(f"**Error:** An internal error has occurred. If reporting this error, please provide the error ID {error_id}.", ephemeral=True)
    logging.info("Sent error feedback")


@client.event
async def on_slash_command_error(ctx: discord.ApplicationCommandInteraction, ex: Exception):
    await handle_interaction_error(ctx, ex)

@client.event
async def on_user_command_error(ctx: discord.UserCommandInteraction, ex: Exception):
    await handle_interaction_error(ctx, ex)

@client.event
async def on_message_command_error(ctx: discord.MessageCommandInteraction, ex: Exception):
    await handle_interaction_error(ctx, ex)


def check_author_can_manage_guild(ctx: discord.Interaction):
    if not isinstance(ctx.channel, discord.abc.GuildChannel) or not isinstance(ctx.author, discord.Member):
        raise UserFacingError("This command does not work in DMs")
    if not bool(ctx.channel.permissions_for(ctx.author).manage_guild):
        raise UserFacingError("You must have Manage Server permissions to use this command")

def check_author_can_manage_messages(ctx: discord.Interaction):
    if not isinstance(ctx.channel, discord.abc.GuildChannel) or not isinstance(ctx.author, discord.Member):
        raise UserFacingError("This command does not work in DMs")
    if not bool(ctx.channel.permissions_for(ctx.author).manage_messages):
        raise UserFacingError("You must have Manage Messages permissions to use this command")

def check_author_has_admin_role(ctx: discord.Interaction):
    if ctx.guild is None or not isinstance(ctx.author, discord.Member):
        raise UserFacingError("This command does not work in DMs")

    c = db.cursor()
    c.execute("SELECT admin_role FROM guilds WHERE id = ?;", (ctx.guild.id, ))
    row: Optional[Tuple[int]] = c.fetchone()
    admin_role = ctx.guild.get_role(row[0]) if row is not None else None
    if admin_role is not None:
        if not admin_role in ctx.author.roles:
            raise UserFacingError(f"You must have the {admin_role.mention} role to use this command")
    else:
        check_author_can_manage_guild(ctx)


@client.slash_command(
    name="subscriptions",
    description="Manage subscriptions"
)
async def subscriptions_cmd(_: discord.ApplicationCommandInteraction):
    pass

@subscriptions_cmd.sub_command(
    name="new",
    description="Create a new paid subscription in this server",
    options=[
        discord.Option(
            name="role",
            type=discord.OptionType.role,
            description="The role to grant to subscribers",
            required=True
        ),
        discord.Option(
            name="price_per_week",
            type=discord.OptionType.number,
            description="The price of this subscription, charged weekly",
            required=True
        )
    ]
)
async def subscriptions_new(ctx: discord.ApplicationCommandInteraction, role: discord.Role, price_per_week: float):
    check_author_has_admin_role(ctx)
    if ctx.guild is None:
        raise UserFacingError("This command does not work in DMs")

    price, spare_change = balance.from_float(float(price_per_week))

    c = db.cursor()
    c.execute("""
        INSERT INTO available_subscriptions VALUES (?, ?, ?, ?);
    """, (role.id, ctx.guild.id, price, spare_change))
    db.commit()

    await ctx.send(f"Created subscription for role {role.mention} for {balance.to_string(price, spare_change)} per week")

@subscriptions_cmd.sub_command_group(
    name="delete",
    description="Delete a paid subscription from this server. The role will not be revoked from current subscribers.",
    options=[
        discord.Option(
            name="role",
            type=discord.OptionType.role,
            description="The role of the subscription to delete",
            required=True
        )
    ]
)
async def subscriptions_delete(ctx: discord.ApplicationCommandInteraction, role: discord.Role):
    check_author_has_admin_role(ctx)

    c = db.cursor()
    c.execute("""
        SELECT EXISTS(SELECT 1 FROM available_subscriptions WHERE role_id = ?);
    """, (role.id, ))
    existed: bool = c.fetchone()[0]
    c.execute("""
        DELETE FROM available_subscriptions WHERE role_id = ?;    
    """, (role.id, ))
    c.execute("""
        DELETE FROM member_subscriptions WHERE role_id = ?;
    """, (role.id, ))
    db.commit()

    if existed:
        await ctx.send(f"Deleted subscription for role {role.mention}")
    else:
        await ctx.send(f"Subscription for role {role.mention} does not exist", ephemeral=True)

@subscriptions_cmd.sub_command(
    name="list",
    description="List available subscriptions"
)
async def subscriptions_list(ctx: discord.ApplicationCommandInteraction):
    if ctx.guild is None:
        raise UserFacingError("This command does not work in DMs")

    c = db.cursor()
    c.execute("""
        SELECT role_id, price, spare_change FROM available_subscriptions
            WHERE guild_id = ?;
    """, (ctx.guild.id, ))
    available_subscriptions: List[Tuple[int, int, bool]] = c.fetchall()
    c.execute("""
        SELECT role_id, subscribed_since FROM member_subscriptions
            WHERE member_id = ?;
    """, (ctx.author.id, ))
    member_subscriptions: Dict[int, datetime] = dict(c.fetchall())

    message_parts = [f"Available subscriptions in ‘{ctx.guild.name}’:"]
    for role_id, price, spare_change in available_subscriptions:
        part = f"<@&{role_id}>: {balance.to_string(price, spare_change)} per week"
        if role_id in member_subscriptions:
            subscribed_since = member_subscriptions[role_id].replace(tzinfo=timezone.utc).astimezone(None)
            part += f" (subscribed since {subscribed_since})"
        message_parts.append(part)
    await ctx.send("\n".join(message_parts), ephemeral=True)

@client.slash_command(
    name="subscribe",
    description="Subscribe to a paid subscription",
    options=[
        discord.Option(
            name="role",
            type=discord.OptionType.role,
            description="The role of the subscription to subscribe to",
            required=True
        )
    ]
)
async def subscribe(ctx: discord.ApplicationCommandInteraction, role: discord.Role):
    if not isinstance(ctx.author, discord.Member):
        raise UserFacingError("This command does not work in DMs")

    c = db.cursor()
    c.execute("""
        SELECT price, spare_change FROM available_subscriptions
            WHERE role_id = ?; 
    """, (role.id, ))
    price: Optional[Tuple[int, bool]] = c.fetchone()
    if price is None:
        await ctx.send(f"Subscription for role {role.mention} does not exist", ephemeral=True)
        return

    c.execute("""
        SELECT EXISTS(SELECT 1 FROM member_subscriptions WHERE member_id = ? AND role_id = ?);
    """, (ctx.author.id, role.id))
    already_subscribed: bool = c.fetchone()[0]
    if already_subscribed:
        await ctx.send(f"You are already subscribed to {role.mention}", ephemeral=True)
        return

    action_row = discord.ui.ActionRow(
        discord.ui.Button(
            style=discord.ButtonStyle.green,
            label="Subscribe",
            custom_id="subscribe"
        ),
        discord.ui.Button(
            style=discord.ButtonStyle.gray,
            label="Cancel",
            custom_id="cancel"
        )
    )
    await ctx.send((
        f"Subscribe to {role.mention} for {balance.to_string(*price)} per week? "
        f"You will be charged for the first week immediately."
    ), components=[action_row], ephemeral=True)
    button_ctx = await utils.wait_for_component(client, action_row)

    if button_ctx.data.custom_id != "subscribe":
        await button_ctx.response.edit_message(content=f"Cancelled.", components=[])
        return

    try:
        balance.subtract(ctx.author, *price)
    except UserFacingError as ex:
        # The active context changed, so the global on_slash_command_error
        # handler will not work.
        await button_ctx.response.edit_message(content=f"**Error:** {ex}", components=[])
        raise ex

    try:
        await subscriptions.subscribe(ctx.author, role)
    except discord.Forbidden:
        await button_ctx.response.edit_message(content=(
            "**Error:** Missing permissions. Make sure the bot has the Manage "
            "Roles permission and the subscription role is below the bot’s "
            "highest role."
        ), components=[])
        return

    await button_ctx.response.edit_message(content=f"Subscribed to {role.mention}.", components=[])

@client.slash_command(
    name="unsubscribe",
    description="Unsubscribe from a paid subscription",
    options=[
        discord.Option(
            name="role",
            type=discord.OptionType.role,
            description="The role of the subscription to unsubscribe from",
            required=True
        )
    ]
)
async def unsubscribe(ctx: discord.ApplicationCommandInteraction, role: discord.Role):
    if not isinstance(ctx.author, discord.Member):
        raise UserFacingError("This command does not work in DMs")

    c = db.cursor()
    c.execute("""
        SELECT EXISTS(SELECT 1 FROM member_subscriptions WHERE member_id = ? AND role_id = ?);
    """, (ctx.author.id, role.id))
    already_subscribed: bool = c.fetchone()[0]
    if not already_subscribed:
        await ctx.send(f"You are not subscribed to {role.mention}", ephemeral=True)
        return

    action_row = discord.ui.ActionRow(
        discord.ui.Button(
            style=discord.ButtonStyle.red,
            label="Unsubscribe",
            custom_id="unsubscribe"
        ),
        discord.ui.Button(
            style=discord.ButtonStyle.gray,
            label="Cancel",
            custom_id="cancel"
        )
    )
    await ctx.send(f"Unsubscribe from {role.mention}?", components=[action_row], ephemeral=True)
    button_ctx = await utils.wait_for_component(client, action_row)

    if button_ctx.data.custom_id != "unsubscribe":
        await button_ctx.response.edit_message(content="Cancelled.", components=[])
        return

    try:
        await subscriptions.unsubscribe(ctx.author, role)
    except discord.Forbidden:
        await button_ctx.response.edit_message(content=(
            "**Error:** Missing permissions. Make sure the bot has the Manage "
            "Roles permission and the subscription role is below the bot’s "
            "highest role."
        ), components=[])
        return

    await button_ctx.response.edit_message(content=f"Unsubscribed from {role.mention}.", components=[])


if __name__ == "__main__":
    try:
        with open("data/token.txt", "r") as token_file:
            token = token_file.read()
        client.run(token)
    except KeyboardInterrupt:
        print("Stopping...")
        db.close()
