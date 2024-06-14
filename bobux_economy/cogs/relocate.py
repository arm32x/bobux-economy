from typing import Union

import disnake
from disnake.ext import commands

from bobux_economy.bot import BobuxEconomyBot
from bobux_economy.utils import UserFacingError


class MessageAlreadyInChannel(UserFacingError):
    channel: disnake.abc.GuildChannel

    def __init__(self, channel: disnake.abc.GuildChannel):
        super().__init__(f"Message already in {channel.mention}")
        self.channel = channel


class Relocate(commands.Cog):
    bot: BobuxEconomyBot

    def __init__(self, bot: BobuxEconomyBot):
        self.bot = bot

    @commands.slash_command(name="relocate")
    # There are additional permission checks in the command body that
    # check against the destination channel.
    @commands.bot_has_permissions(manage_messages=True)
    @commands.has_permissions(manage_messages=True)
    async def slash_relocate(
        self,
        inter: disnake.GuildCommandInteraction,
        message_id: str,
        destination: Union[disnake.TextChannel, disnake.VoiceChannel],
        remove_speech_bubbles: bool = False,
    ):
        """
        Move a message to a different channel

        Parameters
        ----------
        message_id:
            The ID of the message to relocate (slash commands don't
            support messages as parameters)
        destination:
            The channel to relocate the message to
        remove_speech_bubbles:
            Whether to remove 💬 or 🗨️ from the start of the message
        """

        try:
            message_id_int = int(message_id)
        except ValueError as ex:
            raise commands.errors.BadArgument("Input a valid integer.") from ex

        # These permission checks cannot be expressed as decorators
        # because they depend on the destination parameter.
        if not destination.permissions_for(inter.author).manage_messages:
            raise commands.errors.MissingPermissions(["manage_messages"])
        if not destination.permissions_for(inter.me).manage_webhooks:
            raise commands.errors.BotMissingPermissions(["manage_webhooks"])

        message = await inter.channel.fetch_message(message_id_int)
        await self._relocate_message(message, destination, remove_speech_bubbles)

        await inter.response.send_message(
            f"Relocated message to {destination.mention}",
            allowed_mentions=disnake.AllowedMentions.none(),
            ephemeral=True,
        )

    async def _relocate_message(
        self,
        message: disnake.Message,
        # TODO: Support threads.
        destination: Union[disnake.TextChannel, disnake.VoiceChannel],
        remove_speech_bubbles: bool = False,
    ):
        if message.channel.id == destination.id:
            raise MessageAlreadyInChannel(destination)

        # Create a webhook that mimics the original poster.
        target_author = message.author
        webhook: disnake.Webhook = await destination.create_webhook(
            name=target_author.display_name,
            avatar=await target_author.display_avatar.read(),
            reason=f"Puppeting user {target_author.id} in order to relocate a message",
        )

        # Get the attachments from the original message as uploadable
        # files.
        files = []
        for attachment in message.attachments:
            files.append(await attachment.to_file(spoiler=attachment.is_spoiler()))

        # If requested, remove speech bubbles from the start of the
        # message content.
        content = message.content
        if remove_speech_bubbles:
            if content.startswith("💬"):
                content = content[1:].lstrip()
            elif content.startswith("🗨️"):
                content = content[2:].lstrip()

        # Repost the meme in the destination channel. Vote reactions
        # will be automatically added if necessary in the on_message()
        # handler.
        await webhook.send(
            content=content,
            files=files,
            allowed_mentions=disnake.AllowedMentions.none(),
            tts=message.tts,
        )
        # Delete the original message using the bot API, not the
        # interactions API.
        await disnake.Message.delete(message)

        # Permanently associate this webhook ID with the original
        # poster.
        async with self.bot.db_connection.cursor() as db_cursor:
            await db_cursor.execute(
                "INSERT INTO webhooks VALUES(?, ?)",
                (webhook.id, target_author.id),
            )
            await self.bot.db_connection.commit()

        # Delete the webhook
        await webhook.delete(reason="Will no longer be used")


def setup(bot: BobuxEconomyBot):
    bot.add_cog(Relocate(bot))
