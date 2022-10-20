import asyncio
from datetime import datetime, timezone
import logging
import random
import sqlite3
from typing import cast, Dict, List, Optional, Tuple, Union

import disnake as discord
from disnake.ext.commands import CommandInvokeError

from bobux_economy import balance
from bobux_economy import database
from bobux_economy.database import connection as db
from bobux_economy.globals import client, CommandError
from bobux_economy import real_estate
from bobux_economy import subscriptions
from bobux_economy import upvotes
from bobux_economy import utils

logging.basicConfig(format="%(levelname)8s [%(name)s] %(message)s", level=logging.INFO)

logging.info("Initializing...")
database.migrate()

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
    if isinstance(ex, CommandInvokeError):
        ex = ex.original
    if isinstance(ex, CommandError):
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
        raise CommandError("This command does not work in DMs")
    if not bool(ctx.channel.permissions_for(ctx.author).manage_guild):
        raise CommandError("You must have Manage Server permissions to use this command")

def check_author_can_manage_messages(ctx: discord.Interaction):
    if not isinstance(ctx.channel, discord.abc.GuildChannel) or not isinstance(ctx.author, discord.Member):
        raise CommandError("This command does not work in DMs")
    if not bool(ctx.channel.permissions_for(ctx.author).manage_messages):
        raise CommandError("You must have Manage Messages permissions to use this command")

def check_author_has_admin_role(ctx: discord.Interaction):
    if ctx.guild is None or not isinstance(ctx.author, discord.Member):
        raise CommandError("This command does not work in DMs")

    c = db.cursor()
    c.execute("SELECT admin_role FROM guilds WHERE id = ?;", (ctx.guild.id, ))
    row: Optional[Tuple[int]] = c.fetchone()
    admin_role = ctx.guild.get_role(row[0]) if row is not None else None
    if admin_role is not None:
        if not admin_role in ctx.author.roles:
            raise CommandError(f"You must have the {admin_role.mention} role to use this command")
    else:
        check_author_can_manage_guild(ctx)


client.load_extension("bobux_economy.cogs.bot_info")


@client.slash_command(
    name="config",
    description="Change the settings of the bot"
)
async def config(_: discord.ApplicationCommandInteraction):
    pass

@config.sub_command(
    name="admin_role",
    description="Change which role is required to modify balances",
    options=[
        discord.Option(
            name="role",
            type=discord.OptionType.role,
            description="The role to set, or blank to remove",
            required=False
        )
    ]
)
async def config_admin_role(ctx: discord.ApplicationCommandInteraction, role: Optional[discord.Role] = None):
    check_author_can_manage_guild(ctx)
    if ctx.guild is None:
        raise CommandError("This command does not work in DMs")

    role_id = role.id if role is not None else None
    role_mention = role.mention if role is not None else "None"

    c = db.cursor()
    c.execute("""
        INSERT INTO guilds(id, admin_role) VALUES(?, ?)
            ON CONFLICT(id) DO UPDATE SET admin_role = excluded.admin_role;
    """, (ctx.guild.id, role_id))
    db.commit()
    await ctx.send(f"Set admin role to {role_mention}")

@config.sub_command(
    name="memes_channel",
    description="Set the channel where upvote reactions are enabled",
    options=[
        discord.Option(
            name="channel",
            type=discord.OptionType.channel,
            description="The channel to set, or blank to remove",
            required=False
        )
    ]
)
async def config_memes_channel(ctx: discord.ApplicationCommandInteraction, channel: Optional[discord.abc.GuildChannel] = None):
    check_author_can_manage_guild(ctx)
    if ctx.guild is None:
        raise CommandError("This command does not work in DMs")
    if channel is not None and not isinstance(channel, discord.TextChannel):
        raise CommandError("The memes channel must be a text channel")

    channel_id = channel.id if channel is not None else None
    channel_mention = channel.mention if channel is not None else "None"

    c = db.cursor()
    c.execute("""
        INSERT INTO guilds(id, memes_channel) VALUES(?, ?)
            ON CONFLICT(id) DO UPDATE SET memes_channel = excluded.memes_channel;
    """, (ctx.guild.id, channel_id))
    db.commit()
    await ctx.send(f"Set memes channel to {channel_mention}")

