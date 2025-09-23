import discord
from discord.ext import commands, tasks
from datetime import datetime, timedelta
import pytz
from flask import Flask
from threading import Thread
import os
import warnings
import asyncio
import pymongo
from pymongo import MongoClient
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Suppress the Flask development server warning
warnings.filterwarnings("ignore", message="This is a development server.")

# ===== MONGODB SETUP =====
class MongoDBHandler:
    def __init__(self, connection_string=None):
        self.connection_string = connection_string or os.getenv("MONGODB_URI")
        self.client = None
        self.db = None
        self.connect()
    
    def connect(self):
        """Connect to MongoDB"""
        try:
            if not self.connection_string:
                logger.warning("No MongoDB connection string found. Using in-memory storage only.")
                return
            
            self.client = MongoClient(
                self.connection_string, 
                serverSelectionTimeoutMS=5000,
                connectTimeoutMS=30000,
                socketTimeoutMS=45000
            )
            self.client.admin.command('ping')  # Test connection
            self.db = self.client.discord_boss_tracker
            logger.info("✅ Connected to MongoDB successfully")
        except Exception as e:
            logger.error(f"❌ MongoDB connection failed: {e}")
            self.client = None
            self.db = None
    
    def reconnect(self):
        """Attempt to reconnect to MongoDB"""
        logger.info("Attempting to reconnect to MongoDB...")
        try:
            if self.client:
                self.client.close()
            self.connect()
            if self.is_connected():
                logger.info("✅ MongoDB reconnection successful")
                return True
            return False
        except Exception as e:
            logger.error(f"❌ MongoDB reconnection failed: {e}")
            return False
    
    def is_connected(self):
        """Check if MongoDB is connected"""
        try:
            if self.client:
                self.client.admin.command('ping')
                return True
            return False
        except:
            return False
    
    async def save_boss_data(self, boss_data):
        """Save boss data to MongoDB with reconnection attempt"""
        if not self.connection_string:
            logger.warning("No MongoDB connection string - skipping save")
            return False
        
        # Try to reconnect if not connected
        if not self.is_connected():
            logger.warning("MongoDB disconnected. Attempting to reconnect...")
            if not self.reconnect():
                logger.error("Failed to reconnect to MongoDB - cannot save data")
                return False
        
        try:
            # Convert datetime objects to strings for storage
            storage_data = {}
            for boss_name, data in boss_data.items():
                # Skip notification flags (they're stored as booleans, not dicts)
                if not isinstance(data, dict):
                    continue
                    
                storage_data[boss_name] = {}
                for key, value in data.items():
                    if isinstance(value, datetime):
                        storage_data[boss_name][key] = value.isoformat()
                    else:
                        storage_data[boss_name][key] = value
            
            result = self.db.boss_data.replace_one(
                {'_id': 'current_bosses'}, 
                {'_id': 'current_bosses', 'data': storage_data}, 
                upsert=True
            )
            logger.info("✅ Boss data saved to MongoDB successfully")
            return result.acknowledged
        except Exception as e:
            logger.error(f"Error saving boss data: {e}")
            # Mark as disconnected for next attempt
            self.client = None
            self.db = None
            return False
    
    async def load_boss_data(self):
        """Load boss data from MongoDB"""
        if not self.is_connected():
            if self.connection_string:
                logger.warning("MongoDB not connected - attempting to reconnect for load")
                self.reconnect()
            return {}
        
        try:
            document = self.db.boss_data.find_one({'_id': 'current_bosses'})
            if document and 'data' in document:
                # Convert string dates back to datetime objects
                loaded_data = {}
                for boss_name, data in document['data'].items():
                    loaded_data[boss_name] = {}
                    for key, value in data.items():
                        if key in ['spawn_time', 'kill_time'] and isinstance(value, str):
                            loaded_data[boss_name][key] = datetime.fromisoformat(value)
                        else:
                            loaded_data[boss_name][key] = value
                logger.info(f"✅ Loaded {len(loaded_data)} bosses from MongoDB")
                return loaded_data
            logger.info("No existing boss data found in MongoDB")
            return {}
        except Exception as e:
            logger.error(f"Error loading boss data: {e}")
            return {}

# Initialize MongoDB handler
mongodb = MongoDBHandler()

