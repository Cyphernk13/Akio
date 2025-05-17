import discord
import random
def setup(bot):
    @bot.hybrid_command(description="Flip a coin")
    async def flip(ctx):
        result = random.choice(["Heads", "Tails"])
        embed = discord.Embed(
            title="🪙 Coin Flip",
            description=f"The coin landed on: **{result}**",
            color=discord.Color.random()
        )
        # embed.set_thumbnail(url="https://i.imgur.com/5M7CwEe.png")
        await ctx.send(embed=embed)