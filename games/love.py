import discord
import random

class LoveView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=60)
        
    @discord.ui.button(label="Re-calculate <:pinkheart:1399583453258977440>", style=discord.ButtonStyle.red)
    async def recalculate(self, interaction: discord.Interaction, button: discord.ui.Button):
        new_percentage = random.randint(1, 100)
        embed = interaction.message.embeds[0]
        embed.set_field_at(0, name=embed.fields[0].name, value=f"Love Percentage: {new_percentage}%")
        await interaction.response.edit_message(embed=embed)

def setup(bot):
    @bot.hybrid_command(description="Calculate love percentage")
    async def love(ctx, user1: discord.Member, user2: discord.Member):
        embed = discord.Embed(title="<:pinkheart:1399583453258977440> Love Calculator", color=discord.Color.red())
        cat_id = 952954729061810246
        my_id = 603003195911831573
        # Always 100% for you and cat, in any order
        if (user1.id == cat_id and user2.id == my_id) or (user1.id == my_id and user2.id == cat_id):
            love_percentage = 100
            user1_name = user1.nick if user1.nick else user1.name
            user2_name = user2.nick if user2.nick else user2.name
            embed.add_field(
                name=f"{user1_name} <:pinkheart:1399583453258977440> {user2_name}",
                value=f"Love Percentage: {love_percentage}%",
                inline=False
            )
            embed.set_footer(text="Click the button below to re-calculate")
            view = LoveView()
            await ctx.send(embed=embed, view=view)
            return
        if user1 == user2:
            love_percentage = 101
            user1_name = user1.nick if user1.nick else user1.name
            embed.description = f"{user1_name} loves themselves the most! <:pinkheart:1399583453258977440>\nLove Percentage: {love_percentage}%"
        else:
            love_percentage = random.randint(1, 100)
            user1_name = user1.nick if user1.nick else user1.name
            user2_name = user2.nick if user2.nick else user2.name
            if bot.user in [user1, user2]:
                love_percentage = 100
                embed.description = f"Awww {bot.user.name} loves you a lot! ( ´･･)ﾉ(･･ ˶)\nLove Percentage: {love_percentage}%"
            else:
                embed.add_field(
                    name=f"{user1_name} <:pinkheart:1399583453258977440> {user2_name}",
                    value=f"Love Percentage: {love_percentage}%",
                    inline=False
                )
                embed.set_footer(text="Click the button below to re-calculate")
                view = LoveView()
                await ctx.send(embed=embed, view=view)
                return
        await ctx.send(embed=embed)
