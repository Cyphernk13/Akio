# anime/commands.py
import discord
from discord.ext import commands
from discord import app_commands
import requests
from typing import Optional, List, Dict, Any
from datetime import datetime
import asyncio
import textwrap

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
        response.raise_for_status()  # Raises an HTTPError for bad responses (4xx or 5xx)
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
    """Creates a professional and visually appealing embed for an anime."""
    title = anime.get('title_english') or anime.get('title', 'Unknown Title')
    synopsis = truncate_text(anime.get('synopsis'), 400)

    embed = discord.Embed(
        title=f"📺 {title}",
        url=anime.get('url'),
        description=synopsis,
        color=ANIME_COLOR
    )

    if image_url := anime.get('images', {}).get('jpg', {}).get('large_image_url'):
        embed.set_thumbnail(url=image_url)

    embed.add_field(name="⭐ Score", value=f"**{anime.get('score') or 'N/A'}**" if anime.get('score') else "N/A", inline=True)
    embed.add_field(name="❤️ Rank", value=f"#{format_number(anime.get('rank'))}" if anime.get('rank') else "N/A", inline=True)
    embed.add_field(name="👥 Popularity", value=f"#{format_number(anime.get('popularity'))}" if anime.get('popularity') else "N/A", inline=True)

    embed.add_field(name="🎬 Type", value=anime.get('type') or 'N/A', inline=True)
    embed.add_field(name="💿 Episodes", value=anime.get('episodes') or 'N/A', inline=True)
    embed.add_field(name="⏳ Status", value=anime.get('status') or 'N/A', inline=True)

    if studios := anime.get('studios'):
        studio_names = ', '.join([s['name'] for s in studios])
        embed.add_field(name="🏢 Studios", value=studio_names, inline=False)

    if genres := anime.get('genres'):
        genre_names = ', '.join([g['name'] for g in genres])
        embed.add_field(name="🎭 Genres", value=genre_names, inline=False)

    embed.set_footer(text=f"Aired: {anime.get('aired', {}).get('string', 'N/A')}")
    return embed

def create_manga_embed(manga: Dict[str, Any]) -> discord.Embed:
    """Creates a professional and visually appealing embed for a manga."""
    title = manga.get('title_english') or manga.get('title', 'Unknown Title')
    synopsis = truncate_text(manga.get('synopsis'), 400)

    embed = discord.Embed(
        title=f"📖 {title}",
        url=manga.get('url'),
        description=synopsis,
        color=MANGA_COLOR
    )

    if image_url := manga.get('images', {}).get('jpg', {}).get('large_image_url'):
        embed.set_thumbnail(url=image_url)

    embed.add_field(name="⭐ Score", value=f"**{manga.get('score') or 'N/A'}**" if manga.get('score') else "N/A", inline=True)
    embed.add_field(name="❤️ Rank", value=f"#{format_number(manga.get('rank'))}" if manga.get('rank') else "N/A", inline=True)
    embed.add_field(name="👥 Popularity", value=f"#{format_number(manga.get('popularity'))}" if manga.get('popularity') else "N/A", inline=True)

    embed.add_field(name="📚 Type", value=manga.get('type') or 'N/A', inline=True)
    embed.add_field(name="⏳ Status", value=manga.get('status') or 'N/A', inline=True)
    embed.add_field(name="❤️ Favorites", value=format_number(manga.get('favorites')), inline=True)

    if authors := manga.get('authors'):
        author_names = ', '.join([a['name'] for a in authors])
        embed.add_field(name="✍️ Authors", value=author_names, inline=False)

    if genres := manga.get('genres'):
        genre_names = ', '.join([g['name'] for g in genres])
        embed.add_field(name="🎭 Genres", value=genre_names, inline=False)

    embed.set_footer(text=f"Published: {manga.get('published', {}).get('string', 'N/A')}")
    return embed