@config.sub_command(
    name="real_estate_category",
    description="Set the category where purchased real estate channels appear",
    options=[
        discord.Option(
            name="category",
            type=discord.OptionType.channel,
            description="The category to set, or blank to remove",
            required=False
        )
    ]
)
async def config_real_estate_category(ctx: discord.ApplicationCommandInteraction, category: Optional[discord.abc.GuildChannel] = None):
    check_author_can_manage_guild(ctx)
    if ctx.guild is None:
        raise CommandError("This command does not work in DMs")
    if category is not None and not isinstance(category, discord.CategoryChannel):
        raise CommandError("The real estate category must be a category")

    category_id = category.id if category is not None else None
    category_mention = f"‘{category.name}’" if category is not None else "None"

    c = db.cursor()
    c.execute("""
        INSERT INTO guilds(id, real_estate_category) VALUES(?, ?)
            ON CONFLICT(id) DO UPDATE SET real_estate_category = excluded.real_estate_category;
    """, (ctx.guild.id, category_id))
    db.commit()
    await ctx.send(f"Set real estate category to {category_mention}")


@client.slash_command(
    name="bal",
    description="Manage account balances"
)
async def bal(_: discord.ApplicationCommandInteraction):
    pass

@bal.sub_command_group(
    name="check",
    description="Check the balance of yourself or someone else"
)
async def bal_check(_: discord.ApplicationCommandInteraction):
    pass

@bal_check.sub_command(
    name="self",
    description="Check your balance",
)
async def bal_check_self(ctx: discord.ApplicationCommandInteraction):
    if not isinstance(ctx.author, discord.Member):
        raise CommandError("This command does not work in DMs")
    await bal_check_user(ctx, ctx.author)

async def bal_check_user(ctx: discord.Interaction, target: discord.Member):
    amount, spare_change = balance.get(target)
    await ctx.send(f"{target.mention}: {balance.to_string(amount, spare_change)}", ephemeral=True)

@bal_check.sub_command(
    name="user",
    description="Check someone’s balance",
    options=[
        discord.Option(
            name="target",
            type=discord.OptionType.user,
            description="The user to check the balance of",
            required=True
        )
    ]
)
async def bal_check_user_cmd(ctx: discord.ApplicationCommandInteraction, target: discord.Member):
    await bal_check_user(ctx, target)

@client.user_command(
    name="Check Balance"
)
async def bal_check_context_menu(ctx: discord.UserCommandInteraction):
    if not isinstance(ctx.target, discord.Member):
        raise CommandError("This command does not work in DMs")
    await bal_check_user(ctx, ctx.target)

@bal_check.sub_command(
    base="bal",
    base_description="Manage account balances",
    subcommand_group="check",
    subcommand_group_description="Check the balance of yourself or someone else",
    name="everyone",
    description="Check the balance of everyone in this server"
)
async def bal_check_everyone(ctx: discord.ApplicationCommandInteraction):
    if ctx.guild is None:
        raise CommandError("This command does not work in DMs")

    c = db.cursor()
    c.execute("""
            SELECT id, balance, spare_change FROM members WHERE guild_id = ?
                ORDER BY balance DESC, spare_change DESC;
        """, (ctx.guild.id, ))
    results: List[Tuple[int, int, bool]] = c.fetchall()

    message_parts = []
    for member_id, amount, spare_change in results:
        message_parts.append(f"<@{member_id}>: {balance.to_string(amount, spare_change)}")

    if len(message_parts) > 0:
        await ctx.send("\n".join(message_parts), ephemeral=True)
    else:
        await ctx.send("No results")

@bal.sub_command(
    name="set",
    description="Set someone’s balance",
    options=[
        discord.Option(
            name="target",
            type=discord.OptionType.user,
            description="The user to set the balance of",
            required=True
        ),
        discord.Option(
            name="amount",
            type=discord.OptionType.number,
            description="The new balance of the target",
            required=True
        )
    ]
)
async def bal_set(ctx: discord.ApplicationCommandInteraction, target: discord.Member, amount: float):
    check_author_has_admin_role(ctx)

    amount, spare_change = balance.from_float(float(amount))
    balance.set(target, amount, spare_change)
    db.commit()

    await ctx.send(f"Set the balance of {target.mention} to {balance.to_string(amount, spare_change)}")

