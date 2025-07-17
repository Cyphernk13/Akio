import discord
import random
from typing import List, Tuple, Optional
from games.shared import active_challenges

class DotsAndBoxesButton(discord.ui.Button):
    def __init__(self, line_type: str, row: int, col: int, game_size: int = 3):
        """
        line_type: 'h' for horizontal, 'v' for vertical
        row, col: position of the line
        """
        super().__init__(style=discord.ButtonStyle.secondary, row=row % 5)
        self.line_type = line_type
        self.row = row
        self.col = col
        self.is_drawn = False
        
        # Set appropriate emoji based on line type
        if line_type == 'h':
            self.emoji = "➖"
        else:  # vertical
            self.emoji = "🔸"
            
        self.label = "\u200b"  # Invisible character

    async def callback(self, interaction: discord.Interaction):
        view: DotsAndBoxesView = self.view
        
        if view.game_over:
            await interaction.response.send_message("🏁 Game is already over!", ephemeral=True)
            return

        # Check if it's the correct player's turn
        if interaction.user != view.current_player:
            await interaction.response.send_message("❌ It's not your turn!", ephemeral=True)
            return

        # Check if line is already drawn
        if self.is_drawn:
            await interaction.response.send_message("❌ This line is already drawn!", ephemeral=True)
            return

        # Draw the line
        self.is_drawn = True
        self.style = discord.ButtonStyle.primary
        self.disabled = True
        
        # Update the game state
        if self.line_type == 'h':
            view.horizontal_lines[self.row][self.col] = True
        else:
            view.vertical_lines[self.row][self.col] = True

        # Check for completed boxes and award points
        boxes_completed = view.check_completed_boxes(self.line_type, self.row, self.col)
        
        if boxes_completed > 0:
            # Player gets another turn for completing box(es)
            view.scores[view.current_player] += boxes_completed
            content = f"🎉 {view.current_player.mention} completed {boxes_completed} box{'es' if boxes_completed > 1 else ''}! Go again!\n\n"
        else:
            # Switch turns
            view.switch_turn()
            content = f"➡️ {view.current_player.mention}'s turn\n\n"

        # Check if game is over
        if view.is_game_over():
            winner = view.get_winner()
            if winner:
                content = f"🏆 **GAME OVER!** 🏆\n{winner.mention} wins!\n\n"
            else:
                content = f"🤝 **GAME OVER!** It's a tie!\n\n"
            
            view.game_over = True
            view.stop()
            for child in view.children:
                child.disabled = True

        # Update the embed with current game state
        embed = view.create_game_embed()
        await interaction.response.edit_message(content=content, embed=embed, view=view)

