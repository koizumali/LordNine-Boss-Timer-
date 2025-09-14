import discord
from discord.ext import commands, tasks
from datetime import datetime, timedelta
import pytz
from flask import Flask
from threading import Thread
import os
import warnings 
from pymongo import MongoClient


# Suppress the Flask development server warning
warnings.filterwarnings("ignore", message="This is a development server.")

# ===== KEEP ALIVE SERVER =====
app = Flask(__name__)

@app.route('/')
def home():
    return "Bot is alive and running! 🚀"

def run():
    app.run(host='0.0.0.0', port=8080)

def keep_alive():
    t = Thread(target=run)
    t.start()

# PASTE YOUR BOT TOKEN HERE
BOT_TOKEN = os.getenv("DISCORD_TOKEN")

# SPECIFIC CHANNEL FOR BOSS NOTIFICATIONS (replace with your channel ID)
NOTIFICATION_CHANNEL_ID = 1416149291839258696  # Replace with your actual channel ID

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='!', intents=intents)

try:
    mongodb_uri = os.environ['MONGODB_URI']
    client = MongoClient(mongodb_uri)
    db = client.boss_tracker
    bosses_collection = db.bosses
    kill_data_collection = db.kill_data
    print("Connected to MongoDB successfully!")
except Exception as e:
    print(f"Error connecting to MongoDB: {e}")
    # Fallback to in-memory storage if MongoDB fails
    bosses_collection = None
    kill_data_collection = None

# Set Philippine Timezone
PH_TZ = pytz.timezone('Asia/Manila')

# ===== REGULAR BOSSES WITH RESPAWN TIMERS =====
REGULAR_BOSSES = {
    "amentis": {"hours": 29, "location": "Land of Glory"},
    "araneo": {"hours": 24, "location": "Tyriosa 1F"},
    "asta": {"hours": 62, "location": "Silvergrass Field"},
    "baron": {"hours": 32, "location": "Battlefield of Templar"},
    "catena": {"hours": 35, "location": "Deadman 3F"},
    "duplican": {"hours": 48, "location": "Plateau of Revolution"},
    "ego": {"hours": 21, "location": "Ulan Canyon"},
    "gareth": {"hours": 32, "location": "Deadman 1F"},
    "general": {"hours": 29, "location": "Tyriosa 2F"},
    "lady": {"hours": 18, "location": "Twilight Hill"},
    "larba": {"hours": 35, "location": "Ruins of the War"},
    "livera": {"hours": 24, "location": "Protector's Ruins"},
    "metus": {"hours": 48, "location": "Plateau of Revolution"},
    "ordo": {"hours": 62, "location": "Silvergrass Field"},
    "secreta": {"hours": 62, "location": "Silvergrass Field"},
    "shuliar": {"hours": 35, "location": "Ruins of the War"},
    "supore": {"hours": 62, "location": "Silvergrass Field"},
    "titore": {"hours": 37, "location": "Deadman 2F"},
    "undomiel": {"hours": 24, "location": "Secret Lab"},
    "venatus": {"hours": 10, "location": "Corrupted Basin"},
    "viorent": {"hours": 10, "location": "Crescent Lake"},
    "wannitas": {"hours": 48, "location": "Plateau of Revolution"},
}

# ===== FIXED TIME BOSSES =====
FIXED_BOSSES = {
    "clemantis": {
        "location": "Corrupted Basin",
        "spawn_times": [
            {"day": "monday", "time": "11:30"},
            {"day": "thursday", "time": "19:00"}
        ]
    },
    "saphirus": {
        "location": "Crescent Lake",
        "spawn_times": [
            {"day": "sunday", "time": "17:00"},
            {"day": "tuesday", "time": "11:30"}
        ]
    },
    "neutro": {
        "location": "Desert of the Screaming",
        "spawn_times": [
            {"day": "tuesday", "time": "19:00"},
            {"day": "thursday", "time": "11:30"}
        ]
    },
    "thymele": {
        "location": "Twilight Hill",
        "spawn_times": [
            {"day": "monday", "time": "19:00"},
            {"day": "wednesday", "time": "11:30"}
        ]
    },
    "milavy": {
        "location": "Tyriosa 3F",
        "spawn_times": [
            {"day": "saturday", "time": "15:00"}
        ]
    },
    "ringor": {
        "location": "Battlefield of Templar",
        "spawn_times": [
            {"day": "saturday", "time": "17:00"}
        ]
    },
    "roderick": {
        "location": "Garbana 1F",
        "spawn_times": [
            {"day": "friday", "time": "19:00"}
        ]
    },
    "auraq": {
        "location": "Garbana 2F",
        "spawn_times": [
            {"day": "sunday", "time": "21:00"},
            {"day": "wednesday", "time": "21:00"}
        ]
    },
    "chaiflock": {
        "location": "Silvergrass",
        "spawn_times": [
            {"day": "saturday", "time": "22:00"}
        ]
    }
}

