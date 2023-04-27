import logging
import random

import disnake
from disnake.ext import commands

from bobux_economy.bot import BobuxEconomyBot
from bobux_economy.utils import UserFacingError

logger = logging.getLogger(__name__)


class ErrorHandling(commands.Cog):
    @classmethod
    def get_error_message(cls, ex: Exception):
        if isinstance(ex, commands.CommandInvokeError):
            ex = ex.original

        if isinstance(ex, (UserFacingError, commands.CommandError)):
            return f"**Error:** {ex}"
        else:
            error_id = random.randint(0, 65535)
            logging.error(f"Internal error D-{error_id}: {ex}", exc_info=ex)
            return (
                f"**Error:** An internal error has occurred. "
                f"If reporting this error, please provide the error ID `D-{error_id}`."
            )

    @classmethod
    async def send_error_feedback(cls, inter: disnake.Interaction, ex: Exception):
        await inter.response.send_message(
            cls.get_error_message(ex),
            allowed_mentions=disnake.AllowedMentions.none(),
            ephemeral=True,
        )

    @classmethod
    async def edit_into_error_feedback(cls, inter: disnake.Interaction, ex: Exception):
        await inter.response.edit_message(
            cls.get_error_message(ex),
            allowed_mentions=disnake.AllowedMentions.none(),
            components=[],
        )

    @commands.Cog.listener(name="on_slash_command_error")
    @commands.Cog.listener(name="on_user_command_error")
    @commands.Cog.listener(name="on_message_command_error")
    async def on_interaction_error(
        self, inter: disnake.ApplicationCommandInteraction, ex: Exception
    ):
        await self.__class__.send_error_feedback(inter, ex)


def setup(bot: BobuxEconomyBot):
    bot.add_cog(ErrorHandling())
