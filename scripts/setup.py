# bot_setup.py

import discord
from discord.ext import commands
import os
import wavelink

intents = discord.Intents.all()
bot = commands.Bot(command_prefix=['Akio ', 'akio '], help_command=None, intents=intents)

@bot.event
async def on_ready():
    await bot.change_presence(activity=discord.Streaming(name="akio help", url="https://www.twitch.tv/discord"))
    print(f'Logged in as {bot.user.name}')
    await bot.tree.sync()

    # node = wavelink.Node(
    #     uri='http://lavalink.serenetia.com:443',
    #     password='https://dsc.gg/ajidevserver',
    #     secure=True  # Changed from https=True
    # )
    # await wavelink.NodePool.connect(client=bot, nodes=[node])
    # print("Lavalink connected!")