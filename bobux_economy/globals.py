import discord
from discord_slash import SlashCommand


client = discord.Client()

slash = SlashCommand(client, sync_commands=True)
