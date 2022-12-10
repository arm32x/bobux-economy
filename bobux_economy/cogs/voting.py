import logging
from contextlib import closing

import disnake
from disnake.ext import commands

from bobux_economy import upvotes
from bobux_economy.bot import BobuxEconomyBot

logger = logging.getLogger(__name__)


class Voting(commands.Cog):
    bot: BobuxEconomyBot

    def __init__(self, bot: BobuxEconomyBot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_ready(self):
        logger.info("Synchronizing votes...")
        await upvotes.sync_votes()

    @commands.Cog.listener()
    async def on_message(self, message: disnake.Message):
        if message.author == self.bot.user or message.guild is None:
            return

        if upvotes.message_eligible(message):
            await upvotes.add_reactions(message)
            with closing(self.bot.db_connection.cursor()) as db_cursor:
                db_cursor.execute(
                    """
                    INSERT INTO
                        guilds (id, last_memes_message)
                    VALUES
                        (?, ?) ON CONFLICT (id) DO
                    UPDATE
                    SET
                        last_memes_message = excluded.last_memes_message
                    """,
                    (message.guild.id, message.id),
                )
                self.bot.db_connection.commit()

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload: disnake.RawReactionActionEvent):
        if payload.user_id == self.bot.user.id:
            # This reaction was added by the bot, ignore it.
            return
        if payload.guild_id is None:
            return

        channel = self.bot.get_channel(payload.channel_id)
        if not isinstance(channel, disnake.abc.Messageable):
            logger.error("Reaction added in non-messageable channel (how?)")
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

        guild = self.bot.get_guild(payload.guild_id) or message.guild
        if guild is None:
            return

        original_author = await upvotes.get_original_author(message, guild)
        if original_author is None:
            return

        if payload.user_id == original_author.id:
            # The poster voted on their own message.
            await upvotes.remove_extra_reactions(message, payload.member, None)
            return

        await upvotes.record_vote(
            payload.message_id, payload.channel_id, payload.member.id, vote
        )
        await upvotes.remove_extra_reactions(message, payload.member, vote)

    @commands.Cog.listener()
    async def on_raw_reaction_remove(self, payload: disnake.RawReactionActionEvent):
        if payload.user_id == self.bot.user.id:
            # The removed reaction was from the bot.
            return

        channel = self.bot.get_channel(payload.channel_id)
        if not isinstance(channel, disnake.abc.Messageable):
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

        if (
            payload.message_id,
            vote,
            payload.user_id,
        ) in upvotes.recently_removed_reactions:
            upvotes.recently_removed_reactions.remove(
                (payload.message_id, vote, payload.user_id)
            )
            return

        await upvotes.delete_vote(
            payload.message_id, payload.channel_id, payload.user_id, check_equal_to=vote
        )
        user = self.bot.get_user(payload.user_id) or await self.bot.fetch_user(
            payload.user_id
        )
        await upvotes.remove_extra_reactions(message, user, None)


def setup(bot: BobuxEconomyBot):
    bot.add_cog(Voting(bot))