# Combine all bosses for easier reference
ALL_BOSSES = {**REGULAR_BOSSES, **FIXED_BOSSES}

# Store boss data in memory
boss_data = {}

def get_ph_time():
    """Get current time in Philippine Time"""
    return datetime.now(PH_TZ)

def format_time_left(time_delta):
    """Properly format time left including days"""
    total_seconds = int(time_delta.total_seconds())
    days, remainder = divmod(total_seconds, 86400)
    hours, remainder = divmod(remainder, 3600)
    minutes, seconds = divmod(remainder, 60)

    if days > 0:
        return f"{days}d {hours}h {minutes}m"
    elif hours > 0:
        return f"{hours}h {minutes}m"
    else:
        return f"{minutes}m {seconds}s"

def parse_manual_time(time_str):
    """Parse manual time input in various formats"""
    try:
        current_time = get_ph_time()

        # Try full date formats first
        try:
            # Format: YYYY-MM-DD HH:MM
            dt = datetime.strptime(time_str, "%Y-%m-%d %H:%M")
            return PH_TZ.localize(dt)
        except ValueError:
            pass

        try:
            # Format: MM/DD/YYYY HH:MM
            dt = datetime.strptime(time_str, "%m/%d/%Y %H:%M")
            return PH_TZ.localize(dt)
        except ValueError:
            pass

        try:
            # Format: MM/DD HH:MM (assume current year)
            dt = datetime.strptime(time_str, "%m/%d %H:%M")
            dt = dt.replace(year=current_time.year)
            # If the date is in the future (e.g., we're in Dec but entered Jan),
            # assume it's for last year
            if dt > current_time + timedelta(days=30):
                dt = dt.replace(year=current_time.year - 1)
            return PH_TZ.localize(dt)
        except ValueError:
            pass

        # Try time-only format (HH:MM or HH:MM:SS)
        if ':' in time_str and len(time_str) <= 8:
            try:
                # Try HH:MM:SS first
                time_part = datetime.strptime(time_str, "%H:%M:%S").time()
            except ValueError:
                try:
                    # Try HH:MM
                    time_part = datetime.strptime(time_str, "%H:%M").time()
                except ValueError:
                    raise ValueError("Invalid time format")

            # Combine with today's date
            dt = datetime.combine(current_time.date(), time_part)
            localized_dt = PH_TZ.localize(dt)

            # If the time is in the future but it's still early in the day,
            # assume it was yesterday
            if localized_dt > current_time and (current_time - localized_dt) > timedelta(hours=12):
                localized_dt -= timedelta(days=1)

            return localized_dt

        raise ValueError("Could not parse time format")

    except Exception as e:
        raise ValueError(f"Invalid time format: {str(e)}")

def get_next_spawn_time(boss_name):
    """Calculate the next spawn time for fixed-time bosses"""
    if boss_name not in FIXED_BOSSES:
        return None

    boss_info = FIXED_BOSSES[boss_name]
    current_time = get_ph_time()
    current_weekday = current_time.strftime("%A").lower()
    current_time_str = current_time.strftime("%H:%M")

    # Get all spawn times for this boss
    spawn_times = []
    for spawn_info in boss_info["spawn_times"]:
        spawn_day = spawn_info["day"]
        spawn_time_str = spawn_info["time"]

        # Parse the time
        spawn_hour, spawn_minute = map(int, spawn_time_str.split(":"))

        # Calculate days until next spawn
        days_ahead = (list(days_of_week).index(spawn_day) - list(days_of_week).index(current_weekday))
        if days_ahead < 0 or (days_ahead == 0 and spawn_time_str <= current_time_str):
            days_ahead += 7

        # Create datetime object for the next spawn
        spawn_date = current_time + timedelta(days=days_ahead)
        spawn_date = spawn_date.replace(hour=spawn_hour, minute=spawn_minute, second=0, microsecond=0)

        spawn_times.append(spawn_date)

    # Return the earliest spawn time
    return min(spawn_times)

# Days of the week for fixed boss calculations
days_of_week = ["sunday", "monday", "tuesday", "wednesday", "thursday", "friday", "saturday"]

