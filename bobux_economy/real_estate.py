import sqlite3
from contextlib import closing
from typing import cast, Dict, Optional, Union

import disnake

from bobux_economy import balance
from bobux_economy.utils import UserFacingError


# PyCharm’s type checker is stupid and can’t figure out these enums.
CHANNEL_PRICES = {
    cast(disnake.ChannelType, disnake.ChannelType.text): (150, False),
    cast(disnake.ChannelType, disnake.ChannelType.voice): (100, False)
}

async def buy(db_connection: sqlite3.Connection, channel_type: disnake.ChannelType, buyer: disnake.Member, name: str) -> disnake.abc.GuildChannel:
    try:
        price = CHANNEL_PRICES[channel_type]
    except KeyError:
        raise UserFacingError(f"{channel_type.name.capitalize()} channels are not for sale")

    balance.subtract(db_connection, buyer, *price)

    bot_is_administrator = buyer.guild.me.guild_permissions.administrator

    category = get_category(db_connection, buyer.guild)
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
        balance.add(db_connection, buyer, *price)
        raise UserFacingError("The bot needs the Manage Channels permission for real estate")

    with closing(db_connection.cursor()) as db_cursor:
        db_cursor.execute("""
            INSERT INTO purchased_channels(id, owner_id, guild_id, purchase_time) VALUES (?, ?, ?, ?);
        """, (channel.id, buyer.id, channel.guild.id, channel.created_at))
        db_connection.commit()

    return channel

async def sell(db_connection: sqlite3.Connection, channel: Union[disnake.TextChannel, disnake.VoiceChannel], seller: disnake.Member):
    with closing(db_connection.cursor()) as db_cursor:
        db_cursor.execute("""
            SELECT owner_id FROM purchased_channels WHERE id = ?;
        """, (channel.id, ))
        owner_id: Optional[int] = (db_cursor.fetchone() or (None, ))[0]

        if owner_id != seller.id:
            raise UserFacingError(f"Only the owner of {channel.mention} can sell it")

        try:
            selling_price = balance.from_float(balance.to_float(*CHANNEL_PRICES[channel.type]) / 2)
        except KeyError:
            raise UserFacingError(f"{channel.type.name.capitalize()} channels are not for sale, how did you get one?")

        await channel.delete(reason=f"Sold by {seller.name}.")

        db_cursor.execute("""
            DELETE FROM purchased_channels WHERE id = ?;
        """, (channel.id, ))
        db_connection.commit()

    balance.add(db_connection, seller, *selling_price)

    return selling_price


def get_category(db_connection: sqlite3.Connection, guild: disnake.Guild) -> disnake.CategoryChannel:
    with closing(db_connection.cursor()) as db_cursor:
        db_cursor.execute("""
            SELECT real_estate_category FROM guilds WHERE id = ?;
        """, (guild.id, ))
        channel_id: Optional[int] = (db_cursor.fetchone() or (None, ))[0]

    if channel_id is None:
        raise UserFacingError("Real estate is not set up on this server")
    channel = guild.get_channel(channel_id)

    if not isinstance(channel, disnake.CategoryChannel):
        raise UserFacingError("Real estate category is not a category")

    return channel
