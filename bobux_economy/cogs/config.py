"""
A cog containing commands to change the bot's configuration in a guild.
"""

from contextlib import closing
from typing import Optional
import disnake
from disnake.ext import commands

from bobux_economy.bot import BobuxEconomyBot


class Config(commands.Cog):
    bot: BobuxEconomyBot

    def __init__(self, bot: BobuxEconomyBot):
        self.bot = bot

    @commands.slash_command(name="config")
    @commands.has_guild_permissions(manage_guild=True)
    async def slash_config(self, _: disnake.GuildCommandInteraction):
        """Change the settings of the bot"""

    @slash_config.sub_command(name="admin_role")
    async def slash_config_admin_role(
        self,
        inter: disnake.GuildCommandInteraction,
        role: Optional[disnake.Role] = None,
    ):
        """
        Change which role is required to modify balances

        Parameters
        ----------
        role: The role to set, or blank to remove
        """

        role_id = role.id if role is not None else None
        role_mention = role.mention if role is not None else "None"

        with closing(self.bot.db_connection.cursor()) as db_cursor:
            db_cursor.execute(
                """
                    INSERT INTO guilds(id, admin_role) VALUES(?, ?)
                        ON CONFLICT(id) DO UPDATE SET admin_role = excluded.admin_role
                """,
                (inter.guild.id, role_id),
            )
            self.bot.db_connection.commit()

        await inter.response.send_message(f"Set admin role to {role_mention}")

    @slash_config.sub_command(name="memes_channel")
    async def slash_config_memes_channel(
        self,
        inter: disnake.GuildCommandInteraction,
        channel: Optional[disnake.TextChannel] = None,
    ):
        """
        Set the channel where upvote reactions are enabled

        Parameters
        ----------
        channel: The channel to set, or blank to remove
        """

        channel_id = channel.id if channel is not None else None
        channel_mention = channel.mention if channel is not None else "None"

        with closing(self.bot.db_connection.cursor()) as db_cursor:
            db_cursor.execute(
                """
                    INSERT INTO guilds(id, memes_channel) VALUES(?, ?)
                        ON CONFLICT(id) DO UPDATE SET memes_channel = excluded.memes_channel
                """,
                (inter.guild.id, channel_id),
            )
            self.bot.db_connection.commit()

        await inter.response.send_message(f"Set memes channel to {channel_mention}")

    @slash_config.sub_command(name="real_estate_category")
    async def slash_config_real_estate_category(
        self,
        inter: disnake.GuildCommandInteraction,
        category: Optional[disnake.CategoryChannel] = None,
    ):
        """
        Set the category where purchased real estate channels appear

        Parameters
        ----------
        category: The category to set, or blank to remove
        """

        category_id = category.id if category is not None else None
        category_mention = f"‘{category.name}’" if category is not None else "None"

        with closing(self.bot.db_connection.cursor()) as db_cursor:
            db_cursor.execute(
                """
                    INSERT INTO guilds(id, real_estate_category) VALUES(?, ?)
                        ON CONFLICT(id) DO UPDATE SET real_estate_category = excluded.real_estate_category
                """,
                (inter.guild.id, category_id),
            )
            self.bot.db_connection.commit()

        await inter.response.send_message(
            f"Set real estate category to {category_mention}"
        )


def setup(bot: BobuxEconomyBot):
    bot.add_cog(Config(bot))
