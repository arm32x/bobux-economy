import enum
import logging
from typing import *

import discord
from discord.ext import commands

from database import connection as db


# TODO: Make these configurable.
UPVOTE_EMOJI_ID = 806246359560486933
DOWNVOTE_EMOJI_ID = 806246395723645009

def _get_emojis(client: discord.Client) -> Tuple[discord.Emoji, discord.Emoji]:
    upvote_emoji = client.get_emoji(UPVOTE_EMOJI_ID)
    downvote_emoji = client.get_emoji(DOWNVOTE_EMOJI_ID)

    if upvote_emoji is None or downvote_emoji is None:
        raise commands.CommandError("Could not get upvote or downvote emoji.")

    return upvote_emoji, downvote_emoji


class Vote(enum.IntEnum):
    UPVOTE = 1
    DOWNVOTE = -1


async def add_reactions(client: discord.Client, message: Union[discord.Message, discord.PartialMessage]):
    upvote_emoji, downvote_emoji = _get_emojis(client)

    await message.add_reaction(upvote_emoji)
    await message.add_reaction(downvote_emoji)

    logging.debug("Added upvote and downvote reactions to message %d.", message.id)

recently_removed_reactions: List[Tuple[int, Vote, int]] = [ ]

async def _user_reacted(message: discord.Message, user: discord.User, emoji: discord.Emoji) -> bool:
    for reaction in message.reactions:
        if reaction.emoji == emoji:
            async for reaction_user in reaction.users():
                if reaction_user == user:
                    return True
    return False

async def remove_extra_reactions(client: discord.Client, message: discord.Message, user: discord.User, vote: Optional[Vote]):
    logging.debug("Removed extra reactions on message %d for member '%s'.", message.id, user.display_name)

    upvote_emoji, downvote_emoji = _get_emojis(client)

    if vote != Vote.UPVOTE and await _user_reacted(message, user, upvote_emoji):
        recently_removed_reactions.append((message.id, Vote.UPVOTE, user.id))
        await message.remove_reaction(upvote_emoji, user)
    if vote != Vote.DOWNVOTE and await _user_reacted(message, user, downvote_emoji):
        recently_removed_reactions.append((message.id, Vote.DOWNVOTE, user.id))
        await message.remove_reaction(downvote_emoji, user)


def record_vote(message_id: int, channel_id: int, member_id: int, vote: Vote, commit: bool = True):
    c = db.cursor()
    c.execute("""
        INSERT INTO votes(message_id, channel_id, member_id, vote) VALUES (?, ?, ?, ?)
            ON CONFLICT(message_id, member_id) DO UPDATE SET vote = excluded.vote;
    """, (message_id, channel_id, member_id, vote))
    if commit: db.commit()
    logging.debug("Recorded %s by member %d on message %d.", vote.name.lower(), member_id, message_id)

def delete_vote(message_id: int, member_id: int, check_equal_to: Optional[Vote] = None):
    c = db.cursor()
    if check_equal_to is not None:
        c.execute("""
            DELETE FROM votes WHERE message_id = ? AND member_id = ? AND vote = ?;
        """, (message_id, member_id, check_equal_to))
        db.commit()
        logging.debug("Removed vote by member %d on message %d, if it was %s.", member_id, message_id, "an upvote" if check_equal_to == Vote.UPVOTE else "a downvote")
    else:
        c.execute("""
            DELETE FROM votes WHERE message_id = ? AND member_id = ?;
        """, (message_id, member_id))
        db.commit()
        logging.debug("Removed vote by member %d on message %d.", member_id, message_id)


async def _sync_message(client: discord.Client, message: discord.Message):
    c = db.cursor()
    c.execute("""
        DELETE FROM votes WHERE message_id = ? AND channel_id = ?;
    """, (message.id, message.channel.id))

    await add_reactions(client, message)
    for reaction in message.reactions:
        if not isinstance(reaction.emoji, str):
            vote = None
            if reaction.emoji.id == UPVOTE_EMOJI_ID:
                vote = Vote.UPVOTE
            elif reaction.emoji.id == DOWNVOTE_EMOJI_ID:
                vote = Vote.DOWNVOTE

            if vote is not None:
                async for user in reaction.users():
                    if user != client.user:
                        record_vote(message.id, message.channel.id, user.id, vote, commit=False)
    db.commit()

async def sync_votes(client: discord.Client):
    c = db.cursor()
    c.execute("""
        SELECT DISTINCT message_id, channel_id FROM votes;
    """)
    result: List[Tuple[int, int]] = c.fetchall()
    # TODO: Parallelize this.
    for message_id, channel_id in result:
        message = await client.get_channel(channel_id).fetch_message(message_id)
        await _sync_message(client, message)

    c.execute("""
        SELECT memes_channel, last_memes_message FROM guilds
            WHERE memes_channel IS NOT NULL AND last_memes_message IS NOT NULL;
    """)
    result = c.fetchall()
    for channel_id, last_memes_message in result:
        channel = client.get_channel(channel_id)
        if isinstance(channel, discord.TextChannel):
            async for message in channel.history(after=discord.Object(last_memes_message)):
                await _sync_message(client, message)
