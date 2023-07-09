"""
A cog containing commands to change the bot's configuration in a guild.
"""

import disnake
from disnake.ext import commands

from bobux_economy.bot import BobuxEconomyBot


class GuildConfig(commands.Cog):
    bot: BobuxEconomyBot

    def __init__(self, bot: BobuxEconomyBot):
        self.bot = bot

    @commands.slash_command(name="config")
    async def slash_config(self, _: disnake.GuildCommandInteraction):
        pass

    @slash_config.sub_command_group(name="admin_role")
    async def slash_config_admin_role(self, _: disnake.GuildCommandInteraction):
        pass

    @slash_config_admin_role.sub_command(name="get")
    async def slash_config_admin_role_get(self, inter: disnake.GuildCommandInteraction):
        """
        Show which role is currently required to modify balances
        """

        role_id = await self.bot.guild_config(inter.guild).admin_role_id.get()
        role_mention = f"<@&{role_id}>" if role_id is not None else "unset"

        await inter.response.send_message(
            f"Admin role is currently {role_mention}",
            allowed_mentions=disnake.AllowedMentions.none(),
            ephemeral=True,
        )

    @slash_config_admin_role.sub_command(name="set")
    @commands.has_guild_permissions(manage_guild=True)
    async def slash_config_admin_role_set(
        self, inter: disnake.GuildCommandInteraction, role: disnake.Role
    ):
        """
        Change which role is required to modify balances

        Parameters
        ----------
        role: The role to set
        """

        await self.bot.guild_config(inter.guild).admin_role_id.set(role.id)

        await inter.response.send_message(
            f"Set admin role to {role.mention}",
            allowed_mentions=disnake.AllowedMentions.none(),
        )

    @slash_config_admin_role.sub_command(name="unset")
    @commands.has_guild_permissions(manage_guild=True)
    async def slash_config_admin_role_unset(
        self, inter: disnake.GuildCommandInteraction
    ):
        """
        Unset the admin role, allowing anyone with Manage Server
        permissions to modify balances
        """

        await self.bot.guild_config(inter.guild).admin_role_id.set(None)

        await inter.response.send_message(
            "Unset admin role; falling back to Manage Server permissions",
            allowed_mentions=disnake.AllowedMentions.none(),
        )

    @slash_config.sub_command_group(name="memes_channel")
    async def slash_config_memes_channel(self, _: disnake.GuildCommandInteraction):
        pass

    @slash_config_memes_channel.sub_command(name="get")
    async def slash_config_memes_channel_get(
        self, inter: disnake.GuildCommandInteraction
    ):
        """
        Show which channel vote reactions are enabled in
        """

        channel_id = await self.bot.guild_config(inter.guild).memes_channel_id.get()
        channel_mention = f"<#{channel_id}>" if channel_id is not None else "unset"

        await inter.response.send_message(
            f"Memes channel is currently {channel_mention}",
            allowed_mentions=disnake.AllowedMentions.none(),
            ephemeral=True,
        )

    @slash_config_memes_channel.sub_command(name="set")
    @commands.has_guild_permissions(manage_guild=True)
    async def slash_config_memes_channel_set(
        self,
        inter: disnake.GuildCommandInteraction,
        channel: disnake.TextChannel,
    ):
        """
        Change which channel vote reactions are enabled in

        Parameters
        ----------
        channel: The channel to enable reactions in
        """

        await self.bot.guild_config(inter.guild).memes_channel_id.set(channel.id)

        await inter.response.send_message(
            f"Set memes channel to {channel.mention}",
            allowed_mentions=disnake.AllowedMentions.none(),
        )

    @slash_config_memes_channel.sub_command(name="unset")
    @commands.has_guild_permissions(manage_guild=True)
    async def slash_config_memes_channel_unset(
        self, inter: disnake.GuildCommandInteraction
    ):
        """
        Unset the memes channel, disabling vote reactions
        """

        await self.bot.guild_config(inter.guild).memes_channel_id.set(None)

        await inter.response.send_message(
            "Unset memes channel",
            allowed_mentions=disnake.AllowedMentions.none(),
        )

    @slash_config.sub_command_group(name="real_estate_category")
    async def slash_config_real_estate_category(
        self, _: disnake.GuildCommandInteraction
    ):
        pass

    @slash_config_real_estate_category.sub_command(name="get")
    async def slash_config_real_estate_category_get(
        self, inter: disnake.GuildCommandInteraction
    ):
        """
        Show the category where purchased real estate channels appear
        """

        category_id = await self.bot.guild_config(
            inter.guild
        ).real_estate_category_id.get()
        category_mention = f"<#{category_id}>" if category_id is not None else "unset"

        await inter.response.send_message(
            f"Real estate category is currently {category_mention}",
            allowed_mentions=disnake.AllowedMentions.none(),
            ephemeral=True,
        )

    @slash_config_real_estate_category.sub_command(name="set")
    @commands.has_guild_permissions(manage_guild=True)
    async def slash_config_real_estate_category_set(
        self, inter: disnake.GuildCommandInteraction, category: disnake.CategoryChannel
    ):
        """
        Set the category where purchased real estate channels appear

        Parameters
        ----------
        category: The category to set
        """

        await self.bot.guild_config(inter.guild).real_estate_category_id.set(
            category.id
        )

        await inter.response.send_message(
            f"Set real estate category to {category.mention}",
            allowed_mentions=disnake.AllowedMentions.none(),
        )

    @slash_config_real_estate_category.sub_command(name="unset")
    @commands.has_guild_permissions(manage_guild=True)
    async def slash_config_real_estate_category_unset(
        self, inter: disnake.GuildCommandInteraction
    ):
        """
        Unset the real estate category, preventing anyone from
        purchasing real estate channels
        """

        await self.bot.guild_config(inter.guild).real_estate_category_id.set(None)

        await inter.response.send_message(
            "Unset real estate category",
            allowed_mentions=disnake.AllowedMentions.none(),
        )


def setup(bot: BobuxEconomyBot):
    bot.add_cog(GuildConfig(bot))
