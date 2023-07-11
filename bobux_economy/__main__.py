import asyncio
from contextlib import suppress
import logging
import sqlite3
import sys
from typing import List

import aiosqlite
from apscheduler.schedulers.asyncio import AsyncIOScheduler
import yoyo

from bobux_economy.bot import BobuxEconomyBot


async def main():
    logging.basicConfig(
        format="%(levelname)8s [%(name)s] %(message)s", level=logging.INFO
    )
    logging.info("Initializing...")

    # Run database migrations.
    yoyo_backend = yoyo.get_backend("sqlite:///data/bobux.db")
    yoyo_migrations = yoyo.read_migrations("migrations")
    with yoyo_backend.lock():
        yoyo_backend.apply_migrations(yoyo_backend.to_apply(yoyo_migrations))

    async with aiosqlite.connect(
        "data/bobux.db", detect_types=sqlite3.PARSE_DECLTYPES
    ) as db_connection:
        # This will not affect existing code since sqlite3.Row objects
        # support the same operations as tuples.
        db_connection.row_factory = sqlite3.Row

        # Initialize the scheduler.
        scheduler = AsyncIOScheduler()

        async def start_scheduler():
            scheduler.start()

        # Load list of test guilds from a file.
        test_guilds: List[int]
        try:
            with open("data/test_guilds.txt", "r") as test_guilds_file:
                test_guilds = [int(line) for line in test_guilds_file.readlines()]
        except FileNotFoundError:
            test_guilds = []

        logging.info(f"Test guilds: {test_guilds}")

        bot = BobuxEconomyBot(db_connection, scheduler, test_guilds=test_guilds)
        bot.add_listener(start_scheduler, "on_ready")

        bot.load_extension("bobux_economy.cogs.bal")
        bot.load_extension("bobux_economy.cogs.bot_info")
        bot.load_extension("bobux_economy.cogs.error_handling")
        bot.load_extension("bobux_economy.cogs.guild_config")
        bot.load_extension("bobux_economy.cogs.real_estate")
        bot.load_extension("bobux_economy.cogs.relocate")
        bot.load_extension("bobux_economy.cogs.subscriptions")
        bot.load_extension("bobux_economy.cogs.voting")

        with open("data/token.txt", "r") as token_file:
            token = token_file.read()

        await bot.start(token)


if __name__ == "__main__":
    with suppress(KeyboardInterrupt):
        sys.exit(asyncio.run(main()))
