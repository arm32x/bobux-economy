import math
from typing import Tuple

import aiosqlite
import disnake

from bobux_economy.utils import UserFacingError


class InsufficientFundsError(UserFacingError):
    def __init__(self):
        super().__init__("Insufficient funds")

class NegativeAmountError(UserFacingError):
    def __init__(self):
        super().__init__("Amount must not be negative")


async def get(db_connection: aiosqlite.Connection, member: disnake.Member) -> Tuple[int, bool]:
    async with db_connection.cursor() as db_cursor:
        await db_cursor.execute("""
            SELECT balance, spare_change FROM members WHERE id = ? AND guild_id = ?;
        """, (member.id, member.guild.id))
        row = await db_cursor.fetchone()

        if row is not None:
            return (row["balance"], row["spare_change"])
        else:
            return (0, False)

async def set(db_connection: aiosqlite.Connection, member: disnake.Member, amount: int, spare_change: bool):
    async with db_connection.cursor() as db_cursor:
        await db_cursor.execute("""
            INSERT INTO members(id, guild_id, balance, spare_change) VALUES(?, ?, ?, ?)
                ON CONFLICT(id, guild_id) DO UPDATE SET balance = excluded.balance, spare_change = excluded.spare_change;
        """, (member.id, member.guild.id, amount, spare_change))
        await db_connection.commit()

async def add(db_connection: aiosqlite.Connection, member: disnake.Member, amount: int, spare_change: bool):
    if amount < 0:
        raise NegativeAmountError()

    balance, balance_spare_change = await get(db_connection, member)

    balance += amount
    if spare_change and balance_spare_change:
        balance += 1
    balance_spare_change ^= spare_change

    await set(db_connection, member, balance, balance_spare_change)

async def subtract(db_connection: aiosqlite.Connection, member: disnake.Member, amount: int, spare_change: bool, allow_overdraft=False):
    if amount < 0:
        raise NegativeAmountError()

    balance, balance_spare_change = await get(db_connection, member)

    if not allow_overdraft and balance < amount or balance == amount and spare_change and not balance_spare_change:
        raise InsufficientFundsError()

    balance -= amount
    if spare_change and not balance_spare_change:
        balance -= 1
    balance_spare_change ^= spare_change

    await set(db_connection, member, balance, balance_spare_change)


def from_float(amount: float) -> Tuple[int, bool]:
    return int(amount), not amount.is_integer()

def from_float_floor(amount: float) -> Tuple[int, bool]:
    rounded = math.floor(amount * 2) / 2
    return from_float(rounded)

def from_float_ceil(amount: float) -> Tuple[int, bool]:
    rounded = math.ceil(amount * 2) / 2
    return from_float(rounded)

def from_float_round(amount: float) -> Tuple[int, bool]:
    rounded = round(amount * 2) / 2
    return from_float(rounded)

def to_float(amount: int, spare_change: bool) -> float:
    return amount + (0.5 if spare_change else 0)


def to_string(amount: int, spare_change: bool) -> str:
    if spare_change:
        return f"{amount} bobux and some spare change"
    else:
        return f"{amount} bobux"
