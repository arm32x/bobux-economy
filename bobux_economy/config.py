from typing import Generic, Optional, TypeVar
import aiosqlite

from bobux_economy import utils

# SQLite types only
T = TypeVar("T", None, int, float, str, bytes)


class GuildOption(Generic[T]):
    name: str

    def __init__(self, name: str):
        self.name = name

    async def get_value(
        self, db_connection: aiosqlite.Connection, guild_id: int
    ) -> Optional[T]:
        async with db_connection.cursor() as db_cursor:
            await db_cursor.execute(
                f"SELECT {self.name} FROM guilds WHERE id = ?",
                (guild_id,),
            )

            row = await db_cursor.fetchone()
            if row is None:
                return None

            value = row[self.name]
            if value is None:
                return None

            return value

    async def set_value(
        self, db_connection: aiosqlite.Connection, guild_id: int, value: Optional[T]
    ):
        async with utils.db_transaction(db_connection) as db_cursor:
            await db_cursor.execute(
                f"""
                INSERT INTO
                    guilds (id, {self.name})
                VALUES
                    (?, ?)
                ON CONFLICT (id) DO
                UPDATE
                SET
                    {self.name} = excluded.{self.name}
                """,
                (guild_id, value),
            )


admin_role_id: GuildOption[int] = GuildOption("admin_role")
memes_channel_id: GuildOption[int] = GuildOption("memes_channel")
real_estate_category_id: GuildOption[int] = GuildOption("real_estate_category")
