import sqlite3

import discord

import database

cursor = database.connection.cursor()
database.initialize(cursor)

client = discord.Client()

@client.event
async def on_ready():
    print("Ready.")

@client.event
async def on_message(message: discord.Message):
    if message.author == client.user:
        return

    cursor.execute("INSERT OR IGNORE INTO guilds(id) VALUES(?);", (message.guild.id, ))
    database.connection.commit()
    cursor.execute("SELECT * FROM guilds WHERE id = ?;", (message.guild.id, ))
    guild_row: sqlite3.Row = cursor.fetchone()

    prefix = guild_row["prefix"]

with open("../token.txt", "r") as token_file:
    token = token_file.read()
    client.run(token)
