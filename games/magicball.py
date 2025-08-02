import discord
from discord.ext import commands
import requests

# --- Constants ---
API_URL = "https://eightballapi.com/api"
THUMBNAIL_URL = "https://i.imgur.com/ThgTXjU.jpeg" # A generic 8-ball image for the embed thumbnail

def setup(bot: commands.Bot):
    """This function is called by discord.py to load the command."""

    @bot.hybrid_command(name="8ball", aliases=['8b'], description="Ask the magic 8-ball a question.")
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def eight_ball(ctx: commands.Context, *, question: str):
        """
        Consult the Magic 8-Ball for an answer to your question.

        Args:
            question (str): The yes/no question you want to ask.
        """
        # Defer the response to let the user know the bot is working on it.
        await ctx.defer()

        try:
            # Make the GET request to the API
            response = requests.get(API_URL)
            # Raise an HTTPError if the HTTP request returned an unsuccessful status code
            response.raise_for_status()
            
            data = response.json()
            answer = data.get("reading")

        except requests.exceptions.RequestException as e:
            # Handle cases where the API is down or the request fails
            print(f"8-Ball API Error: {e}")
            answer = "Sorry, my crystal ball is cloudy right now. Try again later."

        # Create a nicely formatted embed for the response
        embed = discord.Embed(
            title="🔮 Magic 8-Ball",
            color=discord.Color.dark_purple()
        )
        embed.set_author(name=ctx.author.display_name, icon_url=ctx.author.avatar.url)
        embed.add_field(name="❓ Your Question", value=question, inline=False)
        embed.add_field(name="💬 My Answer", value=answer, inline=False)
        embed.set_thumbnail(url=THUMBNAIL_URL)

        # Send the final embed as the response
        await ctx.send(embed=embed)