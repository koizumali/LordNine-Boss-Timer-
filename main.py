import discord
from discord.ext import commands, tasks
from datetime import datetime, timedelta
import pytz
from flask import Flask
from threading import Thread
import os
import warnings
from discord.ui import Button, View, Select

# Suppress the Flask development server warning
warnings.filterwarnings("ignore", message="This is a development server.")

# ===== KEEP ALIVE SERVER =====
app = Flask(__name__)

@app.route('/')
def home():
    return "Bot is alive and running! 🚀"

def run_flask():
    """Run Flask in a separate thread"""
    app.run(host='0.0.0.0', port=8080, debug=False, use_reloader=False)

def keep_alive():
    """Start Flask in a background thread"""
    t = Thread(target=run_flask)
    t.daemon = True
    t.start()

# PASTE YOUR BOT TOKEN HERE
BOT_TOKEN = os.getenv("DISCORD_TOKEN") or "YOUR_BOT_TOKEN_HERE"

# SPECIFIC CHANNEL FOR BOSS NOTIFICATIONS
NOTIFICATION_CHANNEL_ID = 1416149291839258696

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

# ===== UI COMPONENTS =====
class BossSelectView(View):
    def __init__(self, action_type):
        super().__init__(timeout=60)
        self.action_type = action_type
        self.selected_boss = None
        
        # Create boss selection dropdown
        options = []
        for boss_name in sorted(ALL_BOSSES.keys()):
            display_name = ' '.join(word.capitalize() for word in boss_name.split())
            options.append(discord.SelectOption(label=display_name, value=boss_name))
        
        self.select = Select(placeholder="Choose a boss...", options=options)
        self.select.callback = self.boss_selected
        self.add_item(self.select)

    async def boss_selected(self, interaction):
        self.selected_boss = self.select.values[0]
        await interaction.response.defer()
        
        if self.action_type == "kill":
            await self.handle_kill(interaction)
        elif self.action_type == "killtime":
            await self.handle_killtime(interaction)
        elif self.action_type == "status":
            await self.handle_status(interaction)
        elif self.action_type == "schedule":
            await self.handle_schedule(interaction)
        elif self.action_type == "location":
            await self.handle_location(interaction)

    async def handle_kill(self, interaction):
        boss_name_lower = self.selected_boss.lower()
        
        if boss_name_lower in FIXED_BOSSES:
            await interaction.followup.send(
                f"ℹ️ **{self.selected_boss.capitalize()}** is a fixed-time boss and doesn't use the kill command.\n"
                f"Use `!schedule {self.selected_boss}` to see its spawn times."
            )
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

        display_name = ' '.join(word.capitalize() for word in boss_name_lower.split())
        kill_str = kill_time.strftime("%I:%M %p PHT")
        spawn_str = spawn_time.strftime("%I:%M %p PHT")
        
        await interaction.followup.send(
            f"✅ **{display_name}** defeated at `{kill_str}`!\n"
            f"📍 **Location:** {location}\n"
            f"⏰ Respawns at `{spawn_str}`\n"
            f"⏳ In {respawn_hours} hours"
        )

    async def handle_killtime(self, interaction):
        boss_name_lower = self.selected_boss.lower()
        
        if boss_name_lower in FIXED_BOSSES:
            await interaction.followup.send(
                f"ℹ️ **{self.selected_boss.capitalize()}** is a fixed-time boss and doesn't use the kill command.\n"
                f"Use `!schedule {self.selected_boss}` to see its spawn times."
            )
            return

        # Create time input modal
        modal = TimeInputModal(boss_name_lower)
        await interaction.response.send_modal(modal)

    async def handle_status(self, interaction):
        boss_name_lower = self.selected_boss.lower()
        
        if boss_name_lower in FIXED_BOSSES:
            await send_fixed_boss_status(interaction, boss_name_lower)
        else:
            boss_info = boss_data.get(boss_name_lower)
            if not boss_info:
                display_name = ' '.join(word.capitalize() for word in boss_name_lower.split())
                location = REGULAR_BOSSES[boss_name_lower]["location"]
                await interaction.followup.send(f"**{display_name}**\n📍 **Location:** {location}\nStatus: ❓ Not killed yet")
            else:
                await send_boss_status(interaction, boss_name_lower, boss_info)

    async def handle_schedule(self, interaction):
        boss_name_lower = self.selected_boss.lower()
        
        if boss_name_lower not in FIXED_BOSSES:
            await interaction.followup.send(f"❌ `{self.selected_boss}` is not a fixed-time boss.")
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

        await interaction.followup.send(message)

    async def handle_location(self, interaction):
        boss_name_lower = self.selected_boss.lower()
        display_name = ' '.join(word.capitalize() for word in boss_name_lower.split())
        location = ALL_BOSSES[boss_name_lower]["location"]

        if boss_name_lower in FIXED_BOSSES:
            respawn_info = "Fixed schedule"
        else:
            respawn_hours = REGULAR_BOSSES[boss_name_lower]["hours"]
            respawn_info = f"{respawn_hours} hours"

        await interaction.followup.send(f"**{display_name}**\n📍 **Location:** {location}\n⏰ **Respawn:** {respawn_info}")

