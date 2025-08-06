import discord
from discord.ext import commands
import requests

# The base URL for TheCatAPI
CAT_API_URL = "https://api.thecatapi.com/v1/images/search"

def setup(bot):
    """Adds the cat command to the bot."""

    @bot.hybrid_command(description="Get a random cat picture.")
    async def cat(ctx: commands.Context):
        """Sends a random cat picture."""
        try:
            # Make a request to the Cat API
            response = requests.get(CAT_API_URL)
            response.raise_for_status()  # Raise an exception for bad status codes
            
            # Get the image URL from the JSON response
            data = response.json()
            if data and isinstance(data, list) and data[0].get("url"):
                image_url = data[0]["url"]
                
                # Create and send the embed
                embed = discord.Embed(
                    title="<a:Cat_Pat:1402647706169774181> Here's a cat for you! ₍^. .^₎Ⳋ",
                    color=0x9C27B0
                )
                embed.set_image(url=image_url)
                await ctx.send(embed=embed)
            else:
                # Handle cases where the API response is not what we expect
                await ctx.send("Sorry, I couldn't find a cat picture right now. (´・ω・`)")

        except requests.exceptions.RequestException as e:
            # Handle network-related errors
            print(f"Error fetching cat image: {e}")
            await ctx.send("Sorry, I couldn't connect to the cat API. Please try again later.")
        except Exception as e:
            # Handle other unexpected errors
            print(f"An unexpected error occurred in the cat command: {e}")
            await ctx.send("An unexpected error occurred. Please try again.")