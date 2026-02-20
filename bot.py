import os
import json
import datetime
import asyncio
import logging
import time
from typing import Union
import discord
from discord.ext import commands, tasks
from dotenv import load_dotenv
from keep_alive import keep_alive
import database # Import database module

# Load environment variables
load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')
if TOKEN:
    TOKEN = TOKEN.strip().strip('`').strip('"').strip("'")
# DATA_DIR = "data" # No longer needed for main storage

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler("bot.log", encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Configure intents
intents = discord.Intents.default()
intents.members = True  # Required to detect member joins and updates
intents.message_content = True # Required for reading commands

bot = commands.Bot(command_prefix='!', intents=intents, case_insensitive=True)
sticky_channels = {}

# Configuration
SUFFIX = " [𝙼𝚂𝚄𝚊𝚗]"
# Set this to the name of the role that triggers the nickname change
# If None, it will trigger on ANY role change (which might be spammy, so be careful)
TRIGGER_ROLE_NAME = None 

def can_manage_nick(ctx, member):
    """Checks if the bot has permission to change the member's nickname."""
    # Bot cannot change the server owner's nickname
    if member.id == ctx.guild.owner_id:
        return False, "I cannot change the Server Owner's nickname due to Discord's security limitations."
    
    # Bot cannot change nickname of someone with higher or equal role
    if member.top_role >= ctx.guild.me.top_role:
        return False, f"I cannot change {member.display_name}'s nickname because their role ({member.top_role.name}) is higher than or equal to my highest role ({ctx.guild.me.top_role.name}). Please move my role higher in the Server Settings."
        
    return True, None

async def apply_nickname(member):
    """Helper function to apply the nickname suffix."""
    settings = load_settings(member.guild.id)
    suffix = settings.get("suffix_format", SUFFIX)
    
    try:
        current_name = member.display_name
        
        # Avoid double tagging if they already have the suffix
        if current_name.endswith(suffix):
            return

        # Truncate original name if necessary to fit the suffix within 32 chars (Discord limit)
        max_name_length = 32 - len(suffix)
        
        if len(current_name) > max_name_length:
            new_nick = current_name[:max_name_length] + suffix
        else:
            new_nick = current_name + suffix
            
        logger.info(f'Attempting to change nickname for {member.name} to {new_nick}')
        await member.edit(nick=new_nick)
        logger.info(f'Successfully changed nickname for {member.name} to {new_nick}')
        
    except discord.Forbidden:
        logger.warning(f"Failed to change nickname for {member.name}: Missing Permissions (Check role hierarchy)")
    except Exception as e:
        logger.error(f"An error occurred: {e}")

async def remove_nickname(member):
    """Helper function to remove the nickname suffix."""
    settings = load_settings(member.guild.id)
    suffix = settings.get("suffix_format", SUFFIX)
    
    try:
        current_name = member.display_name
        
        # Only attempt removal if the suffix exists
        if current_name.endswith(suffix):
            new_nick = current_name[:-len(suffix)]
            
            # If the name becomes empty (edge case), don't change it or revert to name
            if not new_nick.strip():
                new_nick = member.name
            
            logger.info(f'Attempting to remove nickname suffix for {member.name} to {new_nick}')
            await member.edit(nick=new_nick)
            logger.info(f'Successfully removed nickname suffix for {member.name}')
            
    except discord.Forbidden:
        logger.warning(f"Failed to remove nickname for {member.name}: Missing Permissions (Check role hierarchy)")
    except Exception as e:
        logger.error(f"An error occurred: {e}")


@bot.event
async def on_member_join(member):
    logger.info(f"Member joined: {member.name}")
    
    # If member is pending (Membership Screening), wait for on_member_update
    if member.pending:
        logger.info(f"Member {member.name} is pending verification. Skipping auto-nick.")
        return

    settings = load_settings(member.guild.id)
    if settings.get("auto_nick_on_join", False):
        await apply_nickname(member)

@bot.event
async def on_member_update(before, after):
    settings = load_settings(after.guild.id)
    
    # Handle Membership Screening Completion (Pending -> Member)
    if before.pending and not after.pending:
        logger.info(f"Member {after.name} completed verification.")
        if settings.get("auto_nick_on_join", False):
             await apply_nickname(after)

    # Enforce Suffix
    if settings.get("enforce_suffix", False):
        # Check if nickname changed and suffix was removed
        if before.display_name != after.display_name:
             suffix = settings.get("suffix_format", SUFFIX)
             if not after.display_name.endswith(suffix):
                 await apply_nickname(after)

    # Remove on Role Loss (placeholder logic)
    pass
    # Auto-nickname disabled by request
    # pass
    # Check if roles have changed
    # if len(before.roles) < len(after.roles):
    #     # A role was added
    #     new_roles = [role for role in after.roles if role not in before.roles]
    #     for role in new_roles:
    #         print(f"User {after.name} received role: {role.name}")
            
    #         if TRIGGER_ROLE_NAME:
    #             if role.name == TRIGGER_ROLE_NAME:
    #                 await apply_nickname(after)
    #         else:
    #             await apply_nickname(after)

    # elif len(before.roles) > len(after.roles):
    #     # A role was removed
    #     removed_roles = [role for role in before.roles if role not in after.roles]
    #     for role in removed_roles:
    #         print(f"User {after.name} lost role: {role.name}")
            
    #         if TRIGGER_ROLE_NAME:
    #             if role.name == TRIGGER_ROLE_NAME:
    #                 await remove_nickname(after)
    #         else:
    #             if len(after.roles) <= 1:
    #                  await remove_nickname(after)

@bot.command(name='setnick')
@commands.has_permissions(manage_nicknames=True)
async def set_nickname(ctx, member: discord.Member, *, new_name: str):
    """
    Manually sets a user's nickname and appends the suffix.
    Usage: !setnick @Member NewName
    """
    # Check hierarchy first
    allowed, message = can_manage_nick(ctx, member)
    if not allowed:
        await ctx.send(f"Failed: {message}")
        return

    try:
        # Check if the suffix is already in the provided name, if not, append it
        if not new_name.endswith(SUFFIX):
             # Truncate if necessary
            max_name_length = 32 - len(SUFFIX)
            if len(new_name) > max_name_length:
                new_nick = new_name[:max_name_length] + SUFFIX
            else:
                new_nick = new_name + SUFFIX
        else:
            new_nick = new_name
            
        await member.edit(nick=new_nick)
        await ctx.send(f"Successfully changed nickname for {member.mention} to `{new_nick}`")
        
    except discord.Forbidden:
        await ctx.send("Failed: I don't have permission to change that user's nickname. (Unexpected Forbidden error)")
    except Exception as e:
        await ctx.send(f"An error occurred: {e}")

@set_nickname.error
async def set_nickname_error(ctx, error):
    if isinstance(error, commands.MissingPermissions):
        await ctx.send("You do not have permission to use this command.")
    elif isinstance(error, commands.MissingRequiredArgument):
        await ctx.send("Usage: `!setnick @Member New Name`")

@bot.command(name='nick')
async def nick(ctx, *, name: str = None):
    """
    Sets your own nickname with the suffix.
    Usage: !nick NewName
    Usage: !nick remove (to remove the suffix)
    """
    logger.info(f"Command !nick triggered by {ctx.author}")
    member = ctx.author
    
    if name is None:
        await ctx.send("Usage: Type `!nick YourName` to change your nickname, or `!nick remove` to remove the suffix.")
        return

    if name.lower() == "remove":
        # Check hierarchy first
        allowed, message = can_manage_nick(ctx, member)
        if not allowed:
            await ctx.send(f"Failed: {message}")
            return
            
        await remove_nickname(member)
        await ctx.send(f"Nickname suffix removed for {member.mention}.")
    else:
        try:
            # Check hierarchy first
            allowed, message = can_manage_nick(ctx, member)
            if not allowed:
                await ctx.send(f"Failed: {message}")
                return

            # Check if the suffix is already in the provided name, if not, append it
            settings = load_settings(ctx.guild.id)
            suffix = settings.get("suffix_format", SUFFIX)
            if not name.endswith(suffix):
                 # Truncate if necessary
                max_name_length = 32 - len(suffix)
                if len(name) > max_name_length:
                    new_nick = name[:max_name_length] + suffix
                else:
                    new_nick = name + suffix
            else:
                new_nick = name
                
            logger.info(f"Changing nickname for {member} to {new_nick}")
            await member.edit(nick=new_nick)
            await ctx.send(f"Successfully changed nickname for {member.mention} to `{new_nick}`")
            
        except discord.Forbidden:
            logger.warning("Forbidden: Cannot change nickname.")
            await ctx.send("Failed: I don't have permission to change your nickname. Ensure my role is higher than yours in the server settings.")
        except Exception as e:
            logger.error(f"Error in !nick: {e}")
            await ctx.send(f"An error occurred: {e}")

@nick.error
async def nick_error(ctx, error):
    # MissingRequiredArgument is now handled inside the command function
    pass

# --- Helper Functions ---

def parse_time_input(time_str):
    """Parses various time string formats into HH:MM (24h)."""
    time_str = time_str.lower().replace(" ", "").replace(".", "")
    
    # Formats to try
    # %H:%M (14:30), %I:%M%p (2:30pm), %I%p (2pm), %H (14)
    formats = [
        "%H:%M", 
        "%I:%M%p", 
        "%I%p", 
        "%H"
    ]
    
    for fmt in formats:
        try:
            dt = datetime.datetime.strptime(time_str, fmt)
            return dt.strftime("%H:%M")
        except ValueError:
            continue
            
    return None

@bot.command(name='ping')
async def ping(ctx):
    """Checks if the bot is alive."""
    await ctx.send(f"Pong! 🏓 Latency: {round(bot.latency * 1000)}ms")

async def check_and_notify_setup_completion(ctx):
    """
    Checks if all critical configuration steps are completed and notifies the user.
    Required: Time Window, Report Channel, Present Role, Absent Role, Excused Role, Permit Role.
    """
    try:
        data = load_attendance_data(ctx.guild.id)
        settings = load_settings(ctx.guild.id)
        
        # Check required fields
        # 1. Time Window (implied by attendance_mode='window' which is set by !settime, 
        #    but we check if start/end times are set properly just in case)
        has_time = settings.get('attendance_mode') == 'window' and settings.get('window_start_time') and settings.get('window_end_time')
        
        # 2. Roles
        has_present = bool(data.get('attendance_role_id'))
        has_absent = bool(data.get('absent_role_id'))
        has_excused = bool(data.get('excused_role_id'))
        has_permit = bool(data.get('allowed_role_id'))
        
        # 3. Channel
        has_channel = bool(data.get('report_channel_id'))
        
        if has_time and has_present and has_absent and has_excused and has_permit and has_channel:
            # Check if we already notified? 
            # For now, we'll just send a nice embed message.
            # To prevent spam on every single command if they re-run them, we could add a flag,
            # but the user asked for a message "after ... then the bot will message me".
            
            embed = discord.Embed(
                title="🎉 Setup Complete!",
                description=(
                    "All systems are go! The bot is fully configured.\n\n"
                    "**Configuration Checklist:**\n"
                    "✅ Time Window Set\n"
                    "✅ Attendance Report Channel Assigned\n"
                    "✅ 'Present' Role Configured\n"
                    "✅ 'Absent' Role Configured\n"
                    "✅ 'Excused' Role Configured\n"
                    "✅ 'Permitted' Role Configured\n\n"
                    "Users with the **Permitted Role** can now use `!present` within the time window to mark their attendance!"
                ),
                color=discord.Color.green()
            )
            await ctx.send(embed=embed)
            
    except Exception as e:
        logger.error(f"Error in setup check: {e}")

@bot.command(name='settime')
@commands.has_permissions(administrator=True)
async def set_attendance_time(ctx, *, time_input: str = None):
    """
    Sets the attendance window time.
    Usage: !settime 6am to 11:59pm
    Usage: !settime 08:00 - 17:00
    """
    logger.info(f"Command execution started: settime with input '{time_input}'")
    
    # Normalize input
    if not time_input:
         await ctx.send("❌ Please provide a time range. Usage: `!settime 6am to 11:59pm`")
         return
         
    try:
        raw_input = time_input.lower()
        logger.info(f"Processing time input: '{raw_input}'")
        
        # Try different separators
        parts = []
        if " to " in raw_input:
            parts = raw_input.split(" to ")
        elif "-" in raw_input:
            parts = raw_input.split("-")
        else:
            # Fallback: Split by space
            temp_parts = raw_input.split()
            if len(temp_parts) == 2:
                parts = temp_parts
        
        if len(parts) < 2:
            logger.warning(f"Failed to split time input: {raw_input}")
            await ctx.send("Could not identify start and end time. Please separate them with `to` or `-`. \nExample: `!settime 6am to 11pm`")
            return
    
        start_str = parts[0].strip()
        end_str = parts[1].strip()
    
        # Validate
        s_parsed = parse_time_input(start_str)
        e_parsed = parse_time_input(end_str)
        
        if not s_parsed or not e_parsed:
            logger.warning(f"Failed to parse times: {start_str} -> {s_parsed}, {end_str} -> {e_parsed}")
            await ctx.send(f"Invalid time format (`{start_str}` or `{end_str}`). Please use formats like `6am`, `11:59pm`, `08:00`.")
            return
            
        settings = load_settings(ctx.guild.id)
        settings['attendance_mode'] = 'window'
        settings['window_start_time'] = s_parsed
        settings['window_end_time'] = e_parsed
        
        # Reset the last processed date so we don't accidentally skip today if re-setting
        settings['last_processed_date'] = None
        
        save_settings(ctx.guild.id, settings)
        
        # Convert to 12-hour format for confirmation message
        dt_start = datetime.datetime.strptime(s_parsed, "%H:%M")
        dt_end = datetime.datetime.strptime(e_parsed, "%H:%M")
        display_s = dt_start.strftime("%I:%M %p").lstrip('0')
        display_e = dt_end.strftime("%I:%M %p").lstrip('0')
        
        logger.info(f"Successfully saved settings: {s_parsed} - {e_parsed}")
        await ctx.send(f"✅ Attendance time set to **{display_s} - {display_e}**. Mode switched to 'Window'.")
        
        # Check if allowed_role is set for auto-absence
        data = load_attendance_data(ctx.guild.id)
        if not data.get('allowed_role_id'):
            await ctx.send("⚠️ **Note:** You haven't set a 'Permitted Role' (the role required to attend). \n"
                           "Bot cannot determine who is 'missing' without it. \n"
                           "Please run `!setpermitrole @Role` (e.g., @Student) so the bot knows who should be marked absent if they don't show up.")
        
        await ctx.send(f"Bot will now automatically mark absences and reset attendance after {display_e}.")
        
        # Check setup completion
        await check_and_notify_setup_completion(ctx)
        
    except Exception as e:
        logger.error(f"Critical error in set_attendance_time: {e}", exc_info=True)
        await ctx.send(f"❌ An internal error occurred: {e}")

# --- Attendance Logic ---

_settings_cache = {}

def load_attendance_data(guild_id):
    """Loads attendance data for a specific guild from the database."""
    config = database.get_guild_config(guild_id)
    if not config:
        # Default structure for new guilds
        return {
            "attendance_role_id": None, 
            "absent_role_id": None, 
            "excused_role_id": None, 
            "welcome_channel_id": None, 
            "report_channel_id": None,
            "last_report_message_id": None,
            "last_report_channel_id": None,
            "records": {}, 
            "settings": {}
        }
    
    # Reconstruct settings dict
    settings = {
        "attendance_mode": config.get('attendance_mode'),
        "attendance_expiry_hours": config.get('attendance_expiry_hours'),
        "window_start_time": config.get('window_start_time'),
        "window_end_time": config.get('window_end_time'),
        "last_processed_date": config.get('last_processed_date'),
        "last_opened_date": config.get('last_opened_date'),
        "allow_self_marking": bool(config.get('allow_self_marking')),
        "require_admin_excuse": bool(config.get('require_admin_excuse')),
        "auto_nick_on_join": bool(config.get('auto_nick_on_join')),
        "enforce_suffix": bool(config.get('enforce_suffix')),
        "remove_suffix_on_role_loss": bool(config.get('remove_suffix_on_role_loss')),
        "suffix_format": config.get('suffix_format')
    }
    
    records = database.get_attendance_records(guild_id)
    
    return {
        "attendance_role_id": config.get('attendance_role_id'),
        "absent_role_id": config.get('absent_role_id'),
        "excused_role_id": config.get('excused_role_id'),
        "welcome_channel_id": config.get('welcome_channel_id'),
        "report_channel_id": config.get('report_channel_id'),
        "last_report_message_id": config.get('last_report_message_id'),
        "last_report_channel_id": config.get('last_report_channel_id'),
        "records": records,
        "settings": settings
    }

def save_attendance_data(guild_id, guild_data):
    """Saves attendance data for a specific guild to the database."""
    settings = guild_data.get('settings', {})
    
    # Flatten for DB update
    config_update = {
        "attendance_role_id": guild_data.get('attendance_role_id'),
        "absent_role_id": guild_data.get('absent_role_id'),
        "excused_role_id": guild_data.get('excused_role_id'),
        "welcome_channel_id": guild_data.get('welcome_channel_id'),
        "report_channel_id": guild_data.get('report_channel_id'),
        "last_report_message_id": guild_data.get('last_report_message_id'),
        "last_report_channel_id": guild_data.get('last_report_channel_id'),
        
        # Settings
        "attendance_mode": settings.get('attendance_mode'),
        "attendance_expiry_hours": settings.get('attendance_expiry_hours'),
        "window_start_time": settings.get('window_start_time'),
        "window_end_time": settings.get('window_end_time'),
        "last_processed_date": settings.get('last_processed_date'),
        "last_opened_date": settings.get('last_opened_date'),
        "allow_self_marking": settings.get('allow_self_marking'),
        "require_admin_excuse": settings.get('require_admin_excuse'),
        "auto_nick_on_join": settings.get('auto_nick_on_join'),
        "enforce_suffix": settings.get('enforce_suffix'),
        "remove_suffix_on_role_loss": settings.get('remove_suffix_on_role_loss'),
        "suffix_format": settings.get('suffix_format')
    }
    
    database.update_guild_config(guild_id, **config_update)
    database.replace_all_records(guild_id, guild_data.get('records', {}))

def load_settings(guild_id):
    """Helper to get settings with defaults for a guild (Cached)"""
    # Check cache first
    if guild_id in _settings_cache:
        return _settings_cache[guild_id]

    config = database.get_guild_config(guild_id)
    
    defaults = {
        "debug_mode": False,
        "auto_nick_on_join": False,
        "enforce_suffix": False,
        "remove_suffix_on_role_loss": False,
        "attendance_expiry_hours": 12,
        "allow_self_marking": True,
        "require_admin_excuse": True,
        "suffix_format": " [𝙼𝚂𝚄𝚊𝚗]",
        "attendance_mode": "duration", 
        "window_start_time": "00:00",
        "window_end_time": "23:59",
        "last_processed_date": None,
        "last_opened_date": None
    }
    
    if not config:
        # Cache defaults and return
        _settings_cache[guild_id] = defaults.copy()
        return defaults.copy()
        
    # Map DB fields to settings dict
    settings = {
        "auto_nick_on_join": bool(config.get('auto_nick_on_join', False)),
        "enforce_suffix": bool(config.get('enforce_suffix', False)),
        "remove_suffix_on_role_loss": bool(config.get('remove_suffix_on_role_loss', False)),
        "attendance_expiry_hours": config.get('attendance_expiry_hours', 12),
        "allow_self_marking": bool(config.get('allow_self_marking', True)),
        "require_admin_excuse": bool(config.get('require_admin_excuse', True)),
        "suffix_format": config.get('suffix_format', " [𝙼𝚂𝚄𝚊𝚗]"),
        "attendance_mode": config.get('attendance_mode', 'duration'),
        "window_start_time": config.get('window_start_time', '00:00'),
        "window_end_time": config.get('window_end_time', '23:59'),
        "last_processed_date": config.get('last_processed_date'),
        "last_opened_date": config.get('last_opened_date')
    }
    
    # Merge defaults
    for k, v in defaults.items():
        if k not in settings or settings[k] is None:
            settings[k] = v
            
    # Update cache
    _settings_cache[guild_id] = settings
    return settings

def save_settings(guild_id, settings):
    # Update cache
    _settings_cache[guild_id] = settings
    
    config_update = {
        "attendance_mode": settings.get('attendance_mode'),
        "attendance_expiry_hours": settings.get('attendance_expiry_hours'),
        "window_start_time": settings.get('window_start_time'),
        "window_end_time": settings.get('window_end_time'),
        "last_processed_date": settings.get('last_processed_date'),
        "last_opened_date": settings.get('last_opened_date'),
        "allow_self_marking": settings.get('allow_self_marking'),
        "require_admin_excuse": settings.get('require_admin_excuse'),
        "auto_nick_on_join": settings.get('auto_nick_on_join'),
        "enforce_suffix": settings.get('enforce_suffix'),
        "remove_suffix_on_role_loss": settings.get('remove_suffix_on_role_loss'),
        "suffix_format": settings.get('suffix_format')
    }
    database.update_guild_config(guild_id, **config_update)

# --- Configuration Views ---

class SettingsSelect(discord.ui.Select):
    def __init__(self, bot_instance):
        options = [
            discord.SelectOption(label="System Settings", description="Debug Mode, Sync Commands", emoji="⚙️"),
            discord.SelectOption(label="Auto-Nickname", description="Suffix, Auto-Add, Enforce", emoji="📝"),
            discord.SelectOption(label="Attendance Settings", description="Expiry, Self-Marking, Admin Only", emoji="📅"),
            discord.SelectOption(label="Presence", description="Set Bot Status", emoji="🤖")
        ]
        super().__init__(placeholder="Select a category to configure...", min_values=1, max_values=1, options=options)
        self.bot_instance = bot_instance

    async def callback(self, interaction: discord.Interaction):
        category = self.values[0]
        settings = load_settings(interaction.guild.id)
        
        if category == "System Settings":
            view = SystemSettingsView(interaction.guild.id, settings)
            embed = discord.Embed(title="System Settings", color=discord.Color.blue())
            embed.add_field(name="Debug Mode", value="Enabled" if settings['debug_mode'] else "Disabled")
            await interaction.response.edit_message(embed=embed, view=view)
            
        elif category == "Auto-Nickname":
            view = AutoNickSettingsView(interaction.guild.id, settings)
            embed = discord.Embed(title="Auto-Nickname Configuration", color=discord.Color.green())
            embed.add_field(name="Suffix Format", value=f"`{settings['suffix_format']}`", inline=False)
            embed.add_field(name="Auto-Add on Join", value=str(settings['auto_nick_on_join']))
            embed.add_field(name="Enforce Suffix", value=str(settings['enforce_suffix']))
            embed.add_field(name="Remove on Role Loss", value=str(settings['remove_suffix_on_role_loss']))
            await interaction.response.edit_message(embed=embed, view=view)
            
        elif category == "Attendance Settings":
            view = AttendanceSettingsView(interaction.guild.id, settings)
            embed = discord.Embed(title="Attendance Settings", color=discord.Color.orange())
            embed.add_field(name="Attendance Mode", value=settings['attendance_mode'].title())
            if settings['attendance_mode'] == 'window':
                 embed.add_field(name="Window", value=f"{settings['window_start_time']} - {settings['window_end_time']}")
            else:
                 embed.add_field(name="Auto-Expiry (Hours)", value=str(settings['attendance_expiry_hours']))
            
            embed.add_field(name="Allow Self-Marking", value=str(settings['allow_self_marking']))
            embed.add_field(name="Require Admin for Excuse", value=str(settings['require_admin_excuse']))
            await interaction.response.edit_message(embed=embed, view=view)
            
        elif category == "Presence":
            await interaction.response.send_modal(PresenceModal(self.bot_instance))

class PresenceModal(discord.ui.Modal, title="Set Bot Presence"):
    status_type = discord.ui.TextInput(label="Type (playing, watching, listening)", placeholder="playing")
    status_text = discord.ui.TextInput(label="Status Text", placeholder="Managing Attendance")

    def __init__(self, bot_instance):
        super().__init__()
        self.bot_instance = bot_instance

    async def on_submit(self, interaction: discord.Interaction):
        activity_type = discord.ActivityType.playing
        if self.status_type.value.lower() == 'watching':
            activity_type = discord.ActivityType.watching
        elif self.status_type.value.lower() == 'listening':
            activity_type = discord.ActivityType.listening
            
        await self.bot_instance.change_presence(activity=discord.Activity(type=activity_type, name=self.status_text.value))
        await interaction.response.send_message(f"Presence updated to: {self.status_type.value} {self.status_text.value}", ephemeral=True)

class BaseSettingsView(discord.ui.View):
    def __init__(self, guild_id, settings):
        super().__init__(timeout=180)
        self.guild_id = guild_id
        self.settings = settings

    async def update_message(self, interaction, embed):
        save_settings(self.guild_id, self.settings)
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="Back to Main Menu", style=discord.ButtonStyle.secondary, row=4)
    async def back_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(embed=discord.Embed(title="Settings Dashboard", description="Select a category below."), view=MainSettingsView(interaction.client))

