import discord

client = discord.Client()

@client.event
async def on_ready():
    pass

@client.event
async def on_message(message: discord.Message):
    if message.author == client.user:
        return

    if message.content.startswith("b$ping"):
        await message.channel.send("Pong!")

with open("token.txt", "r") as token_file:
    token = token_file.read()
    client.run(token)