# ===== KEEP ALIVE SERVER =====
app = Flask(__name__)

@app.route('/')
def home():
    return "Bot is alive and running! 🚀"

@app.route('/health')
def health_check():
    """Health check endpoint for monitoring"""
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}

def run_flask():
    """Run Flask in a separate thread"""
    app.run(host='0.0.0.0', port=8080, debug=False, use_reloader=False)

def keep_alive():
    """Start Flask in a background thread"""
    t = Thread(target=run_flask)
    t.daemon = True
    t.start()

# ===== BOT CONFIGURATION =====
BOT_TOKEN = os.getenv("DISCORD_TOKEN")
if not BOT_TOKEN:
    raise ValueError("No DISCORD_TOKEN found in environment variables")

NOTIFICATION_CHANNEL_ID = 1416149291839258696  # Your channel ID

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='!', intents=intents)

# Set Philippine Timezone
PH_TZ = pytz.timezone('Asia/Manila')

# ===== BOSS DATA =====
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

ALL_BOSSES = {**REGULAR_BOSSES, **FIXED_BOSSES}
boss_data = {}

# ===== UTILITY FUNCTIONS =====
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

        # Try different date formats
        formats = [
            "%Y-%m-%d %H:%M",
            "%m/%d/%Y %H:%M", 
            "%m/%d %H:%M",
            "%H:%M:%S",
            "%H:%M"
        ]
        
        for fmt in formats:
            try:
                if fmt in ["%H:%M:%S", "%H:%M"]:
                    time_part = datetime.strptime(time_str, fmt).time()
                    dt = datetime.combine(current_time.date(), time_part)
                    localized_dt = PH_TZ.localize(dt)
                    if localized_dt > current_time and (current_time - localized_dt) > timedelta(hours=12):
                        localized_dt -= timedelta(days=1)
                    return localized_dt
                else:
                    dt = datetime.strptime(time_str, fmt)
                    if dt.year == 1900:  # If no year provided
                        dt = dt.replace(year=current_time.year)
                    return PH_TZ.localize(dt)
            except ValueError:
                continue

        raise ValueError("Invalid time format")
    except Exception as e:
        raise ValueError(f"Invalid time format: {str(e)}")

def get_next_spawn_time(boss_name):
    """Calculate the next spawn time for fixed-time bosses"""
    if boss_name not in FIXED_BOSSES:
        return None

    boss_info = FIXED_BOSSES[boss_name]
    current_time = get_ph_time()
    current_weekday = current_time.strftime("%A").lower()

    days_of_week = ["sunday", "monday", "tuesday", "wednesday", "thursday", "friday", "saturday"]
    spawn_times = []
    
    for spawn_info in boss_info["spawn_times"]:
        spawn_day = spawn_info["day"]
        spawn_time_str = spawn_info["time"]
        spawn_hour, spawn_minute = map(int, spawn_time_str.split(":"))

        days_ahead = (days_of_week.index(spawn_day) - days_of_week.index(current_weekday))
        if days_ahead < 0 or (days_ahead == 0 and spawn_time_str <= current_time.strftime("%H:%M")):
            days_ahead += 7

        spawn_date = current_time + timedelta(days=days_ahead)
        spawn_date = spawn_date.replace(hour=spawn_hour, minute=spawn_minute, second=0, microsecond=0)
        spawn_times.append(spawn_date)

    return min(spawn_times) if spawn_times else None

async def save_boss_data():
    """Save boss data to MongoDB"""
    return await mongodb.save_boss_data(boss_data)

async def send_boss_status(ctx, boss_name_lower, boss_info):
    """Send status for a single boss"""
    current_time = get_ph_time()
    display_name = ' '.join(word.capitalize() for word in boss_name_lower.split())
    location = boss_info.get("location", "Unknown")
    
    if boss_info["spawn_time"] < current_time:
        status = "✅ ALIVE"
        time_left = "Now"
    else:
        status = "❌ DEAD"
        time_left = format_time_left(boss_info["spawn_time"] - current_time)
    
    kill_time_str = boss_info["kill_time"].strftime("%Y-%m-%d %I:%M %p PHT")
    spawn_time_str = boss_info["spawn_time"].strftime("%Y-%m-%d %I:%M %p PHT")
    
    await ctx.send(
        f"**{display_name}**\n"
        f"📍 **Location:** {location}\n"
        f"**Status:** {status}\n"
        f"⏰ **Killed at:** {kill_time_str}\n"
        f"🔄 **Respawn at:** {spawn_time_str}\n"
        f"⏳ **Time left:** {time_left}"
    )

