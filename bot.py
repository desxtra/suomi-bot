import os
import asyncio
import logging
import discord
from discord import app_commands
from discord.ext import commands, tasks
from PyCharacterAI import Client
from dotenv import load_dotenv
from datetime import datetime, timedelta
import pytz
import json

# Load environment variables
load_dotenv()

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Bot configuration - works without privileged intents using slash commands
intents = discord.Intents.default()
intents.message_content = False  # Set to True if you enable Message Content Intent in Discord portal
bot = commands.Bot(command_prefix='!', intents=intents)

# Character.AI client and chat storage
client = None
user_chats = {}  # Store chat sessions per user to maintain context

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


def get_next_reset_time():
    """Get the next reset time in Jakarta timezone"""
    jakarta_now = datetime.now(JAKARTA_TZ)
    next_reset = jakarta_now.replace(hour=RESET_HOUR,
                                     minute=0,
                                     second=0,
                                     microsecond=0)

    if jakarta_now.hour >= RESET_HOUR:
        next_reset += timedelta(days=1)

    return next_reset


def get_gunsmoke_status(config):
    """Get current gunsmoke status"""
    if not config['enabled'] or not config['current_start']:
        return None, None, None

    start_time = datetime.fromisoformat(
        config['current_start']).replace(tzinfo=JAKARTA_TZ)
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
    current_start_dt = datetime.fromisoformat(current_start).replace(
        tzinfo=JAKARTA_TZ)
    current_end = current_start_dt + timedelta(days=7)
    next_start = current_end + timedelta(days=21)  # 3 weeks later
    return next_start


@bot.event
async def on_ready():
    global client
    print(f'{bot.user} has landed!')

    # Sync slash commands
    try:
        # DON'T clear commands - just sync normally
        synced = await bot.tree.sync()
        print(f'Synced {len(synced)} slash commands')
    except Exception as e:
        print(f'Failed to sync slash commands: {e}')

    # Initialize Character.AI client
    try:
        char_token = os.getenv('CHARACTERAI_TOKEN')
        if char_token:
            client = Client()
            await client.authenticate(char_token)
            print(
                'Character.AI client initialized and authenticated successfully!'
            )
        else:
            print(
                'Warning: No Character.AI token found. Bot will work without AI responses.'
            )
    except Exception as e:
        print(f'Error initializing Character.AI client: {e}')

    # Start gunsmoke reminder task
    gunsmoke_reminder.start()
    print('Gunsmoke Frontline reminder system started!')


