import discord
from discord.ext import commands, tasks
import math
import os
import asyncio
import json
import threading
from aiohttp import web

######## WEB SERVICE FOR RENDER ########
async def handle(request):
    return web.Response(text="Bot is running!")

def run_web():
    port = int(os.environ.get("PORT", 8000))
    app = web.Application()
    app.add_routes([web.get("/", handle)])
    web.run_app(app, port=port, handle_signals=False)

# Start the web server in a separate thread
threading.Thread(target=run_web, daemon=True).start()
######## END OF COMMENT TAG ########

# Enable all needed intents
intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)

HONOR_FILE = "honor_data.json"

# Load honor data from file
def load_honor_data():
    if os.path.isfile(HONOR_FILE):
        with open(HONOR_FILE, "r") as f:
            raw = json.load(f)
            return {int(k): v for k, v in raw.items()}
    return {}

# Save honor data to file
def save_honor_data(data):
    with open(HONOR_FILE, "w") as f:
        json.dump(data, f)

# Load honor data on startup
honor_stats = load_honor_data()

@tasks.loop(minutes=4)
async def keep_alive_task():
    print("Running keep-alive task to maintain connection...")

@keep_alive_task.before_loop
async def before_keep_alive():
    await bot.wait_until_ready()

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")
    print("Commands loaded:", list(bot.commands))
    keep_alive_task.start()

@bot.event
async def on_disconnect():
    print("Warning: Bot disconnected from Discord!")

@bot.event
async def on_resumed():
    print("Bot resumed connection to Discord!")

@bot.event
async def on_error(event_method, *args, **kwargs):
    print(f"Error in {event_method}:")
    import traceback
    traceback.print_exc()

@bot.event
async def on_message(message):
    if message.author.bot:
        return
    if not message.content.startswith("!"):
        return
    await bot.process_commands(message)

from datetime import datetime, timedelta

# Track usage limits per user
honor_uses = {}

@bot.command()
async def honor(ctx, *args):
    if len(args) == 0:
        await ctx.send("No, you have to use `!honor check [user]`, `!honor @user amount`, or `!honor @user up/low`.")
        return

    # ===== CHECK HONOR =====
    if args[0].lower() == "check":
        member = ctx.author
        if len(args) > 1:
            try:
                member = await commands.MemberConverter().convert(ctx, args[1])
            except:
                await ctx.send("Couldn't identify the user.")
                return

        points = honor_stats.get(member.id, 0)
        emojiNum = abs(math.floor(points / 100))
        currMessage = ""

        for _ in range(emojiNum):
            if points > 0:
                currMessage += "<:highhonor:1283293149644456071>"
            elif points < 0:
                currMessage += "<:lowhonor:1283293077884239913>"
        for _ in range(5 - emojiNum):
            currMessage += "\u26AB"

        await ctx.send(f"{member.display_name} has **{points} honor:** {currMessage}")
        return

    # ===== UP/LOW FROM NON-MOD USERS =====
    if args[1].lower() in ("up", "low"):
        if any(role.name.lower() == "mod" for role in ctx.author.roles):
            await ctx.send("Mods must use `!honor @user amount`.")
            return

        try:
            target = await commands.MemberConverter().convert(ctx, args[0])
        except:
            await ctx.send("Couldn't identify the user.")
            return

        if target.bot or target.id == ctx.author.id:
            await ctx.send("You can't use this on yourself or bots.")
            return

        user_id = ctx.author.id
        now = datetime.utcnow()
        uses, last_reset = honor_uses.get(user_id, (0, now))

        if now - last_reset > timedelta(days=1):
            uses = 0
            last_reset = now

        if uses >= 5:
            await ctx.send("You've already used your 5 daily honor commands.")
            return

        amount = 1 if args[1].lower() == "up" else -1
        honor_uses[user_id] = (uses + 1, last_reset)

        old = honor_stats.get(target.id, 0)
        new_honor = max(-500, min(500, old + amount))
        honor_stats[target.id] = new_honor
        save_honor_data(honor_stats)

        emoji = "<:highhonor:1283293149644456071>" if amount > 0 else "<:lowhonor:1283293077884239913>"
        remaining = 5 - (uses + 1)

        await ctx.send(
            **f"{emoji} {'+1' if amount > 0 else '-1'} honor** for {target.display_name}\n"
            f"-#{remaining} more judgements allowed for today"
        )
        return

    # ===== MOD HONOR ASSIGNMENT =====
    if len(args) < 2:
        await ctx.send("No, you have to use `!honor check`, `!honor @user amount`, or `!honor @user up/low`")
        return

    try:
        member = await commands.MemberConverter().convert(ctx, args[0])
        amount = int(args[1])
    except:
        await ctx.send("Invalid format. Usage: `!honor @user amount`")
        return

    reason = " ".join(args[2:]) if len(args) > 2 else ""

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
    new_honor = max(-500, min(500, old + amount))
    honor_stats[member.id] = new_honor
    save_honor_data(honor_stats)

    emojiToUse = "<:highhonor:1283293149644456071> +" if amount > 0 else "<:lowhonor:1283293077884239913> "
    if reason == "":
        await ctx.send(f"**{emojiToUse}{amount} honor** for {member.display_name}")
    else:
        await ctx.send(f"**{emojiToUse}{amount} honor** for {member.display_name} for {reason}")

