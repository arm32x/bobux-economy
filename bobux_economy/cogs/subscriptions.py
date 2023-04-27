import asyncio
from datetime import datetime, timezone
import logging
from typing import Dict

import disnake
from disnake.ext import commands

from bobux_economy import balance, subscriptions, transactions, utils
from bobux_economy.bobux import Account, Bobux
from bobux_economy.bot import BobuxEconomyBot
from bobux_economy.cogs.error_handling import ErrorHandling


class SubscriptionNotFound(commands.errors.CommandError):
    def __init__(self, subscription_role: disnake.Role):
        super().__init__(
            f"Subscription for role {subscription_role.mention} does not exist."
        )


class AlreadySubscribed(commands.errors.CommandError):
    def __init__(self, subscription_role: disnake.Role):
        super().__init__(f"You are already subscribed to {subscription_role.mention}.")


class NotSubscribed(commands.errors.CommandError):
    def __init__(self, subscription_role: disnake.Role):
        super().__init__(f"You are not subscribed to {subscription_role.mention}.")


class Subscriptions(commands.Cog):
    bot: BobuxEconomyBot

    def __init__(self, bot: BobuxEconomyBot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_ready(self):
        logging.info("Starting subscriptions background task...")
        asyncio.create_task(subscriptions.run(self.bot))

    @commands.slash_command(name="subscriptions")
    async def slash_subscriptions(self, _: disnake.GuildCommandInteraction):
        """Manage subscriptions"""

    @slash_subscriptions.sub_command(name="new")
    @utils.has_admin_role()
    async def slash_subscriptions_new(
        self,
        inter: disnake.GuildCommandInteraction,
        role: disnake.Role,
        price_per_week: float,
    ):
        """
        Create a new subscription in this server

        Parameters
        ----------
        role: The role to grant to subscribers
        price_per_week: The price of this subscription, charged weekly
        """

        price_per_week_bobux = Bobux.from_float(price_per_week)

        async with utils.db_transaction(self.bot.db_connection) as db_cursor:
            await db_cursor.execute(
                """
                INSERT INTO
                    available_subscriptions (role_id, guild_id, price, spare_change)
                VALUES
                    (?, ?, ?, ?)
                """,
                (
                    role.id,
                    inter.guild.id,
                    price_per_week_bobux.amount,
                    price_per_week_bobux.spare_change,
                ),
            )

        await inter.response.send_message(
            f"Created subscription for {role.mention} for {price_per_week_bobux} per week",
            allowed_mentions=disnake.AllowedMentions.none(),
        )

    @slash_subscriptions.sub_command(name="delete")
    @utils.has_admin_role()
    async def slash_subscriptions_delete(
        self, inter: disnake.GuildCommandInteraction, role: disnake.Role
    ):
        """
        Delete a subscription from this server. The role will not be
        revoked from current subscribers.

        Parameters
        ----------
        role: The role of the subscription to delete
        """

        async with utils.db_transaction(self.bot.db_connection) as db_cursor:
            await db_cursor.execute(
                """
                DELETE FROM available_subscriptions
                WHERE
                    role_id = ?
                """,
                (role.id,),
            )
            if db_cursor.rowcount == 0:
                raise SubscriptionNotFound(role)

            await db_cursor.execute(
                """
                DELETE FROM member_subscriptions
                WHERE
                    role_id = ?
                """,
                (role.id,),
            )

        await inter.response.send_message(
            f"Deleted subscription for role {role.mention}.",
            allowed_mentions=disnake.AllowedMentions.none(),
        )

    @slash_subscriptions.sub_command(name="list")
    async def slash_subscriptions_list(self, inter: disnake.GuildCommandInteraction):
        """List available subscriptions"""

        async with self.bot.db_connection.cursor() as db_cursor:
            await db_cursor.execute(
                """
                SELECT
                    role_id,
                    price,
                    spare_change
                FROM
                    available_subscriptions
                WHERE
                    guild_id = ?
                """,
                (inter.guild.id,),
            )
            available_subscriptions_rows = await db_cursor.fetchall()

            await db_cursor.execute(
                """
                SELECT
                    role_id,
                    subscribed_since
                FROM
                    member_subscriptions
                WHERE
                    member_id = ?
                """,
                (inter.author.id,),
            )
            member_subscriptions_rows = await db_cursor.fetchall()
            member_subscriptions_dict: Dict[int, datetime] = {
                row["role_id"]: row["subscribed_since"]
                for row in member_subscriptions_rows
            }

        message_lines = [f"Available subscriptions in ‘{inter.guild.name}’:"]
        for row in available_subscriptions_rows:
            role_id: int = row["role_id"]
            price_per_week = Bobux(int(row["price"]), bool(row["spare_change"]))

            line = f"<@&{role_id}>: {price_per_week} per week"
            if role_id in member_subscriptions_dict:
                # TODO: Use Discord's built-in support for displaying
                #       timestamps.
                subscribed_since = (
                    member_subscriptions_dict[role_id]
                    .replace(tzinfo=timezone.utc)
                    .astimezone(None)
                )
                line += f" (subscribed since {subscribed_since})"

            message_lines.append(line)

        await inter.response.send_message(
            "\n".join(message_lines),
            allowed_mentions=disnake.AllowedMentions.none(),
            ephemeral=True,
        )

    @commands.slash_command(name="subscribe")
    @commands.bot_has_guild_permissions(manage_roles=True)
    async def slash_subscribe(
        self, inter: disnake.GuildCommandInteraction, role: disnake.Role
    ):
        """
        Subscribe to a subscription

        Parameters
        ----------
        role: The role of the subscription to subscribe to
        """

        async with self.bot.db_connection.cursor() as db_cursor:
            await db_cursor.execute(
                """
                SELECT
                    price,
                    spare_change
                FROM
                    available_subscriptions
                WHERE
                    role_id = ?
                """,
                (role.id,),
            )
            row = await db_cursor.fetchone()
            if row is None:
                raise SubscriptionNotFound(role)
            price_per_week = Bobux(int(row["price"]), bool(row["spare_change"]))

            await db_cursor.execute(
                """
                SELECT
                    COUNT(*)
                FROM
                    member_subscriptions
                WHERE
                    member_id = ?
                    AND role_id = ?
                """,
                (inter.author.id, role.id),
            )
            # Exactly one row will always be returned since we are using
            # an aggregate function.
            row = await db_cursor.fetchone()
            assert row is not None
            already_subscribed = bool(row[0])

        if already_subscribed:
            raise AlreadySubscribed(role)

        # TODO: Make this use Disnake views.
        action_row = disnake.ui.ActionRow(
            disnake.ui.Button(
                style=disnake.ButtonStyle.green,
                label="Subscribe",
                custom_id="subscribe",
            ),
            disnake.ui.Button(
                style=disnake.ButtonStyle.gray, label="Cancel", custom_id="cancel"
            ),
        )
        await inter.response.send_message(
            (
                f"Subscribe to {role.mention} for {price_per_week} per week? "
                f"You will be charged for the first week immediately."
            ),
            allowed_mentions=disnake.AllowedMentions.none(),
            components=[action_row],
            ephemeral=True,
        )

        button_inter = await utils.wait_for_component(self.bot, action_row)

        if button_inter.data.custom_id != "subscribe":
            await button_inter.response.edit_message("Cancelled.", components=[])
            return

        # The interaction passed to this command is no longer valid, so
        # the global error handlers will not work. We have to handle the
        # error here.
        try:
            async with utils.db_transaction(self.bot.db_connection) as db_cursor:
                await transactions.create_transaction(
                    self.bot.db_connection,
                    source=Account.from_member(inter.author),
                    destination=None,
                    amount=price_per_week,
                )
                await subscriptions.subscribe(
                    self.bot.db_connection, inter.author, role
                )
                await button_inter.response.edit_message(
                    f"Subscribed to {role.mention}.", components=[]
                )
        except Exception as ex:
            if isinstance(ex, disnake.Forbidden):
                # We know the bot has the Manage Roles permission
                # thanks to the check decorator, so this must have been
                # caused by the subscription role being above the bot's
                # highest role.
                await button_inter.response.edit_message(
                    f"**Error:** Role {role.mention} is above the bot’s highest role.",
                    components=[],
                )
            else:
                await ErrorHandling.edit_into_error_feedback(inter, ex)

    @commands.slash_command(name="unsubscribe")
    @commands.bot_has_guild_permissions(manage_roles=True)
    async def slash_unsubscribe(
        self, inter: disnake.GuildCommandInteraction, role: disnake.Role
    ):
        """
        Unsubscribe from a subscription

        Parameters
        ----------
        role: The role of the subscription to unsubscribe from
        """

        async with self.bot.db_connection.cursor() as db_cursor:
            await db_cursor.execute(
                """
                SELECT
                    COUNT(*)
                FROM
                    member_subscriptions
                WHERE
                    member_id = ?
                    AND role_id = ?
                """,
                (inter.author.id, role.id),
            )
            # Exactly one row will always be returned since we are using
            # an aggregate function.
            row = await db_cursor.fetchone()
            assert row is not None
            already_subscribed = bool(row[0])

        if not already_subscribed:
            raise NotSubscribed(role)

        # TODO: Make this use Disnake views.
        action_row = disnake.ui.ActionRow(
            disnake.ui.Button(
                style=disnake.ButtonStyle.red,
                label="Unsubscribe",
                custom_id="unsubscribe",
            ),
            disnake.ui.Button(
                style=disnake.ButtonStyle.gray, label="Cancel", custom_id="cancel"
            ),
        )
        await inter.response.send_message(
            f"Unsubscribe from {role.mention}?",
            allowed_mentions=disnake.AllowedMentions.none(),
            components=[action_row],
            ephemeral=True,
        )

        button_inter = await utils.wait_for_component(self.bot, action_row)

        if button_inter.data.custom_id != "unsubscribe":
            await button_inter.response.edit_message("Cancelled.", components=[])
            return

        # The interaction passed to this command is no longer valid, so
        # the global error handlers will not work. We have to handle the
        # error here.
        try:
            await subscriptions.unsubscribe(self.bot.db_connection, inter.author, role)
            await button_inter.response.edit_message(
                f"Unsubscribed from {role.mention}.", components=[]
            )
        except Exception as ex:
            if isinstance(ex, disnake.Forbidden):
                # We know the bot has the Manage Roles permission
                # thanks to the check decorator, so this must have been
                # caused by the subscription role being above the bot's
                # highest role.
                await button_inter.response.edit_message(
                    f"**Error:** Role {role.mention} is above the bot’s highest role.",
                    components=[],
                )
            else:
                await ErrorHandling.edit_into_error_feedback(inter, ex)


def setup(bot: BobuxEconomyBot):
    bot.add_cog(Subscriptions(bot))