class DotsAndBoxesView(discord.ui.View):
    def __init__(self, player1: discord.Member, player2: discord.Member, game_size: int = 3):
        super().__init__(timeout=300)  # 5 minutes timeout
        
        self.player1 = player1
        self.player2 = player2
        self.current_player = player1
        self.game_size = game_size
        self.game_over = False
        
        # Initialize scores
        self.scores = {player1: 0, player2: 0}
        
        # Initialize line states
        # horizontal_lines[row][col] represents horizontal line between dots
        self.horizontal_lines = [[False for _ in range(game_size)] for _ in range(game_size + 1)]
        # vertical_lines[row][col] represents vertical line between dots
        self.vertical_lines = [[False for _ in range(game_size + 1)] for _ in range(game_size)]
        
        # Track completed boxes for visual representation
        self.completed_boxes = [[None for _ in range(game_size)] for _ in range(game_size)]
        
        self.setup_buttons()

    def setup_buttons(self):
        """Setup all the line buttons in a compact layout"""
        buttons = []
        
        # For a 3x3 grid, we need:
        # - 4 rows of 3 horizontal lines each = 12 horizontal lines
        # - 3 rows of 4 vertical lines each = 12 vertical lines
        # Total: 24 buttons (perfect for Discord's 25 limit)
        
        button_count = 0
        
        # Add horizontal lines
        for row in range(self.game_size + 1):
            for col in range(self.game_size):
                if button_count < 25:  # Discord limit
                    btn = DotsAndBoxesButton('h', row, col, self.game_size)
                    buttons.append(btn)
                    button_count += 1
        
        # Add vertical lines
        for row in range(self.game_size):
            for col in range(self.game_size + 1):
                if button_count < 25:  # Discord limit
                    btn = DotsAndBoxesButton('v', row, col, self.game_size)
                    buttons.append(btn)
                    button_count += 1
        
        # Add buttons to view (Discord automatically arranges them in rows of 5)
        for btn in buttons:
            self.add_item(btn)

    def switch_turn(self):
        """Switch to the other player"""
        self.current_player = self.player2 if self.current_player == self.player1 else self.player1

    def check_completed_boxes(self, line_type: str, row: int, col: int) -> int:
        """Check how many boxes were completed by drawing this line"""
        completed = 0
        
        if line_type == 'h':
            # Check box above
            if row > 0:
                if self.is_box_complete(row - 1, col):
                    if not self.completed_boxes[row - 1][col]:
                        self.completed_boxes[row - 1][col] = self.current_player
                        completed += 1
            
            # Check box below
            if row < self.game_size:
                if self.is_box_complete(row, col):
                    if not self.completed_boxes[row][col]:
                        self.completed_boxes[row][col] = self.current_player
                        completed += 1
        
        else:  # vertical line
            # Check box to the left
            if col > 0:
                if self.is_box_complete(row, col - 1):
                    if not self.completed_boxes[row][col - 1]:
                        self.completed_boxes[row][col - 1] = self.current_player
                        completed += 1
            
            # Check box to the right
            if col < self.game_size:
                if self.is_box_complete(row, col):
                    if not self.completed_boxes[row][col]:
                        self.completed_boxes[row][col] = self.current_player
                        completed += 1
        
        return completed

    def is_box_complete(self, box_row: int, box_col: int) -> bool:
        """Check if a specific box is complete (all 4 sides drawn)"""
        # Top horizontal line
        top = self.horizontal_lines[box_row][box_col]
        # Bottom horizontal line
        bottom = self.horizontal_lines[box_row + 1][box_col]
        # Left vertical line
        left = self.vertical_lines[box_row][box_col]
        # Right vertical line
        right = self.vertical_lines[box_row][box_col + 1]
        
        return top and bottom and left and right

    def is_game_over(self) -> bool:
        """Check if all possible lines have been drawn"""
        total_lines = (self.game_size + 1) * self.game_size + self.game_size * (self.game_size + 1)
        drawn_lines = 0
        
        for row in self.horizontal_lines:
            drawn_lines += sum(row)
        for row in self.vertical_lines:
            drawn_lines += sum(row)
            
        return drawn_lines == total_lines

    def get_winner(self) -> Optional[discord.Member]:
        """Get the winner or None if tie"""
        if self.scores[self.player1] > self.scores[self.player2]:
            return self.player1
        elif self.scores[self.player2] > self.scores[self.player1]:
            return self.player2
        return None

    def create_visual_grid(self) -> str:
        """Create a visual representation of the current game state"""
        grid = []
        
        for row in range(self.game_size + 1):
            # Dot row
            dot_line = ""
            for col in range(self.game_size + 1):
                dot_line += "🔹"  # Dot
                if col < self.game_size:
                    # Horizontal line
                    if self.horizontal_lines[row][col]:
                        dot_line += "━━"
                    else:
                        dot_line += "  "
            grid.append(dot_line)
            
            # Box row (if not the last row)
            if row < self.game_size:
                box_line = ""
                for col in range(self.game_size + 1):
                    # Vertical line
                    if self.vertical_lines[row][col]:
                        box_line += "┃"
                    else:
                        box_line += " "
                    
                    if col < self.game_size:
                        # Box content
                        if self.completed_boxes[row][col]:
                            if self.completed_boxes[row][col] == self.player1:
                                box_line += "🔴"  # Player 1's box
                            else:
                                box_line += "🔵"  # Player 2's box
                        else:
                            box_line += "  "
                grid.append(box_line)
        
        return "\n".join(grid)

    def create_game_embed(self) -> discord.Embed:
        """Create a beautiful embed showing the game state"""
        embed = discord.Embed(
            title="🎯 Dots and Boxes",
            description="Draw lines to complete boxes and score points!",
            color=0x00ff00 if self.current_player == self.player1 else 0xff0000
        )
        
        # Add the visual grid
        grid_visual = self.create_visual_grid()
        if len(grid_visual) <= 1024:  # Discord field limit
            embed.add_field(
                name="🎮 Game Board",
                value=f"```\n{grid_visual}\n```",
                inline=False
            )
        
        # Player scores
        embed.add_field(
            name=f"🔴 {self.player1.display_name}",
            value=f"**{self.scores[self.player1]}** boxes",
            inline=True
        )
        
        embed.add_field(
            name=f"🔵 {self.player2.display_name}",
            value=f"**{self.scores[self.player2]}** boxes",
            inline=True
        )
        
        # Current turn indicator
        if not self.game_over:
            embed.add_field(
                name="🎯 Current Turn",
                value=f"{self.current_player.mention}",
                inline=True
            )
        
        # Game instructions
        if not self.game_over:
            embed.add_field(
                name="📋 How to Play",
                value="Click buttons to draw lines!\n➖ = Horizontal lines\n🔸 = Vertical lines\n\nComplete boxes to score points!",
                inline=False
            )
        
        # Footer with game info
        total_boxes = self.game_size * self.game_size
        completed_boxes = sum(self.scores.values())
        embed.set_footer(text=f"Boxes completed: {completed_boxes}/{total_boxes} | Game size: {self.game_size}x{self.game_size}")
        
        return embed