@bot.command()
async def leaderboard(ctx, *args):
    limit = 5           # default
    sort_order = "high" # default
    skip_zero = False

    for arg in args:
        if arg.lower() == "skip":
            skip_zero = True
        elif arg.lower() in ("high", "low"):
            sort_order = arg.lower()
        elif arg.lower() == "all":
            limit = None
        else:
            try:
                parsed = int(arg)
                if parsed > 0:
                    limit = parsed
            except ValueError:
                pass  # ignore unknown args

    # Filter honor_stats for members in this guild
    members_with_honor = []
    for user_id, honor in honor_stats.items():
        member = ctx.guild.get_member(user_id)
        if member:
            if skip_zero and honor == 0:
                continue
            members_with_honor.append((member.display_name, honor))

    if not members_with_honor:
        await ctx.send("No leaderboard entries found for this server.")
        return

    # Sort the list
    reverse = sort_order == "high"
    members_with_honor.sort(key=lambda x: x[1], reverse=reverse)

    if limit is not None:
        members_with_honor = members_with_honor[:limit]

    leaderboard_msg = "**Leaderboard:**\n"
    for i, (name, honor) in enumerate(members_with_honor, start=1):
        emoji = "<:highhonor:1283293149644456071>" if honor >= 0 else "<:lowhonor:1283293077884239913>"
        leaderboard_msg += f"{emoji} {i}. {name} for **{honor} honor**\n"

    await ctx.send(leaderboard_msg)

@bot.command()
async def horsey(ctx):
    await ctx.send("i <3 my horsey and my horsey <3 me")

@bot.command()
async def howtouse(ctx):
    await ctx.send("Use `!honor @user amount` to raise or reduce someone's honor (mods only).\n Use `!honor check @user` to see someone's honor standing.\n Use !leaderboard to see the honor leaderboard.")

@bot.command(name="exporthonor")
@commands.is_owner()
async def export_honor(ctx):
    if not honor_stats:
        await ctx.send("No honor data to export.")
        return

    try:
        # Dump honor stats into a JSON file
        with open("honor_data.json", "w") as f:
            json.dump(honor_stats, f, indent=4)

        await ctx.send("Here is the exported honor data:", file=discord.File("honor_data.json"))

    except Exception as e:
        await ctx.send("Failed to export honor data.")
        print("Export error:", e)


@bot.command(name="resethonor")
@commands.has_role("Mod")
async def reset_honor(ctx):
    message = await ctx.send("**Are you sure? This cannot be undone.** (React with <:highhonor:1283293149644456071> or <:lowhonor:1283293077884239913> to confirm/cancel)")
    await message.add_reaction("<:highhonor:1283293149644456071>")
    await message.add_reaction("<:lowhonor:1283293077884239913>")

    def check(reaction, user):
        return (
            user == ctx.author
            and str(reaction.emoji) in ["<:highhonor:1283293149644456071>", "<:lowhonor:1283293077884239913>"]
            and reaction.message.id == message.id
        )

    try:
        reaction, user = await bot.wait_for("reaction_add", timeout=30.0, check=check)

        if str(reaction.emoji) == "<:highhonor:1283293149644456071>":
            honor_stats.clear()
            save_honor_data(honor_stats)
            await ctx.send("All honor scores have been reset to **0**.")
        else:
            await ctx.send("Reset cancelled.")
    except asyncio.TimeoutError:
        await ctx.send("Timed out. Reset cancelled.")

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

def start_bot():
    try:
        bot.run(os.getenv("BotToken"))
    except Exception as e:
        print("Error on startup:", e)

if __name__ == "__main__":
    start_bot()
