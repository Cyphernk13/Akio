# music/music.py
import discord
from discord.ext import commands
import wavelink

# Global queue dict: guild_id -> list of tracks
music_queues = {}

def get_queue(guild_id):
    return music_queues.setdefault(guild_id, [])

def setup(bot):
    # Ensure Lavalink node is connected when bot is ready
    @bot.hybrid_command(name="join", description="Join your voice channel")
    async def join(ctx):
        if not ctx.author.voice:
            return await ctx.send("You must be in a voice channel.")
        channel = ctx.author.voice.channel
        if ctx.voice_client is None:
            await channel.connect(cls=wavelink.Player)
            await ctx.send(f"Joined {channel.name}")
        else:
            await ctx.send("I'm already connected!")

    @bot.hybrid_command(name="play", description="Play a song from YouTube, SoundCloud, or Spotify (track)")
    async def play(ctx, *, query: str):
        player: wavelink.Player = ctx.voice_client
        if not player:
            if not ctx.author.voice:
                return await ctx.send("You must be in a voice channel.")
            channel = ctx.author.voice.channel
            player = await channel.connect(cls=wavelink.Player)

        tracks = await wavelink.YouTubeTrack.search(query)
        if not tracks:
            return await ctx.send("No tracks found.")

        track = tracks[0]
        queue = get_queue(ctx.guild.id)
        queue.append(track)

        if not player.is_playing():
            await start_playback(ctx, player, queue)
        else:
            await ctx.send(f"Added to queue: {track.title}")

    async def start_playback(ctx, player, queue):
        if not queue:
            await ctx.send("Queue is empty.")
            return
        track = queue.pop(0)
        await player.play(track)
        await ctx.send(f"Now playing: {track.title}")

    @bot.hybrid_command(name="skip", description="Skip the current song")
    async def skip(ctx):
        player: wavelink.Player = ctx.voice_client
        if not player or not player.is_playing():
            return await ctx.send("Nothing is playing.")
        await player.stop()
        await ctx.send("Skipped the current song.")

    @bot.hybrid_command(name="pause", description="Pause the music")
    async def pause(ctx):
        player: wavelink.Player = ctx.voice_client
        if not player or not player.is_playing():
            return await ctx.send("Nothing is playing.")
        await player.pause(True)
        await ctx.send("Paused.")

    @bot.hybrid_command(name="resume", description="Resume the music")
    async def resume(ctx):
        player: wavelink.Player = ctx.voice_client
        if not player or not player.is_paused():
            return await ctx.send("Nothing is paused.")
        await player.pause(False)
        await ctx.send("Resumed.")

    @bot.hybrid_command(name="stop", description="Stop the music and clear the queue")
    async def stop(ctx):
        player: wavelink.Player = ctx.voice_client
        if player:
            await player.stop()
        music_queues[ctx.guild.id] = []
        await ctx.send("Stopped and cleared the queue.")

    @bot.hybrid_command(name="queue", description="Show the song queue")
    async def queue_cmd(ctx):
        queue = get_queue(ctx.guild.id)
        if not queue:
            return await ctx.send("Queue is empty.")
        embed = discord.Embed(title="Music Queue", color=discord.Color.blue())
        for i, track in enumerate(queue, 1):
            embed.add_field(name=f"{i}. {track.title}", value=track.author, inline=False)
        await ctx.send(embed=embed)

    @bot.hybrid_command(name="leave", description="Leave the voice channel")
    async def leave(ctx):
        if ctx.voice_client:
            await ctx.voice_client.disconnect()
            await ctx.send("Disconnected.")
        else:
            await ctx.send("Not connected to a voice channel.")

    @bot.hybrid_command(name="volume", description="Set the volume (0-100)")
    async def volume(ctx, volume: int):
        player: wavelink.Player = ctx.voice_client
        if not player:
            return await ctx.send("Not connected to a voice channel.")
        await player.set_volume(volume)
        await ctx.send(f"Volume set to {volume}%")

    # Handle automatic playback of next song
    @bot.event
    async def on_wavelink_track_end(player, track, reason):
        queue = get_queue(player.guild.id)
        # Try to get a context for the guild
        guild = player.guild
        channel = guild.text_channels[0] if guild.text_channels else None
        if queue and channel:
            class DummyCtx:
                def __init__(self, guild, channel):
                    self.guild = guild
                    self.send = channel.send
            ctx = DummyCtx(guild, channel)
            await start_playback(ctx, player, queue)

