import asyncio
from contextlib import suppress
import logging
import sqlite3
import sys

import aiosqlite
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
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
        scheduler.add_jobstore(SQLAlchemyJobStore(url="sqlite+pysqlite:///data/scheduler.db"))

        async def start_scheduler():
            scheduler.start()

        # TODO: Load list of test guilds from a file.
        bot = BobuxEconomyBot(
            db_connection, scheduler, test_guilds=[766073081449545798]
        )
        bot.add_listener(start_scheduler, "on_ready")

        bot.load_extension("bobux_economy.cogs.bal")
        bot.load_extension("bobux_economy.cogs.bot_info")
        bot.load_extension("bobux_economy.cogs.config")
        bot.load_extension("bobux_economy.cogs.error_handling")
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