class SystemSettingsView(BaseSettingsView):
    @discord.ui.button(label="Toggle Debug Mode", style=discord.ButtonStyle.primary)
    async def toggle_debug(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.settings['debug_mode'] = not self.settings['debug_mode']
        
        # Apply logging change immediately
        if self.settings['debug_mode']:
            logger.setLevel(logging.DEBUG)
            logging.getLogger().setLevel(logging.DEBUG)
        else:
            logger.setLevel(logging.INFO)
            logging.getLogger().setLevel(logging.INFO)
            
        embed = interaction.message.embeds[0]
        embed.set_field_at(0, name="Debug Mode", value="Enabled" if self.settings['debug_mode'] else "Disabled")
        await self.update_message(interaction, embed)

class AutoNickSettingsView(BaseSettingsView):
    @discord.ui.button(label="Toggle Auto-Add on Join", style=discord.ButtonStyle.primary)
    async def toggle_auto_add(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.settings['auto_nick_on_join'] = not self.settings['auto_nick_on_join']
        self.update_embed(interaction.message.embeds[0])
        await self.update_message(interaction, interaction.message.embeds[0])

    @discord.ui.button(label="Toggle Enforce Suffix", style=discord.ButtonStyle.primary)
    async def toggle_enforce(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.settings['enforce_suffix'] = not self.settings['enforce_suffix']
        self.update_embed(interaction.message.embeds[0])
        await self.update_message(interaction, interaction.message.embeds[0])

    @discord.ui.button(label="Toggle Remove on Role Loss", style=discord.ButtonStyle.primary)
    async def toggle_remove(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.settings['remove_suffix_on_role_loss'] = not self.settings['remove_suffix_on_role_loss']
        self.update_embed(interaction.message.embeds[0])
        await self.update_message(interaction, interaction.message.embeds[0])

    def update_embed(self, embed):
        embed.set_field_at(1, name="Auto-Add on Join", value=str(self.settings['auto_nick_on_join']))
        embed.set_field_at(2, name="Enforce Suffix", value=str(self.settings['enforce_suffix']))
        embed.set_field_at(3, name="Remove on Role Loss", value=str(self.settings['remove_suffix_on_role_loss']))

class TimeWindowModal(discord.ui.Modal, title="Set Time Window"):
    start_time = discord.ui.TextInput(label="Start Time (HH:MM 24h)", placeholder="08:00", min_length=5, max_length=5)
    end_time = discord.ui.TextInput(label="End Time (HH:MM 24h)", placeholder="17:00", min_length=5, max_length=5)

    def __init__(self, view_instance):
        super().__init__()
        self.view_instance = view_instance

    async def on_submit(self, interaction: discord.Interaction):
        # Basic validation
        try:
            datetime.datetime.strptime(self.start_time.value, "%H:%M")
            datetime.datetime.strptime(self.end_time.value, "%H:%M")
        except ValueError:
            await interaction.response.send_message("Invalid time format. Please use HH:MM (e.g., 09:00, 23:59).", ephemeral=True)
            return

        self.view_instance.settings['window_start_time'] = self.start_time.value
        self.view_instance.settings['window_end_time'] = self.end_time.value
        self.view_instance.update_embed(interaction.message.embeds[0])
        await self.view_instance.update_message(interaction, interaction.message.embeds[0])

class AttendanceSettingsView(BaseSettingsView):
    @discord.ui.button(label="Toggle Mode (Duration/Window)", style=discord.ButtonStyle.primary, row=0)
    async def toggle_mode(self, interaction: discord.Interaction, button: discord.ui.Button):
        current = self.settings.get('attendance_mode', 'duration')
        self.settings['attendance_mode'] = 'window' if current == 'duration' else 'duration'
        self.update_embed(interaction.message.embeds[0])
        await self.update_message(interaction, interaction.message.embeds[0])

    @discord.ui.button(label="Set Time Window", style=discord.ButtonStyle.secondary, row=0)
    async def set_window(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.settings.get('attendance_mode') != 'window':
             await interaction.response.send_message("Enable 'Window' mode first.", ephemeral=True)
             return
        await interaction.response.send_modal(TimeWindowModal(self))

    @discord.ui.button(label="Toggle Self-Marking", style=discord.ButtonStyle.primary, row=1)
    async def toggle_self_mark(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.settings['allow_self_marking'] = not self.settings['allow_self_marking']
        self.update_embed(interaction.message.embeds[0])
        await self.update_message(interaction, interaction.message.embeds[0])

    @discord.ui.button(label="Toggle Admin Only Excuse", style=discord.ButtonStyle.primary, row=1)
    async def toggle_admin_excuse(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.settings['require_admin_excuse'] = not self.settings['require_admin_excuse']
        self.update_embed(interaction.message.embeds[0])
        await self.update_message(interaction, interaction.message.embeds[0])

    @discord.ui.select(placeholder="Select Expiry Time (Duration Mode)", options=[
        discord.SelectOption(label="12 Hours", value="12"),
        discord.SelectOption(label="24 Hours", value="24"),
        discord.SelectOption(label="48 Hours", value="48")
    ], row=2)
    async def select_expiry(self, interaction: discord.Interaction, select: discord.ui.Select):
        self.settings['attendance_expiry_hours'] = int(select.values[0])
        self.update_embed(interaction.message.embeds[0])
        await self.update_message(interaction, interaction.message.embeds[0])

    def update_embed(self, embed):
        embed.clear_fields() # Rebuild fields
        
        mode = self.settings.get('attendance_mode', 'duration')
        embed.add_field(name="Attendance Mode", value=mode.title(), inline=False)
        
        if mode == 'window':
             embed.add_field(name="Window", value=f"{self.settings.get('window_start_time', '00:00')} - {self.settings.get('window_end_time', '23:59')}", inline=False)
        else:
             embed.add_field(name="Auto-Expiry (Hours)", value=str(self.settings['attendance_expiry_hours']), inline=False)

        embed.add_field(name="Allow Self-Marking", value=str(self.settings['allow_self_marking']))
        embed.add_field(name="Require Admin for Excuse", value=str(self.settings['require_admin_excuse']))

class MainSettingsView(discord.ui.View):
    def __init__(self, bot_instance):
        super().__init__()
        self.add_item(SettingsSelect(bot_instance))

@bot.command(name='settings', aliases=['panel', 'config'])
@commands.has_permissions(administrator=True)
async def settings_panel(ctx):
    """Opens the interactive settings dashboard."""
    embed = discord.Embed(title="Settings Dashboard", description="Select a category below to configure the bot.", color=discord.Color.blurple())
    await ctx.send(embed=embed, view=MainSettingsView(bot))

@bot.command(name='presentrole', aliases=['assignrole'])
@commands.has_permissions(manage_roles=True)
async def assign_attendance_role(ctx, role: discord.Role):
    """
    Sets the role that users receive when they say 'present'.
    Usage: !presentrole @Role (or !assignrole @Role)
    """
    data = load_attendance_data(ctx.guild.id)
    data['attendance_role_id'] = role.id
    save_attendance_data(ctx.guild.id, data)
    await ctx.send(f"Attendance role has been set to {role.mention}. Users who say 'present' will now receive this role for 12 hours.")
    
    # Check setup completion
    await check_and_notify_setup_completion(ctx)

@bot.command(name='absentrole')
@commands.has_permissions(manage_roles=True)
async def assign_absent_role(ctx, role: discord.Role):
    """
    Sets the role that users receive when marked as absent.
    Usage: !absentrole @Role
    """
    data = load_attendance_data(ctx.guild.id)
    data['absent_role_id'] = role.id
    save_attendance_data(ctx.guild.id, data)
    await ctx.send(f"Absent role has been set to {role.mention}.")
    
    # Check setup completion
    await check_and_notify_setup_completion(ctx)

@bot.command(name='excuserole')
@commands.has_permissions(manage_roles=True)
async def assign_excused_role(ctx, role: discord.Role):
    """
    Sets the role that users receive when marked as excused.
    Usage: !excuserole @Role
    """
    data = load_attendance_data(ctx.guild.id)
    data['excused_role_id'] = role.id
    save_attendance_data(ctx.guild.id, data)
    await ctx.send(f"Excused role has been set to {role.mention}.")
    
    # Check setup completion
    await check_and_notify_setup_completion(ctx)

async def update_user_status(ctx, member, status, reason=None):
    data = load_attendance_data(ctx.guild.id)
    
    # Get all role IDs
    present_role_id = data.get('attendance_role_id')
    absent_role_id = data.get('absent_role_id')
    excused_role_id = data.get('excused_role_id')
    
    target_role_id = None
    roles_to_remove = []
    
    if status == 'present':
        target_role_id = present_role_id
        if absent_role_id: roles_to_remove.append(absent_role_id)
        if excused_role_id: roles_to_remove.append(excused_role_id)
    elif status == 'absent':
        target_role_id = absent_role_id
        if present_role_id: roles_to_remove.append(present_role_id)
        if excused_role_id: roles_to_remove.append(excused_role_id)
    elif status == 'excused':
        target_role_id = excused_role_id
        if present_role_id: roles_to_remove.append(present_role_id)
        if absent_role_id: roles_to_remove.append(absent_role_id)
        
    # Remove conflicting roles
    for rid in roles_to_remove:
        role = ctx.guild.get_role(rid)
        if role and role in member.roles:
            try:
                await member.remove_roles(role)
            except discord.Forbidden:
                await ctx.send(f"Warning: Could not remove role {role.name} from {member.display_name} (Missing Permissions)")

    # Add new role
    if target_role_id:
        role = ctx.guild.get_role(target_role_id)
        if role:
            try:
                await member.add_roles(role)
                msg = f"Marked {member.mention} as **{status.upper()}** and gave them the {role.name} role."
                if reason:
                    msg += f"\nReason: {reason}"
                await ctx.send(msg, delete_after=10)
            except discord.Forbidden:
                await ctx.send(f"Failed to give {status} role to {member.display_name} (Missing Permissions)", delete_after=10)
        else:
             msg = f"Marked {member.mention} as **{status.upper()}**, but the role for this status is not configured or deleted."
             if reason:
                 msg += f"\nReason: {reason}"
             await ctx.send(msg, delete_after=10)
    else:
        msg = f"Marked {member.mention} as **{status.upper()}**. (No role configured for this status)"
        if reason:
            msg += f"\nReason: {reason}"
        await ctx.send(msg, delete_after=10)

    # Update JSON
    user_id = str(member.id)
    if 'records' not in data:
        data['records'] = {}
    
    record = {
        "status": status,
        "timestamp": datetime.datetime.now().isoformat(),
        "channel_id": ctx.channel.id
    }
    if reason:
        record["reason"] = reason
        
    data['records'][user_id] = record
    save_attendance_data(ctx.guild.id, data)
    if status in ('present', 'absent', 'excused'):
        database.increment_status_count(ctx.guild.id, member.id, status)
    
    # Philippines Time (UTC+8) for DMs
    ph_tz = datetime.timezone(datetime.timedelta(hours=8))
    now_ph = datetime.datetime.now(ph_tz)
    date_str = now_ph.strftime('%B %d, %Y')
    time_str = now_ph.strftime('%I:%M %p')

    # DM the user if excused
    if status == 'excused':
        try:
            dm_embed = discord.Embed(
                title="Attendance Status: Excused",
                description=f"You have been marked as **EXCUSED** in **{ctx.guild.name}**.",
                color=discord.Color.from_rgb(255, 255, 255),
                timestamp=now_ph
            )
            if reason:
                dm_embed.add_field(name="Reason", value=reason, inline=False)
            
            dm_embed.add_field(name="Date", value=date_str, inline=True)
            dm_embed.add_field(name="Time", value=time_str, inline=True)
            
            if ctx.guild.icon:
                dm_embed.set_author(name=ctx.guild.name, icon_url=ctx.guild.icon.url)
                dm_embed.set_thumbnail(url=ctx.guild.icon.url)
            else:
                dm_embed.set_author(name=ctx.guild.name)
            
            dm_embed.set_footer(text="Registrar Bot • Attendance System")
                
            await member.send(embed=dm_embed)
        except discord.Forbidden:
            pass
            
    # DM the user if absent
    if status == 'absent':
        try:
            dm_embed = discord.Embed(
                title="Attendance Status: Absent",
                description=f"You have been marked as **ABSENT** in **{ctx.guild.name}**.",
                color=discord.Color.red(),
                timestamp=now_ph
            )
            
            dm_embed.add_field(name="Date", value=date_str, inline=True)
            dm_embed.add_field(name="Time", value=time_str, inline=True)
            
            if ctx.guild.icon:
                dm_embed.set_author(name=ctx.guild.name, icon_url=ctx.guild.icon.url)
                dm_embed.set_thumbnail(url=ctx.guild.icon.url)
            else:
                dm_embed.set_author(name=ctx.guild.name)
            
            dm_embed.set_footer(text="Registrar Bot • Attendance System")
                
            await member.send(embed=dm_embed)
        except discord.Forbidden:
            pass

    # Refresh the report immediately
    await refresh_attendance_report(ctx.guild, force_update=True)

@bot.command(name='setpermitrole', aliases=['allowrole'])
@commands.has_permissions(manage_roles=True)
async def set_permit_role(ctx, role: discord.Role = None):
    """
    Sets the role required to use the 'present' command.
    Usage: !setpermitrole @Role
    Usage: !setpermitrole (to reset/allow everyone)
    """
    data = load_attendance_data(ctx.guild.id)
    if role:
        data['allowed_role_id'] = role.id
        await ctx.send(f"Permission Updated: Only users with the {role.mention} role can mark attendance.")
    else:
        data['allowed_role_id'] = None
        await ctx.send("Permission Updated: Everyone can now mark attendance.")
    
    save_attendance_data(ctx.guild.id, data)
    
    # Check setup completion
    await check_and_notify_setup_completion(ctx)

@bot.command(name='resetpermitrole', aliases=['resetassignrole', 'resetallowedrole'])
@commands.has_permissions(manage_roles=True)
async def reset_permit_role_users(ctx):
    """
    Removes the 'Permitted Role' (assigned via !setpermitrole) from ALL users who have it.
    This effectively resets who is allowed to say 'present'.
    Usage: !resetpermitrole
    """
    data = load_attendance_data(ctx.guild.id)
    allowed_role_id = data.get('allowed_role_id')
    
    if not allowed_role_id:
        await ctx.send("No 'Permitted Role' is currently configured. Use `!setpermitrole @Role` first.")
        return
        
    role = ctx.guild.get_role(allowed_role_id)
    if not role:
        await ctx.send("The configured 'Permitted Role' no longer exists in this server.")
        return
        
    # Get users with the role
    users_with_role = role.members
    
    if not users_with_role:
        await ctx.send(f"No users currently have the {role.mention} role.")
        return
        
    await ctx.send(f"Removing {role.mention} from {len(users_with_role)} users... This may take a moment.")
    
    count = 0
    for member in users_with_role:
        try:
            await member.remove_roles(role)
            count += 1
            # Add a small delay to avoid rate limits if many users
            if count % 5 == 0:
                await asyncio.sleep(1) 
        except discord.Forbidden:
            logger.warning(f"Failed to remove permitted role from {member.name} (Missing Permissions)")
        except Exception as e:
            logger.error(f"Error removing permitted role from {member.id}: {e}")
            
    await ctx.send(f"✅ Reset complete! Removed {role.mention} from {count} users. They will need to be re-assigned the role to say 'present'.")

@bot.command(name='reset')
@commands.has_permissions(manage_roles=True)
async def reset_specific_role(ctx, role: discord.Role):
    """
    Removes the specified role from ALL users who have it.
    Usage: !reset @Role
    """
    # Get users with the role
    users_with_role = role.members
    
    if not users_with_role:
        await ctx.send(f"No users currently have the {role.mention} role.")
        return
        
    await ctx.send(f"Removing {role.mention} from {len(users_with_role)} users... This may take a moment.")
    
    count = 0
    for member in users_with_role:
        try:
            await member.remove_roles(role)
            count += 1
            # Add a small delay to avoid rate limits if many users
            if count % 5 == 0:
                await asyncio.sleep(1) 
        except discord.Forbidden:
            logger.warning(f"Failed to remove role {role.name} from {member.name} (Missing Permissions)")
        except Exception as e:
            logger.error(f"Error removing role {role.name} from {member.id}: {e}")
            
    await ctx.send(f"✅ Reset complete! Removed {role.mention} from {count} users.")

def is_in_attendance_window(guild_id):
    settings = load_settings(guild_id)
    if settings.get('attendance_mode') != 'window':
        return True, None
    
    start_str = settings.get('window_start_time', '00:00')
    end_str = settings.get('window_end_time', '23:59')
    
    try:
        t_start = datetime.datetime.strptime(start_str, "%H:%M").time()
        t_end = datetime.datetime.strptime(end_str, "%H:%M").time()
        
        # Use Philippines Time (UTC+8)
        ph_tz = datetime.timezone(datetime.timedelta(hours=8))
        now_dt = datetime.datetime.now(ph_tz)
        now = now_dt.time()
        
        in_window = False
        if t_start <= t_end:
            in_window = t_start <= now <= t_end
        else:
            in_window = now >= t_start or now <= t_end
            
        if not in_window:
            # Convert to 12-hour format for display
            display_start = t_start.strftime("%I:%M %p").lstrip('0')
            display_end = t_end.strftime("%I:%M %p").lstrip('0')
            current_time = now.strftime("%I:%M %p").lstrip('0')
            return False, f"Attendance is only allowed between {display_start} and {display_end}. (Current Time: {current_time})"
            
        return True, None
    except ValueError:
        return True, None

@bot.command(name='present')
async def mark_present(ctx, member: discord.Member = None):
    """
    Marks a user as present.
    Usage: !present (for yourself)
    Usage: !present @User (requires Manage Roles)
    """
    if member is None:
        member = ctx.author

    # Check for required role if marking self
    if member == ctx.author:
        settings = load_settings(ctx.guild.id)
        
        # Check Window
        allowed, msg = is_in_attendance_window(ctx.guild.id)
        if not allowed:
             await ctx.send(msg)
             return
        
        if not settings.get('allow_self_marking', True):
            await ctx.send("Self-marking is currently disabled.")
            return

        data = load_attendance_data(ctx.guild.id)
        allowed_role_id = data.get('allowed_role_id')
        if allowed_role_id:
            allowed_role = ctx.guild.get_role(allowed_role_id)
            if allowed_role and allowed_role not in ctx.author.roles:
                await ctx.send(f"You need the {allowed_role.mention} role to mark attendance.")
                return

    if member != ctx.author and not ctx.author.guild_permissions.manage_roles:
        await ctx.send("You do not have permission to mark others as present.")
        return

    await update_user_status(ctx, member, 'present')

@bot.command(name='absent')
@commands.has_permissions(manage_roles=True)
async def mark_absent(ctx, member: discord.Member):
    """
    Marks a user as absent.
    Usage: !absent @User
    """
    await update_user_status(ctx, member, 'absent')

@bot.command(name='excuse')
async def mark_excuse(ctx, member: discord.Member, *, reason: str):
    """
    Marks a user as excused with a reason.
    Usage: !excuse @User I was sick
    """
    settings = load_settings(ctx.guild.id)
    if settings.get('require_admin_excuse', True):
        if not ctx.author.guild_permissions.manage_roles:
            await ctx.send("You do not have permission to excuse users.")
            return

    await update_user_status(ctx, member, 'excused', reason=reason)

@mark_excuse.error
async def mark_excuse_error(ctx, error):
    if isinstance(error, commands.MissingRequiredArgument):
        await ctx.send("Usage: `!excuse @User <reason>` (e.g., `!excuse @John I was sick`)")

def create_attendance_embed(guild):
    logger.info(f"Generating report for guild: {guild.name} ({guild.id})")
    data = load_attendance_data(guild.id)
    records = data.get('records', {})
    
    # Philippines Time (UTC+8)
    ph_tz = datetime.timezone(datetime.timedelta(hours=8))
    now_ph = datetime.datetime.now(ph_tz)

    embed = discord.Embed(title="Daily Attendance Report", color=discord.Color.gold())
    if guild.icon:
        embed.set_author(name=guild.name, icon_url=guild.icon.url)
        embed.set_thumbnail(url=guild.icon.url)
    else:
        embed.set_author(name=guild.name)
        
    # Check status
    allowed, _ = is_in_attendance_window(guild.id)
    status_str = "🟢 **OPEN**" if allowed else "🔴 **CLOSED**"
    
    # Get Window Info
    settings = data.get('settings', {})
    time_info = f"**⌚ Time:** `{now_ph.strftime('%I:%M %p')}`"
    
    if settings.get('attendance_mode') == 'window':
        end_str = settings.get('window_end_time', '23:59')
        try:
            t_end = datetime.datetime.strptime(end_str, "%H:%M").time()
            display_end = t_end.strftime("%I:%M %p").lstrip('0')
            time_info += f"\n**⏳ Deadline:** `{display_end}`"
        except:
            pass

    embed.description = (
        f"**🗓️ Date:** `{now_ph.strftime('%B %d, %Y')}`\n"
        f"{time_info}\n"
        f"**Status:** {status_str}\n"
    )
    
    # Helper to get name
    def get_name(uid):
        member = guild.get_member(int(uid))
        return member.display_name if member else f"Unknown ({uid})"

    # Sort records by name for cleaner display
    sorted_records = sorted(records.items(), key=lambda x: get_name(x[0]).lower())

    present_entries = []
    absent_entries = []
    excused_entries = []

    for uid, info in sorted_records:
        if isinstance(info, str):
            info = {"status": "present", "timestamp": info}
            
        status = info.get('status', 'present')
        reason = info.get('reason')
        name = get_name(uid)
        
        entry = f"• {name}"
        if reason:
            entry += f" (*{reason}*)"

        if status == 'present':
            present_entries.append(entry)
        elif status == 'absent':
            absent_entries.append(entry)
        elif status == 'excused':
            excused_entries.append(entry)

    # Helper to chunk list to avoid hitting Discord 1024 char limit
    def format_list(entries):
        if not entries:
            return "None"
        text = "\n".join(entries)
        if len(text) > 1000:
            return text[:950] + "\n... (truncated)"
        return text

    embed.add_field(name=f"✅  **Present**  ` {len(present_entries)} `", value=format_list(present_entries), inline=True)
    embed.add_field(name=f"❌  **Absent**  ` {len(absent_entries)} `", value=format_list(absent_entries), inline=True)
    embed.add_field(name=f"⚠️  **Excused**  ` {len(excused_entries)} `", value=format_list(excused_entries), inline=False)
    
    embed.set_footer(text=f"Calvsbot • Last Updated: {now_ph.strftime('%I:%M %p')}", icon_url=guild.icon.url if guild.icon else None)
    
    return embed

@bot.command(name='removepresent')
@commands.has_permissions(manage_roles=True)
async def remove_present(ctx, member: discord.Member):
    """
    Removes a user's present status/role so they can mark attendance again.
    Usage: !removepresent @User
    """
    data = load_attendance_data(ctx.guild.id)
    role_id = data.get('attendance_role_id')
    user_id = str(member.id)
    
    # Remove from records
    if 'records' in data and user_id in data['records']:
        del data['records'][user_id]
        save_attendance_data(ctx.guild.id, data)
    
    # Remove role
    if role_id:
        role = ctx.guild.get_role(role_id)
        if role and role in member.roles:
            try:
                await member.remove_roles(role)
            except discord.Forbidden:
                await ctx.send("Warning: Could not remove role (Missing Permissions).")
                
    await ctx.send(f"Reset attendance for {member.mention}. You can now say 'present' again.")

@bot.command(name='restartattendance', aliases=['resetattendance'])
@commands.has_permissions(administrator=True)
async def restart_attendance(ctx):
    """
    Completely resets ALL attendance data and settings for this server.
    Removes roles from present users, clears all records, and resets configuration.
    Usage: !restartattendance
    """
    embed = discord.Embed(title="⚠️ Confirm Full Reset", description="Are you sure you want to restart everything?\n\nThis will:\n1. Remove 'Present' role from all users.\n2. Delete ALL attendance records.\n3. Reset configuration (Time Window, Roles, Channels) to default.\n\nType `confirm` to proceed.", color=discord.Color.red())
    await ctx.send(embed=embed)

    def check(m):
        return m.author == ctx.author and m.channel == ctx.channel and m.content.lower() == 'confirm'

    try:
        await bot.wait_for('message', check=check, timeout=30.0)
    except asyncio.TimeoutError:
        await ctx.send("Reset cancelled (timed out).")
        return

    # Proceed with reset
    await ctx.send("🔄 Resetting attendance system... Please wait.")
    
    data = load_attendance_data(ctx.guild.id)
    
    # 1. Remove Roles
    roles_to_reset = []
    
    # Get all configured roles
    if data.get('attendance_role_id'): roles_to_reset.append(data.get('attendance_role_id'))
    if data.get('absent_role_id'): roles_to_reset.append(data.get('absent_role_id'))
    if data.get('excused_role_id'): roles_to_reset.append(data.get('excused_role_id'))
    
    for rid in roles_to_reset:
        role = ctx.guild.get_role(rid)
        if role:
            for member in role.members:
                try:
                    await member.remove_roles(role)
                    await asyncio.sleep(0.3)
                except: pass
    
    # 2. Wipe Data and Settings
    # Create a fresh default structure
    default_settings = {
        "suffix_format": " [𝙼𝚂𝚄𝚊𝚗]",
        "auto_nick_on_join": False,
        "enforce_suffix": False,
        "remove_suffix_on_role_loss": False,
        "attendance_mode": "duration",
        "attendance_expiry_hours": 12,
        "allow_self_marking": True,
        "require_admin_excuse": False,
        "window_start_time": "08:00",
        "window_end_time": "17:00",
        "last_processed_date": None
    }

    fresh_data = {
        "attendance_role_id": data.get('attendance_role_id'),
        "absent_role_id": data.get('absent_role_id'),
        "excused_role_id": data.get('excused_role_id'),
        "welcome_channel_id": data.get('welcome_channel_id'),
        "report_channel_id": data.get('report_channel_id'),
        "records": {},
        "settings": default_settings
    }
    
    save_attendance_data(ctx.guild.id, fresh_data)
    database.clear_attendance_stats(ctx.guild.id)
    
    # Attempt to post a fresh, empty report to the report channel
    report_channel_id = data.get('report_channel_id')
    if report_channel_id:
        channel = ctx.guild.get_channel(report_channel_id)
        if channel:
            try:
                # Create a temporary guild object or just call the function since it only needs ID for loading data
                # but create_attendance_embed uses guild.get_member etc.
                # Since we are in ctx, we can use ctx.guild
                embed = create_attendance_embed(ctx.guild)
                await channel.send(embed=embed)
            except:
                pass

    await ctx.send("✅ **System Reset Complete.**\nAll data has been cleared. You can now reconfigure the bot using `!settime`, `!assignchannel`, etc.")

# Store the last report state to prevent unnecessary updates
guild_report_state = {}

async def refresh_attendance_report(guild, target_channel=None, force_update=False):
    """
    Updates the existing report or sends a new one if it doesn't exist.
    """
    data = load_attendance_data(guild.id)
    
    # Calculate state to check if update is needed
    try:
        is_open, _ = is_in_attendance_window(guild.id)
        records = data.get('records', {})
        # Create a stable string representation of the data that affects the report content
        # We include: Open Status, Records (sorted), and Window Settings (in case time changes)
        settings = data.get('settings', {})
        window_info = f"{settings.get('window_start_time')}-{settings.get('window_end_time')}"
        
        # Sort records by user ID to ensure consistent ordering in the hash
        sorted_records = sorted(records.items())
        
        current_state = f"{is_open}|{window_info}|{str(sorted_records)}"
        
        last_state = guild_report_state.get(guild.id)
        
        if not force_update and last_state == current_state:
            # Content hasn't changed, skip update to prevent spam
            return None
            
        guild_report_state[guild.id] = current_state
        
    except Exception as e:
        logger.error(f"Error calculating report state: {e}")
        # If calculation fails, proceed with update just in case
    
    last_msg_id = data.get('last_report_message_id')
    last_chan_id = data.get('last_report_channel_id')
    
    # Determine Target Channel
    channel = target_channel
    if not channel:
        report_channel_id = data.get('report_channel_id')
        if report_channel_id:
            channel = guild.get_channel(report_channel_id)
            
    # Removed fallback to welcome/system channel to allow "removing" the report completely
    if not channel:
        return None # Nowhere to send

    # SAFETY CHECK: Ensure target channel belongs to the guild
    if channel.guild.id != guild.id:
        logger.error(f"Security Alert: Attempted to post report for {guild.name} to channel in {channel.guild.name}!")
        return None
        
    embed = create_attendance_embed(guild)
    
    # Try to edit existing message if channel matches
    if last_msg_id and last_chan_id and last_chan_id == channel.id:
        try:
            msg = await channel.fetch_message(last_msg_id)
            await msg.edit(embed=embed)
            return msg
        except (discord.NotFound, discord.Forbidden):
            # Message deleted or can't access, fall through to send new
            pass
        except Exception as e:
            logger.error(f"Error editing report: {e}")
            pass

    # If we are here, we need to send a new message
    # First, try to delete the old one if it was in a DIFFERENT channel (or we failed to edit)
    if last_msg_id and last_chan_id and last_chan_id != channel.id:
        try:
             old_chan = guild.get_channel(last_chan_id)
             if old_chan:
                 try:
                     old_msg = await old_chan.fetch_message(last_msg_id)
                     await old_msg.delete()
                 except: pass
        except:
            pass
            
    try:
        new_msg = await channel.send(embed=embed)
        data['last_report_message_id'] = new_msg.id
        data['last_report_channel_id'] = channel.id
        save_attendance_data(guild.id, data)
        return new_msg
    except discord.Forbidden:
        return None

@bot.command(name='attendance_leaderboard', aliases=['presentleaderboard', 'leaderboard'])
async def attendance_leaderboard(ctx, limit: int = 10):
    if limit < 1:
        limit = 1
    if limit > 25:
        limit = 25
    rows = database.get_attendance_leaderboard(ctx.guild.id, limit)
    if not rows:
        await ctx.send("No attendance data yet.")
        return
    embed = discord.Embed(
        title="Attendance Leaderboard",
        description=None,
        color=discord.Color.gold()
    )
    if ctx.guild.icon:
        embed.set_author(name=ctx.guild.name, icon_url=ctx.guild.icon.url)
        embed.set_thumbnail(url=ctx.guild.icon.url)
    else:
        embed.set_author(name=ctx.guild.name)
    header = "**Rank | Member | Present / Absent / Excused**"
    lines = [header]
    rank = 1
    for row in rows:
        member = ctx.guild.get_member(row["user_id"])
        if not member:
            continue
        present = row["present_count"] or 0
        absent = row["absent_count"] or 0
        excused = row["excused_count"] or 0
        lines.append(f"{rank}. {member.mention} — {present} / {absent} / {excused}")
        rank += 1
    if not lines:
        await ctx.send("No attendance data yet.")
        return
    embed.add_field(name="Leaders", value="\n".join(lines), inline=False)
    embed.set_footer(text=f"Calvsbot • Server: {ctx.guild.name}", icon_url=ctx.guild.icon.url if ctx.guild.icon else None)
    await ctx.send(embed=embed)

@bot.command(name='stick')
@commands.has_permissions(manage_messages=True)
async def stick_message(ctx, *, message_text: str):
    msg = await ctx.send(message_text)
    sticky_channels[ctx.channel.id] = {
        "message_id": msg.id,
        "content": message_text
    }

@bot.command(name='removestick')
@commands.has_permissions(manage_messages=True)
async def removestick_message(ctx):
    sticky_channels.pop(ctx.channel.id, None)
    if ctx.message.reference and ctx.message.reference.resolved:
        target = ctx.message.reference.resolved
        try:
            if target.pinned:
                await target.unpin()
                return
        except discord.Forbidden:
            await ctx.send("I cannot unpin that message. Please check my permissions.", delete_after=5)
            return
    pins = await ctx.channel.pins()
    if not pins:
        await ctx.send("There are no pinned messages in this channel.", delete_after=5)
        return
    target = pins[0]
    try:
        await target.unpin()
    except discord.Forbidden:
        await ctx.send("I cannot unpin messages here. Please check my permissions.", delete_after=5)

@bot.command(name='attendance')
async def view_attendance(ctx):
    """
    View the current attendance lists.
    Usage: !attendance
    """
    await refresh_attendance_report(ctx.guild, ctx.channel, force_update=True)

@assign_attendance_role.error
async def assign_role_error(ctx, error):
    if isinstance(error, commands.MissingPermissions):
        await ctx.send("You do not have permission to use this command.")
    elif isinstance(error, commands.MissingRequiredArgument):
        await ctx.send("Usage: `!assignrole @Role`")
    elif isinstance(error, commands.BadArgument):
        await ctx.send("Invalid role. Please ping a valid role.")

@tasks.loop(minutes=1)
async def check_attendance_expiry():
    # Iterate over guilds first, then load data for each
    for guild in bot.guilds:
        try:
            settings = load_settings(guild.id)
            data = load_attendance_data(guild.id)
            
            mode = settings.get('attendance_mode', 'duration')
            expiry_hours = settings.get("attendance_expiry_hours", 12)
            records = data.get('records', {})
            
            # --- End of Day / Session Logic (Window Mode) ---
            if mode == 'window':
                start_str = settings.get('window_start_time', '00:00')
                end_str = settings.get('window_end_time', '23:59')
                last_processed = settings.get('last_processed_date')
            
            try:
                # Use Philippines Time (UTC+8)
                ph_tz = datetime.timezone(datetime.timedelta(hours=8))
                now = datetime.datetime.now(ph_tz)
                today_str = now.strftime("%Y-%m-%d")
                
                t_start = datetime.datetime.strptime(start_str, "%H:%M").time()
                t_end = datetime.datetime.strptime(end_str, "%H:%M").time()
                
                # Construct datetime objects for comparison (make them timezone-aware)
                dt_start = datetime.datetime.combine(now.date(), t_start).replace(tzinfo=ph_tz)
                dt_end = datetime.datetime.combine(now.date(), t_end).replace(tzinfo=ph_tz)
                
                # --- START OF WINDOW LOGIC ---
                # Automatically post/refresh report when window opens
                last_opened = settings.get('last_opened_date')
                
                if now >= dt_start and now < dt_end:
                     if last_opened != today_str:
                         logger.info(f"Opening attendance window for {guild.name}")
                         
                         # Update state FIRST to prevent loops if refresh fails
                         settings['last_opened_date'] = today_str
                         save_settings(guild.id, settings)
                         
                         try:
                             await refresh_attendance_report(guild)
                         except Exception as e:
                             logger.error(f"Failed to refresh report on window open: {e}")
                
                target_date_to_process = None
                
                # Check 1: Post-Shift (Same Day)
                # If we are past the end time today
                if now > dt_end:
                    target_date_to_process = today_str
                    
                # Check 2: Pre-Shift (Next Day / Overnight)
                # If we are before the start time, we might need to close out yesterday
                # (Logic: If we haven't closed out yesterday, do it now)
                elif now < dt_start:
                    yesterday = now - datetime.timedelta(days=1)
                    target_date_to_process = yesterday.strftime("%Y-%m-%d")

                # Handle Cross-Midnight windows (Start > End, e.g. 22:00 to 06:00)
                # Not fully supported by this simple logic yet, but user asked for 6am-11:59pm
                
                if target_date_to_process and last_processed != target_date_to_process:
                    logger.info(f"Triggering End-of-Day for {guild.name} (Date: {target_date_to_process})")
                    
                    # 1. Auto-Absent Logic
                    allowed_role_id = data.get('allowed_role_id')
                    absent_role_id = data.get('absent_role_id')
                    
                    if allowed_role_id:
                        allowed_role = guild.get_role(allowed_role_id)
                        if allowed_role:
                            # Identify missing users
                            present_ids = set(records.keys())
                            missing_members = [m for m in allowed_role.members if str(m.id) not in present_ids and not m.bot]
                            
                            # Mark them absent
                            if missing_members:
                                absent_role = guild.get_role(absent_role_id) if absent_role_id else None
                                
                                for member in missing_members:
                                    # Add to records
                                    records[str(member.id)] = {
                                        "status": "absent",
                                        "timestamp": now.isoformat(),
                                        "reason": "Auto-marked at end of attendance window"
                                    }
                                    database.increment_status_count(guild.id, member.id, "absent")
                                    
                                    # Give absent role
                                    if absent_role:
                                        try:
                                            await member.add_roles(absent_role)
                                            await asyncio.sleep(0.3)
                                        except discord.Forbidden:
                                            pass
                                    
                                    # DM the user
                                    try:
                                        dm_embed = discord.Embed(
                                            title="Attendance Status: Absent",
                                            description=f"You have been marked **ABSENT** in **{guild.name}** because you did not check in within the attendance window.",
                                            color=discord.Color.red(),
                                            timestamp=now
                                        )
                                        
                                        date_str = now.strftime('%B %d, %Y')
                                        time_str = now.strftime('%I:%M %p')
                                        
                                        dm_embed.add_field(name="Date", value=date_str, inline=True)
                                        dm_embed.add_field(name="Time", value=time_str, inline=True)

                                        if guild.icon:
                                            dm_embed.set_author(name=guild.name, icon_url=guild.icon.url)
                                            dm_embed.set_thumbnail(url=guild.icon.url)
                                        else:
                                             dm_embed.set_author(name=guild.name)
                                        
                                        dm_embed.set_footer(text="Registrar Bot • Attendance System")

                                        await member.send(embed=dm_embed)
                                        await asyncio.sleep(0.5)
                                    except discord.Forbidden:
                                        pass # User has DMs blocked
                                            
                                logger.info(f"Marked {len(missing_members)} users as absent in {guild.name}")
                    else:
                        logger.warning(f"Cannot auto-mark absences for {guild.name}: No 'allowed_role' configured.")
                    
                    # 2. Generate and Post Report
                    # Save data first so embed is accurate
                    data['records'] = records
                    save_attendance_data(guild.id, data)
                    
                    await refresh_attendance_report(guild)

                    # 3. Reset/Clear Data ("Old attendance will be out")
                    # Remove 'present' roles
                    present_role_id = data.get('attendance_role_id')
                    if present_role_id:
                        role = guild.get_role(present_role_id)
                        if role:
                            for uid in list(records.keys()):
                                member = guild.get_member(int(uid))
                                if member and role in member.roles:
                                    try:
                                        await member.remove_roles(role)
                                        await asyncio.sleep(0.3)
                                    except: pass

                    # Clear Records
                    data['records'] = {}
                    
                    # Update Settings
                    settings['last_processed_date'] = target_date_to_process
                    save_settings(guild.id, settings)
                    save_attendance_data(guild.id, data)
                    
                    logger.info(f"Attendance reset complete for {guild.name}")
                    
            except ValueError as e:
                logger.error(f"Error parsing time settings for {guild.name}: {e}")
                
        # --- End of Window Logic ---
        except Exception as e:
            logger.error(f"Error in check_attendance_expiry loop for guild {guild.id}: {e}")
        
        # Determine if we should expire individual users (Duration Mode Only)
        # Window mode now handles bulk expiry/reset above.
        if mode == 'window':
            continue 

        # ... Existing Duration Mode Logic Below ...
        
        # Get all role IDs
        role_map = {
            'present': data.get('attendance_role_id'),
            'absent': data.get('absent_role_id'),
            'excused': data.get('excused_role_id')
        }
        ping_role_id = data.get('ping_role_id')
    
        now = datetime.datetime.now()
        users_to_remove = []
        users_to_update = {} 

        for user_id_str, info in records.items():
            # Handle migration/fallback
            if isinstance(info, str):
                info = {"status": "present", "timestamp": info, "channel_id": None}
            
            timestamp_str = info.get('timestamp')
            status = info.get('status', 'present')
            channel_id = info.get('channel_id')
            role_id = role_map.get(status)

            if not timestamp_str:
                users_to_remove.append(user_id_str)
                continue

            try:
                timestamp = datetime.datetime.fromisoformat(str(timestamp_str))
                should_expire = False
                
                if mode == 'window':
                    # In window mode, we expire if we are outside the window AND they are still present
                    # We assume if they are 'present', they haven't been expired yet.
                    if expire_all_present and status == 'present':
                        should_expire = True
                else:
                    # Duration mode
                    if now - timestamp > datetime.timedelta(hours=expiry_hours):
                        should_expire = True

                if should_expire:
                    user_id = int(user_id_str)
                    member = guild.get_member(user_id)
                    
                    # 1. Remove current role
                    if member and role_id:
                        role = guild.get_role(role_id)
                        if role and role in member.roles:
                            try:
                                await member.remove_roles(role)
                                logger.info(f"Removed {status} role from {member.name} (expired)")
                            except discord.Forbidden:
                                logger.warning(f"Failed to remove role from {member.name}: Missing Permissions")
                    
                    # 2. Determine Channel
                    channel = None
                    if channel_id:
                        channel = guild.get_channel(channel_id)
                    if not channel and data.get('welcome_channel_id'):
                        channel = guild.get_channel(data.get('welcome_channel_id'))

                    # 3. Handle Transitions
                    if status == 'present':
                        # Transition to ABSENT
                        absent_role_id = data.get('absent_role_id')
                        if absent_role_id:
                            absent_role = guild.get_role(absent_role_id)
                            if absent_role and member:
                                try:
                                    await member.add_roles(absent_role)
                                except: pass
                        
                        # Schedule update to 'absent'
                        users_to_update[user_id_str] = {
                            "status": "absent",
                            "timestamp": now.isoformat(), 
                            "channel_id": channel_id
                        }
                        database.increment_status_count(guild.id, user_id, "absent")

                        # Notify
                        if channel:
                            msg_content = f"{member.mention}, your attendance session has expired. You have been marked as Absent. You are now allowed to say present again."
                            if ping_role_id:
                                ping_role = guild.get_role(ping_role_id)
                                if ping_role:
                                    msg_content = f"{ping_role.mention} " + msg_content
                            await channel.send(msg_content)

                    else:
                        # For absent/excused, just remove the record
                        users_to_remove.append(user_id_str)
                                    
            except (ValueError, TypeError) as e:
                logger.error(f"Error parsing timestamp for user {user_id_str}: {e}")
                users_to_remove.append(user_id_str)

        # Apply Updates
        if users_to_update:
            for uid, new_record in users_to_update.items():
                data['records'][uid] = new_record
                
        # Apply Removals
        if users_to_remove:
            users_to_remove = list(set(users_to_remove))
            for uid in users_to_remove:
                if uid in data['records'] and uid not in users_to_update:
                    del data['records'][uid]
                    
        if users_to_update or users_to_remove:
            save_attendance_data(guild.id, data)

@check_attendance_expiry.before_loop
async def before_check_attendance_expiry():
    await bot.wait_until_ready()

@bot.event
async def on_ready():
    logger.info(f'Logged in as {bot.user.name}')
    logger.info('Bot is ready to auto-nickname users!')
    
    # Initialize Database
    try:
        database.init_db()
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")
        
    if not check_attendance_expiry.is_running():
        check_attendance_expiry.start()
    
    # Register persistent views
    bot.add_view(AttendanceView(bot))

# --- Persistent Views for Attendance ---

class ExcuseModal(discord.ui.Modal, title="Excuse Reason"):
    reason = discord.ui.TextInput(
        label="Reason for being excused",
        style=discord.TextStyle.paragraph,
        placeholder="e.g., I was sick...",
        required=True,
        max_length=200
    )

    def __init__(self, view_instance):
        super().__init__()
        self.view_instance = view_instance

    async def on_submit(self, interaction: discord.Interaction):
        await self.view_instance.handle_attendance(interaction, "excused", self.reason.value)
        # handle_attendance handles the response

class AttendanceView(discord.ui.View):
    def __init__(self, bot_instance):
        super().__init__(timeout=None) # Persistent view
        self.bot_instance = bot_instance

    @discord.ui.button(label="Mark Present", style=discord.ButtonStyle.success, custom_id="attendance_btn_present", emoji="✅")
    async def btn_present(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.handle_attendance(interaction, "present")

    @discord.ui.button(label="Excused", style=discord.ButtonStyle.secondary, custom_id="attendance_btn_excused", emoji="⚠️")
    async def btn_excused(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Check permission for admin only excuse is handled inside handle_attendance or here?
        # The modal should open first, then we check? Or check first?
        # Checking first is better UX.
        
        settings = load_settings(interaction.guild.id)
        if settings.get('require_admin_excuse', True) and not interaction.user.guild_permissions.manage_roles:
            await interaction.response.send_message("Only admins can mark users as excused.", ephemeral=True)
            return
            
        # Open Modal to get reason
        await interaction.response.send_modal(ExcuseModal(self))

    async def handle_attendance(self, interaction, status, reason=None):
        user = interaction.user
        
        # Check Window (only for present)
        if status == 'present':
            allowed, msg = is_in_attendance_window(interaction.guild.id)
            if not allowed:
                 await interaction.response.send_message(msg, ephemeral=True)
                 return

        # Check self-marking setting (only for present)
        settings = load_settings(interaction.guild.id)
        if status == 'present' and not settings.get('allow_self_marking', True):
             await interaction.response.send_message("Self-marking is currently disabled.", ephemeral=True)
             return

        # Check permitted role
        data = load_attendance_data(interaction.guild.id)
        allowed_role_id = data.get('allowed_role_id')
        if allowed_role_id:
            allowed_role = interaction.guild.get_role(allowed_role_id)
            if allowed_role and allowed_role not in user.roles:
                await interaction.response.send_message(f"You need the {allowed_role.mention} role to use this.", ephemeral=True)
                return

        # If it's a modal submission (interaction.type == modal_submit), we don't need to defer usually if we reply quickly.
        # But process_status_update might take a moment.
        if not interaction.response.is_done():
             await interaction.response.defer(ephemeral=True)
        
        await self.process_status_update(interaction, user, status, reason)
        
        msg = f"Successfully marked as **{status.upper()}**!"
        if reason:
            msg += f"\nReason: {reason}"
        
        if interaction.response.is_done():
            await interaction.followup.send(msg, ephemeral=True)
        else:
            await interaction.response.send_message(msg, ephemeral=True)

    async def process_status_update(self, interaction, member, status, reason=None):
        # Logic duplicated/adapted from update_user_status to avoid ctx dependency
        data = load_attendance_data(interaction.guild.id)
        present_role_id = data.get('attendance_role_id')
        absent_role_id = data.get('absent_role_id')
        excused_role_id = data.get('excused_role_id')
        
        target_role_id = None
        roles_to_remove = []
        
        if status == 'present':
            target_role_id = present_role_id
            if absent_role_id: roles_to_remove.append(absent_role_id)
            if excused_role_id: roles_to_remove.append(excused_role_id)
        elif status == 'excused':
            target_role_id = excused_role_id
            if present_role_id: roles_to_remove.append(present_role_id)
            if absent_role_id: roles_to_remove.append(absent_role_id)
            
        guild = interaction.guild
        
        # Remove roles
        for rid in roles_to_remove:
            role = guild.get_role(rid)
            if role and role in member.roles:
                try:
                    await member.remove_roles(role)
                except: pass

        # Add role
        if target_role_id:
            role = guild.get_role(target_role_id)
            if role:
                try:
                    await member.add_roles(role)
                except: pass
        
        # Save record
        user_id = str(member.id)
        if 'records' not in data:
            data['records'] = {}
        
        record = {
            "status": status,
            "timestamp": datetime.datetime.now().isoformat()
        }
        if reason:
            record["reason"] = reason
            
        data['records'][user_id] = record
        save_attendance_data(interaction.guild.id, data)
        if status in ('present', 'absent', 'excused'):
            database.increment_status_count(interaction.guild.id, member.id, status)

        # Update Report
        await refresh_attendance_report(interaction.guild, interaction.channel, force_update=True)

        # Send DM if present
        if status == 'present':
            try:
                embed = discord.Embed(
                    title="✅ Attendance Confirmed",
                    description="Your attendance has been checked successfully.",
                    color=discord.Color.gold()
                )
                if interaction.guild.icon:
                    embed.set_author(name=interaction.guild.name, icon_url=interaction.guild.icon.url)
                    embed.set_thumbnail(url=interaction.guild.icon.url)
                else:
                    embed.set_author(name=interaction.guild.name)

                embed.add_field(name="Status", value="Present", inline=True)
                embed.add_field(name="Note", value="You will be notified once the 12-hour period has expired, after which you will be allowed to mark yourself as present again.", inline=False)
                embed.set_footer(text=f"Calvsbot • Server: {interaction.guild.name}")
                await member.send(embed=embed)
            except:
                pass

@bot.command(name='assignchannel')
@commands.has_permissions(administrator=True)
async def assign_report_channel(ctx, channel: Union[discord.TextChannel, str] = None):
    """
    Sets the channel where attendance reports will be sent.
    Usage: !assignchannel #channel-name
    Usage: !assignchannel remove (to disable reports)
    """
    if channel is None:
        await ctx.send("❌ Usage: `!assignchannel #channel` or `!assignchannel remove`")
        return

    try:
        data = load_attendance_data(ctx.guild.id)
        
        if isinstance(channel, str):
            if channel.lower() in ['remove', 'none', 'off', 'disable']:
                data['report_channel_id'] = None
                save_attendance_data(ctx.guild.id, data)
                await ctx.send("✅ Attendance reports have been **disabled**. No new reports will be sent.")
                return
            else:
                await ctx.send("❌ Invalid input. Please mention a channel (e.g., `#general`) or use `remove`.")
                return
                
        # If it's a TextChannel
        data['report_channel_id'] = channel.id
        save_attendance_data(ctx.guild.id, data)
        
        logger.info(f"Report channel set to {channel.name} ({channel.id}) for guild {ctx.guild.id}")
        await ctx.send(f"✅ Attendance reports will now be sent to {channel.mention}.")
        
        # Check setup completion
        await check_and_notify_setup_completion(ctx)
        
    except Exception as e:
        logger.error(f"Error assigning channel: {e}", exc_info=True)
        await ctx.send(f"❌ Failed to assign channel: {e}")

@bot.command(name='removereport', aliases=['deletereport'])
@commands.has_permissions(administrator=True)
async def remove_last_report(ctx):
    """
    Deletes the currently active attendance report message.
    Usage: !removereport
    """
    data = load_attendance_data(ctx.guild.id)
    last_msg_id = data.get('last_report_message_id')
    last_chan_id = data.get('last_report_channel_id')
    
    if not last_msg_id or not last_chan_id:
        await ctx.send("⚠️ No active report found to remove.")
        return
        
    try:
        channel = ctx.guild.get_channel(last_chan_id)
        if channel:
            try:
                msg = await channel.fetch_message(last_msg_id)
                await msg.delete()
                await ctx.send("✅ Report removed.")
            except discord.NotFound:
                await ctx.send("⚠️ Report message not found (maybe already deleted).")
            except discord.Forbidden:
                await ctx.send("❌ I don't have permission to delete the report message.")
        else:
             await ctx.send("⚠️ Report channel no longer exists.")
             
        # Clear the record so it doesn't try to edit it later
        data['last_report_message_id'] = None
        data['last_report_channel_id'] = None
        save_attendance_data(ctx.guild.id, data)
        
    except Exception as e:
        logger.error(f"Error removing report: {e}")
        await ctx.send(f"❌ Error removing report: {e}")

@bot.command(name='setup_attendance')
@commands.has_permissions(administrator=True)
async def setup_attendance_ui(ctx):
    """Posts the persistent attendance buttons."""
    embed = discord.Embed(
        title="Attendance Check-In", 
        description="Click the button below to mark your attendance.", 
        color=discord.Color.green()
    )
    await ctx.send(embed=embed, view=AttendanceView(bot))


@bot.event
async def on_command_error(ctx, error):
    """Global error handler to catch and report errors to the user."""
    if isinstance(error, commands.CommandNotFound):
        # Ignore unknown commands
        return
        
    if isinstance(error, commands.MissingPermissions):
        await ctx.send("❌ You do not have permission to use this command.")
        return
        
    if isinstance(error, commands.MissingRequiredArgument):
        await ctx.send(f"❌ Missing required argument. Usage: `{ctx.prefix}{ctx.command.name} {ctx.command.signature}`")
        return
        
    if isinstance(error, commands.BadArgument):
        await ctx.send("❌ Invalid argument provided. Please check your input.")
        return
    
    # Log the full error
    logger.error(f"Command error in {ctx.command}: {error}", exc_info=True)
    await ctx.send(f"❌ An error occurred while executing the command: `{error}`")

@bot.event
async def on_message(message):
    # Don't let the bot reply to itself
    if message.author == bot.user:
        return
    
    # Debug log to ensure we are receiving messages
    if message.content.startswith('!'):
        logger.info(f"Command-like message received from {message.author}: {message.content}")

    await bot.process_commands(message)

    msg_content = message.content.strip().lower()

    if msg_content == "present":
        if not message.guild:
            return

        settings = load_settings(message.guild.id)
        
        # Check Window
        allowed, window_msg = is_in_attendance_window(message.guild.id)
        if not allowed:
            await message.channel.send(window_msg, delete_after=5)
            return

        if not settings.get('allow_self_marking', True):
            # If self-marking is disabled, we ignore the message or warn?
            # Warn is better UX
            await message.channel.send("Self-marking is currently disabled.", delete_after=5)
            return

        data = load_attendance_data(message.guild.id)
        
        # Check permissions
        allowed_role_id = data.get('allowed_role_id')
        if allowed_role_id:
            allowed_role = message.guild.get_role(allowed_role_id)
            if allowed_role and allowed_role not in message.author.roles:
                # Silently ignore to prevent spam if they don't have perms.
                return

        attendance_role_id = data.get('attendance_role_id')
        absent_role_id = data.get('absent_role_id')
        excused_role_id = data.get('excused_role_id')

        if attendance_role_id:
            role = message.guild.get_role(attendance_role_id)
            if role:
                user_id = str(message.author.id)
                now = datetime.datetime.now()
                
                # Check if already marked today (prevent spamming present)
                # We check if they HAVE the role already as a proxy for "already present"
                if role in message.author.roles:
                     await message.channel.send(f"{message.author.mention}, you have already marked your attendance!", delete_after=5)
                else:
                    # Give role
                    try:
                        # Remove conflicting roles first
                        roles_to_remove = []
                        if absent_role_id: roles_to_remove.append(absent_role_id)
                        if excused_role_id: roles_to_remove.append(excused_role_id)
                        
                        for rid in roles_to_remove:
                            r = message.guild.get_role(rid)
                            if r and r in message.author.roles:
                                await message.author.remove_roles(r)

                        await message.author.add_roles(role)
                        await message.add_reaction("✅")
                        
                        # Update record with FULL timestamp for 24h expiry
                        if 'records' not in data:
                            data['records'] = {}
                        data['records'][user_id] = {
                            "status": "present",
                            "timestamp": now.isoformat(),
                            "channel_id": message.channel.id
                        }
                        save_attendance_data(message.guild.id, data)
                        database.increment_status_count(message.guild.id, message.author.id, "present")
                        
                        await message.channel.send(f"Attendance marked for {message.author.mention}! You have been given the {role.name} role.", delete_after=10)
                        
                        # DM the user
                        try:
                            embed = discord.Embed(
                                title="✅ Attendance Confirmed",
                                description="Your attendance has been checked successfully.",
                                color=discord.Color.gold()
                            )
                            if message.guild.icon:
                                embed.set_author(name=message.guild.name, icon_url=message.guild.icon.url)
                                embed.set_thumbnail(url=message.guild.icon.url)
                            else:
                                embed.set_author(name=message.guild.name)

                            embed.add_field(name="Status", value="Present", inline=True)
                            embed.add_field(name="Note", value="You will be notified once the 12-hour period has expired, after which you will be allowed to mark yourself as present again.", inline=False)
                            embed.set_footer(text=f"Calvsbot • Server: {message.guild.name}")
                            await message.author.send(embed=embed)
                        except discord.Forbidden:
                            logger.warning(f"Could not DM user {message.author.name} (Closed DMs)")
                        except Exception:
                            pass

                        await refresh_attendance_report(message.guild, message.channel, force_update=True)
                    except discord.Forbidden:
                        await message.channel.send("I tried to give you the role, but I don't have permission! Please check my role hierarchy.")
    elif msg_content == "presents":
        if message.guild:
            await refresh_attendance_report(message.guild, message.channel, force_update=True)
    elif msg_content.startswith("excuse"):
        if not message.guild:
            return
            
        settings = load_settings(message.guild.id)
        if settings.get('require_admin_excuse', True):
            # Check if user has manage_roles
            if not message.author.guild_permissions.manage_roles:
                await message.channel.send("Only admins can excuse users.", delete_after=5)
                return

        data = load_attendance_data(message.guild.id)
        attendance_role_id = data.get('attendance_role_id')
        absent_role_id = data.get('absent_role_id')
        excused_role_id = data.get('excused_role_id')
        
        # Parse reason
        # "excuse because i am sick" -> reason: "because i am sick"
        reason = message.content[6:].strip()
        if not reason:
            reason = "No reason provided"

        if excused_role_id:
            role = message.guild.get_role(excused_role_id)
            if role:
                user_id = str(message.author.id)
                now = datetime.datetime.now()
                
                # Check if already marked (prevent spamming)
                if role in message.author.roles:
                     await message.channel.send(f"{message.author.mention}, you have already marked your status as excused!", delete_after=5)
                else:
                    # Give role
                    try:
                        # Remove conflicting roles first
                        roles_to_remove = []
                        if attendance_role_id: roles_to_remove.append(attendance_role_id)
                        if absent_role_id: roles_to_remove.append(absent_role_id)
                        
                        for rid in roles_to_remove:
                            r = message.guild.get_role(rid)
                            if r and r in message.author.roles:
                                await message.author.remove_roles(r)

                        await message.author.add_roles(role)
                        await message.add_reaction("✅")
                        
                        # Update record with FULL timestamp for 24h expiry
                        if 'records' not in data:
                            data['records'] = {}
                        data['records'][user_id] = {
                            "status": "excused",
                            "timestamp": now.isoformat(),
                            "channel_id": message.channel.id,
                            "reason": reason
                        }
                        save_attendance_data(message.guild.id, data)
                        
                        await message.channel.send(f"Excused status marked for {message.author.mention}! Reason: {reason}", delete_after=10)
                        
                        # Automatically show the attendance report
                        await refresh_attendance_report(message.guild, force_update=True)
                    except discord.Forbidden:
                        await message.channel.send("I tried to give you the role, but I don't have permission! Please check my role hierarchy.")

    if message.guild and not message.content.startswith('!'):
        sticky_info = sticky_channels.get(message.channel.id)
        if sticky_info:
            has_image_attachment = False
            if message.attachments:
                for att in message.attachments:
                    if att.content_type and att.content_type.startswith("image/"):
                        has_image_attachment = True
                        break
                    filename = att.filename.lower()
                    if filename.endswith((".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp")):
                        has_image_attachment = True
                        break
            if has_image_attachment:
                return
            try:
                await message.delete()
            except discord.Forbidden:
                pass
            except discord.HTTPException:
                pass
            channel = message.channel
            sticky_msg = None
            try:
                sticky_msg = await channel.fetch_message(sticky_info["message_id"])
            except (discord.NotFound, discord.Forbidden):
                sticky_msg = None
            if not sticky_msg:
                new_msg = await channel.send(sticky_info["content"])
                sticky_info["message_id"] = new_msg.id


if __name__ == "__main__":
    if not TOKEN:
        print("Error: Please set your DISCORD_TOKEN in the .env file.")
    else:
        keep_alive()
        try:
            bot.run(TOKEN)
        except discord.LoginFailure as e:
            logger.error(f"Login failed: {e}")
        except Exception as e:
            logger.error(f"Bot crashed with error: {e}", exc_info=True)
