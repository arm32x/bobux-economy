from typing import cast, Dict, Optional, Union

import aiosqlite
import disnake

from bobux_economy import balance
from bobux_economy.utils import UserFacingError


# PyCharm’s type checker is stupid and can’t figure out these enums.
CHANNEL_PRICES = {
    cast(disnake.ChannelType, disnake.ChannelType.text): (150, False),
    cast(disnake.ChannelType, disnake.ChannelType.voice): (100, False)
}

async def buy(db_connection: aiosqlite.Connection, channel_type: disnake.ChannelType, buyer: disnake.Member, name: str) -> disnake.abc.GuildChannel:
    try:
        price = CHANNEL_PRICES[channel_type]
    except KeyError:
        raise UserFacingError(f"{channel_type.name.capitalize()} channels are not for sale")

    await balance.subtract(db_connection, buyer, *price)

    bot_is_administrator = buyer.guild.me.guild_permissions.administrator

    category = await get_category(db_connection, buyer.guild)
    permissions: Dict[Union[disnake.Member, disnake.Role], disnake.PermissionOverwrite] = {
        # The bot can’t grant permission to manage permissions unless it is Administrator.
        buyer: disnake.PermissionOverwrite(manage_channels=True, manage_permissions=(True if bot_is_administrator else None)),
        buyer.guild.me: disnake.PermissionOverwrite(view_channel=True, manage_channels=True, send_messages=False)
    }
    try:
        if channel_type is disnake.ChannelType.text:
            channel = await category.create_text_channel(name, overwrites=permissions)
        elif channel_type is disnake.ChannelType.voice:
            channel = await category.create_voice_channel(name, overwrites=permissions)
        else:
            raise RuntimeError(f"Could not create {channel_type.name} channel")
    except disnake.Forbidden:
        await balance.add(db_connection, buyer, *price)
        raise UserFacingError("The bot needs the Manage Channels permission for real estate")

    async with db_connection.cursor() as db_cursor:
        await db_cursor.execute("""
            INSERT INTO purchased_channels(id, owner_id, guild_id, purchase_time) VALUES (?, ?, ?, ?);
        """, (channel.id, buyer.id, channel.guild.id, channel.created_at))
        await db_connection.commit()

    return channel

async def sell(db_connection: aiosqlite.Connection, channel: Union[disnake.TextChannel, disnake.VoiceChannel], seller: disnake.Member):
    async with db_connection.cursor() as db_cursor:
        await db_cursor.execute("""
            SELECT owner_id FROM purchased_channels WHERE id = ?;
        """, (channel.id, ))
        row = await db_cursor.fetchone()

        owner_id: Optional[int] = row["owner_id"] if row is not None else None

        if owner_id != seller.id:
            raise UserFacingError(f"Only the owner of {channel.mention} can sell it")

        try:
            selling_price = balance.from_float(balance.to_float(*CHANNEL_PRICES[channel.type]) / 2)
        except KeyError:
            raise UserFacingError(f"{channel.type.name.capitalize()} channels are not for sale, how did you get one?")

        await channel.delete(reason=f"Sold by {seller.name}.")

        await db_cursor.execute("""
            DELETE FROM purchased_channels WHERE id = ?;
        """, (channel.id, ))
        await db_connection.commit()

    await balance.add(db_connection, seller, *selling_price)

    return selling_price


async def get_category(db_connection: aiosqlite.Connection, guild: disnake.Guild) -> disnake.CategoryChannel:
    async with db_connection.cursor() as db_cursor:
        await db_cursor.execute("""
            SELECT real_estate_category FROM guilds WHERE id = ?;
        """, (guild.id, ))
        row = await db_cursor.fetchone()

        channel_id: Optional[int] = row["real_estate_category"] if row is not None else None

    if channel_id is None:
        raise UserFacingError("Real estate is not set up on this server")
    channel = guild.get_channel(channel_id)

    if not isinstance(channel, disnake.CategoryChannel):
        raise UserFacingError("Real estate category is not a category")

    return channel