@bal.sub_command(
    base="bal",
    base_description="Manage account balances",
    name="add",
    description="Add bobux to someone’s balance",
    options=[
        discord.Option(
            name="target",
            type=discord.OptionType.user,
            description="The user whose balance will be added to",
            required=True
        ),
        discord.Option(
            name="amount",
            type=discord.OptionType.number,
            description="The amount to add to the target’s balance",
            required=True
        )
    ]
)
async def bal_add(ctx: discord.ApplicationCommandInteraction, target: discord.Member, amount: float):
    check_author_has_admin_role(ctx)

    amount, spare_change = balance.from_float(float(amount))
    balance.add(target, amount, spare_change)
    db.commit()

    await ctx.send(f"Added {balance.to_string(amount, spare_change)} to {target.mention}’s balance")

@bal.sub_command(
    name="subtract",
    description="Subtract bobux from someone’s balance",
    options=[
        discord.Option(
            name="target",
            type=discord.OptionType.user,
            description="The user whose balance will be subtracted from",
            required=True
        ),
        discord.Option(
            name="amount",
            type=discord.OptionType.number,
            description="The amount to subtract from the target’s balance",
            required=True
        )
    ]
)
async def bal_subtract(ctx: discord.ApplicationCommandInteraction, target: discord.Member, amount: float):
    check_author_has_admin_role(ctx)

    amount, spare_change = balance.from_float(float(amount))
    balance.subtract(target, amount, spare_change, allow_overdraft=True)
    db.commit()

    await ctx.send(f"Subtracted {balance.to_string(amount, spare_change)} from {target.mention}’s balance")


@client.slash_command(
    name="pay",
    description="Transfer bobux to someone",
    options=[
        discord.Option(
            name="recipient",
            type=discord.OptionType.user,
            description="The user to transfer bobux to",
            required=True
        ),
        discord.Option(
            name="amount",
            type=discord.OptionType.number,
            description="The amount to transfer to the recipient",
            required=True
        )
    ]
)
async def pay(ctx: discord.ApplicationCommandInteraction, recipient: discord.Member, amount: float):
    if not isinstance(ctx.author, discord.Member):
        raise CommandError("This command does not work in DMs")

    try:
        amount, spare_change = balance.from_float(float(amount))
        balance.subtract(ctx.author, amount, spare_change)
        balance.add(recipient, amount, spare_change)
    except sqlite3.Error:
        db.rollback()
        raise
    else:
        db.commit()

    await ctx.send(f"Transferred {balance.to_string(amount, spare_change)} to {recipient.mention}")


@client.slash_command(
    name="real_estate",
    description="Manage your real estate"
)
async def real_estate_cmd(_: discord.ApplicationCommandInteraction):
    pass

@real_estate_cmd.sub_command_group(
    name="buy",
    description="Buy a real estate channel"
)
async def real_estate_buy(_: discord.ApplicationCommandInteraction):
    pass

@real_estate_buy.sub_command(
    name="text",
    description=f"Buy a text channel for {balance.to_string(*real_estate.CHANNEL_PRICES[discord.ChannelType.text])}",
    options=[
        discord.Option(
            name="name",
            type=discord.OptionType.string,
            description="The name of the purchased channel",
            required=True
        )
    ]
)
async def real_estate_buy_text(ctx: discord.ApplicationCommandInteraction, name: str):
    if not isinstance(ctx.author, discord.Member):
        raise CommandError("This command does not work in DMs")

    channel = await real_estate.buy(cast(discord.ChannelType, discord.ChannelType.text), ctx.author, name)
    await ctx.send(f"Bought {channel.mention} for {balance.to_string(*real_estate.CHANNEL_PRICES[discord.ChannelType.text])}")

@real_estate_buy.sub_command(
    name="voice",
    description=f"Buy a voice channel for {balance.to_string(*real_estate.CHANNEL_PRICES[discord.ChannelType.voice])}",
    options=[
        discord.Option(
            name="name",
            type=discord.OptionType.string,
            description="The name of the purchased channel",
            required=True
        )
    ]
)
async def real_estate_buy_voice(ctx: discord.ApplicationCommandInteraction, name: str):
    if not isinstance(ctx.author, discord.Member):
        raise CommandError("This command does not work in DMs")

    channel = await real_estate.buy(cast(discord.ChannelType, discord.ChannelType.voice), ctx.author, name)
    await ctx.send(f"Bought {channel.mention} for {balance.to_string(*real_estate.CHANNEL_PRICES[discord.ChannelType.voice])}")

