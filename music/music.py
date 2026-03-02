"""Enhanced Music module with persistent queue and proper loop handling.

Features:
- Persistent JSON-based queue storage with current index tracking
- Proper loop modes: Track (1), Queue (2), Off (0)
- Pagination for queue display (10 tracks per page)
- Queue position markers and navigation
- Comprehensive error handling and logging
- Index-based queue operations without track removal
"""

import discord
from discord.ext import commands
import lavalink
import asyncio
import random
import logging
import os
from typing import Dict, List, Tuple, Optional

from .client import LavalinkVoiceClient
from .controls import PlayerControls
from .persistent_queue import PersistentQueue
from .utils import URL_REGEX, format_duration

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

#  Search quality improvements
SEARCH_ENHANCERS = [
    "official music video", "official audio", "lyrics", "hq", "high quality",
    "music video", "official", "hd", "original"
]


def setup(bot: commands.Bot):
    # YouTube-only mode (no Spotify/SoundCloud integrations).
    
    # Initialize persistent queue store
    queue_store = PersistentQueue()
    
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

    async def safe_player_operation(guild_id: int, operation_name: str, operation_func, *args, **kwargs):
        """Safely execute player operations with automatic node failover."""
        max_retries = 3
        for attempt in range(max_retries):
            try:
                player = bot.lavalink.player_manager.get(guild_id)
                if not player:
                    logger.warning(f"[SafeOp] No player found for guild {guild_id}")
                    return None
                
                # Test node health before operation
                if not player.node or not player.node.is_connected():
                    raise Exception("Node not connected")
                
                # Execute the operation
                result = await operation_func(player, *args, **kwargs)
                return result
                
            except Exception as e:
                logger.warning(f"[SafeOp] {operation_name} failed (attempt {attempt + 1}/{max_retries}): {e}")
                
                # Try to handle node failure and switch
                node_manager = getattr(bot, 'node_manager', None)
                if node_manager and attempt < max_retries - 1:
                    try:
                        # Mark current node as failed
                        if player and player.node:
                            await node_manager.handle_node_failure(player.node.identifier)
                        
                        # Wait a bit before retry
                        await asyncio.sleep(2 ** attempt)
                        
                        # Try to get a new player with better node
                        player = bot.lavalink.player_manager.create(guild_id)
                        if player:
                            logger.info(f"[SafeOp] Created new player for guild {guild_id} on attempt {attempt + 1}")
                    except Exception as recovery_error:
                        logger.error(f"[SafeOp] Recovery failed: {recovery_error}")
                
                if attempt == max_retries - 1:
                    logger.error(f"[SafeOp] {operation_name} failed after {max_retries} attempts")
                    raise e
        
        return None

    # Equalizer preset definitions (15 bands: 0..14), gains in range [-0.25, +1.0] typically
    EQ_PRESETS: Dict[str, List[Tuple[int, float]]] = {
        'flat': [(i, 0.0) for i in range(15)],
        'soft': [(i, -0.05) for i in range(15)],  # slight reduction overall
        'enhanced': [  # YouTube-like enhanced audio quality
            (0, 0.1), (1, 0.15), (2, 0.2), (3, 0.1), (4, 0.05),
            (5, 0.0), (6, 0.0), (7, 0.05), (8, 0.1), (9, 0.05),
            (10, 0.1), (11, 0.15), (12, 0.1), (13, 0.05), (14, 0.0)
        ],
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
            logger.error(f"[Music] set_filters equalizer failed: {e}")

        try:
            # Older API: set_gains(*[(band, gain), ...])
            if hasattr(player, 'set_gains'):
                await player.set_gains(*bands_tuples)
                return
        except Exception as e:
            logger.error(f"[Music] set_gains failed: {e}")

        try:
            # Older API: equalizer([{band, gain}, ...])
            if hasattr(player, 'equalizer'):
                await player.equalizer(bands_dicts)  # type: ignore
                return
        except Exception as e:
            logger.error(f"[Music] equalizer() failed: {e}")

    def enhance_search_query(query: str) -> str:
        """Normalize a user query for YouTube search without changing intent."""
        if URL_REGEX.match(query):
            return query
        return ' '.join(query.strip().split())

    def url_to_search_query(url: str) -> str:
        """Best-effort conversion of a URL into a human search query.

        Used to keep the `play` command behaving reasonably even if the user
        pastes a non-YouTube URL after switching providers to YouTube.
        """
        try:
            # Strip protocol and query params
            cleaned = url.split('?', 1)[0].split('#', 1)[0]
            # Keep last 1-2 path segments (often contains the title)
            parts = [p for p in cleaned.replace('\\', '/').split('/') if p]
            tail = ' '.join(parts[-2:]) if len(parts) >= 2 else (parts[-1] if parts else '')
            tail = tail.replace('-', ' ').replace('_', ' ')
            tail = ' '.join(tail.split())
            return tail.strip()
        except Exception:
            return ""

    def filter_youtube_for_official(tracks, query: str):
        """Smart filtering for YouTube to find official/best quality content."""
        if not tracks or len(tracks) <= 1:
            return tracks
            
        scored_tracks = []
        query_lower = query.lower()
        query_words = set(query_lower.split())
        
        for track in tracks:
            score = 0
            title_lower = track.title.lower()
            author_lower = getattr(track, 'author', '').lower()
            
            # 🏆 HIGH PRIORITY SCORING
            
            # Official indicators in author name (major boost)
            if any(indicator in author_lower for indicator in [
                'official', 'records', 'music', 'entertainment', 'label', 'vevo'
            ]):
                score += 100
                
            # Verified/popular account indicators
            if any(indicator in author_lower for indicator in [
                'verified', 'artist', 'band', 'singer'
            ]):
                score += 50
            
            # Title quality indicators
            if any(indicator in title_lower for indicator in [
                'official', 'original', 'single', 'album'
            ]):
                score += 40
                
            # 🎵 CONTENT MATCHING
            
            # Perfect author-title matching (likely official)
            if author_lower in title_lower or title_lower.startswith(author_lower):
                score += 60
                
            # Query word matching in author (artist name match)
            author_matches = sum(1 for word in query_words if word in author_lower and len(word) > 2)
            score += author_matches * 30
            
            # Query word matching in title
            title_matches = sum(1 for word in query_words if word in title_lower and len(word) > 2)
            score += title_matches * 15
            
            # Exact or close title matching
            if query_lower in title_lower:
                score += 35
            
            # 🚫 PENALTY SYSTEM - FIXED TO PRIORITIZE ORIGINAL CONTENT
            
            # SEVERE penalties for unwanted content (these should NEVER win)
            severe_penalties = [
                ('remix', -150), ('cover', -120), ('nightcore', -100),
                ('slowed', -100), ('reverb', -90), ('sped up', -90),
                ('8d audio', -80), ('bass boosted', -80), ('karaoke', -150),
                ('instrumental', -60), ('acoustic version', -50), 
                ('live version', -40), ('mashup', -100), ('bootleg', -120),
                ('edit', -80), ('unofficial', -100)
            ]
            
            for penalty_word, penalty_score in severe_penalties:
                if penalty_word in title_lower:
                    score += penalty_score
                    
            # Additional penalties for remix indicators in author names
            if any(word in author_lower for word in ['remix', 'edit', 'bootleg', 'cover']):
                score -= 100
                    
            # User upload indicators (penalty)
            if any(bad in author_lower for bad in ['user', 'upload', 'random', '123', 'dj']):
                score -= 30
                
            # Duration-based scoring (2-6 minutes is typical)
            duration_minutes = (track.duration or 0) / 60000
            if 2 <= duration_minutes <= 6:
                score += 20
            elif duration_minutes > 8:
                score -= 10  # Very long might be mix/compilation
                
            scored_tracks.append((track, score))
        
        # Sort by score (highest first)
        scored_tracks.sort(key=lambda x: x[1], reverse=True)
        
        # Log top candidates for debugging
        logger.info(f"[Music] 🎯 YouTube ranking for '{query}':")
        for i, (track, score) in enumerate(scored_tracks[:3]):
            logger.info(f"[Music]   {i+1}. [{score}pts] {track.author} - {track.title}")
        
        return [track for track, score in scored_tracks]



    YOUTUBE_DOMAINS = ('youtube.com', 'youtu.be', 'music.youtube.com')

    def is_youtube_url(url: str) -> bool:
        u = (url or '').lower()
        return any(d in u for d in YOUTUBE_DOMAINS)

    async def search_tracks(player: lavalink.DefaultPlayer, query: str, is_url: bool):
        """YouTube-only search.

        - URL: only YouTube URLs are accepted and loaded directly.
        - Text: one `ytsearch:` call; caller uses first result.
        """
        if is_url:
            if not is_youtube_url(query):
                return None
            return await player.node.get_tracks(query)

        normalized = enhance_search_query(query)
        if not normalized:
            return None
        return await player.node.get_tracks(f"ytsearch:{normalized}")

    async def apply_enhanced_audio_settings(player: lavalink.DefaultPlayer):
        """Apply enhanced audio settings for YouTube-like quality"""
        try:
            # Enhanced equalizer settings for richer sound
            # Frequencies: 25, 40, 63, 100, 160, 250, 400, 630, 1000, 1600, 2500, 4000, 6300, 10000, 16000
            enhanced_eq = [
                (0, 0.1),    # 25Hz - Sub bass boost
                (1, 0.15),   # 40Hz - Bass boost  
                (2, 0.2),    # 63Hz - Low bass
                (3, 0.1),    # 100Hz - Upper bass
                (4, 0.05),   # 160Hz - Low mids
                (5, 0.0),    # 250Hz - Mids (neutral)
                (6, 0.0),    # 400Hz - Upper mids
                (7, 0.05),   # 630Hz - Presence
                (8, 0.1),    # 1000Hz - Clarity
                (9, 0.05),   # 1600Hz - Definition
                (10, 0.1),   # 2500Hz - Brightness
                (11, 0.15),  # 4000Hz - Vocal clarity
                (12, 0.1),   # 6300Hz - Presence
                (13, 0.05),  # 10000Hz - Air
                (14, 0.0),   # 16000Hz - Sparkle
            ]
            
            # Apply enhanced equalizer
            await apply_equalizer(player, enhanced_eq)
            
            # Set optimal volume (75% for good dynamic range)
            await player.set_volume(75)
            
            logger.info(f"[Music] ✨ Applied enhanced audio settings for guild {player.guild_id}")
            
        except Exception as e:
            logger.error(f"[Music] Failed to apply enhanced audio settings: {e}")

    async def schedule_idle_disconnect(player: lavalink.DefaultPlayer, guild_id: int):
        """Schedule a gentle idle disconnect if no activity for reasonable time"""
        try:
            # Wait 10 minutes for new activity instead of 5 minutes (non-blocking)
            await asyncio.sleep(600)  
            
            # Check if still idle (not playing and no queue)
            if (player.is_connected and 
                not player.is_playing and 
                not player.current and 
                len(queue_store.get_queue(guild_id)) == 0):
                
                logger.info(f"[Music] Disconnecting idle player for guild {guild_id}")
                try:
                    guild = bot.get_guild(guild_id)
                    if guild and guild.voice_client:
                        await guild.voice_client.disconnect(force=True)
                        # Only clear queue on actual disconnect, not during normal operations
                        queue_store.clear_guild(guild_id)
                except Exception as e:
                    logger.error(f"[Music] Error during idle disconnect: {e}")
            else:
                logger.debug(f"[Music] Player still active for guild {guild_id}, skipping disconnect")
                
        except Exception as e:
            logger.error(f"[Music] Error in idle disconnect scheduler: {e}")

    # Track recovery intentionally removed for YouTube-only fast mode.

    async def play_track_at_index(player: lavalink.DefaultPlayer, guild_id: int) -> bool:
        """Play track at current index from persistent queue with enhanced retry mechanism."""
        current_track = queue_store.current_track(guild_id)
        if not current_track:
            logger.warning(f"[Music] No current track for guild {guild_id}")
            return False

        track_title = current_track.get('title', 'Unknown')
        track_uri = current_track.get('uri', '')
        
        # Strategy 1: Try direct URI first (works for YouTube URLs and any directly supported sources)
        if track_uri:
            try:
                res = await player.node.get_tracks(track_uri)
                if res and res.tracks:
                    track = res.tracks[0]
                    track.requester = current_track.get('requester')
                    await player.play(track)
                    player.store('current_track_info', current_track)
                    current_index = queue_store.get_index(guild_id)
                    logger.info(f"[Music] ✅ Playing direct track at index {current_index}: {track_title}")
                    return True
            except Exception as e:
                logger.warning(f"[Music] Direct URI failed for {track_title}: {e}")

        # Strategy 2: Re-resolve via YouTube search
        try:
            search_query = track_title
            if current_track.get('author'):
                search_query = f"{current_track.get('author')} {track_title}"
            
            logger.info(f"[Music] 🔍 Smart search for: {search_query}")
            
            # 🎯 SIMPLE SELECTION: YouTube search
            search_attempts = [
                ('ytsearch', 'YouTube'),
            ]
            logger.info(f"[Music] 🎵 YouTube search")
            
            for search_type, source_name in search_attempts:
                try:
                    search_result = await player.node.get_tracks(f"{search_type}:{search_query}")
                    
                    if search_result and search_result.tracks:
                        track = search_result.tracks[0]
                        track.requester = current_track.get('requester')
                        
                        # Play the track
                        await player.play(track)
                        
                        # Update the stored track with new working URI
                        current_track['uri'] = track.uri
                        queue_store.update_track(guild_id, queue_store.get_index(guild_id), current_track)
                        
                        player.store('current_track_info', current_track)
                        current_index = queue_store.get_index(guild_id)
                        logger.info(f"[Music] ✅ Playing track from {source_name} at index {current_index}: {track.title}")
                        return True
                        
                except Exception as e:
                    logger.debug(f"[Music] {source_name} search failed for {track_title}: {e}")
                    continue
                    
            logger.warning(f"[Music] ❌ All search sources failed for: {search_query}")
                
        except Exception as e:
            logger.error(f"[Music] Enhanced search failed for {track_title}: {e}")

        # Strategy 3: Final fallback - try direct URI one more time
        if track_uri:
            try:
                res = await player.node.get_tracks(track_uri)
                if res and res.tracks:
                    track = res.tracks[0]
                    track.requester = current_track.get('requester')
                    await player.play(track)
                    player.store('current_track_info', current_track)
                    logger.info(f"[Music] ✅ Playing fallback URI for: {track_title}")
                    return True
            except Exception as e:
                logger.error(f"[Music] Final URI attempt failed for {track_title}: {e}")

        # All strategies failed - skip to next track
        logger.error(f"[Music] ❌ All playback attempts failed for: {track_title}")
        return await skip_to_next(player, guild_id)

    async def skip_to_next(player: lavalink.DefaultPlayer, guild_id: int) -> bool:
        """Skip to next track based on current index and loop mode."""
        try:
            guild_data = queue_store.get_guild(guild_id)
            current_index = guild_data.get('index', 0)
            loop_mode = guild_data.get('loop', 0)
            queue = queue_store.get_queue(guild_id)
            
            logger.info(f"[Music] Skip request - Guild: {guild_id}, Current index: {current_index}, Loop mode: {loop_mode}, Queue length: {len(queue)}")
            
            # Calculate next index
            if loop_mode == 1:  # Track loop - move to next track anyway when skip is pressed
                next_index = current_index + 1
            elif current_index + 1 < len(queue):
                next_index = current_index + 1
            elif loop_mode == 2:  # Queue loop - go to beginning
                next_index = 0
            else:
                # No more tracks and no queue loop
                logger.info(f"[Music] No more tracks to skip to for guild {guild_id}")
                return False
            
            if 0 <= next_index < len(queue):
                queue_store.set_index(guild_id, next_index)
                return await play_track_at_index(player, guild_id)
            
        except Exception as e:
            logger.error(f"[Music] Error skipping to next track for guild {guild_id}: {e}")
        return False

    async def go_to_previous(player: lavalink.DefaultPlayer, guild_id: int) -> bool:
        """Go to previous track."""
        try:
            guild_data = queue_store.get_guild(guild_id)
            current_index = guild_data.get('index', 0)
            queue = queue_store.get_queue(guild_id)
            
            logger.info(f"[Music] Previous request - Guild: {guild_id}, Current index: {current_index}, Queue length: {len(queue)}")
            
            if current_index > 0:
                prev_index = current_index - 1
                queue_store.set_index(guild_id, prev_index)
                return await play_track_at_index(player, guild_id)
            elif len(queue) > 0:
                # If at first track, go to last track
                last_index = len(queue) - 1
                queue_store.set_index(guild_id, last_index)
                return await play_track_at_index(player, guild_id)
            
        except Exception as e:
            logger.error(f"[Music] Error going to previous track for guild {guild_id}: {e}")
        return False

    async def preload_next_track(player: lavalink.DefaultPlayer, guild_id: int) -> None:
        """Preload next track for seamless playback."""
        try:
            guild_data = queue_store.get_guild(guild_id)
            current_index = guild_data.get('index', 0)
            queue = queue_store.get_queue(guild_id)
            loop_mode = guild_data.get('loop', 0)
            
            # Calculate next track index
            if loop_mode == 1:  # Track loop - no need to preload
                return
            elif current_index + 1 < len(queue):
                next_index = current_index + 1
            elif loop_mode == 2:  # Queue loop
                next_index = 0
            else:
                return  # No next track
            
            if 0 <= next_index < len(queue):
                next_track = queue[next_index]
                # Preload the track to cache
                try:
                    await player.node.get_tracks(next_track.get('uri'))
                    logger.debug(f"[Music] Preloaded next track for guild {guild_id}")
                except Exception as e:
                    logger.debug(f"[Music] Failed to preload next track for guild {guild_id}: {e}")
                    
        except Exception as e:
            logger.debug(f"[Music] Error preloading next track for guild {guild_id}: {e}")

    async def handle_track_end(player: lavalink.DefaultPlayer, guild_id: int) -> bool:
        """Handle track end based on loop mode."""
        try:
            guild_data = queue_store.get_guild(guild_id)
            current_index = guild_data.get('index', 0)
            loop_mode = guild_data.get('loop', 0)
            queue = queue_store.get_queue(guild_id)
            
            logger.info(f"[Music] Track ended - Guild: {guild_id}, Current index: {current_index}, Loop mode: {loop_mode}, Queue length: {len(queue)}")
            
            # Track loop: replay same track
            if loop_mode == 1:
                return await play_track_at_index(player, guild_id)
            
            # Move to next track
            if current_index + 1 < len(queue):
                next_index = current_index + 1
                queue_store.set_index(guild_id, next_index)
                return await play_track_at_index(player, guild_id)
            elif loop_mode == 2:  # Queue loop: restart from beginning
                queue_store.set_index(guild_id, 0)
                return await play_track_at_index(player, guild_id)
            else:
                # Queue finished, no loop - reset state for clean new additions
                logger.info(f"[Music] Queue finished for guild {guild_id}")
                # Reset index to -1 to indicate queue has finished
                queue_store.set_index(guild_id, -1)
                return False
                
        except Exception as e:
            logger.error(f"[Music] Error handling track end for guild {guild_id}: {e}")
        return False

    # --- 'Now Playing' Message Management ---
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

    async def send_now_playing_embed(player: lavalink.DefaultPlayer, guild_id: int):
        """Creates and sends the 'Now Playing' embed with queue position."""
        # Ensure we have a channel to send in
        channel_id = player.fetch('channel')
        if not channel_id:
            logger.warning(f"[Music] NP aborted: no text channel stored for guild {guild_id}")
            return

        # If a panel already exists, update it instead of deleting/resending.
        existing_message_id = player.fetch('message_id')
        panel_channel_id = player.fetch('panel_channel_id') or channel_id

        try:
            channel = bot.get_channel(channel_id) or await bot.fetch_channel(channel_id)
        except (discord.NotFound, discord.Forbidden) as e:
            logger.error(f"[Music] NP aborted: cannot access channel {channel_id}: {e}")
            return

        track = player.current
        if not track:
            logger.warning(f"[Music] NP aborted: no current track for guild {guild_id}")
            return

        # Get queue position info
        current_index = queue_store.get_index(guild_id)
        queue = queue_store.get_queue(guild_id)
        queue_length = len(queue)
        loop_mode = queue_store.get_guild(guild_id).get('loop', 0)
        
        # Build embed with clean styling
        requester = channel.guild.get_member(getattr(track, 'requester', 0))
        
        embed = discord.Embed(
            title="<:music:1415162611942686740> MUSIC PANEL",
            description=f"<a:Milk10:1399578671941156996> **[{track.title}]({track.uri})**",
            color=discord.Color.blurple()
        )
        
        if getattr(track, 'artwork_url', None):
            embed.set_thumbnail(url=track.artwork_url)
            
        # Add fields with emojis and code blocks
        try:
            vol = int(player.fetch('volume') or 70)
        except Exception:
            vol = 70
            
        embed.add_field(name="<:speaker:1412542837198950511> Volume", value=f"`{vol}%`", inline=True)
        embed.add_field(name="<:microphone:1415163397657464874> Duration", value=f"`{format_duration(track.duration)}`", inline=True)
        embed.add_field(name="<:user:1415166117697028116> Author", value=f"`{getattr(track, 'author', 'Unknown')}`", inline=True)
        
        if requester:
            avatar_url = requester.display_avatar.url
            embed.set_footer(text=f"Requested by {requester.display_name}", icon_url=avatar_url)

        try:
            # If the panel exists but the stored panel channel differs from the current command channel,
            # delete the old panel and recreate it in the new channel.
            if existing_message_id and panel_channel_id and int(panel_channel_id) != int(channel_id):
                try:
                    old_channel = bot.get_channel(int(panel_channel_id)) or await bot.fetch_channel(int(panel_channel_id))
                    old_message = await old_channel.fetch_message(int(existing_message_id))
                    await old_message.delete()
                except Exception:
                    pass
                try:
                    player.store('message_id', None)
                except Exception:
                    pass
                existing_message_id = None

            if existing_message_id:
                try:
                    message = await channel.fetch_message(existing_message_id)
                    await message.edit(
                        embed=embed,
                        view=PlayerControls(
                            player,
                            queue_store=queue_store,
                            get_prefs_func=get_prefs,
                            apply_eq_func=apply_equalizer,
                            eq_presets=EQ_PRESETS,
                        ),
                    )
                    player.store('panel_channel_id', int(channel_id))
                    logger.info(f"[Music] NP updated: guild={guild_id}, channel={channel.id}, message_id={existing_message_id}, track={track.title}")
                    return
                except (discord.NotFound, discord.Forbidden):
                    player.store('message_id', None)
                except Exception as e:
                    logger.debug(f"[Music] NP edit failed; will resend: {e}")

            message = await channel.send(
                embed=embed,
                view=PlayerControls(
                    player,
                    queue_store=queue_store,
                    get_prefs_func=get_prefs,
                    apply_eq_func=apply_equalizer,
                    eq_presets=EQ_PRESETS,
                ),
            )
            player.store('message_id', message.id)
            player.store('panel_channel_id', int(channel_id))
            logger.info(f"[Music] NP sent: guild={guild_id}, channel={channel.id}, message_id={message.id}, track={track.title}")
        except Exception as e:
            logger.error(f"Failed to send Now Playing embed in guild {guild_id} channel {channel.id}: {e}")

    async def update_now_playing_panel(guild_id: int):
        """Update the existing Now Playing panel with current info."""
        try:
            player = bot.lavalink.player_manager.get(guild_id)
            if not player:
                return
                
            message_id = player.fetch('message_id')
            channel_id = player.fetch('channel')
            panel_channel_id = player.fetch('panel_channel_id') or channel_id
            
            if not channel_id:
                return

            if not message_id:
                await send_now_playing_embed(player, guild_id)
                return
                
            try:
                # If the command channel changed, move/recreate the panel there.
                if panel_channel_id and int(panel_channel_id) != int(channel_id):
                    await send_now_playing_embed(player, guild_id)
                    return

                channel = bot.get_channel(int(panel_channel_id)) or await bot.fetch_channel(int(panel_channel_id))
                message = await channel.fetch_message(message_id)
                
                track = player.current
                if not track:
                    return

                embed = discord.Embed(
                    title="<:music:1415162611942686740> MUSIC PANEL",
                    description=f"<a:Milk10:1399578671941156996> **[{track.title}]({track.uri})**",
                    color=discord.Color.blurple(),
                )
                if getattr(track, 'artwork_url', None):
                    embed.set_thumbnail(url=track.artwork_url)

                try:
                    vol = int(player.fetch('volume') or 70)
                except Exception:
                    vol = 70

                embed.add_field(name="<:speaker:1412542837198950511> Volume", value=f"`{vol}%`", inline=True)
                embed.add_field(name="<:microphone:1415163397657464874> Duration", value=f"`{format_duration(track.duration)}`", inline=True)
                embed.add_field(name="<:user:1415166117697028116> Author", value=f"`{getattr(track, 'author', 'Unknown')}`", inline=True)

                try:
                    requester = channel.guild.get_member(getattr(track, 'requester', 0))
                    if requester:
                        embed.set_footer(
                            text=f"Requested by {requester.display_name}",
                            icon_url=requester.display_avatar.url,
                        )
                except Exception:
                    pass

                await message.edit(
                    embed=embed,
                    view=PlayerControls(
                        player,
                        queue_store=queue_store,
                        get_prefs_func=get_prefs,
                        apply_eq_func=apply_equalizer,
                        eq_presets=EQ_PRESETS,
                    ),
                )
                    
            except (discord.NotFound, discord.Forbidden):
                # Panel was deleted; recreate.
                try:
                    player.store('message_id', None)
                except Exception:
                    pass
                await send_now_playing_embed(player, guild_id)
                
        except Exception as e:
            logger.error(f"[Music] Error updating now playing panel for guild {guild_id}: {e}")

    # --- Event Handling ---
    async def lavalink_event_hook(event):
        event_name = type(event).__name__
        
        # Track Start
        if event_name == 'TrackStartEvent':
            player = getattr(event, 'player', None)
            if not player:
                return
                
            guild_id = player.guild_id
            logger.info(f"[Music] TrackStartEvent received: guild={guild_id}")
            
            await asyncio.sleep(0.15)  # Small delay for stability
            
            # Apply enhanced audio settings and preferred settings per guild
            try:
                prefs = get_prefs(guild_id)
                
                # Apply enhanced audio settings first for YouTube-like quality
                await apply_enhanced_audio_settings(player)
                
                # Then apply user preferences if they exist
                if prefs.get('volume') is not None:
                    await player.set_volume(int(prefs.get('volume', 75)))
                    player.store('volume', int(prefs.get('volume', 75)))
                
                # Apply custom EQ if user has preference, otherwise keep enhanced settings
                if prefs.get('eq_preset') and prefs.get('eq_preset') != 'enhanced':
                    preset = prefs.get('eq_preset', 'enhanced')
                    bands = EQ_PRESETS.get(preset)
                    if bands:
                        await apply_equalizer(player, bands)
                    player.store('eq_preset', preset)
                else:
                    player.store('eq_preset', 'enhanced')
                
            except Exception as e:
                logger.error(f"[Music] Failed to apply audio settings on start: {e}")
            
            # Sticky panel: always update (or create) on track start.
            if player.current and player.is_playing:
                await update_now_playing_panel(guild_id)
                asyncio.create_task(preload_next_track(player, guild_id))
            else:
                logger.info(f"[Music] Skipping NP panel - track failed or not playing")
            
            return

        # Track End
        if event_name == 'TrackEndEvent':
            player = getattr(event, 'player', None)
            if not player:
                return
                
            guild_id = player.guild_id
            reason = str(getattr(event, 'reason', 'unknown')).lower()
            logger.info(f"[Music] TrackEndEvent: guild={guild_id}, reason={reason}")
            
            # Handle only relevant reasons; ignore manual stop/replace and LOADFAILED (already handled by TrackExceptionEvent)
            if reason in {'replaced', 'stopped', 'loadfailed'}:
                logger.info(f"[Music] Ignoring TrackEndEvent with reason '{reason}' - already handled")
                return
                
            # Serialize end-handling to avoid races
            lock = get_lock(guild_id)
            async with lock:
                try:
                    # Try to play next track based on queue and loop settings
                    success = await handle_track_end(player, guild_id)
                    if not success:
                        # Queue ended - don't block, just stay connected for new requests
                        logger.info(f"[Music] Queue ended for guild {guild_id} - staying connected for new requests")
                        
                        # Schedule a gentle disconnect after reasonable idle time (non-blocking)
                        asyncio.create_task(schedule_idle_disconnect(player, guild_id))
                        
                except Exception as e:
                    logger.error(f"[Music] Error during TrackEnd handling: {e}")
            return

        # Track Stuck or Exception -> skip quickly (YouTube-only)
        if event_name in {'TrackStuckEvent', 'TrackExceptionEvent'}:
            player = getattr(event, 'player', None)
            if not player:
                return
                
            guild_id = player.guild_id
            exception_info = getattr(event, 'exception', 'Unknown error')
            logger.warning(f"[Music] {event_name}: guild={guild_id}, error={exception_info}")
            lock = get_lock(guild_id)
            async with lock:
                try:
                    await skip_to_next(player, guild_id)
                except Exception as e:
                    logger.error(f"[Music] Failed to handle {event_name}: {e}")
                    await skip_to_next(player, guild_id)
            return

    # Register event hook
    try:
        bot.lavalink.add_event_hook(lavalink_event_hook)
        logger.info("[Music] Registered lavalink event hook")
    except Exception as e:
        logger.error(f"[Music] Failed to register lavalink event hook: {e}")

    # --- Commands ---
    @bot.hybrid_command(name="play", description="Play a song or add to the queue")
    async def play(ctx: commands.Context, *, query: str):
        try:
            if not ctx.author.voice or not ctx.author.voice.channel:
                return await ctx.send("You must be in a voice channel.", ephemeral=True)
                
            player = bot.lavalink.player_manager.create(ctx.guild.id)
            player.store('channel', ctx.channel.id)
            logger.info(f"[Music] Play command - Guild: {ctx.guild.id}, Query: {query[:50]}...")

            lock = get_lock(ctx.guild.id)
            async with lock:
                if not ctx.voice_client:
                    await ctx.author.voice.channel.connect(cls=LavalinkVoiceClient)
                    # Only clear queue if bot was disconnected for a long time or explicitly disconnected
                    # Don't clear for normal queue end situations
                    logger.info(f"[Music] Connected to VC for guild {ctx.guild.id}")
                elif ctx.voice_client.channel.id != ctx.author.voice.channel.id:
                    return await ctx.send("You must be in the same voice channel as me.", ephemeral=True)

                await ctx.defer()

                query = query.strip('<>')
                is_url = URL_REGEX.match(query) is not None

                # YouTube-only: reject non-YouTube URLs for clarity and speed.
                if is_url and not is_youtube_url(query):
                    return await ctx.send(
                        embed=discord.Embed(
                            description="Only **YouTube** links are supported. Try searching by name instead.",
                            color=discord.Color.red(),
                        )
                    )

                temp_msg = await ctx.send(
                    embed=discord.Embed(
                        description="<:ZeroSip:1404982303180066856> Searching...", 
                        color=discord.Color.blurple()
                    ), 
                    delete_after=3  # Faster deletion
                )

                # Search for tracks
                try:
                    results = await search_tracks(player, query, is_url)
                except Exception as e:
                    logger.error(f"[Music] Search failed for guild {ctx.guild.id}: {e}")
                    results = None

                if not results or not results.tracks:
                    return await ctx.send(
                        embed=discord.Embed(
                            description=f"<:no:1404980370486722621> No results found for `{query}`.", 
                            color=discord.Color.red()
                        )
                    )

                # Handle playlist
                if results.load_type == lavalink.LoadType.PLAYLIST:
                    tracks_data = []
                    for track in results.tracks:
                        tracks_data.append({
                            'title': track.title,
                            'uri': track.uri,
                            'duration': track.duration,
                            'identifier': track.identifier,
                            'author': track.author,
                            'requester': ctx.author.id,
                        })
                    
                    queue_store.extend_tracks(ctx.guild.id, tracks_data)
                    
                    embed = discord.Embed(
                        title="<:playlist:1412531317186498580> Playlist Added", 
                        description=f"Added **{len(tracks_data)}** songs from **{results.playlist_info.name}**.", 
                        color=discord.Color.purple()
                    )
                    await ctx.send(embed=embed)
                else:
                    # Single track
                    chosen = results.tracks[0]

                    alternatives: list[dict] = []
                    try:
                        for t in results.tracks[1:11]:
                            alternatives.append({
                                'title': t.title,
                                'uri': t.uri,
                                'duration': t.duration,
                                'identifier': t.identifier,
                                'author': t.author,
                            })
                    except Exception:
                        alternatives = []

                    track_data = {
                        'title': chosen.title,
                        'uri': chosen.uri,
                        'duration': chosen.duration,
                        'identifier': chosen.identifier,
                        'author': chosen.author,
                        'requester': ctx.author.id,
                        'alternatives': alternatives,
                    }
                    
                    # Add to queue
                    queue_store.append_track(ctx.guild.id, track_data)

                    added_index = len(queue_store.get_queue(ctx.guild.id)) - 1
                    
                    # Debug logging for queue state
                    current_index = queue_store.get_index(ctx.guild.id)
                    queue_length = len(queue_store.get_queue(ctx.guild.id))
                    logger.info(f"[Music] Added track: '{chosen.title}' | Queue length: {queue_length} | Current index: {current_index}")
                    
                    added_message = await ctx.send(
                        embed=discord.Embed(
                            description=f"<a:verify:1399579399107379271> Added **[{chosen.title}]({chosen.uri})** to the queue.", 
                            color=discord.Color.green()
                        )
                    )

                    # Persist the message reference so the 🔎 button can update it later if the user swaps results.
                    try:
                        msg_id = getattr(added_message, 'id', None)
                        ch_id = getattr(getattr(added_message, 'channel', None), 'id', None)
                        if msg_id and ch_id:
                            latest = dict(queue_store.get_queue(ctx.guild.id)[added_index])
                            latest['added_message_id'] = int(msg_id)
                            latest['added_channel_id'] = int(ch_id)
                            queue_store.update_track(ctx.guild.id, added_index, latest)
                    except Exception as e:
                        logger.debug(f"[Music] Failed to store added-message metadata: {e}")

                # If nothing is playing, start playback  
                if not player.is_playing:
                    queue = queue_store.get_queue(ctx.guild.id)
                    if queue:
                        # Always play the newly added track (last in queue) when playback is stopped
                        new_index = len(queue) - 1  # Last track = newly added track
                        queue_store.set_index(ctx.guild.id, new_index)
                        logger.info(f"[Music] Starting playback - newly added track at index {new_index}: '{queue[new_index].get('title', 'Unknown')}'")
                        await play_track_at_index(player, ctx.guild.id)
                        
        except Exception as e:
            logger.error(f"[Music] Error in play command for guild {ctx.guild.id}: {e}")
            await ctx.send("An error occurred while processing your request.", ephemeral=True)

    @bot.hybrid_command(name="queue", description="Shows the current music queue")
    async def queue_cmd(ctx: commands.Context, page: int = 1):
        try:
            from .controls import QueueView
            
            queue = queue_store.get_queue(ctx.guild.id)
            current_index = queue_store.get_index(ctx.guild.id)
            
            if not queue:
                return await ctx.send(
                    embed=discord.Embed(
                        description="The queue is empty.", 
                        color=discord.Color.orange()
                    )
                )

            # Convert 1-based page to 0-based
            current_page = max(0, page - 1)
            
            # Create interactive queue view
            view = QueueView(queue_store, ctx.guild.id, current_page)
            embed = view.get_queue_embed()
            
            message = await ctx.send(embed=embed, view=view)
            view.message = message
            
        except Exception as e:
            logger.error(f"[Music] Error in queue command for guild {ctx.guild.id}: {e}")
            await ctx.send("An error occurred while retrieving the queue.", ephemeral=True)

    @bot.hybrid_command(name="nowplaying", aliases=["np"], description="Shows the currently playing song")
    async def nowplaying(ctx: commands.Context):
        try:
            player = bot.lavalink.player_manager.get(ctx.guild.id)

            if not player or not player.current:
                return await ctx.send(
                    embed=discord.Embed(
                        description="Nothing is currently playing.", 
                        color=discord.Color.orange()
                    )
                )

            await send_now_playing_embed(player, ctx.guild.id)
            
        except Exception as e:
            logger.error(f"[Music] Error in nowplaying command for guild {ctx.guild.id}: {e}")
            await ctx.send("An error occurred while retrieving now playing info.", ephemeral=True)

    @bot.hybrid_command(name="loop", description="Toggle loop mode (Off, Track, Queue)")
    async def loop_cmd(ctx: commands.Context):
        try:
            guild_data = queue_store.get_guild(ctx.guild.id)
            current_loop = guild_data.get('loop', 0)
            new_loop = (current_loop + 1) % 3
            
            queue_store.set_guild_prop(ctx.guild.id, 'loop', new_loop)
            
            loop_map = {0: '➡️ Off', 1: '🔂 Track', 2: '🔁 Queue'}
            embed = discord.Embed(
                description=f"Looping is now **{loop_map[new_loop]}**.", 
                color=discord.Color.blue()
            )
            await ctx.send(embed=embed)
            
            # Update the now playing panel to reflect the change
            await update_now_playing_panel(ctx.guild.id)
            
            logger.info(f"[Music] Loop mode changed to {new_loop} for guild {ctx.guild.id}")
            
        except Exception as e:
            logger.error(f"[Music] Error in loop command for guild {ctx.guild.id}: {e}")
            await ctx.send("An error occurred while changing loop mode.", ephemeral=True)

    @bot.hybrid_command(name="shuffle", description="Shuffles the queue")
    async def shuffle_cmd(ctx: commands.Context):
        try:
            queue = queue_store.get_queue(ctx.guild.id)
            if not queue:
                return await ctx.send(
                    embed=discord.Embed(
                        description="The queue is empty.", 
                        color=discord.Color.orange()
                    )
                )
            
            # Get current track to preserve it
            current_index = queue_store.get_index(ctx.guild.id)
            current_track = None
            if 0 <= current_index < len(queue):
                current_track = queue[current_index]
            
            # Shuffle the queue
            random.shuffle(queue)
            
            # If there was a current track, move it to the front
            if current_track:
                if current_track in queue:
                    queue.remove(current_track)
                queue.insert(0, current_track)
                queue_store.set_index(ctx.guild.id, 0)
            
            # Save shuffled queue using the new method
            queue_store.set_queue(ctx.guild.id, queue)
            
            embed = discord.Embed(
                description="<:shuffle:1412532183750676532> The queue has been shuffled!", 
                color=discord.Color.random()
            )
            await ctx.send(embed=embed)
            
            logger.info(f"[Music] Queue shuffled for guild {ctx.guild.id}")
            
        except Exception as e:
            logger.error(f"[Music] Error in shuffle command for guild {ctx.guild.id}: {e}")
            await ctx.send("An error occurred while shuffling the queue.", ephemeral=True)

    @bot.hybrid_command(name="remove", description="Removes a song from the queue")
    async def remove_cmd(ctx: commands.Context, index: int):
        try:
            queue = queue_store.get_queue(ctx.guild.id)
            if not queue:
                return await ctx.send(
                    embed=discord.Embed(
                        description="The queue is empty.", 
                        color=discord.Color.orange()
                    )
                )
            
            if not 1 <= index <= len(queue):
                return await ctx.send(
                    embed=discord.Embed(
                        description=f"Invalid index. Please provide a number between 1 and {len(queue)}.", 
                        color=discord.Color.red()
                    )
                )
            
            # Convert to 0-based index
            remove_index = index - 1
            removed_track = queue_store.remove_at(ctx.guild.id, remove_index)
            
            if removed_track:
                title = removed_track.get('title', 'Unknown')
                embed = discord.Embed(
                    description=f"<:Sage_Trash:1399580044531339356> Removed **{title}** from the queue.", 
                    color=discord.Color.green()
                )
                await ctx.send(embed=embed)
                logger.info(f"[Music] Removed track at index {index} for guild {ctx.guild.id}")
            else:
                await ctx.send("Failed to remove track.", ephemeral=True)
                
        except Exception as e:
            logger.error(f"[Music] Error in remove command for guild {ctx.guild.id}: {e}")
            await ctx.send("An error occurred while removing the track.", ephemeral=True)

    @bot.hybrid_command(name="clearqueue", aliases=["cq"], description="Clear the entire queue")
    async def clearqueue_cmd(ctx: commands.Context):
        try:
            queue = queue_store.get_queue(ctx.guild.id)
            if not queue:
                return await ctx.send(
                    embed=discord.Embed(
                        description="The queue is already empty.", 
                        color=discord.Color.orange()
                    )
                )
            
            # Clear the entire queue including current track
            queue_store.clear_guild(ctx.guild.id)
            
            embed = discord.Embed(
                description="<:trash:1415172903061815317> Queue has been cleared!", 
                color=discord.Color.green()
            )
            await ctx.send(embed=embed)
            
            # Update the now playing panel
            await update_now_playing_panel(ctx.guild.id)
            
            logger.info(f"[Music] Queue cleared for guild {ctx.guild.id}")
            
        except Exception as e:
            logger.error(f"[Music] Error in clearqueue command for guild {ctx.guild.id}: {e}")
            await ctx.send("An error occurred while clearing the queue.", ephemeral=True)

    @bot.hybrid_command(name="skip", description="Skip the current song")
    async def skip_cmd(ctx: commands.Context):
        try:
            player = bot.lavalink.player_manager.get(ctx.guild.id)
            if not player or not player.is_playing:
                return await ctx.send("Nothing is playing to skip.")
            
            lock = get_lock(ctx.guild.id)
            async with lock:
                success = await skip_to_next(player, ctx.guild.id)
                if success:
                    await ctx.send("<:skip:1412530943121555546> Skipped the current song.")
                    logger.info(f"[Music] Skipped track for guild {ctx.guild.id}")
                else:
                    await ctx.send("No next track to skip to.")
                    
        except Exception as e:
            logger.error(f"[Music] Error in skip command for guild {ctx.guild.id}: {e}")
            await ctx.send("An error occurred while skipping.", ephemeral=True)

    @bot.hybrid_command(name="back", description="Go to the previous song")
    async def back_cmd(ctx: commands.Context):
        try:
            player = bot.lavalink.player_manager.get(ctx.guild.id)
            if not player:
                return await ctx.send("Not connected.")
            
            lock = get_lock(ctx.guild.id)
            async with lock:
                success = await go_to_previous(player, ctx.guild.id)
                if success:
                    await ctx.send("<:prev:1412530972779352214> Went back to the previous song.")
                    logger.info(f"[Music] Went back for guild {ctx.guild.id}")
                else:
                    await ctx.send("No previous track.")
                    
        except Exception as e:
            logger.error(f"[Music] Error in back command for guild {ctx.guild.id}: {e}")
            await ctx.send("An error occurred while going back.", ephemeral=True)

    @bot.hybrid_command(name="disconnect", aliases=["leave"], description="Disconnects the bot and clears the queue")
    async def disconnect_cmd(ctx: commands.Context):
        try:
            if not ctx.voice_client:
                return await ctx.send(
                    embed=discord.Embed(
                        description="I'm not connected to any voice channel.", 
                        color=discord.Color.orange()
                    )
                )
            
            await ctx.voice_client.disconnect(force=True)
            
            # Reset preferences and clear queue
            prefs = get_prefs(ctx.guild.id)
            prefs['volume'] = 70
            queue_store.clear_guild(ctx.guild.id)
            
            embed = discord.Embed(
                description="<:MomijiWave:1399580630207168606> Disconnected and cleared the queue.", 
                color=discord.Color.blue()
            )
            await ctx.send(embed=embed)
            
            logger.info(f"[Music] Disconnected and cleared queue for guild {ctx.guild.id}")
            
        except Exception as e:
            logger.error(f"[Music] Error in disconnect command for guild {ctx.guild.id}: {e}")
            await ctx.send("An error occurred while disconnecting.", ephemeral=True)

    @bot.hybrid_command(name="volume", description="Set the player volume (0-1000)")
    async def volume_cmd(ctx: commands.Context, volume: commands.Range[int, 0, 1000]):
        try:
            player = bot.lavalink.player_manager.get(ctx.guild.id)
            if not player:
                return await ctx.send("Not connected to a voice channel.")
            
            await player.set_volume(volume)
            
            # Update stored state
            prefs = get_prefs(ctx.guild.id)
            prefs['volume'] = int(volume)
            player.store('volume', int(volume))
            
            # Send self-destruct message
            embed = discord.Embed(
                description=f"<:autoplay:1412531621990629466> Volume changed to **{volume}%**", 
                color=discord.Color.green()
            )
            message = await ctx.send(embed=embed)
            
            # Update the music panel
            await update_now_playing_panel(ctx.guild.id)
            
            # Auto-delete the message after 5 seconds
            await asyncio.sleep(5)
            try:
                await message.delete()
            except:
                pass
            
            logger.info(f"[Music] Volume set to {volume}% for guild {ctx.guild.id}")
            
        except Exception as e:
            logger.error(f"[Music] Error in volume command for guild {ctx.guild.id}: {e}")
            await ctx.send("An error occurred while setting volume.", ephemeral=True)

    @bot.hybrid_command(name="pause", description="Pause the music")
    async def pause_cmd(ctx: commands.Context):
        try:
            player = bot.lavalink.player_manager.get(ctx.guild.id)
            if not player or not player.is_playing:
                return await ctx.send("Nothing is playing to pause.")
            
            await player.set_pause(True)
            await ctx.send("<:pause:1412529948861665491> Paused.")
            logger.info(f"[Music] Paused for guild {ctx.guild.id}")
            
        except Exception as e:
            logger.error(f"[Music] Error in pause command for guild {ctx.guild.id}: {e}")
            await ctx.send("An error occurred while pausing.", ephemeral=True)

    @bot.hybrid_command(name="resume", description="Resume the music")
    async def resume_cmd(ctx: commands.Context):
        try:
            player = bot.lavalink.player_manager.get(ctx.guild.id)
            if not player:
                return await ctx.send("Not connected.")
            
            if player.paused:
                await player.set_pause(False)
                await ctx.send("<:play:1412530216965767349> Resumed.")
                logger.info(f"[Music] Resumed for guild {ctx.guild.id}")
            else:
                await ctx.send("Music is not paused.")
                
        except Exception as e:
            logger.error(f"[Music] Error in resume command for guild {ctx.guild.id}: {e}")
            await ctx.send("An error occurred while resuming.", ephemeral=True)

    @bot.event
    async def on_voice_state_update(member, before, after):
        """Clear queue when bot disconnects from voice channel."""
        try:
            if member.id == bot.user.id:
                # Bot's voice state changed
                if before.channel and not after.channel:
                    # Bot left a voice channel - don't auto-clear queue to allow quick reconnection
                    guild_id = before.channel.guild.id
                    logger.info(f"[Music] Bot disconnected from guild {guild_id} - keeping queue for potential reconnection")
        except Exception as e:
            logger.error(f"[Music] Error in voice state update: {e}")
