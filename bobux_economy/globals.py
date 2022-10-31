from disnake.ext import commands

from bobux_economy.bot import BobuxEconomyBot
from bobux_economy.database import connection as db_connection


class UserFacingError(RuntimeError):
    """An Exception type for user errors in commands, such as invalid input"""

    def __init__(self, message: str):
        super().__init__(message)


client = BobuxEconomyBot(db_connection, test_guilds=[766073081449545798])
