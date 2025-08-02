import discord
from discord.ext import commands
import random
import asyncio

# Dictionary to store active games or lobbies, keyed by channel ID
active_games = {}

# A curated list of direct GIF links to be displayed on player elimination.
death_gifs = [
    "https://media.tenor.com/gR8d340A1-sAAAAC/shitwaifu-zankyou.gif",
    "https://media.tenor.com/5r2sA02Dk2AAAAAC/jjk-jujutsu-kaisen.gif",
    "https://media.tenor.com/K89I0FN2VzAAAAAC/homelander-homelander-laser.gif",
    "https://media.tenor.com/K5YI0nv62RIAAAAC/ponzu-hunter-x-hunter.gif",
    "https://media.tenor.com/G50gHcs1t2sAAAAC/nanami-nanami-kento.gif"
]

# --- Game View (After Lobby) ---
class RussianRouletteView(discord.ui.View):
    """
    The interactive view for the actual Russian Roulette game.
    Contains the 'Pull Trigger' button and handles game logic on interaction.
    """
    def __init__(self, game_state: dict):
        super().__init__(timeout=180.0) # 3-minute timeout for the game
        self.game_state = game_state
        self.update_button_label()

    def update_button_label(self):
        """Updates the button to show whose turn it is."""
        if not self.game_state.get('players'):
            return
        current_player = self.game_state['players'][self.game_state['current_player_index']]
        button = self.children[0]
        button.label = f"Pull Trigger ({current_player.display_name})"

    async def on_timeout(self):
        """Disables the game on timeout and cleans up the active game state."""
        channel_id = self.game_state['message'].channel.id
        if channel_id in active_games:
            embed = self.game_state['message'].embeds[0]
            embed.description = "The game ended due to inactivity."
            embed.color = discord.Color.orange()
            for item in self.children:
                item.disabled = True
            await self.game_state['message'].edit(embed=embed, view=self)
            del active_games[channel_id]

    @discord.ui.button(label="Pull Trigger", style=discord.ButtonStyle.danger, emoji="🔫")
    async def pull_trigger_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """The callback for the 'Pull Trigger' button."""
        channel_id = interaction.channel.id
        if channel_id not in active_games:
            await interaction.response.send_message("This game has ended.", ephemeral=True)
            return

        game = active_games[channel_id]
        current_player = game['players'][game['current_player_index']]

        if interaction.user.id != current_player.id:
            await interaction.response.send_message("It's not your turn!", ephemeral=True)
            return

        game['turn_number'] += 1
        embed = discord.Embed(title="Russian Roulette 🔫")

        if game['turn_number'] == game['bullet_chamber']:
            # --- BANG! Player is eliminated ---
            embed.color = discord.Color.dark_red()
            embed.description = f"**BANG!** 💥\n\nThe revolver fires. {current_player.mention} has been eliminated!"
            
            # Set the image from our curated list
            embed.set_image(url=random.choice(death_gifs))
            
            game['players'].pop(game['current_player_index'])
            
            if len(game['players']) < 2:
                # --- GAME OVER ---
                winner_text = f"\n\n**{game['players'][0].mention} is the last one standing and wins!** 🎉" if game['players'] else "\n\nEveryone has been eliminated. No one wins."
                embed.description += winner_text
                
                player_list = ", ".join([p.mention for p in game['players']])
                embed.add_field(name="Players Remaining", value=player_list if player_list else "None", inline=False)
                embed.set_footer(text=f"Chamber {game['turn_number']}/{game['chambers']}")

                # Disable all buttons and stop the view
                for child in self.children:
                    child.disabled = True
                self.stop()
                
                await interaction.response.edit_message(embed=embed, view=self)
                if channel_id in active_games:
                    del active_games[channel_id]

            else:
                # --- GAME CONTINUES ---
                game['chambers'] = 6
                game['bullet_chamber'] = random.randint(1, game['chambers'])
                game['turn_number'] = 0
                game['current_player_index'] %= len(game['players'])
                next_player = game['players'][game['current_player_index']]
                embed.description += f"\nThe game continues with a new round. It's now {next_player.mention}'s turn."
                
                player_list = ", ".join([p.mention for p in game['players']])
                embed.add_field(name="Players Remaining", value=player_list, inline=False)
                embed.set_footer(text=f"Chamber {game['turn_number']}/{game['chambers']}")
                
                self.update_button_label()
                await interaction.response.edit_message(embed=embed, view=self)
        else:
            # --- CLICK! Player survives ---
            embed.color = discord.Color.green()
            embed.description = f"*CLICK!* The hammer falls on an empty chamber. {current_player.mention} survives."
            game['current_player_index'] = (game['current_player_index'] + 1) % len(game['players'])
            next_player = game['players'][game['current_player_index']]
            embed.description += f"\nThe revolver is passed to {next_player.mention}."

            player_list = ", ".join([p.mention for p in game['players']])
            embed.add_field(name="Players Remaining", value=player_list, inline=False)
            embed.set_footer(text=f"Chamber {game['turn_number']}/{game['chambers']}")

            self.update_button_label()
            await interaction.response.edit_message(embed=embed, view=self)

