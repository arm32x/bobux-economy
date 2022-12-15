import sqlite3
from typing import Optional, Sequence

import aiosqlite
from disnake.ext import commands


class BobuxEconomyBot(commands.InteractionBot):
    db_connection: aiosqlite.Connection

    def __init__(
        self,
        db_connection: aiosqlite.Connection,
        *,
        test_guilds: Optional[Sequence[int]] = None
    ):
        super().__init__(sync_commands=True, test_guilds=test_guilds)
        self.db_connection = db_connection
