import discord
from discord.ext import commands,tasks
import yt_dlp as youtube_dl
import random
import asyncio

def setup(bot):
    # Suppress noise about console usage from errors
    youtube_dl.utils.bug_reports_message = lambda: ''

    ytdl_format_options = {
    'format': 'bestaudio/best',
    'outtmpl': '-',  # Output to stdout
    'restrictfilenames': True,
    'noplaylist': True,
    'nocheckcertificate': True,
    'ignoreerrors': False,
    'logtostderr': False,
    'quiet': True,
    'no_warnings': True,
    'default_search': 'ytsearch1',
    'source_address': '0.0.0.0',
    'extract_flat': 'in_playlist',  # Don't extract videos in playlists
}

    ffmpeg_options = {
        'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5 -nostdin',
        'options': '-vn -bufsize 64k -probesize 10M',
        'executable': 'C:\\ffmpeg-7.0.1-essentials_build\\bin\\ffmpeg.exe'  # Change this to your ffmpeg path
    }

    ytdl = youtube_dl.YoutubeDL(ytdl_format_options)

    class YTDLSource(discord.PCMVolumeTransformer):
        def __init__(self, source, *, data, volume=0.5):
            super().__init__(source, volume)
            self.data = data
            self.title = data.get('title')
            self.url = data.get('webpage_url')
            self.channel = data.get('channel', 'Unknown')
            self.duration = data.get('duration')

        @classmethod
        async def from_url(cls, url, *, loop=None, stream=True, retry_count=3):
            loop = loop or asyncio.get_event_loop()
            for attempt in range(retry_count):
                try:
                    data = await loop.run_in_executor(None, lambda: ytdl.extract_info(url, download=not stream))
                    if 'entries' in data:
                        data = data['entries'][0]
                    filename = data['url'] if stream else ytdl.prepare_filename(data)
                    return cls(discord.FFmpegPCMAudio(filename, **ffmpeg_options), data=data)
                except Exception as e:
                    if attempt < retry_count - 1:
                        await asyncio.sleep(1)
                    else:
                        raise e

        @classmethod
        async def regather_stream(cls, data, *, loop, retry_count=3):
            loop = loop or asyncio.get_event_loop()
            for attempt in range(retry_count):
                try:
                    refreshed_data = await loop.run_in_executor(None, lambda: ytdl.extract_info(data['webpage_url'], download=False))
                    return cls(discord.FFmpegPCMAudio(refreshed_data['url'], **ffmpeg_options), data=refreshed_data)
                except Exception as e:
                    if attempt < retry_count - 1:
                        await asyncio.sleep(1)
                    else:
                        raise e


    songs = []
    current_song = None

    @bot.command()
    async def play(ctx, *, query):
        global current_song
        try:
            if not ctx.voice_client.is_playing():
                player = await YTDLSource.from_url(query, loop=ctx.bot.loop)
                ctx.voice_client.play(player, after=lambda e: asyncio.run_coroutine_threadsafe(play_next(ctx), ctx.bot.loop))
                current_song = player
                embed = create_music_panel(player.title, ctx.author, player.duration, player.channel)
                view = MusicControlView(ctx)
                await ctx.send(embed=embed, view=view)
                
                if not check_voice_state.is_running():
                    check_voice_state.start(ctx)
            else:
                songs.append(query)
                player = await YTDLSource.from_url(query, loop=ctx.bot.loop, stream=False)
                await ctx.send(f'Added to queue: {player.title}')
        except Exception as e:
            await ctx.send(f"An error occurred while processing your request: {str(e)}")

    async def play_next(ctx):
        global current_song
        if songs:
            query = songs.pop(0)
            try:
                player = await YTDLSource.from_url(query, loop=ctx.bot.loop)
                ctx.voice_client.play(player, after=lambda e: asyncio.run_coroutine_threadsafe(play_next(ctx), ctx.bot.loop))
                current_song = player
                embed = create_music_panel(player.title, ctx.author, player.duration, player.channel)
                view = MusicControlView(ctx)
                await ctx.send(embed=embed, view=view)
            except Exception as e:
                await ctx.send(f"An error occurred while playing {query}: {str(e)}")
                await asyncio.sleep(1)  # Wait a bit before trying the next song
                await play_next(ctx)
        else:
            current_song = None
            await ctx.send('Queue is empty.')
            if check_voice_state.is_running():
                check_voice_state.cancel()

    @bot.command()
    async def join(ctx):
        if not ctx.message.author.voice:
            await ctx.send("{} is not connected to a voice channel".format(ctx.message.author.name))
            return
        else:
            channel = ctx.message.author.voice.channel

        await channel.connect()

    @bot.command()
    async def leave(ctx):
        if ctx.voice_client:
            await ctx.guild.voice_client.disconnect()
        else:
            await ctx.send("The bot is not connected to a voice channel.")

    @bot.command()
    async def pause(ctx):
        if ctx.voice_client.is_playing():
            ctx.voice_client.pause()
            await ctx.send("Music paused.")
        else:
            await ctx.send("No music is playing.")

    @bot.command()
    async def resume(ctx):
        if ctx.voice_client.is_paused():
            ctx.voice_client.resume()
            await ctx.send("Music resumed.")
        else:
            await ctx.send("The music is not paused.")

    @bot.command()
    async def stop(ctx):
        if ctx.voice_client.is_playing():
            ctx.voice_client.stop()
        songs.clear()
        global current_song
        current_song = None
        
        # Stop the voice state check
        if check_voice_state.is_running():
            check_voice_state.cancel()
        
        await ctx.send("Music stopped and queue cleared.")

    class MusicControlView(discord.ui.View):
        def __init__(self, ctx):
            super().__init__(timeout=None)
            self.ctx = ctx

        @discord.ui.button(label='', style=discord.ButtonStyle.primary, emoji='⏮️')
        async def back_button(self, button: discord.ui.Button, interaction: discord.Interaction):
            if len(songs) > 0:
                songs.insert(0, current_song.url)
                self.ctx.voice_client.stop()
                await interaction.response.send_message("Playing previous song.", ephemeral=True)
            else:
                await interaction.response.send_message("No previous song in queue.", ephemeral=True)

        @discord.ui.button(label='', style=discord.ButtonStyle.primary, emoji='⏸️')
        async def pause_button(self, button: discord.ui.Button, interaction: discord.Interaction):
            if self.ctx.voice_client.is_playing():
                self.ctx.voice_client.pause()
                await interaction.response.send_message("Music paused.", ephemeral=True)
            else:
                await interaction.response.send_message("No music is playing.", ephemeral=True)

        @discord.ui.button(label='', style=discord.ButtonStyle.primary, emoji='▶️')
        async def resume_button(self, button: discord.ui.Button, interaction: discord.Interaction):
            if self.ctx.voice_client.is_paused():
                self.ctx.voice_client.resume()
                await interaction.response.send_message("Music resumed.", ephemeral=True)
            else:
                await interaction.response.send_message("The music is not paused.", ephemeral=True)

        @discord.ui.button(label='', style=discord.ButtonStyle.danger, emoji='⏭️')
        async def skip_button(self, button: discord.ui.Button, interaction: discord.Interaction):
            if self.ctx.voice_client.is_playing():
                self.ctx.voice_client.stop()
                await interaction.response.send_message("Skipped current song.", ephemeral=True)
                await play_next(self.ctx)
            else:
                await interaction.response.send_message("No music is playing.", ephemeral=True)

        @discord.ui.button(label='', style=discord.ButtonStyle.danger, emoji='⏹️')
        async def stop_button(self, button: discord.ui.Button, interaction: discord.Interaction):
            global current_song
            self.ctx.voice_client.stop()
            songs.clear()
            current_song = None
            await interaction.response.send_message("Music stopped and queue cleared.", ephemeral=True)

        @discord.ui.button(label='', style=discord.ButtonStyle.secondary, emoji='🔀')
        async def shuffle_button(self, button: discord.ui.Button, interaction: discord.Interaction):
            if len(songs) > 1:
                random.shuffle(songs)
                await interaction.response.send_message("Queue shuffled.", ephemeral=True)
            else:
                await interaction.response.send_message("Not enough songs in queue to shuffle.", ephemeral=True)

        async def interaction_check(self, interaction: discord.Interaction) -> bool:
            return interaction.user == self.ctx.author

    def create_music_panel(title, requester, duration, channel):
        embed = discord.Embed(title="MUSIC PANEL", color=discord.Color.blue())
        embed.add_field(name="🎵", value=title, inline=False)
        embed.add_field(name="Requested By", value=requester.mention, inline=True)
        embed.add_field(name="Music Duration", value=f"{duration//60}m {duration%60}s", inline=True)
        embed.add_field(name="Music Author", value=channel, inline=True)  # Change this line
        return embed

    @bot.command()
    async def queue(ctx):
        if ctx.voice_client and ctx.voice_client.is_playing():
            embed = discord.Embed(title="Music Queue", color=discord.Color.blue())
            
            # Try to get the current song info
            try:
                current = ctx.voice_client.source
                embed.add_field(name="Now Playing:", value=current.title if hasattr(current, 'title') else "Unknown", inline=False)
            except AttributeError:
                embed.add_field(name="Now Playing:", value="Unable to fetch current song info", inline=False)

            # Add queued songs
            for i, song in enumerate(songs, start=1):
                try:
                    player = await YTDLSource.from_url(song, loop=ctx.bot.loop, stream=False)
                    embed.add_field(name=f"Song {i}:", value=player.title, inline=False)
                except Exception as e:
                    embed.add_field(name=f"Song {i}:", value=f"Error fetching song info: {str(e)}", inline=False)
            
            await ctx.send(embed=embed)
        else:
            await ctx.send("No music is currently playing and the queue is empty.")


    @play.before_invoke
    @join.before_invoke
    async def ensure_voice_connected(ctx):
        if ctx.voice_client is None or not ctx.voice_client.is_connected():
            channel = ctx.author.voice.channel
            await channel.connect()

    @tasks.loop(seconds=30)
    async def check_voice_state(ctx):
        if ctx.voice_client and not ctx.voice_client.is_playing() and current_song:
            try:
                player = await YTDLSource.regather_stream(current_song.data, loop=ctx.bot.loop)
                ctx.voice_client.play(player, after=lambda e: asyncio.run_coroutine_threadsafe(play_next(ctx), ctx.bot.loop))
            except Exception as e:
                await ctx.send(f"An error occurred while trying to resume playback: {str(e)}")
                await asyncio.sleep(1)  # Wait a bit before trying to play the next song
                await play_next(ctx)