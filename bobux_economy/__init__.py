import sqlite3
from typing import *

import discord
from discord.ext import commands

import database

cursor = database.connection.cursor()
database.initialize(cursor)

def determine_prefix(_, message: discord.Message):
    cursor.execute("SELECT prefix FROM guilds WHERE id = ?;", (message.guild.id, ))
    guild_row: Optional[sqlite3.Row] = cursor.fetchone()
    if guild_row is None:
        return "b$"
    else:
        return guild_row["prefix"]

bot = commands.Bot(command_prefix=determine_prefix)

@bot.event
async def on_ready():
    print("Ready.")

@bot.command()
async def ping(ctx: commands.Context):
    await ctx.channel.send("Pong!")

@bot.command()
async def prefix(ctx: commands.Context, new_prefix: str):
    cursor.execute("INSERT INTO guilds(id, prefix) VALUES(?, ?) ON CONFLICT(id) DO UPDATE SET prefix=excluded.prefix;", (ctx.guild.id, new_prefix))
    cursor.commit()
    await ctx.channel.send(f"Updated prefix to `{new_prefix}`.")

with open("../token.txt", "r") as token_file:
    token = token_file.read()
    bot.run(token)
