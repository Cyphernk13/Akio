# scripts/setup.py
import discord
from discord.ext import commands
import lavalink
import os

# Import the music module to be set up later
from music import music

intents = discord.Intents.all()
bot = commands.Bot(command_prefix=['Akio ', 'akio '], help_command=None, intents=intents)

@bot.event
async def on_ready():
    """Fires when the bot is ready and handles all post-login setup."""
    print(f'Logged in as {bot.user.name}')
    
    # Initialize the Lavalink client
    bot.lavalink = lavalink.Client(bot.user.id)
    bot.lavalink.add_node(
        host='lavalink.serenetia.com',
        port=443,
        password='https://dsc.gg/ajidevserver',
        region='us-central',
        ssl=True
    )
    print("Lavalink client initialized.")

    # --- This is the crucial line ---
    # Load the music module now that Lavalink is ready.
    music.setup(bot)
    print("Music module loaded.")

    # Finalize bot startup
    await bot.change_presence(activity=discord.Streaming(name="akio help", url="https://www.twitch.tv/discord"))
    await bot.tree.sync()
    print("Bot is ready and commands are synced!")

