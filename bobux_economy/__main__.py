import logging

from bobux_economy import database
from bobux_economy.database import connection as db
from bobux_economy.globals import client

logging.basicConfig(format="%(levelname)8s [%(name)s] %(message)s", level=logging.INFO)

logging.info("Initializing...")
database.migrate()

client.load_extension("bobux_economy.cogs.bal")
client.load_extension("bobux_economy.cogs.bot_info")
client.load_extension("bobux_economy.cogs.config")
client.load_extension("bobux_economy.cogs.error_handling")
client.load_extension("bobux_economy.cogs.real_estate")
client.load_extension("bobux_economy.cogs.relocate")
client.load_extension("bobux_economy.cogs.subscriptions")
client.load_extension("bobux_economy.cogs.voting")


if __name__ == "__main__":
    try:
        with open("data/token.txt", "r") as token_file:
            token = token_file.read()
        client.run(token)
    except KeyboardInterrupt:
        print("Stopping...")
        db.close()