class TimeInputModal(discord.ui.Modal):
    def __init__(self, boss_name):
        super().__init__(title=f"Enter Kill Time for {boss_name.capitalize()}")
        self.boss_name = boss_name
        
        self.time_input = discord.ui.TextInput(
            label="Kill Time (HH:MM or YYYY-MM-DD HH:MM)",
            placeholder="Example: 14:30 or 2024-01-15 14:30",
            required=True
        )
        self.add_item(self.time_input)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            kill_time = parse_manual_time(self.time_input.value)
            respawn_hours = REGULAR_BOSSES[self.boss_name]["hours"]
            spawn_time = kill_time + timedelta(hours=respawn_hours)
            location = REGULAR_BOSSES[self.boss_name]["location"]

            boss_data[self.boss_name] = {
                "spawn_time": spawn_time,
                "notified": False,
                "kill_time": kill_time,
                "location": location,
                "type": "regular"
            }

            display_name = ' '.join(word.capitalize() for word in self.boss_name.split())
            kill_str = kill_time.strftime("%Y-%m-%d %I:%M %p PHT")
            spawn_str = spawn_time.strftime("%Y-%m-%d %I:%M %p PHT")
            
            await interaction.response.send_message(
                f"✅ **{display_name}** defeated at `{kill_str}`!\n"
                f"📍 **Location:** {location}\n"
                f"⏰ Respawns at `{spawn_str}`\n"
                f"⏳ In {respawn_hours} hours"
            )
            
        except ValueError as e:
            await interaction.response.send_message(
                f"❌ {e}\n**Valid formats:**\n"
                f"• `HH:MM` (e.g., 14:30)\n"
                f"• `YYYY-MM-DD HH:MM` (e.g., 2024-01-15 14:30)"
            )

class MainMenuView(View):
    def __init__(self):
        super().__init__(timeout=60)
        
    @discord.ui.button(label="🚀 Quick Kill", style=discord.ButtonStyle.primary, emoji="⚔️")
    async def quick_kill(self, interaction: discord.Interaction, button: discord.ui.Button):
        view = BossSelectView("kill")
        await interaction.response.send_message("Select a boss to report kill:", view=view, ephemeral=True)

    @discord.ui.button(label="⏰ Kill with Time", style=discord.ButtonStyle.secondary, emoji="⏰")
    async def kill_with_time(self, interaction: discord.Interaction, button: discord.ui.Button):
        view = BossSelectView("killtime")
        await interaction.response.send_message("Select a boss to report kill with time:", view=view, ephemeral=True)

    @discord.ui.button(label="📊 Check Status", style=discord.ButtonStyle.success, emoji="📊")
    async def check_status(self, interaction: discord.Interaction, button: discord.ui.Button):
        view = BossSelectView("status")
        await interaction.response.send_message("Select a boss to check status:", view=view, ephemeral=True)

    @discord.ui.button(label="📅 View Schedule", style=discord.ButtonStyle.success, emoji="📅")
    async def view_schedule(self, interaction: discord.Interaction, button: discord.ui.Button):
        view = BossSelectView("schedule")
        await interaction.response.send_message("Select a fixed-time boss to view schedule:", view=view, ephemeral=True)

    @discord.ui.button(label="📍 Get Location", style=discord.ButtonStyle.secondary, emoji="📍")
    async def get_location(self, interaction: discord.Interaction, button: discord.ui.Button):
        view = BossSelectView("location")
        await interaction.response.send_message("Select a boss to get location:", view=view, ephemeral=True)

    @discord.ui.button(label="🌐 All Bosses", style=discord.ButtonStyle.primary, emoji="🌐")
    async def all_bosses(self, interaction: discord.Interaction, button: discord.ui.Button):
        await list_bosses(interaction)

    @discord.ui.button(label="⏰ Current Time", style=discord.ButtonStyle.secondary, emoji="⏰")
    async def current_time(self, interaction: discord.Interaction, button: discord.ui.Button):
        current_time = get_ph_time()
        await interaction.response.send_message(
            f"⏰ **Current Philippine Time:** {current_time.strftime('%Y-%m-%d %I:%M:%S %p PHT')}",
            ephemeral=True
        )