@bot.event
async def on_ready():
    print(f'{bot.user} is online! Tracking {len(ALL_BOSSES)} bosses.')
    print(f'Using Philippine Time (PHT)')
    print(f'Notification channel ID: {NOTIFICATION_CHANNEL_ID}')
    check_spawns.start()

@bot.command(name='kill', help='Report a boss kill with current time. Example: !kill Amentis')
async def report_kill(ctx, *, boss_name):
    boss_name_lower = boss_name.lower()

    # Check if boss exists
    if boss_name_lower not in ALL_BOSSES:
        valid_bosses = ", ".join([f"`{b}`" for b in ALL_BOSSES.keys()])
        await ctx.send(f"❌ Unknown boss `{boss_name}`.\n**Valid bosses:** {valid_bosses}")
        return

    # Check if it's a fixed-time boss
    if boss_name_lower in FIXED_BOSSES:
        await ctx.send(f"ℹ️ **{boss_name.capitalize()}** is a fixed-time boss and doesn't use the kill command.\n"
                       f"Use `!schedule {boss_name}` to see its spawn times.")
        return

    # Calculate spawn time in PHT (using current time)
    respawn_hours = REGULAR_BOSSES[boss_name_lower]["hours"]
    kill_time = get_ph_time()
    spawn_time = kill_time + timedelta(hours=respawn_hours)
    location = REGULAR_BOSSES[boss_name_lower]["location"]

    # Store the data
    boss_data[boss_name_lower] = {
        "spawn_time": spawn_time,
        "notified": False,
        "kill_time": kill_time,
        "location": location,
        "type": "regular"
    }

    # Create pretty display name
    display_name = ' '.join(word.capitalize() for word in boss_name_lower.split())

    # Send confirmation
    kill_str = kill_time.strftime("%I:%M %p PHT")
    spawn_str = spawn_time.strftime("%I:%M %p PHT")
    await ctx.send(f"✅ **{display_name}** defeated at `{kill_str}`!\n📍 **Location:** {location}\n⏰ Respawns at `{spawn_str}`\n⏳ In {respawn_hours} hours")

@bot.command(name='killtime', help='Report boss kill with manual time. Example: !killtime Amentis 14:30')
async def report_kill_manual(ctx, boss_name, *, time_input):
    boss_name_lower = boss_name.lower()

    # Check if boss exists
    if boss_name_lower not in ALL_BOSSES:
        valid_bosses = ", ".join([f"`{b}`" for b in ALL_BOSSES.keys()])
        await ctx.send(f"❌ Unknown boss `{boss_name}`.\n**Valid bosses:** {valid_bosses}")
        return

    # Check if it's a fixed-time boss
    if boss_name_lower in FIXED_BOSSES:
        await ctx.send(f"ℹ️ **{boss_name.capitalize()}** is a fixed-time boss and doesn't use the kill command.\n"
                       f"Use `!schedule {boss_name}` to see its spawn times.")
        return

    try:
        # Parse the manual time input
        kill_time = parse_manual_time(time_input)
        respawn_hours = REGULAR_BOSSES[boss_name_lower]["hours"]
        spawn_time = kill_time + timedelta(hours=respawn_hours)
        location = REGULAR_BOSSES[boss_name_lower]["location"]

        # Store the data
        boss_data[boss_name_lower] = {
            "spawn_time": spawn_time,
            "notified": False,
            "kill_time": kill_time,
            "location": location,
            "type": "regular"
        }

        # Create pretty display name
        display_name = ' '.join(word.capitalize() for word in boss_name_lower.split())

        # Send confirmation
        kill_str = kill_time.strftime("%Y-%m-%d %I:%M %p PHT")
        spawn_str = spawn_time.strftime("%Y-%m-%d %I:%M %p PHT")
        await ctx.send(f"✅ **{display_name}** defeated at `{kill_str}`!\n📍 **Location:** {location}\n⏰ Respawns at `{spawn_str}`\n⏳ In {respawn_hours} hours")

    except ValueError as e:
        await ctx.send(f"❌ {e}\n**Valid formats:**\n"
                       f"• `!killtime BossName 2024-01-15 14:30`\n"
                       f"• `!killtime BossName 01/15/2024 14:30`\n"
                       f"• `!killtime BossName 01/15 14:30`\n"
                       f"• `!killtime BossName 14:30` (assumes today)")