async def send_fixed_boss_status(ctx, boss_name_lower):
    """Send status for a fixed-time boss"""
    display_name = ' '.join(word.capitalize() for word in boss_name_lower.split())
    location = FIXED_BOSSES[boss_name_lower]["location"]
    next_spawn = get_next_spawn_time(boss_name_lower)
    current_time = get_ph_time()
    
    message = f"**{display_name}**\n📍 **Location:** {location}\n"
    
    if next_spawn:
        if next_spawn <= current_time:
            message += "**Status:** ✅ **ALIVE**\n"
        else:
            time_left = format_time_left(next_spawn - current_time)
            message += f"**Status:** ❌ **DEAD**\n"
            message += f"⏰ **Next spawn:** {next_spawn.strftime('%Y-%m-%d %I:%M %p PHT')}\n"
            message += f"⏳ **Time left:** {time_left}\n"
        
        message += "\n**Schedule:**\n"
        for spawn_info in FIXED_BOSSES[boss_name_lower]["spawn_times"]:
            message += f"• {spawn_info['day'].capitalize()} at {spawn_info['time']}\n"
    else:
        message += "**Status:** ❓ **UNKNOWN**\n"
    
    await ctx.send(message)

# ===== BOT EVENTS AND COMMANDS =====
@bot.event
async def on_ready():
    logger.info(f'{bot.user} is online! Tracking {len(ALL_BOSSES)} bosses.')
    
    # Load boss data from MongoDB
    global boss_data
    loaded_data = await mongodb.load_boss_data()
    boss_data.update(loaded_data)
    logger.info(f'Loaded {len(loaded_data)} bosses from database')
    
    # Test notification channel
    channel = bot.get_channel(NOTIFICATION_CHANNEL_ID)
    if channel:
        logger.info(f'✅ Found notification channel: {channel.name}')
        try:
            await channel.send("🤖 Boss tracker bot is now online and ready! Data loaded from database.")
        except Exception as e:
            logger.error(f"Error sending ready message: {e}")
    else:
        logger.error(f"❌ Could not find notification channel with ID {NOTIFICATION_CHANNEL_ID}")
    
    # Start background tasks
    if not check_spawns.is_running():
        check_spawns.start()
    
    if not auto_save.is_running():
        auto_save.start()

@bot.command(name='kill')
async def report_kill(ctx, *, boss_name):
    boss_name_lower = boss_name.lower()

    if boss_name_lower not in ALL_BOSSES:
        valid_bosses = ", ".join([f"`{b}`" for b in ALL_BOSSES.keys()])
        await ctx.send(f"❌ Unknown boss `{boss_name}`.\n**Valid bosses:** {valid_bosses}")
        return

    if boss_name_lower in FIXED_BOSSES:
        await ctx.send(f"ℹ️ **{boss_name.capitalize()}** is a fixed-time boss.\nUse `!schedule {boss_name}` for spawn times.")
        return

    respawn_hours = REGULAR_BOSSES[boss_name_lower]["hours"]
    kill_time = get_ph_time()
    spawn_time = kill_time + timedelta(hours=respawn_hours)
    location = REGULAR_BOSSES[boss_name_lower]["location"]

    boss_data[boss_name_lower] = {
        "spawn_time": spawn_time,
        "notified": False,
        "kill_time": kill_time,
        "location": location,
        "type": "regular"
    }

    # Save to database
    await save_boss_data()

    display_name = ' '.join(word.capitalize() for word in boss_name_lower.split())
    kill_str = kill_time.strftime("%I:%M %p PHT")
    spawn_str = spawn_time.strftime("%I:%M %p PHT")
    
    await ctx.send(
        f"✅ **{display_name}** defeated at `{kill_str}`!\n"
        f"📍 **Location:** {location}\n"
        f"⏰ Respawns at `{spawn_str}`\n"
        f"⏳ In {respawn_hours} hours"
    )

