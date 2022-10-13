import enum
import logging
from typing import List, Optional, Tuple, Union

import discord

from bobux_economy import balance
from bobux_economy.database import connection as db
from bobux_economy.globals import client

# TODO: Make these configurable.
UPVOTE_EMOJI = "⬆️"
DOWNVOTE_EMOJI = "⬇️"


class Vote(enum.IntEnum):
    UPVOTE = 1
    DOWNVOTE = -1

def message_eligible(message: discord.Message) -> bool:
    if message.guild is None:
        return False

    c = db.cursor()
    c.execute("SELECT memes_channel FROM guilds WHERE id = ?;", (message.guild.id, ))
    memes_channel_id: Optional[int] = (c.fetchone() or (None, ))[0]

    return (
        memes_channel_id is not None
        and message.channel.id == memes_channel_id
        and not message.content.startswith("💬")
        and not message.content.startswith("🗨️")
    )

async def add_reactions(message: Union[discord.Message, discord.PartialMessage]):
    await message.add_reaction(UPVOTE_EMOJI)
    await message.add_reaction(DOWNVOTE_EMOJI)

    logging.info("Added upvote and downvote reactions to message %d.", message.id)

recently_removed_reactions: List[Tuple[int, Vote, int]] = [ ]

async def _user_reacted(message: discord.Message, user: Union[discord.User, discord.Member], emoji: Union[discord.Emoji, discord.PartialEmoji, str]) -> bool:
    for reaction in message.reactions:
        if reaction.emoji == emoji:
            async for reaction_user in reaction.users():
                if reaction_user == user:
                    return True
    return False

async def remove_extra_reactions(message: discord.Message, user: Union[discord.User, discord.Member], vote: Optional[Vote]):
    logging.info("Removed extra reactions on message %d for member '%s'.", message.id, user.display_name)

    if vote != Vote.UPVOTE and await _user_reacted(message, user, UPVOTE_EMOJI):
        recently_removed_reactions.append((message.id, Vote.UPVOTE, user.id))
        await message.remove_reaction(UPVOTE_EMOJI, user)
    if vote != Vote.DOWNVOTE and await _user_reacted(message, user, DOWNVOTE_EMOJI):
        recently_removed_reactions.append((message.id, Vote.DOWNVOTE, user.id))
        await message.remove_reaction(DOWNVOTE_EMOJI, user)


async def record_vote(message_id: int, channel_id: int, member_id: int, vote: Vote, commit: bool = True, event: bool = True):
    c = db.cursor()

    c.execute("""
        SELECT vote FROM votes WHERE message_id = ? AND channel_id = ? AND member_id = ?;
    """, (message_id, channel_id, member_id))
    previous_vote_code: Optional[int] = (c.fetchone() or (None, ))[0]
    previous_vote: Optional[Vote] = Vote(previous_vote_code) if previous_vote_code is not None else None

    c.execute("""
        INSERT INTO votes(message_id, channel_id, member_id, vote) VALUES (?, ?, ?, ?)
            ON CONFLICT(message_id, member_id) DO UPDATE SET vote = excluded.vote;
    """, (message_id, channel_id, member_id, vote))

    logging.info("Recorded %s by member %d on message %d.", vote.name.lower(), member_id, message_id)

    if event:
        await on_vote_raw(message_id, channel_id, member_id, previous_vote, vote)

    if commit: db.commit()

async def delete_vote(message_id: int, channel_id: int, member_id: int, check_equal_to: Optional[Vote] = None, commit: bool = True, event: bool = True):
    c = db.cursor()
    if check_equal_to is not None:
        c.execute("""
            SELECT vote FROM votes WHERE message_id = ? AND member_id = ? AND vote = ?;
        """, (message_id, member_id, check_equal_to))
        previous_vote: Optional[int] = (c.fetchone() or (None, ))[0]
        c.execute("""
            DELETE FROM votes WHERE message_id = ? AND member_id = ? AND vote = ?;
        """, (message_id, member_id, check_equal_to))

        if event:
            if previous_vote is not None:
                await on_vote_raw(message_id, channel_id, member_id, Vote(previous_vote), None)

        if commit: db.commit()
        logging.info("Removed vote by member %d on message %d, if it was %s.", member_id, message_id, "an upvote" if check_equal_to == Vote.UPVOTE else "a downvote")

    else:
        c.execute("""
            SELECT vote FROM votes WHERE message_id = ? AND member_id = ?;
        """, (message_id, member_id))
        previous_vote: Optional[int] = (c.fetchone() or (None, ))[0]
        c.execute("""
            DELETE FROM votes WHERE message_id = ? AND member_id = ?;
        """, (message_id, member_id))

        if event:
            if previous_vote is not None:
                await on_vote_raw(message_id, channel_id, member_id, Vote(previous_vote), None)

        if commit: db.commit()
        logging.info("Removed vote by member %d on message %d.", member_id, message_id)


