import math
import discord
from discord.ext import commands
import random
import asyncio
def setup(bot):
    @bot.command()
    async def num(ctx, query):
        try:
            l = query.split(',')
            if len(l) == 2:
                num1 = int(l[0])
                num2 = int(l[1])
                if num1 <= num2:
                    random_num = random.randint(num1, num2)
                    await ctx.send(f"I think <:gurathink:1124874101434097756> {random_num}")
                else:
                    await ctx.send(f"{ctx.author.name}, num1 must be less than or equal to num2.")
            else:
                await ctx.send("Please provide input in this format: akio num num1,num2")
        except ValueError:
            await ctx.send("Please provide input in this format: akio num num1,num2")

    @bot.command()
    async def root(ctx,number):
        number=float(number)
        if number<0:
            await ctx.send("Please provide a non negative number :(")
            return
        number=number**0.5
        await ctx.send(str(number))

    @bot.command()
    async def square(ctx,number):
        number=float(number)
        number=number*number
        await ctx.send(str(number))

    @bot.command()
    async def power(ctx, query):
        try:
            l = query.split(',')
            if len(l) == 2:
                await ctx.send("%.2f" % math.pow(float(l[0]), float(l[1])))
            else:
                await ctx.send("Please provide input in this format: akio power num1,num2")
        except:
            await ctx.send("Invalid input. Please provide numbers in the correct format.")

    @bot.command()
    async def log(ctx, query):
        try:
            l = query.split(',')
            if len(l) == 2:
                await ctx.send("%.2f" % math.log(float(l[0]), float(l[1])))
            else:
                await ctx.send("Please provide input in this format: akio log num,base with base > 1")
        except:
            await ctx.send("Invalid input. Please provide numbers in the correct format.")

    @bot.command()
    async def add(ctx, query):
        try:
            l = query.split(',')
            if len(l) == 2:
                await ctx.send(str(float(l[0])+float(l[1])))
            else:
                await ctx.send("Please provide input in this format: akio log num1,num2")
        except:
            await ctx.send("Invalid input. Please provide numbers in the correct format.")

    @bot.command()
    async def sub(ctx, query):
        try:
            l = query.split(',')
            if len(l) == 2:
                await ctx.send(str(float(l[0])-float(l[1])))
            else:
                await ctx.send("Please provide input in this format: akio log num1,num2")
        except:
            await ctx.send("Invalid input. Please provide numbers in the correct format.")

    @bot.command()
    async def mul(ctx, query):
        try:
            l = query.split(',')
            if len(l) == 2:
                await ctx.send(str(float(l[0])*float(l[1])))
            else:
                await ctx.send("Please provide input in this format: akio log num1,num2")
        except:
            await ctx.send("Invalid input. Please provide numbers in the correct format.")

    @bot.command()
    async def div(ctx, query):
        try:
            l = query.split(',')
            if len(l) == 2:
                await ctx.send(str(float(l[0])/float(l[1])))
            else:
                await ctx.send("Please provide input in this format: akio log num1,num2")
        except:
            await ctx.send("Invalid input. Please provide numbers in the correct format.")
    
    # bot.add_command(num)
    # bot.add_command(root)
    # bot.add_command(square)
    # bot.add_command(power)
    # bot.add_command(log)
    # bot.add_command(add)
    # bot.add_command(sub)
    # bot.add_command(mul)
    # bot.add_command(div)