# --- Lobby View ---
class LobbyView(discord.ui.View):
    """
    A view for the game lobby, allowing players to join or the host to start.
    """
    def __init__(self, author: discord.Member):
        super().__init__(timeout=300.0) # 5-minute timeout for lobby
        self.author = author
        self.players = [author]
        self.message = None

    async def update_embed(self):
        """Updates the lobby message with the current player list."""
        player_list = "\n".join([f"‣ {player.display_name}" for player in self.players])
        embed = self.message.embeds[0]
        embed.description = f"Click the button to join the game!\n\n**Players ({len(self.players)}/6):**\n{player_list}"
        await self.message.edit(embed=embed)

    @discord.ui.button(label="Join Game", style=discord.ButtonStyle.success, emoji="✅")
    async def join_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Allows a player to join the game."""
        if interaction.user in self.players:
            await interaction.response.send_message("You are already in the game.", ephemeral=True)
            return
        if len(self.players) >= 6:
            await interaction.response.send_message("The lobby is full!", ephemeral=True)
            return
        
        self.players.append(interaction.user)
        await self.update_embed()
        await interaction.response.defer()

    @discord.ui.button(label="Start Game", style=discord.ButtonStyle.primary, emoji="▶️")
    async def start_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Starts the game if conditions are met."""
        await interaction.response.defer() # Acknowledge the interaction immediately
        
        if interaction.user.id != self.author.id:
            await interaction.followup.send("Only the person who started the lobby can start the game.", ephemeral=True)
            return
        if len(self.players) < 2:
            await interaction.followup.send("You need at least 2 players to start.", ephemeral=True)
            return

        # Disable the lobby view
        for item in self.children:
            item.disabled = True
        await self.message.edit(view=self)
        self.stop()

        # --- Start the actual game ---
        random.shuffle(self.players)
        chambers = 6
        game_state = {
            'players': self.players,
            'current_player_index': 0,
            'chambers': chambers,
            'bullet_chamber': random.randint(1, chambers),
            'turn_number': 0,
            'message': self.message,
        }
        active_games[interaction.channel.id] = game_state

        first_player = self.players[0]
        embed = discord.Embed(
            title="Russian Roulette 🔫",
            description=f"The game has begun! The revolver is loaded.\nThe barrel swings and points to {first_player.mention} first. Good luck.",
            color=discord.Color.from_rgb(150, 75, 0)
        )
        player_list = ", ".join([p.mention for p in self.players])
        embed.add_field(name="Contestants", value=player_list, inline=False)

        game_view = RussianRouletteView(game_state)
        await self.message.edit(content="", embed=embed, view=game_view)

    async def on_timeout(self):
        if self.message:
            channel_id = self.message.channel.id
            if channel_id in active_games and active_games[channel_id] is self:
                embed = self.message.embeds[0]
                embed.description = "This game lobby has expired."
                embed.color = discord.Color.orange()
                for item in self.children:
                    item.disabled = True
                await self.message.edit(embed=embed, view=self)
                del active_games[channel_id]

def setup(bot):
    """Adds the Russian Roulette command to the bot."""
    @bot.hybrid_command(name="russianroulette", aliases=['rr'], description="Start a game of Russian Roulette.")
    @commands.cooldown(1, 30, commands.BucketType.channel)
    async def russian_roulette(ctx: commands.Context):
        if ctx.channel.id in active_games:
            await ctx.send("A game is already in progress in this channel.", ephemeral=True)
            return

        lobby_view = LobbyView(ctx.author)
        embed = discord.Embed(
            title="🔫 Russian Roulette Lobby",
            description=f"Click the button to join the game!\n\n**Players (1/6):**\n‣ {ctx.author.display_name}",
            color=discord.Color.blurple()
        )
        message = await ctx.send(embed=embed, view=lobby_view)
        lobby_view.message = message
        active_games[ctx.channel.id] = lobby_view # Store the view to manage the lobby state
