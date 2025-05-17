import discord
import random
from games.shared import active_challenges

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

def setup(bot):
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