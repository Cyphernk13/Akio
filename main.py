from dotenv import load_dotenv
from scripts.setup import bot
import discord
import os
from modules import commands, games, maths, bot_help
from music import music

load_dotenv()
commands.setup(bot)
games.setup(bot)
maths.setup(bot)
music.setup(bot)
bot_help.setup(bot)

@bot.event
async def on_message(message):
    if isinstance(message.channel, discord.DMChannel) and message.author != bot.user:
        await message.author.send("Hello! I received your DM.\nI am sorry I don't have permissions to help you in the DM yet but you can always say **akio help** in the server :)")
    await bot.process_commands(message)

##------------>TOKEN<-----------##
TOKEN = os.getenv('TOKEN')
print(f"TOKEN: {TOKEN}")  # Add this line to check the value
bot.run(TOKEN)
