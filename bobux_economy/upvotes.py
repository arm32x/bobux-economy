import enum
import logging
from typing import Dict, List, Optional, Tuple, Union

import aiosqlite
import disnake as disnake

from bobux_economy import balance
from bobux_economy.bot import BobuxEconomyBot

# TODO: Make these configurable.
UPVOTE_EMOJI = "⬆️"
DOWNVOTE_EMOJI = "⬇️"


class Vote(enum.IntEnum):
    UPVOTE = 1
    DOWNVOTE = -1

async def message_eligible(db_connection: aiosqlite.Connection, message: disnake.Message) -> bool:
    if message.guild is None:
        return False

    async with db_connection.cursor() as db_cursor:
        await db_cursor.execute("SELECT memes_channel FROM guilds WHERE id = ?;", (message.guild.id, ))
        row = await db_cursor.fetchone()

    return (
        row is not None
        and message.channel.id == row["memes_channel"]
        and not message.content.startswith("💬")
        and not message.content.startswith("🗨️")
    )

async def add_reactions(message: Union[disnake.Message, disnake.PartialMessage]):
    await message.add_reaction(UPVOTE_EMOJI)
    await message.add_reaction(DOWNVOTE_EMOJI)

    logging.info("Added upvote and downvote reactions to message %d.", message.id)

recently_removed_reactions: List[Tuple[int, Vote, int]] = [ ]

async def _user_reacted(message: disnake.Message, user: Union[disnake.User, disnake.Member], emoji: Union[disnake.Emoji, disnake.PartialEmoji, str]) -> bool:
    for reaction in message.reactions:
        if reaction.emoji == emoji:
            async for reaction_user in reaction.users():
                if reaction_user == user:
                    return True
    return False

async def remove_extra_reactions(message: disnake.Message, user: Union[disnake.User, disnake.Member], vote: Optional[Vote]):
    logging.info("Removed extra reactions on message %d for member '%s'.", message.id, user.display_name)

    if vote != Vote.UPVOTE and await _user_reacted(message, user, UPVOTE_EMOJI):
        recently_removed_reactions.append((message.id, Vote.UPVOTE, user.id))
        await message.remove_reaction(UPVOTE_EMOJI, user)
    if vote != Vote.DOWNVOTE and await _user_reacted(message, user, DOWNVOTE_EMOJI):
        recently_removed_reactions.append((message.id, Vote.DOWNVOTE, user.id))
        await message.remove_reaction(DOWNVOTE_EMOJI, user)


async def record_vote(bot: BobuxEconomyBot, message_id: int, channel_id: int, member_id: int, vote: Vote, commit: bool = True, event: bool = True):
    async with bot.db_connection.cursor() as db_cursor:
        await db_cursor.execute("""
            SELECT vote FROM votes WHERE message_id = ? AND channel_id = ? AND member_id = ?;
        """, (message_id, channel_id, member_id))
        row = await db_cursor.fetchone()

        previous_vote: Optional[Vote] = Vote(row["vote"]) if row is not None else None

        await db_cursor.execute("""
            INSERT INTO votes(message_id, channel_id, member_id, vote) VALUES (?, ?, ?, ?)
                ON CONFLICT(message_id, member_id) DO UPDATE SET vote = excluded.vote;
        """, (message_id, channel_id, member_id, vote))

    logging.info("Recorded %s by member %d on message %d.", vote.name.lower(), member_id, message_id)

    if event:
        await on_vote_raw(bot, message_id, channel_id, member_id, previous_vote, vote)

    if commit:
        await bot.db_connection.commit()

async def delete_vote(bot: BobuxEconomyBot, message_id: int, channel_id: int, member_id: int, check_equal_to: Optional[Vote] = None, commit: bool = True, event: bool = True):
    async with bot.db_connection.cursor() as db_cursor:
        if check_equal_to is not None:
            await db_cursor.execute("""
                SELECT vote FROM votes WHERE message_id = ? AND member_id = ? AND vote = ?;
            """, (message_id, member_id, check_equal_to))
            row = await db_cursor.fetchone()

            previous_vote: Optional[Vote] = Vote(row["vote"]) if row is not None else None

            await db_cursor.execute("""
                DELETE FROM votes WHERE message_id = ? AND member_id = ? AND vote = ?;
            """, (message_id, member_id, check_equal_to))

            if event:
                if previous_vote is not None:
                    await on_vote_raw(bot, message_id, channel_id, member_id, previous_vote, None)

            if commit:
                await bot.db_connection.commit()
            logging.info("Removed vote by member %d on message %d, if it was %s.", member_id, message_id, "an upvote" if check_equal_to == Vote.UPVOTE else "a downvote")

        else:
            await db_cursor.execute("""
                SELECT vote FROM votes WHERE message_id = ? AND member_id = ?;
            """, (message_id, member_id))
            row = await db_cursor.fetchone()

            previous_vote: Optional[Vote] = Vote(row["vote"]) if row is not None else None

            await db_cursor.execute("""
                DELETE FROM votes WHERE message_id = ? AND member_id = ?;
            """, (message_id, member_id))

            if event:
                if previous_vote is not None:
                    await on_vote_raw(bot, message_id, channel_id, member_id, previous_vote, None)

            if commit:
                await bot.db_connection.commit()
            logging.info("Removed vote by member %d on message %d.", member_id, message_id)


