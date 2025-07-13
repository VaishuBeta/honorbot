import discord
from discord.ext import commands, tasks
import math
import os
import asyncio
import json
import threading
from aiohttp import web
from datetime import datetime, timedelta, timezone

######## WEB SERVICE FOR RENDER ########
async def handle(request):
    return web.Response(text="Bot is running!")

def run_web():
    port = int(os.environ.get("PORT", 8000))
    app = web.Application()
    app.add_routes([web.get("/", handle)])
    web.run_app(app, port=port, handle_signals=False)

threading.Thread(target=run_web, daemon=True).start()
######## END OF COMMENT TAG ########

intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)

HONOR_FILE = "honor_data.json"
JUDGEMENTS_FILE = "judgements_data.json"
JUDGEMENT_LIMIT = 5  # max judgments per day

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

honor_stats = load_honor_data()

# Judgements data structure: {guild_id: {user_id: {"uses": int, "reset": datetime, "banned": bool}}}
# Load judgments data from file
def load_judgements_data():
    if os.path.isfile(JUDGEMENTS_FILE):
        with open(JUDGEMENTS_FILE, "r") as f:
            raw = json.load(f)
            return {
                int(gid): {
                    int(uid): {
                        "uses": v.get("uses", 0),
                        "reset": datetime.fromisoformat(v.get("reset")),
                        "banned": v.get("banned", False),
                    }
                    for uid, v in users.items()
                }
                for gid, users in raw.items()
            }
    return {}

# Save judgments data to file
def save_judgements_data(data):
    serializable = {
        str(gid): {
            str(uid): {
                "uses": v["uses"],
                "reset": v["reset"].isoformat(),
                "banned": v["banned"],
            }
            for uid, v in users.items()
        }
        for gid, users in data.items()
    }
    with open(JUDGEMENTS_FILE, "w") as f:
        json.dump(serializable, f, indent=4)

def get_judgement_data(guild_id: int, user_id: int):
    now = datetime.now(timezone.utc)
    reset_time = now + timedelta(days=1)

    if guild_id not in judgements_data:
        judgements_data[guild_id] = {}

    user_data = judgements_data[guild_id].get(user_id)

    if not user_data:
        judgements_data[guild_id][user_id] = {
            "uses": 0,
            "reset": reset_time,
            "banned": False,
        }
    else:
        if now >= user_data["reset"]:
            judgements_data[guild_id][user_id]["uses"] = 0
            judgements_data[guild_id][user_id]["reset"] = reset_time

    save_judgements_data(judgements_data)
    return judgements_data[guild_id][user_id]

judgements_data = load_judgements_data()

@bot.command(name="exportjudgements")
@commands.is_owner()
async def export_judgements(ctx):
    if not os.path.isfile(JUDGEMENTS_FILE):
        await ctx.send("No judgments data to export.")
        return

    try:
        await ctx.send("Here is the exported judgments data:", file=discord.File(JUDGEMENTS_FILE))
    except Exception as e:
        await ctx.send("Failed to export judgments data.")
        print("ExportJudgements error:", e)

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

