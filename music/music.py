# music/music.py
import discord
from discord.ext import commands
import lavalink
import asyncio
from datetime import timedelta
import re

# Import the custom voice client from its dedicated file
from .lavalink_client import LavalinkVoiceClient

URL_REGEX = re.compile(r'https?://(?:www\.)?.+')

def format_duration(milliseconds: int) -> str:
    """Formats milliseconds into a HH:MM:SS or MM:SS string."""
    if milliseconds is None:
        return 'N/A'
    seconds = milliseconds / 1000
    td = timedelta(seconds=seconds)
    minutes, seconds = divmod(td.seconds, 60)
    hours, minutes = divmod(minutes, 60)
    if td.days > 0 or hours > 0:
        return f"{hours:02}:{minutes:02}:{int(seconds):02}"
    else:
        return f"{minutes:02}:{int(seconds):02}"

class PlayerControls(discord.ui.View):
    """A view with music player controls."""
    def __init__(self, player: lavalink.DefaultPlayer):
        super().__init__(timeout=None)
        self.player = player
        self.update_buttons()

    def update_buttons(self):
        """Updates the state of the buttons based on the player's state."""
        self.pause_resume.label = "Resume" if self.player.paused else "Pause"
        loop_map = {0: "Off", 1: "Track", 2: "Queue"}
        self.loop.label = f"Loop: {loop_map.get(self.player.loop, 'Off')}"

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        """A robust check to ensure the user is in the same voice channel as the bot."""
        if not interaction.user.voice:
            await interaction.response.send_message("You must be in a voice channel.", ephemeral=True)
            return False
        if not interaction.guild.voice_client:
            await interaction.response.send_message("I'm not connected to a voice channel.", ephemeral=True)
            return False
        if interaction.user.voice.channel.id != interaction.guild.voice_client.channel.id:
            await interaction.response.send_message("You must be in the same voice channel as me.", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="Pause", style=discord.ButtonStyle.secondary, emoji="⏯️")
    async def pause_resume(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.player.set_pause(not self.player.paused)
        self.update_buttons()
        await interaction.response.edit_message(view=self)

    @discord.ui.button(label="Skip", style=discord.ButtonStyle.primary, emoji="⏭️")
    async def skip(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.player.skip()
        await interaction.response.send_message("Skipped the song.", ephemeral=True)

    @discord.ui.button(label="Stop", style=discord.ButtonStyle.danger, emoji="⏹️")
    async def stop_callback(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.guild.voice_client:
            await interaction.guild.voice_client.disconnect(force=True)
        try:
            await interaction.message.delete()
        except discord.NotFound:
            pass
        self.stop()

    @discord.ui.button(label="Loop: Off", style=discord.ButtonStyle.secondary, emoji="🔁")
    async def loop(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.player.loop = (self.player.loop + 1) % 3
        self.update_buttons()
        await interaction.response.edit_message(view=self)

class TrackSelect(discord.ui.Select):
    """A select menu for choosing a track from search results."""
    def __init__(self, tracks: list[lavalink.AudioTrack]):
        options = [
            discord.SelectOption(
                label=track.title[:100],
                description=f"by {track.author} | {format_duration(track.duration)}",
                value=str(i)
            ) for i, track in enumerate(tracks[:25])
        ]
        super().__init__(placeholder="Choose a song...", options=options)
        self.tracks = tracks
        self.chosen_track = None

    async def callback(self, interaction: discord.Interaction):
        self.chosen_track = self.tracks[int(self.values[0])]
        self.view.stop()
        await interaction.response.defer()

def setup(bot: commands.Bot):

    # --- New Central Playback Function ---
    async def start_playback(ctx: commands.Context, player: lavalink.DefaultPlayer):
        """Handles popping tracks from the queue and sending 'Now Playing' messages."""
        # Delete the old "Now Playing" message if it exists
        old_message_id = player.fetch('message_id')
        if old_message_id:
            try:
                old_message = await ctx.channel.fetch_message(old_message_id)
                await old_message.delete()
            except discord.NotFound:
                pass

        if not player.queue and player.loop != 1:
            await asyncio.sleep(120)
            if player.is_connected and not player.is_playing:
                await ctx.voice_client.disconnect(force=True)
            return

        track = None
        if player.loop == 1 and player.current:
            track = player.current
        else:
            track = player.queue.pop(0)

        if player.loop == 2: # Loop queue
            player.queue.append(track)
        
        await player.play(track)
        
        requester = ctx.guild.get_member(track.requester)
        embed = discord.Embed(
            title="<a:Milk10:1399578671941156996> Now Playing",
            description=f"**[{track.title}]({track.uri})**\nby {track.author}",
            color=discord.Color.green()
        )
        if track.artwork_url:
            embed.set_thumbnail(url=track.artwork_url)
        embed.add_field(name="Duration", value=format_duration(track.duration))
        if requester:
            embed.set_footer(text=f"Requested by {requester.display_name}", icon_url=requester.avatar.url)

        message = await ctx.channel.send(embed=embed, view=PlayerControls(player))
        player.store('message_id', message.id)

    @lavalink.listener(lavalink.TrackEndEvent)
    async def on_track_end(event: lavalink.TrackEndEvent):
        player = event.player
        guild = bot.get_guild(player.guild_id)
        channel = bot.get_channel(player.fetch('channel'))

        if guild and channel:
            # Create a dummy context to pass to the playback function
            class DummyCtx:
                def __init__(self, guild, channel, voice_client):
                    self.guild = guild
                    self.channel = channel
                    self.voice_client = voice_client
            
            await start_playback(DummyCtx(guild, channel, guild.voice_client), player)
    
    @bot.hybrid_command(name="play", description="Play a song or add to the queue")
    async def play(ctx: commands.Context, *, query: str):
        if not ctx.author.voice or not ctx.author.voice.channel:
            return await ctx.send("You must be in a voice channel.", ephemeral=True)

        player = bot.lavalink.player_manager.create(ctx.guild.id)
        player.store('channel', ctx.channel.id)
        
        if not ctx.voice_client:
            await ctx.author.voice.channel.connect(cls=LavalinkVoiceClient)
        elif ctx.voice_client.channel.id != ctx.author.voice.channel.id:
            return await ctx.send("You must be in the same voice channel as me.", ephemeral=True)

        await ctx.defer()
        
        query = query.strip('<>')
        if not URL_REGEX.match(query):
            query = f'ytsearch:{query}'
            
        results = await player.node.get_tracks(query)

        if not results or not results.tracks:
            return await ctx.send(embed=discord.Embed(description=f"❌ No results found for `{query}`.", color=discord.Color.red()))

        if results.load_type == lavalink.LoadType.PLAYLIST:
            tracks = results.tracks
            for track in tracks:
                track.requester = ctx.author.id
                player.add(track=track)
            embed = discord.Embed(title="📜 Playlist Added", description=f"Added **{len(tracks)}** songs from **{results.playlist_info.name}**.", color=discord.Color.purple())
            await ctx.send(embed=embed)
        else:
            track_to_add = None
            if len(results.tracks) > 1 and results.load_type == lavalink.LoadType.SEARCH:
                view = discord.ui.View(timeout=60)
                select_menu = TrackSelect(results.tracks)
                view.add_item(select_menu)
                msg = await ctx.send("🔎 **Found multiple tracks, please choose one:**", view=view)
                await view.wait()
                
                try:
                    await msg.delete()
                except discord.NotFound:
                    pass
                
                track_to_add = select_menu.chosen_track
                if not track_to_add:
                    return await ctx.send(embed=discord.Embed(description="Selection timed out.", color=discord.Color.orange()))
            else:
                track_to_add = results.tracks[0]

            track_to_add.requester = ctx.author.id
            player.add(track=track_to_add)
            embed = discord.Embed(description=f"<a:verify:1399579399107379271> Added **[{track_to_add.title}]({track_to_add.uri})** to the queue.", color=discord.Color.og_blurple())
            await ctx.send(embed=embed)

        if not player.is_playing:
            await start_playback(ctx, player)

    @bot.hybrid_command(name="queue", description="Shows the current music queue")
    async def queue(ctx: commands.Context, page: int = 1):
        player = bot.lavalink.player_manager.get(ctx.guild.id)
        
        if not player or not player.queue:
            return await ctx.send(embed=discord.Embed(description="The queue is empty.", color=discord.Color.orange()))

        items_per_page = 10
        pages = -(-len(player.queue) // items_per_page)
        if not 1 <= page <= pages:
            return await ctx.send(embed=discord.Embed(description=f"Invalid page number. Please choose between 1 and {pages}.", color=discord.Color.red()))

        start_index = (page - 1) * items_per_page
        end_index = start_index + items_per_page
        
        queue_list = ""
        for i, track in enumerate(player.queue[start_index:end_index], start=start_index + 1):
            queue_list += f"`{i}.` `[{format_duration(track.duration)}]` {track.title}\n"
        
        embed = discord.Embed(title="<a:Milk10:1399578671941156996> Music Queue", description=queue_list, color=discord.Color.blue())
        embed.set_footer(text=f"Page {page}/{pages} | Total songs: {len(player.queue)}")
        
        if player.current:
            embed.add_field(name="Now Playing", value=f"**[{player.current.title}]({player.current.uri})**", inline=False)
            
        await ctx.send(embed=embed)


    @bot.hybrid_command(name="nowplaying", aliases=["np"], description="Shows the currently playing song")
    async def nowplaying(ctx: commands.Context):
        player = bot.lavalink.player_manager.get(ctx.guild.id)

        if not player or not player.current:
            return await ctx.send(embed=discord.Embed(description="Nothing is currently playing.", color=discord.Color.orange()))

        track = player.current
        position = player.position
        duration = track.duration
        
        progress = int((position / duration) * 20) if duration > 0 else 0
        progress_bar = f"[`{format_duration(position)}`] {'▬' * progress}🔵{'▬' * (20 - progress)} [`{format_duration(duration)}`]"
        
        requester = ctx.guild.get_member(track.requester)

        embed = discord.Embed(title="<a:Milk10:1399578671941156996> Now Playing", description=f"**[{track.title}]({track.uri})** by {track.author}", color=discord.Color.green())
        if track.artwork_url:
            embed.set_thumbnail(url=track.artwork_url)
        embed.add_field(name="Progress", value=progress_bar, inline=False)
        if requester:
            embed.set_footer(text=f"Requested by {requester.display_name}", icon_url=requester.avatar.url)
        
        await ctx.send(embed=embed, view=PlayerControls(player))

    @bot.hybrid_command(name="loop", description="Toggle loop mode (Off, Track, Queue)")
    async def loop(ctx: commands.Context):
        player = bot.lavalink.player_manager.get(ctx.guild.id)
        if not player:
            return await ctx.send("I'm not playing anything.")

        player.loop = (player.loop + 1) % 3
        loop_map = {0: '➡️ Off', 1: '🔂 Track', 2: '🔁 Queue'}
        embed = discord.Embed(description=f"Looping is now **{loop_map[player.loop]}**.", color=discord.Color.blue())
        await ctx.send(embed=embed)


    @bot.hybrid_command(name="shuffle", description="Shuffles the queue")
    async def shuffle(ctx: commands.Context):
        player = bot.lavalink.player_manager.get(ctx.guild.id)
        if not player or not player.queue:
            return await ctx.send(embed=discord.Embed(description="The queue is empty.", color=discord.Color.orange()))
        
        player.shuffle = not player.shuffle
        
        desc = "🔀 The queue has been shuffled!" if player.shuffle else "▶️ The queue is no longer shuffled."
        embed = discord.Embed(description=desc, color=discord.Color.random())
        await ctx.send(embed=embed)


    @bot.hybrid_command(name="remove", description="Removes a song from the queue")
    async def remove(ctx: commands.Context, index: int):
        player = bot.lavalink.player_manager.get(ctx.guild.id)
        if not player or not player.queue:
            return await ctx.send(embed=discord.Embed(description="The queue is empty.", color=discord.Color.orange()))
        
        if not 1 <= index <= len(player.queue):
            return await ctx.send(embed=discord.Embed(description=f"Invalid index. Please provide a number between 1 and {len(player.queue)}.", color=discord.Color.red()))
        
        removed_track = player.queue.pop(index - 1)
        embed = discord.Embed(description=f"<:Sage_Trash:1399578671941156996> Removed **{removed_track.title}** from the queue.", color=discord.Color.green())
        await ctx.send(embed=embed)


    @bot.hybrid_command(name="disconnect", aliases=["leave"], description="Disconnects the bot and clears the queue")
    async def disconnect(ctx: commands.Context):
        if not ctx.voice_client:
            return await ctx.send(embed=discord.Embed(description="I'm not connected to any voice channel.", color=discord.Color.orange()))
        
        await ctx.voice_client.disconnect(force=True)
        
        embed = discord.Embed(description="<:MomijiWave:1399580630207168606> Disconnected and cleared the queue.", color=discord.Color.blue())
        await ctx.send(embed=embed)

    @bot.hybrid_command(name="volume", description="Set the player volume (0-1000)")
    async def volume(ctx: commands.Context, volume: commands.Range[int, 0, 1000]):
        player = bot.lavalink.player_manager.get(ctx.guild.id)
        if not player:
            return await ctx.send("Not connected to a voice channel.")
            
        await player.set_volume(volume)
        await ctx.send(f"🔊 Volume set to **{volume}%**")
        
    @bot.hybrid_command(name="skip", description="Skip the current song")
    async def skip(ctx: commands.Context):
        player = bot.lavalink.player_manager.get(ctx.guild.id)
        if not player or not player.is_playing:
            return await ctx.send("Nothing is playing to skip.")
        await player.skip()
        await ctx.send("⏭️ Skipped the current song.")

    @bot.hybrid_command(name="pause", description="Pause the music")
    async def pause(ctx: commands.Context):
        player = bot.lavalink.player_manager.get(ctx.guild.id)
        if not player or not player.is_playing:
            return await ctx.send("Nothing is playing to pause.")
        
        await player.set_pause(True)
        await ctx.send("⏯️ Paused.")

    @bot.hybrid_command(name="resume", description="Resume the music")
    async def resume(ctx: commands.Context):
        player = bot.lavalink.player_manager.get(ctx.guild.id)
        if not player:
            return await ctx.send("Not connected.")
        
        if player.paused:
            await player.set_pause(False)
            await ctx.send("▶️ Resumed.")
        else:
            await ctx.send("Music is not paused.")
