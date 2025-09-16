import discord
from discord.ext import commands
import aiohttp
import random
from typing import Optional

def setup(bot):
    # Matt Bas Insult API
    INSULT_API_BASE = "https://insult.mattbas.org/api/insult"
    
    # Custom responses for self-roasting protection
    SELF_ROAST_RESPONSES = [
        "Aww {author}, don't be so hard on yourself! You're amazing!",
        "{author}, no self-bullying allowed here! You're wonderful!",
        "Hey {author}, be nice to yourself! You deserve kindness!",
        "{author}, I refuse to roast you - you're too precious!",
        "Nope {author}, I'm giving you compliments instead! You're fantastic!"
    ]
    
    async def fetch_insult(target_name: str = None) -> dict:
        """Fetch an insult from the Matt Bas Insult API"""
        try:
            params = {}
            
            # If we have a target, use the 'who' parameter
            if target_name:
                params['who'] = target_name
            
            async with aiohttp.ClientSession() as session:
                async with session.get(INSULT_API_BASE, params=params) as response:
                    if response.status == 200:
                        insult_text = await response.text()
                        return {
                            'success': True,
                            'insult': insult_text.strip(),
                            'target': target_name
                        }
                    
                    # Fallback if API fails
                    fallback_insults = [
                        "You're like a cloud... when you disappear, it's a beautiful day!",
                        "I'd explain it to you, but I left my English-to-Silly dictionary at home!",
                        "You're not stupid, you just have bad luck thinking!",
                        "I would roast you, but my mom told me not to burn trash!",
                        "You bring everyone so much joy... when you leave the room!"
                    ]
                    
                    selected_insult = random.choice(fallback_insults)
                    if target_name:
                        # Replace "You" with the target's name for third person
                        selected_insult = selected_insult.replace("You're", f"{target_name} is")
                        selected_insult = selected_insult.replace("you", target_name.lower())
                    
                    return {
                        'success': True,
                        'insult': selected_insult,
                        'target': target_name
                    }
                        
        except Exception as e:
            print(f"Error fetching insult: {e}")
            return {
                'success': False,
                'error': str(e)
            }

    @bot.hybrid_command(
        name="roast", 
        description="Roast yourself or mention someone to roast them!"
    )
    async def roast(ctx, member: Optional[discord.Member] = None):
        """
        Roast command that can target a specific member or default to the command user.
        Usage: 
        - /roast (or akio roast) - roasts the command user
        - /roast @user (or akio roast @user) - roasts the mentioned user
        """
        
        # Determine the target
        target = member
        target_name = None
        
        if target:
            if target.id == ctx.author.id:
                # Self-mention case - give compliment instead
                response = random.choice(SELF_ROAST_RESPONSES).format(author=ctx.author.display_name)
                await ctx.send(response)
                return
            else:
                # Mention someone else
                target_name = target.display_name
        
        # Show typing indicator for dramatic effect
        async with ctx.typing():
            # Fetch insult from API
            result = await fetch_insult(target_name)
            
            if not result['success']:
                await ctx.send("I couldn't come up with a good roast right now. Try again later!")
                return
            
            # Send the plain text insult
            await ctx.send(result['insult'])

    # Error handler for the roast command
    @roast.error
    async def roast_error(ctx, error):
        if isinstance(error, commands.MemberNotFound):
            await ctx.send("I couldn't find that member! Make sure you're mentioning someone in this server.")
        else:
            await ctx.send("Something went wrong while trying to generate a roast!")
            print(f"Roast command error: {error}")