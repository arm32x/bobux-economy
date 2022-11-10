from contextlib import closing
import sqlite3
from typing import cast

import disnake
from disnake.ext import commands

from bobux_economy import balance
from bobux_economy.bot import BobuxEconomyBot


class Bal(commands.Cog):
    bot: BobuxEconomyBot

    def __init__(self, bot: BobuxEconomyBot):
        self.bot = bot

    @commands.slash_command(name="bal")
    async def slash_bal(self, _: disnake.GuildCommandInteraction):
        """Manage account balances"""

    @slash_bal.sub_command_group(name="check")
    async def slash_bal_check(self, _: disnake.GuildCommandInteraction):
        """Check the balance of yourself or someone else"""

    @slash_bal_check.sub_command(name="self")
    async def slash_bal_check_self(self, inter: disnake.GuildCommandInteraction):
        """Check your balance in this server"""

        await Bal._check_user_and_respond(inter, inter.author)

    @slash_bal_check.sub_command(name="user")
    async def slash_bal_check_user(
        self, inter: disnake.GuildCommandInteraction, target: disnake.Member
    ):
        """
        Check someone's balance in this server

        Parameters
        ----------
        target: The user to check the balance of
        """

        await Bal._check_user_and_respond(inter, target)

    @commands.user_command(name="Check Balance", dm_permission=False)
    @commands.guild_only()
    async def user_check_balance(self, inter: disnake.UserCommandInteraction):
        await Bal._check_user_and_respond(inter, cast(disnake.Member, inter.user))

    @staticmethod
    async def _check_user_and_respond(
        inter: disnake.Interaction,
        user: disnake.Member,
    ):
        amount, spare_change = balance.get(user)
        balance_str = balance.to_string(amount, spare_change)

        await inter.response.send_message(
            f"{user.mention}: {balance_str}",
            allowed_mentions=disnake.AllowedMentions.none(),
            ephemeral=True,
        )

    @slash_bal_check.sub_command(name="everyone")
    async def slash_bal_check_everyone(self, inter: disnake.GuildCommandInteraction):
        """Check the balance of everyone in this server"""

        with closing(self.bot.db_connection.cursor()) as db_cursor:
            db_cursor.execute(
                """
                    SELECT id, balance, spare_change FROM members WHERE guild_id = ?
                        ORDER BY balance DESC, spare_change DESC
                """,
                (inter.guild.id,),
            )
            rows: list[sqlite3.Row] = db_cursor.fetchall()

        message_parts = []
        for member_id, amount, spare_change in rows:
            message_parts.append(
                f"<@{member_id}>: {balance.to_string(amount, spare_change)}"
            )

        if len(message_parts) > 0:
            await inter.response.send_message(
                "\n".join(message_parts),
                allowed_mentions=disnake.AllowedMentions.none(),
                ephemeral=True,
            )
        else:
            await inter.response.send_message("No results", ephemeral=True)


def setup(bot: BobuxEconomyBot):
    bot.add_cog(Bal(bot))
