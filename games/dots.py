import discord
import random
from typing import List, Tuple, Optional
from games.shared import active_challenges

class DotsAndBoxesButton(discord.ui.Button):
    def __init__(self, line_id: str, line_type: str, row: int, col: int, button_row: int = 0):
        """
        line_id: unique identifier for this line
        line_type: 'h' for horizontal, 'v' for vertical
        row, col: position of the line in the grid
        button_row: which UI row this button should be in
        """
        super().__init__(style=discord.ButtonStyle.secondary, row=button_row)
        self.line_id = line_id
        self.line_type = line_type
        self.row = row
        self.col = col
        self.is_drawn = False
        
        # Set simple, clear labels
        if line_type == 'h':
            self.emoji = "➖"
            self.label = f"━ {line_id}"
        else:  # vertical
            self.emoji = "⬜"
            self.label = f"┃ {line_id}"

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
        self.style = discord.ButtonStyle.success
        self.disabled = True
        self.label = f"✅ {self.line_id}"
        
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
            
            # Clean up active game when finished
            game_key = f"{view.player1.id}_{view.player2.id}"
            reverse_key = f"{view.player2.id}_{view.player1.id}"
            if game_key in active_challenges:
                del active_challenges[game_key]
            if reverse_key in active_challenges:
                del active_challenges[reverse_key]

        # Update the embed with current game state
        embed = view.create_game_embed()
        await interaction.response.edit_message(content=content, embed=embed, view=view)

class DotsAndBoxesView(discord.ui.View):
    def __init__(self, player1: discord.Member, player2: discord.Member, game_size: int = 2):
        super().__init__(timeout=300)  # 5 minutes timeout
        
        self.player1 = player1
        self.player2 = player2
        self.current_player = player1
        self.game_size = game_size
        self.game_over = False
        
        # Initialize scores
        self.scores = {player1: 0, player2: 0}
        
        # Initialize line states
        self.horizontal_lines = [[False for _ in range(game_size)] for _ in range(game_size + 1)]
        self.vertical_lines = [[False for _ in range(game_size + 1)] for _ in range(game_size)]
        
        # Track completed boxes for visual representation
        self.completed_boxes = [[None for _ in range(game_size)] for _ in range(game_size)]
        
        self.setup_buttons()

    def setup_buttons(self):
        """Setup buttons in a clean, organized layout"""
        current_row = 0
        buttons_in_row = 0
        
        # Create horizontal line buttons with clear labels
        for row in range(self.game_size + 1):
            for col in range(self.game_size):
                if buttons_in_row >= 5:
                    current_row += 1
                    buttons_in_row = 0
                    
                line_id = f"H{row}{col}"
                btn = DotsAndBoxesButton(line_id, 'h', row, col, current_row)
                self.add_item(btn)
                buttons_in_row += 1
        
        # Create vertical line buttons with clear labels
        for row in range(self.game_size):
            for col in range(self.game_size + 1):
                if buttons_in_row >= 5:
                    current_row += 1
                    buttons_in_row = 0
                    
                line_id = f"V{row}{col}"
                btn = DotsAndBoxesButton(line_id, 'v', row, col, current_row)
                self.add_item(btn)
                buttons_in_row += 1

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
        """Create a visual representation with line reference IDs"""
        lines = []
        
        # Add explanation header
        lines.append("📍 Line Reference Guide:")
        lines.append("━ = Horizontal lines (H##)")
        lines.append("┃ = Vertical lines (V##)")
        lines.append("")
        
        for row in range(self.game_size + 1):
            # Horizontal lines row
            h_line = ""
            for col in range(self.game_size + 1):
                h_line += "🔹"  # Dot
                if col < self.game_size:
                    line_id = f"H{row}{col}"
                    if self.horizontal_lines[row][col]:
                        h_line += "━━"
                    else:
                        h_line += f" {line_id[-1]} "  # Show last digit of ID
            lines.append(h_line)
            
            # Vertical lines and boxes row (if not the last row)
            if row < self.game_size:
                v_line = ""
                for col in range(self.game_size + 1):
                    line_id = f"V{row}{col}"
                    if self.vertical_lines[row][col]:
                        v_line += "┃"
                    else:
                        v_line += f"{line_id[-1]}"  # Show last digit of ID
                    
                    if col < self.game_size:
                        # Box content
                        if self.completed_boxes[row][col]:
                            if self.completed_boxes[row][col] == self.player1:
                                v_line += "🔴"
                            else:
                                v_line += "🔵"
                        else:
                            v_line += "  "
                lines.append(v_line)
        
        return "\n".join(lines)

    def create_game_embed(self) -> discord.Embed:
        """Create a beautiful embed showing the game state"""
        embed = discord.Embed(
            title="🎯 Dots and Boxes",
            description="Click the buttons below to draw lines!",
            color=0x00ff00 if self.current_player == self.player1 else 0xff0000
        )
        
        # Player scores - more prominent
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
        
        # Add the visual grid
        grid_visual = self.create_visual_grid()
        if len(grid_visual) <= 1024:
            embed.add_field(
                name="🎮 Game Board & Button Guide",
                value=f"```\n{grid_visual}\n```",
                inline=False
            )
        
        # Simple instructions
        if not self.game_over:
            embed.add_field(
                name="📋 How to Play",
                value="• Click ➖ buttons for horizontal lines\n• Click ⬜ buttons for vertical lines\n• Complete boxes to score points!\n• Numbers in grid show button IDs",
                inline=False
            )
        
        # Footer with game info
        total_boxes = self.game_size * self.game_size
        completed_boxes = sum(self.scores.values())
        embed.set_footer(text=f"Boxes: {completed_boxes}/{total_boxes} | Grid: {self.game_size}x{self.game_size}")
        
        return embed

    async def on_timeout(self):
        """Clean up when the view times out"""
        game_key = f"{self.player1.id}_{self.player2.id}"
        reverse_key = f"{self.player2.id}_{self.player1.id}"
        if game_key in active_challenges:
            del active_challenges[game_key]
        if reverse_key in active_challenges:
            del active_challenges[reverse_key]
        self.stop()

def setup(bot):
    @bot.hybrid_command(description="Play Dots and Boxes with another player")
    async def dots(ctx, opponent: discord.Member, size: int = 2):
        """
        Start a game of Dots and Boxes
        
        Parameters:
        - opponent: The player to challenge
        - size: Grid size (2 only for now to keep UI clean)
        """
        
        # Validation
        if opponent == ctx.author:
            await ctx.send("❌ You can't play against yourself!", ephemeral=True)
            return
            
        if opponent.bot:
            await ctx.send("❌ You can't play against a bot!", ephemeral=True)
            return
            
        if size != 2:
            await ctx.send("❌ Only 2x2 grid is supported for clean UI! Use: `/dots @opponent`", ephemeral=True)
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
                f"🎲 2x2 Grid (12 lines total)\n"
                f"🎮 {ctx.author.mention} goes first!\n\n"
                f"**Instructions:** Use the buttons below to draw lines. The numbers in the grid show which button controls each line!",
                embed=embed,
                view=view
            )
            
        except Exception as e:
            # Clean up if something goes wrong
            if game_key in active_challenges:
                del active_challenges[game_key]
            await ctx.send(f"❌ An error occurred while starting the game: {str(e)}", ephemeral=True)

    @bot.hybrid_command(description="View Dots and Boxes leaderboard")
    async def dotsleaderboard(ctx):
        """Show the Dots and Boxes leaderboard"""
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