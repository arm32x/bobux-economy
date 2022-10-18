from disnake.ext import commands


class CommandError(RuntimeError):
    """An Exception type for user errors in commands, such as invalid input"""

    def __init__(self, message: str):
        super().__init__(message)


client = commands.InteractionBot(sync_commands=True, test_guilds=[766073081449545798])
