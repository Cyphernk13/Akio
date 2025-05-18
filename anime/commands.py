# anime/anime_command.py
import discord
from discord import app_commands
from discord.ext import commands
import requests
from typing import Optional
from datetime import datetime
import asyncio

JIKAN_BASE = "https://api.jikan.moe/v4"

async def fetch_popular_anime(anime_list):
    """Fetch anime details in parallel and return the most popular one"""
    async def get_anime_details(anime_id):
        response = requests.get(f"{JIKAN_BASE}/anime/{anime_id}")
        return response.json().get('data', {}) if response.status_code == 200 else {}

    tasks = [get_anime_details(entry['anime']['mal_id']) for entry in anime_list[:5]]
    results = await asyncio.gather(*tasks)
    
    return max(results, key=lambda x: x.get('members', 0), default={})

def jikan_request(endpoint: str, params: dict = None):
    response = requests.get(f"{JIKAN_BASE}/{endpoint}", params=params)
    response.raise_for_status()
    return response.json().get("data", [])

# Anime Search (existing)
def search_anime(query: str, limit: int = 1):
    return jikan_request("anime", {"q": query, "limit": limit})

# New Commands Functions
def get_manga(query: str, limit: int = 1):
    return jikan_request("manga", {"q": query, "limit": limit})

async def get_character_data(query: str):
    # Fetch characters sorted by favorites (most popular first)
    search_results = jikan_request(
        "characters",
        {"q": query, "limit": 1, "order_by": "favorites", "sort": "desc"}
    )
    if not search_results:
        return None

    char_id = search_results[0]['mal_id']
    char_data = jikan_request(f"characters/{char_id}/full")

    # Determine most popular anime source
    source = "Unknown"
    if char_data.get('anime'):
        popular_anime = await fetch_popular_anime(char_data['anime'])
        source = popular_anime.get('title', source)
    elif char_data.get('manga'):
        source = char_data['manga'][0]['manga']['title']

    char_data['source'] = source
    return char_data

def get_top_anime(type: str = "all", limit: int = 5):
    return jikan_request(f"top/anime?type={type}&limit={limit}")

def get_seasonal(year: int = None, season: str = None):
    endpoint = "seasons/now" if not year else f"seasons/{year}/{season}"
    return jikan_request(endpoint)

def get_user(username: str):
    return jikan_request(f"users/{username}")

def get_user_stats(username: str):
    url = f"{JIKAN_BASE}/users/{username}/statistics"
    response = requests.get(url)
    response.raise_for_status()
    return response.json().get("data", {})

