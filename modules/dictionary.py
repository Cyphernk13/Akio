import discord
from discord.ext import commands
import requests

def setup(bot):
    """Adds the dictionary command to the bot."""

    @bot.hybrid_command(name="dictionary", aliases=["dict"], description="Get the definition of a word.")
    async def dictionary(ctx: commands.Context, *, word: str):
        """Looks up a word in the dictionary."""
        await ctx.defer()
        
        try:
            # Make a request to the Dictionary API
            response = requests.get(f"https://api.dictionaryapi.dev/api/v2/entries/en/{word}")
            response.raise_for_status()
            
            data = response.json()
            
            if not data or not isinstance(data, list):
                await ctx.send(f"Sorry, I couldn't find a definition for **{word}**.")
                return

            # Create the initial embed
            word_data = data[0]
            embed = discord.Embed(
                title=f"<:Mod_Book:1402656464518250636> Definition of {word_data.get('word', word).title()}",
                description=f"**Phonetic:** {word_data.get('phonetic', 'N/A')}",
                color=discord.Color.blue()
            )

            # Add meanings to the embed
            for meaning in word_data.get('meanings', []):
                part_of_speech = meaning.get('partOfSpeech', 'N/A')
                definitions = []
                for definition_info in meaning.get('definitions', []):
                    definition = definition_info.get('definition', 'No definition available.')
                    example = definition_info.get('example')
                    def_str = f"• {definition}"
                    if example:
                        def_str += f"\n*e.g., \"{example}\"*"
                    definitions.append(def_str)
                
                if definitions:
                    embed.add_field(
                        name=f"**{part_of_speech.title()}**",
                        value="\n".join(definitions),
                        inline=False
                    )

            await ctx.send(embed=embed)

        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 404:
                await ctx.send(f"Sorry, I couldn't find a definition for **{word}**. Please check the spelling and try again.")
            else:
                await ctx.send(f"An error occurred while looking up the definition: {e}")
        except Exception as e:
            print(f"An unexpected error occurred in the dictionary command: {e}")
            await ctx.send("An unexpected error occurred. Please try again.")