@real_estate_cmd.sub_command(
    name="sell",
    description="Sell one of your channels for half its purchase price",
    options=[
        discord.Option(
            name="channel",
            type=discord.OptionType.channel,
            description="The channel to sell",
            required=True
        )
    ]
)
async def real_estate_sell(ctx: discord.ApplicationCommandInteraction, channel: Union[discord.TextChannel, discord.VoiceChannel]):
    if not isinstance(ctx.author, discord.Member):
        raise CommandError("This command does not work in DMs")

    price = await real_estate.sell(channel, ctx.author)
    await ctx.send(f"Sold ‘{channel.name}’ for {balance.to_string(*price)}")


@real_estate_cmd.sub_command_group(
    name="check",
    description="Check the real estate holdings of yourself or someone else"
)
async def real_estate_check(_: discord.ApplicationCommandInteraction):
    pass

@real_estate_check.sub_command(
    name="self",
    description="Check your real estate holdings"
)
async def real_estate_check_self(ctx: discord.ApplicationCommandInteraction):
    if not isinstance(ctx.author, discord.Member):
        raise CommandError("This command does not work in DMs")
    await real_estate_check_user(ctx, ctx.author)

async def real_estate_check_user(ctx: discord.Interaction, target: discord.Member):
    c = db.cursor()
    c.execute("""
            SELECT id, purchase_time FROM purchased_channels WHERE owner_id = ?;
        """, (target.id, ))
    results: List[Tuple[int, datetime]] = c.fetchall()

    message_parts = [f"{target.mention}:"]
    for channel_id, purchase_time in results:
        message_parts.append(f"<#{channel_id}>: Purchased {purchase_time}.")
    await ctx.send("\n".join(message_parts), ephemeral=True)

@real_estate_check.sub_command(
    name="user",
    description="Check someone’s real estate holdings",
    options=[
        discord.Option(
            name="target",
            type=discord.OptionType.user,
            description="The user to check the real estate holdings of",
            required=True
        )
    ]
)
async def real_estate_check_user_cmd(ctx: discord.ApplicationCommandInteraction, target: discord.Member):
    await real_estate_check_user(ctx, target)

@client.user_command(
    name="Check Real Estate"
)
async def real_estate_check_context_menu(ctx: discord.UserCommandInteraction):
    if not isinstance(ctx.target, discord.Member):
        raise CommandError("This command does not work in DMs")
    await real_estate_check_user(ctx, ctx.target)

@real_estate_check.sub_command(
    name="everyone",
    description="Check the real estate holdings of everyone in this server"
)
async def real_estate_check_everyone(ctx: discord.ApplicationCommandInteraction):
    if ctx.guild is None:
        raise CommandError("This command does not work in DMs")

    c = db.cursor()
    c.execute("""
            SELECT id, owner_id, purchase_time FROM purchased_channels WHERE guild_id = ?
                ORDER BY owner_id;
        """, (ctx.guild.id, ))
    results: List[Tuple[int, int, datetime]] = c.fetchall()

    message_parts = []
    current_owner_id = None
    for channel_id, owner_id, purchase_time in results:
        if owner_id != current_owner_id:
            message_parts.append(f"<@{owner_id}>:")
            current_owner_id = owner_id
        message_parts.append(f"<#{channel_id}>: Purchased {purchase_time}.")

    if len(message_parts) > 0:
        await ctx.send("\n".join(message_parts), ephemeral=True)
    else:
        await ctx.send("No results", ephemeral=True)


