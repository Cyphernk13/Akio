# music/music.py
import discord
from discord.ext import commands
import wavelink
import asyncio
import typing
from datetime import timedelta
import random

# --- Global Dictionaries for State Management ---
music_queues = {}
loop_modes = {}

def get_queue(guild_id: int) -> list:
    """Gets the music queue for a given guild."""
    return music_queues.setdefault(guild_id, [])

def get_loop_mode(guild_id: int) -> str:
    """Gets the loop mode for a given guild."""
    return loop_modes.setdefault(guild_id, 'NONE')

def format_duration(seconds: int) -> str:
    """Formats seconds into a HH:MM:SS or MM:SS string."""
    td = timedelta(seconds=seconds)
    minutes, seconds = divmod(td.seconds, 60)
    hours, minutes = divmod(minutes, 60)
    if td.days > 0 or hours > 0:
        return f"{hours:02}:{minutes:02}:{seconds:02}"
    else:
        return f"{minutes:02}:{seconds:02}"

# --- UI Views ---

class PlayerControls(discord.ui.View):
    """A view with music player controls, now usable by anyone in the VC."""
    def __init__(self, player: wavelink.Player, ctx: commands.Context):
        super().__init__(timeout=None)
        self.player = player
        self.ctx = ctx
        self.update_buttons()

    def update_buttons(self):
        """Updates the state of the buttons based on the player's state."""
        self.pause_resume.label = "Resume" if self.player.is_paused() else "Pause"
        self.loop.label = f"Loop: {get_loop_mode(self.ctx.guild.id).capitalize()}"

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        """Check if the user is in the same voice channel as the bot."""
        if not interaction.user.voice or interaction.user.voice.channel != self.player.channel:
            await interaction.response.send_message("You must be in the same voice channel to use controls.", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="Pause", style=discord.ButtonStyle.secondary, emoji="⏯️")
    async def pause_resume(self, interaction: discord.Interaction, button: discord.ui.Button):
        # --- FIX 1: Use separate pause() and resume() methods ---
        if self.player.is_paused():
            await self.player.resume()
        else:
            await self.player.pause()
        
        self.update_buttons()
        await interaction.response.edit_message(view=self)

    @discord.ui.button(label="Skip", style=discord.ButtonStyle.primary, emoji="⏭️")
    async def skip(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.player.stop()
        # Ephemeral response to avoid channel spam
        try:
            await interaction.response.send_message("Skipped the song.", ephemeral=True)
        except discord.NotFound:
            pass # Interaction might have expired, which is fine

    @discord.ui.button(label="Stop", style=discord.ButtonStyle.danger, emoji="⏹️")
    async def stop_callback(self, interaction: discord.Interaction, button: discord.ui.Button):
        # --- FIX 2: Renamed function to stop_callback to avoid name conflict ---
        get_queue(self.ctx.guild.id).clear()
        await self.player.disconnect()
        
        # Using try/except to prevent an error if the message was already deleted
        try:
            await interaction.message.delete()
        except discord.NotFound:
            pass
        
        self.stop() # This now correctly calls the View's stop method
        
    @discord.ui.button(label="Loop: Off", style=discord.ButtonStyle.secondary, emoji="🔁")
    async def loop(self, interaction: discord.Interaction, button: discord.ui.Button):
        current_mode = get_loop_mode(self.ctx.guild.id)
        if current_mode == 'NONE':
            loop_modes[self.ctx.guild.id] = 'TRACK'
        elif current_mode == 'TRACK':
            loop_modes[self.ctx.guild.id] = 'QUEUE'
        else:
            loop_modes[self.ctx.guild.id] = 'NONE'
        
        self.update_buttons()
        await interaction.response.edit_message(view=self)


class TrackSelect(discord.ui.Select):
    """A select menu for choosing a track from search results."""
    def __init__(self, tracks: list[wavelink.Playable]):
        options = [
            discord.SelectOption(
                label=f"{track.title[:95]}...",
                description=f"by {track.author} | {format_duration(track.duration // 1000)}",
                value=str(i)
            ) for i, track in enumerate(tracks[:25])
        ]
        super().__init__(placeholder="Choose a song...", min_values=1, max_values=1, options=options)
        self.tracks = tracks
        self.chosen_track = None

    async def callback(self, interaction: discord.Interaction):
        self.chosen_track = self.tracks[int(self.values[0])]
        self.view.stop()
        await interaction.response.defer()

def setup(bot):

    # --- Helper Function for Playback ---
    async def start_playback(ctx: commands.Context, player: wavelink.Player):
        """Starts playback and sends the 'Now Playing' message."""
        queue = get_queue(ctx.guild.id)
        if not queue:
            await asyncio.sleep(120)
            if not player.is_playing() and player.is_connected():
                 await player.disconnect()
            return
        
        track: wavelink.Playable = queue.pop(0)
        await player.play(track)

        player.bound_channel = ctx.channel
        
        requester = track.requester if hasattr(track, 'requester') else bot.user

        embed = discord.Embed(
            title="<a:Milk10:1399578671941156996> Now Playing",
            description=f"**[{track.title}]({track.uri})**\nby {track.author}",
            color=discord.Color.green()
        )
        embed.set_thumbnail(url=track.thumbnail)
        embed.add_field(name="Duration", value=format_duration(track.duration // 1000))
        embed.set_footer(text=f"Requested by {requester.display_name}", icon_url=requester.avatar.url)

        await ctx.send(embed=embed, view=PlayerControls(player, ctx))

    # --- Bot Events ---
    @bot.event
    async def on_wavelink_track_end(payload: wavelink.TrackEventPayload):
        """Handles auto-play and looping when a track ends."""
        player = payload.player
        if not player:
            return

        guild_id = player.guild.id
        queue = get_queue(guild_id)
        loop_mode = get_loop_mode(guild_id)

        if loop_mode == 'TRACK':
            queue.insert(0, payload.track)
        elif loop_mode == 'QUEUE':
            queue.append(payload.track)
            
        if hasattr(player, 'bound_channel') and player.bound_channel:
            class DummyCtx:
                def __init__(self, guild, channel):
                    self.guild = guild
                    self.channel = channel
                    self.send = channel.send
            
            await start_playback(DummyCtx(player.guild, player.bound_channel), player)

    # --- Music Commands ---
    
    @bot.hybrid_command(name="play", description="Play a song or add to the queue")
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def play(ctx: commands.Context, *, query: str):
        if not ctx.author.voice:
            return await ctx.send(embed=discord.Embed(description="You must be in a voice channel to play music.", color=discord.Color.red()))

        player: wavelink.Player = ctx.voice_client
        if not player:
            try:
                player = await ctx.author.voice.channel.connect(cls=wavelink.Player)
            except Exception as e:
                return await ctx.send(embed=discord.Embed(description=f"Failed to connect to the voice channel: {e}", color=discord.Color.red()))

        await player.set_volume(50)
        await ctx.defer()
        
        try:
            tracks = await wavelink.YouTubeTrack.search(query)
            if not tracks:
                return await ctx.send(embed=discord.Embed(description=f"❌ No results found for `{query}`.", color=discord.Color.red()))
        except Exception as e:
            return await ctx.send(embed=discord.Embed(description=f"An error occurred while searching: {e}", color=discord.Color.red()))
        
        queue = get_queue(ctx.guild.id)
        
        if isinstance(tracks, wavelink.Playlist):
            for track in tracks.tracks:
                track.requester = ctx.author
            
            added = len(tracks.tracks)
            queue.extend(tracks.tracks)
            embed = discord.Embed(
                title="📜 Playlist Added",
                description=f"Added **{added}** songs from **{tracks.name}** to the queue.",
                color=discord.Color.purple()
            )
            await ctx.send(embed=embed)
        else:
            track_to_add = None
            if len(tracks) > 1:
                view = discord.ui.View(timeout=60)
                select_menu = TrackSelect(tracks)
                view.add_item(select_menu)
                msg = await ctx.send("🔎 **Found multiple tracks, please choose one:**", view=view)
                await view.wait()
                await msg.delete()
                
                track_to_add = select_menu.chosen_track
                if not track_to_add:
                    return await ctx.send(embed=discord.Embed(description="Selection timed out.", color=discord.Color.orange()))
            else:
                track_to_add = tracks[0]

            track_to_add.requester = ctx.author
            queue.append(track_to_add)
            embed = discord.Embed(
                description=f"<a:verify:1399579399107379271> Added **[{track_to_add.title}]({track_to_add.uri})** to the queue.",
                color=discord.Color.og_blurple()
            )
            await ctx.send(embed=embed)

        if not player.is_playing():
            player.bound_channel = ctx.channel
            await start_playback(ctx, player)

    @bot.hybrid_command(name="queue", description="Shows the current music queue")
    async def queue(ctx: commands.Context, page: int = 1):
        queue = get_queue(ctx.guild.id)
        if not queue:
            return await ctx.send(embed=discord.Embed(description="The queue is empty.", color=discord.Color.orange()))

        items_per_page = 10
        pages = -(-len(queue) // items_per_page)
        if not 1 <= page <= pages:
            return await ctx.send(embed=discord.Embed(description=f"Invalid page number. Please choose between 1 and {pages}.", color=discord.Color.red()))

        start_index = (page - 1) * items_per_page
        end_index = start_index + items_per_page
        
        queue_list = ""
        for i, track in enumerate(queue[start_index:end_index], start=start_index + 1):
            queue_list += f"`{i}.` `[{format_duration(track.duration // 1000)}]` {track.title}\n"
        
        embed = discord.Embed(title="<a:Milk10:1399578671941156996> Music Queue", description=queue_list, color=discord.Color.blue())
        embed.set_footer(text=f"Page {page}/{pages} | Total songs: {len(queue)}")
        
        player: wavelink.Player = ctx.voice_client
        if player and player.current:
            embed.add_field(name="Now Playing", value=f"**[{player.current.title}]({player.current.uri})**", inline=False)
            
        await ctx.send(embed=embed)


    @bot.hybrid_command(name="nowplaying", aliases=["np"], description="Shows the currently playing song")
    async def nowplaying(ctx: commands.Context):
        player: wavelink.Player = ctx.voice_client
        if not player or not player.current:
            return await ctx.send(embed=discord.Embed(description="Nothing is currently playing.", color=discord.Color.orange()))

        track = player.current
        position = player.position // 1000
        duration = track.duration // 1000
        
        progress = int((position / duration) * 20) if duration > 0 else 0
        progress_bar = f"[`{format_duration(position)}`] {'▬' * progress}🔵{'▬' * (20 - progress)} [`{format_duration(duration)}`]"
        
        requester = track.requester if hasattr(track, 'requester') else ctx.author
        
        embed = discord.Embed(title="<a:Milk10:1399578671941156996> Now Playing", description=f"**[{track.title}]({track.uri})** by {track.author}", color=discord.Color.green())
        embed.set_thumbnail(url=track.thumbnail)
        embed.add_field(name="Progress", value=progress_bar, inline=False)
        embed.set_footer(text=f"Requested by {requester.display_name}", icon_url=requester.avatar.url)
        
        await ctx.send(embed=embed, view=PlayerControls(player, ctx))

    @bot.hybrid_command(name="loop", description="Toggle loop mode (Off, Track, Queue)")
    async def loop(ctx: commands.Context):
        current_mode = get_loop_mode(ctx.guild.id)
        if current_mode == 'NONE':
            next_mode, emoji, description = 'TRACK', '🔂', "Looping the current **track**."
        elif current_mode == 'TRACK':
            next_mode, emoji, description = 'QUEUE', '🔁', "Looping the entire **queue**."
        else:
            next_mode, emoji, description = 'NONE', '➡️', "Looping is now **off**."
            
        loop_modes[ctx.guild.id] = next_mode
        embed = discord.Embed(description=f"{emoji} {description}", color=discord.Color.blue())
        await ctx.send(embed=embed)


    @bot.hybrid_command(name="shuffle", description="Shuffles the queue")
    async def shuffle(ctx: commands.Context):
        queue = get_queue(ctx.guild.id)
        if not queue:
            return await ctx.send(embed=discord.Embed(description="The queue is empty, nothing to shuffle.", color=discord.Color.orange()))
        
        random.shuffle(queue)
        embed = discord.Embed(description="🔀 The queue has been shuffled!", color=discord.Color.random())
        await ctx.send(embed=embed)


    @bot.hybrid_command(name="remove", description="Removes a song from the queue")
    async def remove(ctx: commands.Context, index: int):
        queue = get_queue(ctx.guild.id)
        if not queue:
            return await ctx.send(embed=discord.Embed(description="The queue is empty.", color=discord.Color.orange()))
        
        if not 1 <= index <= len(queue):
            return await ctx.send(embed=discord.Embed(description=f"Invalid index. Please provide a number between 1 and {len(queue)}.", color=discord.Color.red()))
        
        removed_track = queue.pop(index - 1)
        embed = discord.Embed(description=f"<:Sage_Trash:1399580044531339356> Removed **{removed_track.title}** from the queue.", color=discord.Color.green())
        await ctx.send(embed=embed)


    @bot.hybrid_command(name="disconnect", aliases=["leave"], description="Disconnects the bot and clears the queue")
    async def disconnect(ctx: commands.Context):
        player: wavelink.Player = ctx.voice_client
        if not player:
            return await ctx.send(embed=discord.Embed(description="I'm not connected to any voice channel.", color=discord.Color.orange()))
        
        get_queue(ctx.guild.id).clear()
        loop_modes.pop(ctx.guild.id, None)
        await player.disconnect()
        
        embed = discord.Embed(description="<:MomijiWave:1399580630207168606> Disconnected and cleared the queue. See you next time!", color=discord.Color.blue())
        await ctx.send(embed=embed)

    @bot.hybrid_command(name="volume", description="Set the player volume (0-100)")
    async def volume(ctx, volume: commands.Range[int, 0, 100]):
        player: wavelink.Player = ctx.voice_client
        if not player:
            return await ctx.send("Not connected to a voice channel.")
            
        await player.set_volume(volume)
        await ctx.send(f"🔊 Volume set to **{volume}%**")
        
    @bot.hybrid_command(name="skip", description="Skip the current song")
    async def skip(ctx):
        player: wavelink.Player = ctx.voice_client
        if not player or not player.is_playing():
            return await ctx.send("Nothing is playing to skip.")
        await player.stop()
        await ctx.send("⏭️ Skipped the current song.")

    @bot.hybrid_command(name="pause", description="Pause the music")
    async def pause(ctx):
        player: wavelink.Player = ctx.voice_client
        if not player or not player.is_playing():
            return await ctx.send("Nothing is playing to pause.")
        # --- FIX 1: Use separate pause() method ---
        await player.pause()
        await ctx.send("⏯️ Paused.")

    @bot.hybrid_command(name="resume", description="Resume the music")
    async def resume(ctx):
        player: wavelink.Player = ctx.voice_client
        if not player or not player.is_paused():
            return await ctx.send("Music is not paused.")
        # --- FIX 1: Use separate resume() method ---
        await player.resume()
        await ctx.send("▶️ Resumed.")