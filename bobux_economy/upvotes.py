import enum
import logging
from typing import *

import discord
from discord.ext import commands

from database import connection as db


# TODO: Make these configurable.
UPVOTE_EMOJI_ID = 806246359560486933
DOWNVOTE_EMOJI_ID = 806246395723645009

def get_emojis(client: discord.Client) -> Tuple[discord.Emoji, discord.Emoji]:
    upvote_emoji = client.get_emoji(UPVOTE_EMOJI_ID)
    downvote_emoji = client.get_emoji(DOWNVOTE_EMOJI_ID)

    if upvote_emoji is None or downvote_emoji is None:
        raise commands.CommandError("Could not get upvote or downvote emoji.")

    return upvote_emoji, downvote_emoji


class Vote(enum.IntEnum):
    UPVOTE = 1
    DOWNVOTE = -1


async def add_reactions(client: discord.Client, message: Union[discord.Message, discord.PartialMessage]):
    upvote_emoji, downvote_emoji = get_emojis(client)

    await message.add_reaction(upvote_emoji)
    await message.add_reaction(downvote_emoji)

    logging.debug("Added upvote and downvote reactions to message %d.", message.id)

recently_removed_reactions: List[Tuple[int, Vote, int]] = [ ]

async def user_reacted(message: discord.Message, user: discord.User, emoji: discord.Emoji) -> bool:
    for reaction in message.reactions:
        if reaction.emoji == emoji:
            async for reaction_user in reaction.users():
                if reaction_user == user:
                    return True
    return False

async def remove_extra_reactions(client: discord.Client, message: discord.Message, user: discord.User, vote: Optional[Vote]):
    logging.debug("Removed extra reactions on message %d for member '%s'.", message.id, user.display_name)

    upvote_emoji, downvote_emoji = get_emojis(client)

    if vote != Vote.UPVOTE and await user_reacted(message, user, upvote_emoji):
        recently_removed_reactions.append((message.id, Vote.UPVOTE, user.id))
        await message.remove_reaction(upvote_emoji, user)
    if vote != Vote.DOWNVOTE and await user_reacted(message, user, downvote_emoji):
        recently_removed_reactions.append((message.id, Vote.DOWNVOTE, user.id))
        await message.remove_reaction(downvote_emoji, user)


def record_vote(message_id: int, channel_id: int, member_id: int, vote: Vote):
    c = db.cursor()
    c.execute("""
        INSERT INTO votes(message_id, channel_id, member_id, vote) VALUES (?, ?, ?, ?)
            ON CONFLICT(message_id, member_id) DO UPDATE SET vote = excluded.vote;
    """, (message_id, channel_id, member_id, vote))
    db.commit()
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
