# anime/anime_command.py
import discord
from discord import app_commands
from discord.ext import commands
import requests
from typing import Optional
from datetime import datetime

JIKAN_BASE = "https://api.jikan.moe/v4"

# Common utility function
def jikan_request(endpoint: str, params: dict = None):
    url = f"{JIKAN_BASE}/{endpoint}"
    response = requests.get(url, params=params)
    response.raise_for_status()
    return response.json().get("data", [])

# Anime Search (existing)
def search_anime(query: str, limit: int = 1):
    return jikan_request("anime", {"q": query, "limit": limit})

# New Commands Functions
def get_manga(query: str, limit: int = 1):
    return jikan_request("manga", {"q": query, "limit": limit})

def get_character(query: str, limit: int = 1):
    return jikan_request("characters", {"q": query, "limit": limit})

def get_top_anime(type: str = "all", limit: int = 5):
    return jikan_request(f"top/anime?type={type}&limit={limit}")

def get_seasonal(year: int = None, season: str = None):
    endpoint = "seasons/now" if not year else f"seasons/{year}/{season}"
    return jikan_request(endpoint)

def get_user(username: str):
    return jikan_request(f"users/{username}")

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
            embed = discord.Embed(
                title=anime["title"],
                url=anime["url"],
                description=anime.get("synopsis", "No synopsis available.")[:400] + "...",
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
            results = await ctx.bot.loop.run_in_executor(None, get_manga, query, 1)
            if not results:
                return await ctx.send("❌ No manga found!", ephemeral=True)
            
            manga = results[0]
            embed = discord.Embed(
                title=manga["title"],
                url=manga["url"],
                description=f"**Volumes:** {manga.get('volumes', 'N/A')}\n"
                            f"**Chapters:** {manga.get('chapters', 'N/A')}\n"
                            f"**Status:** {manga.get('status', 'N/A')}",
                color=0xE91E63
            )
            embed.set_thumbnail(url=manga["images"]["jpg"]["image_url"])
            embed.add_field(name="📖 Type", value=manga.get("type", "N/A"), inline=True)
            embed.add_field(name="⭐ Score", value=manga.get("score", "N/A"), inline=True)
            embed.add_field(name="❤️ Favorites", value=f"{manga.get('favorites', 0):,}", inline=True)
            await ctx.send(embed=embed)
        except Exception as e:
            await ctx.send(f"❌ Error: {str(e)}", ephemeral=True)

    # New: Character Search Command
    @bot.hybrid_command(description="Search character details (e.g., /character Luffy)")
    async def character(ctx, *, query: str):
        await ctx.typing()
        try:
            results = await ctx.bot.loop.run_in_executor(None, get_character, query, 1)
            if not results:
                return await ctx.send("❌ No character found!", ephemeral=True)
            
            char = results[0]
            embed = discord.Embed(
                title=char["name"],
                url=char["url"],
                description=char.get("about", "No information available.")[:200] + "...",
                color=0x9C27B0
            )
            embed.set_image(url=char["images"]["jpg"]["image_url"])
            embed.add_field(name="❤️ Favorites", value=f"{char.get('favorites', 0):,}", inline=True)
            embed.add_field(name="📚 Anime", value=char["anime"][0]["anime"]["title"] if char.get("anime") else "N/A", inline=True)
            embed.set_footer(text="Known for")
            await ctx.send(embed=embed)
        except Exception as e:
            await ctx.send(f"❌ Error: {str(e)}", ephemeral=True)

    # New: Top Anime Command
    @bot.hybrid_command(description="Show top anime (e.g., /topanime tv)")
    async def topanime(ctx, type: Optional[str] = "all"):
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
            profile = await ctx.bot.loop.run_in_executor(None, get_user, username)
            embed = discord.Embed(
                title=f"🐾 {profile['username']}'s Profile",
                url=profile["url"],
                color=0xFF9800
            )
            embed.set_thumbnail(url=profile["images"]["jpg"]["image_url"])
            embed.add_field(name="Joined", value=datetime.fromisoformat(profile["joined"]).strftime("%b %d, %Y"), inline=True)
            embed.add_field(name="Anime Days", value=profile["anime_stats"]["days_watched"], inline=True)
            embed.add_field(name="Manga Days", value=profile["manga_stats"]["days_read"], inline=True)
            embed.add_field(name="Favorites", value=f"🎬 {profile['favorites']['anime']}\n📚 {len(profile['favorites']['manga'])}", inline=False)
            await ctx.send(embed=embed)
        except Exception as e:
            await ctx.send(f"❌ Error: {str(e)}", ephemeral=True)
