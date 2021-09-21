from typing import *

import discord
from discord.ext import commands

from database import connection as db


bot: commands.Bot = commands.Bot(command_prefix="b$")