async def _sync_message(message: discord.Message):
    c = db.cursor()
    c.execute("""
        SELECT member_id, vote FROM votes WHERE message_id = ? AND channel_id = ?;
    """, (message.id, message.channel.id))
    deleted_rows: List[Tuple[int, int]] = c.fetchall()
    c.execute("""
        DELETE FROM votes WHERE message_id = ? AND channel_id = ?;
    """, (message.id, message.channel.id))
    previous_votes = dict([ (u, Vote(v)) for (u, v) in deleted_rows ]) if deleted_rows is not None else { }

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
                    if user != client.user:
                        await record_vote(message.id, message.channel.id, user.id, vote, commit=False, event=False)
                        await on_vote_raw(message.id, message.channel.id, user.id, previous_votes.get(user.id), vote)
    db.commit()

async def sync_votes():
    c = db.cursor()
    # c.execute("""
    #     SELECT DISTINCT message_id, channel_id FROM votes;
    # """)
    # result: List[Tuple[int, int]] = c.fetchall()
    # # TODO: Parallelize this.
    # for message_id, channel_id in result:
    #     channel = await bot.fetch_channel(channel_id)
    #     message = await channel.fetch_message(message_id)
    #     await _sync_message(message)

    c.execute("""
        SELECT memes_channel, last_memes_message FROM guilds
            WHERE memes_channel IS NOT NULL AND last_memes_message IS NOT NULL;
    """)
    result: List[Tuple[int, int]] = c.fetchall()
    for channel_id, last_memes_message in result:
        channel = client.get_channel(channel_id)
        if isinstance(channel, discord.TextChannel):
            async for message in channel.history(after=discord.Object(last_memes_message)):
                await _sync_message(message)


POSTER_REWARD = 5.0
VOTER_REWARD = 2.5

async def on_vote_raw(message_id: int, channel_id: int, member_id: int, old: Optional[Vote], new: Optional[Vote]):
    channel = client.get_channel(channel_id)
    if not isinstance(channel, discord.TextChannel):
        return
    partial_message = channel.get_partial_message(message_id)
    member = channel.guild.get_member(member_id) or await channel.guild.fetch_member(member_id)
    if member is None:
        logging.error(f"Member {member_id} not found in guild {channel.guild.id}!")
        return
    await on_vote(partial_message, member, old, new)

async def on_vote(partial_message: discord.PartialMessage, member: discord.Member, old: Optional[Vote], new: Optional[Vote]):
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
        poster = await get_original_author(message, member.guild)
        if poster is None:
            logging.error(f"Member {message.author.id} not found in guild {member.guild.id}!")
            return

        if negative and not vote_removed:
            balance.subtract(poster, *poster_reward, allow_overdraft=True)
            balance.add(member, *voter_reward)
            logging.info(f"{member.id} on {partial_message.id}: -{poster_reward} bobux / {voter_reward} bobux")
        elif not negative and not vote_removed:
            balance.add(poster, *poster_reward)
            balance.add(member, *voter_reward)
            logging.info(f"{member.id} on {partial_message.id}: {poster_reward} bobux / {voter_reward} bobux")
        elif negative and vote_removed:
            balance.subtract(poster, *poster_reward)
            balance.subtract(member, *voter_reward)
            logging.info(f"{member.id} on {partial_message.id}: -{poster_reward} bobux / -{voter_reward} bobux")
        elif not negative and vote_removed:
            balance.add(poster, *poster_reward)
            balance.subtract(member, *voter_reward)
            logging.info(f"{member.id} on {partial_message.id}: {poster_reward} bobux / -{voter_reward} bobux")

async def get_original_author(message: discord.Message, guild: discord.Guild) -> Optional[discord.Member]:
    if isinstance(message.author, discord.Member):
        return message.author

    try:
        return guild.get_member(message.author.id) \
               or await guild.fetch_member(message.author.id)
    except discord.NotFound:
        # Could be a webhook, check for puppeting
        if message.webhook_id is not None:
            c = db.cursor()
            c.execute("""
                SELECT member_id FROM webhooks WHERE webhook_id = ?;
            """, (message.webhook_id, ))
            member_id: Optional[int] = (c.fetchone() or (None, ))[0]
            if member_id is not None:
                try:
                    return guild.get_member(member_id) \
                           or await guild.fetch_member(member_id)
                except discord.NotFound:
                    return None

    return None