def create_character_embed(char: Dict[str, Any]) -> discord.Embed:
    """Creates a professional and visually appealing embed for a character."""
    about = truncate_text(char.get('about'), 400)

    embed = discord.Embed(
        title=f"👤 {char.get('name', 'Unknown Character')}",
        url=char.get('url'),
        description=about,
        color=CHAR_COLOR
    )

    if image_url := char.get('images', {}).get('jpg', {}).get('image_url'):
        embed.set_thumbnail(url=image_url)

    embed.add_field(name="❤️ Favorites", value=format_number(char.get('favorites')), inline=True)

    if nicknames := char.get('nicknames'):
        embed.add_field(name="Alias", value=', '.join(nicknames), inline=True)

    anime_appearances = char.get('anime', [])
    if anime_appearances:
        main_anime = sorted(anime_appearances, key=lambda x: x['anime'].get('popularity', 99999))[0]
        embed.add_field(name="🎬 Main Anime", value=f"[{main_anime['anime']['title']}]({main_anime['anime']['url']})", inline=False)

    if voice_actors := char.get('voices'):
        jp_va = next((va for va in voice_actors if va['language'] == 'Japanese'), None)
        if jp_va:
            embed.set_footer(
                text=f"🇯🇵 VA: {jp_va['person']['name']}",
                icon_url=jp_va['person']['images']['jpg']['image_url']
            )
    return embed

