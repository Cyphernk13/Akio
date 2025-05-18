import discord
from discord.ext import commands
import yt_dlp as youtube_dl
import random
import asyncio
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)

def setup(bot):
    # Suppress noise about console usage from errors
    youtube_dl.utils.bug_reports_message = lambda: ''

    ytdl_format_options = {
        'format': 'bestaudio/best',
        'outtmpl': '%(extractor)s-%(id)s-%(title)s.%(ext)s',
        'restrictfilenames': True,
        'noplaylist': True,
        'nocheckcertificate': True,
        'ignoreerrors': False,
        'logtostderr': False,
        'quiet': True,
        'no_warnings': True,
        'default_search': 'ytsearch1',  # Search for the first video on YouTube
        'source_address': '0.0.0.0'  # Bind to IPv4 since IPv6 addresses cause issues sometimes
    }

    ffmpeg_options = {
        'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
        'options': '-vn -filter:a "volume=0.5"',
        'executable': 'C:\\ffmpeg-7.0.1-essentials_build\\bin\\ffmpeg.exe'  # Change this to your ffmpeg path
    }

    ytdl = youtube_dl.YoutubeDL(ytdl_format_options)

    class YTDLSource(discord.PCMVolumeTransformer):
        def __init__(self, source, *, data, volume=0.5):
            super().__init__(source, volume)

            self.data = data
            self.title = data.get('title')
            self.url = data.get('url')
            self.channel = data.get('channel')
            self.channel_avatar = data.get('thumbnail')

        @classmethod
        async def from_url(cls, url, *, loop=None, stream=False):
            loop = loop or asyncio.get_event_loop()
            data = await loop.run_in_executor(None, lambda: ytdl.extract_info(url, download=not stream))
            if 'entries' in data:
                # Takes the first item from a playlist or search results
                data = data['entries'][0]

            filename = data['url'] if stream else ytdl.prepare_filename(data)
            return cls(discord.FFmpegPCMAudio(filename, **ffmpeg_options), data=data)


    songs = []
    current_song = None

    async def play_next(ctx):
        global current_song
        try:
            if songs:
                query = songs.pop(0)
                player = await YTDLSource.from_url(query, loop=ctx.bot.loop, stream=True)
                ctx.voice_client.play(player, after=lambda e: asyncio.run_coroutine_threadsafe(play_next(ctx), ctx.bot.loop))
                current_song = player
                embed = create_music_panel(player.title, ctx.author, player.data['duration'],player.channel, player.channel_avatar)
                view = MusicControlView(ctx)
                await ctx.send(embed=embed, view=view)
            else:
                current_song = None
                await ctx.send('Queue is empty.')
        except Exception as e:
            logging.error(f"Error in play_next function: {str(e)}")
            current_song = None
            await ctx.send(f"An error occurred while playing the next song: {str(e)}")
            await play_next(ctx)  # Retry playing the next song

    async def retry_play(ctx, query):
        try:
            player = await YTDLSource.from_url(query, loop=ctx.bot.loop, stream=True)
            ctx.voice_client.play(player, after=lambda e: asyncio.run_coroutine_threadsafe(after_song_end(ctx, e), ctx.bot.loop))
            current_song = player
            embed = create_music_panel(player.title, ctx.author, player.data['duration'],player.channel, player.channel_avatar)
            view = MusicControlView(ctx)
            await ctx.send(embed=embed, view=view)
        except Exception as e:
            logging.error(f"Error in retry_play function: {str(e)}")
            await ctx.send(f"An error occurred while trying to play the song: {str(e)}")
            await asyncio.sleep(5)  # Wait before retrying
            await retry_play(ctx, query)  # Retry playing the song

    async def after_song_end(ctx, error):
        if error:
            logging.error(f"Playback error: {error}")
        await play_next(ctx)

    @bot.hybrid_command(description="Play a song from YouTube")
    async def play(ctx, *, query):
        global current_song
        try:
            if not ctx.voice_client.is_playing():
                player = await YTDLSource.from_url(query, loop=ctx.bot.loop, stream=True)
                ctx.voice_client.play(player, after=lambda e: asyncio.run_coroutine_threadsafe(after_song_end(ctx, e), ctx.bot.loop))
                current_song = player
                embed = create_music_panel(player.title, ctx.author, player.data['duration'], player.channel, player.channel_avatar)
                view = MusicControlView(ctx)
                await ctx.send(embed=embed, view=view)
            else:
                songs.append(query)
                player = await YTDLSource.from_url(query, loop=ctx.bot.loop, stream=True)
                await ctx.send(f'Added to queue: {player.title}')
        except Exception as e:
            logging.error(f"Error in play command: {str(e)}")
            await ctx.send(f"An error occurred while trying to play the song: {str(e)}")
            await retry_play(ctx, query)  # Retry playing the song on error

    @bot.hybrid_command(description="Join the voice channel")
    async def join(ctx):
        if not ctx.message.author.voice:
            await ctx.send("{} is not connected to a voice channel".format(ctx.message.author.name))
            return
        else:
            channel = ctx.message.author.voice.channel

        await channel.connect()

    @bot.hybrid_command(description="Leave the voice channel")
    async def leave(ctx):
        if ctx.voice_client:
            await ctx.guild.voice_client.disconnect()
        else:
            await ctx.send("The bot is not connected to a voice channel.")

    @bot.hybrid_command(description="Pause the music")
    async def pause(ctx):
        if ctx.voice_client.is_playing():
            ctx.voice_client.pause()
            await ctx.send("Music paused.")
        else:
            await ctx.send("No music is playing.")

    @bot.hybrid_command(description="Resume the music")
    async def resume(ctx):
        if ctx.voice_client.is_paused():
            ctx.voice_client.resume()
            await ctx.send("Music resumed.")
        else:
            await ctx.send("The music is not paused.")

    @bot.hybrid_command(description="Stop the music and clear the queue")
    async def stop(ctx):
        if ctx.voice_client.is_playing():
            ctx.voice_client.stop()
        songs.clear()
        await ctx.send("Music stopped and queue cleared.")

    @bot.hybrid_command(description="Skip the current song")
    async def skip(ctx):
        if ctx.voice_client.is_playing():
            ctx.voice_client.stop()
            await ctx.send("Skipped the current song.")
        else:
            await ctx.send("No music is playing.")

    @bot.hybrid_command(description="Shuffle the queue")
    async def volume(ctx, volume: int):
        if ctx.voice_client is None:
            return await ctx.send("Not connected to a voice channel.")
        ctx.voice_client.source.volume = volume / 100
        await ctx.send(f"Changed volume to {volume}%")

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

        @discord.ui.button(label='', style=discord.ButtonStyle.primary, emoji='⏯️')
        async def pause_resume_button(self, button: discord.ui.Button, interaction: discord.Interaction):
            if self.ctx.voice_client.is_playing():
                self.ctx.voice_client.pause()
                await interaction.response.send_message("Music paused.", ephemeral=True)
            elif self.ctx.voice_client.is_paused():
                self.ctx.voice_client.resume()
                await interaction.response.send_message("Music resumed.", ephemeral=True)
            else:
                await interaction.response.send_message("No music is playing.", ephemeral=True)


        @discord.ui.button(label='', style=discord.ButtonStyle.primary, emoji='⏭️')
        async def skip_button(self, button: discord.ui.Button, interaction: discord.Interaction):
            if self.ctx.voice_client.is_playing():
                self.ctx.voice_client.stop()
                await interaction.response.send_message("Skipped current song.", ephemeral=True)
                await play_next(self.ctx)
            else:
                await interaction.response.send_message("No music is playing.", ephemeral=True)

        @discord.ui.button(label='', style=discord.ButtonStyle.primary, emoji='⏹️')
        async def stop_button(self, button: discord.ui.Button, interaction: discord.Interaction):
            global current_song
            self.ctx.voice_client.stop()
            songs.clear()
            current_song = None
            await interaction.response.send_message("Music stopped and queue cleared.", ephemeral=True)

        @discord.ui.button(label='', style=discord.ButtonStyle.primary, emoji='🔀')
        async def shuffle_button(self, button: discord.ui.Button, interaction: discord.Interaction):
            if len(songs) > 1:
                random.shuffle(songs)
                await interaction.response.send_message("Queue shuffled.", ephemeral=True)
            else:
                await interaction.response.send_message("Not enough songs in queue to shuffle.", ephemeral=True)

        @discord.ui.button(label='', style=discord.ButtonStyle.secondary, emoji='🔊')
        async def volume_up_button(self, button: discord.ui.Button, interaction: discord.Interaction):
            if self.ctx.voice_client.source.volume < 1.0:
                self.ctx.voice_client.source.volume += 0.1
                await interaction.response.send_message(f"Volume increased to {int(self.ctx.voice_client.source.volume * 100)}%", ephemeral=True)
            else:
                await interaction.response.send_message("Volume is already at maximum.", ephemeral=True)

        @discord.ui.button(label='', style=discord.ButtonStyle.secondary, emoji='🔉')
        async def volume_down_button(self, button: discord.ui.Button, interaction: discord.Interaction):
            if self.ctx.voice_client.source.volume > 0.0:
                self.ctx.voice_client.source.volume -= 0.1
                await interaction.response.send_message(f"Volume decreased to {int(self.ctx.voice_client.source.volume * 100)}%", ephemeral=True)
            else:
                await interaction.response.send_message("Volume is already at minimum.", ephemeral=True)

        async def interaction_check(self, interaction: discord.Interaction) -> bool:
            return interaction.user == self.ctx.author

    def create_music_panel(title, requester, duration,channel, channel_avatar):
        embed = discord.Embed(title="MUSIC PANEL", color=discord.Color.blue())
        embed.add_field(name="🎵", value=title, inline=False)
        embed.add_field(name="Requested By", value=requester.mention, inline=True)
        embed.add_field(name="Duration", value=f"{duration//60}m {duration%60}s", inline=True)
        embed.add_field(name="Author", value=channel, inline=True) 
        embed.set_thumbnail(url=channel_avatar)
        return embed

    @bot.hybrid_command(description="Show the music queue")
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
                    player = await YTDLSource.from_url(song, loop=ctx.bot.loop, stream=True)
                    embed.add_field(name=f"Song {i}:", value=player.title, inline=False)
                except Exception as e:
                    embed.add_field(name=f"Song {i}:", value=f"Error fetching song info: {str(e)}", inline=False)

            view = MusicControlView(ctx)
            await ctx.send(embed=embed, view=view)
        else:
            await ctx.send("No music is currently playing and the queue is empty.")
    @play.before_invoke
    @join.before_invoke
    async def ensure_voice(ctx):
        if ctx.voice_client is None:
            if ctx.author.voice:
                await ctx.author.voice.channel.connect()
            else:
                await ctx.send("You are not connected to a voice channel.")
                raise commands.CommandError("Author not connected to a voice channel.")