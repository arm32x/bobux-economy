import asyncio
import sqlite3
from contextlib import closing, suppress

from datetime import datetime, time, timedelta
import logging
from typing import List, Tuple

import disnake

from bobux_economy import balance
from bobux_economy.bot import BobuxEconomyBot

# Charge subscriptions every minute for testing purposes
DEBUG_TIMING = False

async def run(bot: BobuxEconomyBot):
    while True:
        if DEBUG_TIMING:
            # Wait one minute
            next_charge_datetime = datetime.now() + timedelta(minutes=1)
            sleep_seconds = 60
        else:
            # Wait until next Monday at midnight local time
            now = datetime.now()
            today = now.date()
            next_charge_date = today + timedelta(days=(0 - today.weekday()) % 7)
            next_charge_datetime = datetime.combine(next_charge_date, time(0, 0, 0))
            if next_charge_datetime <= now:
                next_charge_datetime += timedelta(days=7)
            sleep_seconds = (next_charge_datetime - now).total_seconds()
        logging.info(f"Next subscriptions charge at {next_charge_datetime}, in {sleep_seconds} seconds")
        await asyncio.sleep(sleep_seconds)

        # Find all active subscriptions across all guilds
        with closing(bot.db_connection.cursor()) as db_cursor:
            db_cursor.execute("""
                SELECT member_id, member_subscriptions.role_id, guild_id, price, spare_change
                    FROM member_subscriptions
                    INNER JOIN available_subscriptions USING(role_id);
            """)
            results: List[Tuple[int, int, int, int, bool]] = db_cursor.fetchall()

        for member_id, role_id, guild_id, price, spare_change in results:
            guild = bot.get_guild(guild_id) or await bot.fetch_guild(guild_id)
            member = guild.get_member(member_id) or await guild.fetch_member(member_id)

            try:
                balance.subtract(bot.db_connection, member, price, spare_change)
            except balance.InsufficientFundsError:
                role = guild.get_role(role_id)
                if role is not None:
                    with suppress(disnake.Forbidden):
                        await unsubscribe(bot.db_connection, member, role, reason="Insufficient funds for paid subscription")
                    logging.info(f"Automatically unsubscribed @{member.display_name}#{member.discriminator} from ‘{role.name}’ due to insufficient funds.")


async def subscribe(db_connection: sqlite3.Connection, member: disnake.Member, role: disnake.Role, *, reason: str = "Subscribed to paid subscription"):
    await member.add_roles(role, reason=reason)
    with closing(db_connection.cursor()) as db_cursor:
        db_cursor.execute("""
            INSERT INTO member_subscriptions VALUES (?, ?, ?);
        """, (member.id, role.id, datetime.utcnow()))
        db_connection.commit()

async def unsubscribe(db_connection: sqlite3.Connection, member: disnake.Member, role: disnake.Role, *, reason: str = "Unsubscribed from paid subscription"):
    await member.remove_roles(role, reason=reason)
    with closing(db_connection.cursor()) as db_cursor:
        db_cursor.execute("""
            DELETE FROM member_subscriptions WHERE member_id = ? AND role_id = ?;
        """, (member.id, role.id))
        db_connection.commit()
