import discord
import discord.ext.commands as commands

from .database import connection as db


class InsufficientFundsError(commands.CommandError):
    def __init__(self):
        super().__init__("Insufficient funds.")

class NegativeAmountError(commands.CommandError):
    def __init__(self):
        super().__init__("Amount must not be negative.")


def get(member: discord.Member) -> (int, bool):
    c = db.cursor()
    c.execute("""
        SELECT balance, spare_change FROM members WHERE id = ? AND guild_id = ?;
    """, (member.id, member.guild.id))
    return c.fetchone() or (0, False)

def set(member: discord.Member, amount: int, spare_change: bool):
    c = db.cursor()
    c.execute("""
        INSERT INTO members(id, guild_id, balance, spare_change) VALUES(?, ?, ?, ?)
            ON CONFLICT(id, guild_id) DO UPDATE SET balance = excluded.balance, spare_change = excluded.spare_change;
    """, (member.id, member.guild.id, amount, spare_change))

def add(member: discord.Member, amount: int, spare_change: bool):
    if amount < 0:
        raise NegativeAmountError()

    balance, balance_spare_change = get(member)

    balance += amount
    if spare_change and balance_spare_change:
        balance += 1
    balance_spare_change ^= spare_change

    set(member, balance, balance_spare_change)

def subtract(member: discord.Member, amount: int, spare_change: bool):
    if amount < 0:
        raise NegativeAmountError()

    balance, balance_spare_change = get(member)

    if balance < amount or balance == amount and spare_change and not balance_spare_change:
        raise InsufficientFundsError()

    balance -= amount
    if spare_change and not balance_spare_change:
        balance -= 1
    balance_spare_change ^= spare_change

    set(member, balance, balance_spare_change)


def from_float(amount: float) -> (int, bool):
    return int(amount), not amount.is_integer()
