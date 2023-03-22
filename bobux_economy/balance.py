import dataclasses
import math
from typing import Tuple
from typing_extensions import deprecated

import aiosqlite
import disnake
from bobux_economy import utils
from bobux_economy.bobux import Account, Bobux
from bobux_economy.transactions import create_transaction


@deprecated("Use Account.from_member(...).get_balance(...) instead.")
async def get(
    db_connection: aiosqlite.Connection, member: disnake.Member
) -> Tuple[int, bool]:
    balance = await Account.from_member(member).get_balance(db_connection)
    return dataclasses.astuple(balance)


@deprecated("Use transactions.create_transaction(...) instead.")
async def set(
    db_connection: aiosqlite.Connection,
    member: disnake.Member,
    amount: int,
    spare_change: bool,
):
    async with utils.db_transaction(db_connection):
        account = Account.from_member(member)

        old_balance = await account.get_balance(db_connection)
        new_balance = Bobux(amount, spare_change)
        transaction_amount = new_balance - old_balance

        if transaction_amount < Bobux.ZERO:
            transaction_amount = -transaction_amount
            source, destination = account, None
        else:
            source, destination = None, account

        await create_transaction(db_connection, source, destination, transaction_amount)


@deprecated("Use transactions.create_transaction(...) instead.")
async def add(
    db_connection: aiosqlite.Connection,
    member: disnake.Member,
    amount: int,
    spare_change: bool,
):
    account = Account.from_member(member)
    transaction_amount = Bobux(amount, spare_change)
    await create_transaction(db_connection, None, account, transaction_amount)


@deprecated("Use transactions.create_transaction(...) instead.")
async def subtract(
    db_connection: aiosqlite.Connection,
    member: disnake.Member,
    amount: int,
    spare_change: bool,
    allow_overdraft=False,
):
    account = Account.from_member(member)
    transaction_amount = Bobux(amount, spare_change)
    await create_transaction(db_connection, account, None, transaction_amount, allow_overdraft)


@deprecated("Use Bobux.from_float(...) instead.")
def from_float(amount: float) -> Tuple[int, bool]:
    return int(amount), not amount.is_integer()


@deprecated("No replacement.")
def from_float_floor(amount: float) -> Tuple[int, bool]:
    rounded = math.floor(amount * 2) / 2
    return from_float(rounded)


@deprecated("No replacement.")
def from_float_ceil(amount: float) -> Tuple[int, bool]:
    rounded = math.ceil(amount * 2) / 2
    return from_float(rounded)


@deprecated("No replacement.")
def from_float_round(amount: float) -> Tuple[int, bool]:
    rounded = round(amount * 2) / 2
    return from_float(rounded)


@deprecated("Use Bobux(...).to_float() instead.")
def to_float(amount: int, spare_change: bool) -> float:
    return amount + (0.5 if spare_change else 0)


@deprecated("Use str(Bobux(...)) instead.")
def to_string(amount: int, spare_change: bool) -> str:
    if spare_change:
        return f"{amount} bobux and some spare change"
    else:
        return f"{amount} bobux"
