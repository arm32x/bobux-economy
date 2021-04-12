from typing import *

import discord
from discord.ext import commands

from database import connection as db


def determine_prefix(_, message: discord.Message) -> str:
    c = db.cursor()
    c.execute("SELECT prefix FROM guilds WHERE id = ?;", (message.guild.id, ))
    guild_row: Optional[Tuple[str]] = c.fetchone()
    if guild_row is None:
        return "b$"
    else:
        return guild_row[0]

bot: commands.Bot = commands.Bot(command_prefix=determine_prefix)