@bot.command(name='status', help='Check status of all bosses or a specific boss. Example: !status or !status Amentis')
async def check_status(ctx, *, specific_boss=None):
    if specific_boss:
        # Show status for one specific boss
        boss_name_lower = specific_boss.lower()
        if boss_name_lower not in ALL_BOSSES:
            await ctx.send(f"❌ Unknown boss `{specific_boss}`")
            return

        # Handle fixed-time bosses differently
        if boss_name_lower in FIXED_BOSSES:
            await send_fixed_boss_status(ctx, boss_name_lower)
            return

        boss_info = boss_data.get(boss_name_lower)
        if not boss_info:
            display_name = ' '.join(word.capitalize() for word in boss_name_lower.split())
            location = REGULAR_BOSSES[boss_name_lower]["location"]
            await ctx.send(f"**{display_name}**\n📍 **Location:** {location}\nStatus: ❓ Not killed yet")
            return

        await send_boss_status(ctx, boss_name_lower, boss_info)
    else:
        # Show status for all bosses
        message = "**BOSS STATUS**\n"
        message += "```\n"
        message += "BOSS NAME           STATUS        TIME LEFT\n"
        message += "───────────────────────────────────────────\n"

        for boss_name in sorted(ALL_BOSSES.keys()):
            # Handle fixed-time bosses
            if boss_name in FIXED_BOSSES:
                next_spawn = get_next_spawn_time(boss_name)
                current_time = get_ph_time()

                if next_spawn:
                    time_left = next_spawn - current_time
                    if time_left.total_seconds() <= 0:
                        status = "✅ ALIVE"
                        time_str = "-"
                    else:
                        status = "❌ DEAD"
                        time_str = format_time_left(time_left).ljust(12)
                else:
                    status = "❓ UNKNOWN"
                    time_str = "-"

                display_name = ' '.join(word.capitalize() for word in boss_name.split())
                name_display = display_name.ljust(18)
                message += f"{name_display} {status.ljust(12)} {time_str}\n"
            else:
                # Regular bosses
                boss_info = boss_data.get(boss_name)
                status_line = get_boss_status_line(boss_name, boss_info)
                message += status_line + "\n"

        message += "```"
        await ctx.send(message)

def get_boss_status_line(boss_name, boss_info):
    """Helper function to format a single boss status line"""
    # Create pretty display name (capitalize each word)
    display_name = ' '.join(word.capitalize() for word in boss_name.split())
    name_display = display_name.ljust(18)

    if not boss_info:
        return f"{name_display} ❓ NOT KILLED     -"

    spawn_time = boss_info["spawn_time"]
    current_time = get_ph_time()

    if current_time > spawn_time:
        return f"{name_display} ✅ ALIVE         -"
    else:
        time_left = spawn_time - current_time
        time_str = format_time_left(time_left).ljust(12)
        return f"{name_display} ❌ DEAD         {time_str}"

async def send_boss_status(ctx, boss_name, boss_info):
    """Send detailed status for a single regular boss"""
    # Create pretty display name
    display_name = ' '.join(word.capitalize() for word in boss_name.split())

    spawn_time = boss_info["spawn_time"]
    kill_time = boss_info.get("kill_time", spawn_time - timedelta(hours=REGULAR_BOSSES[boss_name]["hours"]))
    current_time = get_ph_time()
    respawn_hours = REGULAR_BOSSES[boss_name]["hours"]
    location = boss_info.get("location", REGULAR_BOSSES[boss_name]["location"])

    if current_time > spawn_time:
        await ctx.send(
            f"**{display_name}**\n"
            f"📍 **Location:** {location}\n"
            f"Status: ✅ **ALIVE**\n"
            f"Killed at: {kill_time.strftime('%Y-%m-%d %I:%M %p PHT')}\n"
            f"Respawn timer: {respawn_hours} hours\n"
            f"Use `!kill {boss_name}` after defeat"
        )
    else:
        time_left = spawn_time - current_time
        time_str = format_time_left(time_left)

        await ctx.send(
            f"**{display_name}**\n"
            f"📍 **Location:** {location}\n"
            f"Status: ❌ **DEAD**\n"
            f"Killed at: {kill_time.strftime('%Y-%m-%d %I:%M %p PHT')}\n"
            f"Respawns: {spawn_time.strftime('%Y-%m-%d %I:%M %p PHT')}\n"
            f"Time left: {time_str}\n"
            f"Respawn timer: {respawn_hours} hours"
        )

