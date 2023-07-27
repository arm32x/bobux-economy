from typing import Generic, Optional, TypeVar
from typing_extensions import LiteralString

import aiosqlite
import disnake

from bobux_economy import utils


# Any type that is compatible with SQLite
TSqlite = TypeVar("TSqlite", None, int, float, str, bytes)


class BasicOption(Generic[TSqlite]):
    """
    An option of an SQLite-compatible type that can be None.
    """

    db_connection: aiosqlite.Connection
    table_name: LiteralString
    snowflake: disnake.abc.Snowflake
    name: LiteralString

    def __init__(
        self,
        db_connection: aiosqlite.Connection,
        table_name: LiteralString,
        snowflake: disnake.abc.Snowflake,
        name: LiteralString,
    ):
        self.db_connection = db_connection
        self.table_name = table_name
        self.snowflake = snowflake
        self.name = name

    async def get(self) -> Optional[TSqlite]:
        async with self.db_connection.cursor() as db_cursor:
            await db_cursor.execute(
                f"SELECT {self.name} FROM {self.table_name} WHERE snowflake = ?",
                (self.snowflake.id,),
            )

            row = await db_cursor.fetchone()
            if row is None:
                return None

            value = row[self.name]
            if value is None:
                return None

            return value

    async def set(self, value: Optional[TSqlite]):
        async with utils.db_transaction(self.db_connection) as db_cursor:
            await db_cursor.execute(
                f"""
                INSERT INTO
                    {self.table_name} (snowflake, {self.name})
                VALUES
                    (?, ?)
                ON CONFLICT (snowflake) DO
                UPDATE
                SET
                    {self.name} = excluded.{self.name}
                """,
                (self.snowflake.id, value),
            )


class SetOption(Generic[TSqlite]):
    """
    An option of a set of an SQLite-compatible type represented as an
    SQL table.
    """

    db_connection: aiosqlite.Connection
    table_name: LiteralString
    snowflake: disnake.abc.Snowflake

    def __init__(
        self,
        db_connection: aiosqlite.Connection,
        table_name: LiteralString,
        snowflake: disnake.abc.Snowflake,
    ):
        self.db_connection = db_connection
        self.table_name = table_name
        self.snowflake = snowflake

    async def get(self) -> set[TSqlite]:
        async with self.db_connection.cursor() as db_cursor:
            await db_cursor.execute(
                f"SELECT value FROM {self.table_name} WHERE snowflake = ?",
                (self.snowflake.id,),
            )
            return {row["value"] for row in await db_cursor.fetchall()}

    async def contains(self, value: TSqlite) -> bool:
        async with self.db_connection.cursor() as db_cursor:
            # This SQL formatting is questionable...
            await db_cursor.execute(
                f"""
                SELECT
                    EXISTS (
                        SELECT
                            1
                        FROM
                            {self.table_name}
                        WHERE
                            snowflake = ?
                            AND value = ?
                    )
                """,
                (self.snowflake.id, value),
            )
            row = await db_cursor.fetchone()
            assert row is not None
            
            return bool(row[0])

    async def add(self, value: TSqlite):
        async with utils.db_transaction(self.db_connection) as db_cursor:
            await db_cursor.execute(
                f"""
                INSERT INTO
                    {self.table_name} (snowflake, value)
                VALUES
                    (?, ?)
                """,
                (self.snowflake.id, value),
            )

    async def remove(self, value: TSqlite) -> bool:
        async with utils.db_transaction(self.db_connection) as db_cursor:
            await db_cursor.execute(
                f"""
                DELETE FROM {self.table_name}
                WHERE
                    snowflake = ?
                    AND value = ?
                """,
                (self.snowflake.id, value),
            )
            return bool(db_cursor.rowcount)

    async def clear(self) -> int:
        async with utils.db_transaction(self.db_connection) as db_cursor:
            await db_cursor.execute(
                f"""
                DELETE FROM {self.table_name}
                WHERE
                    snowflake = ?
                """,
                (self.snowflake.id,),
            )
            return db_cursor.rowcount
