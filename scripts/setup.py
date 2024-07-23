# bot_setup.py

import discord
from discord.ext import commands
import os

intents = discord.Intents.all()
bot = commands.Bot(command_prefix=['Akio ', 'akio '], help_command=None, intents=intents)

@bot.event
async def on_ready():
    await bot.change_presence(activity=discord.Game(name="akio help"))
    print(f'Logged in as {bot.user.name}')
    await bot.tree.sync()