async def send_fixed_boss_status(ctx, boss_name):
    """Send detailed status for a fixed-time boss"""
    display_name = ' '.join(word.capitalize() for word in boss_name.split())
    boss_info = FIXED_BOSSES[boss_name]
    location = boss_info["location"]

    next_spawn = get_next_spawn_time(boss_name)
    current_time = get_ph_time()

    if next_spawn:
        time_left = next_spawn - current_time

        if time_left.total_seconds() <= 0:
            status_message = (
                f"**{display_name}**\n"
                f"📍 **Location:** {location}\n"
                f"Status: ✅ **ALIVE**\n"
                f"Next spawn: Calculating..."
            )
        else:
            time_str = format_time_left(time_left)
            status_message = (
                f"**{display_name}**\n"
                f"📍 **Location:** {location}\n"
                f"Status: ❌ **DEAD**\n"
                f"Next spawn: {next_spawn.strftime('%Y-%m-%d %I:%M %p PHT')}\n"
                f"Time left: {time_str}\n"
                f"**Spawn schedule:**\n"
            )

            # Add all spawn times
            for spawn_info in boss_info["spawn_times"]:
                status_message += f"• {spawn_info['day'].capitalize()} at {spawn_info['time']}\n"
    else:
        status_message = f"**{display_name}**\n📍 **Location:** {location}\nStatus: ❓ Unable to calculate next spawn"

    await ctx.send(status_message)

@bot.command(name='bosses', help='List all available bosses with locations')
async def list_bosses(ctx):
    message = "**AVAILABLE BOSSES**\n"
    message += "```\n"
    message += "BOSS NAME           TYPE         LOCATION\n"
    message += "───────────────────────────────────────────────────\n"

    for boss_name, boss_info in sorted(ALL_BOSSES.items()):
        display_name = ' '.join(word.capitalize() for word in boss_name.split())
        name_display = display_name.ljust(18)

        # Determine boss type
        if boss_name in FIXED_BOSSES:
            type_display = "FIXED-TIME".ljust(12)
        else:
            type_display = f"{boss_info['hours']}H".ljust(12)

        location_display = boss_info["location"][:25]  # Trim long location names
        message += f"{name_display} {type_display} {location_display}\n"

    message += "```\n"
    message += "**Legend:**\n• H = Hours respawn timer\n• FIXED-TIME = Spawns at specific times"
    await ctx.send(message)

@bot.command(name='schedule', help='Get spawn schedule for a fixed-time boss. Example: !schedule Clemantis')
async def get_schedule(ctx, *, boss_name):
    boss_name_lower = boss_name.lower()

    if boss_name_lower not in FIXED_BOSSES:
        await ctx.send(f"❌ `{boss_name}` is not a fixed-time boss or doesn't exist.\n"
                       f"Use `!bosses` to see all available bosses.")
        return

    boss_info = FIXED_BOSSES[boss_name_lower]
    display_name = ' '.join(word.capitalize() for word in boss_name_lower.split())
    location = boss_info["location"]

    next_spawn = get_next_spawn_time(boss_name_lower)
    current_time = get_ph_time()

    message = (
        f"**{display_name} Schedule**\n"
        f"📍 **Location:** {location}\n"
        f"**Spawn times:**\n"
    )

    for spawn_info in boss_info["spawn_times"]:
        message += f"• {spawn_info['day'].capitalize()} at {spawn_info['time']}\n"

    if next_spawn:
        time_left = next_spawn - current_time
        if time_left.total_seconds() <= 0:
            message += f"\n**Status:** ✅ **ALIVE**\nNext spawn: Calculating..."
        else:
            time_str = format_time_left(time_left)
            message += f"\n**Next spawn:** {next_spawn.strftime('%Y-%m-%d %I:%M %p PHT')}\n**Time left:** {time_str}"

    await ctx.send(message)

@bot.command(name='location', help='Get location of a specific boss. Example: !location Amentis')
async def get_location(ctx, *, boss_name):
    boss_name_lower = boss_name.lower()

    if boss_name_lower not in ALL_BOSSES:
        await ctx.send(f"❌ Unknown boss `{boss_name}`")
        return

    display_name = ' '.join(word.capitalize() for word in boss_name_lower.split())
    location = ALL_BOSSES[boss_name_lower]["location"]

    if boss_name_lower in FIXED_BOSSES:
        respawn_info = "Fixed schedule (use !schedule for details)"
    else:
        respawn_hours = REGULAR_BOSSES[boss_name_lower]["hours"]
        respawn_info = f"{respawn_hours} hours"

    await ctx.send(f"**{display_name}**\n📍 **Location:** {location}\n⏰ **Respawn:** {respawn_info}")