# ===== HELPER FUNCTIONS =====
def get_ph_time():
    return datetime.now(PH_TZ)

def format_time_left(time_delta):
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
    try:
        current_time = get_ph_time()
        # ... (same parse_manual_time function as before)
        # [Keep the original parse_manual_time function content here]
        
    except Exception as e:
        raise ValueError(f"Invalid time format: {str(e)}")

def get_next_spawn_time(boss_name):
    if boss_name not in FIXED_BOSSES:
        return None

    boss_info = FIXED_BOSSES[boss_name]
    current_time = get_ph_time()
    current_weekday = current_time.strftime("%A").lower()
    current_time_str = current_time.strftime("%H:%M")

    spawn_times = []
    for spawn_info in boss_info["spawn_times"]:
        spawn_day = spawn_info["day"]
        spawn_time_str = spawn_info["time"]
        spawn_hour, spawn_minute = map(int, spawn_time_str.split(":"))

        days_ahead = (list(days_of_week).index(spawn_day) - list(days_of_week).index(current_weekday))
        if days_ahead < 0 or (days_ahead == 0 and spawn_time_str <= current_time_str):
            days_ahead += 7

        spawn_date = current_time + timedelta(days=days_ahead)
        spawn_date = spawn_date.replace(hour=spawn_hour, minute=spawn_minute, second=0, microsecond=0)
        spawn_times.append(spawn_date)

    return min(spawn_times)

days_of_week = ["sunday", "monday", "tuesday", "wednesday", "thursday", "friday", "saturday"]

async def send_boss_status(interaction, boss_name, boss_info):
    display_name = ' '.join(word.capitalize() for word in boss_name.split())
    spawn_time = boss_info["spawn_time"]
    kill_time = boss_info.get("kill_time", spawn_time - timedelta(hours=REGULAR_BOSSES[boss_name]["hours"]))
    current_time = get_ph_time()
    respawn_hours = REGULAR_BOSSES[boss_name]["hours"]
    location = boss_info.get("location", REGULAR_BOSSES[boss_name]["location"])

    if current_time > spawn_time:
        await interaction.followup.send(
            f"**{display_name}**\n"
            f"📍 **Location:** {location}\n"
            f"Status: ✅ **ALIVE**\n"
            f"Killed at: {kill_time.strftime('%Y-%m-%d %I:%M %p PHT')}\n"
            f"Respawn timer: {respawn_hours} hours"
        )
    else:
        time_left = spawn_time - current_time
        time_str = format_time_left(time_left)
        await interaction.followup.send(
            f"**{display_name}**\n"
            f"📍 **Location:** {location}\n"
            f"Status: ❌ **DEAD**\n"
            f"Killed at: {kill_time.strftime('%Y-%m-%d %I:%M %p PHT')}\n"
            f"Respawns: {spawn_time.strftime('%Y-%m-%d %I:%M %p PHT')}\n"
            f"Time left: {time_str}\n"
            f"Respawn timer: {respawn_hours} hours"
        )

