from typing import Optional, Sequence

import aiosqlite
from apscheduler.schedulers.asyncio import AsyncIOScheduler
import disnake
from disnake.ext import commands


class BobuxEconomyBot(commands.InteractionBot):
    db_connection: aiosqlite.Connection
    scheduler: AsyncIOScheduler

    def __init__(
        self,
        db_connection: aiosqlite.Connection,
        scheduler: AsyncIOScheduler,
        *,
        test_guilds: Optional[Sequence[int]] = None
    ):
        super().__init__(
            intents=disnake.Intents(
                # General cache usage throughout the bot.
                guilds=True,
                # Detect new messages in vote channels.
                guild_messages=True,
                # Detect new votes on messages in vote channels.
                guild_reactions=True,
                # Detect speech bubbles in vote channels.
                message_content=True,
            ),
            sync_commands=True,
            test_guilds=test_guilds,
        )
        self.db_connection = db_connection
        self.scheduler = scheduler
