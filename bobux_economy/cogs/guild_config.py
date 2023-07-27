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

    @slash_config.sub_command_group(name="vote_channels")
    async def slash_config_vote_channels(self, _: disnake.GuildCommandInteraction):
        pass

    @slash_config_vote_channels.sub_command(name="list")
    async def slash_config_vote_channels_list(
        self, inter: disnake.GuildCommandInteraction
    ):
        """
        Show the channels in this server where voting is enabled
        """

        channel_ids = await self.bot.guild_config(inter.guild).vote_channel_ids.get()

        # This sorts the list by channel ID instead of channel name,
        # which should maybe be changed in the future.
        channel_mentions = [f"<#{id}>" for id in sorted(channel_ids)]
        channel_mentions_str = "\n".join(channel_mentions)

        await inter.response.send_message(
            f"Vote channels in **{inter.guild.name}**:\n{channel_mentions_str}",
            allowed_mentions=disnake.AllowedMentions.none(),
            ephemeral=True,
        )

    @slash_config_vote_channels.sub_command(name="add")
    @commands.has_guild_permissions(manage_guild=True)
    async def slash_config_vote_channels_add(
        self, inter: disnake.GuildCommandInteraction, channel: disnake.TextChannel
    ):
        """
        Enable vote reactions for a channel

        Parameter
        ---------
        channel: The channel to enable voting in
        """

        await self.bot.guild_config(inter.guild).vote_channel_ids.add(channel.id)

        await inter.response.send_message(
            f"Enabled vote reactions for {channel.mention}",
            allowed_mentions=disnake.AllowedMentions.none(),
        )

    @slash_config_vote_channels.sub_command(name="remove")
    @commands.has_guild_permissions(manage_guild=True)
    async def slash_config_vote_channels_remove(
        self, inter: disnake.GuildCommandInteraction, channel: disnake.TextChannel
    ):
        """
        Disable vote reactions for a channel

        Parameter
        ---------
        channel: The channel to disable voting in
        """

        await self.bot.guild_config(inter.guild).vote_channel_ids.remove(channel.id)

        await inter.response.send_message(
            f"Disabled vote reactions for {channel.mention}",
            allowed_mentions=disnake.AllowedMentions.none(),
        )

    @slash_config_vote_channels.sub_command(name="remove_all")
    @commands.has_guild_permissions(manage_guild=True)
    async def slash_config_vote_channels_remove_all(
        self, inter: disnake.GuildCommandInteraction
    ):
        """
        Disable vote reactions for every channel in this server
        """

        channels_affected = await self.bot.guild_config(
            inter.guild
        ).vote_channel_ids.clear()

        await inter.response.send_message(
            f"Disabled vote reactions for {channels_affected} channels",
            allowed_mentions=disnake.AllowedMentions.none(),
        )


def setup(bot: BobuxEconomyBot):
    bot.add_cog(GuildConfig(bot))