@bot.command(name='killtime')
async def report_kill_manual(ctx, boss_name, *, time_input):
    boss_name_lower = boss_name.lower()

    if boss_name_lower not in ALL_BOSSES:
        valid_bosses = ", ".join([f"`{b}`" for b in ALL_BOSSES.keys()])
        await ctx.send(f"❌ Unknown boss `{boss_name}`.\n**Valid bosses:** {valid_bosses}")
        return

    if boss_name_lower in FIXED_BOSSES:
        await ctx.send(f"ℹ️ **{boss_name.capitalize()}** is a fixed-time boss.\nUse `!schedule {boss_name}` for spawn times.")
        return

    try:
        kill_time = parse_manual_time(time_input)
        respawn_hours = REGULAR_BOSSES[boss_name_lower]["hours"]
        spawn_time = kill_time + timedelta(hours=respawn_hours)
        location = REGULAR_BOSSES[boss_name_lower]["location"]

        boss_data[boss_name_lower] = {
            "spawn_time": spawn_time,
            "notified": False,
            "kill_time": kill_time,
            "location": location,
            "type": "regular"
        }

        # Save to database
        await save_boss_data()

        display_name = ' '.join(word.capitalize() for word in boss_name_lower.split())
        kill_str = kill_time.strftime("%Y-%m-%d %I:%M %p PHT")
        spawn_str = spawn_time.strftime("%Y-%m-%d %I:%M %p PHT")
        
        await ctx.send(
            f"✅ **{display_name}** defeated at `{kill_str}`!\n"
            f"📍 **Location:** {location}\n"
            f"⏰ Respawns at `{spawn_str}`\n"
            f"⏳ In {respawn_hours} hours"
        )

    except ValueError as e:
        await ctx.send(f"❌ {e}\n**Valid formats:**\n• `!killtime BossName 14:30`\n• `!killtime BossName 2024-01-15 14:30`")

@bot.command(name='status')
async def check_status(ctx, *, specific_boss=None):
    if specific_boss:
        # Show status for one specific boss
        boss_name_lower = specific_boss.lower()
        if boss_name_lower not in ALL_BOSSES:
            await ctx.send(f"❌ Unknown boss `{specific_boss}`")
            return

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
        # Show status for all bosses - FIXED: Split into multiple messages if too long
        current_time = get_ph_time()
        boss_statuses = []

        for boss_name in ALL_BOSSES.keys():
            if boss_name in FIXED_BOSSES:
                next_spawn = get_next_spawn_time(boss_name)
                if next_spawn:
                    time_left = next_spawn - current_time
                    if time_left.total_seconds() <= 0:
                        status = "✅ ALIVE"
                        time_left_seconds = 0
                        spawn_time_str = "Now"
                    else:
                        status = "❌ DEAD"
                        time_left_seconds = time_left.total_seconds()
                        spawn_time_str = next_spawn.strftime("%I:%M %p/%d %b")
                else:
                    status = "❓ UNKNOWN"
                    time_left_seconds = float('inf')
                    spawn_time_str = "Unknown"
            else:
                boss_info = boss_data.get(boss_name)
                if boss_info:
                    spawn_time = boss_info["spawn_time"]
                    if current_time > spawn_time:
                        status = "✅ ALIVE"
                        time_left_seconds = 0
                        spawn_time_str = "Now"
                    else:
                        status = "❌ DEAD"
                        time_left_seconds = (spawn_time - current_time).total_seconds()
                        spawn_time_str = spawn_time.strftime("%I:%M %p/%d %b")
                else:
                    status = "❓ NOT KILLED"
                    time_left_seconds = float('inf')
                    spawn_time_str = "Unknown"

            display_name = ' '.join(word.capitalize() for word in boss_name.split())
            boss_statuses.append({
                'name': display_name,
                'status': status,
                'time_left_seconds': time_left_seconds,
                'boss_name': boss_name,
                'spawn_time_str': spawn_time_str
            })

        def sort_key(boss):
            if boss['status'] == "✅ ALIVE":
                return (0, boss['time_left_seconds'])
            elif boss['status'] == "❌ DEAD":
                return (1, boss['time_left_seconds'])
            else:
                return (2, boss['time_left_seconds'])

        boss_statuses.sort(key=sort_key)

        # Split into multiple messages if too long
        messages = []
        current_message = "**BOSS STATUS** (Sorted by spawn time)\n```\n"
        current_message += "BOSS NAME           STATUS        TIME LEFT     SPAWN TIME\n"
        current_message += "──────────────────────────────────────────────────────────\n"

        dead_bosses = [boss for boss in boss_statuses if boss['status'] == "❌ DEAD"]
        
        for i, boss in enumerate(boss_statuses):
            if boss['status'] == "✅ ALIVE":
                time_str = "-".ljust(12)
                spawn_str = "Now".ljust(14)
            elif boss['status'] == "❌ DEAD":
                time_str = format_time_left(timedelta(seconds=boss['time_left_seconds'])).ljust(12)
                spawn_str = boss['spawn_time_str'].ljust(14)
            else:
                time_str = "-".ljust(12)
                spawn_str = "Unknown".ljust(14)

            name_display = boss['name'].ljust(18)
            
            line_content = ""
            if boss['status'] == "❌ DEAD" and dead_bosses.index(boss) < 5:
                line_content = f"🔥 {name_display} {boss['status'].ljust(12)} {time_str} {spawn_str}\n"
            else:
                line_content = f"   {name_display} {boss['status'].ljust(12)} {time_str} {spawn_str}\n"

            # Check if adding this line would exceed Discord's 2000 character limit
            if len(current_message + line_content + "```") > 1900:
                current_message += "```"
                messages.append(current_message)
                current_message = "```\n"
                current_message += "BOSS NAME           STATUS        TIME LEFT     SPAWN TIME\n"
                current_message += "──────────────────────────────────────────────────────────\n"
            
            current_message += line_content

        current_message += "```"
        messages.append(current_message)
        
        # Add format explanation to the last message
        if messages:
            messages[-1] += f"\n**Format:** Time: `HH:MM AM/PM` Date: `DD MMM` (e.g., 02:30 PM/15 Jan)"
        
        # Send all messages
        for message in messages:
            if message.strip():  # Only send non-empty messages
                await ctx.send(message)

