# anime/commands.py
import discord
from discord.ext import commands
from discord import app_commands
import requests
from typing import Optional, List, Dict, Any
from datetime import datetime
import asyncio
import textwrap
import re

# --- Constants & Configuration ---
JIKAN_BASE_URL = "https://api.jikan.moe/v4"
ANIME_COLOR = 0x2E51A2  # Blue
MANGA_COLOR = 0xE91E63  # Pink
CHAR_COLOR = 0x9C27B0   # Purple
USER_COLOR = 0xFF9800    # Orange
SUCCESS_COLOR = 0x4CAF50 # Green
ERROR_COLOR = 0xF44336   # Red

# --- Helper Functions ---

def jikan_request(endpoint: str, params: Optional[Dict] = None) -> Dict[str, Any]:
    """Makes a request to the Jikan API and returns the JSON response."""
    try:
        response = requests.get(f"{JIKAN_BASE_URL}/{endpoint}", params=params)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Jikan API request failed: {e}")
        return {}

def format_number(number: int) -> str:
    """Formats a number with commas."""
    return f"{number:,}" if number else "N/A"

def truncate_text(text: str, max_length: int) -> str:
    """Truncates text to a maximum length, adding an ellipsis if needed."""
    if not text:
        return "No description available."
    return textwrap.shorten(text, width=max_length, placeholder="...")

# --- Embed Creation Functions ---

def create_anime_embed(anime: Dict[str, Any]) -> discord.Embed:
    title = anime.get('title_english') or anime.get('title', 'Unknown Title')
    synopsis = truncate_text(anime.get('synopsis'), 400)
    embed = discord.Embed(title=f"📺 {title}", url=anime.get('url'), description=synopsis, color=ANIME_COLOR)
    if image_url := anime.get('images', {}).get('jpg', {}).get('large_image_url'):
        embed.set_thumbnail(url=image_url)
    embed.add_field(name="⭐ Score", value=f"**{anime.get('score') or 'N/A'}**" if anime.get('score') else "N/A", inline=True)
    embed.add_field(name="❤️ Rank", value=f"#{format_number(anime.get('rank'))}" if anime.get('rank') else "N/A", inline=True)
    embed.add_field(name="👥 Popularity", value=f"#{format_number(anime.get('popularity'))}" if anime.get('popularity') else "N/A", inline=True)
    embed.add_field(name="🎬 Type", value=anime.get('type') or 'N/A', inline=True)
    embed.add_field(name="💿 Episodes", value=anime.get('episodes') or 'N/A', inline=True)
    embed.add_field(name="⏳ Status", value=anime.get('status') or 'N/A', inline=True)
    if studios := anime.get('studios'):
        embed.add_field(name="🏢 Studios", value=', '.join([s['name'] for s in studios]), inline=False)
    if genres := anime.get('genres'):
        embed.add_field(name="🎭 Genres", value=', '.join([g['name'] for g in genres]), inline=False)
    embed.set_footer(text=f"Aired: {anime.get('aired', {}).get('string', 'N/A')}")
    return embed

def create_manga_embed(manga: Dict[str, Any]) -> discord.Embed:
    title = manga.get('title_english') or manga.get('title', 'Unknown Title')
    synopsis = truncate_text(manga.get('synopsis'), 400)
    embed = discord.Embed(title=f"📖 {title}", url=manga.get('url'), description=synopsis, color=MANGA_COLOR)
    if image_url := manga.get('images', {}).get('jpg', {}).get('large_image_url'):
        embed.set_thumbnail(url=image_url)
    embed.add_field(name="⭐ Score", value=f"**{manga.get('score') or 'N/A'}**" if manga.get('score') else "N/A", inline=True)
    embed.add_field(name="❤️ Rank", value=f"#{format_number(manga.get('rank'))}" if manga.get('rank') else "N/A", inline=True)
    embed.add_field(name="👥 Popularity", value=f"#{format_number(manga.get('popularity'))}" if manga.get('popularity') else "N/A", inline=True)
    embed.add_field(name="📚 Type", value=manga.get('type') or 'N/A', inline=True)
    embed.add_field(name="⏳ Status", value=manga.get('status') or 'N/A', inline=True)
    embed.add_field(name="❤️ Favorites", value=format_number(manga.get('favorites')), inline=True)
    if authors := manga.get('authors'):
        embed.add_field(name="✍️ Authors", value=', '.join([a['name'] for a in authors]), inline=False)
    if genres := manga.get('genres'):
        embed.add_field(name="🎭 Genres", value=', '.join([g['name'] for g in genres]), inline=False)
    embed.set_footer(text=f"Published: {manga.get('published', {}).get('string', 'N/A')}")
    return embed

