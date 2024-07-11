import discord
from discord.ext import commands
import random
import asyncio
import json
from meta_ai import ai

characters_file = "characters.json"
leaderboard = {}


def setup(bot):

    @bot.command()
    async def query(ctx, *, question: str):
        response = await ai(question)
        # print(f"MetaAI response: {response}")  # Debugging line
        await ctx.send(response)

    @bot.command()
    async def guess(ctx):
        number = random.randint(1, 100)
        attempts = 0

        await ctx.send("I'm thinking of a number between 1 and 100. Can you guess it?")

        def check(message):
            return message.author == ctx.author and message.channel == ctx.channel and message.content.isdigit()

        while True:
            try:
                guess = await bot.wait_for("message", check=check, timeout=30)
                guess = int(guess.content)
            except asyncio.TimeoutError:
                await ctx.send("Time's up! You took too long to guess.")
                return

            attempts += 1

            if guess < number:
                await ctx.send("Too low! Try guessing a higher number.")
            elif guess > number:
                await ctx.send("Too high! Try guessing a lower number.")
            else:
                await ctx.send(f"Congratulations! You guessed the number {number} correctly in {attempts} attempts!")

                user_id = str(ctx.author.id)
                if user_id not in leaderboard or attempts < leaderboard[user_id]:
                    leaderboard[user_id] = attempts

                return

    @bot.command()
    async def guess_lead(ctx):
        if leaderboard:
            sorted_leaderboard = sorted(leaderboard.items(), key=lambda x: x[1])
            leaderboard_embed = discord.Embed(title="Leaderboard", color=discord.Color.blue())
            for index, (user_id, attempts) in enumerate(sorted_leaderboard, start=1):
                member = ctx.guild.get_member(int(user_id))
                if member:
                    leaderboard_embed.add_field(name=f"#{index} {member.display_name}", value=f"Attempts: {attempts}", inline=False)
            await ctx.send(embed=leaderboard_embed)
        else:
            await ctx.send("No leaderboard data available.")

    @bot.command()
    async def rps(ctx):
        choices = ['rock', 'paper', 'scissors']
        abbreviations = {'r': 'rock', 'p': 'paper', 's': 'scissors'}
        user = ctx.author

        await ctx.send(f'{user.mention}, choose your move: rock (r), paper (p), or scissors (s).')

        def check(message):
            return message.author == user and (message.content.lower() in choices or message.content.lower() in abbreviations)

        try:
            user_choice = await bot.wait_for('message', check=check, timeout=30)
        except asyncio.TimeoutError:
            await ctx.send(f'{user.mention}, you took too long to make a choice. Game over.')
            return

        user_choice = user_choice.content.lower()
        user_choice = abbreviations.get(user_choice, user_choice)

        bot_choice = random.choice(choices)

        await ctx.send(f'{user.mention} chose {user_choice}, and I chose {bot_choice}.')

        if user_choice == bot_choice:
            await ctx.send("It's a tie!")
        elif (
            (user_choice == 'rock' and bot_choice == 'scissors')
            or (user_choice == 'paper' and bot_choice == 'rock')
            or (user_choice == 'scissors' and bot_choice == 'paper')
        ):
            await ctx.send(f'{user.mention} wins!')
        else:
            await ctx.send(f'I win! {user.mention} loses.')
    @bot.command()
    async def ask(ctx, *, question):
        responses = [
        "It is certain.",
        "It is decidedly so.",
        "Without a doubt.",
        "Yes definitely.",
        "You may rely on it.",
        "As I see it, yes.",
        "Most likely.",
        "Outlook good.",
        "Yes.",
        "Signs point to yes.",
        "Reply hazy, try again.",
        "Ask again later.",
        "Better not tell you now.",
        "Cannot predict now.",
        "Concentrate and ask again.",
        "Don't count on it.",
        "My reply is no.",
        "My sources say no.",
        "Outlook not so good.",
        "Very doubtful."
    ]
        # Randomly select a response from the list
        response = random.choice(responses)

        # Create and send an embedded message with the response
        embed = discord.Embed(
            title="Magic 8-Ball",
            description=f"**Question:** {question}\n**Answer:** {response}",
            color=discord.Color.random()
        )
        await ctx.send(embed=embed)

    @bot.command()
    async def flip(ctx):
        # Randomly choose "Heads" or "Tails"
        result = random.choice(["Heads", "Tails"])

        # Create and send an embedded message with the result
        embed = discord.Embed(
            title="Coin Flip",
            description=f"The coin landed on: **{result}**",
            color=discord.Color.random()
        )
        await ctx.send(embed=embed)

    @bot.command()
    async def draw(ctx):
        global characters_file  
        try:
            with open(characters_file, 'r') as file:
                data = json.load(file)
            
            dumb_conditions = ["in a different shows style","but as a robot (or human if already a robot)","as a JoJo character","fused with another character","90's style","as a fashion magazine cover","as a pirate","as a soul reaper","but another alignment (good/evil)","playing a sport","hanging out with a character from another show","as an album cover","eating a burrito","looking exceptionally bad ass","relaxing by the pool","as a fish","as any animal","as a superhero","as a magical girl","in a kimono or hakama or yukata whichever u want","playing a sport","with a social media acc","ready for Halloween","celebrating Xmas","meditating","cooking","on the computer",
            ]
            if 'results' in data and 'characters' in data['results']:
                characters = data['results']['characters']
                names = [character['name'] for character in characters]
                random_name = random.choice(names)
                random_condition = random.choice(dumb_conditions)
                await ctx.send(f"Draw {random_name}, {random_condition}.")
            else:
                await ctx.send("Failed to fetch character data.")
        except Exception as e:
            await ctx.send(f"An error occurred: {e}")

    @bot.command()
    async def love(ctx, user1: discord.Member, user2: discord.Member):
        embed = discord.Embed(title="Love Calculator", color=discord.Color.red())
        if user1 == user2:
            love_percentage = 101
            user1_name = user1.nick if user1.nick else user1.name
            embed.description = f"{user1_name} loves themselves the most! 💖\nLove Percentage: {love_percentage}%"
        else:
            love_percentage = random.randint(1, 100)
            user1_name = user1.nick if user1.nick else user1.name
            user2_name = user2.nick if user2.nick else user2.name
            if bot.user in [user1, user2]:
                love_percentage = 100
                embed.description = f"Awww akio loves you a lot, {ctx.author.nick or ctx.author.name}! ( ´･･)ﾉ(･･ `˶)\nLove Percentage: {love_percentage}%"
            else:
                embed.add_field(name=f"{user1_name} ❤️ {user2_name}", value=f"Love Percentage: {love_percentage}%")
        await ctx.send(embed=embed)