def setup(bot):
    # Existing anime command
    @bot.hybrid_command(description="Search anime details (e.g., /anime Attack on Titan)")
    async def anime(ctx, *, query: str):
        await ctx.typing()
        try:
            results = await ctx.bot.loop.run_in_executor(None, search_anime, query, 1)
            if not results:
                return await ctx.send("❌ No anime found!", ephemeral=True)
            
            anime = results[0]
            # Only first paragraph for description
            synopsis = anime.get("synopsis", "No synopsis available.").split('\n')[0]
            embed = discord.Embed(
                title=anime["title"],
                url=anime["url"],
                description=synopsis,
                color=0x2E51A2
            )
            embed.set_thumbnail(url=anime["images"]["jpg"]["image_url"])
            embed.add_field(name="📺 Type", value=anime.get("type", "N/A"), inline=True)
            embed.add_field(name="🎬 Episodes", value=anime.get("episodes", "N/A"), inline=True)
            embed.add_field(name="⭐ Score", value=anime.get("score", "N/A"), inline=True)
            embed.add_field(name="📅 Aired", value=anime["aired"]["string"], inline=False)
            embed.set_footer(text=f"Status: {anime['status']} | Rated: {anime['rating']}")
            await ctx.send(embed=embed)
        except Exception as e:
            await ctx.send(f"❌ Error: {str(e)}", ephemeral=True)

    # New: Manga Search Command
    @bot.hybrid_command(description="Search manga details (e.g., /manga Berserk)")
    async def manga(ctx, *, query: str):
        await ctx.typing()
        try:
            results = jikan_request("manga", {"q": query, "limit": 1})
            if not results:
                return await ctx.send("❌ No manga found!", ephemeral=True)
            
            manga = results[0]
            is_publishing = manga.get("status", "").lower() == "publishing"
            
            # Improved publishing status handling
            chapters = manga.get('chapters', 0) or 0
            volumes = manga.get('volumes', 0) or 0
            
            chapters_display = "Ongoing" if is_publishing and chapters <= 0 else chapters or "N/A"
            volumes_display = "Ongoing" if is_publishing and volumes <= 0 else volumes or "N/A"

            embed = discord.Embed(
                title=manga["title"],
                url=manga["url"],
                description=manga.get("synopsis", "No synopsis available.").split('\n')[0],
                color=0xE91E63
            )
            embed.set_thumbnail(url=manga["images"]["jpg"]["image_url"])
            
            fields = [
                ("📖 Type", manga.get("type", "N/A")),
                ("📚 Status", manga.get("status", "N/A")),
                ("📑 Chapters", chapters_display),
                ("📚 Volumes", volumes_display),
                ("⭐ Score", manga.get("score", "N/A")),
                ("❤️ Favorites", f"{manga.get('favorites', 0):,}")
            ]
            
            for name, value in fields:
                embed.add_field(name=name, value=value, inline=True)
            
            await ctx.send(embed=embed)
        except Exception as e:
            await ctx.send(f"❌ Error: {str(e)}", ephemeral=True)
            
    # New: Character Search Command
    @bot.hybrid_command(description="Search character details (e.g., /character Vegeta)")
    async def char(ctx, *, query: str):
        await ctx.typing()
        try:
            char = await get_character_data(query)
            if not char:
                return await ctx.send("❌ No character found!", ephemeral=True)
            
            embed = discord.Embed(
                title=char["name"],
                url=char["url"],
                description=char.get("about", "No information available.").split('\n''\n')[1],
                color=0x9C27B0
            )
            embed.set_image(url=char["images"]["jpg"]["image_url"])
            embed.add_field(name="❤️ Favorites", value=f"{char.get('favorites', 0):,}", inline=True)
            embed.add_field(name="📚 Source", value=char['source'], inline=True)
            await ctx.send(embed=embed)
        except Exception as e:
            await ctx.send(f"❌ Error: {str(e)}", ephemeral=True)

    # New: Top Anime Command
    @bot.hybrid_command(description="Show top anime (e.g., /topanime tv)")
    async def top(ctx, type: Optional[str] = "all"):
        await ctx.typing()
        try:
            results = await ctx.bot.loop.run_in_executor(None, get_top_anime, type, 5)
            if not results:
                return await ctx.send("❌ No results found!", ephemeral=True)
            
            embed = discord.Embed(
                title=f"Top {type.upper()} Anime",
                color=0x2196F3
            )
            for idx, anime in enumerate(results[:5], 1):
                embed.add_field(
                    name=f"{idx}. {anime['title']}",
                    value=f"⭐ {anime['score']} | 🎬 {anime['type']} | 📺 {anime['episodes']} eps",
                    inline=False
                )
            embed.set_thumbnail(url=results[0]["images"]["jpg"]["image_url"])
            await ctx.send(embed=embed)
        except Exception as e:
            await ctx.send(f"❌ Error: {str(e)}", ephemeral=True)

    # New: Seasonal Anime Command
    @bot.hybrid_command(description="Show seasonal anime (e.g., /seasonal 2023 summer)")
    async def seasonal(ctx, year: Optional[int] = None, season: Optional[str] = None):
        await ctx.typing()
        try:
            results = await ctx.bot.loop.run_in_executor(None, get_seasonal, year, season)
            if not results:
                return await ctx.send("❌ No seasonal anime found!", ephemeral=True)
            
            embed = discord.Embed(
                title=f"{season.capitalize()} {year}" if year else "Current Season",
                color=0x4CAF50
            )
            for anime in results[:5]:
                embed.add_field(
                    name=anime["title"],
                    value=f"📅 {anime['aired']['string']}\n"
                          f"⭐ {anime.get('score', 'N/A')} | 🏢 {anime['studios'][0]['name']}",
                    inline=False
                )
            await ctx.send(embed=embed)
        except Exception as e:
            await ctx.send(f"❌ Error: {str(e)}", ephemeral=True)

    # New: User Profile Command
    @bot.hybrid_command(description="Get MAL user profile (e.g., /user john)")
    async def user(ctx, *, username: str):
        await ctx.typing()
        try:
            # Fetch profile and stats separately
            profile = await ctx.bot.loop.run_in_executor(None, get_user, username)
            stats = await ctx.bot.loop.run_in_executor(None, get_user_stats, username)

            if not profile:
                return await ctx.send("❌ User not found!", ephemeral=True)

            embed = discord.Embed(
                title=f"🐾 {profile['username']}'s Profile",
                url=profile["url"],
                color=0xFF9800
            )

            # Set thumbnail
            if profile.get("images") and profile["images"].get("jpg"):
                embed.set_thumbnail(url=profile["images"]["jpg"]["image_url"])

            # Add joined date
            if profile.get("joined"):
                joined_date = datetime.fromisoformat(profile["joined"]).strftime("%b %d, %Y")
                embed.add_field(name="Joined", value=joined_date, inline=False)

            # Add Anime stats (Watching/Completed)
            anime_stats = stats.get("anime", {})
            anime_field = (
                f"Watching: {anime_stats.get('watching', 0)}\n"
                f"Completed: {anime_stats.get('completed', 0)}"
            )
            embed.add_field(name="🎬 Anime", value=anime_field, inline=False)

            # Add Manga stats (Reading/Completed)
            manga_stats = stats.get("manga", {})
            manga_field = (
                f"Reading: {manga_stats.get('reading', 0)}\n"
                f"Completed: {manga_stats.get('completed', 0)}"
            )
            embed.add_field(name="📚 Manga", value=manga_field, inline=False)

            await ctx.send(embed=embed)
        except Exception as e:
            await ctx.send(f"❌ Error: {str(e)}", ephemeral=True)