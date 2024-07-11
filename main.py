from dotenv import load_dotenv
from setup import bot
import discord
import os
import commands
import games
import maths

load_dotenv()
commands.setup(bot)
games.setup(bot)
maths.setup(bot)

@bot.event
async def on_message(message):
    if isinstance(message.channel, discord.DMChannel) and message.author != bot.user:
        await message.author.send("Hello! I received your DM.\nI am sorry I don't have permissions to help you in the DM yet but you can always say **akio help** in the server :)")
    await bot.process_commands(message)

##------------>TOKEN<-----------##
TOKEN = os.getenv('TOKEN')
bot.run(TOKEN)

