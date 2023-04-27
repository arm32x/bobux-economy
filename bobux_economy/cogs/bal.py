from typing import cast

import disnake
from disnake.ext import commands

from bobux_economy import balance, utils
from bobux_economy.bobux import Account, Bobux
from bobux_economy.bot import BobuxEconomyBot
from bobux_economy.transactions import create_transaction


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

        await self.check_user_and_respond(inter, inter.author)

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

        await self.check_user_and_respond(inter, target)

    @commands.user_command(name="Check Balance", dm_permission=False)
    @commands.guild_only()
    async def user_check_balance(self, inter: disnake.UserCommandInteraction):
        await self.check_user_and_respond(inter, cast(disnake.Member, inter.target))

    async def check_user_and_respond(
        self,
        inter: disnake.Interaction,
        user: disnake.Member,
    ):
        account = Account.from_member(user)
        balance = await account.get_balance(self.bot.db_connection)

        await inter.response.send_message(
            f"{user.mention}: {balance}",
            allowed_mentions=disnake.AllowedMentions.none(),
            ephemeral=True,
        )

    @slash_bal_check.sub_command(name="everyone")
    async def slash_bal_check_everyone(self, inter: disnake.GuildCommandInteraction):
        """Check the balance of everyone in this server"""

        # TODO: Move this to a function in the new transactions API.
        async with self.bot.db_connection.cursor() as db_cursor:
            await db_cursor.execute(
                """
                    SELECT id, balance, spare_change FROM members WHERE guild_id = ?
                        ORDER BY balance DESC, spare_change DESC
                """,
                (inter.guild.id,),
            )
            rows = await db_cursor.fetchall()

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

        async with utils.db_transaction(self.bot.db_connection):
            account = Account.from_member(target)

            old_balance = await account.get_balance(self.bot.db_connection)
            new_balance = Bobux.from_float(amount)
            transaction_amount = new_balance - old_balance

            if transaction_amount < Bobux.ZERO:
                transaction_amount = -transaction_amount
                source, destination = account, None
            else:
                source, destination = None, account

            await create_transaction(self.bot.db_connection, source, destination, transaction_amount)

        await inter.response.send_message(
            f"Set {target.mention}’s balance to {new_balance}",
            allowed_mentions=disnake.AllowedMentions(
                users=[target], roles=False, everyone=False, replied_user=False
            ),
        )

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

        account = Account.from_member(target)
        transaction_amount = Bobux.from_float(amount)

        await create_transaction(
            self.bot.db_connection, None, account, transaction_amount
        )

        await inter.response.send_message(
            f"Added {transaction_amount} to {target.mention}’s balance",
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

        account = Account.from_member(target)
        transaction_amount = Bobux.from_float(amount)

        await create_transaction(
            self.bot.db_connection, account, None, transaction_amount
        )

        await inter.response.send_message(
            f"Subtracted {transaction_amount} from {target.mention}’s balance",
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

        source = Account.from_member(inter.author)
        destination = Account.from_member(recipient)
        transaction_amount = Bobux.from_float(amount)

        await create_transaction(
            self.bot.db_connection, source, destination, transaction_amount
        )

        await inter.response.send_message(
            f"Transferred {transaction_amount} to {recipient.mention}",
            allowed_mentions=disnake.AllowedMentions(
                users=[recipient], roles=False, everyone=False, replied_user=False
            ),
        )


def setup(bot: BobuxEconomyBot):
    bot.add_cog(Bal(bot))
