from typing import *

import discord

import balance
from database import connection as db
from globals import client, CommandError


# PyCharm’s type checker is stupid and can’t figure out these enums.
CHANNEL_PRICES = {
    cast(discord.ChannelType, discord.ChannelType.text): (150, False),
    cast(discord.ChannelType, discord.ChannelType.voice): (100, False)
}

async def buy(channel_type: discord.ChannelType, buyer: discord.Member, name: str) -> discord.abc.GuildChannel:
    try:
        price = CHANNEL_PRICES[channel_type]
    except KeyError:
        raise CommandError(f"{channel_type.name.capitalize()} channels are not for sale")

    balance.subtract(buyer, *price)

    category = get_category(buyer.guild)
    permissions = {
        # The bot can’t grant permission to manage permissions unless it is Administrator.
        buyer: discord.PermissionOverwrite(manage_channels=True),
        client.user: discord.PermissionOverwrite(view_channel=True, manage_channels=True, send_messages=False)
    }
    try:
        if channel_type is discord.ChannelType.text:
            channel = await category.create_text_channel(name, overwrites=permissions)
        elif channel_type is discord.ChannelType.voice:
            channel = await category.create_voice_channel(name, overwrites=permissions)
        else:
            raise RuntimeError(f"Could not create {channel_type.name} channel")
    except discord.Forbidden:
        balance.add(buyer, *price)
        raise CommandError("The bot needs the Manage Channels permission for real estate")

    c = db.cursor()
    c.execute("""
        INSERT INTO purchased_channels(id, owner_id, guild_id, purchase_time) VALUES (?, ?, ?, ?);
    """, (channel.id, buyer.id, channel.guild.id, channel.created_at))
    db.commit()

    return channel

async def sell(channel: Union[discord.TextChannel, discord.VoiceChannel], seller: discord.Member):
    c = db.cursor()
    c.execute("""
        SELECT owner_id FROM purchased_channels WHERE id = ?;
    """, (channel.id, ))
    owner_id: Optional[int] = (c.fetchone() or (None, ))[0]

    if owner_id != seller.id:
        raise CommandError(f"Only the owner of {channel.mention} can sell it")

    try:
        selling_price = balance.from_float(balance.to_float(*CHANNEL_PRICES[channel.type]) / 2)
    except KeyError:
        raise CommandError(f"{channel.type.name.capitalize()} channels are not for sale, how did you get one?")

    await channel.delete(reason=f"Sold by {seller.name}.")

    c.execute("""
        DELETE FROM purchased_channels WHERE id = ?;
    """, (channel.id, ))
    db.commit()


    balance.add(seller, *selling_price)

    return selling_price


def get_category(guild: discord.Guild) -> discord.CategoryChannel:
    c = db.cursor()
    c.execute("""
        SELECT real_estate_category FROM guilds WHERE id = ?;
    """, (guild.id, ))
    channel_id: Optional[int] = (c.fetchone() or (None, ))[0]

    if channel_id is None:
        raise CommandError("Real estate is not set up on this server")
    channel = guild.get_channel(channel_id)

    if not isinstance(channel, discord.CategoryChannel):
        raise CommandError("Real estate category is not a category")

    return channel
