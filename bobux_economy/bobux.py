from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar, Type, TypeVar
import aiosqlite

import disnake

A = TypeVar("A", bound="Account")
B = TypeVar("B", bound="Bobux")


@dataclass(frozen=True, order=True)
class Bobux:
    amount: int
    spare_change: bool

    ZERO: ClassVar[Bobux]

    @classmethod
    def from_float(cls: Type[B], amount: float) -> B:
        """
        Create a bobux value from a floating-point number.

        The `amount` of the result will be the input number truncated to
        the nearest integer. `spare_change` will be set if the input was
        not an exact integer.

        Parameters
        ----------
        amount: The floating-point number to convert.

        Returns
        -------
        A new `Bobux` object containing the values described above.
        """

        return cls(int(amount), not amount.is_integer())

    def to_float(self) -> float:
        return self.amount + (0.5 if self.spare_change else 0)

    def __add__(self, other: Bobux) -> Bobux:
        amount = self.amount + other.amount
        if self.spare_change and other.spare_change:
            amount += 1
        spare_change = self.spare_change ^ other.spare_change
        return Bobux(amount, spare_change)

    def __sub__(self, other: Bobux) -> Bobux:
        amount = self.amount - other.amount
        if not self.spare_change and other.spare_change:
            amount -= 1
        spare_change = self.spare_change ^ other.spare_change
        return Bobux(amount, spare_change)

    def __neg__(self) -> Bobux:
        amount = -self.amount - int(self.spare_change)
        return Bobux(amount, self.spare_change)

    def __str__(self) -> str:
        if self.spare_change:
            return f"{self.amount} bobux and some spare change"
        else:
            return f"{self.amount} bobux"


Bobux.ZERO = Bobux(0, False)


@dataclass
class Account:
    discord_user_id: int
    discord_guild_id: int

    @classmethod
    def from_member(cls: Type[A], member: disnake.Member) -> A:
        return cls(member.id, member.guild.id)

    async def get_balance(self, db_connection: aiosqlite.Connection) -> Bobux:
        """
        Get the current balance of this account.

        Parameters
        ----------
        db_connection: A connection to the SQLite database in use.

        Returns
        -------
        The current balance of this account.
        """

        async with db_connection.cursor() as db_cursor:
            await db_cursor.execute(
                """
                SELECT
                    balance,
                    spare_change
                FROM
                    members
                WHERE
                    id = ?
                    AND guild_id = ?
                """,
                (self.discord_user_id, self.discord_guild_id),
            )
            row = await db_cursor.fetchone()

            if row is not None:
                return Bobux(row["balance"], row["spare_change"])
            else:
                return Bobux.ZERO