@bot.command(name='bosses')
async def list_bosses(ctx):
    # Split the bosses list into multiple messages if too long
    regular_bosses_msg = "**REGULAR BOSSES** (Respawn timer)\n```\n"
    regular_bosses_msg += "BOSS NAME           HOURS  LOCATION\n"
    regular_bosses_msg += "─────────────────────────────────────────\n"
    
    fixed_bosses_msg = "**FIXED-TIME BOSSES** (Scheduled spawns)\n```\n"
    fixed_bosses_msg += "BOSS NAME           LOCATION\n"
    fixed_bosses_msg += "─────────────────────────────────────\n"
    
    for boss_name, boss_info in sorted(ALL_BOSSES.items()):
        display_name = ' '.join(word.capitalize() for word in boss_name.split())
        name_display = display_name.ljust(18)
        location_display = boss_info["location"][:25]
        
        if boss_name in FIXED_BOSSES:
            fixed_bosses_msg += f"{name_display} {location_display}\n"
        else:
            hours_display = f"{boss_info['hours']}H".ljust(6)
            regular_bosses_msg += f"{name_display} {hours_display} {location_display}\n"
    
    regular_bosses_msg += "```"
    fixed_bosses_msg += "```"
    
    await ctx.send(regular_bosses_msg)
    await ctx.send(fixed_bosses_msg)

@bot.command(name='schedule')
async def get_schedule(ctx, *, boss_name):
    boss_name_lower = boss_name.lower()

    if boss_name_lower not in FIXED_BOSSES:
        await ctx.send(f"❌ `{boss_name}` is not a fixed-time boss or doesn't exist.\nUse `!bosses` to see all available bosses.")
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

@bot.command(name='location')
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

@bot.command(name='time')
async def check_time(ctx):
    current_time = get_ph_time()
    await ctx.send(f"⏰ **Current Philippine Time:** {current_time.strftime('%Y-%m-%d %I:%M:%S %p PHT')}")

@bot.command(name='test')
async def test_command(ctx):
    """Test if the bot can send messages"""
    try:
        await ctx.send("✅ Bot is working and can send messages!")
        
        channel = bot.get_channel(NOTIFICATION_CHANNEL_ID)
        if channel:
            await channel.send("✅ Notification channel test successful!")
        else:
            await ctx.send(f"❌ Could not find notification channel with ID {NOTIFICATION_CHANNEL_ID}")
            
    except Exception as e:
        await ctx.send(f"❌ Error: {e}")

