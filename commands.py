import discord
from discord.ext import commands
from googletrans import Translator
import random
from gif_utils import get_top_8_gifs

def setup(bot):
    @bot.hybrid_command()
    async def hello(ctx):
        await ctx.send(f'Hello, {ctx.author.name}!')
    
    @bot.command()
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

    @bot.command()
    async def say(ctx, *, message):
        await ctx.message.delete()
        await ctx.send(message)

    @bot.command()
    async def echo(ctx, *, message):
        await ctx.send(message)

    @bot.command()
    async def pfp(ctx, member: discord.Member = None):
        if member:
            avatar_url = member.avatar.url
        else:
            avatar_url = ctx.author.avatar.url
        await ctx.channel.send(avatar_url)

    @bot.command()
    async def hug(ctx, member: discord.Member = None):
        query = ["Anime hug","hug anime","anime hugging","sweet anime hug"]
        l = get_top_8_gifs(random.choice(query))
        auto = discord.Embed(color=discord.Color.random())
        if member:
            if member.name == ctx.author.name:
                auto.title = f"Aww {ctx.author.name} I'll give you a hug..."
            else:
                auto.title = f"{ctx.author.name} hugged {member.name}!"
        else:
            auto.title = f"Aww {ctx.author.name} I'll give you a hug..."
        auto.set_image(url=random.choice(l))
        await ctx.send(embed=auto)

    #-------------->PAT COMMAND 🤗<--------------#
    @bot.command()
    async def pat(ctx,member: discord.Member = None):
        # Example usage
        query = ["Anime pat","pat anime","anime patting","sweet anime pat"]
        l = get_top_8_gifs(random.choice(query))
        auto=discord.Embed(color=discord.Color.random())
        if member:
            if member.name==ctx.author.name:
                auto.title = f"Aww {ctx.author.name} come here :)..."
            else:
                auto.title = f"{ctx.author.name} pats {member.name} "
        else:
            auto.title = f"Aww {ctx.author.name} come here :)..."
        auto.set_image(url=random.choice(l))
        await ctx.send(embed=auto)

    #-------------->SLAP COMMAND 🤚🏻<--------------#
    @bot.command()
    async def slap(ctx,member: discord.Member = None):
        # Example usage
        query = ["Anime slap","slap anime","anime slapping","brutal anime slap"]
        l = get_top_8_gifs(random.choice(query))
        auto=discord.Embed(color=discord.Color.random())
        if member:
            if member.name==ctx.author.name:
                auto.title = f"Baka!! {ctx.author.name}, here you deserve it >:(..."
            else:
                auto.title = f"{ctx.author.name} slapped {member.name}!"
        else:
            auto.title = f"Baka!! {ctx.author.name}, here you deserve it >:(..."
        auto.set_image(url=random.choice(l))
        await ctx.send(embed=auto)

    #-------------->KICK COMMAND 🦵🏻<--------------#
    @bot.command()
    async def kick(ctx,member: discord.Member = None):
        # Example usage
        query = ["Anime kick","kick anime","anime kicking","brutal anime kick"]
        l = get_top_8_gifs(random.choice(query))
        auto=discord.Embed(color=discord.Color.random())
        if member:
            if member.name==ctx.author.name:
                auto.title = f"Idiot!! {ctx.author.name}, here you deserve it >:(..."
            else:
                auto.title = f"{ctx.author.name} kicked {member.name}!"
        else:
            auto.title = f"Idiot!! {ctx.author.name}, here you deserve it >:(..."
        auto.set_image(url=random.choice(l))
        await ctx.send(embed=auto)

    #-------------->KISS COMMAND 💋<--------------#
    @bot.command()
    async def kiss(ctx,member: discord.Member = None):
        # Example usage
        query = ["Anime kiss","kiss anime","anime kissing","romantic anime kiss"]
        l = get_top_8_gifs(random.choice(query))
        auto=discord.Embed(color=discord.Color.random())
        if member:
            if member.name==ctx.author.name:
                auto.title = f"Umm {ctx.author.name}, I don't mind it if it is with you >///<..."
            else:
                auto.title = f"{ctx.author.name} kissed {member.name} !"
        else:
            auto.title = f"Umm {ctx.author.name}, I don't mind it if it is with you >///<..."
        auto.set_image(url=random.choice(l))
        await ctx.send(embed=auto)

    #-------------->KILL COMMAND 🔪<--------------#
    @bot.command()
    async def kill(ctx,member: discord.Member = None):
        # Example usage
        query = ["Anime kill","kill anime","anime killing","brutal anime kill"]
        l = get_top_8_gifs(random.choice(query))
        auto=discord.Embed(color=discord.Color.random())
        if member:
            if member.name==ctx.author.name:
                auto.title = f"DIE {ctx.author.name}!!!!"
            else:
                auto.title = f"{ctx.author.name} killed {member.name} !"
        else:
            auto.title = f"DIE {ctx.author.name}!!!!"
        auto.set_image(url=random.choice(l))
        await ctx.send(embed=auto)


    #-------------->BLUSH COMMAND 😳<--------------#
    @bot.command()
    async def blush(ctx,member: discord.Member = None):
        # Example usage
        query = ["Anime blush","blushing anime","anime blushing","cute anime blush"]
        l = get_top_8_gifs(random.choice(query))
        auto=discord.Embed(color=discord.Color.random())
        if member:
            if member.name==ctx.author.name:
                auto.title = f"{ctx.author.name} is blushing >///<"
            else:
                auto.title = f"{ctx.author.name} blushes on {member.name} UwU!"
        else:
            auto.title = f"{ctx.author.name} is blushing >///<"
            pass
        auto.set_image(url=random.choice(l))
        await ctx.send(embed=auto)

    @bot.command()
    async def kuru(ctx):
        await ctx.send("kuru~ kuru~ kuru~ kuru~ kuru~ kuru~ kuru~ kuru~ kuru kururin kuru kururin")
        await ctx.send("https://tenor.com/hCh8h4nNTBe.gif")

    #-------------->SHRUG COMMAND ＼（〇_ｏ）／<--------------#
    @bot.command()
    async def shrug(ctx,member: discord.Member = None):
        # Example usage
        query = ["Anime shrug","shruging anime","anime shruging","cute anime shrug"]
        l = get_top_8_gifs(random.choice(query))
        auto=discord.Embed(color=discord.Color.random())
        if member:
            if member.name==ctx.author.name:
                auto.title = f"{ctx.author.name} shrugged ¯\\_(ツ)_/¯"
            else:
                auto.title = f"{ctx.author.name} shrugged ¯\\_(ツ)_/¯"
        else:
            auto.title = f"{ctx.author.name} shrugged ¯\\_(ツ)_/¯"
            pass
        auto.set_image(url=random.choice(l))
        await ctx.send(embed=auto)


    #-------------->POUT COMMAND 😒<--------------#
    @bot.command()
    async def pout(ctx,member: discord.Member = None):
        # Example usage
        query = ["Anime pout","pouting anime","anime pouting","cute anime pout"]
        l = get_top_8_gifs(random.choice(query))
        auto=discord.Embed(color=discord.Color.random())
        if member:
            if member.name==ctx.author.name:
                auto.title = f"{ctx.author.name} is angry !!"
            else:
                auto.title = f"{ctx.author.name} is angry !!"
        else:
            auto.title = f"{ctx.author.name} is angry !!"
            pass
        auto.set_image(url=random.choice(l))
        await ctx.send(embed=auto)

    #-------------->cry COMMAND 😒<--------------#
    @bot.command()
    async def cry(ctx,member: discord.Member = None):
        # Example usage
        query = ["Anime cry","crying anime","anime crying","cute anime cry"]
        l = get_top_8_gifs(random.choice(query))
        auto=discord.Embed(color=discord.Color.random())
        if member:
            if member.name==ctx.author.name:
                auto.title = f"{ctx.author.name} is sad....there there :("
            else:
                auto.title = f"{ctx.author.name} is crying...🥹"
        else:
            auto.title = f"{ctx.author.name} is crying 😭"
            pass
        auto.set_image(url=random.choice(l))
        await ctx.send(embed=auto)


    #-------------->SPIN COMMAND 💫<--------------#
    @bot.command()
    async def spin(ctx,member: discord.Member = None):
        # Example usage
        query = ["Anime spin","spinning anime","anime spinning","cute anime spin"]
        l = get_top_8_gifs(random.choice(query))
        auto=discord.Embed(color=discord.Color.random())
        if member:
            if member.name==ctx.author.name:
                auto.title = f"Woah {ctx.author.name} is spinning! "
            else:
                auto.title = f"{member.name} is spinning hard!!"
        else:
            auto.title = f"Woah {ctx.author.name} is spinning! "
            pass
        auto.set_image(url=random.choice(l))
        await ctx.send(embed=auto)

    #-------------->Tickle COMMAND 💫<--------------#
    @bot.command()
    async def tickle(ctx,member: discord.Member = None):
        # Example usage
        query = ["Anime tickle","tickling anime","anime tickling","cute anime tickle"]
        l = get_top_8_gifs(random.choice(query))
        auto=discord.Embed(color=discord.Color.random())
        if member:
            if member.name==ctx.author.name:
                auto.title = f"{ctx.author.name} hahahaha!"
            else:
                auto.title = f"{ctx.author.name} tickles {member.name} huehuehue!"
        else:
            auto.title = f"hahaha {ctx.author.name} stop it!"
            pass
        auto.set_image(url=random.choice(l))
        await ctx.send(embed=auto)

    #-------------->ROAST COMMAND 💫<--------------#
    @bot.command()
    async def roast(ctx,member: discord.Member = None):
        # Example usage
        query = ["Anime roast","roasting anime","anime roasting","angry anime roast"]
        l = get_top_8_gifs(random.choice(query))
        auto=discord.Embed(color=discord.Color.random())
        if member:
            if member.name==ctx.author.name:
                auto.title = f"{ctx.author.name} haha how was that?"
            else:
                auto.title = f"{ctx.author.name} roasts {member.name} 😈"
        else:
            auto.title = f"{ctx.author.name} haha how was that?"
            pass
        auto.set_image(url=random.choice(l))
        await ctx.send(embed=auto)


    #-------------->DANCE COMMAND 💃🏻<--------------#
    @bot.command()
    async def dance(ctx,member: discord.Member = None):
        # Example usage
        query = ["Anime dance","dancing anime","anime dancing","cute anime dance"]
        l = get_top_8_gifs(random.choice(query))
        auto=discord.Embed(color=discord.Color.random())
        if member:
            if member.name==ctx.author.name:
                auto.title = f"Nice moves {ctx.author.name}"
            else:
                auto.title = f"{member.name} is dancing :D"
        else:
            auto.title = f"{ctx.author.name} loves dancing"
            pass
        auto.set_image(url=random.choice(l))
        await ctx.send(embed=auto)

    #-------------->WAVE COMMAND 👋🏻<--------------#
    @bot.command()
    async def wave(ctx,member: discord.Member = None):
        # Example usage
        query = ["Anime wave","waving anime","anime waving","cute anime wave"]
        l = get_top_8_gifs(random.choice(query))
        auto=discord.Embed(color=discord.Color.random())
        if member:
            if member.name==ctx.author.name:
                auto.title = f"{ctx.author.name} is waving "
            else:
                auto.title = f"{ctx.author.name} waves at {member.name} "
        else:
            auto.title = f"{ctx.author.name} is waving"
            pass
        auto.set_image(url=random.choice(l))
        await ctx.send(embed=auto)


    #-------------->LAUGH COMMAND 😆<--------------#
    @bot.command()
    async def laugh(ctx,member: discord.Member = None):
        # Example usage
        query = ["Anime laugh","laughing anime","anime laughing","cute anime laugh"]
        l = get_top_8_gifs(random.choice(query))
        auto=discord.Embed(color=discord.Color.random())
        if member:
            if member.name==ctx.author.name:
                auto.title = f"{ctx.author.name} is laughing "
            else:
                auto.title = f"{ctx.author.name} laughs at {member.name} "
        else:
            auto.title = f"{ctx.author.name} is laughing"
            pass
        auto.set_image(url=random.choice(l))
        await ctx.send(embed=auto)

    #-------------->WINK COMMAND 😉<--------------#
    @bot.command()
    async def wink(ctx,member: discord.Member = None):
        # Example usage
        query = ["Anime wink","winking anime","anime winking","cute anime wink"]
        l = get_top_8_gifs(random.choice(query))
        auto=discord.Embed(color=discord.Color.random())
        if member:
            if member.name==ctx.author.name:
                auto.title = f"{ctx.author.name} is winking "
            else:
                auto.title = f"{ctx.author.name} winks at {member.name} "
        else:
            auto.title = f"{ctx.author.name} is winking"
            pass
        auto.set_image(url=random.choice(l))
        await ctx.send(embed=auto)

    #-------------->CHEER COMMAND 🥳<--------------#
    @bot.command()
    async def cheer(ctx,member: discord.Member = None):
        # Example usage
        query = ["Anime cheer","cheering anime","anime cheering","cute anime cheer"]
        l = get_top_8_gifs(random.choice(query))
        auto=discord.Embed(color=discord.Color.random())
        if member:
            if member.name==ctx.author.name:
                auto.title = f"{ctx.author.name} is cheering "
            else:
                auto.title = f"{ctx.author.name} cheers {member.name} "
        else:
            auto.title = f"{ctx.author.name} is cheering"
            pass
        auto.set_image(url=random.choice(l))
        await ctx.send(embed=auto)


    #-------------->THINK COMMAND 🤔<--------------#
    @bot.command()
    async def think(ctx,member: discord.Member = None):
        # Example usage
        query = ["Anime think","thinking anime","anime thinking","cute anime think"]
        l = get_top_8_gifs(random.choice(query))
        auto=discord.Embed(color=discord.Color.random())
        if member:
            if member.name==ctx.author.name:
                auto.title = f"{ctx.author.name} is thinking hard!! "
            else:
                auto.title = f"{ctx.author.name} thinks about {member.name} "
        else:
            auto.title = f"{ctx.author.name} is thinking hard!!"
            pass
        auto.set_image(url=random.choice(l))
        await ctx.send(embed=auto)

    #-------------->HIGHFIVE COMMAND 🙏🏻<--------------#
    @bot.command()
    async def highfive(ctx,member: discord.Member = None):
        # Example usage
        query = ["Anime highfive","highfiving anime","anime highfiving","cute anime highfive"]
        l = get_top_8_gifs(random.choice(query))
        auto=discord.Embed(color=discord.Color.random())
        if member:
            if member.name==ctx.author.name:
                auto.title = f"We are the best fr {ctx.author.name} "
            else:
                auto.title = f"{ctx.author.name} highfives {member.name} "
        else:
            auto.title = f"We are the best fr {ctx.author.name}"
            pass
        auto.set_image(url=random.choice(l))
        await ctx.send(embed=auto)

    #-------------->SALUTE COMMAND 🫡<--------------#
    @bot.command()
    async def salute(ctx,member: discord.Member = None):
        # Example usage
        query = ["Anime salute","saluting anime","anime saluting","cute anime salute"]
        l = get_top_8_gifs(random.choice(query))
        auto=discord.Embed(color=discord.Color.random())
        if member:
            if member.name==ctx.author.name:
                auto.title = f"{ctx.author.name} salutes 🫡"
            else:
                auto.title = f"{ctx.author.name} salutes {member.name} "
        else:
            auto.title = f"{ctx.author.name} salutes 🫡"
            pass
        auto.set_image(url=random.choice(l))
        await ctx.send(embed=auto)

    #-------------->APPLAUD COMMAND 👏🏻<--------------#
    @bot.command()
    async def applaud(ctx,member: discord.Member = None):
        # Example usage
        query = ["Anime applaud","applauding anime","anime applauding","cute anime applaud"]
        l = get_top_8_gifs(random.choice(query))
        auto=discord.Embed(color=discord.Color.random())
        if member:
            if member.name==ctx.author.name:
                auto.title = f"{ctx.author.name} applauds!"
            else:
                auto.title = f"{ctx.author.name} applauds {member.name} "
        else:
            auto.title = f"{ctx.author.name} applauds!"
            pass
        auto.set_image(url=random.choice(l))
        await ctx.send(embed=auto)


    #-------------->CLAP COMMAND 👏🏻<--------------#
    @bot.command()
    async def clap(ctx,member: discord.Member = None):
        # Example usage
        query = ["Anime clap","clapping anime","anime clapping","cute anime clap"]
        l = get_top_8_gifs(random.choice(query))
        auto=discord.Embed(color=discord.Color.random())
        if member:
            if member.name==ctx.author.name:
                auto.title = f"{ctx.author.name} is clapping 👏🏻"
            else:
                auto.title = f"{ctx.author.name} claps for {member.name} "
        else:
            auto.title = f"{ctx.author.name} is clapping!"
            pass
        auto.set_image(url=random.choice(l))
        await ctx.send(embed=auto)

    #-------------->SMIRK COMMAND 😏<--------------#
    @bot.command()
    async def smirk(ctx,member: discord.Member = None):
        # Example usage
        query = ["Anime smirk","smirking anime","anime smirking","cute anime smirk"]
        l = get_top_8_gifs(random.choice(query))
        auto=discord.Embed(color=discord.Color.random())
        if member:
            if member.name==ctx.author.name:
                auto.title = f"{ctx.author.name} is smirking 😏"
            else:
                auto.title = f"{ctx.author.name} smirks on {member.name} 😼"
        else:
            auto.title = f"{ctx.author.name} is smirking!"
            pass
        auto.set_image(url=random.choice(l))
        await ctx.send(embed=auto)

    #-------------->BULLY COMMAND <--------------#
    @bot.command()
    async def bully(ctx,member: discord.Member = None):
        # Example usage
        query = ["Anime bully","bullying anime","anime bullying","cute anime bully"]
        l = get_top_8_gifs(random.choice(query))
        auto=discord.Embed(color=discord.Color.random())
        if member:
            if member.name==ctx.author.name:
                auto.title = f" Hahaha how's that {ctx.author.name}"
            else:
                auto.title = f"{ctx.author.name} is bullying {member.name} >:)"
        else:
            auto.title = f"{ctx.author.name} gets bullied"
            pass
        auto.set_image(url=random.choice(l))
        await ctx.send(embed=auto)
    @bot.command()
    async def help(ctx):
        auto = discord.Embed(title="Help Commands", description="Prefix is ```akio```\n1. ***NEW*** Ask me anything or generate an ai image using ```akio query <your question here>```\n2. Hehe, wanna hug/kiss/kill/slap etc. someone? Just mention them! Use ```akio <action> <mention>```\n ``` current actions available: hug kiss slap kill blush smirk tickle roast kick shrug pat bully clap applaud salute highfive think cheer wink laugh wave dances spin and pout```\n3. I can repeat your sentences as well as sing with you :D Use ```akio echo <sentence to repeat>```\n4. GAMES!!! (under development) ```akio guess, akio rps```\n5. Maths! do some fun maths operations currently available ```add sub mul div root square log power```\n6. Fetch pfp of a user by ```akio pfp <mention>```\n6. kuru~ kuru~ kuru~ kuru~ kuru~ kuru~ kuru~ kuru~ kuru kururin kuru kururin ```akio kuru```\n7. Translate any language! ```akio tl <sentence to translate>```\n8. Get random drawing ideas, random numbers and more ```akio draw | akio flip | akio ask```\n9. Calculate love percentage!!! ```akio love user1 user2```" , color=discord.Color.random())
        avatar_url = bot.user.avatar.url
        auto.set_thumbnail(url=avatar_url)
        await ctx.send(embed=auto)