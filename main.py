# main.py
import os
import logging
import discord
from discord.ext import commands
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Bot configuration
intents = discord.Intents.default()
intents.message_content = True
intents.voice_states = True  # Required for music functionality
bot = commands.Bot(command_prefix='!', intents=intents)

# Load command modules
async def load_commands():
    """Load all command modules"""
    commands_dir = "commands"
    for filename in os.listdir(commands_dir):
        if filename.endswith('.py') and filename != '__init__.py':
            module_name = f"{commands_dir}.{filename[:-3]}"
            try:
                await bot.load_extension(module_name)
                logger.info(f"Loaded module: {module_name}")
            except Exception as e:
                logger.error(f"Failed to load module {module_name}: {e}")

@bot.event
async def on_ready():
    print(f'{bot.user} has landed!')

    # Load command modules first
    await load_commands()

    # Sync slash commands globally
    try:
        print("🔄 Syncing slash commands...")
        synced = await bot.tree.sync()
        print(f'✅ Successfully synced {len(synced)} slash commands globally')
        
        # List all synced commands for verification
        if synced:
            command_names = [cmd.name for cmd in synced]
            print(f'📋 Available commands: {", ".join(sorted(command_names))}')
        else:
            print('⚠️  No commands were synced. Check if your cogs are loading properly.')
        
    except Exception as e:
        print(f'❌ Failed to sync slash commands: {e}')
        # Try to get more detailed error information
        import traceback
        traceback.print_exc()

    print('🤖 Bot is ready!')

@bot.event
async def on_guild_join(guild):
    """Automatically sync commands when bot joins a new server"""
    try:
        await bot.tree.sync(guild=guild)
        print(f"✅ Synced commands with new guild: {guild.name} (ID: {guild.id})")
    except Exception as e:
        print(f"❌ Failed to sync with new guild {guild.name}: {e}")

@bot.event
async def on_error(event, *args, **kwargs):
    logger.error(f"Unhandled error in event {event}: {args} {kwargs}")

@bot.tree.error
async def on_app_command_error(interaction: discord.Interaction, error: discord.app_commands.AppCommandError):
    logger.error(f"Slash command error: {error}")
    try:
        if not interaction.response.is_done():
            await interaction.response.send_message("An error occurred while processing your command.", ephemeral=True)
        else:
            await interaction.followup.send("An error occurred while processing your command.", ephemeral=True)
    except Exception as e:
        logger.error(f"Error sending error message: {e}")

# Update the on_message to handle AI chat in DMs
@bot.event
async def on_message(message):
    # Don't respond to the bot's own messages
    if message.author == bot.user:
        return

    # Process commands first
    await bot.process_commands(message)

    # Only respond in DMs (mentions require Message Content Intent in Discord portal)
    if isinstance(message.channel, discord.DMChannel):
        # Get the AI chat cog and handle the response
        ai_cog = bot.get_cog('AIChatCommands')
        if ai_cog:
            await ai_cog.handle_ai_response(message)

if __name__ == '__main__':
    discord_token = os.getenv('DISCORD_TOKEN')
    if not discord_token:
        print("❌ Error: DISCORD_TOKEN not found in environment variables.")
        exit(1)

    try:
        print("🚀 Starting bot...")
        bot.run(discord_token)
    except discord.LoginFailure:
        print("❌ Error: Invalid Discord token. Please check your DISCORD_TOKEN.")
    except Exception as e:
        print(f"❌ Error running bot: {e}")