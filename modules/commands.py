import discord
from discord.ext import commands
from googletrans import Translator
import random
from modules.gif_utils import get_otaku_gif, resolve_reaction, get_all_reactions
from typing import Optional

def setup(bot):
    # ---- Helpers for nicer action text and consistent embeds ---- #
    ACTION_VERBS = {
        "hug": "hugs",
        "kiss": "kisses",
        "pat": "pats",
        "slap": "slaps",
        "punch": "punches",
        "smack": "smacks",
        "tickle": "tickles",
        "brofist": "bro-fists",
        "thumbsup": "gives a thumbs up to",
        "cheers": "cheers for",
        "clap": "claps for",
        "smug": "smirks at",
        "pout": "pouts at",
        "cry": "cries about",
        "shrug": "shrugs at",
        "dance": "dances with",
        "wave": "waves at",
        "laugh": "laughs at",
        "wink": "winks at",
        "confused": "stares at",
        "roll": "rolls around with",
        "stare": "stares at",
        "nuzzle": "nuzzles",
        "cuddle": "cuddles",
        "handhold": "holds hands with",
        "airkiss": "blows a kiss to",
        "headbang": "headbangs with",
        "bite": "bites",
        "peek": "peeks at",
        "pinch": "pinches",
        "poke": "pokes",
    }

    SELF_SOFT = {
        "hug": "Aww {a}, I'll give you a warm hug~ <:gura_hug:1404972923831193662>",
        "kiss": "Umm {a}... that's bold >///<",
        "pat": "Aww {a}, here, pats pats~ <a:Cat_Pat:1402647706169774181>",
        "slap": "{a} slaps... (lightly) >:(",
        "punch": "{a} throws a punch...🥊",
        "smack": "{a} smacks... 😤",
        "tickle": "{a} hahaha! tickle tickle~ <:hehe_giggle:1404973806141051071>",
        "brofist": "Boom! Bro-fist, {a}! 👊🏻",
        "airkiss": "{a} blows a kiss~ 💋",
        "lick": "{a} licks... >///< <:CH_Lick:1404976447306596472>",
        "nom": "{a} noms~",
        "bite": "{a} bites... chomp!",
        "peek": "{a} peeks~ <:pikameepeek:1404977012942180402>",
        "pinch": "{a} pinches... ouch! <a:pinchy:1404977207700361366>",
        "poke": "{a} pokes~ 👉🏻",
        "stare": "{a} stares~ <:laffeystare:1404977299920654346>",
        "cuddle": "There there, {a}... cuddle time~ <a:cuddlegirl:1404976197594775663><a:cuddleboy:1404976223347675237>",
        "nuzzle": "{a} nuzzles~ ♡",
        "handhold": "{a} holds hands... with air? >///< <:SkyHoldingHands:1404983126341714050>",
        "cheers": "{a} is cheering! 🥂",
        "clap": "{a} is clapping! 👏🏻",
        "smug": "{a} looks smug~ <:02smug:1404974796260900894>",
        "pout": "{a} is angry!!",
        "cry": "There there, {a}...",
        "shrug": "{a} shrugged ¯\\_(ツ)_/¯",
        "dance": "Nice moves, {a}! <a:CH_JotaroDance:1404975479471214612>",
        "wave": "{a} is waving~ <:GawrGuraWaveBackgroundless:1399581860836802652>",
        "laugh": "{a} is laughing! <a:Hahah:1404978377189752892>",
        "wink": "{a} is winking~ <:ReimuWink:1404975630658965708>",
        "confused": "{a} is thinking hard!!",
        "roll": "{a} is spinning! <a:rabbit_roll:1404981264515076207>",
    }

    DEF_ARTICLE = {
        "kiss": "a kiss",
        "hug": "a hug",
        "pat": "a pat",
        "tickle": "a tickle",
        "brofist": "a bro-fist",
    }

    def nice_phrase_for_target(reaction: str) -> str:
        return ACTION_VERBS.get(reaction, reaction.replace("_", " ") + "s")

    # Targeted lines with emojis/emoticons
    TARGET_LINES = {
        "hug": "{a} gives {b} a warm hug <:gura_hug:1404972923831193662>",
        "kiss": "{a} kisses {b} <a:cheek_kiss:1404972724010618972>",
        "pat": "{a} pats {b}'s head <a:Cat_Pat:1402647706169774181>",
        "slap": "{a} slaps {b}! >:(",
        "punch": "{a} punches {b}! 🥊",
        "smack": "{a} smacks {b}! 😤",
        "tickle": "{a} tickles {b}! <:hehe_giggle:1404973806141051071>",
        "brofist": "{a} bro-fists {b}! 👊🏻",
        "cheers": "{a} cheers for {b}! 🥂",
        "clap": "{a} claps for {b}! 👏🏻",
        "smug": "{a} smirks at {b} <:02smug:1404974796260900894>",
        "wave": "{a} waves at {b} <:GawrGuraWaveBackgroundless:1399581860836802652>",
        "dance": "{a} dances with {b} <a:CH_JotaroDance:1404975479471214612>",
        "wink": "{a} winks at {b} <:ReimuWink:1404975630658965708>",
        "handhold": "{a} holds hands with {b} <:SkyHoldingHands:1404983126341714050>",
        "nuzzle": "{a} nuzzles {b} ♡",
        "cuddle": "{a} cuddles with {b} <a:cuddlegirl:1404976197594775663><a:cuddleboy:1404976223347675237>",
        "airkiss": "{a} blows a kiss to {b} 💋",
        "lick": "{a} licks {b} <:CH_Lick:1404976447306596472>",
        "bite": "{a} bites {b}! chomp!",
        "peek": "{a} peeks at {b} <:pikameepeek:1404977012942180402>",
        "poke": "{a} pokes {b} 👉🏻",
        "pinch": "{a} pinches {b} <a:pinchy:1404977207700361366>",
        "stare": "{a} stares at {b} <:laffeystare:1404977299920654346>",
        "angrystare": "{a} glares at {b} 😠",
        "evillaugh": "{a} cackles at {b} <:Satania_Laugh:1404977537175781518>",
    }

    def build_action_line(reaction: str, author: discord.Member, member: Optional[discord.Member]) -> str:
        rxn = reaction.lower()
        author_name = author.display_name
        if member is None or member is discord.utils.MISSING:
            # No target -> prefer custom self lines; otherwise gentle default if applicable
            if rxn in SELF_SOFT:
                return SELF_SOFT[rxn].format(a=author_name)
            if rxn in DEF_ARTICLE:
                return f"Aww {author_name}, I'll give you {DEF_ARTICLE[rxn]}~"
            return f"{author_name} {rxn}"
        if member.id == author.id:
            # Self-case
            if rxn in SELF_SOFT:
                return SELF_SOFT[rxn].format(a=author_name)
            return f"{author_name} {rxn}"
        # With target
        if rxn in TARGET_LINES:
            return TARGET_LINES[rxn].format(a=author_name, b=member.display_name)
        verb = nice_phrase_for_target(rxn)
        # Default: no tilde, add exclamation
        return f"{author_name} {verb} {member.display_name}!"

    def create_action_embed(ctx, line: str, gif_url: Optional[str]) -> discord.Embed:
        # Use description (smaller font) so custom emojis render, and keep avatar via author
        embed = discord.Embed(description=line, color=discord.Color.random())
        if gif_url:
            embed.set_image(url=gif_url)
        return embed

    # --- Categorization like OwO: Emotes (self only) vs Actions (can target) ---
    EMOTE_REACTIONS = {
        "bleh","blush","celebrate","cheers","clap","confused","cool","cry","dance","drool",
        "evillaugh","facepalm","happy","headbang","huh","laugh","love","mad","nervous","no",
        "nosebleed","nyah","pout","roll","run","sad","scared","shout","shrug","shy","sigh",
        "sip","sleep","slowclap","smile","smug","sneeze","sorry","stop","surprised","sweat",
        "thumbsup","tired","wink","woah","yawn","yay","yes"
    }
    ACTION_REACTIONS = {
        "airkiss","angrystare","bite","brofist","cuddle","handhold","hug","kiss","lick","nom",
        "nuzzle","pat","peek","pinch","poke","punch","slap","smack","stare","tickle","wave"
    }

    EMOTE_LINES = {
        "bleh": "{a} goes 'bleh~'",
        "blush": "{a} blushed!! >///<",
        "celebrate": "{a} is celebrating! 🎉",
        "cheers": "{a} raises a toast! 🥂",
        "clap": "{a} claps! 👏🏻",
        "confused": "{a} tilts their head, confused...",
        "cool": "{a} is looking cool <:Anya_cool:1404977918664511508>",
        "cry": "{a} starts tearing up... <:AquaCry:1404978107735343154>",
        "dance": "{a} starts dancing! <a:CH_JotaroDance:1404975479471214612>",
        "drool": "{a} is drooling...",
        "evillaugh": "{a} laughs menacingly...<a:Hahah:1404978377189752892>",
        "facepalm": "{a} facepalms...<:PikaFacepalm:1404978493892067508>",
        "happy": "{a} looks so happy! <:shinobu_happy:1404978611219337412>",
        "headbang": "{a} is headbanging! <:AkatsukiAngry:1404979342542377151>",
        "huh": "{a} goes 'huh?' <:mikuhuh:1404979450587648041>",
        "laugh": "{a} laughs! <a:Hahah:1404978377189752892>",
        "love": "{a} is full of love~ <a:love:1404979792612425810>",
        "mad": "{a} is mad! >:(",
        "nervous": "{a} is nervous...",
        "no": "{a} says no! <:no:1404980370486722621>",
        "nosebleed": "{a} gets a nosebleed!",
        "nyah": "{a} goes 'nyah~' ₍^. .^₎Ⳋ",
        "pout": "{a} pouts... hmph! <:pikapout:1404980982389407764>",
        "roll": "{a} rolls around <a:rabbit_roll:1404981264515076207>",
        "run": "{a} runs! <a:nezukorun:1404981370228576329>",
        "sad": "{a} is sad <:neco_sadhappy:1404981626429116547>",
        "scared": "{a} is scared! <:Zenitsu_Scared:1404981784210575492>",
        "shout": "{a} shouts! 🗣️",
        "shrug": "{a} shrugged ¯\\_(ツ)_/¯",
        "shy": "{a} is shy...<:RemShy:1404982011675803658>",
        "sigh": "{a} sighs...<:SakuSigh:1404982106106495066>",
        "sip": "{a} sips a drink <:ZeroSip:1404982303180066856>",
        "sleep": "{a} falls asleep... <:giyuu_sleep:1404982404430434334>",
        "slowclap": "{a} slow claps 👏🏻",
        "smile": "{a} smiles <:Miku_smile:1404982682852528209>",
        "smug": "{a} smugs <:02smug:1404974796260900894>",
        "sneeze": "{a} sneezes! 🤧",
        "sorry": "{a} says sorry...<:neco_sadhappy:1404981626429116547>",
        "stop": "{a} says stop! 🤚🏻",
        "surprised": "{a} is surprised! 😲",
        "sweat": "{a} is sweating nervously...<:Sakusweat:1404983581193015409>",
        "thumbsup": "{a} gives a thumbs up! <:sataniathumbsup:1404983668778205236>",
        "tired": "{a} is tired...💤",
        "wink": "{a} winks~ <:ReimuWink:1404975630658965708>",
        "woah": "{a} goes 'woah!' <:IRyS_Woah:1404983942976639038>",
        "yawn": "{a} yawns~ <:Sakuyawn:1404984041765081202>",
        "yay": "{a} goes yay! <a:yay:1404984128243368078>",
        "yes": "{a} says yes! <:Hemoji_yes:1404984245843263509>"
    }

    def build_emote_line(reaction: str, author: discord.Member) -> str:
        rxn = reaction.lower()
        author_name = author.display_name
        template = EMOTE_LINES.get(rxn)
        if template:
            return template.format(a=author_name)
        # fallback: simple "Author reaction"
        return f"{author_name} {rxn}"
    @bot.hybrid_command(aliases=["hi"], description="Say hello to the bot!")
    async def hello(ctx):
        await ctx.send(f'Hello, {ctx.author.name}! <:GawrGuraWaveBackgroundless:1399581860836802652>')
    
    @bot.hybrid_command(description="Translate a sentence to English")
    async def tl(ctx, *, sentence: str):
        translator = Translator()
        try:
            translation = translator.translate(sentence, dest='en')
            embed = discord.Embed(
                title="Translation",
                description=f"**Original:** {sentence}\n**English:** {translation.text}",
                color=discord.Color.blue()
            )
            embed.set_footer(text=f"Requested by {ctx.author}", icon_url=ctx.author.avatar.url)
            await ctx.send(embed=embed)
        except Exception as e:
            error_embed = discord.Embed(
                title="Error",
                description=f"An error occurred: {str(e)}",
                color=discord.Color.red()
            )
            await ctx.send(embed=error_embed)

    @bot.hybrid_command(description="List all available OtakuGIFs reactions")
    async def reactions(ctx):
        rxns = get_all_reactions()
        if not rxns:
            return await ctx.send("Couldn't fetch reactions right now. Please try again later.")
        rxns.sort()
        embed = discord.Embed(
            title="Available Reactions",
            description=", ".join(rxns),
            color=discord.Color.purple()
        )
        embed.set_footer(text=f"Requested by {ctx.author}", icon_url=ctx.author.avatar.url)
        await ctx.send(embed=embed)

    @bot.hybrid_command(description="Make the bot say something")
    async def say(ctx, *, message):
        await ctx.message.delete()
        await ctx.send(message)

    @bot.hybrid_command(description="Make the bot repeat your message")
    async def echo(ctx, *, message):
        await ctx.send(message)

    @bot.hybrid_command(description="Get anyone's profile picture")
    async def pfp(ctx, member: discord.Member = None):
        if member:
            avatar_url = member.avatar.url
        else:
            avatar_url = ctx.author.avatar.url
        await ctx.channel.send(avatar_url)

    @bot.hybrid_command(description="Hug someone")
    async def hug(ctx, member: discord.Member = None):
        gif_url = get_otaku_gif(resolve_reaction("hug") or "hug")
        line = build_action_line("hug", ctx.author, member)
        embed = create_action_embed(ctx, line, gif_url)
        await ctx.send(embed=embed)

    #-------------->PAT COMMAND 🤗<--------------#
    @bot.hybrid_command(description="Pat someone")
    async def pat(ctx,member: discord.Member = None):
        gif_url = get_otaku_gif(resolve_reaction("pat") or "pat")
        line = build_action_line("pat", ctx.author, member)
        embed = create_action_embed(ctx, line, gif_url)
        await ctx.send(embed=embed)

    #-------------->SLAP COMMAND 🤚🏻<--------------#
    @bot.hybrid_command(description="Slap someone")
    async def slap(ctx,member: discord.Member = None):
        gif_url = get_otaku_gif(resolve_reaction("slap") or "slap")
        line = build_action_line("slap", ctx.author, member)
        embed = create_action_embed(ctx, line, gif_url)
        await ctx.send(embed=embed)

    #-------------->KISS COMMAND 💋<--------------#
    @bot.hybrid_command(description="Kiss someone")
    async def kiss(ctx,member: discord.Member = None):
        gif_url = get_otaku_gif(resolve_reaction("kiss") or "kiss")
        line = build_action_line("kiss", ctx.author, member)
        embed = create_action_embed(ctx, line, gif_url)
        await ctx.send(embed=embed)


    #-------------->BLUSH COMMAND 😳<--------------#
    @bot.hybrid_command(description="Get a random blush gif")
    async def blush(ctx,member: discord.Member = None):
        gif_url = get_otaku_gif(resolve_reaction("blush") or "blush")
        line = build_emote_line("blush", ctx.author)
        embed = create_action_embed(ctx, line, gif_url)
        await ctx.send(embed=embed)

    #-------------->SHRUG COMMAND ＼（〇_ｏ）／<--------------#
    @bot.hybrid_command(description="Get a random shrug gif")
    async def shrug(ctx,member: discord.Member = None):
        gif_url = get_otaku_gif(resolve_reaction("shrug") or "shrug")
        line = build_emote_line("shrug", ctx.author)
        embed = create_action_embed(ctx, line, gif_url)
        await ctx.send(embed=embed)


    #-------------->POUT COMMAND 😒<--------------#
    @bot.hybrid_command(description="Get a random pout gif")
    async def pout(ctx,member: discord.Member = None):
        gif_url = get_otaku_gif(resolve_reaction("pout") or "pout")
        line = build_emote_line("pout", ctx.author)
        embed = create_action_embed(ctx, line, gif_url)
        await ctx.send(embed=embed)

    #-------------->cry COMMAND 😒<--------------#
    @bot.hybrid_command(description="Get a random crying gif")
    async def cry(ctx,member: discord.Member = None):
        gif_url = get_otaku_gif(resolve_reaction("cry") or "cry")
        line = build_emote_line("cry", ctx.author)
        embed = create_action_embed(ctx, line, gif_url)
        await ctx.send(embed=embed)

    #-------------->Tickle COMMAND 💫<--------------#
    @bot.hybrid_command(description="Tickle someone")
    async def tickle(ctx,member: discord.Member = None):
        gif_url = get_otaku_gif(resolve_reaction("tickle") or "tickle")
        line = build_action_line("tickle", ctx.author, member)
        embed = create_action_embed(ctx, line, gif_url)
        await ctx.send(embed=embed)

    #-------------->DANCE COMMAND 💃🏻<--------------#
    @bot.hybrid_command(description="Get a random dancing gif")
    async def dance(ctx,member: discord.Member = None):
        gif_url = get_otaku_gif(resolve_reaction("dance") or "dance")
        line = build_emote_line("dance", ctx.author)
        embed = create_action_embed(ctx, line, gif_url)
        await ctx.send(embed=embed)

    #-------------->WAVE COMMAND 👋🏻<--------------#
    @bot.hybrid_command(description="Wave at someone")
    async def wave(ctx,member: discord.Member = None):
        gif_url = get_otaku_gif(resolve_reaction("wave") or "wave")
        line = build_action_line("wave", ctx.author, member)
        embed = create_action_embed(ctx, line, gif_url)
        await ctx.send(embed=embed)


    #-------------->LAUGH COMMAND 😆<--------------#
    @bot.hybrid_command(description="Get a random laughing gif")
    async def laugh(ctx,member: discord.Member = None):
        gif_url = get_otaku_gif(resolve_reaction("laugh") or "laugh")
        line = build_emote_line("laugh", ctx.author)
        embed = create_action_embed(ctx, line, gif_url)
        await ctx.send(embed=embed)

    #-------------->WINK COMMAND 😉<--------------#
    @bot.hybrid_command(description="Get a random wink gif")
    async def wink(ctx,member: discord.Member = None):
        gif_url = get_otaku_gif(resolve_reaction("wink") or "wink")
        line = build_emote_line("wink", ctx.author)
        embed = create_action_embed(ctx, line, gif_url)
        await ctx.send(embed=embed)

    # ---- Dynamically generate tons of extra action commands from OtakuGIFs ---- #
    existing = {c.name for c in bot.commands}
    # Avoid conflicting with game command names that load after this module
    reserved_names = existing.union({"love"})
    try:
        extra_reactions = [r for r in get_all_reactions() if r not in reserved_names]
    except Exception:
        extra_reactions = []

    def _nice_label(text: str) -> str:
        return text.replace("_", " ").replace("-", " ").title()

    for reaction_name in extra_reactions:
        if reaction_name in bot.commands:
            continue
        def _factory(rxn: str):
            @bot.command(name=rxn, help=f"Send a {_nice_label(rxn)} anime emote/action (prefix).")
            async def _generated_action_command(ctx, member: Optional[discord.Member] = None, fmt: str = "gif"):
                gif_url = get_otaku_gif(rxn, fmt)
                if rxn in EMOTE_REACTIONS:
                    line = build_emote_line(rxn, ctx.author)
                    member = None
                else:
                    line = build_action_line(rxn, ctx.author, member)
                embed = create_action_embed(ctx, line, gif_url)
                await ctx.send(embed=embed)
            _generated_action_command.__name__ = f"action_{rxn}"
            return _generated_action_command
        _factory(reaction_name)
