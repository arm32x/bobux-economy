from typing import Any

import aiosqlite
import disnake
from typing_extensions import LiteralString

from bobux_economy.config.option import BasicOption, SetOption


class GuildConfig:
    admin_role_id: BasicOption[int]
    real_estate_category_id: BasicOption[int]
    vote_channel_ids: SetOption[int]

    def __init__(
        self, db_connection: aiosqlite.Connection, guild: disnake.abc.Snowflake
    ):
        def make_option(name: LiteralString) -> BasicOption[Any]:
            return BasicOption(db_connection, "guild_config", guild, name)

        self.admin_role_id = make_option("admin_role_id")
        self.real_estate_category_id = make_option("real_estate_category_id")
        self.vote_channel_ids = SetOption(
            db_connection, "guild_config_vote_channel_ids", guild
        )