def create_character_embed(char: Dict[str, Any]) -> discord.Embed:
    about = truncate_text(char.get('about'), 400)
    embed = discord.Embed(title=f"👤 {char.get('name', 'Unknown Character')}", url=char.get('url'), description=about, color=CHAR_COLOR)
    if image_url := char.get('images', {}).get('jpg', {}).get('image_url'):
        embed.set_thumbnail(url=image_url)
    embed.add_field(name="❤️ Favorites", value=format_number(char.get('favorites')), inline=True)
    if nicknames := char.get('nicknames'):
        embed.add_field(name="Alias", value=', '.join(nicknames), inline=True)
    if anime_appearances := char.get('anime', []):
        main_anime = sorted(anime_appearances, key=lambda x: x['anime'].get('popularity', 99999))[0]
        embed.add_field(name="🎬 Main Anime", value=f"[{main_anime['anime']['title']}]({main_anime['anime']['url']})", inline=False)
    if voice_actors := char.get('voices'):
        if jp_va := next((va for va in voice_actors if va['language'] == 'Japanese'), None):
            embed.set_footer(text=f"🇯🇵 VA: {jp_va['person']['name']}", icon_url=jp_va['person']['images']['jpg']['image_url'])
    return embed

# --- UI Components ---

class SearchSelect(discord.ui.Select):
    """A select menu for choosing from a list of search results."""
    def __init__(self, items: List[Dict[str, Any]], item_type: str, original_author: discord.User):
        self.items = items
        self.item_type = item_type
        self.original_author = original_author
        options = []
        for i, item in enumerate(items[:25]):
            title = item.get('title', item.get('name', 'Unknown'))
            description = None
            if item_type in ['anime', 'manga']:
                description = f"Type: {item.get('type', 'N/A')} | Score: {item.get('score', 'N/A')}"
            elif item_type == 'character':
                anime_from = "N/A"
                if anime_list := item.get('anime'):
                    if anime_list[0].get('anime'):
                        anime_from = anime_list[0]['anime'].get('title', 'N/A')
                description = f"From: {anime_from}"
            options.append(discord.SelectOption(label=truncate_text(title, 100), description=truncate_text(description, 100) if description else None, value=str(i), emoji='🥇' if i == 0 else None))
        super().__init__(placeholder="Didn't find what you were looking for? Choose here!", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.original_author.id:
            return await interaction.response.send_message("You cannot interact with this menu.", ephemeral=True)
        await interaction.response.defer()
        selected_item = self.items[int(self.values[0])]
        endpoint_map = {'anime': 'anime', 'manga': 'manga', 'character': 'characters'}
        item_endpoint = endpoint_map[self.item_type]
        full_data_response = jikan_request(f"{item_endpoint}/{selected_item['mal_id']}/full")
        if not (full_data := full_data_response.get('data')):
            return await interaction.followup.send("Sorry, I couldn't fetch the details for that selection.", ephemeral=True)
        if self.item_type == 'anime': embed = create_anime_embed(full_data)
        elif self.item_type == 'manga': embed = create_manga_embed(full_data)
        elif self.item_type == 'character': embed = create_character_embed(full_data)
        else: embed = discord.Embed(title="Error", description="Unknown item type.", color=ERROR_COLOR)
        await interaction.message.edit(content=None, embed=embed, view=self.view)

class SearchView(discord.ui.View):
    def __init__(self, items: List[Dict[str, Any]], item_type: str, author: discord.User):
        super().__init__(timeout=120.0)
        self.message = None
        self.add_item(SearchSelect(items, item_type, author))
    async def on_timeout(self):
        if self.message:
            try:
                for item in self.children: item.disabled = True
                await self.message.edit(view=self)
            except discord.NotFound: pass

class TopAnimeButton(discord.ui.Button):
    """A button for a specific top anime category."""
    def __init__(self, label: str, category: str, param_type: str, emoji: str, row: int):
        super().__init__(label=label, style=discord.ButtonStyle.secondary, emoji=emoji, row=row)
        self.category = category
        self.param_type = param_type

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer()
        params = {"limit": 10, self.param_type: self.category}
        response_data = jikan_request("top/anime", params)
        results = response_data.get('data', [])
        if not results:
            error_embed = discord.Embed(description=f"Could not fetch top anime for the **{self.label}** category.", color=ERROR_COLOR)
            return await interaction.edit_original_response(embed=error_embed, view=self.view.clear_items())
        
        title = f"🏆 Top 10 Anime - {self.label}"
        embed = discord.Embed(title=title, color=SUCCESS_COLOR)
        description = ""
        for i, anime_data in enumerate(results, 1):
            title_text = anime_data.get('title_english') or anime_data.get('title')
            score = anime_data.get('score', 'N/A')
            description += f"**{i}. [{truncate_text(title_text, 40)}]({anime_data['url']})** - ⭐ {score}\n"
        embed.description = description
        if results and results[0].get('images', {}).get('jpg', {}).get('image_url'):
            embed.set_thumbnail(url=results[0]['images']['jpg']['image_url'])
        await interaction.edit_original_response(embed=embed)

class TopAnimeView(discord.ui.View):
    """A view that holds the TopAnime buttons."""
    def __init__(self):
        super().__init__(timeout=180.0)
        self.message = None
        buttons = [
            ("Popular", "bypopularity", "filter", "🔥", 0), ("Airing", "airing", "filter", "📺", 0),
            ("Upcoming", "upcoming", "filter", "⏳", 0), ("Favorites", "favorite", "filter", "❤️", 0),
            ("TV", "tv", "type", "🎬", 1), ("Movie", "movie", "type", "🍿", 1),
            ("OVA", "ova", "type", "💿", 1), ("Special", "special", "type", "🌟", 1)
        ]
        for label, category, param_type, emoji, row in buttons:
            self.add_item(TopAnimeButton(label, category, param_type, emoji, row))

    async def on_timeout(self):
        if self.message:
            try:
                for item in self.children: item.disabled = True
                await self.message.edit(view=self)
            except discord.NotFound: pass

# --- Bot Setup ---

def setup(bot):
    def calculate_relevance_score(item: Dict[str, Any], query: str, item_type: str) -> tuple:
        """Calculates a more nuanced relevance score."""
        query_lower = query.lower().strip()
        names_to_check = []
        
        # Primary name/title
        if name := (item.get('name' if item_type == 'character' else 'title', '') or '').lower():
            names_to_check.append(name)
        
        # English title for anime/manga
        if item_type != 'character':
            if title_english := (item.get('title_english', '') or '').lower():
                names_to_check.append(title_english)
        
        # Nicknames for characters
        if item_type == 'character':
            if nicknames := item.get('nicknames', []):
                names_to_check.extend([n.lower() for n in nicknames])

        match_quality = 0
        for name in names_to_check:
            if query_lower == name:
                match_quality = max(match_quality, 5)  # Exact match
            # Check if query is a whole word in the name
            elif re.search(r'\b' + re.escape(query_lower) + r'\b', name):
                 match_quality = max(match_quality, 4) # Whole word match
            elif name.startswith(query_lower):
                match_quality = max(match_quality, 3)  # Starts with
            elif query_lower in name:
                match_quality = max(match_quality, 2)  # Substring
        
        popularity_score = item.get('favorites' if item_type == 'character' else 'members', 0) or 0
        return (match_quality, popularity_score)

    async def search_and_display(ctx: commands.Context, query: str, item_type: str):
        await ctx.defer()
        endpoint_map = {'anime': 'anime', 'manga': 'manga', 'character': 'characters'}
        endpoint = endpoint_map[item_type]
        response_data = jikan_request(endpoint, {"q": query, "limit": 25})
        results = response_data.get('data', [])
        if not results:
            embed = discord.Embed(title="❌ No Results Found", description=f"I couldn't find any {item_type} matching your query `{query}`.", color=ERROR_COLOR)
            return await ctx.send(embed=embed)
        
        results.sort(key=lambda item: calculate_relevance_score(item, query, item_type), reverse=True)
        top_result = results[0]
        full_data_response = jikan_request(f"{endpoint}/{top_result['mal_id']}/full")
        top_result_full = full_data_response.get('data') or top_result
        
        if item_type == 'anime': embed = create_anime_embed(top_result_full)
        elif item_type == 'manga': embed = create_manga_embed(top_result_full)
        else: embed = create_character_embed(top_result_full)
        
        view = SearchView(results, item_type, ctx.author) if len(results) > 1 else None
        message = await ctx.send(embed=embed, view=view)
        if view: view.message = message

    async def handle_missing_query(ctx: commands.Context):
        msg = await ctx.send("You forgot to tell me what to search for! (´・ω・`)")
        await asyncio.sleep(5)
        try: await msg.delete()
        except discord.NotFound: pass
        try:
            if ctx.interaction is None: await ctx.message.delete()
        except (discord.Forbidden, discord.NotFound): pass

    @bot.hybrid_command(name="anime", description="Search for an anime with detailed info.")
    @app_commands.describe(query="The name of the anime you want to search for.")
    async def anime(ctx: commands.Context, *, query: Optional[str] = None):
        if query is None: return await handle_missing_query(ctx)
        await search_and_display(ctx, query, 'anime')

    @bot.hybrid_command(name="manga", description="Search for a manga with detailed info.")
    @app_commands.describe(query="The name of the manga you want to search for.")
    async def manga(ctx: commands.Context, *, query: Optional[str] = None):
        if query is None: return await handle_missing_query(ctx)
        await search_and_display(ctx, query, 'manga')

    @bot.hybrid_command(name="character", aliases=["char"], description="Search for an anime or manga character.")
    @app_commands.describe(query="The name of the character you want to search for.")
    async def character(ctx: commands.Context, *, query: Optional[str] = None):
        if query is None: return await handle_missing_query(ctx)
        await search_and_display(ctx, query, 'character')

    @bot.hybrid_command(name="topanime", description="Shows the top anime by selected category.")
    async def topanime(ctx: commands.Context):
        embed = discord.Embed(title="🏆 Top Anime Rankings", description="Please select a category from the buttons below to see the top 10 results.", color=ANIME_COLOR)
        view = TopAnimeView()
        message = await ctx.send(embed=embed, view=view)
        view.message = message

    @bot.hybrid_command(description="Show seasonal anime (e.g., /seasonal 2023 summer)")
    async def seasonal(ctx, year: Optional[int] = None, season: Optional[str] = None):
        await ctx.typing()
        try:
            current_date = datetime.now()
            if year is None: year = current_date.year
            if season is None:
                month = current_date.month
                if 3 <= month <= 5: season = 'spring'
                elif 6 <= month <= 8: season = 'summer'
                elif 9 <= month <= 11: season = 'fall'
                else: season = 'winter'
            
            response_data = jikan_request(f"seasons/{year}/{season}")
            if not (results := response_data.get('data', [])):
                return await ctx.send("❌ No seasonal anime found!", ephemeral=True)

            embed = discord.Embed(title=f"🌸 {season.capitalize()} {year}", color=SUCCESS_COLOR)
            description = ""
            for anime_item in results[:10]:
                anime_title = anime_item.get('title_english') or anime_item.get('title')
                score = anime_item.get('score', 'N/A')
                description += f"• **[{truncate_text(anime_title, 50)}]({anime_item['url']})** - ⭐ {score}\n"
            embed.description = description
            await ctx.send(embed=embed)
        except Exception as e:
            await ctx.send(f"❌ Error: {str(e)}", ephemeral=True)

    @bot.hybrid_command(description="Get MyAnimeList user profile and stats.")
    @app_commands.describe(username="The MyAnimeList username.")
    async def user(ctx, *, username: str):
        await ctx.defer()
        try:
            if not (profile := jikan_request(f"users/{username}").get('data')):
                return await ctx.send(f"❌ User '{username}' not found!", ephemeral=True)
            
            stats = jikan_request(f"users/{username}/statistics").get('data', {})
            embed = discord.Embed(title=f"👤 {profile['username']}'s Profile", url=profile["url"], color=USER_COLOR)
            if img_url := profile.get("images", {}).get("jpg", {}).get("image_url"):
                embed.set_thumbnail(url=img_url)
            if joined := profile.get("joined"):
                embed.add_field(name="Joined", value=datetime.fromisoformat(joined).strftime("%b %d, %Y"), inline=True)
            if last_online := profile.get("last_online"):
                embed.add_field(name="Last Online", value=datetime.fromisoformat(last_online).strftime("%b %d, %Y"), inline=True)
            if anime_stats := stats.get("anime"):
                embed.add_field(name="🎬 Anime Stats", value=(f"**Watching:** {format_number(anime_stats.get('watching'))}\n"
                               f"**Completed:** {format_number(anime_stats.get('completed'))}\n"
                               f"**Mean Score:** {anime_stats.get('mean_score', 0):.2f}"), inline=False)
            if manga_stats := stats.get("manga"):
                embed.add_field(name="📚 Manga Stats", value=(f"**Reading:** {format_number(manga_stats.get('reading'))}\n"
                               f"**Completed:** {format_number(manga_stats.get('completed'))}\n"
                               f"**Mean Score:** {manga_stats.get('mean_score', 0):.2f}"), inline=False)
            await ctx.send(embed=embed)
        except Exception as e:
            await ctx.send(f"❌ Error: {str(e)}", ephemeral=True)