async def send_fixed_boss_status(interaction, boss_name):
    display_name = ' '.join(word.capitalize() for word in boss_name.split())
    boss_info = FIXED_BOSSES[boss_name]
    location = boss_info["location"]
    next_spawn = get_next_spawn_time(boss_name)
    current_time = get_ph_time()

    if next_spawn:
        time_left = next_spawn - current_time
        if time_left.total_seconds() <= 0:
            status_message = f"**{display_name}**\n📍 **Location:** {location}\nStatus: ✅ **ALIVE**\nNext spawn: Calculating..."
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
            for spawn_info in boss_info["spawn_times"]:
                status_message += f"• {spawn_info['day'].capitalize()} at {spawn_info['time']}\n"
    else:
        status_message = f"**{display_name}**\n📍 **Location:** {location}\nStatus: ❓ Unable to calculate next spawn"

    await interaction.followup.send(status_message)

async def list_bosses(interaction):
    message = "**AVAILABLE BOSSES**\n```\n"
    message += "BOSS NAME           TYPE         LOCATION\n"
    message += "───────────────────────────────────────────────────\n"

    for boss_name, boss_info in sorted(ALL_BOSSES.items()):
        display_name = ' '.join(word.capitalize() for word in boss_name.split())
        name_display = display_name.ljust(18)

        if boss_name in FIXED_BOSSES:
            type_display = "FIXED-TIME".ljust(12)
        else:
            type_display = f"{boss_info['hours']}H".ljust(12)

        location_display = boss_info["location"][:25]
        message += f"{name_display} {type_display} {location_display}\n"

    message += "```\n**Legend:**\n• H = Hours respawn timer\n• FIXED-TIME = Spawns at specific times"
    await interaction.response.send_message(message, ephemeral=True)

# ===== BOT COMMANDS =====
@bot.event
async def on_ready():
    print(f'{bot.user} is online! Tracking {len(ALL_BOSSES)} bosses.')
    print(f'Using Philippine Time (PHT)')
    print(f'Notification channel ID: {NOTIFICATION_CHANNEL_ID}')
    
    channel = bot.get_channel(NOTIFICATION_CHANNEL_ID)
    if channel:
        print(f'✅ Found notification channel: {channel.name}')
        try:
            await channel.send("🤖 Boss tracker bot is now online and ready!")
        except Exception as e:
            print(f"❌ Error sending test message: {e}")
    else:
        print(f"❌ Could not find notification channel with ID {NOTIFICATION_CHANNEL_ID}")
    
    check_spawns.start()

@bot.command(name='menu', help='Show interactive boss menu')
async def show_menu(ctx):
    """Show the interactive boss menu"""
    view = MainMenuView()
    await ctx.send(
        "**🤖 BOSS TRACKER MENU**\n"
        "Choose an action below:",
        view=view
    )

# Keep the original commands for backward compatibility
@bot.command(name='kill', help='Report a boss kill with current time')
async def report_kill(ctx, *, boss_name):
    # ... (keep original kill command)
    pass

@bot.command(name='killtime', help='Report boss kill with manual time')
async def report_kill_manual(ctx, boss_name, *, time_input):
    # ... (keep original killtime command)
    pass

@bot.command(name='status', help='Check status of bosses')
async def check_status(ctx, *, specific_boss=None):
    # ... (keep original status command)
    pass

@bot.command(name='bosses', help='List all available bosses')
async def list_bosses_cmd(ctx):
    # ... (keep original bosses command)
    pass

@bot.command(name='schedule', help='Get spawn schedule')
async def get_schedule_cmd(ctx, *, boss_name):
    # ... (keep original schedule command)
    pass

@bot.command(name='location', help='Get boss location')
async def get_location_cmd(ctx, *, boss_name):
    # ... (keep original location command)
    pass

@bot.command(name='time', help='Check current time')
async def check_time_cmd(ctx):
    # ... (keep original time command)
    pass

@tasks.loop(seconds=30.0)
async def check_spawns():
    # ... (keep original check_spawns function)
    pass

# Start the keep-alive server
keep_alive()

# Run the bot
bot.run(BOT_TOKEN)
