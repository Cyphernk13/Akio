import discord
import random
import json
from games.shared import characters_file
def setup(bot):
    @bot.hybrid_command(description="Get drawing ideas")
    async def draw(ctx):
        try:
            with open(characters_file, 'r') as file:
                data = json.load(file)
            
            conditions = [
                "in a different show's style", "as a robot/human", "as a JoJo character",
                "fused with another character", "90's style", "as a fashion magazine cover",
                "as a pirate", "as a soul reaper", "playing a sport", "as an album cover"
            ]
            
            if 'results' in data and 'characters' in data['results']:
                character = random.choice(data['results']['characters'])
                condition = random.choice(conditions)
                
                embed = discord.Embed(
                    title="🎨 Drawing Challenge",
                    color=discord.Color.purple()
                )
                embed.add_field(name="Character", value=character['name'], inline=True)
                embed.add_field(name="Condition", value=condition, inline=True)
                # embed.set_thumbnail(url=character.get('image', 'https://i.imgur.com/3QZ2t.png'))
                await ctx.send(embed=embed)
            else:
                await ctx.send("🔴 Failed to fetch character data.")
        except Exception as e:
            await ctx.send(f"❌ An error occurred: {str(e)}")