import discord
from discord_slash import SlashCommand


class CommandError(RuntimeError):
    """An Exception type for user errors in commands, such as invalid input"""

    def __init__(self, message: str):
        super().__init__(message)


client = discord.Client()

slash = SlashCommand(client, sync_commands=True)