@bot.command(name='cleardata')
async def clear_data(ctx):
    """Clear all boss data (admin command)"""
    boss_data.clear()
    if mongodb.is_connected():
        await mongodb.save_boss_data({})
    await ctx.send("✅ All boss data cleared!")

@bot.command(name='dbstatus')
async def db_status(ctx):
    """Check database connection status"""
    status = "✅ Connected" if mongodb.is_connected() else "❌ Disconnected"
    boss_count = len(boss_data)
    await ctx.send(f"**Database Status:** {status}\n**Bosses in memory:** {boss_count}")

@bot.command(name='forcesave')
async def force_save(ctx):
    """Force save boss data to database"""
    try:
        if not boss_data:
            await ctx.send("❌ No boss data to save")
            return
            
        success = await mongodb.save_boss_data(boss_data)
        if success:
            await ctx.send("✅ Boss data saved successfully to database!")
        else:
            await ctx.send("❌ Failed to save boss data. MongoDB may be disconnected.")
    except Exception as e:
        await ctx.send(f"❌ Error saving data: {e}")

@bot.command(name='dbinfo')
async def db_info(ctx):
    """Show detailed database information"""
    status = "✅ Connected" if mongodb.is_connected() else "❌ Disconnected"
    boss_count = len(boss_data)
    
    message = f"**Database Information:**\n"
    message += f"• **Status:** {status}\n"
    message += f"• **Bosses in memory:** {boss_count}\n"
    message += f"• **MongoDB Configured:** {'Yes' if mongodb.connection_string else 'No'}\n"
    
    await ctx.send(message)

@bot.command(name='debugdb')
async def debug_db(ctx):
    """Debug MongoDB connection"""
    has_uri = bool(mongodb.connection_string)
    is_connected = mongodb.is_connected()
    
    message = f"**MongoDB Debug:**\n"
    message += f"• URI Configured: {'✅ Yes' if has_uri else '❌ No'}\n"
    message += f"• Connection Status: {'✅ Connected' if is_connected else '❌ Disconnected'}\n"
    
    if has_uri:
        # Show first few characters of URI (don't show full URI for security)
        message += f"• URI Starts with: {mongodb.connection_string[:20]}...\n"
    else:
        message += f"• **ERROR:** No MONGODB_URI found in environment variables!\n"
    
    await ctx.send(message)

@bot.command(name='debugdata')
async def debug_data(ctx):
    """Debug boss data structure"""
    if not boss_data:
        await ctx.send("No boss data in memory")
        return
        
    message = "**Boss Data Structure:**\n"
    for boss_name, data in boss_data.items():
        message += f"\n**{boss_name}**: {type(data)}\n"
        if isinstance(data, dict):
            for key, value in data.items():
                message += f"  - {key}: {type(value)}"
                if isinstance(value, datetime):
                    message += f" ({value.strftime('%Y-%m-%d %H:%M')})"
                message += "\n"
        else:
            message += f"  Value: {data}\n"
    
    # Split long messages if needed
    if len(message) > 1900:
        parts = [message[i:i+1900] for i in range(0, len(message), 1900)]
        for part in parts:
            await ctx.send(f"```{part}```")
    else:
        await ctx.send(f"```{message}```")

# ===== BACKGROUND TASKS =====
@tasks.loop(minutes=5.0)
async def auto_save():
    """Auto-save boss data to database every 5 minutes"""
    try:
        if boss_data:
            success = await mongodb.save_boss_data(boss_data)
            if success:
                logger.info("✅ Auto-saved boss data to database")
            else:
                logger.warning("❌ Failed to auto-save boss data - will retry next cycle")
        else:
            logger.info("No boss data to save")
    except Exception as e:
        logger.error(f"Error in auto_save: {e}")

