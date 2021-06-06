from typing import *

import discord
from discord.ext import commands

import balance
from database import connection as db


TEXT_CHANNEL_PRICE = (150, False)
VOICE_CHANNEL_PRICE = (100, False)
CATEGORY_PRICE = (250, False)

async def buy(buyer: discord.Member, name: str):
    balance.subtract(buyer, *TEXT_CHANNEL_PRICE)

    category = get_category(buyer.guild)
    channel = await category.create_text_channel(name, overwrites={
        buyer: discord.PermissionOverwrite(manage_channels=True)
    })

    c = db.cursor()
    c.execute("""
        INSERT INTO purchased_channels VALUES (?, ?, ?, ?);
    """, (channel.id, buyer.id, channel.guild.id, channel.created_at))


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
