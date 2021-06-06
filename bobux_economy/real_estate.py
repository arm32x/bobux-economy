from typing import *

import discord
from discord.ext import commands

import balance
from database import connection as db


# PyCharm’s type checker is stupid and can’t figure out these enums.
CHANNEL_PRICES = {
    cast(discord.ChannelType, discord.ChannelType.text): (150, False),
    cast(discord.ChannelType, discord.ChannelType.voice): (100, False)
}

async def buy(channel_type: discord.ChannelType, buyer: discord.Member, name: str):
    price = CHANNEL_PRICES[channel_type]
    if price is None:
        raise commands.CommandError(f"{channel_type.name.capitalize()} channels are not for sale.")

    balance.subtract(buyer, *price)

    category = get_category(buyer.guild)
    channel = await category.create_text_channel(name, overwrites={
        buyer: discord.PermissionOverwrite(manage_channels=True)
    })

    c = db.cursor()
    c.execute("""
        INSERT INTO purchased_channels VALUES (?, ?, ?, ?);
    """, (channel.id, buyer.id, channel.guild.id, channel.created_at))
    db.commit()


def get_category(guild: discord.Guild) -> discord.CategoryChannel:
    c = db.cursor()
    c.execute("""
        SELECT real_estate_category FROM guilds WHERE id = ?;
    """, (guild.id, ))
    channel_id: Optional[int] = (c.fetchone() or (None, ))[0]

    if channel_id is None:
        raise commands.CommandError("Real estate is not set up on this server.")
    channel = guild.get_channel(channel_id)

    if not isinstance(channel, discord.CategoryChannel):
        raise commands.CommandError("Real estate category is not a category.")

    return channel
