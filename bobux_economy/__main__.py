"""
bobux economy v0.8.1
  - fix strange embeds when relocating messages with Tenor GIFs
  - '/changelog' now works again
  - upvotes and downvotes can no longer be manually added to messages starting
    with 💬 or 🗨️
  - added '/relocate' command, which does the same thing as the 'Send to Memes
    Channel' context menu command but with more options
      - messages can now be relocated to other channels, not just the memes
        channel
      - added option to strip 💬 or 🗨️ from relocated messages (enabled for the
        context menu command)

bobux economy v0.8.0
  - added subscriptions, which allow purchasing certain roles for a weekly
    subscription fee
      - use ‘/subscriptions list’ for more info
  - ‘/version’ and ‘/changelog’ no longer broadcast to the entire server
  - messages starting with 💬 or 🗨️ in the memes channel will no longer have
    upvote and downvote buttons
  - messages already in the memes channel can no longer be moved to the memes
    channel
  - removed Herobrine

bobux economy v0.7.1 - the interactions update
  - users with the manage messages permission can now send memes posted in other
    channels to the memes channel
      - upvotes work as if the message was originally sent in the memes channel
      - there is no penalty for having your post moved (yet)

bobux economy v0.7.0 - the interactions update
  - converted all commands to slash commands
  - you can now check someone’s balance using the right-click menu
  - removed stocks, since they stopped working and no one used them
  - the results of ‘/bal check everyone’ are now sorted

bobux economy v0.6.2 - the stonks update
  - fix infinite money glitch with stocks

bobux economy v0.6.1 - the stonks update
  - fix issue with stocks
  - adjust rounding of stock prices

bobux economy v0.6.0 - the stonks update
  - you can now buy and sell stocks, cryptocurrencies, and real-world currencies
    using 'b$stock' commands
  - 'b$real_estate' is now interpreted as 'b$real_estate check'

bobux economy v0.5.4
  - you can now check the real estate holdings of other people
  - you can now set config options back to none

bobux economy v0.5.3
  - fix permissions issue with real estate (for real this time)
  - fuck you discord

bobux economy v0.5.2
  - fix permissions issue with real estate
  - 'b$bal check @everyone' now works as expected

bobux economy v0.5.1
  - remove the requirement for posts in the memes channel to have an attachment
    or embed

bobux economy v0.5.0
  - you can now buy text channels and voice channels with bobux
  - posts in the memes channel without an attachment or embed no longer have
    upvote or downvote buttons

bobux economy v0.4.0
  - new votes on past messages are no longer recorded while the bot is offline

bobux economy v0.3.2
  - improve various error messages

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

import asyncio
from datetime import datetime, timezone
import logging
import sqlite3
from typing import cast, Dict, List, Optional, Tuple, Union

import discord
from discord_slash import SlashContext, SlashCommandOptionType as OptionType, ContextMenuType, ButtonStyle
from discord_slash.context import InteractionContext, MenuContext
from discord_slash.utils.manage_commands import create_option
from discord_slash.utils.manage_components import create_actionrow, create_button, wait_for_component

from bobux_economy import balance
from bobux_economy import database
from bobux_economy.database import connection as db
from bobux_economy.globals import client, slash, CommandError
from bobux_economy import real_estate
from bobux_economy import subscriptions
from bobux_economy import upvotes

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

@client.event
async def on_slash_command_error(ctx: SlashContext, ex: Exception):
    if isinstance(ex, CommandError):
        logging.info("Sent error feedback")
        await ctx.send(f"**Error:** {ex}", hidden=True)
    raise ex


def check_author_can_manage_guild(ctx: InteractionContext):
    if not isinstance(ctx.channel, discord.abc.GuildChannel):
        raise CommandError("This command does not work in DMs")
    if not bool(ctx.author.permissions_in(ctx.channel).manage_guild):
        raise CommandError("You must have Manage Server permissions to use this command")

def check_author_can_manage_messages(ctx: InteractionContext):
    if not isinstance(ctx.channel, discord.abc.GuildChannel):
        raise CommandError("This command does not work in DMs")
    if not bool(ctx.author.permissions_in(ctx.channel).manage_messages):
        raise CommandError("You must have Manage Messages permissions to use this command")

def check_author_has_admin_role(ctx: InteractionContext):
    if ctx.guild is None or not isinstance(ctx.author, discord.Member):
        raise CommandError("This command does not work in DMs")

    c = db.cursor()
    c.execute("SELECT admin_role FROM guilds WHERE id = ?;", (ctx.guild.id, ))
    row: Tuple[Optional[int]] = c.fetchone()
    admin_role = ctx.guild.get_role(row[0]) if row[0] is not None else None
    if admin_role is not None:
        if not admin_role in ctx.author.roles:
            raise CommandError(f"You must have the {admin_role.mention} role to use this command")
    else:
        check_author_can_manage_guild(ctx)


@slash.slash(
    name="version",
    description="Check the version of the bot"
)
async def version(ctx: SlashContext):
    if ctx.invoked_subcommand is None:
        if __doc__ is None:
            raise CommandError("Unable to determine bot version")
        await ctx.send(__doc__.strip().partition("\n")[0].strip(), hidden=True)

@slash.slash(
    name="changelog",
    description="Show the changelog of the bot"
)
async def changelog(ctx: SlashContext):
    if __doc__ is None:
        raise CommandError("Unable to determine bot version")

    entries = __doc__.strip().split("\n\n")
    page = ""
    for entry in entries:
        if len(page) + len(entry) + 8 > 1900:
            break
        else:
            page += f"\n\n{entry}"  # Yes, I know str.join(list) is faster
    await ctx.send(f"```{page}```\nFull changelog at <https://github.com/arm32x/bobux-economy/blob/master/bobux_economy/__main__.py>", hidden=True)


@slash.subcommand(
    base="config",
    base_description="Change the settings of the bot",
    name="admin_role",
    description="Change which role is required to modify balances",
    options=[
        create_option(
            name="role",
            option_type=OptionType.ROLE,
            description="The role to set, or blank to remove",
            required=False
        )
    ]
)
async def config_admin_role(ctx: SlashContext, role: Optional[discord.Role] = None):
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

@slash.subcommand(
    base="config",
    base_description="Change the settings of the bot",
    name="memes_channel",
    description="Set the channel where upvote reactions are enabled",
    options=[
        create_option(
            name="channel",
            option_type=OptionType.CHANNEL,
            description="The channel to set, or blank to remove",
            required=False
        )
    ]
)
async def config_memes_channel(ctx: SlashContext, channel: Optional[discord.abc.GuildChannel] = None):
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

@slash.subcommand(
    base="config",
    base_description="Change the settings of the bot",
    name="real_estate_category",
    description="Set the category where purchased real estate channels appear",
    options=[
        create_option(
            name="category",
            option_type=OptionType.CHANNEL,
            description="The category to set, or blank to remove",
            required=False
        )
    ]
)
async def config_real_estate_category(ctx: SlashContext, category: Optional[discord.abc.GuildChannel] = None):
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


@slash.subcommand(
    base="bal",
    base_description="Manage account balances",
    subcommand_group="check",
    subcommand_group_description="Check the balance of yourself or someone else",
    name="self",
    description="Check your balance",
)
async def bal_check_self(ctx: SlashContext):
    await bal_check_user.invoke(ctx, ctx.author)

@slash.subcommand(
    base="bal",
    subcommand_group="check",
    subcommand_group_description="Check the balance of yourself or someone else",
    name="user",
    description="Check someone’s balance",
    options=[
        create_option(
            name="target",
            option_type=OptionType.USER,
            description="The user to check the balance of",
            required=True
        )
    ]
)
async def bal_check_user(ctx: InteractionContext, target: discord.Member):
    amount, spare_change = balance.get(target)
    await ctx.send(f"{target.mention}: {balance.to_string(amount, spare_change)}", hidden=True)

@slash.context_menu(
    target=ContextMenuType.USER,
    name="Check Balance"
)
async def bal_check_context_menu(ctx: MenuContext):
    await bal_check_user.invoke(ctx, ctx.target_author)

@slash.subcommand(
    base="bal",
    base_description="Manage account balances",
    subcommand_group="check",
    subcommand_group_description="Check the balance of yourself or someone else",
    name="everyone",
    description="Check the balance of everyone in this server"
)
async def bal_check_everyone(ctx: SlashContext):
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
    await ctx.send("\n".join(message_parts), hidden=True)

@slash.subcommand(
    base="bal",
    base_description="Manage account balances",
    name="set",
    description="Set someone’s balance",
    options=[
        create_option(
            name="target",
            option_type=OptionType.USER,
            description="The user to set the balance of",
            required=True
        ),
        create_option(
            name="amount",
            option_type=OptionType.FLOAT,
            description="The new balance of the target",
            required=True
        )
    ]
)
async def bal_set(ctx: SlashContext, target: discord.Member, amount: float):
    check_author_has_admin_role(ctx)

    amount, spare_change = balance.from_float(float(amount))
    balance.set(target, amount, spare_change)
    db.commit()

    await ctx.send(f"Set the balance of {target.mention} to {balance.to_string(amount, spare_change)}")

@slash.subcommand(
    base="bal",
    base_description="Manage account balances",
    name="add",
    description="Add bobux to someone’s balance",
    options=[
        create_option(
            name="target",
            option_type=OptionType.USER,
            description="The user whose balance will be added to",
            required=True
        ),
        create_option(
            name="amount",
            option_type=OptionType.FLOAT,
            description="The amount to add to the target’s balance",
            required=True
        )
    ]
)
async def bal_add(ctx: SlashContext, target: discord.Member, amount: float):
    check_author_has_admin_role(ctx)

    amount, spare_change = balance.from_float(float(amount))
    balance.add(target, amount, spare_change)
    db.commit()

    await ctx.send(f"Added {balance.to_string(amount, spare_change)} to {target.mention}’s balance")

@slash.subcommand(
    base="bal",
    base_description="Manage account balances",
    name="subtract",
    description="Subtract bobux from someone’s balance",
    options=[
        create_option(
            name="target",
            option_type=OptionType.USER,
            description="The user whose balance will be subtracted from",
            required=True
        ),
        create_option(
            name="amount",
            option_type=OptionType.FLOAT,
            description="The amount to subtract from the target’s balance",
            required=True
        )
    ]
)
async def bal_subtract(ctx: SlashContext, target: discord.Member, amount: float):
    check_author_has_admin_role(ctx)

    amount, spare_change = balance.from_float(float(amount))
    balance.subtract(target, amount, spare_change, allow_overdraft=True)
    db.commit()

    await ctx.send(f"Subtracted {balance.to_string(amount, spare_change)} from {target.mention}’s balance")


@slash.slash(
    name="pay",
    description="Transfer bobux to someone",
    options=[
        create_option(
            name="recipient",
            option_type=OptionType.USER,
            description="The user to transfer bobux to",
            required=True
        ),
        create_option(
            name="amount",
            option_type=OptionType.FLOAT,
            description="The amount to transfer to the recipient",
            required=True
        )
    ]
)
async def pay(ctx: SlashContext, recipient: discord.Member, amount: float):
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


@slash.subcommand(
    base="real_estate",
    base_description="Manage your real estate",
    subcommand_group="buy",
    subcommand_group_description="Buy a real estate channel",
    name="text",
    description=f"Buy a text channel for {balance.to_string(*real_estate.CHANNEL_PRICES[discord.ChannelType.text])}",
    options=[
        create_option(
            name="name",
            option_type=OptionType.STRING,
            description="The name of the purchased channel",
            required=True
        )
    ]
)
async def real_estate_buy_text(ctx: SlashContext, name: str):
    if not isinstance(ctx.author, discord.Member):
        raise CommandError("This command does not work in DMs")

    channel = await real_estate.buy(cast(discord.ChannelType, discord.ChannelType.text), ctx.author, name)
    await ctx.send(f"Bought {channel.mention} for {balance.to_string(*real_estate.CHANNEL_PRICES[discord.ChannelType.text])}")

@slash.subcommand(
    base="real_estate",
    base_description="Manage your real estate",
    subcommand_group="buy",
    subcommand_group_description="Buy a real estate channel",
    name="voice",
    description=f"Buy a voice channel for {balance.to_string(*real_estate.CHANNEL_PRICES[discord.ChannelType.voice])}",
    options=[
        create_option(
            name="name",
            option_type=OptionType.STRING,
            description="The name of the purchased channel",
            required=True
        )
    ]
)
async def real_estate_buy_voice(ctx: SlashContext, name: str):
    if not isinstance(ctx.author, discord.Member):
        raise CommandError("This command does not work in DMs")

    channel = await real_estate.buy(cast(discord.ChannelType, discord.ChannelType.voice), ctx.author, name)
    await ctx.send(f"Bought {channel.mention} for {balance.to_string(*real_estate.CHANNEL_PRICES[discord.ChannelType.voice])}")

@slash.subcommand(
    base="real_estate",
    base_description="Manage your real estate",
    name="sell",
    description="Sell one of your channels for half its purchase price",
    options=[
        create_option(
            name="channel",
            option_type=OptionType.CHANNEL,
            description="The channel to sell",
            required=True
        )
    ]
)
async def real_estate_sell(ctx: SlashContext, channel: Union[discord.TextChannel, discord.VoiceChannel]):
    if not isinstance(ctx.author, discord.Member):
        raise CommandError("This command does not work in DMs")

    price = await real_estate.sell(channel, ctx.author)
    await ctx.send(f"Sold ‘{channel.name}’ for {balance.to_string(*price)}")


@slash.subcommand(
    base="real_estate",
    base_description="Manage your real estate",
    subcommand_group="check",
    subcommand_group_description="Check the real estate holdings of yourself or someone else",
    name="self",
    description="Check your real estate holdings"
)
async def real_estate_check_self(ctx: SlashContext):
    await real_estate_check_user.invoke(ctx, ctx.author)

@slash.subcommand(
    base="real_estate",
    base_description="Manage your real estate",
    subcommand_group="check",
    subcommand_group_description="Check the real estate holdings of yourself or someone else",
    name="user",
    description="Check someone’s real estate holdings",
    options=[
        create_option(
            name="target",
            option_type=OptionType.USER,
            description="The user to check the real estate holdings of",
            required=True
        )
    ]
)
async def real_estate_check_user(ctx: InteractionContext, target: discord.Member):
    c = db.cursor()
    c.execute("""
            SELECT id, purchase_time FROM purchased_channels WHERE owner_id = ?;
        """, (target.id, ))
    results: List[Tuple[int, datetime]] = c.fetchall()

    message_parts = [f"{target.mention}:"]
    for channel_id, purchase_time in results:
        message_parts.append(f"<#{channel_id}>: Purchased {purchase_time}.")
    await ctx.send("\n".join(message_parts), hidden=True)

@slash.context_menu(
    target=ContextMenuType.USER,
    name="Check Real Estate"
)
async def real_estate_check_context_menu(ctx: MenuContext):
    await real_estate_check_user.invoke(ctx, ctx.target_author)

@slash.subcommand(
    base="real_estate",
    base_description="Manage your real estate",
    subcommand_group="check",
    subcommand_group_description="Check the real estate holdings of yourself or someone else",
    name="everyone",
    description="Check the real estate holdings of everyone in this server"
)
async def real_estate_check_everyone(ctx: SlashContext):
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
    await ctx.send("\n".join(message_parts), hidden=True)


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
            avatar=await target_author.avatar_url.read(),
            reason=f"Puppeting user {target_author.id} in order to relocate a message"
        )
    except discord.Forbidden:
        # Check future requirements for a better error message
        if destination.guild.me.permissions_in(message.channel).manage_messages:
            raise CommandError("The bot must have Manage Webhooks permissions to use this command")
        else:
            raise CommandError("The bot must have Manage Webhooks and Manage Messages permissions to use this command")

    # If the bot doesn't have Manage Messages permissions, this will fail later
    if not destination.guild.me.permissions_in(message.channel).manage_messages:
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

@slash.slash(
    name="relocate",
    description="Move a message to a different channel",
    options=[
        create_option(
            name="message_id",
            option_type=OptionType.STRING,
            description="The ID of the message to relocate (slash commands don't support messages as parameters)",
            required=True
        ),
        create_option(
            name="destination",
            option_type=OptionType.CHANNEL,
            description="The channel to relocate the message to",
            required=True
        ),
        create_option(
            name="remove_speech_bubbles",
            option_type=OptionType.BOOLEAN,
            description="Whether or not to remove 💬 or 🗨️ from the start of the message",
            required=False
        )
    ]
)
async def relocate(ctx: SlashContext, message_id: str, destination: discord.abc.GuildChannel, remove_speech_bubbles: Optional[bool] = None):
    check_author_can_manage_messages(ctx)
    if not isinstance(ctx.channel, discord.abc.GuildChannel):
        raise CommandError("This command does not work in DMs")

    if remove_speech_bubbles is None:
        remove_speech_bubbles = False

    if not isinstance(destination, discord.TextChannel):
        raise CommandError(f"Destination channel must be a text channel")

    message = await ctx.channel.fetch_message(int(message_id))
    await relocate_message(message, destination, remove_speech_bubbles=remove_speech_bubbles)

    await ctx.send(f"Relocated message to {destination.mention}", hidden=True)

@slash.context_menu(
    target=ContextMenuType.MESSAGE,
    name="Send to Memes Channel"
)
async def relocate_meme(ctx: MenuContext):
    check_author_can_manage_messages(ctx)
    if ctx.guild is None:
        raise CommandError("This command does not work in DMs")
    if ctx.target_message is None:
        raise CommandError("No message selected")

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
    if ctx.target_message.channel.id == memes_channel_id:
        raise CommandError("Message is already in the memes channel")

    await relocate_message(ctx.target_message, memes_channel, remove_speech_bubbles=True)

    await ctx.send(f"Relocated message to {memes_channel.mention}", hidden=True)


@slash.subcommand(
    base="subscriptions",
    base_description="Manage paid subscriptions",
    name="new",
    description="Create a new paid subscription in this server",
    options=[
        create_option(
            name="role",
            option_type=OptionType.ROLE,
            description="The role to grant to subscribers",
            required=True
        ),
        create_option(
            name="price_per_week",
            option_type=OptionType.FLOAT,
            description="The price of this subscription, charged weekly",
            required=True
        )
    ]
)
async def subscriptions_new(ctx: SlashContext, role: discord.Role, price_per_week: Union[float, int]):
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

@slash.subcommand(
    base="subscriptions",
    base_description="Manage paid subscriptions",
    name="delete",
    description="Delete a paid subscription from this server. The role will not be revoked from current subscribers.",
    options=[
        create_option(
            name="role",
            option_type=OptionType.ROLE,
            description="The role of the subscription to delete",
            required=True
        )
    ]
)
async def subscriptions_delete(ctx: SlashContext, role: discord.Role):
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
        await ctx.send(f"Subscription for role {role.mention} does not exist", hidden=True)

@slash.subcommand(
    base="subscriptions",
    base_description="Manage paid subscriptions",
    name="list",
    description="List available subscriptions"
)
async def subscriptions_list(ctx: SlashContext):
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
    await ctx.send("\n".join(message_parts), hidden=True)

@slash.slash(
    name="subscribe",
    description="Subscribe to a paid subscription",
    options=[
        create_option(
            name="role",
            option_type=OptionType.ROLE,
            description="The role of the subscription to subscribe to",
            required=True
        )
    ]
)
async def subscribe(ctx: SlashContext, role: discord.Role):
    if not isinstance(ctx.author, discord.Member):
        raise CommandError("This command does not work in DMs")

    c = db.cursor()
    c.execute("""
        SELECT price, spare_change FROM available_subscriptions
            WHERE role_id = ?; 
    """, (role.id, ))
    price: Optional[Tuple[int, bool]] = c.fetchone()
    if price is None:
        await ctx.send(f"Subscription for role {role.mention} does not exist", hidden=True)
        return

    c.execute("""
        SELECT EXISTS(SELECT 1 FROM member_subscriptions WHERE member_id = ? AND role_id = ?);
    """, (ctx.author.id, role.id))
    already_subscribed: bool = c.fetchone()[0]
    if already_subscribed:
        await ctx.send(f"You are already subscribed to {role.mention}", hidden=True)
        return

    action_row = create_actionrow(
        create_button(
            style=ButtonStyle.green,
            label="Subscribe",
            custom_id="subscribe"
        ),
        create_button(
            style=ButtonStyle.gray,
            label="Cancel",
            custom_id="cancel"
        )
    )
    await ctx.send((
        f"Subscribe to {role.mention} for {balance.to_string(*price)} per week? "
        f"You will be charged for the first week immediately."
    ), components=[action_row], hidden=True)
    button_ctx = await wait_for_component(client, components=action_row)

    if button_ctx.custom_id != "subscribe":
        await button_ctx.edit_origin(content=f"Cancelled.", components=[])
        return

    try:
        balance.subtract(ctx.author, *price)
    except CommandError as ex:
        # The active context changed, so the global on_slash_command_error
        # handler will not work.
        await button_ctx.edit_origin(content=f"**Error:** {ex}", components=[])
        raise ex

    try:
        await subscriptions.subscribe(ctx.author, role)
    except discord.Forbidden:
        await button_ctx.edit_origin(content=(
            "**Error:** Missing permissions. Make sure the bot has the Manage "
            "Roles permission and the subscription role is below the bot’s "
            "highest role."
        ), components=[])
        return

    await button_ctx.edit_origin(content=f"Subscribed to {role.mention}.", components=[])

@slash.slash(
    name="unsubscribe",
    description="Unsubscribe from a paid subscription",
    options=[
        create_option(
            name="role",
            option_type=OptionType.ROLE,
            description="The role of the subscription to unsubscribe from",
            required=True
        )
    ]
)
async def unsubscribe(ctx: SlashContext, role: discord.Role):
    if not isinstance(ctx.author, discord.Member):
        raise CommandError("This command does not work in DMs")

    c = db.cursor()
    c.execute("""
        SELECT EXISTS(SELECT 1 FROM member_subscriptions WHERE member_id = ? AND role_id = ?);
    """, (ctx.author.id, role.id))
    already_subscribed: bool = c.fetchone()[0]
    if not already_subscribed:
        await ctx.send(f"You are not subscribed to {role.mention}", hidden=True)
        return

    action_row = create_actionrow(
        create_button(
            style=ButtonStyle.red,
            label="Unsubscribe",
            custom_id="unsubscribe"
        ),
        create_button(
            style=ButtonStyle.gray,
            label="Cancel",
            custom_id="cancel"
        )
    )
    await ctx.send(f"Unsubscribe from {role.mention}?", components=[action_row], hidden=True)
    button_ctx = await wait_for_component(client, components=action_row)

    if button_ctx.custom_id != "unsubscribe":
        await button_ctx.edit_origin(content="Cancelled.", components=[])
        return

    try:
        await subscriptions.unsubscribe(ctx.author, role)
    except discord.Forbidden:
        await button_ctx.edit_origin(content=(
            "**Error:** Missing permissions. Make sure the bot has the Manage "
            "Roles permission and the subscription role is below the bot’s "
            "highest role."
        ), components=[])
        return

    await button_ctx.edit_origin(content=f"Unsubscribed from {role.mention}.", components=[])


if __name__ == "__main__":
    try:
        with open("data/token.txt", "r") as token_file:
            token = token_file.read()
        client.run(token)
    except KeyboardInterrupt:
        print("Stopping...")
        db.close()
