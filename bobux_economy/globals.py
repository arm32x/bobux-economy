import discord
from discord_slash import SlashCommand


client = discord.Client()

slash = SlashCommand(client, sync_commands=True, debug_guild=766073081449545798)
