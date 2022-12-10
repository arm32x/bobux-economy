import asyncio
from datetime import datetime, timezone
import logging
import random
import sqlite3
from typing import cast, Dict, List, Optional, Tuple, Union

import disnake as discord
from disnake.ext import commands

from bobux_economy import balance
from bobux_economy import database
from bobux_economy.database import connection as db
from bobux_economy.globals import client, UserFacingError
from bobux_economy import real_estate
from bobux_economy import subscriptions
from bobux_economy import upvotes
from bobux_economy import utils

logging.basicConfig(format="%(levelname)8s [%(name)s] %(message)s", level=logging.INFO)

logging.info("Initializing...")
database.migrate()

client.load_extension("bobux_economy.cogs.bal")
client.load_extension("bobux_economy.cogs.bot_info")
client.load_extension("bobux_economy.cogs.config")
client.load_extension("bobux_economy.cogs.real_estate")
client.load_extension("bobux_economy.cogs.relocate")
client.load_extension("bobux_economy.cogs.subscriptions")
client.load_extension("bobux_economy.cogs.voting")


async def handle_interaction_error(ctx: discord.Interaction, ex: Exception):
    if isinstance(ex, commands.CommandInvokeError):
        ex = ex.original
    if isinstance(ex, (UserFacingError, commands.CommandError)):
        await ctx.send(f"**Error:** {ex}", ephemeral=True)
    else:
        error_id = random.randint(0, 65535)
        logging.error(f"Internal error {error_id}: {ex}", exc_info=ex)
        await ctx.send(f"**Error:** An internal error has occurred. If reporting this error, please provide the error ID {error_id}.", ephemeral=True)
    logging.info("Sent error feedback")


@client.event
async def on_slash_command_error(ctx: discord.ApplicationCommandInteraction, ex: Exception):
    await handle_interaction_error(ctx, ex)

@client.event
async def on_user_command_error(ctx: discord.UserCommandInteraction, ex: Exception):
    await handle_interaction_error(ctx, ex)

@client.event
async def on_message_command_error(ctx: discord.MessageCommandInteraction, ex: Exception):
    await handle_interaction_error(ctx, ex)


if __name__ == "__main__":
    try:
        with open("data/token.txt", "r") as token_file:
            token = token_file.read()
        client.run(token)
    except KeyboardInterrupt:
        print("Stopping...")
        db.close()