@tasks.loop(minutes=1)  # Check every 1 minutes
async def gunsmoke_reminder():
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
            if days_remaining == 7:
                # First day of Gunsmoke
                if config.get('last_notification_sent') != f"{current_date}_day1":
                    await send_gunsmoke_notification(
                        config['notification_channels'],
                        "**First Day of Gunsmoke Frontline!**\n\n"
                        "Everyone, it's time to shine! Let's make today count and score some points!\n"
                        "Remember, Gunsmoke ends 3 hours before reset."
                    )
                    config['last_notification_sent'] = f"{current_date}_day1"
                    save_gunsmoke_config(config)

            elif days_remaining == 6:
                # Second day of Gunsmoke
                if config.get('last_notification_sent') != f"{current_date}_day2":
                    await send_gunsmoke_notification(
                        config['notification_channels'],
                        "**Second Day of Gunsmoke Frontline!**\n\n"
                        "Keep up the great work and aim for even higher scores!\n"
                        "Remember, Gunsmoke ends 3 hours before reset."
                    )
                    config['last_notification_sent'] = f"{current_date}_day2"
                    save_gunsmoke_config(config)

            elif days_remaining == 5:
                # Third day of Gunsmoke
                if config.get('last_notification_sent') != f"{current_date}_day3":
                    await send_gunsmoke_notification(
                        config['notification_channels'],
                        "**Third Day of Gunsmoke Frontline!**\n\n"
                        "Let's push for even better results today!\n"
                        "Remember, Gunsmoke ends 3 hours before reset."
                    )
                    config['last_notification_sent'] = f"{current_date}_day3"
                    save_gunsmoke_config(config)

            elif days_remaining == 4:
                # Fourth day of Gunsmoke
                if config.get('last_notification_sent') != f"{current_date}_day4":
                    await send_gunsmoke_notification(
                        config['notification_channels'],
                        "**Fourth Day of Gunsmoke Frontline!**\n\n"
                        "Let's aim for some great scores today!\n"
                        "Remember, Gunsmoke ends 3 hours before reset."
                    )
                    config['last_notification_sent'] = f"{current_date}_day4"
                    save_gunsmoke_config(config)

            elif days_remaining == 3:
                # Fifth day of Gunsmoke
                if config.get('last_notification_sent') != f"{current_date}_day5":
                    await send_gunsmoke_notification(
                        config['notification_channels'],
                        "**Fifth Day of Gunsmoke Frontline!**\n\n"
                        "Let's make the most of today and aim for some great scores!\n"
                        "Remember, Gunsmoke ends 3 hours before reset."
                    )
                    config['last_notification_sent'] = f"{current_date}_day5"
                    save_gunsmoke_config(config)

            elif days_remaining == 2:
                # Sixth day of Gunsmoke
                if config.get('last_notification_sent') != f"{current_date}_day6":
                    await send_gunsmoke_notification(
                        config['notification_channels'],
                        "**Sixth Day of Gunsmoke Frontline!**\n\n"
                        "Let's make today count and aim for some great scores!\n"
                        "Remember, Gunsmoke ends 3 hours before reset."
                    )
                    config['last_notification_sent'] = f"{current_date}_day6"
                    save_gunsmoke_config(config)

            elif days_remaining == 1:
                # Last day of Gunsmoke
                if config.get('last_notification_sent') != f"{current_date}_lastday":
                    await send_gunsmoke_notification(
                        config['notification_channels'],
                        "**Last Day of Gunsmoke Frontline!**\n\n"
                        "It's the final day! Let's make it count and aim for some great scores!\n"
                        "Remember, Gunsmoke ends 3 hours before reset."
                    )
                    config['last_notification_sent'] = f"{current_date}_lastday"
                    save_gunsmoke_config(config)

            # Check for 3-hour warning (only on last day)
            last_day = end_time.date() == now.date()
            warning_time = end_time - timedelta(hours=3)

            if (last_day and now >= warning_time and now < end_time
                    and config.get('last_notification_sent')
                    != f"{current_date}_warning"):

                await send_gunsmoke_notification(
                    config['notification_channels'],
                    "**Gunsmoke Frontline Warning!**\n\n"
                    "Keep in mind that Gunsmoke ends 3 hours before reset! "
                    "Make sure to finish your runs before the event closes!"
                )

                config['last_notification_sent'] = f"{current_date}_warning"
                save_gunsmoke_config(config)

            # Check for daily reset notification
            reset_time = now.replace(hour=RESET_HOUR,
                                     minute=0,
                                     second=0,
                                     microsecond=0)
            if (abs((now - reset_time).total_seconds()) < 600
                    and  # Within 10 minutes of reset
                    config.get('last_reset_notification') != current_date):

                await send_gunsmoke_notification(
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
            if days_until_start == 2:
                # 2 days before Gunsmoke starts
                if config.get('last_notification_sent') != f"{current_date}_2days":
                    await send_gunsmoke_notification(
                        config['notification_channels'],
                        "**Gunsmoke Frontline is coming in 2 days!**\n\n"
                        "Everyone, get ready to shine! Let's make the most of this event and aim for some great scores!\n"
                    )
                    config['last_notification_sent'] = f"{current_date}_2days"
                    save_gunsmoke_config(config)

            elif days_until_start == 1:
                # 1 day before Gunsmoke starts
                if config.get('last_notification_sent') != f"{current_date}_1day":
                    await send_gunsmoke_notification(
                        config['notification_channels'],
                        "**Gunsmoke Frontline is coming tomorrow!**\n\n"
                        "Everyone, get ready to shine! Let's make the most of this event and aim for some great scores!\n"   
                    )
                    config['last_notification_sent'] = f"{current_date}_1day"
                    save_gunsmoke_config(config)

            elif days_until_start == 0:
                # Day before Gunsmoke starts
                if config.get('last_notification_sent') != f"{current_date}_today":
                    await send_gunsmoke_notification(
                        config['notification_channels'],
                        "**Gunsmoke Frontline is starting today!**\n\n"
                        "Everyone, get ready to shine! Let's make the most of this event and aim for some great scores!\n"
                    )
                    config['last_notification_sent'] = f"{current_date}_today"
                    save_gunsmoke_config(config)

        elif status == "ended":
            # Auto-schedule next gunsmoke
            next_start = calculate_next_gunsmoke_start(config['current_start'])
            config['current_start'] = next_start.isoformat()
            config['last_notification_sent'] = None
            config['last_reset_notification'] = None
            save_gunsmoke_config(config)

            await send_gunsmoke_notification(
                config['notification_channels'],
                f"**Next Gunsmoke Frontline scheduled!**\n\n"
                f"Next event starts: **{next_start.strftime('%Y-%m-%d %H:%M')} (UTC+7) Time**\n"
                f"Get ready Everyone!"
            )

    except Exception as e:
        logger.error(f"Error in gunsmoke reminder task: {e}")


async def send_gunsmoke_notification(channel_ids, message):
    """Send notification to all configured channels"""
    for channel_id in channel_ids:
        try:
            channel = bot.get_channel(int(channel_id))
            if channel:
                await channel.send(message)
        except Exception as e:
            logger.error(
                f"Error sending notification to channel {channel_id}: {e}")


@bot.event
async def on_message(message):
    # Don't respond to the bot's own messages
    if message.author == bot.user:
        return

    # Process commands first
    await bot.process_commands(message)

    # Only respond in DMs (mentions require Message Content Intent in Discord portal)
    if isinstance(message.channel, discord.DMChannel):
        await handle_ai_response(message)


async def handle_ai_response(message):
    """Handle AI response generation"""
    try:
        if not client:
            await message.reply(
                "Character.AI is not configured. Please set up CHARACTERAI_TOKEN and CHARACTER_ID."
            )
            return

        # Get the user's message, clean it up
        user_message = message.content
        if message.content.startswith('!ai'):
            user_message = message.content[3:].strip()
        elif bot.user and bot.user.mentioned_in(message):
            user_message = message.content.replace(f'<@{bot.user.id}>',
                                                   '').strip()
        else:
            user_message = message.content.strip()

        if not user_message:
            await message.reply("Hi! Ask me anything!")
            return

        # Show typing indicator
        async with message.channel.typing():
            # Get character ID from environment
            character_id = os.getenv('CHARACTER_ID')

            if not character_id:
                await message.reply(
                    "Character ID not configured. Please set CHARACTER_ID in your environment variables."
                )
                return

            try:
                if not client:
                    await message.reply(
                        "Character.AI client not available. Please restart the bot."
                    )
                    return

                # Get or create chat session for this user
                user_id = str(message.author.id)

                if user_id not in user_chats:
                    # Create new chat session for this user
                    chat, greeting = await client.chat.create_chat(character_id
                                                                   )
                    user_chats[user_id] = chat.chat_id
                    logger.info(
                        f"Created new chat session for user {user_id}: {chat.chat_id}"
                    )

                chat_id = user_chats[user_id]

                # Send message and get response
                response = await client.chat.send_message(
                    character_id, chat_id, user_message)

                # Get the AI's response text from primary candidate
                primary_candidate = response.get_primary_candidate()
                ai_response = primary_candidate.text if primary_candidate else "Sorry, I can't think anything. I'm confused. TwT"

                # Discord has a 2000 character limit for messages
                if len(ai_response) > 1900:
                    ai_response = ai_response[:1900] + "..."

                await message.reply(ai_response)

            except Exception as api_error:
                logger.error(f"Character.AI API error: {api_error}")
                # Reset user's chat session on error
                user_id = str(message.author.id)
                if user_id in user_chats:
                    del user_chats[user_id]

                # Fallback response when Character.AI fails
                await message.reply(
                    f"I heard you say: '{user_message}'\n\But sorry, I can't think anything. I'll try to fix this... :D"
                )

    except Exception as e:
        logger.error(f"Error generating AI response: {e}")
        await message.reply(
            "Sorry, my brain explode while trying to talk with you. T_T")


@bot.command(name='chat')
async def chat_command(ctx, *, message):
    """Chat with Suomi using a command"""

    # Create a fake message object for consistency
    class FakeMessage:

        def __init__(self, content, channel, author):
            self.content = content
            self.channel = channel
            self.author = author
            # Add missing Discord message attributes
            self.mention_everyone = False
            self.mentions = []
            self.role_mentions = []
            self.channel_mentions = []
            self.attachments = []
            self.embeds = []
            self.reactions = []

        async def reply(self, content):
            await self.channel.send(f"{self.author.mention} {content}")

    fake_message = FakeMessage(message, ctx.channel, ctx.author)
    await handle_ai_response(fake_message)


@bot.command(name='help_bot')
async def help_command(ctx):
    """Show bot help"""
    embed = discord.Embed(title="Suomi KP-31",
                          description="I'm here to help!",
                          color=0x00ff00)
    embed.add_field(name="Usage",
                    value="Use `/chat <message>` to chat with me!.",
                    inline=False)
    embed.add_field(name="Commands",
                    value="`/gunsmoke` - For gunsmoke frontline management~",
                    inline=False)
    embed.add_field(
        name="Commands",
        value=
        "`!help_bot` - Show this help\n`!reset_chat` - Reset your conversation history",
        inline=False)
    await ctx.send(embed=embed)


@bot.command(name='reset_chat')
async def reset_chat_command(ctx):
    """Reset user's chat history with the AI"""
    user_id = str(ctx.author.id)
    if user_id in user_chats:
        del user_chats[user_id]
        await ctx.send("Your conversation history has been reset!")
    else:
        await ctx.send("You don't have an active conversation to reset.")


# Slash Commands (work without privileged intents)
@bot.tree.command(name='chat', description='Chat with the AI character')
async def slash_chat(interaction: discord.Interaction, message: str):
    """Slash command to chat with AI"""
    await interaction.response.defer()

    # Create a mock message object for the AI handler
    class MockMessage:

        def __init__(self, content, channel, author):
            self.content = content
            self.channel = channel
            self.author = author
            # Add missing Discord message attributes
            self.mention_everyone = False
            self.mentions = []
            self.role_mentions = []
            self.channel_mentions = []
            self.attachments = []
            self.embeds = []
            self.reactions = []

        async def reply(self, content):
            await interaction.followup.send(content)

    mock_message = MockMessage(message, interaction.channel, interaction.user)
    await handle_ai_response(mock_message)


@bot.tree.command(name='reset', description='Reset your conversation history')
async def slash_reset(interaction: discord.Interaction):
    """Slash command to reset chat history"""
    user_id = str(interaction.user.id)
    if user_id in user_chats:
        del user_chats[user_id]
        await interaction.response.send_message(
            "Your conversation history has been reset!")
    else:
        await interaction.response.send_message(
            "You don't have an active conversation to reset.")


@bot.tree.command(name='help',
                  description='Show bot help and usage information')
async def slash_help(interaction: discord.Interaction):
    """Slash command for help"""
    embed = discord.Embed(title="Suomi KP-31",
                          description="I'm here to help!",
                          color=0x00ff00)
    embed.add_field(name="Usage",
                    value="Use `/chat <message>` to chat with me!.",
                    inline=False)
    embed.add_field(
        name="Commands",
        value=
        "`/gunsmoke` - For gunsmoke frontline management~\nUse `enable` to enable reminder system\n`set_start` <date> set gunsmoke date\n`add_channel` <channel> set reminder channel",
        inline=False)
    embed.add_field(
        name="Commands",
        value=
        "`/help` - Show this help\n`/reset` - Reset your conversation history",
        inline=False)
    await interaction.response.send_message(embed=embed)


@bot.tree.command(name='sheets', description='Get a link to important sheets')
async def slash_sheets(interaction: discord.Interaction):
    """Slash command to get links to important Google Sheets"""
    sheet1_url = "https://docs.google.com/spreadsheets/d/1-ElgYSa6DscI9FsodU1S3gxLy3Xk7TwrN4IDpnqQfxo/edit?usp=sharing"
    sheet2_url = "https://docs.google.com/spreadsheets/d/1DogyU3K7ZXw2qbhP1EhRXIAw5nCyIV5G5e-QWviBZME/edit?usp=sharing"

    description = (
        f"[Alaris Awesome Support Sheet]({sheet1_url})\n"
        f"[GFL2 Official Release Info Compilation]({sheet2_url})"
    )

    embed = discord.Embed(
        title="Important Sheets",
        description=description,
        color=0x00ff00
    )
    await interaction.response.send_message(embed=embed)


# Gunsmoke Frontline Management Commands
@bot.tree.command(name='gunsmoke',
                  description='Manage Gunsmoke Frontline event system')
@app_commands.describe(
    action='What action to perform',
    start_date=
    'Start date for gunsmoke (YYYY-MM-DD format,UTC+7)',
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
async def slash_gunsmoke(interaction: discord.Interaction,
                         action: str,
                         start_date: str = None,
                         channel: discord.TextChannel = None):
    """Gunsmoke Frontline management command"""

    # Check permissions (only server moderators can manage)
    if not interaction.user.guild_permissions.manage_channels:
        await interaction.response.send_message(
            "Sorry you're not allowed to do that!",
            ephemeral=True)
        return

    config = load_gunsmoke_config()

    if action == 'status':
        status, start_time, end_time = get_gunsmoke_status(config)

        embed = discord.Embed(title="Gunsmoke Frontline Status",
                              color=0x00ff00)
        embed.add_field(
            name="System",
            value="Enabled" if config['enabled'] else "Disabled",
            inline=True)

        if status:
            if status == "active":
                embed.add_field(name="Current Status",
                                value="**ACTIVE**",
                                inline=True)
                embed.add_field(name="Ends",
                                value=end_time.strftime(
                                    '%Y-%m-%d %H:%M (UTC+7)'),
                                inline=True)
            elif status == "upcoming":
                embed.add_field(name="Current Status",
                                value="Upcoming",
                                inline=True)
                embed.add_field(name="Starts",
                                value=start_time.strftime(
                                    '%Y-%m-%d %H:%M (UTC+7)'),
                                inline=True)
            else:
                embed.add_field(name="Current Status",
                                value="Ended",
                                inline=True)
        else:
            embed.add_field(name="Current Status",
                            value="Not Scheduled",
                            inline=True)

        embed.add_field(name="Notification Channels",
                        value=str(len(config['notification_channels'])),
                        inline=True)
        embed.add_field(name="Reset Time",
                        value="16:00 (UTC+7) Time",
                        inline=True)

        await interaction.response.send_message(embed=embed)

    elif action == 'enable':
        config['enabled'] = True
        save_gunsmoke_config(config)
        await interaction.response.send_message(
            "Gunsmoke Frontline system enabled!")

    elif action == 'disable':
        config['enabled'] = False
        save_gunsmoke_config(config)
        await interaction.response.send_message(
            "Gunsmoke Frontline system disabled!")

    elif action == 'set_start':
        if not start_date:
            await interaction.response.send_message(
                "Please provide a start date in YYYY-MM-DD format!")
            return

        try:
            # Parse date and set to reset time in Jakarta timezone
            start_datetime = datetime.strptime(start_date, '%Y-%m-%d')
            start_datetime = start_datetime.replace(hour=RESET_HOUR,
                                                    minute=0,
                                                    second=0)
            start_datetime = JAKARTA_TZ.localize(start_datetime)

            config['current_start'] = start_datetime.isoformat()
            config['last_notification_sent'] = None
            config['last_reset_notification'] = None
            save_gunsmoke_config(config)

            await interaction.response.send_message(
                f"Gunsmoke Frontline start date set to: **{start_datetime.strftime('%Y-%m-%d %H:%M')} (UTC+7)**"
            )
        except ValueError:
            await interaction.response.send_message(
                "Invalid date format! Use YYYY-MM-DD (e.g., 2024-12-25)")

    elif action == 'add_channel':
        if not channel:
            await interaction.response.send_message(
                "Please specify a channel to add!")
            return

        channel_id = str(channel.id)
        if channel_id not in config['notification_channels']:
            config['notification_channels'].append(channel_id)
            save_gunsmoke_config(config)
            await interaction.response.send_message(
                f"Added {channel.mention} to Gunsmoke notifications!")
        else:
            await interaction.response.send_message(
                f"{channel.mention} is already in the notification list!")

    elif action == 'remove_channel':
        if not channel:
            await interaction.response.send_message(
                "Please specify a channel to remove!")
            return

        channel_id = str(channel.id)
        if channel_id in config['notification_channels']:
            config['notification_channels'].remove(channel_id)
            save_gunsmoke_config(config)
            await interaction.response.send_message(
                f"Removed {channel.mention} from Gunsmoke notifications!")
        else:
            await interaction.response.send_message(
                f"{channel.mention} is not in the notification list!")

    elif action == 'list_channels':
        if not config['notification_channels']:
            await interaction.response.send_message(
                "No notification channels configured!")
            return

        channels_list = []
        for channel_id in config['notification_channels']:
            channel_obj = bot.get_channel(int(channel_id))
            if channel_obj:
                channels_list.append(channel_obj.mention)
            else:
                channels_list.append(f"Unknown Channel ({channel_id})")

        embed = discord.Embed(title="Gunsmoke Notification Channels",
                              description="\n".join(channels_list),
                              color=0x00ff00)
        await interaction.response.send_message(embed=embed)


if __name__ == '__main__':
    # Get Discord token
    discord_token = os.getenv('DISCORD_TOKEN')

    if not discord_token:
        print("Error: DISCORD_TOKEN not found in environment variables.")
        print(
            "Please set DISCORD_TOKEN, CHARACTERAI_TOKEN, and CHARACTER_ID in your .env file"
        )
        exit(1)

    # Run the bot
    try:
        bot.run(discord_token)
    except discord.LoginFailure:
        print("Error: Invalid Discord token. Please check your DISCORD_TOKEN.")
    except Exception as e:
        print(f"Error running bot: {e}")