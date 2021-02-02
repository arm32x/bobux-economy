import discord
from discord.ext import commands


# TODO: Make these configurable.
UPVOTE_EMOJI_ID = 806246359560486933
DOWNVOTE_EMOJI_ID = 806246395723645009


async def add_reactions(bot: commands.Bot, message: discord.Message):
    upvote_emoji = bot.get_emoji(UPVOTE_EMOJI_ID)
    downvote_emoji = bot.get_emoji(DOWNVOTE_EMOJI_ID)

    if upvote_emoji is None or downvote_emoji is None:
        raise commands.CommandError("Could not get upvote or downvote emoji.")

    await message.add_reaction(upvote_emoji)
    await message.add_reaction(downvote_emoji)