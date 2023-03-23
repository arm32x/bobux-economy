import logging
from typing import Optional

import aiosqlite
from bobux_economy import utils

from bobux_economy.bobux import Account, Bobux


logger = logging.getLogger(__name__)


class InsufficientFunds(utils.UserFacingError):
    amount_short: Bobux

    def __init__(self, amount_short: Bobux):
        super().__init__(f"Insufficient funds (need an additional {amount_short}).")
        self.amount_short = amount_short


class NegativeAmount(utils.UserFacingError):
    def __init__(self):
        super().__init__("Negative transaction amounts are not allowed.")



async def _set_balance_raw(
    db_connection: aiosqlite.Connection, account: Account, balance: Bobux
):
    """
    Set the current balance of an account directly.

    This function does not commit the current database transaction,
    which allows it to be used as a building block for larger
    operations.

    Intended only for use within the `transactions` module.

    Parameters
    ----------
    db_connection: A connection to the SQLite database in use.
    account:       The account to update the balance of.
    balance:       The new balance of the account.
    """

    async with db_connection.cursor() as db_cursor:
        await db_cursor.execute(
            """
            INSERT INTO
                members (id, guild_id, balance, spare_change)
            VALUES
                (?, ?, ?, ?)
            ON CONFLICT (id, guild_id) DO
            UPDATE
            SET
                balance = excluded.balance,
                spare_change = excluded.spare_change
            """,
            (
                account.discord_user_id,
                account.discord_guild_id,
                balance.amount,
                balance.spare_change,
            ),
        )


async def create_transaction(
    db_connection: aiosqlite.Connection,
    source: Optional[Account],
    destination: Optional[Account],
    amount: Bobux,
    allow_overdraft: bool = False,
):
    """
    Create a transaction between two accounts.

    Parameters
    ----------
    db_connection:   A connection to the SQLite database in use.
    source:          The account that bobux will be withdrawn from.
    destination:     The account that bobux will be deposited to.
    amount:          The amount of bobux to transfer.
    allow_overdraft: Whether to allow the balance of the source account
                     to go below zero.
    """

    if amount < Bobux.ZERO:
        raise NegativeAmount()

    async with utils.db_transaction(db_connection):
        if source is not None:
            source_balance = await source.get_balance(db_connection)
            source_balance -= amount
            if source_balance < Bobux.ZERO and not allow_overdraft:
                raise InsufficientFunds(-source_balance)
            await _set_balance_raw(db_connection, source, source_balance)

        if destination is not None:
            destination_balance = await destination.get_balance(db_connection)
            destination_balance += amount
            await _set_balance_raw(db_connection, destination, destination_balance)

    logger.info(f"Transaction: {amount} from {source} to {destination}")