@bot.command()
async def honor(ctx, *args):
    if len(args) == 0:
        await ctx.send("No, you have to use `!honor check [user]` or `!honor @user amount`")
        return

    # Special case for 'check'
    if args[0].lower() == "check":
        member = ctx.author
        if len(args) > 1:
            try:
                member = await commands.MemberConverter().convert(ctx, args[1])
            except:
                await ctx.send("Could not find that member.")
                return
        points = honor_stats.get(member.id, 0)

        emojiNum = abs(math.floor(points / 100))
        currMessage = ""

        for i in range(emojiNum):
            if points > 0:
                currMessage += "<:highhonor:1283293149644456071>"
            elif points < 0:
                currMessage += "<:lowhonor:1283293077884239913>"
        for i in range(5 - emojiNum):
            currMessage += "\u26AB"

        await ctx.send(f"{member.display_name} has **{points} honor:** {currMessage}")
        return

    # For up/down commands (without mod role)
    if len(args) == 2 and args[1].lower() in ("up", "down"):
        try:
            member = await commands.MemberConverter().convert(ctx, args[0])
        except:
            await ctx.send("Could not find that member.")
            return
        # Check if the command user is banned from judgments
        jd = get_judgement_data(ctx.guild.id, ctx.author.id)
        if jd["banned"]:
            await ctx.send("You are banned from passing judgments.")
            return

        if jd["uses"] >= JUDGEMENT_LIMIT:
            await ctx.send("You have used your daily judgment limit.")
            return
            
        if member.bot:
            await ctx.send("Bots don't have honor.")
            return

        if ctx.author.id == member.id:
            await ctx.send("You don't decide your own honor.")
            return
        
        # Modify honor by +1 or -1 depending on up or down
        amount = 1 if args[1].lower() == "up" else -1

        old = honor_stats.get(member.id, 0)
        new_honor = old + amount
        if new_honor > 500:
            new_honor = 500
            await ctx.send("**<:highhonor:1283293149644456071> Highest honor reached.**")
        elif new_honor < -500:
            new_honor = -500
            await ctx.send("**<:lowhonor:1283293077884239913> Lowest honor reached.**")

        honor_stats[member.id] = new_honor
        save_honor_data(honor_stats)

        emojiToUse = "<:highhonor:1283293149644456071> +" if amount > 0 else "<:lowhonor:1283293077884239913> "
        await ctx.send(f"**{emojiToUse}{amount} honor** for {member.display_name}")

        jd["uses"] += 1
        return

    # Otherwise, normal mod command with amount number
    if len(args) < 2:
        await ctx.send("No, you have to use `!honor @user amount`")
        return

    try:
        member = await commands.MemberConverter().convert(ctx, args[0])
        amount = int(args[1])
    except Exception:
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
    new_honor = old + amount

    if new_honor > 500:
        honor_stats[member.id] = 500
        await ctx.send("**<:highhonor:1283293149644456071> Highest honor reached.**")
        save_honor_data(honor_stats)
        return
    elif new_honor < -500:
        honor_stats[member.id] = -500
        await ctx.send("**<:lowhonor:1283293077884239913> Lowest honor reached.**")
        save_honor_data(honor_stats)
        return
    else:
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
    await ctx.send("Use `!honor @user amount` to raise or reduce someone's honor (mods only).\n Use `!honor check @user` to see someone's honor standing.\n Use !leaderboard to see the honor leaderboard.\n Non-mods can use `!honor @user up` or `!honor @user low` up to 5 times daily.")

@bot.command(name="exporthonor")
@commands.is_owner()
async def export_honor(ctx):
    if not honor_stats:
        await ctx.send("No honor data to export.")
        return

    try:
        with open(HONOR_FILE, "w") as f:
            json.dump(honor_stats, f, indent=4)
        await ctx.send("Here is the exported honor data:", file=discord.File(HONOR_FILE))
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

@bot.command()
@commands.has_role("Mod")
async def edit(ctx, member: discord.Member):
    if member.guild_permissions.manage_roles:
        await ctx.send("You cannot edit a moderator’s judgments.")
        return

    jd = get_judgement_data(ctx.guild.id, member.id)
    emoji = "<:highhonor:1283293149644456071>" if honor_stats.get(member.id, 0) >= 0 else "<:lowhonor:1283293077884239913>"
    honor_points = honor_stats.get(member.id, 0)

    msg = f"""**{member.display_name}** - {emoji} **{honor_points} honor**
-# {JUDGEMENT_LIMIT - jd['uses']} judgments remaining for today

**Actions:**
1. Refill judgments
2. Drain judgments
3. {"Unban" if jd['banned'] else "Ban"} from passing judgments"""

    response = await ctx.send(msg)
    for emoji in ["1️⃣", "2️⃣", "3️⃣"]:
        await response.add_reaction(emoji)
        await asyncio.sleep(0.5)  # 0.5 sec pause helps avoid rate limit

    def check(reaction, user):
        return (
            user == ctx.author
            and reaction.message.id == response.id
            and str(reaction.emoji) in ["1️⃣", "2️⃣", "3️⃣"]
        )

    try:
        reaction, _ = await bot.wait_for("reaction_add", timeout=30.0, check=check)
        emoji = str(reaction.emoji)

        if emoji == "1️⃣":
            jd["uses"] = 0
            jd["reset"] = datetime.utcnow() + timedelta(days=1)
            await ctx.send(f"{member.display_name}'s judgments refilled.")
        elif emoji == "2️⃣":
            jd["uses"] = JUDGEMENT_LIMIT
            await ctx.send(f"{member.display_name}'s judgments drained.")
        elif emoji == "3️⃣":
            jd["banned"] = not jd["banned"]
            action = "unbanned" if not jd["banned"] else "banned"
            await ctx.send(f"{member.display_name} has been {action} from passing judgments.")

    except asyncio.TimeoutError:
        await ctx.send("Timeout. No changes made.")

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
