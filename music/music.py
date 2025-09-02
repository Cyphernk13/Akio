# music/music.py
import discord
from discord.ext import commands
import lavalink
import asyncio
from datetime import timedelta
import re
from typing import Dict, List, Optional, Tuple

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
    def __init__(self, player: lavalink.DefaultPlayer, get_prefs_func=None, apply_eq_func=None, eq_presets: Dict[str, List[Tuple[int, float]]] | None = None):
        super().__init__(timeout=None)
        self.player = player
        self.get_prefs = get_prefs_func
        self.apply_equalizer = apply_eq_func
        self.eq_presets = eq_presets or {}
        self.update_buttons()

    def update_buttons(self):
        """Updates the state of the buttons based on the player's state."""
        # Custom emoji set
        E = {
            'pause': '<:pause:1412529948861665491>',
            'play': '<:play:1412530216965767349>',
            'skip': '<:skip:1412530943121555546>',
            'prev': '<:prev:1412530972779352214>',
            'vol_up': '<:vol_up:1412531098474512556>',
            'vol_down': '<:vol_down:1412531122348232704>',
            'loop': '<:loop:1412531198147952832>',
            'playlist': '<:playlist:1412531317186498580>',
            'stop': '<:stop:1412531800592613406>',
            'shuffle': '<:shuffle:1412532183750676532>',
            'restart': '<:restart:1412545166161481818>',
        }

        # Pause/Resume label and emoji
        self.pause_resume.label = "Resume" if self.player.paused else "Pause"
        try:
            self.pause_resume.emoji = E['play'] if self.player.paused else E['pause']
        except Exception:
            pass

        # Loop label (no "Off" text)
        loop_map = {0: "Loop", 1: "Track", 2: "Queue"}
        self.loop.label = loop_map.get(self.player.loop, "Loop")
        try:
            self.loop.emoji = E['loop']
        except Exception:
            pass

        # Volume labels and emojis
        try:
            vol = int(self.player.fetch('volume') or 100)
        except Exception:
            vol = 100
        vol = max(0, min(1000, vol))
        if hasattr(self, 'vol_down'):
            self.vol_down.label = "Down"
            try:
                self.vol_down.emoji = E['vol_down']
            except Exception:
                pass
        if hasattr(self, 'vol_up'):
            self.vol_up.label = "Up"
            try:
                self.vol_up.emoji = E['vol_up']
            except Exception:
                pass

        # Static button emojis
        try:
            self.skip.emoji = E['skip']
            self.back.emoji = E['prev']
            self.stop_callback.emoji = E['stop']
            self.shuffle.emoji = E['shuffle']
            self.playlist.emoji = E['playlist']
            if hasattr(self, 'restart'):
                self.restart.emoji = E['restart']
        except Exception:
            pass

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

    @discord.ui.button(label="Pause", style=discord.ButtonStyle.secondary, emoji="⏸️", row=0)
    async def pause_resume(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.player.set_pause(not self.player.paused)
        self.update_buttons()
        await interaction.response.edit_message(view=self)

    @discord.ui.button(label="Skip", style=discord.ButtonStyle.primary, emoji="⏭️", row=0)
    async def skip(self, interaction: discord.Interaction, button: discord.ui.Button):
        # If loop is off and the next track is identical to current, drop it to avoid double playback
        try:
            current = self.player.current
            if current and getattr(self.player, 'loop', 0) == 0 and self.player.queue:
                nxt = self.player.queue[0]
                if getattr(nxt, 'identifier', None) == getattr(current, 'identifier', None):
                    self.player.queue.pop(0)
        except Exception:
            pass
        await self.player.skip()
        await interaction.response.send_message("Skipped the song.", ephemeral=True)

    @discord.ui.button(label="Stop", style=discord.ButtonStyle.danger, emoji="⏹️", row=1)
    async def stop_callback(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.guild.voice_client:
            await interaction.guild.voice_client.disconnect(force=True)
            # Reset volume to default on manual stop
            try:
                if self.get_prefs:
                    prefs = self.get_prefs(interaction.guild.id)
                    prefs['volume'] = 70
                self.player.store('volume', 70)
            except Exception:
                pass
        try:
            await interaction.message.delete()
        except discord.NotFound:
            pass
        self.stop()

    @discord.ui.button(label="Loop", style=discord.ButtonStyle.secondary, emoji="🔁", row=1)
    async def loop(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.player.loop = (self.player.loop + 1) % 3
        self.update_buttons()
        await interaction.response.edit_message(view=self)

    @discord.ui.button(label="Down", style=discord.ButtonStyle.secondary, emoji="🔉", row=0)
    async def vol_down(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            current = int(self.player.fetch('volume') or 100)
        except Exception:
            current = 100
        new_vol = max(0, current - 10)
        await self.player.set_volume(new_vol)
        try:
            self.player.store('volume', new_vol)
            if self.get_prefs:
                prefs = self.get_prefs(interaction.guild.id)
                prefs['volume'] = new_vol
        except Exception:
            pass
        self.update_buttons()
        # Update panel embed Volume field live
        try:
            msg = interaction.message
            if msg and msg.embeds:
                embed = msg.embeds[0]
                for i, field in enumerate(embed.fields):
                    if field.name == "Volume":
                        embed.set_field_at(i, name="Volume", value=f"{new_vol}%", inline=field.inline)
                        break
                await interaction.response.edit_message(embed=embed, view=self)
            else:
                await interaction.response.edit_message(view=self)
        except Exception:
            await interaction.response.edit_message(view=self)

    @discord.ui.button(label="Up", style=discord.ButtonStyle.secondary, emoji="🔊", row=0)
    async def vol_up(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            current = int(self.player.fetch('volume') or 100)
        except Exception:
            current = 100
        new_vol = min(1000, current + 10)
        await self.player.set_volume(new_vol)
        try:
            self.player.store('volume', new_vol)
            if self.get_prefs:
                prefs = self.get_prefs(interaction.guild.id)
                prefs['volume'] = new_vol
        except Exception:
            pass
        self.update_buttons()
        # Update panel embed Volume field live
        try:
            msg = interaction.message
            if msg and msg.embeds:
                embed = msg.embeds[0]
                for i, field in enumerate(embed.fields):
                    if field.name == "Volume":
                        embed.set_field_at(i, name="Volume", value=f"{new_vol}%", inline=field.inline)
                        break
                await interaction.response.edit_message(embed=embed, view=self)
            else:
                await interaction.response.edit_message(view=self)
        except Exception:
            await interaction.response.edit_message(view=self)

    # Bass button removed; bass-boost is on by default via preferences

    @discord.ui.button(label="Restart", style=discord.ButtonStyle.secondary, emoji="▶️", row=1)
    async def restart(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            await self.player.seek(0)
            await interaction.response.send_message("Restarted track.", ephemeral=True)
        except Exception:
            await interaction.response.send_message("Couldn't restart.", ephemeral=True)

    @discord.ui.button(label="Back", style=discord.ButtonStyle.secondary, emoji="⏮️", row=0)
    async def back(self, interaction: discord.Interaction, button: discord.ui.Button):
        history = self.player.fetch('history') or []
        if not history:
            return await interaction.response.send_message("No previous track.", ephemeral=True)
        prev = history.pop()
        try:
            self.player.store('history', history)
        except Exception:
            pass
        try:
            current = self.player.current
            if current:
                self.player.queue.insert(0, current)
        except Exception:
            pass
        await self.player.play(prev)
        await interaction.response.defer()

    @discord.ui.button(label="Shuffle", style=discord.ButtonStyle.secondary, emoji="🔀", row=1)
    async def shuffle(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            self.player.shuffle = not getattr(self.player, 'shuffle', False)
        except Exception:
            self.player.shuffle = not False
        await interaction.response.send_message("Toggled shuffle.", ephemeral=True)

    @discord.ui.button(label="Playlist", style=discord.ButtonStyle.secondary, emoji="🧾", row=1)
    async def playlist(self, interaction: discord.Interaction, button: discord.ui.Button):
        q = self.player.queue
        if not q:
            return await interaction.response.send_message("Queue is empty.", ephemeral=True)
        items = []
        for i, t in enumerate(q[:10], start=1):
            items.append(f"`{i}.` [{t.title}]({t.uri}) — `{format_duration(t.duration)}`")
        embed = discord.Embed(title="Music Queue", description="\n".join(items), color=discord.Color.blurple())
        await interaction.response.send_message(embed=embed, ephemeral=True)

    

def setup(bot: commands.Bot):
    # Playback lock per guild to serialize queue/play transitions and avoid races
    playback_locks: Dict[int, asyncio.Lock] = {}

    def get_lock(guild_id: int) -> asyncio.Lock:
        lock = playback_locks.get(guild_id)
        if not lock:
            lock = asyncio.Lock()
            playback_locks[guild_id] = lock
        return lock

    # Per-guild audio preferences (volume, EQ preset, autoplay)
    audio_prefs: Dict[int, Dict] = {}

    def get_prefs(guild_id: int) -> Dict:
        if guild_id not in audio_prefs:
            audio_prefs[guild_id] = {
                'volume': 70,  # comfortable default
                'eq_preset': 'bass-boost',  # keep bass on by default
                'autoplay': False,
            }
        return audio_prefs[guild_id]

    # Equalizer preset definitions (15 bands: 0..14), gains in range [-0.25, +1.0] typically
    EQ_PRESETS: Dict[str, List[Tuple[int, float]]] = {
        'flat': [(i, 0.0) for i in range(15)],
        'soft': [(i, -0.05) for i in range(15)],  # slight reduction overall
        'bass-boost': [
            (0, 0.30), (1, 0.25), (2, 0.20), (3, 0.10), (4, 0.05),
            (5, 0.00), (6, 0.00), (7, 0.00), (8, 0.00), (9, 0.00),
            (10, -0.02), (11, -0.04), (12, -0.05), (13, -0.05), (14, -0.05)
        ],
        'vocal-boost': [
            (0, -0.05), (1, -0.05), (2, -0.02), (3, 0.00), (4, 0.10),
            (5, 0.15), (6, 0.18), (7, 0.15), (8, 0.10), (9, 0.05),
            (10, 0.00), (11, -0.02), (12, -0.02), (13, -0.03), (14, -0.03)
        ],
        'treble-cut': [
            (0, 0.00), (1, 0.00), (2, 0.00), (3, 0.00), (4, 0.00),
            (5, -0.05), (6, -0.08), (7, -0.10), (8, -0.12), (9, -0.15),
            (10, -0.18), (11, -0.20), (12, -0.20), (13, -0.20), (14, -0.20)
        ],
    }

    async def apply_equalizer(player: lavalink.DefaultPlayer, bands_tuples: List[Tuple[int, float]]):
        """Try multiple APIs to apply EQ depending on lavalink.py version."""
        # Convert tuples to the structure various APIs expect
        bands_dicts = [{'band': b, 'gain': g} for b, g in bands_tuples]
        try:
            # v5+ possible API
            if hasattr(lavalink, 'Filters') and hasattr(player, 'set_filters'):
                filters = lavalink.Filters()
                # Some versions use property, others a method
                try:
                    filters.equalizer = bands_dicts
                except Exception:
                    # fall back in case different structure needed
                    pass
                await player.set_filters(filters)
                return
        except Exception as e:
            print(f"[Music] set_filters equalizer failed: {e}")

        try:
            # Older API: set_gains(*[(band, gain), ...])
            if hasattr(player, 'set_gains'):
                await player.set_gains(*bands_tuples)
                return
        except Exception as e:
            print(f"[Music] set_gains failed: {e}")

        try:
            # Older API: equalizer([{band, gain}, ...])
            if hasattr(player, 'equalizer'):
                await player.equalizer(bands_dicts)  # type: ignore
                return
        except Exception as e:
            print(f"[Music] equalizer() failed: {e}")

    # --- New 'Now Playing' Sender ---
    async def delete_old_np_message(player: lavalink.DefaultPlayer):
        """Safely delete the previous 'Now Playing' message if it exists."""
        old_message_id = player.fetch('message_id')
        channel_id = player.fetch('channel')
        if not old_message_id or not channel_id:
            return
        try:
            channel = bot.get_channel(channel_id) or await bot.fetch_channel(channel_id)
            old_message = await channel.fetch_message(old_message_id)
            await old_message.delete()
        except (discord.NotFound, discord.Forbidden, AttributeError):
            pass
        finally:
            player.store('message_id', None)

    async def send_now_playing_embed(player: lavalink.DefaultPlayer, event_track: lavalink.AudioTrack | None = None):
        """Creates and sends the 'Now Playing' embed."""
        # Ensure we have a channel to send in
        channel_id = player.fetch('channel')
        if not channel_id:
            print(f"[Music] NP aborted: no text channel stored for guild {getattr(player, 'guild_id', 'unknown')}")
            return

        # Clean up any previous NP message
        await delete_old_np_message(player)

        try:
            channel = bot.get_channel(channel_id) or await bot.fetch_channel(channel_id)
        except (discord.NotFound, discord.Forbidden) as e:
            print(f"[Music] NP aborted: cannot access channel {channel_id}: {e}")
            return

        track = event_track or player.current
        if not track:
            print(f"[Music] NP aborted: no current track for guild {channel.guild.id}; player.is_playing={player.is_playing} queue_len={len(player.queue)}")
            return

        requester = channel.guild.get_member(getattr(track, 'requester', 0))
        embed = discord.Embed(
            title="MUSIC PANEL",
            description=f"<a:Milk10:1399578671941156996> **[{track.title}]({track.uri})**",
            color=discord.Color.blurple()
        )
        if getattr(track, 'artwork_url', None):
            embed.set_thumbnail(url=track.artwork_url)
        # Show current volume instead of duplicating the requester (already in footer)
        try:
            vol = int(player.fetch('volume') or 70)
        except Exception:
            vol = 70
        embed.add_field(name="Volume", value=f"{vol}%")
        embed.add_field(name="Music Duration", value=format_duration(track.duration))
        embed.add_field(name="Music Author", value=getattr(track, 'author', 'Unknown'))
        if requester:
            avatar_url = requester.display_avatar.url
            embed.set_footer(text=f"Requested by {requester.display_name}", icon_url=avatar_url)

        try:
            message = await channel.send(embed=embed, view=PlayerControls(player, get_prefs_func=get_prefs, apply_eq_func=apply_equalizer, eq_presets=EQ_PRESETS))
            player.store('message_id', message.id)
            print(f"[Music] NP sent: guild={channel.guild.id}, channel={channel.id}, message_id={message.id}, track={track.title}")
        except Exception as e:
            # Log the failure to help diagnose in case the channel is invalid or missing perms
            print(f"Failed to send Now Playing embed in guild {channel.guild.id} channel {channel.id}: {e}")

    # --- Use TrackStartEvent for 'Now Playing' messages ---
    async def lavalink_event_hook(event):
        event_name = type(event).__name__
        # Track Start
        if event_name == 'TrackStartEvent':
            player = getattr(event, 'player', None)
            if not player:
                return
            print(f"[Music] TrackStartEvent received: guild={player.guild_id}, track_id={getattr(getattr(event, 'track', None), 'identifier', 'unknown')} title={getattr(getattr(event, 'track', None), 'title', 'unknown')}")
            await asyncio.sleep(0.25)
            track = getattr(event, 'track', None)
            print(f"[Music] After delay: player.current is {'present' if player.current else 'missing'}; event.track is {'present' if track else 'missing'}")
            # Apply preferred volume and EQ per guild on track start (bass-boost by default)
            try:
                prefs = get_prefs(player.guild_id)
                await player.set_volume(int(prefs.get('volume', 70)))
                try:
                    player.store('volume', int(prefs.get('volume', 70)))
                except Exception:
                    pass
                preset = prefs.get('eq_preset', 'bass-boost')
                bands = EQ_PRESETS.get(preset)
                if bands:
                    await apply_equalizer(player, bands)
                try:
                    player.store('eq_preset', preset)
                except Exception:
                    pass
            except Exception as e:
                print(f"[Music] Failed to apply volume/EQ on start: {e}")
            await send_now_playing_embed(player, track)
            return

        # Track End
        if event_name == 'TrackEndEvent':
            player = getattr(event, 'player', None)
            if not player:
                return
            reason = str(getattr(event, 'reason', 'unknown')).lower()
            print(f"[Music] TrackEndEvent: guild={player.guild_id}, reason={reason}, queue_len={len(player.queue)} current={'present' if player.current else 'missing'}")
            await delete_old_np_message(player)
            # Serialize end-handling to avoid races with play command
            lock = get_lock(player.guild_id)
            async with lock:
                # Handle only relevant reasons; ignore manual stop/replace
                if reason in { 'replaced', 'stopped' }:
                    return
                # Loop logic
                try:
                    just_played = getattr(event, 'track', None)
                except Exception:
                    just_played = None

                # Maintain simple history stack
                try:
                    if just_played:
                        hist = player.fetch('history') or []
                        hist.append(just_played)
                        if len(hist) > 25:
                            hist = hist[-25:]
                        player.store('history', hist)
                except Exception:
                    pass

                try:
                    if player.loop == 1:  # Track loop (replay same without queuing duplicates)
                        if just_played:
                            await player.play(just_played)
                            return
                    elif player.loop == 2:  # Queue loop (append just played to end once)
                        if just_played:
                            # Append just played track back to end, avoid immediate duplicate at head
                            try:
                                if not player.queue or getattr(player.queue[-1], 'identifier', None) != getattr(just_played, 'identifier', None):
                                    player.queue.append(just_played)
                            except Exception:
                                pass
                    else:
                        # Loop off: if the next track equals just_played, drop it to prevent double-play
                        try:
                            if player.queue and just_played and getattr(player.queue[0], 'identifier', None) == getattr(just_played, 'identifier', None):
                                player.queue.pop(0)
                        except Exception:
                            pass
                        # Play next available (either next in queue or the just appended)
                        if (not player.is_playing) and (player.current is None):
                            next_track = None
                            if player.queue:
                                next_track = player.queue.pop(0)
                            elif just_played:
                                next_track = just_played
                            if next_track:
                                await player.play(next_track)
                                return

                    # No loop; natural finish -> advance
                    if reason == 'finished' and (not player.is_playing) and (player.current is None):
                        if player.queue:
                            next_track = player.queue.pop(0)
                            print(f"[Music] Auto-advancing to next track: id={getattr(next_track, 'identifier', 'unknown')} title={getattr(next_track, 'title', 'unknown')}")
                            await player.play(next_track)
                        else:
                            print(f"[Music] Queue empty; scheduling disconnect if idle")
                            await asyncio.sleep(120)
                            if player.is_connected and not player.is_playing:
                                try:
                                    guild = bot.get_guild(player.guild_id)
                                    if guild and guild.voice_client:
                                        await guild.voice_client.disconnect(force=True)
                                        try:
                                            # Reset volume to default after disconnect
                                            prefs = get_prefs(player.guild_id)
                                            prefs['volume'] = 70
                                            player.store('volume', 70)
                                        except Exception:
                                            pass
                                except Exception:
                                    pass
                except Exception as e:
                    print(f"[Music] Error during TrackEnd handling: {e}")

            return

        # Track Stuck or Exception -> skip to next gracefully
        if event_name in { 'TrackStuckEvent', 'TrackExceptionEvent' }:
            player = getattr(event, 'player', None)
            if not player:
                return
            print(f"[Music] {event_name}: guild={player.guild_id}; attempting to skip to next")
            lock = get_lock(player.guild_id)
            async with lock:
                try:
                    if player.queue:
                        await player.play(player.queue.pop(0))
                    else:
                        # Try to restart the same track once (stuck)
                        track = getattr(event, 'track', None)
                        if track:
                            try:
                                await player.play(track)
                            except Exception:
                                pass
                except Exception as e:
                    print(f"[Music] Failed to recover from {event_name}: {e}")
            return

        # Queue ended event (if emitted by library)
        if event_name == 'QueueEndEvent':
            player = getattr(event, 'player', None)
            if not player:
                return
            print(f"[Music] QueueEndEvent: guild={player.guild_id}; scheduling idle disconnect")
            await asyncio.sleep(120)
            if player.is_connected and not player.is_playing:
                try:
                    guild = bot.get_guild(player.guild_id)
                    if guild and guild.voice_client:
                        await guild.voice_client.disconnect(force=True)
                        try:
                            prefs = get_prefs(player.guild_id)
                            prefs['volume'] = 70
                            player.store('volume', 70)
                        except Exception:
                            pass
                except Exception:
                    pass
            return

    # Register a single event hook that filters by event type
    try:
        bot.lavalink.add_event_hook(lavalink_event_hook)
        print("[Music] Registered lavalink event hook")
    except Exception as e:
        print(f"[Music] Failed to register lavalink event hook: {e}")

    @bot.hybrid_command(name="play", description="Play a song or add to the queue")
    async def play(ctx: commands.Context, *, query: str):
        if not ctx.author.voice or not ctx.author.voice.channel:
            return await ctx.send("You must be in a voice channel.", ephemeral=True)

        player = bot.lavalink.player_manager.create(ctx.guild.id)
        player.store('channel', ctx.channel.id)
        try:
            print(f"[Music] Stored text channel {ctx.channel.id} for guild {ctx.guild.id}")
        except Exception:
            pass

        lock = get_lock(ctx.guild.id)
        async with lock:
            if not ctx.voice_client:
                await ctx.author.voice.channel.connect(cls=LavalinkVoiceClient)
            elif ctx.voice_client.channel.id != ctx.author.voice.channel.id:
                return await ctx.send("You must be in the same voice channel as me.", ephemeral=True)

            await ctx.defer()

            query = query.strip('<>')
            is_url = URL_REGEX.match(query) is not None
            search_q = query if is_url else f'ytsearch:{query}'

            temp_msg = await ctx.send(embed=discord.Embed(description="<:ZeroSip:1404982303180066856> Akio is thinking...", color=discord.Color.blurple()), delete_after=5)
            results = await player.node.get_tracks(search_q)

            if not results or not results.tracks:
                return await ctx.send(embed=discord.Embed(description=f"<:no:1404980370486722621> No results found for `{query}`.", color=discord.Color.red()))

            if results.load_type == lavalink.LoadType.PLAYLIST:
                tracks = results.tracks
                for track in tracks:
                    track.requester = ctx.author.id
                    player.add(track=track)
                embed = discord.Embed(title="<:playlist:1412531317186498580> Playlist Added", description=f"Added **{len(tracks)}** songs from **{results.playlist_info.name}**.", color=discord.Color.purple())
                await ctx.send(embed=embed)
            else:
                # Auto-choose the first track and play instantly
                chosen = results.tracks[0]
                chosen.requester = ctx.author.id
                player.add(track=chosen)
                await ctx.send(embed=discord.Embed(description=f"<a:verify:1399579399107379271> Added **[{chosen.title}]({chosen.uri})** to the queue.", color=discord.Color.green()), delete_after=6)

            # Start playback only if idle
            if not player.is_playing and not player.current and player.queue:
                await player.play(player.queue.pop(0))

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
        
        await ctx.send(embed=embed, view=PlayerControls(player, get_prefs_func=get_prefs, apply_eq_func=apply_equalizer, eq_presets=EQ_PRESETS))

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
        
        desc = "<:shuffle:1412532183750676532> The queue has been shuffled!" if player.shuffle else "<:play:1412530216965767349> The queue is no longer shuffled."
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
        # Reset volume to default on disconnect
        try:
            prefs = get_prefs(ctx.guild.id)
            prefs['volume'] = 70
            player = bot.lavalink.player_manager.get(ctx.guild.id)
            if player:
                player.store('volume', 70)
        except Exception:
            pass
        
        embed = discord.Embed(description="<:MomijiWave:1399580630207168606> Disconnected and cleared the queue.", color=discord.Color.blue())
        await ctx.send(embed=embed)

    @bot.hybrid_command(name="volume", description="Set the player volume (0-1000)")
    async def volume(ctx: commands.Context, volume: commands.Range[int, 0, 1000]):
        player = bot.lavalink.player_manager.get(ctx.guild.id)
        if not player:
            return await ctx.send("Not connected to a voice channel.")
        
        await player.set_volume(volume)
        # Update stored state for UI buttons and prefs
        prefs = get_prefs(ctx.guild.id)
        prefs['volume'] = int(volume)
        try:
            player.store('volume', int(volume))
        except Exception:
            pass
        # Try to update the latest NP panel Volume field if we can
        try:
            msg_id = player.fetch('message_id') if player else None
            channel_id = player.fetch('channel') if player else None
            if msg_id and channel_id:
                channel = bot.get_channel(channel_id) or await bot.fetch_channel(channel_id)
                msg = await channel.fetch_message(msg_id)
                if msg and msg.embeds:
                    embed = msg.embeds[0]
                    for i, field in enumerate(embed.fields):
                        if field.name == "Volume":
                            embed.set_field_at(i, name="Volume", value=f"{volume}%", inline=field.inline)
                            break
                    await msg.edit(embed=embed)
        except Exception:
            pass
        await ctx.send(f"<:speaker:1412542837198950511> Volume set to **{volume}%**")

    # Removed normalize/eq commands; use player UI buttons for volume and bass
        
    @bot.hybrid_command(name="skip", description="Skip the current song")
    async def skip(ctx: commands.Context):
        player = bot.lavalink.player_manager.get(ctx.guild.id)
        if not player or not player.is_playing:
            return await ctx.send("Nothing is playing to skip.")
        await player.skip()
        await ctx.send("<:skip:1412530943121555546> Skipped the current song.")

    @bot.hybrid_command(name="pause", description="Pause the music")
    async def pause(ctx: commands.Context):
        player = bot.lavalink.player_manager.get(ctx.guild.id)
        if not player or not player.is_playing:
            return await ctx.send("Nothing is playing to pause.")
        
        await player.set_pause(True)
        await ctx.send("<:pause:1412529948861665491> Paused.")

    @bot.hybrid_command(name="resume", description="Resume the music")
    async def resume(ctx: commands.Context):
        player = bot.lavalink.player_manager.get(ctx.guild.id)
        if not player:
            return await ctx.send("Not connected.")
        
        if player.paused:
            await player.set_pause(False)
            await ctx.send("<:play:1412530216965767349> Resumed.")
        else:
            await ctx.send("Music is not paused.")