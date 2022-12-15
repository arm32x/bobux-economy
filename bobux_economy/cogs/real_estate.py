from datetime import datetime
from typing import Union, cast
import disnake
from disnake.ext import commands

from bobux_economy import balance, real_estate
from bobux_economy.bot import BobuxEconomyBot

TEXT_CHANNEL_PRICE_STR = balance.to_string(
    *real_estate.CHANNEL_PRICES[disnake.ChannelType.text]
)
VOICE_CHANNEL_PRICE_STR = balance.to_string(
    *real_estate.CHANNEL_PRICES[disnake.ChannelType.voice]
)


class RealEstate(commands.Cog):
    bot: BobuxEconomyBot

    def __init__(self, bot: BobuxEconomyBot):
        self.bot = bot

    @commands.slash_command(name="real_estate")
    async def slash_real_estate(self, _: disnake.GuildCommandInteraction):
        """Manage your real estate"""

    @slash_real_estate.sub_command_group(name="buy")
    async def slash_real_estate_buy(self, _: disnake.GuildCommandInteraction):
        """Buy a real estate channel"""

    @slash_real_estate_buy.sub_command(
        name="text",
        # The description must be provided here since there is no way to
        # interpolate the correct value into the docstring.
        description=f"Buy a text channel for {TEXT_CHANNEL_PRICE_STR}",
    )
    async def slash_real_estate_buy_text(
        self, inter: disnake.GuildCommandInteraction, name: str
    ):
        """
        Buy a text channel

        Parameters
        ----------
        name: The name of the purchased channel
        """

        channel = await real_estate.buy(self.bot.db_connection, disnake.ChannelType.text, inter.author, name)
        await inter.response.send_message(
            f"Bought {channel.mention} for {TEXT_CHANNEL_PRICE_STR}",
            allowed_mentions=disnake.AllowedMentions.none(),
        )

    @slash_real_estate_buy.sub_command(
        name="voice",
        # The description must be provided here since there is no way to
        # interpolate the correct value into the docstring.
        description=f"Buy a voice channel for {VOICE_CHANNEL_PRICE_STR}",
    )
    async def slash_real_estate_buy_voice(
        self, inter: disnake.GuildCommandInteraction, name: str
    ):
        """
        Buy a voice channel

        Parameters
        ----------
        name: The name of the purchased channel
        """

        channel = await real_estate.buy(self.bot.db_connection, disnake.ChannelType.voice, inter.author, name)
        await inter.response.send_message(
            f"Bought {channel.mention} for {VOICE_CHANNEL_PRICE_STR}",
            allowed_mentions=disnake.AllowedMentions.none(),
        )

    @slash_real_estate.sub_command(name="sell")
    async def slash_real_estate_sell(
        self,
        inter: disnake.GuildCommandInteraction,
        channel: Union[disnake.TextChannel, disnake.VoiceChannel],
    ):
        """
        Sell one of your channels for half of its purchase price

        Parameters
        ----------
        channel: The channel to sell
        """

        price = await real_estate.sell(self.bot.db_connection, channel, inter.author)
        await inter.response.send_message(
            f"Sold ‘{channel.name}’ for {balance.to_string(*price)}",
            allowed_mentions=disnake.AllowedMentions.none(),
        )

    @slash_real_estate.sub_command_group(name="check")
    async def slash_real_estate_check(self, _: disnake.GuildCommandInteraction):
        """Check the real estate holdings of yourself or someone else"""

    @slash_real_estate_check.sub_command(name="self")
    async def slash_real_estate_check_self(
        self, inter: disnake.GuildCommandInteraction
    ):
        """Check your real estate holdings"""

        await self._check_user_and_respond(inter, inter.author)

    @slash_real_estate_check.sub_command(name="user")
    async def slash_real_estate_check_user(
        self,
        inter: disnake.GuildCommandInteraction,
        target: disnake.Member,
    ):
        """
        Check someone’s real estate holdings

        Parameters
        ----------
        target: The user to check the real estate holdings of
        """

        await self._check_user_and_respond(inter, target)

    @commands.user_command(name="Check Real Estate", dm_permission=False)
    @commands.guild_only()
    async def user_check_real_estate(self, inter: disnake.UserCommandInteraction):
        await self._check_user_and_respond(inter, cast(disnake.Member, inter.target))

    async def _check_user_and_respond(
        self, inter: disnake.Interaction, user: disnake.Member
    ):
        async with self.bot.db_connection.cursor() as db_cursor:
            await db_cursor.execute(
                "SELECT id, purchase_time FROM purchased_channels WHERE owner_id = ?",
                (user.id,),
            )
            rows = await db_cursor.fetchall()

            # TODO: Improve this output with Discord's timestamp formatting.
            message_parts = [f"{user.mention}:"]
            for row in rows:
                channel_id: int = row["id"]
                purchase_time: datetime = row["purchase_time"]
                message_parts.append(f"<#{channel_id}>: Purchased {purchase_time}.")

            await inter.response.send_message(
                "\n".join(message_parts),
                allowed_mentions=disnake.AllowedMentions.none(),
                ephemeral=True,
            )

    @slash_real_estate_check.sub_command(name="everyone")
    async def slash_real_estate_check_everyone(
        self, inter: disnake.GuildCommandInteraction
    ):
        """Check the real estate holdings of everyone in this server"""

        async with self.bot.db_connection.cursor() as db_cursor:
            await db_cursor.execute(
                """
                    SELECT id, owner_id, purchase_time FROM purchased_channels
                        WHERE guild_id = ? ORDER BY owner_id
                """,
                (inter.guild.id,),
            )
            rows = await db_cursor.fetchall()

            message_parts = []
            current_owner_id = None
            for row in rows:
                channel_id: int = row["id"]
                owner_id: int = row["owner_id"]
                purchase_time: datetime = row["purchase_time"]
                if owner_id != current_owner_id:
                    message_parts.append(f"<@{owner_id}>:")
                    current_owner_id = owner_id
                message_parts.append(f"<#{channel_id}>: Purchased {purchase_time}.")

            message_content = (
                "\n".join(message_parts) if len(message_parts) > 0 else "No results"
            )
            await inter.response.send_message(
                message_content,
                allowed_mentions=disnake.AllowedMentions.none(),
                ephemeral=True,
            )


def setup(bot: BobuxEconomyBot):
    bot.add_cog(RealEstate(bot))
