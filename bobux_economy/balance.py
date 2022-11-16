from contextlib import closing
import math
from typing import Tuple

import disnake as discord

from bobux_economy.database import connection as db
from bobux_economy.globals import UserFacingError


class InsufficientFundsError(UserFacingError):
    def __init__(self):
        super().__init__("Insufficient funds")

class NegativeAmountError(UserFacingError):
    def __init__(self):
        super().__init__("Amount must not be negative")


def get(member: discord.Member) -> Tuple[int, bool]:
    # TODO: Don't hardcode the database connection.
    with closing(db.cursor()) as c:
        c.execute("""
            SELECT balance, spare_change FROM members WHERE id = ? AND guild_id = ?;
        """, (member.id, member.guild.id))
        return c.fetchone() or (0, False)

def set(member: discord.Member, amount: int, spare_change: bool):
    # TODO: Don't hardcode the database connection.
    with closing(db.cursor()) as c:
        c.execute("""
            INSERT INTO members(id, guild_id, balance, spare_change) VALUES(?, ?, ?, ?)
                ON CONFLICT(id, guild_id) DO UPDATE SET balance = excluded.balance, spare_change = excluded.spare_change;
        """, (member.id, member.guild.id, amount, spare_change))
        db.commit()

def add(member: discord.Member, amount: int, spare_change: bool):
    if amount < 0:
        raise NegativeAmountError()

    balance, balance_spare_change = get(member)

    balance += amount
    if spare_change and balance_spare_change:
        balance += 1
    balance_spare_change ^= spare_change

    set(member, balance, balance_spare_change)

def subtract(member: discord.Member, amount: int, spare_change: bool, allow_overdraft=False):
    if amount < 0:
        raise NegativeAmountError()

    balance, balance_spare_change = get(member)

    if not allow_overdraft and balance < amount or balance == amount and spare_change and not balance_spare_change:
        raise InsufficientFundsError()

    balance -= amount
    if spare_change and not balance_spare_change:
        balance -= 1
    balance_spare_change ^= spare_change

    set(member, balance, balance_spare_change)


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
