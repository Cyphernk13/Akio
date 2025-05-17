import discord
import random
import asyncio
from games.shared import leaderboard
def setup(bot):
    @bot.hybrid_command(description="Play a number guessing game")
    async def guess(ctx):
        number = random.randint(1, 100)
        attempts = 0

        embed = discord.Embed(
            title="Number Guessing Game",
            description="I'm thinking of a number between 1 and 100. Can you guess it?",
            color=discord.Color.blue()
        )
        await ctx.send(embed=embed)

        def check(message):
            return message.author == ctx.author and message.channel == ctx.channel and message.content.isdigit()

        while True:
            try:
                guess = await bot.wait_for("message", check=check, timeout=30)
                guess = int(guess.content)
            except asyncio.TimeoutError:
                await ctx.send("⏰ Time's up! You took too long to guess.")
                return

            attempts += 1

            if guess < number:
                await ctx.send("🔻 Too low! Try guessing a higher number.")
            elif guess > number:
                await ctx.send("🔺 Too high! Try guessing a lower number.")
            else:
                win_embed = discord.Embed(
                    title="Congratulations! 🎉",
                    description=f"You guessed the number {number} correctly in {attempts} attempts!",
                    color=discord.Color.green()
                )
                await ctx.send(embed=win_embed)

                user_id = str(ctx.author.id)
                if user_id not in leaderboard or attempts < leaderboard[user_id]:
                    leaderboard[user_id] = attempts
                return