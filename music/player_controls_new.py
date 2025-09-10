import discord
import lavalink
from typing import Dict, List, Tuple, Callable, Optional
import random
import logging

from .utils import format_duration

logger = logging.getLogger(__name__)


class PlayerControls(discord.ui.View):
    """Enhanced music player controls with persistent queue support."""
    
    def __init__(
        self,
        player: lavalink.DefaultPlayer,
        queue_store=None,
        get_prefs_func: Callable | None = None,
        apply_eq_func: Callable | None = None,
        eq_presets: Dict[str, List[Tuple[int, float]]] | None = None,
    ):
        super().__init__(timeout=None)
        self.player = player
        self.queue_store = queue_store
        self.get_prefs = get_prefs_func
        self.apply_equalizer = apply_eq_func
        self.eq_presets = eq_presets or {}
        self.update_buttons()

    def update_buttons(self):
        """Update button labels and emojis based on current state."""
        # Custom emojis
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

        # Pause/Resume
        self.pause_resume.label = "Resume" if self.player.paused else "Pause"
        try:
            self.pause_resume.emoji = E['play'] if self.player.paused else E['pause']
        except Exception:
            pass

        # Loop label - get from queue store if available
        if self.queue_store:
            try:
                guild_data = self.queue_store.get_guild(self.player.guild_id)
                loop_state = guild_data.get('loop', 0)
            except Exception:
                loop_state = 0
        else:
            loop_state = self.player.fetch('loop') or 0
            
        loop_map = {0: "Loop", 1: "Track", 2: "Queue"}
        self.loop.label = loop_map.get(int(loop_state), "Loop")
        try:
            self.loop.emoji = E['loop']
        except Exception:
            pass

        # Static emojis for other buttons
        try:
            self.skip.emoji = E['skip']
            self.back.emoji = E['prev']
            self.stop_callback.emoji = E['stop']
            self.shuffle.emoji = E['shuffle']
            self.playlist.emoji = E['playlist']
            self.restart.emoji = E['restart']
            self.vol_down.emoji = E['vol_down']
            self.vol_up.emoji = E['vol_up']
        except Exception:
            pass

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        """Check if user can interact with the controls."""
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

    async def update_embed_and_view(self, interaction: discord.Interaction, success_msg: str = None):
        """Update the embed with current track info and refresh the view."""
        try:
            if not self.queue_store:
                await interaction.response.edit_message(view=self)
                return

            # Get current track and queue info
            guild_id = interaction.guild.id
            current_index = self.queue_store.get_index(guild_id)
            queue = self.queue_store.get_queue(guild_id)
            guild_data = self.queue_store.get_guild(guild_id)
            
            # Update the embed if message has one
            if interaction.message and interaction.message.embeds:
                embed = interaction.message.embeds[0]
                
                # Update volume field if present
                try:
                    vol = int(self.player.fetch('volume') or 70)
                    for i, field in enumerate(embed.fields):
                        if field.name == "Volume":
                            embed.set_field_at(i, name="Volume", value=f"{vol}%", inline=field.inline)
                        elif field.name == "Position in Queue":
                            queue_length = len(queue)
                            position_text = f"{current_index + 1} / {queue_length}" if queue_length > 0 else "0 / 0"
                            embed.set_field_at(i, name="Position in Queue", value=position_text, inline=field.inline)
                        elif field.name == "Loop Mode":
                            loop_mode = guild_data.get('loop', 0)
                            loop_icons = {0: "➡️ Off", 1: "🔂 Track", 2: "🔁 Queue"}
                            embed.set_field_at(i, name="Loop Mode", value=loop_icons.get(loop_mode, "Off"), inline=field.inline)
                except Exception as e:
                    logger.error(f"[PlayerControls] Error updating embed fields: {e}")
                
                self.update_buttons()
                
                if success_msg:
                    await interaction.response.send_message(success_msg, ephemeral=True)
                    await interaction.edit_original_response(embed=embed, view=self)
                else:
                    await interaction.response.edit_message(embed=embed, view=self)
            else:
                self.update_buttons()
                if success_msg:
                    await interaction.response.send_message(success_msg, ephemeral=True)
                else:
                    await interaction.response.edit_message(view=self)
                    
        except Exception as e:
            logger.error(f"[PlayerControls] Error updating embed and view: {e}")
            try:
                if success_msg:
                    await interaction.response.send_message(success_msg, ephemeral=True)
                else:
                    await interaction.response.send_message("Action completed.", ephemeral=True)
            except:
                pass

    @discord.ui.button(label="Pause", style=discord.ButtonStyle.secondary, row=0)
    async def pause_resume(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Toggle pause/resume."""
        try:
            await self.player.set_pause(not self.player.paused)
            action = "Resumed" if not self.player.paused else "Paused"
            await self.update_embed_and_view(interaction, f"🎵 {action} the music.")
            logger.info(f"[PlayerControls] {action} music for guild {interaction.guild.id}")
        except Exception as e:
            logger.error(f"[PlayerControls] Error in pause/resume for guild {interaction.guild.id}: {e}")
            await interaction.response.send_message("Error toggling pause/resume.", ephemeral=True)

    @discord.ui.button(label="Skip", style=discord.ButtonStyle.primary, row=0)
    async def skip(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Skip to next track."""
        try:
            if not self.queue_store:
                await interaction.response.send_message("Queue system not available.", ephemeral=True)
                return

            guild_id = interaction.guild.id
            guild_data = self.queue_store.get_guild(guild_id)
            current_index = guild_data.get('index', 0)
            queue = self.queue_store.get_queue(guild_id)
            loop_mode = guild_data.get('loop', 0)
            
            # Calculate next index (skip always moves forward, even in track loop)
            if current_index + 1 < len(queue):
                next_index = current_index + 1
            elif loop_mode == 2:  # Queue loop
                next_index = 0
            else:
                await interaction.response.send_message("No next track to skip to.", ephemeral=True)
                return
            
            # Set new index and play track
            self.queue_store.set_index(guild_id, next_index)
            
            # Play the track at new index
            current_track = self.queue_store.current_track(guild_id)
            if current_track:
                res = await self.player.node.get_tracks(current_track.get('uri'))
                if res and res.tracks:
                    track = res.tracks[0]
                    track.requester = current_track.get('requester')
                    await self.player.play(track)
                    
                    await self.update_embed_and_view(interaction, "⏭️ Skipped to next track.")
                    logger.info(f"[PlayerControls] Skipped to track at index {next_index} for guild {guild_id}")
                else:
                    await interaction.response.send_message("Error loading next track.", ephemeral=True)
            else:
                await interaction.response.send_message("No track found at next position.", ephemeral=True)
                
        except Exception as e:
            logger.error(f"[PlayerControls] Error in skip for guild {interaction.guild.id}: {e}")
            await interaction.response.send_message("Error skipping track.", ephemeral=True)

    @discord.ui.button(label="Back", style=discord.ButtonStyle.secondary, row=0)
    async def back(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Go to previous track."""
        try:
            if not self.queue_store:
                await interaction.response.send_message("Queue system not available.", ephemeral=True)
                return

            guild_id = interaction.guild.id
            guild_data = self.queue_store.get_guild(guild_id)
            current_index = guild_data.get('index', 0)
            queue = self.queue_store.get_queue(guild_id)
            
            # Calculate previous index
            if current_index > 0:
                prev_index = current_index - 1
            elif len(queue) > 0:
                # Go to last track if at beginning
                prev_index = len(queue) - 1
            else:
                await interaction.response.send_message("No previous track.", ephemeral=True)
                return
            
            # Set new index and play track
            self.queue_store.set_index(guild_id, prev_index)
            
            # Play the track at new index
            current_track = self.queue_store.current_track(guild_id)
            if current_track:
                res = await self.player.node.get_tracks(current_track.get('uri'))
                if res and res.tracks:
                    track = res.tracks[0]
                    track.requester = current_track.get('requester')
                    await self.player.play(track)
                    
                    await self.update_embed_and_view(interaction, "⏮️ Went back to previous track.")
                    logger.info(f"[PlayerControls] Went back to track at index {prev_index} for guild {guild_id}")
                else:
                    await interaction.response.send_message("Error loading previous track.", ephemeral=True)
            else:
                await interaction.response.send_message("No track found at previous position.", ephemeral=True)
                
        except Exception as e:
            logger.error(f"[PlayerControls] Error in back for guild {interaction.guild.id}: {e}")
            await interaction.response.send_message("Error going back.", ephemeral=True)

    @discord.ui.button(label="Down", style=discord.ButtonStyle.secondary, row=0)
    async def vol_down(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Decrease volume."""
        try:
            current = int(self.player.fetch('volume') or 100)
            new_vol = max(0, current - 10)
            await self.player.set_volume(new_vol)
            
            # Update stored preferences
            self.player.store('volume', new_vol)
            if self.get_prefs:
                prefs = self.get_prefs(interaction.guild.id)
                prefs['volume'] = new_vol
            
            await self.update_embed_and_view(interaction, f"🔉 Volume decreased to {new_vol}%")
            logger.info(f"[PlayerControls] Volume decreased to {new_vol}% for guild {interaction.guild.id}")
            
        except Exception as e:
            logger.error(f"[PlayerControls] Error decreasing volume for guild {interaction.guild.id}: {e}")
            await interaction.response.send_message("Error adjusting volume.", ephemeral=True)

    @discord.ui.button(label="Up", style=discord.ButtonStyle.secondary, row=0)
    async def vol_up(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Increase volume."""
        try:
            current = int(self.player.fetch('volume') or 100)
            new_vol = min(1000, current + 10)
            await self.player.set_volume(new_vol)
            
            # Update stored preferences
            self.player.store('volume', new_vol)
            if self.get_prefs:
                prefs = self.get_prefs(interaction.guild.id)
                prefs['volume'] = new_vol
            
            await self.update_embed_and_view(interaction, f"🔊 Volume increased to {new_vol}%")
            logger.info(f"[PlayerControls] Volume increased to {new_vol}% for guild {interaction.guild.id}")
            
        except Exception as e:
            logger.error(f"[PlayerControls] Error increasing volume for guild {interaction.guild.id}: {e}")
            await interaction.response.send_message("Error adjusting volume.", ephemeral=True)

    @discord.ui.button(label="Stop", style=discord.ButtonStyle.danger, row=1)
    async def stop_callback(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Stop playback and disconnect."""
        try:
            if interaction.guild.voice_client:
                await interaction.guild.voice_client.disconnect(force=True)
                
                # Reset preferences and clear queue
                if self.get_prefs:
                    prefs = self.get_prefs(interaction.guild.id)
                    prefs['volume'] = 70
                    
                if self.queue_store:
                    self.queue_store.clear_guild(interaction.guild.id)
                    
                self.player.store('volume', 70)
            
            try:
                await interaction.message.delete()
            except discord.NotFound:
                pass
            
            self.stop()
            logger.info(f"[PlayerControls] Stopped and disconnected for guild {interaction.guild.id}")
            
        except Exception as e:
            logger.error(f"[PlayerControls] Error stopping for guild {interaction.guild.id}: {e}")
            await interaction.response.send_message("Error stopping playback.", ephemeral=True)

    @discord.ui.button(label="Loop", style=discord.ButtonStyle.secondary, row=1)
    async def loop(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Toggle loop mode."""
        try:
            if not self.queue_store:
                # Fallback to player storage
                cur = self.player.fetch('loop') or 0
                cur = (int(cur) + 1) % 3
                self.player.store('loop', cur)
            else:
                guild_data = self.queue_store.get_guild(interaction.guild.id)
                cur = guild_data.get('loop', 0)
                cur = (int(cur) + 1) % 3
                self.queue_store.set_guild_prop(interaction.guild.id, 'loop', cur)
            
            loop_map = {0: "➡️ Off", 1: "🔂 Track", 2: "🔁 Queue"}
            await self.update_embed_and_view(interaction, f"🔄 Loop mode: {loop_map[cur]}")
            logger.info(f"[PlayerControls] Loop mode changed to {cur} for guild {interaction.guild.id}")
            
        except Exception as e:
            logger.error(f"[PlayerControls] Error changing loop mode for guild {interaction.guild.id}: {e}")
            await interaction.response.send_message("Error changing loop mode.", ephemeral=True)

    @discord.ui.button(label="Restart", style=discord.ButtonStyle.secondary, row=1)
    async def restart(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Restart current track."""
        try:
            await self.player.seek(0)
            await interaction.response.send_message("🔄 Restarted current track.", ephemeral=True)
            logger.info(f"[PlayerControls] Restarted track for guild {interaction.guild.id}")
        except Exception as e:
            logger.error(f"[PlayerControls] Error restarting track for guild {interaction.guild.id}: {e}")
            await interaction.response.send_message("Error restarting track.", ephemeral=True)

    @discord.ui.button(label="Shuffle", style=discord.ButtonStyle.secondary, row=1)
    async def shuffle(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Shuffle the queue."""
        try:
            if not self.queue_store:
                await interaction.response.send_message("Queue system not available.", ephemeral=True)
                return

            guild_id = interaction.guild.id
            queue = self.queue_store.get_queue(guild_id)
            
            if len(queue) < 2:
                await interaction.response.send_message("Need at least 2 tracks to shuffle.", ephemeral=True)
                return
            
            # Get current track to preserve it
            current_index = self.queue_store.get_index(guild_id)
            current_track = None
            if 0 <= current_index < len(queue):
                current_track = queue[current_index]
            
            # Shuffle the queue
            random.shuffle(queue)
            
            # If there was a current track, move it to the front and update index
            if current_track:
                if current_track in queue:
                    queue.remove(current_track)
                queue.insert(0, current_track)
                self.queue_store.set_index(guild_id, 0)
            
            # Save shuffled queue using the new method
            self.queue_store.set_queue(guild_id, queue)
            
            await self.update_embed_and_view(interaction, "🔀 Queue shuffled!")
            logger.info(f"[PlayerControls] Shuffled queue for guild {guild_id}")
            
        except Exception as e:
            logger.error(f"[PlayerControls] Error shuffling queue for guild {interaction.guild.id}: {e}")
            await interaction.response.send_message("Error shuffling queue.", ephemeral=True)

    @discord.ui.button(label="Queue", style=discord.ButtonStyle.secondary, row=1)
    async def playlist(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Show current queue with pagination."""
        try:
            if not self.queue_store:
                await interaction.response.send_message("Queue system not available.", ephemeral=True)
                return

            guild_id = interaction.guild.id
            queue = self.queue_store.get_queue(guild_id)
            current_index = self.queue_store.get_index(guild_id)
            
            if not queue:
                await interaction.response.send_message("Queue is empty.", ephemeral=True)
                return
            
            # Show current page (around current playing track)
            items_per_page = 10
            current_page = current_index // items_per_page
            start_index = current_page * items_per_page
            end_index = min(start_index + items_per_page, len(queue))
            
            queue_list = ""
            for i in range(start_index, end_index):
                track = queue[i]
                # Add marker for currently playing track
                marker = "<:bolt:1415190820658745415> " if i == current_index else ""
                queue_list += f"`{i + 1}.` {marker}`[{format_duration(track.get('duration'))}]` {track.get('title')}\n"
            
            pages = max(1, -(-len(queue) // items_per_page))
            
            embed = discord.Embed(
                title="🎵 Current Queue", 
                description=queue_list, 
                color=discord.Color.blue()
            )
            embed.set_footer(text=f"Page {current_page + 1}/{pages} | Total: {len(queue)} | Current: {current_index + 1}")
            
            await interaction.response.send_message(embed=embed, ephemeral=True)
            
        except Exception as e:
            logger.error(f"[PlayerControls] Error showing queue for guild {interaction.guild.id}: {e}")
            await interaction.response.send_message("Error retrieving queue.", ephemeral=True)
