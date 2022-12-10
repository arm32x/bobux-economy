from contextlib import closing
import sqlite3
from typing import cast

import disnake
from disnake.ext import commands

from bobux_economy import balance, utils
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
        await Bal._check_user_and_respond(inter, cast(disnake.Member, inter.target))

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

    @slash_bal.sub_command(name="set")
    @utils.has_admin_role()
    async def slash_bal_set(
        self,
        inter: disnake.GuildCommandInteraction,
        target: disnake.Member,
        amount: float,
    ):
        """
        Set someone’s balance

        Parameters
        ----------
        target: The user to set the balance of
        amount: The new balance of the target
        """

        amount, spare_change = balance.from_float(amount)
        balance.set(target, amount, spare_change)

    @slash_bal.sub_command(name="add")
    @utils.has_admin_role()
    async def slash_bal_add(
        self,
        inter: disnake.GuildCommandInteraction,
        target: disnake.Member,
        amount: float,
    ):
        """
        Add bobux to someone’s balance

        Parameters
        ----------
        target: The user whose balance will be added to
        amount: The amount to add to the target’s balance
        """

        amount, spare_change = balance.from_float(float(amount))
        balance.add(target, amount, spare_change)

        bobux_str = balance.to_string(amount, spare_change)
        await inter.response.send_message(
            f"Added {bobux_str} to {target.mention}’s balance",
            allowed_mentions=disnake.AllowedMentions(
                users=[target], roles=False, everyone=False, replied_user=False
            ),
        )

    @slash_bal.sub_command(name="subtract")
    @utils.has_admin_role()
    async def slash_bal_subtract(
        self,
        inter: disnake.GuildCommandInteraction,
        target: disnake.Member,
        amount: float,
    ):
        """
        Subtract bobux from someone’s balance

        Parameters
        ----------
        target: The user whose balance will be subtracted from
        amount: The amount to subtract from the target’s balance
        """

        amount, spare_change = balance.from_float(float(amount))
        balance.subtract(target, amount, spare_change, allow_overdraft=True)

        bobux_str = balance.to_string(amount, spare_change)
        await inter.response.send_message(
            f"Subtracted {bobux_str} from {target.mention}’s balance",
            allowed_mentions=disnake.AllowedMentions(
                users=[target], roles=False, everyone=False, replied_user=False
            ),
        )

    @commands.slash_command(name="pay")
    async def slash_pay(
        self,
        inter: disnake.GuildCommandInteraction,
        recipient: disnake.Member,
        amount: float,
    ):
        """
        Transfer bobux to someone

        Parameters
        ----------
        recipient: The user to transfer bobux to
        amount: The amount to transfer to the recipient
        """

        # TODO: Figure out a nicer way to handle transactions.
        try:
            amount, spare_change = balance.from_float(amount)
            balance.subtract(inter.author, amount, spare_change)
            balance.add(recipient, amount, spare_change)
        except sqlite3.Error:
            self.bot.db_connection.rollback()
            raise
        self.bot.db_connection.commit()

        bobux_str = balance.to_string(amount, spare_change)
        await inter.response.send_message(
            f"Transferred {bobux_str} to {recipient.mention}",
            allowed_mentions=disnake.AllowedMentions(
                users=[recipient], roles=False, everyone=False, replied_user=False
            ),
        )


def setup(bot: BobuxEconomyBot):
    bot.add_cog(Bal(bot))