@bot.command(name='time', help='Check current Philippine time')
async def check_time(ctx):
    current_time = get_ph_time()
    await ctx.send(f"⏰ **Current Philippine Time:** {current_time.strftime('%Y-%m-%d %I:%M:%S %p PHT')}")

@tasks.loop(seconds=30.0)
async def check_spawns():
    current_time = get_ph_time()
    notification_time = current_time + timedelta(minutes=10)  # 10 minutes before spawn

    # Get the specific notification channel
    notification_channel = bot.get_channel(NOTIFICATION_CHANNEL_ID)
    if not notification_channel:
        print(f"❌ ERROR: Could not find notification channel with ID {NOTIFICATION_CHANNEL_ID}")
        return

    # Check regular bosses
    for boss_name, boss_info in list(boss_data.items()):
        if boss_info.get("type") != "regular":
            continue

        spawn_time = boss_info["spawn_time"]
        location = boss_info.get("location", REGULAR_BOSSES.get(boss_name, {}).get("location", "Unknown"))

        # Check if spawn is in the next 10 minutes and not notified yet
        if current_time < spawn_time <= notification_time and not boss_info["notified"]:
            # Create pretty display name
            display_name = ' '.join(word.capitalize() for word in boss_name.split())

            time_left = spawn_time - current_time
            minutes = (time_left.seconds % 3600) // 60
            seconds = time_left.seconds % 60

            try:
                await notification_channel.send(
                    f"@everyone 🚨 **{display_name} SPAWN ALERT!** 🚨\n"
                    f"📍 **Location:** {location}\n"
                    f"**Spawning in {minutes} minutes {seconds} seconds!**\n"
                    f"⏰ **Spawn time:** {spawn_time.strftime('%I:%M %p PHT')}"
                )
                print(f"✅ Sent spawn alert for {display_name} to channel {NOTIFICATION_CHANNEL_ID}")

                # Mark as notified
                boss_info["notified"] = True

            except discord.Forbidden:
                print(f"❌ Missing permissions to send message in channel {NOTIFICATION_CHANNEL_ID}")
            except discord.HTTPException as e:
                print(f"❌ Failed to send message: {e}")

    # Check fixed-time bosses
    for boss_name in FIXED_BOSSES:
        next_spawn = get_next_spawn_time(boss_name)
        if not next_spawn:
            continue

        # Check if we need to notify for this boss
        notification_key = f"{boss_name}_notified"
        already_notified = boss_data.get(notification_key, False)

        if current_time < next_spawn <= notification_time and not already_notified:
            # Create pretty display name
            display_name = ' '.join(word.capitalize() for word in boss_name.split())
            location = FIXED_BOSSES[boss_name]["location"]

            time_left = next_spawn - current_time
            minutes = (time_left.seconds % 3600) // 60
            seconds = time_left.seconds % 60

            try:
                await notification_channel.send(
                    f"@everyone 🚨 **{display_name} SPAWN ALERT!** 🚨\n"
                    f"📍 **Location:** {location}\n"
                    f"**Spawning in {minutes} minutes {seconds} seconds!**\n"
                    f"⏰ **Spawn time:** {next_spawn.strftime('%I:%M %p PHT')}\n"
                    f"📅 **Next spawn:** {next_spawn.strftime('%A, %B %d')}"
                )
                print(f"✅ Sent spawn alert for fixed-time boss {display_name} to channel {NOTIFICATION_CHANNEL_ID}")

                # Mark as notified
                boss_data[notification_key] = True

            except discord.Forbidden:
                print(f"❌ Missing permissions to send message in channel {NOTIFICATION_CHANNEL_ID}")
            except discord.HTTPException as e:
                print(f"❌ Failed to send message: {e}")

    # Reset notifications for bosses that have spawned
    for boss_name, boss_info in list(boss_data.items()):
        if boss_info.get("type") == "regular" and boss_info["spawn_time"] < current_time:
            boss_info["notified"] = False

    # Reset notifications for fixed-time bosses that have spawned
    for boss_name in FIXED_BOSSES:
        next_spawn = get_next_spawn_time(boss_name)
        if next_spawn and next_spawn < current_time:
            notification_key = f"{boss_name}_notified"
            boss_data[notification_key] = False

# Install pytz if not already installed
try:
    import pytz
except ImportError:
    import os
    os.system('pip install pytz')
    import pytz

keep_alive()
bot.run(BOT_TOKEN)