@tasks.loop(seconds=30.0)
async def check_spawns():
    """Check for boss spawns and send notifications"""
    try:
        current_time = get_ph_time()
        notification_time = current_time + timedelta(minutes=10)

        channel = bot.get_channel(NOTIFICATION_CHANNEL_ID)
        if not channel:
            return

        # Check regular bosses
        for boss_name, boss_info in list(boss_data.items()):
            if boss_name.endswith('_notified'):
                continue
                
            if not isinstance(boss_info, dict):
                logger.warning(f"Skipping invalid boss data for {boss_name}: {type(boss_info)}")
                continue
                
            if boss_info.get("type") != "regular":
                continue

            if "spawn_time" not in boss_info or "notified" not in boss_info:
                logger.warning(f"Skipping boss {boss_name} with missing data")
                continue

            spawn_time = boss_info["spawn_time"]
            location = boss_info.get("location", "Unknown")

            if not isinstance(spawn_time, datetime):
                logger.warning(f"Invalid spawn_time for {boss_name}: {type(spawn_time)}")
                continue

            if current_time < spawn_time <= notification_time and not boss_info["notified"]:
                display_name = ' '.join(word.capitalize() for word in boss_name.split())
                time_left = spawn_time - current_time
                minutes = max(0, int(time_left.total_seconds() // 60))

                try:
                    await channel.send(
                        f"@everyone 🚨 **{display_name} SPAWN ALERT!** 🚨\n"
                        f"📍 **Location:** {location}\n"
                        f"**Spawning in {minutes} minutes!**\n"
                        f"⏰ **Spawn time:** {spawn_time.strftime('%I:%M %p PHT')}"
                    )
                    boss_info["notified"] = True
                    await save_boss_data()
                except Exception as e:
                    logger.error(f"Error sending spawn alert: {e}")

        # Check fixed-time bosses
        for boss_name in FIXED_BOSSES:
            try:
                next_spawn = get_next_spawn_time(boss_name)
                if not next_spawn:
                    continue

                notification_key = f"{boss_name}_notified"
                already_notified = boss_data.get(notification_key, False)

                if current_time < next_spawn <= notification_time and not already_notified:
                    display_name = ' '.join(word.capitalize() for word in boss_name.split())
                    location = FIXED_BOSSES[boss_name]["location"]
                    time_left = next_spawn - current_time
                    minutes = max(0, int(time_left.total_seconds() // 60))

                    try:
                        await channel.send(
                            f"@everyone 🚨 **{display_name} SPAWN ALERT!** 🚨\n"
                            f"📍 **Location:** {location}\n"
                            f"**Spawning in {minutes} minutes!**\n"
                            f"⏰ **Spawn time:** {next_spawn.strftime('%I:%M %p PHT')}"
                        )
                        boss_data[notification_key] = True
                        await save_boss_data()
                    except Exception as e:
                        logger.error(f"Error sending fixed boss alert: {e}")
            except Exception as e:
                logger.error(f"Error processing fixed boss {boss_name}: {e}")

        # Reset notifications
        for boss_name, boss_info in list(boss_data.items()):
            if boss_name.endswith('_notified'):
                continue
                
            if not isinstance(boss_info, dict):
                continue
                
            if boss_info.get("type") == "regular" and "spawn_time" in boss_info:
                spawn_time = boss_info["spawn_time"]
                if isinstance(spawn_time, datetime) and spawn_time < current_time:
                    boss_info["notified"] = False

        for boss_name in FIXED_BOSSES:
            try:
                next_spawn = get_next_spawn_time(boss_name)
                if next_spawn and next_spawn < current_time:
                    boss_data[f"{boss_name}_notified"] = False
            except Exception as e:
                logger.error(f"Error resetting notification for {boss_name}: {e}")

    except Exception as e:
        logger.error(f"Error in check_spawns: {e}")

@check_spawns.before_loop
@auto_save.before_loop
async def before_tasks():
    await bot.wait_until_ready()

# ===== SHUTDOWN HANDLER =====
async def shutdown():
    """Clean shutdown procedure"""
    logger.info("Shutting down bot...")
    check_spawns.stop()
    auto_save.stop()
    if boss_data:
        await save_boss_data()
    if mongodb.client:
        mongodb.client.close()

# Start the keep-alive server
keep_alive()

# Run the bot with error handling
try:
    bot.run(BOT_TOKEN)
except KeyboardInterrupt:
    asyncio.run(shutdown())
except Exception as e:
    logger.error(f"Bot crashed: {e}")
    asyncio.run(shutdown())
