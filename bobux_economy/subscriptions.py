import asyncio
from contextlib import suppress

from datetime import datetime, time, timedelta
import logging
from typing import *

import discord

import balance
from database import connection as db
from globals import client

# Charge subscriptions every minute for testing purposes
DEBUG_TIMING = False

async def run():
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
        c = db.cursor()
        c.execute("""
            SELECT member_id, member_subscriptions.role_id, guild_id, price, spare_change
                FROM member_subscriptions
                INNER JOIN available_subscriptions USING(role_id);
        """)
        results: List[Tuple[int, int, int, int, bool]] = c.fetchall()

        for member_id, role_id, guild_id, price, spare_change in results:
            guild = client.get_guild(guild_id) or await client.fetch_guild(guild_id)
            member = guild.get_member(member_id) or await guild.fetch_member(member_id)

            try:
                balance.subtract(member, price, spare_change)
            except balance.InsufficientFundsError:
                role = guild.get_role(role_id)
                with suppress(discord.Forbidden):
                    await unsubscribe(member, role, reason="Insufficient funds for paid subscription")
                logging.info(f"Automatically unsubscribed @{member.display_name}#{member.discriminator} from ‘{role.name}’ due to insufficient funds.")


async def subscribe(member: discord.Member, role: discord.Role, *, reason: str = "Subscribed to paid subscription"):
    await member.add_roles(role, reason=reason)
    c = db.cursor()
    c.execute("""
        INSERT INTO member_subscriptions VALUES (?, ?, ?);
    """, (member.id, role.id, datetime.utcnow()))
    db.commit()

async def unsubscribe(member: discord.Member, role: discord.Role, *, reason: str = "Unsubscribed from paid subscription"):
    await member.remove_roles(role, reason=reason)
    c = db.cursor()
    c.execute("""
        DELETE FROM member_subscriptions WHERE member_id = ? AND role_id = ?;
    """, (member.id, role.id))
    db.commit()
