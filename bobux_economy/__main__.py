"""
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

from datetime import datetime
import logging
import sqlite3
from typing import *

import discord
from discord_slash import SlashContext, SlashCommandOptionType as OptionType, ContextMenuType
from discord_slash.context import InteractionContext, MenuContext
from discord_slash.utils.manage_commands import create_option

import balance
import database
from database import connection as db
from globals import client, slash, CommandError
import real_estate
import upvotes

logging.basicConfig(format="%(levelname)8s [%(name)s] %(message)s", level=logging.INFO)

logging.info("Initializing...")
database.migrate()

@client.event
async def on_ready():
    logging.info("Synchronizing votes...")
    await upvotes.sync_votes()
    logging.info("Done!")

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
                message = await client.get_channel(payload.channel_id).fetch_message(payload.message_id)

                if payload.user_id == message.author.id:
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

                message = await client.get_channel(payload.channel_id).fetch_message(payload.message_id)
                await upvotes.delete_vote(payload.message_id, payload.channel_id, payload.user_id, check_equal_to=vote)
                user = client.get_user(payload.user_id)
                if user is None:
                    user = await client.fetch_user(payload.user_id)
                await upvotes.remove_extra_reactions(message, user, None)

@client.event
async def on_slash_command_error(ctx: SlashContext, ex: Exception):
    if isinstance(ex, CommandError):
        logging.info("Sent error feedback")
        await ctx.send(f"**Error:** {ex}", hidden=True)
    raise ex


def check_author_can_manage_guild(ctx: SlashContext):
    if not bool(ctx.author.permissions_in(ctx.channel).manage_guild):
        raise CommandError("You must have Manage Server permissions to use this command")

def check_author_has_admin_role(ctx: SlashContext):
    c = db.cursor()
    c.execute("SELECT admin_role FROM guilds WHERE id = ?;", (ctx.guild.id, ))
    row: Tuple[Optional[int]] = c.fetchone() or (None, )
    admin_role = ctx.guild.get_role(row[0])
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
        await ctx.send(__doc__.strip().partition("\n")[0].strip())

@slash.slash(
    name="changelog",
    description="Show the changelog of the bot"
)
async def changelog(ctx: SlashContext):
    await ctx.send(f"```{__doc__.strip()}```")


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
    results: List[int, datetime] = c.fetchall()

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
    c = db.cursor()
    c.execute("""
            SELECT id, owner_id, purchase_time FROM purchased_channels WHERE guild_id = ?
                ORDER BY owner_id;
        """, (ctx.guild.id, ))
    results: List[int, int, datetime] = c.fetchall()

    message_parts = []
    current_owner_id = None
    for channel_id, owner_id, purchase_time in results:
        if owner_id != current_owner_id:
            message_parts.append(f"<@{owner_id}>:")
            current_owner_id = owner_id
        message_parts.append(f"<#{channel_id}>: Purchased {purchase_time}.")
    await ctx.send("\n".join(message_parts), hidden=True)


if __name__ == "__main__":
    try:
        with open("data/token.txt", "r") as token_file:
            token = token_file.read()
            client.run(token)
    except KeyboardInterrupt:
        print("Stopping...")
        db.close()
