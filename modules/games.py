import discord
from discord.ext import commands
import random
import asyncio
import json
from ai.meta_ai import ai

characters_file = "modules/characters.json"
leaderboard = {}
active_challenges = {}

# ---------------------------- ENHANCED COMMANDS ---------------------------- #
class RPSView(discord.ui.View):
    def __init__(self, players, challenger_choice=None):
        super().__init__(timeout=30)
        self.players = players
        self.choices = {}
        self.challenger_choice = challenger_choice
        self.challenger_id = players[0].id if len(players) > 1 else None

    async def on_timeout(self):
        # Cleanup active challenges
        if self.challenger_id and self.challenger_id in active_challenges:
            del active_challenges[self.challenger_id]
        
        # Disable buttons and update message
        for child in self.children:
            child.disabled = True
            
        embed = discord.Embed(
            title="⏰ Challenge Expired",
            description="The challenge timed out due to inactivity.",
            color=discord.Color.dark_grey()
        )
        try:
            await self.message.edit(embed=embed, view=self)
        except discord.NotFound:
            pass

    @discord.ui.button(label="🪨 Rock", style=discord.ButtonStyle.primary)
    async def rock(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.handle_choice(interaction, "rock")

    @discord.ui.button(label="📄 Paper", style=discord.ButtonStyle.success)
    async def paper(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.handle_choice(interaction, "paper")

    @discord.ui.button(label="✂️ Scissors", style=discord.ButtonStyle.danger)
    async def scissors(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.handle_choice(interaction, "scissors")

    async def handle_choice(self, interaction: discord.Interaction, choice: str):
        if interaction.user.id not in [p.id for p in self.players]:
            await interaction.response.send_message("❌ You're not part of this game!", ephemeral=True)
            return

        self.choices[interaction.user.id] = choice
        await interaction.response.send_message(f"✅ You chose {choice}!", ephemeral=True)

        if len(self.choices) == len(self.players):
            await self.resolve_game(interaction)

    async def resolve_game(self, interaction: discord.Interaction):
        choices = list(self.choices.values())
        if len(self.players) == 1:
            user = self.players[0]
            bot_choice = random.choice(['rock', 'paper', 'scissors'])
            user_choice = choices[0]
            result_text = self.get_result(user_choice, bot_choice)
            # Determine winner
            if user_choice == bot_choice:
                winner_mention = "No one! It's a tie."
            elif (user_choice, bot_choice) in [('rock', 'scissors'), ('paper', 'rock'), ('scissors', 'paper')]:
                winner_mention = user.mention
            else:
                winner_mention = f"{interaction.client.user.mention}"

            embed = discord.Embed(
                title="Rock Paper Scissors",
                description=(
                    f"{user.mention} chose {user_choice}\n"
                    f"<:Hehe:1228485647786840104> I chose {bot_choice}\n\n"
                    f"**Result:** {result_text}\n"
                    f"**Winner:** {winner_mention}"
                ),
                color=discord.Color.blurple()
            )
            await interaction.message.edit(embed=embed, view=None)
        else:
            p1, p2 = self.players
            c1, c2 = self.choices[p1.id], self.choices[p2.id]
            result_text = self.get_result(c1, c2)
            # Determine winner
            if c1 == c2:
                winner_mention = "No one! It's a tie."
            elif (c1, c2) in [('rock', 'scissors'), ('paper', 'rock'), ('scissors', 'paper')]:
                winner_mention = p1.mention
            else:
                winner_mention = p2.mention

            embed = discord.Embed(
                title="Multiplayer RPS 🎮",
                description=(
                    f"{p1.mention} chose {c1}\n"
                    f"{p2.mention} chose {c2}\n\n"
                    f"**Result:** {result_text}\n"
                    f"**Winner:** {winner_mention}"
                ),
                color=discord.Color.gold()
            )
            await interaction.message.edit(embed=embed, view=None)
        self.stop()


    def get_result(self, choice1, choice2):
        outcomes = {
            ('rock', 'scissors'): "🪨 Rock smashes scissors!",
            ('paper', 'rock'): "📄 Paper covers rock!",
            ('scissors', 'paper'): "✂️ Scissors cut paper!",
        }
        if choice1 == choice2:
            return "🤝 It's a tie!"
        return outcomes.get((choice1, choice2), "❌ You lose!") if (choice1, choice2) in outcomes else outcomes.get((choice2, choice1), "✅ You win!")

class TicTacToeButton(discord.ui.Button):
    def __init__(self, x: int, y: int):
        super().__init__(style=discord.ButtonStyle.secondary, label='\u200b', row=y)
        self.x = x
        self.y = y

    async def callback(self, interaction: discord.Interaction):
        view: TicTacToeView = self.view
        if view.game_over:
            await interaction.response.send_message("Game is already over!", ephemeral=True)
            return

        # Only allow the correct player to make a move
        if interaction.user != view.current_player and not view.is_bot_turn():
            await interaction.response.send_message("❌ It's not your turn!", ephemeral=True)
            return

        if view.board[self.y][self.x] != 0:
            await interaction.response.send_message("❌ That spot is already taken!", ephemeral=True)
            return

        mark = view.player_marks[view.current_player]
        self.style = discord.ButtonStyle.danger if mark == "X" else discord.ButtonStyle.success
        self.label = mark
        self.disabled = True
        view.board[self.y][self.x] = mark

        winner = view.check_winner()
        if winner:
            content = f"🎉 {view.current_player.mention if winner != 'Bot' else interaction.client.user.mention} ({mark}) wins!"
            for child in view.children:
                child.disabled = True
            view.game_over = True
            view.stop()
        elif all(cell != 0 for row in view.board for cell in row):
            content = "🤝 It's a tie!"
            for child in view.children:
                child.disabled = True
            view.game_over = True
            view.stop()
        else:
            view.next_turn()
            content = f"It's now {view.current_player.mention if view.current_player else interaction.client.user.mention}'s turn ({view.player_marks[view.current_player] if view.current_player else view.bot_mark})"

        await interaction.response.edit_message(content=content, view=view)

        # If it's the bot's turn, make a move
        if view.is_bot_turn() and not view.game_over:
            await view.bot_move(interaction)

class TicTacToeView(discord.ui.View):
    def __init__(self, player1: discord.Member, player2: discord.Member = None, bot=None):
        super().__init__(timeout=60)
        self.players = [player1]
        self.bot = bot
        self.bot_mark = "O"
        self.game_over = False
        if player2:
            self.players.append(player2)
            self.player_marks = {player1: "X", player2: "O"}
            self.current_player = player1
        else:
            self.player_marks = {player1: "X"}
            self.current_player = player1  # user always goes first
        self.board = [[0, 0, 0] for _ in range(3)]
        for y in range(3):
            for x in range(3):
                self.add_item(TicTacToeButton(x, y))

    def check_winner(self):
        # Check rows, columns, and diagonals
        for i in range(3):
            if self.board[i][0] == self.board[i][1] == self.board[i][2] != 0:
                return self.board[i][0]
            if self.board[0][i] == self.board[1][i] == self.board[2][i] != 0:
                return self.board[0][i]
        if self.board[0][0] == self.board[1][1] == self.board[2][2] != 0:
            return self.board[0][0]
        if self.board[0][2] == self.board[1][1] == self.board[2][0] != 0:
            return self.board[0][2]
        return None

    def next_turn(self):
        if len(self.players) == 2:
            self.current_player = self.players[1] if self.current_player == self.players[0] else self.players[0]
        else:
            # Singleplayer: user then bot
            self.current_player = None if self.current_player is not None else self.players[0]

    def is_bot_turn(self):
        return len(self.players) == 1 and self.current_player is None

    async def bot_move(self, interaction):
        # Find all empty spots
        empty = [(y, x) for y in range(3) for x in range(3) if self.board[y][x] == 0]
        if not empty:
            return
        y, x = random.choice(empty)
        # Find the button and simulate a click
        for child in self.children:
            if isinstance(child, TicTacToeButton) and child.x == x and child.y == y:
                # Mark the board for the bot
                child.style = discord.ButtonStyle.success
                child.label = self.bot_mark
                child.disabled = True
                self.board[y][x] = self.bot_mark
                winner = self.check_winner()
                if winner:
                    content = f"🎉 {interaction.client.user.mention} ({self.bot_mark}) wins!"
                    for c in self.children:
                        c.disabled = True
                    self.game_over = True
                    self.stop()
                elif all(cell != 0 for row in self.board for cell in row):
                    content = "🤝 It's a tie!"
                    for c in self.children:
                        c.disabled = True
                    self.game_over = True
                    self.stop()
                else:
                    self.current_player = self.players[0]
                    content = f"It's now {self.current_player.mention}'s turn (X)"
                await interaction.message.edit(content=content, view=self)
                break
class LoveView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=60)
        
    @discord.ui.button(label="Re-calculate 💖", style=discord.ButtonStyle.red)
    async def recalculate(self, interaction: discord.Interaction, button: discord.ui.Button):
        new_percentage = random.randint(1, 100)
        embed = interaction.message.embeds[0]
        embed.set_field_at(0, name=embed.fields[0].name, value=f"Love Percentage: {new_percentage}%")
        await interaction.response.edit_message(embed=embed)

def setup(bot):
    @bot.hybrid_command(description="Ask the bot anything")
    async def query(ctx, *, question: str):
        response = await ai(question)
        await ctx.send(response)

    @bot.listen("on_message")
    async def handle_mentions(message):
        if message.author == bot.user:
            return
        if bot.user in message.mentions:
            question = message.content.replace(f"<@{bot.user.id}>", "").strip()
            response = await ai(question)
            await message.channel.send(response)

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

    @bot.hybrid_command(description="Play rock-paper-scissors against the bot or another user")
    async def rps(ctx, opponent: discord.Member = None):
        if opponent and opponent == ctx.author:
            await ctx.send("❌ You can't challenge yourself!", ephemeral=True)
            return
        if opponent and opponent.bot:
            await ctx.send("❌ You can't challenge bots!", ephemeral=True)
            return

        try:
            if opponent:
                if ctx.author.id in active_challenges:
                    await ctx.send("❌ You already have an active challenge!", ephemeral=True)
                    return
                    
                embed = discord.Embed(
                    title="🎮 RPS Challenge!",
                    description=f"{opponent.mention}, you've been challenged by {ctx.author.mention}!\nClick a button below to accept:",
                    color=discord.Color.green()
                )
                view = RPSView(players=[ctx.author, opponent])
                active_challenges[ctx.author.id] = (opponent.id, view)
                message = await ctx.send(embed=embed, view=view)
                view.message = message  # Store message reference for timeout handling
            else:
                embed = discord.Embed(
                    title="Rock Paper Scissors",
                    description="Choose your move:",
                    color=discord.Color.blue()
                )
                view = RPSView(players=[ctx.author])
                await ctx.send(embed=embed, view=view)
        
        except Exception as e:
            # Cleanup if something goes wrong
            if ctx.author.id in active_challenges:
                del active_challenges[ctx.author.id]
            raise e

    @bot.hybrid_command(description="Calculate love percentage")
    async def love(ctx, user1: discord.Member, user2: discord.Member):
        embed = discord.Embed(title="💖 Love Calculator", color=discord.Color.red())
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
                embed.description = f"Awww {bot.user.name} loves you a lot! ( ´･･)ﾉ(･･ ˶)\nLove Percentage: {love_percentage}%"
            else:
                embed.add_field(
                    name=f"{user1_name} ❤️ {user2_name}",
                    value=f"Love Percentage: {love_percentage}%",
                    inline=False
                )
                # embed.set_thumbnail(url="https://i.imgur.com/sW3QF5O.png")
                embed.set_footer(text="Click the button below to re-calculate")
                view = LoveView()
                await ctx.send(embed=embed, view=view)
                return
        await ctx.send(embed=embed)

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
    
    @bot.hybrid_command(description="Play Tic Tac Toe with another user or the bot")
    async def tictactoe(ctx, opponent: discord.Member = None):
        if opponent and opponent == ctx.author:
            await ctx.send("❌ You can't play against yourself!", ephemeral=True)
            return
        if opponent and opponent.bot:
            await ctx.send("❌ You can't play against another bot!", ephemeral=True)
            return

        if opponent:
            view = TicTacToeView(ctx.author, opponent)
            await ctx.send(
                f"Tic Tac Toe: {ctx.author.mention} (X) vs {opponent.mention} (O)\n{ctx.author.mention} goes first!",
                view=view
            )
        else:
            view = TicTacToeView(ctx.author, bot=ctx.bot)
            await ctx.send(
                f"Tic Tac Toe: {ctx.author.mention} (X) vs {ctx.bot.user.mention} (O)\n{ctx.author.mention} goes first!",
                view=view
            )
    @bot.hybrid_command(description="Cancel your active challenge")
    async def cancel(ctx):
        if ctx.author.id in active_challenges:
            del active_challenges[ctx.author.id]
            await ctx.send("✅ Your active challenge has been canceled!", ephemeral=True)
        else:
            await ctx.send("❌ You don't have any active challenges!", ephemeral=True)

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
