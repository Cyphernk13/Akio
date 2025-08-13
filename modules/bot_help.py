import discord
from discord.ui import Select, View
from discord.ext import commands
from modules.gif_utils import get_cached_reactions

# A dictionary to hold all the command information for easy management.
COMMANDS_DATA = {
    "ai": {
        "emoji": "🧠",
        "label": "AI & Chat",
        "description": "Commands for interacting with the AI.",
        "content": (
            "`query <question>`: Ask me anything!\n"
            "`@Akio <question>`: Mention me to chat.\n"
            "`reset`: Reset the conversation.\n"
            "`say <message>`: Make me say something.\n"
            "`echo <message>`: I'll repeat your message."
        )
    },
    "anime": {
        "emoji": "🌸",
        "label": "Anime & Manga",
        "description": "Commands for searching anime, manga, and more.",
        "content": (
            "`anime <name>`: Search for an anime.\n"
            "`manga <name>`: Search for a manga.\n"
            "`character <name>`: Search for a character.\n"
            "`topanime`: Get top anime rankings by category.\n"
            "`seasonal [year] [season]`: Browse seasonal anime.\n"
            "`user <mal_username>`: View a MyAnimeList profile."
        )
    },
    "music": {
        "emoji": "🎵",
        "label": "Music",
        "description": "Commands for playing music in a voice channel.",
        "content": (
            "`play <song>`: Play or queue a song.\n"
            "`pause` / `resume`: Control playback.\n"
            "`skip`: Skip the current song.\n"
            "`queue`: View the song queue.\n"
            "`nowplaying`: See the current track.\n"
            "`disconnect`: Disconnect me from VC."
        )
    },
    "games": {
        "emoji": "🎮",
        "label": "Games & Fun",
        "description": "Commands for playing games and having fun.",
        "content": (
            "`cat`: Get a random cat picture.\n"
            "`rr`: Play Russian Roulette.\n"
            "`rps [user]`: Play Rock, Paper, Scissors.\n"
            "`tictactoe [user]`: Play Tic-Tac-Toe.\n"
            "`guess`: Guess the number.\n"
            "`dots [user]`: Play Dots and Boxes.\n"
            "`flip`: Flip a coin.\n"
            "`8ball [question]`: Ask the magic 8-ball.\n"
            "`draw`: Get a random drawing idea.\n"
            "`love [user1] [user2]`: Calculate love %."
        )
    },
    "actions": {
        "emoji": "<:pinkheart:1399583453258977440>",
        "label": "Actions",
        "description": "Roleplay action commands.",
        "content": ""
    },
    "utility": {
        "emoji": "🛠️",
        "label": "Utility",
        "description": "Helpful utility commands.",
        "content": (
            "`pfp [user]`: Fetch a user's profile picture.\n"
            "`dict <word>`: Get the definition of a word.\n"
            "`tl <sentence>`: Translate text to English.\n"
            "`math <operation>`: e.g., `add`, `sub`, `mul`, `div`..."
        )
    }
}

class HelpSelect(Select):
    """The dropdown select menu for picking a command category."""
    def __init__(self, bot):
        self.bot = bot
        # Define the options for the dropdown
        options = [
            discord.SelectOption(label="Home", description="Return to the main help page.", emoji="🏠", value="home")
        ]
        for key, data in COMMANDS_DATA.items():
            options.append(discord.SelectOption(
                label=data["label"],
                description=data["description"],
                emoji=data["emoji"],
                value=key
            ))
        super().__init__(placeholder="Choose a command category...", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        """This function is called when a user makes a selection."""
        await interaction.response.defer()
        category = self.values[0]
        
        # Create the appropriate embed based on the user's choice
        if category == "home":
            embed = discord.Embed(
                title="<:miku_dab:1228484805562208416> Akio's Command Guide",
                description="Hello! I'm Akio. Here's a list of all my commands.\nMy prefix is `akio ` or `Akio `. You can also use `/` for slash commands!\n\nPlease select a category from the dropdown below.",
                color=0x7289DA
            )
            if self.bot.user.avatar:
                embed.set_thumbnail(url=self.bot.user.avatar.url)
            embed.set_footer(text="Have fun using Akio! | kuru~ kuru~")
        else:
            data = COMMANDS_DATA[category]
            description = data['content']
            if category == "actions":
                try:
                    reactions = get_cached_reactions()
                except Exception:
                    reactions = []
                # Categorize like OwO: Emotes vs Actions
                emotes = {
                    "bleh","blush","celebrate","cheers","clap","confused","cool","cry","dance","drool",
                    "evillaugh","facepalm","happy","headbang","huh","laugh","love","mad","nervous","no",
                    "nosebleed","nyah","pout","roll","run","sad","scared","shout","shrug","shy","sigh",
                    "sip","sleep","slowclap","smile","smug","sneeze","sorry","stop","surprised","sweat",
                    "thumbsup","tired","wink","woah","yawn","yay","yes"
                }
                actions = {
                    "airkiss","angrystare","bite","brofist","cuddle","handhold","hug","kiss","lick","nom",
                    "nuzzle","pat","peek","pinch","poke","punch","slap","smack","stare","tickle","wave"
                }
                # Intersect with actually available reactions (if we got them)
                if reactions:
                    rset = set(reactions)
                    emotes = sorted([r for r in emotes if r in rset])
                    actions = sorted([r for r in actions if r in rset])
                else:
                    emotes = sorted(list(emotes))
                    actions = sorted(list(actions))

                def fmt(items):
                    return " ".join(f"`{x}`" for x in items)

                description = (
                    "Use prefix commands (akio <cmd>).\n"
                    "- **Emotes** are self-only (mentions are ignored).\n"
                    "- **Actions** can mention a target or act on yourself if none is given.\n\n"
                    "🙂 Emotes\n"
                    f"{fmt(emotes)}\n\n"
                    "🤗 Actions\n"
                    f"{fmt(actions)}\n\n"
                    "Examples:\n"
                    "`akio blush` · `akio hug @user` · `akio facepalm`"
                )
            embed = discord.Embed(
                title=f"{data['emoji']} {data['label']} Commands",
                description=description,
                color=0x7289DA
            )
            if self.bot.user.avatar:
                embed.set_thumbnail(url=self.bot.user.avatar.url)

        # Edit the original message with the new embed
        await interaction.edit_original_response(embed=embed, view=self.view)


class HelpView(View):
    """The view that holds the dropdown menu."""
    def __init__(self, bot):
        super().__init__(timeout=180.0)
        self.add_item(HelpSelect(bot))
        self.message = None

    async def on_timeout(self):
        # Disable the dropdown when the view times out
        if self.message:
            try:
                for item in self.children:
                    item.disabled = True
                await self.message.edit(view=self)
            except discord.NotFound:
                pass

def setup(bot):
    @bot.hybrid_command(description="Get help on how to use the bot")
    async def help(ctx):
        # Create the initial "home" embed
        embed = discord.Embed(
            title="<:miku_dab:1228484805562208416> Akio's Command Guide",
            description="Hello! I'm Akio. Here's a list of all my commands.\nMy prefix is `akio ` or `Akio `. You can also use `/` for slash commands!\n\nPlease select a category from the dropdown below.",
            color=0x7289DA
        )
        if bot.user.avatar:
            embed.set_thumbnail(url=bot.user.avatar.url)
        embed.set_footer(text="Have fun using Akio! | kuru~ kuru~")
        
        # Send the message with the interactive view
        view = HelpView(bot)
        message = await ctx.send(embed=embed, view=view)
        view.message = message
