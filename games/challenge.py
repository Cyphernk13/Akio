from games.shared import active_challenges

def setup(bot):
    @bot.hybrid_command(description="Cancel your active challenge")
    async def cancel(ctx):
        if ctx.author.id in active_challenges:
            del active_challenges[ctx.author.id]
            await ctx.send("<a:verify:1399579399107379271> Your active challenge has been canceled!", ephemeral=True)
        else:
            await ctx.send("❌ You don't have any active challenges!", ephemeral=True)
