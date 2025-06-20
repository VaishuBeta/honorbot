import discord
from discord.ext import commands
import math
import os
import asyncio

# Enable all needed intents
intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)
bot.run(os.getenv("BotToken"))

# In-memory storage for honor (user_id -> honor)
honor_stats = {}

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")

@bot.command()
async def honor(ctx, *args):
    if len(args) == 0:
        await ctx.send("No, you have to use `!honor check [user]` or `!honor @user amount`")
        return

    if args[0].lower() == "check":
        member = ctx.author
        if len(args) > 1:
            member = await commands.MemberConverter().convert(ctx, args[1])
        points = honor_stats.get(member.id, 0)

        #HONOR CAPS SHOULD BE -1000 AND 1000
        emojiNum = abs(math.floor(points / 100))
        currMessage = ""

        for i in range(emojiNum):
            if points > 0: currMessage = currMessage + "<:highhonor:1283293149644456071>"
            if points < 0: currMessage = currMessage + "<:lowhonor:1283293077884239913>"
        for i in range(10 - emojiNum):
            currMessage = currMessage + "⚫"
        await ctx.send(f"{member.display_name} has " + "**" f"{points} honor: " + "**" + currMessage)
        #await ctx.send(f"{member.display_name} has {points} honor points.")


        return

    # Else assume modify command
    if len(args) < 2:
        await ctx.send("No, you have to use `!honor @user amount`")
        return

    try:
        member = await commands.MemberConverter().convert(ctx, args[0])
        amount = int(args[1])

    except Exception:
        await ctx.send("Invalid format. Usage: `!honor @user amount`")
        return

    try:
        reason = string(args[2])
    except:
        reason = ""

    if not ctx.author.guild_permissions.manage_roles:
        await ctx.send("You don't decide who's honorable or not.")
        return

    if member.bot:
        await ctx.send("Bots don't have honor.")
        return

    if ctx.author.id == member.id:
        await ctx.send("You don't decide your own honor.")
        return

    old = honor_stats.get(member.id, 0)

    #'''
    if (amount + old > 1000):
        await ctx.send("**<:highhonor:1283293149644456071> Highest honor reached.**")
        honor_stats[member.id] = 1000
        return
    elif (amount + old < -1000):
        await ctx.send("**<:lowhonor:1283293077884239913> Lowest honor reached.**")
        honor_stats[member.id] = -1000
        return
    else:
        honor_stats[member.id] = old + amount
    #'''
    honor_stats[member.id] = old + amount
    emojiToUse = "highhonor"
    if amount > 0: emojiToUse = "<:highhonor:1283293149644456071> +"
    if amount < 0: emojiToUse = "<:lowhonor:1283293077884239913> "

    if reason == "":
        await ctx.send("**" + emojiToUse + str(amount) + " honor" + "**" + " for " + f"{member.display_name}")
    elif reason != "":
        await ctx.send("**" + emojiToUse + str(amount) + " honor" + "**" + " for " + f"{member.display_name}" + " for " + reason)


@bot.command()
async def horsey(ctx):
    await ctx.send("i <3 my horsey and my horsey <3 me")

@bot.command()
async def howtouse(ctx):
    await ctx.send("Use `!honor @user amount` to raise or reduce someone's honor. \n Use `!honor check @user` to see someone's honor standing.")

@bot.command(name="resethonor")
@commands.has_role("Mod")
async def reset_honor(ctx):
    message = await ctx.send("**Are you sure? This cannot be undone.** (React with <:highhonor:1283293149644456071> or <:lowhonor:1283293077884239913> to confirm/cancel)")
    await message.add_reaction("<:highhonor:1283293149644456071>")
    await message.add_reaction("<:lowhonor:1283293077884239913>")

    def check(reaction, user):
        return (
            user == ctx.author
            and str(reaction.emoji) in ["<:highhonor:1283293149644456071>","<:lowhonor:1283293077884239913>"]
            and reaction.message.id == message.id
        )

    try:
        reaction, user = await bot.wait_for("reaction_add", timeout=30.0, check=check)

        if str(reaction.emoji) == "<:highhonor:1283293149644456071>":
            honor_stats.clear()
            await ctx.send("All honor scores have been reset to **0**.")
        else:
            await ctx.send("Reset cancelled.")
    except asyncio.TimeoutError:
        await ctx.send("Timed out. Reset cancelled.")

@bot.event
async def on_message(message):
    print(f"Message from {message.author}: {message.content}")
    await bot.process_commands(message)  # important to allow commands to work

@honor.error
async def honor_error(ctx, error):
    if isinstance(error, commands.MissingRole):
        await ctx.send("You don't decide who's honorable or not.")
    elif isinstance(error, commands.MissingRequiredArgument):
        await ctx.send("Invalid command.")
    elif isinstance(error, commands.BadArgument):
        await ctx.send("Invalid format. Make sure to tag a user and use a valid number.")
    else:
        await ctx.send("An error occurred.")

bot.run(BotToken)