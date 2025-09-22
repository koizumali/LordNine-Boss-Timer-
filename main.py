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
            
            self.client = MongoClient(self.connection_string, serverSelectionTimeoutMS=5000)
            self.client.admin.command('ping')  # Test connection
            self.db = self.client.discord_boss_tracker
            logger.info("✅ Connected to MongoDB successfully")
        except Exception as e:
            logger.error(f"❌ MongoDB connection failed: {e}")
            self.client = None
            self.db = None
    
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
        """Save boss data to MongoDB"""
        if not self.is_connected():
            return False
        
        try:
            # Convert datetime objects to strings for storage
            storage_data = {}
            for boss_name, data in boss_data.items():
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
            return result.acknowledged
        except Exception as e:
            logger.error(f"Error saving boss data: {e}")
            return False
    
    async def load_boss_data(self):
        """Load boss data from MongoDB"""
        if not self.is_connected():
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
                logger.info("✅ Loaded boss data from MongoDB")
                return loaded_data
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
    await mongodb.save_boss_data(boss_data)

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

@bot.event
async def on_disconnect():
    logger.warning("Bot disconnected from Discord")

@bot.event
async def on_resumed():
    logger.info("Bot resumed connection to Discord")

@bot.event
async def on_error(event, *args, **kwargs):
    logger.error(f'Error in event {event}: {args} {kwargs}')

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

# ... (keep your other commands like status, bosses, schedule, location, time, test mostly the same)
# Just add database saving where appropriate

@bot.command(name='cleardata')
async def clear_data(ctx):
    """Clear all boss data (admin command)"""
    # Add permission check here if needed
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

# ===== BACKGROUND TASKS =====
@tasks.loop(minutes=5.0)
async def auto_save():
    """Auto-save boss data to database every 5 minutes"""
    try:
        if boss_data:
            success = await save_boss_data()
            if success:
                logger.info("✅ Auto-saved boss data to database")
            else:
                logger.warning("❌ Failed to auto-save boss data")
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
            if boss_info.get("type") != "regular":
                continue

            spawn_time = boss_info["spawn_time"]
            location = boss_info.get("location", "Unknown")

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

        # Reset notifications
        for boss_name, boss_info in list(boss_data.items()):
            if boss_info.get("type") == "regular" and boss_info["spawn_time"] < current_time:
                boss_info["notified"] = False

        for boss_name in FIXED_BOSSES:
            next_spawn = get_next_spawn_time(boss_name)
            if next_spawn and next_spawn < current_time:
                boss_data[f"{boss_name}_notified"] = False

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
    # Final save before shutdown
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
    asyncio.run(shutdown())import discord
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
            
            self.client = MongoClient(self.connection_string, serverSelectionTimeoutMS=5000)
            self.client.admin.command('ping')  # Test connection
            self.db = self.client.discord_boss_tracker
            logger.info("✅ Connected to MongoDB successfully")
        except Exception as e:
            logger.error(f"❌ MongoDB connection failed: {e}")
            self.client = None
            self.db = None
    
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
        """Save boss data to MongoDB"""
        if not self.is_connected():
            return False
        
        try:
            # Convert datetime objects to strings for storage
            storage_data = {}
            for boss_name, data in boss_data.items():
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
            return result.acknowledged
        except Exception as e:
            logger.error(f"Error saving boss data: {e}")
            return False
    
    async def load_boss_data(self):
        """Load boss data from MongoDB"""
        if not self.is_connected():
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
                logger.info("✅ Loaded boss data from MongoDB")
                return loaded_data
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
    await mongodb.save_boss_data(boss_data)

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

@bot.event
async def on_disconnect():
    logger.warning("Bot disconnected from Discord")

@bot.event
async def on_resumed():
    logger.info("Bot resumed connection to Discord")

@bot.event
async def on_error(event, *args, **kwargs):
    logger.error(f'Error in event {event}: {args} {kwargs}')

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

# ... (keep your other commands like status, bosses, schedule, location, time, test mostly the same)
# Just add database saving where appropriate

@bot.command(name='cleardata')
async def clear_data(ctx):
    """Clear all boss data (admin command)"""
    # Add permission check here if needed
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

# ===== BACKGROUND TASKS =====
@tasks.loop(minutes=5.0)
async def auto_save():
    """Auto-save boss data to database every 5 minutes"""
    try:
        if boss_data:
            success = await save_boss_data()
            if success:
                logger.info("✅ Auto-saved boss data to database")
            else:
                logger.warning("❌ Failed to auto-save boss data")
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
            if boss_info.get("type") != "regular":
                continue

            spawn_time = boss_info["spawn_time"]
            location = boss_info.get("location", "Unknown")

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

        # Reset notifications
        for boss_name, boss_info in list(boss_data.items()):
            if boss_info.get("type") == "regular" and boss_info["spawn_time"] < current_time:
                boss_info["notified"] = False

        for boss_name in FIXED_BOSSES:
            next_spawn = get_next_spawn_time(boss_name)
            if next_spawn and next_spawn < current_time:
                boss_data[f"{boss_name}_notified"] = False

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
    # Final save before shutdown
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
