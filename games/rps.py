import discord
from discord.ext import commands
import random
from games.shared import active_challenges

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

def setup(bot):
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
