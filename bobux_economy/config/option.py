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

    async def set(
        self,
        value: Optional[TSqlite],
    ):
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
