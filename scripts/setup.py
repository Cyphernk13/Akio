# scripts/setup.py
import discord
from discord.ext import commands
import lavalink
import os

# Import the music module to be set up later
from music import music
from music.nodes import EnhancedLavalinkNodeManager

intents = discord.Intents.all()
bot = commands.Bot(command_prefix=['Akio ', 'akio '], help_command=None, intents=intents)

@bot.event
async def on_ready():
    """Fires when the bot is ready and handles all post-login setup."""
    print(f'Logged in as {bot.user.name}')
    
    # Initialize the Lavalink client
    bot.lavalink = lavalink.Client(bot.user.id)
    
    # Primary working node from your old setup
    bot.lavalink.add_node(
        host='173.249.0.115',
        port=13592,
        password='https://camming.xyz',
        region='us-central',
        ssl=False
    )
    print("Lavalink client initialized.")

    # Bootstrap enhanced node manager for 24/7 resilience
    try:
        node_manager = EnhancedLavalinkNodeManager(bot)
        await node_manager.bootstrap()
        node_manager.start_background_tasks()
        bot.node_manager = node_manager
        print("Enhanced Lavalink node manager started with smart failover.")
    except Exception as e:
        print(f"Failed to start enhanced node manager: {e}")

    # --- This is the crucial line ---
    # Load the music module now that Lavalink is ready.
    music.setup(bot)
    print("Music module loaded.")

    # Finalize bot startup
    await bot.change_presence(activity=discord.Streaming(name="akio help", url="https://www.twitch.tv/discord"))
    await bot.tree.sync()
    print("Bot is ready and commands are synced!")


# Add global error handler for node failures
@bot.event
async def on_lavalink_node_disconnect(node):
    """Handle node disconnections with smart failover."""
    try:
        node_manager = getattr(bot, 'node_manager', None)
        if node_manager:
            await node_manager.handle_node_failure(node.identifier)
        print(f"Node {node.identifier} disconnected - attempting failover...")
    except Exception as e:
        print(f"Error handling node failure: {e}")

@bot.event
async def on_lavalink_node_connect(node):
    """Handle node connections."""
    print(f"Node {node.identifier} connected successfully!")