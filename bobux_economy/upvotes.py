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

async def remove_extra_reactions(client: discord.Client, message: Union[discord.Message, discord.PartialMessage], member: discord.Member, vote: Optional[Vote]):
    logging.debug("Removed extra reactions on message %d for member '%s'.", message.id, member.display_name)

    upvote_emoji, downvote_emoji = get_emojis(client)

    if vote != vote.UPVOTE:
        await message.remove_reaction(upvote_emoji, member)
    if vote != vote.DOWNVOTE:
        await message.remove_reaction(downvote_emoji, member)

def record_vote(message_id: int, channel_id: int, member_id: int, vote: Optional[Vote]):
    c = db.cursor()
    if vote is not None:
        c.execute("""
            INSERT INTO votes(message_id, channel_id, member_id, vote) VALUES (?, ?, ?, ?)
                ON CONFLICT(message_id, member_id) DO UPDATE SET vote = excluded.vote;
        """, (message_id, channel_id, member_id, vote))
        db.commit()
        logging.debug("Recorded %s by member %d on message %d.", vote.name.lower(), member_id, message_id)
    else:
        c.execute("""
            DELETE FROM votes WHERE message_id = ? AND channel_id = ? AND member_id = ?;
        """, (message_id, channel_id, member_id))
        db.commit()
        logging.debug("Removed vote by member %d on message %d.", member_id, message_id)

