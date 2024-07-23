import discord
def setup(bot):
    @bot.command()
    async def help(ctx):
        auto = discord.Embed(
            title="Help Commands❗",
            description=(
                "Prefix is `akio`\n"
                "1. ***NEW*** Ask me anything or generate an ai image using ```akio query <your question here>```\n"
                "2. Hehe, wanna hug/kiss/kill/slap etc. someone? Just mention them! Use ```akio <action> <mention>```\n ```Current actions available: hug kiss slap kill blush smirk tickle roast kick shrug pat bully clap applaud salute highfive think cheer wink laugh wave dances spin and pout```\n"
                "3. I can repeat your sentences as well as sing with you :D Use ```akio echo <sentence to repeat>```\n"
                "4. GAMES!!! (under development) ```akio guess, akio rps```\n"
                "5. Maths! do some fun maths operations currently available ```add sub mul div root square log power```\n"
                "6. Fetch pfp of a user by ```akio pfp <mention>```\n"
                "7. Translate any language! ```akio tl <sentence to translate>```\n"
                "8. Get random drawing ideas, random numbers and more ```akio draw | akio flip | akio ask```\n"
                "9. Calculate love percentage!!! ```akio love user1 user2```\n"
                "10. MUSIC (Beta) ```akio play <url or name> | akio queue```\n"
                "11. kuru~ kuru~ kuru~ kuru~ ```akio kuru```" ), color=discord.Color.random())
        avatar_url = bot.user.avatar.url
        auto.set_thumbnail(url=avatar_url)
        await ctx.send(embed=auto)