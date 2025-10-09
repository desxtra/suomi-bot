# commands/gunsmoke.py
import os
import json
import logging
import discord
from discord import app_commands
from discord.ext import commands, tasks
from datetime import datetime, timedelta
import pytz

logger = logging.getLogger(__name__)

# Gunsmoke Frontline configuration
GUNSMOKE_CONFIG_FILE = 'gunsmoke_config.json'
JAKARTA_TZ = pytz.timezone('Asia/Jakarta')
RESET_HOUR = 16  # 4 PM in Jakarta time

# Default configuration
default_gunsmoke_config = {
    'enabled': False,
    'current_start': None,
    'notification_channels': [],
    'last_notification_sent': None,
    'last_reset_notification': None
}

def load_gunsmoke_config():
    """Load gunsmoke configuration from file"""
    try:
        if os.path.exists(GUNSMOKE_CONFIG_FILE):
            with open(GUNSMOKE_CONFIG_FILE, 'r') as f:
                return json.load(f)
        else:
            return default_gunsmoke_config.copy()
    except Exception as e:
        logger.error(f"Error loading gunsmoke config: {e}")
        return default_gunsmoke_config.copy()

def save_gunsmoke_config(config):
    """Save gunsmoke configuration to file"""
    try:
        with open(GUNSMOKE_CONFIG_FILE, 'w') as f:
            json.dump(config, f, indent=2, default=str)
    except Exception as e:
        logger.error(f"Error saving gunsmoke config: {e}")

def get_gunsmoke_status(config):
    """Get current gunsmoke status"""
    if not config['enabled'] or not config['current_start']:
        return None, None, None

    start_time = datetime.fromisoformat(config['current_start']).replace(tzinfo=JAKARTA_TZ)
    end_time = start_time + timedelta(days=7)  # Gunsmoke lasts 1 week
    now = datetime.now(JAKARTA_TZ)

    if now < start_time:
        return "upcoming", start_time, end_time
    elif now < end_time:
        return "active", start_time, end_time
    else:
        return "ended", start_time, end_time

def calculate_next_gunsmoke_start(current_start):
    """Calculate next gunsmoke start time (3 weeks after current ends)"""
    current_start_dt = datetime.fromisoformat(current_start).replace(tzinfo=JAKARTA_TZ)
    current_end = current_start_dt + timedelta(days=7)
    next_start = current_end + timedelta(days=21)  # 3 weeks later
    return next_start

async def send_gunsmoke_notification(bot, channel_ids, message):
    """Send notification to all configured channels"""
    for channel_id in channel_ids:
        try:
            channel = bot.get_channel(int(channel_id))
            if channel:
                await channel.send(message)
        except Exception as e:
            logger.error(f"Error sending notification to channel {channel_id}: {e}")

class GunsmokeCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.gunsmoke_reminder.start()

    def cog_unload(self):
        self.gunsmoke_reminder.cancel()

    @tasks.loop(minutes=1)
    async def gunsmoke_reminder(self):
        """Background task to check for gunsmoke reminders"""
        try:
            config = load_gunsmoke_config()

            if not config['enabled'] or not config['notification_channels']:
                return

            now = datetime.now(JAKARTA_TZ)
            current_date = now.strftime('%Y-%m-%d')
            status, start_time, end_time = get_gunsmoke_status(config)

            if status == "active":
                # Calculate days remaining
                days_remaining = (end_time - now).days + 1

                # Check for different reminder messages based on days remaining
                day_messages = {
                    7: ("First Day of Gunsmoke Frontline!",
                        "Everyone, it's time to shine! Let's make today count and score some points!\nRemember, Gunsmoke ends 3 hours before reset."),
                    6: ("Second Day of Gunsmoke Frontline!",
                        "Keep up the great work and aim for even higher scores!\nRemember, Gunsmoke ends 3 hours before reset."),
                    5: ("Third Day of Gunsmoke Frontline!",
                        "Let's push for even better results today!\nRemember, Gunsmoke ends 3 hours before reset."),
                    4: ("Fourth Day of Gunsmoke Frontline!",
                        "Let's aim for some great scores today!\nRemember, Gunsmoke ends 3 hours before reset."),
                    3: ("Fifth Day of Gunsmoke Frontline!",
                        "Let's make the most of today and aim for some great scores!\nRemember, Gunsmoke ends 3 hours before reset."),
                    2: ("Sixth Day of Gunsmoke Frontline!",
                        "Let's make today count and aim for some great scores!\nRemember, Gunsmoke ends 3 hours before reset."),
                    1: ("Last Day of Gunsmoke Frontline!",
                        "It's the final day! Let's make it count and aim for some great scores!\nRemember, Gunsmoke ends 3 hours before reset.")
                }

                if days_remaining in day_messages:
                    day_key = f"{current_date}_day{days_remaining}" if days_remaining > 1 else f"{current_date}_lastday"
                    if config.get('last_notification_sent') != day_key:
                        title, message_text = day_messages[days_remaining]
                        await send_gunsmoke_notification(
                            self.bot,
                            config['notification_channels'],
                            f"**{title}**\n\n{message_text}"
                        )
                        config['last_notification_sent'] = day_key
                        save_gunsmoke_config(config)

                # Check for 3-hour warning (only on last day)
                last_day = end_time.date() == now.date()
                warning_time = end_time - timedelta(hours=3)

                if (last_day and now >= warning_time and now < end_time
                        and config.get('last_notification_sent') != f"{current_date}_warning"):

                    await send_gunsmoke_notification(
                        self.bot,
                        config['notification_channels'],
                        "**Gunsmoke Frontline Warning!**\n\n"
                        "Keep in mind that Gunsmoke ends 3 hours before reset! "
                        "Make sure to finish your runs before the event closes!"
                    )

                    config['last_notification_sent'] = f"{current_date}_warning"
                    save_gunsmoke_config(config)

                # Check for daily reset notification
                reset_time = now.replace(hour=RESET_HOUR, minute=0, second=0, microsecond=0)
                if (abs((now - reset_time).total_seconds()) < 600
                        and config.get('last_reset_notification') != current_date):

                    await send_gunsmoke_notification(
                        self.bot,
                        config['notification_channels'],
                        "**Gunsmoke is Reset. Good Work everyone! :D**\n\n"
                        "Let's do our best for today too! Time to score some points!"
                    )

                    config['last_reset_notification'] = current_date
                    save_gunsmoke_config(config)

            elif status == "upcoming":
                # Calculate days until Gunsmoke starts
                days_until_start = (start_time - now).days

                # Check for different reminder messages based on days until start
                upcoming_messages = {
                    2: ("Gunsmoke Frontline is coming in 2 days!",
                        "Everyone, get ready to shine! Let's make the most of this event and aim for some great scores!"),
                    1: ("Gunsmoke Frontline is coming tomorrow!",
                        "Everyone, get ready to shine! Let's make the most of this event and aim for some great scores!"),
                    0: ("Gunsmoke Frontline is starting today!",
                        "Everyone, get ready to shine! Let's make the most of this event and aim for some great scores!")
                }

                if days_until_start in upcoming_messages:
                    day_key = f"{current_date}_{days_until_start}days" if days_until_start == 2 else \
                             f"{current_date}_{days_until_start}day" if days_until_start == 1 else \
                             f"{current_date}_today"
                    
                    if config.get('last_notification_sent') != day_key:
                        title, message_text = upcoming_messages[days_until_start]
                        await send_gunsmoke_notification(
                            self.bot,
                            config['notification_channels'],
                            f"**{title}**\n\n{message_text}"
                        )
                        config['last_notification_sent'] = day_key
                        save_gunsmoke_config(config)

            elif status == "ended":
                # Auto-schedule next gunsmoke
                next_start = calculate_next_gunsmoke_start(config['current_start'])
                config['current_start'] = next_start.isoformat()
                config['last_notification_sent'] = None
                config['last_reset_notification'] = None
                save_gunsmoke_config(config)

                await send_gunsmoke_notification(
                    self.bot,
                    config['notification_channels'],
                    f"**Next Gunsmoke Frontline scheduled!**\n\n"
                    f"Next event starts: **{next_start.strftime('%Y-%m-%d %H:%M')} (UTC+7) Time**\n"
                    f"Get ready Everyone!"
                )

        except Exception as e:
            logger.error(f"Error in gunsmoke reminder task: {e}")

    @app_commands.command(name='gunsmoke', description='Manage Gunsmoke Frontline event system')
    @app_commands.describe(
        action='What action to perform',
        start_date='Start date for gunsmoke (YYYY-MM-DD format, UTC+7)',
        channel='Channel to add/remove for notifications')
    @app_commands.choices(action=[
        app_commands.Choice(name='status', value='status'),
        app_commands.Choice(name='enable', value='enable'),
        app_commands.Choice(name='disable', value='disable'),
        app_commands.Choice(name='set_start', value='set_start'),
        app_commands.Choice(name='add_channel', value='add_channel'),
        app_commands.Choice(name='remove_channel', value='remove_channel'),
        app_commands.Choice(name='list_channels', value='list_channels'),
    ])
    async def slash_gunsmoke(self, interaction: discord.Interaction,
                            action: str,
                            start_date: str = None,
                            channel: discord.TextChannel = None):
        """Gunsmoke Frontline management command"""
        try:
            await interaction.response.defer(ephemeral=True)
            
            if not interaction.user.guild_permissions.manage_channels:
                await interaction.followup.send("Sorry you're not allowed to do that!")
                return

            config = load_gunsmoke_config()

            if action == 'status':
                status, start_time, end_time = get_gunsmoke_status(config)

                embed = discord.Embed(title="Gunsmoke Frontline Status", color=0x00ff00)
                embed.add_field(name="System", value="Enabled" if config['enabled'] else "Disabled", inline=True)

                if status:
                    if status == "active":
                        embed.add_field(name="Current Status", value="**ACTIVE**", inline=True)
                        days_remaining = (end_time - datetime.now(JAKARTA_TZ)).days + 1
                        embed.add_field(name="Days Remaining", value=str(days_remaining), inline=True)
                        embed.add_field(name="Ends", value=end_time.strftime('%Y-%m-%d %H:%M (UTC+7)'), inline=False)
                    elif status == "upcoming":
                        embed.add_field(name="Current Status", value="Upcoming", inline=True)
                        days_until = (start_time - datetime.now(JAKARTA_TZ)).days
                        embed.add_field(name="Days Until Start", value=str(days_until), inline=True)
                        embed.add_field(name="Starts", value=start_time.strftime('%Y-%m-%d %H:%M (UTC+7)'), inline=False)
                    else:
                        embed.add_field(name="Current Status", value="Ended", inline=True)
                        next_start = calculate_next_gunsmoke_start(config['current_start'])
                        embed.add_field(name="Next Starts", value=next_start.strftime('%Y-%m-%d %H:%M (UTC+7)'), inline=False)
                else:
                    embed.add_field(name="Current Status", value="Not Scheduled", inline=True)

                embed.add_field(name="Notification Channels", value=str(len(config['notification_channels'])), inline=True)
                embed.add_field(name="Reset Time", value="16:00 (UTC+7) Time", inline=True)

                await interaction.followup.send(embed=embed)

            elif action == 'enable':
                config['enabled'] = True
                save_gunsmoke_config(config)
                await interaction.followup.send("Gunsmoke Frontline system enabled!")

            elif action == 'disable':
                config['enabled'] = False
                save_gunsmoke_config(config)
                await interaction.followup.send("Gunsmoke Frontline system disabled!")

            elif action == 'set_start':
                if not start_date:
                    await interaction.followup.send("Please provide a start date in YYYY-MM-DD format!")
                    return

                try:
                    start_datetime = datetime.strptime(start_date, '%Y-%m-%d')
                    start_datetime = start_datetime.replace(hour=RESET_HOUR, minute=0, second=0)
                    start_datetime = JAKARTA_TZ.localize(start_datetime)

                    config['current_start'] = start_datetime.isoformat()
                    config['last_notification_sent'] = None
                    config['last_reset_notification'] = None
                    save_gunsmoke_config(config)

                    await interaction.followup.send(
                        f"Gunsmoke Frontline start date set to: **{start_datetime.strftime('%Y-%m-%d %H:%M')} (UTC+7)**"
                    )
                except ValueError:
                    await interaction.followup.send("Invalid date format! Use YYYY-MM-DD (e.g., 2024-12-25)")

            elif action == 'add_channel':
                if not channel:
                    await interaction.followup.send("Please specify a channel to add!")
                    return

                channel_id = str(channel.id)
                if channel_id not in config['notification_channels']:
                    config['notification_channels'].append(channel_id)
                    save_gunsmoke_config(config)
                    await interaction.followup.send(f"Added {channel.mention} to Gunsmoke notifications!")
                else:
                    await interaction.followup.send(f"{channel.mention} is already in the notification list!")

            elif action == 'remove_channel':
                if not channel:
                    await interaction.followup.send("Please specify a channel to remove!")
                    return

                channel_id = str(channel.id)
                if channel_id in config['notification_channels']:
                    config['notification_channels'].remove(channel_id)
                    save_gunsmoke_config(config)
                    await interaction.followup.send(f"Removed {channel.mention} from Gunsmoke notifications!")
                else:
                    await interaction.followup.send(f"{channel.mention} is not in the notification list!")

            elif action == 'list_channels':
                if not config['notification_channels']:
                    await interaction.followup.send("No notification channels configured!")
                    return

                channels_list = []
                for channel_id in config['notification_channels']:
                    channel_obj = self.bot.get_channel(int(channel_id))
                    if channel_obj:
                        channels_list.append(channel_obj.mention)
                    else:
                        channels_list.append(f"Unknown Channel ({channel_id})")

                embed = discord.Embed(title="Gunsmoke Notification Channels",
                                    description="\n".join(channels_list),
                                    color=0x00ff00)
                await interaction.followup.send(embed=embed)

        except Exception as e:
            logger.error(f"Error in slash_gunsmoke: {e}")
            try:
                await interaction.followup.send("An error occurred while processing the gunsmoke command.", ephemeral=True)
            except:
                pass

async def setup(bot):
    await bot.add_cog(GunsmokeCommands(bot))