async def _sync_message(bot: BobuxEconomyBot, message: disnake.Message):
    async with bot.db_connection.cursor() as db_cursor:
        await db_cursor.execute("""
            SELECT member_id, vote FROM votes WHERE message_id = ? AND channel_id = ?;
        """, (message.id, message.channel.id))
        deleted_rows = await db_cursor.fetchall()

        await db_cursor.execute("""
            DELETE FROM votes WHERE message_id = ? AND channel_id = ?;
        """, (message.id, message.channel.id))
        previous_votes: Dict[int, Vote] = { row["member_id"]: Vote(row["vote"]) for row in deleted_rows } if deleted_rows is not None else { }

    await add_reactions(message)
    for reaction in message.reactions:
        if isinstance(reaction.emoji, str):
            vote = None
            if reaction.emoji == UPVOTE_EMOJI:
                vote = Vote.UPVOTE
            elif reaction.emoji == DOWNVOTE_EMOJI:
                vote = Vote.DOWNVOTE

            if vote is not None:
                async for user in reaction.users():
                    if user != bot.user:
                        await record_vote(bot, message.id, message.channel.id, user.id, vote, commit=False, event=False)
                        await on_vote_raw(bot, message.id, message.channel.id, user.id, previous_votes.get(user.id), vote)
    await bot.db_connection.commit()

async def sync_votes(bot: BobuxEconomyBot):
    async with bot.db_connection.cursor() as db_cursor:
        # c.execute("""
        #     SELECT DISTINCT message_id, channel_id FROM votes;
        # """)
        # result: List[Tuple[int, int]] = c.fetchall()
        # # TODO: Parallelize this.
        # for message_id, channel_id in result:
        #     channel = await bot.fetch_channel(channel_id)
        #     message = await channel.fetch_message(message_id)
        #     await _sync_message(message)

        await db_cursor.execute("""
            SELECT memes_channel, last_memes_message FROM guilds
                WHERE memes_channel IS NOT NULL AND last_memes_message IS NOT NULL;
        """)
        result = await db_cursor.fetchall()

    for row in result:
        channel_id: int = row["memes_channel"]
        last_memes_message: int = row["last_memes_message"]

        channel = bot.get_channel(channel_id)
        if isinstance(channel, disnake.abc.Messageable):
            async for message in channel.history(after=disnake.Object(last_memes_message)):
                await _sync_message(bot, message)


POSTER_REWARD = 5.0
VOTER_REWARD = 2.5

async def on_vote_raw(bot: BobuxEconomyBot, message_id: int, channel_id: int, member_id: int, old: Optional[Vote], new: Optional[Vote]):
    channel = bot.get_channel(channel_id)
    if not isinstance(channel, disnake.abc.Messageable) or not isinstance(channel, disnake.abc.GuildChannel):
        return
    partial_message = channel.get_partial_message(message_id)
    member = channel.guild.get_member(member_id) or await channel.guild.fetch_member(member_id)
    if member is None:
        logging.error(f"Member {member_id} not found in guild {channel.guild.id}!")
        return
    await on_vote(bot.db_connection, partial_message, member, old, new)

async def on_vote(db_connection: aiosqlite.Connection, partial_message: disnake.PartialMessage, member: disnake.Member, old: Optional[Vote], new: Optional[Vote]):
    if old != new:
        logging.info(f"{member.id} on {partial_message.id}: {old} -> {new}")

        old_value = old or 0
        new_value = new or 0
        difference = new_value - old_value

        negative = difference < 0
        vote_removed = new is None
        poster_reward = balance.from_float(POSTER_REWARD * abs(difference))
        voter_reward = balance.from_float(VOTER_REWARD * abs(difference))

        message = await partial_message.fetch()
        poster = await get_original_author(db_connection, message, member.guild)
        if poster is None:
            logging.error(f"Member {message.author.id} not found in guild {member.guild.id}!")
            return

        if negative and not vote_removed:
            await balance.subtract(db_connection, poster, *poster_reward, allow_overdraft=True)
            await balance.add(db_connection, member, *voter_reward)
            logging.info(f"{member.id} on {partial_message.id}: -{poster_reward} bobux / {voter_reward} bobux")
        elif not negative and not vote_removed:
            await balance.add(db_connection, poster, *poster_reward)
            await balance.add(db_connection, member, *voter_reward)
            logging.info(f"{member.id} on {partial_message.id}: {poster_reward} bobux / {voter_reward} bobux")
        elif negative and vote_removed:
            await balance.subtract(db_connection, poster, *poster_reward)
            await balance.subtract(db_connection, member, *voter_reward)
            logging.info(f"{member.id} on {partial_message.id}: -{poster_reward} bobux / -{voter_reward} bobux")
        elif not negative and vote_removed:
            await balance.add(db_connection, poster, *poster_reward)
            await balance.subtract(db_connection, member, *voter_reward)
            logging.info(f"{member.id} on {partial_message.id}: {poster_reward} bobux / -{voter_reward} bobux")

async def get_original_author(db_connection: aiosqlite.Connection, message: disnake.Message, guild: disnake.Guild) -> Optional[disnake.Member]:
    if isinstance(message.author, disnake.Member):
        return message.author

    try:
        return guild.get_member(message.author.id) \
               or await guild.fetch_member(message.author.id)
    except disnake.NotFound:
        # Could be a webhook, check for puppeting
        if message.webhook_id is not None:
            async with db_connection.cursor() as db_cursor:
                await db_cursor.execute("""
                    SELECT member_id FROM webhooks WHERE webhook_id = ?;
                """, (message.webhook_id, ))
                row = await db_cursor.fetchone()

            if row is not None:
                member_id: int = row["member_id"]
                try:
                    return guild.get_member(member_id) \
                           or await guild.fetch_member(member_id)
                except disnake.NotFound:
                    return None

    return None
