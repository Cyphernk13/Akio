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
from .spotify import init_spotify_api, search_spotify_for_track, create_soundcloud_search_query

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

#  Search quality improvements
SEARCH_ENHANCERS = [
    "official music video", "official audio", "lyrics", "hq", "high quality",
    "music video", "official", "hd", "original"
]


def setup(bot: commands.Bot):
    # Initialize Spotify API for official track data
    try:
        client_id = os.getenv('CLIENT_ID')
        client_secret = os.getenv('CLIENT_SECRET')
        if client_id and client_secret:
            init_spotify_api(client_id, client_secret)
            logger.info("[Music] 🎵 Spotify integration enabled")
        else:
            logger.warning("[Music] ⚠️ Spotify credentials not found, using basic SoundCloud search")
    except Exception as e:
        logger.error(f"[Music] ❌ Failed to initialize Spotify API: {e}")
    
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
        """Enhance search queries for better results and official content."""
        # Don't enhance URLs
        if URL_REGEX.match(query):
            return query
            
        query = query.strip()
        
        # Remove common noise words that hurt search quality
        noise_words = ['lyrics', 'official video', 'music video', 'official', 'audio', 'hd', 'hq']
        
        # Clean the query first
        for noise in noise_words:
            query = query.replace(noise, '').strip()
        
        # Remove extra spaces
        query = ' '.join(query.split())
        
        return query

    def filter_soundcloud_for_official(tracks, query: str):
        """Smart filtering for SoundCloud to find official/best quality content."""
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
        logger.info(f"[Music] 🎯 SoundCloud ranking for '{query}':")
        for i, (track, score) in enumerate(scored_tracks[:3]):
            logger.info(f"[Music]   {i+1}. [{score}pts] {track.author} - {track.title}")
        
        return [track for track, score in scored_tracks]



    async def search_tracks(player: lavalink.DefaultPlayer, query: str, is_url: bool):
        """Smart search: YouTube Music first (official content), SoundCloud fallback."""
        variants = []
        
        if is_url:
            # Direct URL handling - Only support SoundCloud and other direct URLs
            if 'soundcloud.com' in query.lower():
                # SoundCloud URL - use SoundCloud sources
                variants.extend([
                    query,                    # Direct URL first
                    f'scsearch:{query}',      # SoundCloud fallback
                ])
                logger.info(f"[Music] 🎵 Detected SoundCloud URL, using SoundCloud sources")
            else:
                # Other URLs (non-YouTube) - try direct first, then SoundCloud fallback
                variants.extend([
                    query,                    # Direct URL first
                    f'scsearch:{query}',      # SoundCloud fallback
                ])
                logger.info(f"[Music] 🔗 Direct URL detected, trying direct then SoundCloud")
        else:
            # 🚀 HYBRID SEARCH: Spotify for official data → SoundCloud for audio
            logger.info(f"[Music] 🎯 Hybrid Spotify+SoundCloud search for: '{query}'")
            
            try:
                # Step 1: Get official track data from Spotify
                spotify_data = await search_spotify_for_track(query)
                
                if spotify_data:
                    # Step 2: Create optimized SoundCloud searches using Spotify data
                    official_query = create_soundcloud_search_query(spotify_data)
                    logger.info(f"[Music] ✨ Spotify data: {spotify_data['artist']} - {spotify_data['name']}")
                    
                    # Multiple SoundCloud strategies with official Spotify data
                    variants.extend([
                        f'scsearch:{official_query}',                    # Primary: Exact Spotify match
                        f'scsearch:{official_query} official',           # With "official" tag
                        f'scsearch:{spotify_data["name"]} {spotify_data["artist"]}',  # Reversed order
                        f'scsearch:{query}',                             # Fallback: Original query
                    ])
                else:
                    # Fallback: No Spotify data available
                    logger.info(f"[Music] ⚠️ No Spotify data, using enhanced SoundCloud search")
                    enhanced_query = enhance_search_query(query)
                    variants.extend([
                        f'scsearch:{enhanced_query} official',
                        f'scsearch:{enhanced_query}',
                        f'scsearch:{query}',
                    ])
                    
            except Exception as e:
                logger.error(f"[Music] ❌ Spotify search failed: {e}")
                # Emergency fallback to basic SoundCloud search
                enhanced_query = enhance_search_query(query)
                variants.extend([f'scsearch:{enhanced_query}'])
        
        # 🎯 SMART STRATEGY: Try all variants and pick the best overall result
        all_results = []
        
        for i, variant in enumerate(variants):
            try:
                # Small delay between attempts
                if i > 0:
                    await asyncio.sleep(0.2)
                    
                res = await player.node.get_tracks(variant)
                if res and res.tracks:
                    # Filter and score these results
                    if not is_url and 'scsearch' in variant:
                        filtered_tracks = filter_soundcloud_for_official(res.tracks, query)
                        if filtered_tracks:
                            # Store the best result from this search strategy
                            all_results.append((filtered_tracks[0], variant))
                            logger.info(f"[Music] ✅ Got results from: {variant[:50]}...")
                    else:
                        # Direct URL or non-SoundCloud
                        all_results.append((res.tracks[0], variant))
                        logger.info(f"[Music] ✅ Got results from: {variant[:50]}...")
                        
            except Exception as e:
                logger.warning(f"[Music] Search variant failed: {variant[:50]}... - {e}")
                continue
        
        if all_results:
            # 🎯 FINAL QUALITY CHECK: Prefer original tracks over remixes/covers
            original_tracks = []
            remix_tracks = []
            
            for track, variant in all_results:
                title_lower = track.title.lower()
                author_lower = track.author.lower()
                
                # Check if this is likely an original track
                is_remix = any(word in title_lower or word in author_lower for word in [
                    'remix', 'cover', 'edit', 'bootleg', 'unofficial', 'nightcore', 'slowed'
                ])
                
                if is_remix:
                    remix_tracks.append((track, variant))
                else:
                    original_tracks.append((track, variant))
            
            # Prefer original tracks, but fall back to remixes if no originals found
            final_candidates = original_tracks if original_tracks else remix_tracks
            best_track, best_variant = final_candidates[0]
            
            # Create a result object with just the best track
            class SearchResult:
                def __init__(self, track):
                    self.tracks = [track]
                    self.load_type = 'track'
                    
            track_type = "Original" if original_tracks else "Remix/Cover"
            logger.info(f"[Music] 🏆 Selected best {track_type} result: {best_track.author} - {best_track.title}")
            return SearchResult(best_track)
            
        return None

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

    async def attempt_track_recovery(player: lavalink.DefaultPlayer, guild_id: int) -> bool:
        """Attempt to recover a failed track intelligently based on original source"""
        # Check if recovery is already in progress to prevent infinite loops
        if player.fetch(f'recovery_in_progress_{guild_id}'):
            logger.info(f"[Music] Recovery already in progress for guild {guild_id}, skipping")
            return False
            
        # Mark recovery as in progress
        player.store(f'recovery_in_progress_{guild_id}', True)
        
        try:
            current_track = queue_store.current_track(guild_id)
            if not current_track:
                return False
                
            track_title = current_track.get('title', 'Unknown')
            track_uri = current_track.get('uri', '')
            logger.info(f"[Music] 🔧 Attempting recovery for track: {track_title}")
            
            # 🎯 SMART RECOVERY: Multiple SoundCloud strategies for official content
            logger.info(f"[Music] 🎵 Smart SoundCloud recovery for official content")
            recovery_attempts = [
                ('scsearch', f"{current_track.get('author', '')} {track_title} official"),  # With artist + official
                ('scsearch', f"{track_title} official"),                                    # Title + official
                ('scsearch', f"{current_track.get('author', '')} {track_title} original"), # With artist + original
                ('scsearch', f"{current_track.get('author', '')} {track_title}"),          # With artist
                ('scsearch', track_title),                                                  # Title only
            ]
                
            for source, search_query in recovery_attempts:
                try:
                    await asyncio.sleep(0.5)  # Delay to prevent spam
                    search_result = await player.node.get_tracks(f"{source}:{search_query.strip()}")
                    
                    if search_result and search_result.tracks:
                        # Use smart filtering to find the best match
                        filtered_tracks = filter_soundcloud_for_official(search_result.tracks, search_query)
                        track = filtered_tracks[0] if filtered_tracks else search_result.tracks[0]
                        track.requester = current_track.get('requester')
                        
                        # Wait for track to actually start before claiming success
                        await player.play(track)
                        await asyncio.sleep(1.0)  # Verify it works
                        
                        if player.current and player.current.identifier == track.identifier:
                            # Update queue with working source
                            current_track['uri'] = track.uri
                            queue_store.update_track(guild_id, queue_store.get_index(guild_id), current_track)
                            
                            source_name = "YouTube" if "yt" in source else "SoundCloud"
                            logger.info(f"[Music] ✅ Recovery successful with {source_name}: {track.title}")
                            return True
                        else:
                            logger.warning(f"[Music] Track from {source} failed to start properly")
                        
                except Exception as e:
                    logger.debug(f"[Music] Recovery attempt with {source} failed: {e}")
                    continue
            
            logger.warning(f"[Music] ❌ All recovery attempts failed for: {track_title}")
            return False
            
        except Exception as e:
            logger.error(f"[Music] Recovery process error: {e}")
            return False
        finally:
            # Clear recovery flag
            player.store(f'recovery_in_progress_{guild_id}', False)

    async def play_track_at_index(player: lavalink.DefaultPlayer, guild_id: int) -> bool:
        """Play track at current index from persistent queue with enhanced retry mechanism."""
        current_track = queue_store.current_track(guild_id)
        if not current_track:
            logger.warning(f"[Music] No current track for guild {guild_id}")
            return False

        track_title = current_track.get('title', 'Unknown')
        track_uri = current_track.get('uri', '')
        
        # Strategy 1: Try direct URI first (for SoundCloud direct URLs only)
        if track_uri and 'soundcloud.com' in track_uri.lower():
            try:
                res = await player.node.get_tracks(track_uri)
                if res and res.tracks:
                    track = res.tracks[0]
                    track.requester = current_track.get('requester')
                    await player.play(track)
                    player.store('current_track_info', current_track)
                    current_index = queue_store.get_index(guild_id)
                    logger.info(f"[Music] ✅ Playing direct SoundCloud track at index {current_index}: {track_title}")
                    return True
            except Exception as e:
                logger.warning(f"[Music] Direct SoundCloud URI failed for {track_title}: {e}")

        # Strategy 2: Smart source selection based on original track type
        try:
            search_query = track_title
            if current_track.get('author'):
                search_query = f"{current_track.get('author')} {track_title}"
            
            logger.info(f"[Music] 🔍 Smart search for: {search_query}")
            
            # 🎯 SIMPLE SELECTION: SoundCloud only (YouTube completely broken)
            search_attempts = [
                ('scsearch', 'SoundCloud'),       # SoundCloud only - working reliably
            ]
            logger.info(f"[Music] 🎵 SoundCloud-only search (YouTube broken)")
            
            for search_type, source_name in search_attempts:
                try:
                    await asyncio.sleep(0.3)  # Prevent rapid API calls
                    
                    search_result = await player.node.get_tracks(f"{search_type}:{search_query}")
                    
                    if search_result and search_result.tracks:
                        # Use smart filtering to find the best official content
                        filtered_tracks = filter_soundcloud_for_official(search_result.tracks, search_query)
                        track = filtered_tracks[0] if filtered_tracks else search_result.tracks[0]
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

        # Strategy 3: Final fallback - try direct URI one more time with delay
        if track_uri:
            try:
                await asyncio.sleep(1)  # Give network a moment
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

        # Clean up any previous NP message
        await delete_old_np_message(player)

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
            message = await channel.send(
                embed=embed, 
                view=PlayerControls(
                    player, 
                    queue_store=queue_store,
                    get_prefs_func=get_prefs, 
                    apply_eq_func=apply_equalizer, 
                    eq_presets=EQ_PRESETS
                )
            )
            player.store('message_id', message.id)
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
            
            if not message_id or not channel_id:
                return
                
            try:
                channel = bot.get_channel(channel_id) or await bot.fetch_channel(channel_id)
                message = await channel.fetch_message(message_id)
                
                if message and message.embeds:
                    # Get current queue position info
                    current_index = queue_store.get_index(guild_id)
                    queue = queue_store.get_queue(guild_id)
                    queue_length = len(queue)
                    loop_mode = queue_store.get_guild(guild_id).get('loop', 0)
                    
                    embed = message.embeds[0]
                    
                    # Update fields
                    try:
                        vol = int(player.fetch('volume') or 70)
                        for i, field in enumerate(embed.fields):
                            if field.name and "Volume" in field.name:
                                embed.set_field_at(i, name="<:vol_up:1412531098474512556> Volume", value=f"{vol}%", inline=field.inline)
                            elif field.name and "Position" in field.name:
                                position_text = f"{current_index + 1} / {queue_length}" if queue_length > 0 else "0 / 0"
                                embed.set_field_at(i, name="📍 Position in Queue", value=position_text, inline=field.inline)
                            elif field.name and "Loop" in field.name:
                                loop_icons = {0: "➡️ Off", 1: "🔂 Track", 2: "🔁 Queue"}
                                embed.set_field_at(i, name="<:loop:1412531198147952832> Loop Mode", value=loop_icons.get(loop_mode, "Off"), inline=field.inline)
                    except Exception as e:
                        logger.error(f"[Music] Error updating embed fields: {e}")
                    
                    # Update the message with new embed and controls
                    await message.edit(
                        embed=embed,
                        view=PlayerControls(
                            player, 
                            queue_store=queue_store,
                            get_prefs_func=get_prefs, 
                            apply_eq_func=apply_equalizer, 
                            eq_presets=EQ_PRESETS
                        )
                    )
                    
            except (discord.NotFound, discord.Forbidden):
                pass
                
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
            
            await asyncio.sleep(0.25)  # Small delay for stability
            
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
            
            # 🚫 ANTI-SPAM: Wait and verify track is actually stable before showing panel
            await asyncio.sleep(3.0)  # Wait 3 seconds to see if track will fail
            
            # Only send panel if track is still playing and stable (and not in recovery)
            recovery_in_progress = player.fetch(f'recovery_in_progress_{guild_id}')
            if player.current and player.is_playing and not recovery_in_progress:
                # Double-check no existing panel exists
                old_message_id = player.fetch('message_id')
                if not old_message_id:  # Only send if no panel exists
                    await send_now_playing_embed(player, guild_id)
                    # Preload next track for seamless playback
                    asyncio.create_task(preload_next_track(player, guild_id))
                else:
                    logger.info(f"[Music] Panel already exists, skipping duplicate")
            else:
                logger.info(f"[Music] Skipping NP panel - track failed, not playing, or in recovery")
            
            return

        # Track End
        if event_name == 'TrackEndEvent':
            player = getattr(event, 'player', None)
            if not player:
                return
                
            guild_id = player.guild_id
            reason = str(getattr(event, 'reason', 'unknown')).lower()
            logger.info(f"[Music] TrackEndEvent: guild={guild_id}, reason={reason}")
            
            await delete_old_np_message(player)
            
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

        # Track Stuck or Exception -> attempt recovery before skipping
        if event_name in {'TrackStuckEvent', 'TrackExceptionEvent'}:
            player = getattr(event, 'player', None)
            if not player:
                return
                
            guild_id = player.guild_id
            exception_info = getattr(event, 'exception', 'Unknown error')
            logger.warning(f"[Music] {event_name}: guild={guild_id}, error={exception_info}")
            
            # AGGRESSIVE CIRCUIT BREAKER - Completely disable recovery when YouTube is broken
            circuit_breaker_key = f'circuit_breaker_{guild_id}'
            circuit_failures = player.fetch(circuit_breaker_key) or 0
            
            # Much more aggressive: Only 2 failures before circuit breaker activates
            if circuit_failures >= 2:
                logger.warning(f"[Music] 🚫 CIRCUIT BREAKER ACTIVE for guild {guild_id} - All sources failing, skipping immediately")
                player.store(circuit_breaker_key, circuit_failures + 1)  # Continue counting failures
                await skip_to_next(player, guild_id)
                return
            
            # Implement per-track recovery limiting - ONLY 1 attempt per track
            recovery_count_key = f'recovery_attempts_{guild_id}_{getattr(player.current, "identifier", "unknown")}'
            recovery_count = player.fetch(recovery_count_key) or 0
            
            if recovery_count >= 1:  # Only 1 recovery attempt per track
                logger.warning(f"[Music] Maximum recovery attempts (1) reached for current track, skipping")
                player.store(recovery_count_key, 0)  # Reset counter
                player.store(circuit_breaker_key, circuit_failures + 1)  # Increment circuit breaker
                await skip_to_next(player, guild_id)
                return
            
            # Check if recovery is already in progress (additional safeguard)
            if player.fetch(f'recovery_in_progress_{guild_id}'):
                logger.warning(f"[Music] Recovery already in progress for guild {guild_id}, skipping duplicate attempt")
                return
            
            lock = get_lock(guild_id)
            async with lock:
                try:
                    # Increment recovery attempt counter BEFORE attempting recovery
                    player.store(recovery_count_key, recovery_count + 1)
                    
                    # Try to recover the current track
                    recovery_success = await attempt_track_recovery(player, guild_id)
                    
                    if recovery_success:
                        # Reset circuit breaker on successful recovery
                        player.store(circuit_breaker_key, max(0, circuit_failures - 1))  # Reduce failures
                        logger.info(f"[Music] ✅ Recovery successful, circuit breaker reduced to {max(0, circuit_failures - 1)}")
                    else:
                        # If recovery fails, skip to next track and increment circuit breaker
                        logger.warning(f"[Music] ❌ Recovery failed, incrementing circuit breaker")
                        player.store(circuit_breaker_key, circuit_failures + 1)
                        await skip_to_next(player, guild_id)
                        
                except Exception as e:
                    logger.error(f"[Music] Failed to recover from {event_name}: {e}")
                    player.store(circuit_breaker_key, circuit_failures + 1)  # Increment circuit breaker on error
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

                # 🚫 Block YouTube URLs completely 
                if is_url and any(domain in query.lower() for domain in ['youtube.com', 'youtu.be', 'music.youtube.com', 'yt.be']):
                    embed = discord.Embed(
                        title="🚫 YouTube Not Supported",
                        description="Hey there! YouTube has blocked access to their music content, so I can't play YouTube links anymore. 😔\n\n**Instead, try searching by song name!** For example:\n`akio play naruto silhouette` instead of a YouTube link.\n\nThis actually works better and finds higher quality audio! 🎵",
                        color=discord.Color.red()
                    )
                    embed.set_footer(text="💡 Text searches use SoundCloud which has better reliability!")
                    return await ctx.send(embed=embed)

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
                    track_data = {
                        'title': chosen.title,
                        'uri': chosen.uri,
                        'duration': chosen.duration,
                        'identifier': chosen.identifier,
                        'author': chosen.author,
                        'requester': ctx.author.id,
                    }
                    
                    # Add to queue
                    queue_store.append_track(ctx.guild.id, track_data)
                    
                    # Debug logging for queue state
                    current_index = queue_store.get_index(ctx.guild.id)
                    queue_length = len(queue_store.get_queue(ctx.guild.id))
                    logger.info(f"[Music] Added track: '{chosen.title}' | Queue length: {queue_length} | Current index: {current_index}")
                    
                    await ctx.send(
                        embed=discord.Embed(
                            description=f"<a:verify:1399579399107379271> Added **[{chosen.title}]({chosen.uri})** to the queue.", 
                            color=discord.Color.green()
                        )
                    )

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