def setup(bot):
    @bot.hybrid_command(description="Play Dots and Boxes with another player")
    async def dots(ctx, opponent: discord.Member, size: int = 3):
        """
        Start a game of Dots and Boxes
        
        Parameters:
        - opponent: The player to challenge
        - size: Grid size (2-4, default 3). Larger sizes may exceed Discord button limits.
        """
        
        # Validation
        if opponent == ctx.author:
            await ctx.send("❌ You can't play against yourself!", ephemeral=True)
            return
            
        if opponent.bot:
            await ctx.send("❌ You can't play against a bot!", ephemeral=True)
            return
            
        if size < 2 or size > 4:
            await ctx.send("❌ Grid size must be between 2 and 4!", ephemeral=True)
            return
            
        # Check button limit (rough calculation)
        total_buttons = (size + 1) * size + size * (size + 1)
        if total_buttons > 25:
            await ctx.send(f"❌ Grid size {size}x{size} requires {total_buttons} buttons, which exceeds Discord's 25 button limit!\nTry a smaller grid size.", ephemeral=True)
            return
        
        # Check if players are already in a game
        game_key = f"{ctx.author.id}_{opponent.id}"
        reverse_key = f"{opponent.id}_{ctx.author.id}"
        
        if game_key in active_challenges or reverse_key in active_challenges:
            await ctx.send("❌ One of you is already in a game! Finish your current game first.", ephemeral=True)
            return
        
        # Add to active games
        active_challenges[game_key] = True
        
        try:
            # Create the game
            view = DotsAndBoxesView(ctx.author, opponent, size)
            embed = view.create_game_embed()
            
            await ctx.send(
                f"🎯 **Dots and Boxes Game Started!**\n"
                f"🔴 {ctx.author.mention} vs 🔵 {opponent.mention}\n"
                f"🎲 Grid Size: {size}x{size}\n"
                f"🎮 {ctx.author.mention} goes first!\n\n"
                f"Draw lines by clicking the buttons. Complete boxes to score points!",
                embed=embed,
                view=view
            )
            
        except Exception as e:
            # Clean up if something goes wrong
            if game_key in active_challenges:
                del active_challenges[game_key]
            await ctx.send(f"❌ An error occurred while starting the game: {str(e)}", ephemeral=True)
        
        # Clean up when game ends
        async def cleanup():
            if game_key in active_challenges:
                del active_challenges[game_key]
        
        view.add_callback = cleanup

    @bot.hybrid_command(description="View Dots and Boxes leaderboard")
    async def dotsleaderboard(ctx):
        """Show the Dots and Boxes leaderboard"""
        # This would require implementing a persistent leaderboard system
        # For now, just show a placeholder
        embed = discord.Embed(
            title="🏆 Dots and Boxes Leaderboard",
            description="Leaderboard feature coming soon!",
            color=0xffd700
        )
        embed.add_field(
            name="📊 Stats Tracked",
            value="• Games Won\n• Total Boxes Completed\n• Win Rate\n• Average Points per Game",
            inline=False
        )
        await ctx.send(embed=embed)