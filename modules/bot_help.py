import discord
def setup(bot):
    @bot.hybrid_command(description="Get help on how to use the bot")
    async def help(ctx):
        auto = discord.Embed(
            title="Help Commands❗",
            description=(
                "Prefix is `akio/Akio`\n"
                "Ask me anything <:miku_dab:1228484805562208416> ```query <your question here> or mention me!```\n"
                "MyAnimeList ```anime <name>, manga <name>, user <mal username>, char <name>, seasonal <year(optional)> <season>, top <type(ova, tv, etc)>``` \n"
                "Actions! ```<action> <mention>```\n ```Current actions available: hug kiss slap kill blush smirk tickle roast kick shrug pat bully clap applaud salute highfive think cheer wink laugh wave dances spin and pout```\n"
                "Repeat your sentences. ```echo <sentence to repeat>, say <your message>``` \n"
                "GAMES and Ideas!!! ```guess, rps, tictactoe, flip, ask, draw, dots```\n"
                "Maths! ```add sub mul div root square log power```\n"
                "Fetch pfp of a user by ```pfp <user>```\n"
                "Translate any language to English! ```tl <sentence to translate>```\n"
                "Calculate love percentage!!! ```love user1 user2```\n"
                "MUSIC (Not Working) ```play <url or name> | akio queue```\n"
                "kuru~ kuru~ kuru~ kuru~ ```akio kuru```" ), color=discord.Color.random())
        avatar_url = bot.user.avatar.url
        auto.set_thumbnail(url=avatar_url)
        await ctx.send(embed=auto)