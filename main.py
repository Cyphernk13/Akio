from dotenv import load_dotenv
from scripts.setup import bot
import discord
import os
from modules import commands, maths, bot_help
from games import rps, tictactoe, love, guess, flip, draw, challenge, dots
from ai import gemini
from music import music
from anime.commands import setup as setup_anime

load_dotenv()
commands.setup(bot)
maths.setup(bot)
music.setup(bot)
bot_help.setup(bot)
rps.setup(bot)
tictactoe.setup(bot)
love.setup(bot)
guess.setup(bot)
flip.setup(bot)
draw.setup(bot)
challenge.setup(bot)
dots.setup(bot)
gemini.setup(bot)
setup_anime(bot)

@bot.event
async def on_message(message):
    if isinstance(message.channel, discord.DMChannel) and message.author != bot.user:
        await message.author.send("Hello! I received your DM.\nI am sorry I don't have permissions to help you in the DM yet but you can always say **akio help** in the server :)")
    await bot.process_commands(message)

##------------>TOKEN<-----------##
TOKEN = os.getenv('TOKEN')
bot.run(TOKEN)
