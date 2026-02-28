"""
Spotify Web API integration for getting official song metadata.
This module searches Spotify for accurate song information and returns
the official artist name, track title, and other metadata for better
SoundCloud searching.
"""

import aiohttp
import asyncio
import base64
import logging
import os
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta

# Set up logging
logger = logging.getLogger(__name__)

class SpotifyAPI:
    """Spotify Web API client for fetching official song metadata."""
    
    def __init__(self, client_id: str, client_secret: str):
        self.client_id = client_id
        self.client_secret = client_secret
        self.access_token = None
        self.token_expires_at = None
        self.base_url = "https://api.spotify.com/v1"
        
    async def _get_access_token(self) -> str:
        """Get Spotify access token using Client Credentials flow."""
        if self.access_token and self.token_expires_at and datetime.now() < self.token_expires_at:
            return self.access_token
            
        # Encode client credentials
        credentials = f"{self.client_id}:{self.client_secret}"
        encoded_credentials = base64.b64encode(credentials.encode()).decode()
        
        headers = {
            "Authorization": f"Basic {encoded_credentials}",
            "Content-Type": "application/x-www-form-urlencoded"
        }
        
        data = {"grant_type": "client_credentials"}
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    "https://accounts.spotify.com/api/token",
                    headers=headers,
                    data=data
                ) as response:
                    if response.status == 200:
                        token_data = await response.json()
                        self.access_token = token_data["access_token"]
                        expires_in = token_data.get("expires_in", 3600)
                        self.token_expires_at = datetime.now() + timedelta(seconds=expires_in - 60)
                        logger.info("[Spotify] ✅ Access token obtained successfully")
                        return self.access_token
                    else:
                        error = await response.text()
                        logger.error(f"[Spotify] ❌ Token request failed: {response.status} - {error}")
                        return None
        except Exception as e:
            logger.error(f"[Spotify] ❌ Token request error: {e}")
            return None
    
    async def search_track(self, query: str, limit: int = 10) -> List[Dict]:
        """
        Search Spotify for tracks and return official metadata.
        
        Args:
            query: Search query (song name, artist, etc.)
            limit: Maximum number of results to return
            
        Returns:
            List of track dictionaries with official metadata
        """
        token = await self._get_access_token()
        if not token:
            logger.error("[Spotify] ❌ No access token available")
            return []
            
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        
        # Clean and enhance the query
        clean_query = self._clean_search_query(query)
        
        params = {
            "q": clean_query,
            "type": "track",
            "limit": limit,
            "market": "US"  # Use US market for better results
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{self.base_url}/search",
                    headers=headers,
                    params=params
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        tracks = data.get("tracks", {}).get("items", [])
                        
                        # Parse and return structured track data
                        results = []
                        for track in tracks:
                            track_info = self._parse_track_data(track)
                            if track_info:
                                results.append(track_info)
                        
                        logger.info(f"[Spotify] ✅ Found {len(results)} tracks for query: '{query}'")
                        return results
                    else:
                        error = await response.text()
                        logger.error(f"[Spotify] ❌ Search failed: {response.status} - {error}")
                        return []
        except Exception as e:
            logger.error(f"[Spotify] ❌ Search error: {e}")
            return []
    
    def _clean_search_query(self, query: str) -> str:
        """Clean and optimize search query for Spotify."""
        # Remove common noise words and anime/show references that confuse Spotify
        noise_words = ['official', 'music video', 'lyrics', 'hd', 'hq', 'audio', 'naruto', 'opening', 'op1', 'op']
        
        query_lower = query.lower()
        for noise in noise_words:
            query_lower = query_lower.replace(noise, '')
        
        # Clean up extra spaces and normalize
        cleaned = ' '.join(query_lower.strip().split())
        
        # For artist + song queries, try to preserve the structure better
        # This helps with queries like "big dawgs hanumankind" -> "hanumankind big dawgs"
        words = cleaned.split()
        if len(words) >= 2 and len(words) <= 4:
            # Try different arrangements to improve Spotify matching
            original = cleaned
            reversed_query = ' '.join(reversed(words))
            return f"{original} OR {reversed_query}"
        
        return cleaned
    
    def _parse_track_data(self, track: Dict) -> Optional[Dict]:
        """Parse Spotify track data into structured format."""
        try:
            # Get primary artist
            artists = track.get("artists", [])
            if not artists:
                return None
                
            primary_artist = artists[0]["name"]
            all_artists = [artist["name"] for artist in artists]
            
            # Get track info
            track_name = track["name"]
            album_name = track.get("album", {}).get("name", "")
            duration_ms = track.get("duration_ms", 0)
            popularity = track.get("popularity", 0)
            
            # Check if it's likely official content
            is_official = self._is_likely_official(track)
            
            return {
                "name": track_name,
                "artist": primary_artist,
                "all_artists": all_artists,
                "album": album_name,
                "duration_ms": duration_ms,
                "popularity": popularity,
                "is_official": is_official,
                "spotify_id": track["id"],
                "spotify_url": track["external_urls"]["spotify"]
            }
        except Exception as e:
            logger.error(f"[Spotify] Error parsing track data: {e}")
            return None
    
    def _is_likely_official(self, track: Dict) -> bool:
        """Determine if a track is likely official content."""
        try:
            # High popularity usually indicates official releases
            popularity = track.get("popularity", 0)
            if popularity >= 70:
                return True
                
            # Check for verified artists (not always available in API)
            # Check album type
            album = track.get("album", {})
            album_type = album.get("album_type", "").lower()
            
            # Singles and albums are more likely to be official than compilations
            if album_type in ["album", "single"]:
                return True
                
            return False
        except:
            return False
    
    async def get_best_match(self, query: str) -> Optional[Dict]:
        """Get the single best match for a search query with improved relevance scoring."""
        results = await self.search_track(query, limit=10)  # Get more results for better matching
        if not results:
            return None
        
        # Score each result based on relevance to the original query
        query_lower = query.lower().strip()
        query_words = set(query_lower.split())
        
        scored_results = []
        for result in results:
            score = 0
            
            # Base scores
            if result["is_official"]:
                score += 50
            score += result["popularity"] / 10  # Scale popularity
            
            # Relevance scoring - how well does this match the query?
            artist_lower = result["artist"].lower()
            track_lower = result["name"].lower()
            
            # Exact word matches in artist name (very important)
            artist_matches = sum(1 for word in query_words if word in artist_lower and len(word) > 2)
            score += artist_matches * 40
            
            # Exact word matches in track name
            track_matches = sum(1 for word in query_words if word in track_lower and len(word) > 2)
            score += track_matches * 30
            
            # Partial matches
            for word in query_words:
                if len(word) > 2:
                    if word in artist_lower:
                        score += 15
                    if word in track_lower:
                        score += 10
            
            # Bonus for query being contained in result
            if query_lower in track_lower or query_lower in artist_lower:
                score += 25
                
            scored_results.append((result, score))
        
        # Sort by score (highest first)
        scored_results.sort(key=lambda x: x[1], reverse=True)
        
        best_match = scored_results[0][0]
        best_score = scored_results[0][1]
        
        logger.info(f"[Spotify] 🎯 Best match: {best_match['artist']} - {best_match['name']} (Score: {best_score})")
        
        # Log top 3 for debugging
        for i, (result, score) in enumerate(scored_results[:3]):
            logger.debug(f"[Spotify]   {i+1}. [{score}pts] {result['artist']} - {result['name']}")
        
        return best_match

# Global Spotify API instance
spotify_api = None

def init_spotify_api(client_id: str, client_secret: str):
    """Initialize the global Spotify API instance."""
    global spotify_api
    spotify_api = SpotifyAPI(client_id, client_secret)
    logger.info("[Spotify] 🎵 Spotify API initialized")

async def search_spotify_for_track(query: str) -> Optional[Dict]:
    """Search Spotify for official track data."""
    if not spotify_api:
        logger.error("[Spotify] ❌ Spotify API not initialized")
        return None
        
    return await spotify_api.get_best_match(query)

def create_soundcloud_search_query(spotify_data: Dict) -> str:
    """Create an optimized SoundCloud search query from Spotify data."""
    artist = spotify_data.get("artist", "")
    track_name = spotify_data.get("name", "")
    
    # Create the most likely to find official content query
    search_query = f"{artist} {track_name}"
    
    logger.info(f"[Spotify] 🔍 SoundCloud query: '{search_query}'")
    return search_query