async def relocate_message(message: discord.Message, destination: discord.TextChannel, remove_speech_bubbles: bool = False):
    if message.channel.id == destination.id:
        raise CommandError(f"Message already in {destination.mention}")
    if not isinstance(message.channel, discord.abc.GuildChannel):
        raise CommandError("This command does not work in DMs")

    # Create a webhook that mimics the original poster
    target_author = message.author
    try:
        webhook: discord.Webhook = await destination.create_webhook(
            name=target_author.display_name,
            avatar=await target_author.display_avatar.read(),
            reason=f"Puppeting user {target_author.id} in order to relocate a message"
        )
    except discord.Forbidden:
        # Check future requirements for a better error message
        if message.channel.permissions_for(destination.guild.me).manage_messages:
            raise CommandError("The bot must have Manage Webhooks permissions to use this command")
        else:
            raise CommandError("The bot must have Manage Webhooks and Manage Messages permissions to use this command")

    # If the bot doesn't have Manage Messages permissions, this will fail later
    if not message.channel.permissions_for(destination.guild.me).manage_messages:
        raise CommandError("The bot must have Manage Messages permissions to use this command")

    # Get the attachments from the original message as uploadable files
    files = []
    for attachment in message.attachments:
        files.append(await attachment.to_file(spoiler=attachment.is_spoiler()))

    # If requested, remove speech bubbles from the start of the message content
    content = message.content
    if remove_speech_bubbles:
        if content.startswith("💬"):
            content = content[1:].lstrip()
        elif content.startswith("🗨️"):
            content = content[2:].lstrip()

    # Repost the meme in the memes channel. Vote reactions will be automatically
    # added in the on_message() handler.
    # noinspection PyArgumentList
    await webhook.send(
        content=content,
        files=files,
        # embeds=ctx.target_message.embeds,
        allowed_mentions=discord.AllowedMentions.none(),
        tts=message.tts
    )
    # Delete the original message using the bot API, not the interactions API
    await discord.Message.delete(message)

    # Permanently associate this webhook ID with the original poster
    c = db.cursor()
    c.execute("""
        INSERT INTO webhooks VALUES(?, ?);
    """, (webhook.id, target_author.id))
    db.commit()
    # Delete the webhook
    await webhook.delete(reason="Will no longer be used")

@client.slash_command(
    name="relocate",
    description="Move a message to a different channel",
    options=[
        discord.Option(
            name="message_id",
            type=discord.OptionType.string,
            description="The ID of the message to relocate (slash commands don't support messages as parameters)",
            required=True
        ),
        discord.Option(
            name="destination",
            type=discord.OptionType.channel,
            description="The channel to relocate the message to",
            required=True
        ),
        discord.Option(
            name="remove_speech_bubbles",
            type=discord.OptionType.boolean,
            description="Whether or not to remove 💬 or 🗨️ from the start of the message",
            required=False
        )
    ]
)
async def relocate(ctx: discord.ApplicationCommandInteraction, message_id: str, destination: discord.abc.GuildChannel, remove_speech_bubbles: Optional[bool] = None):
    check_author_can_manage_messages(ctx)
    if not isinstance(ctx.channel, discord.abc.GuildChannel):
        raise CommandError("This command does not work in DMs")

    if remove_speech_bubbles is None:
        remove_speech_bubbles = False

    if not isinstance(destination, discord.TextChannel):
        raise CommandError(f"Destination channel must be a text channel")

    message = await ctx.channel.fetch_message(int(message_id))
    await relocate_message(message, destination, remove_speech_bubbles=remove_speech_bubbles)

    await ctx.send(f"Relocated message to {destination.mention}", ephemeral=True)

@client.message_command(
    name="Send to Memes Channel"
)
async def relocate_meme(ctx: discord.MessageCommandInteraction):
    check_author_can_manage_messages(ctx)
    if ctx.guild is None:
        raise CommandError("This command does not work in DMs")

    # Get the memes channel ID from the database
    c = db.cursor()
    c.execute("""
        SELECT memes_channel FROM guilds WHERE id = ?;
    """, (ctx.guild.id, ))
    memes_channel_id: Optional[int] = (c.fetchone() or (None, ))[0]
    if memes_channel_id is None:
        raise CommandError("Memes channel is not configured")
    # Use the channel ID to get a full channel object
    memes_channel = client.get_channel(memes_channel_id) or await client.fetch_channel(memes_channel_id)
    if memes_channel is not None and not isinstance(memes_channel, discord.TextChannel):
        raise CommandError("The memes channel must be a text channel")

    # Don't move messages already in the memes channel
    if ctx.target.channel.id == memes_channel_id:
        raise CommandError("Message is already in the memes channel")

    await relocate_message(ctx.target, memes_channel, remove_speech_bubbles=True)

    await ctx.send(f"Relocated message to {memes_channel.mention}", ephemeral=True)


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
        raise CommandError("This command does not work in DMs")

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
        raise CommandError("This command does not work in DMs")

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
        raise CommandError("This command does not work in DMs")

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
    except CommandError as ex:
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
        raise CommandError("This command does not work in DMs")

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
