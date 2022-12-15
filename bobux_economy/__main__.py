import asyncio
from contextlib import suppress
import logging
import sqlite3
import sys

import yoyo

from bobux_economy.bot import BobuxEconomyBot


async def main():
    logging.basicConfig(format="%(levelname)8s [%(name)s] %(message)s", level=logging.INFO)
    logging.info("Initializing...")

    # Run database migrations.
    yoyo_backend = yoyo.get_backend("sqlite:///data/bobux.db")
    yoyo_migrations = yoyo.read_migrations("migrations")
    with yoyo_backend.lock():
        yoyo_backend.apply_migrations(yoyo_backend.to_apply(yoyo_migrations))

    db_connection = sqlite3.connect("data/bobux.db", detect_types=sqlite3.PARSE_DECLTYPES)
    # This will not affect existing code since sqlite3.Row objects support
    # the same operations as tuples. However, this allows new code to take
    # advantage of features provided by sqlite3.Row.
    db_connection.row_factory = sqlite3.Row

    # TODO: Load list test guilds from a file.
    bot = BobuxEconomyBot(db_connection, test_guilds=[766073081449545798])

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