# --- UI Components (Select Menu) ---

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
                item_type_label = item.get('type', 'N/A')
                score = item.get('score', 'N/A')
                description = f"Type: {item_type_label} | Score: {score}"
            elif item_type == 'character':
                favorites = format_number(item.get('favorites'))
                description = f"Favorites: {favorites}"

            options.append(discord.SelectOption(
                label=truncate_text(title, 100),
                description=truncate_text(description, 100) if description else None,
                value=str(i),
                emoji='🥇' if i == 0 else None
            ))

        super().__init__(placeholder="Didn't find what you were looking for? Choose here!", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.original_author.id:
            await interaction.response.send_message("You cannot interact with this menu.", ephemeral=True)
            return

        selected_index = int(self.values[0])
        selected_item = self.items[selected_index]
        mal_id = selected_item['mal_id']

        await interaction.response.defer()

        endpoint_map = {'anime': 'anime', 'manga': 'manga', 'character': 'characters'}
        item_endpoint = endpoint_map[self.item_type]
        
        endpoint = f"{item_endpoint}/{mal_id}/full"
        full_data_response = jikan_request(endpoint)
        full_data = full_data_response.get('data') if full_data_response else None

        if not full_data:
            endpoint = f"{item_endpoint}/{mal_id}"
            full_data_response = jikan_request(endpoint)
            full_data = full_data_response.get('data') if full_data_response else None

        if not full_data:
            await interaction.followup.send("Sorry, I couldn't fetch the details for that selection.", ephemeral=True)
            return

        if self.item_type == 'anime':
            embed = create_anime_embed(full_data)
        elif self.item_type == 'manga':
            embed = create_manga_embed(full_data)
        elif self.item_type == 'character':
            embed = create_character_embed(full_data)
        else:
            embed = discord.Embed(title="Error", description="Unknown item type.", color=ERROR_COLOR)

        await interaction.message.edit(content=None, embed=embed, view=None)

class SearchView(discord.ui.View):
    """A view that holds the SearchSelect menu."""
    def __init__(self, items: List[Dict[str, Any]], item_type: str, author: discord.User):
        super().__init__(timeout=120.0)
        self.message = None
        self.add_item(SearchSelect(items, item_type, author))

    async def on_timeout(self):
        if self.message:
            try:
                await self.message.edit(view=None)
            except discord.NotFound:
                pass

# --- Bot Setup ---

def setup(bot):
    def calculate_relevance_score(item: Dict[str, Any], query: str) -> int:
        """Calculates a relevance score for a search result to improve sorting."""
        score = 0
        query = query.lower()
        
        title = (item.get('title', '') or '').lower()
        title_english = (item.get('title_english', '') or '').lower()
        
        # Strong boost for exact matches
        if query == title or query == title_english:
            score += 1000
        
        # Boost for starting with the query
        if title.startswith(query) or title_english.startswith(query):
            score += 500
            
        # Add popularity score (favorites are a good metric)
        score += item.get('favorites', 0)
        
        # Add members as a general popularity metric, but weigh it less than favorites
        score += item.get('members', 0) / 10
        
        return score

    async def search_and_display(ctx: commands.Context, query: str, item_type: str):
        """A generic function to handle searching and displaying for any item type."""
        await ctx.defer()

        endpoint_map = {'anime': 'anime', 'manga': 'manga', 'character': 'characters'}
        endpoint = endpoint_map[item_type]
        
        params = {"q": query, "limit": 25}
        
        response_data = jikan_request(endpoint, params)
        results = response_data.get('data', [])

        if not results:
            embed = discord.Embed(
                title="❌ No Results Found",
                description=f"I couldn't find any {item_type} matching your query `{query}`.",
                color=ERROR_COLOR
            )
            await ctx.send(embed=embed)
            return

        # Sort results based on the custom relevance score
        results.sort(key=lambda item: calculate_relevance_score(item, query), reverse=True)

        # Intelligent Filtering to prioritize common types
        preferred_anime_types = ['TV', 'Movie', 'OVA', 'Special', 'ONA']
        preferred_manga_types = ['Manga', 'Novel', 'Light Novel', 'Manhwa', 'Manhua', 'One-shot']
        
        filtered_results = []
        if item_type == 'anime':
            filtered_results = [r for r in results if r.get('type') in preferred_anime_types]
        elif item_type == 'manga':
            filtered_results = [r for r in results if r.get('type') in preferred_manga_types]
        else: # For characters, no type filtering is needed
            filtered_results = results

        display_results = filtered_results if filtered_results else results
        
        if not display_results:
            embed = discord.Embed(
                title="❌ No Relevant Results Found",
                description=f"I found some items for `{query}`, but none were of a standard type (e.g., TV, Movie, Manga).",
                color=ERROR_COLOR
            )
            await ctx.send(embed=embed)
            return

        top_result = display_results[0]
        
        mal_id = top_result['mal_id']
        full_data_response = jikan_request(f"{endpoint}/{mal_id}/full")
        top_result_full = full_data_response.get('data') or top_result
            
        if item_type == 'anime':
            embed = create_anime_embed(top_result_full)
        elif item_type == 'manga':
            embed = create_manga_embed(top_result_full)
        elif item_type == 'character':
            embed = create_character_embed(top_result_full)
        else:
            await ctx.send("An internal error occurred.")
            return

        view = SearchView(display_results, item_type, ctx.author) if len(display_results) > 1 else None
        message = await ctx.send(embed=embed, view=view)
        if view:
            view.message = message

    @bot.hybrid_command(name="anime", description="Search for an anime with detailed info.")
    @app_commands.describe(query="The name of the anime you want to search for.")
    async def anime(ctx: commands.Context, *, query: str):
        await search_and_display(ctx, query, 'anime')

    @bot.hybrid_command(name="manga", description="Search for a manga with detailed info.")
    @app_commands.describe(query="The name of the manga you want to search for.")
    async def manga(ctx: commands.Context, *, query: str):
        await search_and_display(ctx, query, 'manga')

    @bot.hybrid_command(name="character", aliases=["char"], description="Search for an anime or manga character.")
    @app_commands.describe(query="The name of the character you want to search for.")
    async def character(ctx: commands.Context, *, query: str):
        await search_and_display(ctx, query, 'character')

    @bot.hybrid_command(name="topanime", description="Shows the top anime by selected category.")
    @app_commands.describe(filter="The category to filter by (e.g., airing, upcoming, favorite).")
    @app_commands.choices(filter=[
        app_commands.Choice(name="Top Airing", value="airing"),
        app_commands.Choice(name="Top Upcoming", value="upcoming"),
        app_commands.Choice(name="Top TV Series", value="tv"),
        app_commands.Choice(name="Top Movies", value="movie"),
        app_commands.Choice(name="Most Popular", value="bypopularity"),
        app_commands.Choice(name="Most Favorited", value="favorite"),
    ])
    async def topanime(ctx: commands.Context, filter: str = "bypopularity"):
        await ctx.defer()
        response_data = jikan_request("top/anime", {"filter": filter, "limit": 10})
        results = response_data.get('data', [])
        if not results:
            return await ctx.send(embed=discord.Embed(description="Could not fetch top anime.", color=ERROR_COLOR))

        embed = discord.Embed(
            title=f"🏆 Top 10 Anime - {filter.replace('_', ' ').title()}",
            color=SUCCESS_COLOR
        )
        description = ""
        for i, anime_data in enumerate(results, 1):
            title = anime_data.get('title_english') or anime_data.get('title')
            score = anime_data.get('score', 'N/A')
            description += f"**{i}. [{truncate_text(title, 40)}]({anime_data['url']})** - ⭐ {score}\n"

        embed.description = description
        if results[0].get('images', {}).get('jpg', {}).get('image_url'):
            embed.set_thumbnail(url=results[0]['images']['jpg']['image_url'])

        await ctx.send(embed=embed)

    @bot.hybrid_command(description="Show seasonal anime (e.g., /seasonal 2023 summer)")
    async def seasonal(ctx, year: Optional[int] = None, season: Optional[str] = None):
        await ctx.typing()
        try:
            endpoint = "seasons/now" if not year or not season else f"seasons/{year}/{season}"
            response_data = await ctx.bot.loop.run_in_executor(None, jikan_request, endpoint)
            results = response_data.get('data', [])
            if not results:
                return await ctx.send("❌ No seasonal anime found!", ephemeral=True)

            title = f"{season.capitalize()} {year}" if year and season else "Current Season Anime"
            embed = discord.Embed(title=f"🌸 {title}", color=0x4CAF50)
            
            description = ""
            for anime in results[:10]:
                anime_title = anime.get('title_english') or anime.get('title')
                score = anime.get('score', 'N/A')
                description += f"• **[{truncate_text(anime_title, 50)}]({anime['url']})** - ⭐ {score}\n"
            
            embed.description = description
            await ctx.send(embed=embed)
        except Exception as e:
            await ctx.send(f"❌ Error: {str(e)}", ephemeral=True)

    @bot.hybrid_command(description="Get MyAnimeList user profile and stats.")
    async def user(ctx, *, username: str):
        await ctx.defer()
        try:
            profile_response = jikan_request(f"users/{username}")
            profile = profile_response.get('data')
            if not profile:
                return await ctx.send(f"❌ User '{username}' not found!", ephemeral=True)
            
            stats_response = jikan_request(f"users/{username}/statistics")
            stats = stats_response.get('data') if stats_response else {}
            
            embed = discord.Embed(
                title=f"� {profile['username']}'s Profile",
                url=profile["url"],
                color=USER_COLOR
            )
            if profile.get("images", {}).get("jpg", {}).get("image_url"):
                embed.set_thumbnail(url=profile["images"]["jpg"]["image_url"])

            if joined := profile.get("joined"):
                joined_date = datetime.fromisoformat(joined).strftime("%b %d, %Y")
                embed.add_field(name="Joined", value=joined_date, inline=True)
            if last_online := profile.get("last_online"):
                last_online_date = datetime.fromisoformat(last_online).strftime("%b %d, %Y")
                embed.add_field(name="Last Online", value=last_online_date, inline=True)
            
            if anime_stats := stats.get("anime"):
                anime_field = (
                    f"**Watching:** {format_number(anime_stats.get('watching'))}\n"
                    f"**Completed:** {format_number(anime_stats.get('completed'))}\n"
                    f"**Mean Score:** {anime_stats.get('mean_score', 0):.2f}"
                )
                embed.add_field(name="🎬 Anime Stats", value=anime_field, inline=False)

            if manga_stats := stats.get("manga"):
                manga_field = (
                    f"**Reading:** {format_number(manga_stats.get('reading'))}\n"
                    f"**Completed:** {format_number(manga_stats.get('completed'))}\n"
                    f"**Mean Score:** {manga_stats.get('mean_score', 0):.2f}"
                )
                embed.add_field(name="📚 Manga Stats", value=manga_field, inline=False)

            await ctx.send(embed=embed)
        except Exception as e:
            await ctx.send(f"❌ Error: {str(e)}", ephemeral=True)