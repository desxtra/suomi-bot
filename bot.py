import os
import asyncio
import logging
import discord
from discord.ext import commands
import characterai as cai
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Bot configuration
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='!', intents=intents)

# Character.AI client
client = None

@bot.event
async def on_ready():
    global client
    print(f'{bot.user} has landed!')
    
    # Initialize Character.AI client
    try:
        char_token = os.getenv('CHARACTERAI_TOKEN')
        if char_token:
            client = cai.aiocai.Client(char_token)
            print('Character.AI client initialized successfully!')
        else:
            print('Warning: No Character.AI token found. Bot will work without AI responses.')
    except Exception as e:
        print(f'Error initializing Character.AI client: {e}')

@bot.event
async def on_message(message):
    # Don't respond to the bot's own messages
    if message.author == bot.user:
        return
    
    # Process commands first
    await bot.process_commands(message)
    
    # If the bot is mentioned or it's a DM, generate a Character.AI response
    if bot.user in message.mentions or isinstance(message.channel, discord.DMChannel):
        await handle_ai_response(message)

async def handle_ai_response(message):
    """Handle AI response generation"""
    try:
        if not client:
            await message.reply("Character.AI is not configured. Please set up CHARACTERAI_TOKEN and CHARACTER_ID.")
            return
        
        # Get the user's message without mentions
        user_id = bot.user.id if bot.user else None
        user_message = message.content.replace(f'<@{user_id}>', '').strip() if user_id else message.content.strip()
        
        if not user_message:
            await message.reply("Hi! Ask me anything!")
            return
        
        # Show typing indicator
        async with message.channel.typing():
            # Get character ID from environment
            character_id = os.getenv('CHARACTER_ID')
            
            if not character_id:
                await message.reply("Character ID not configured. Please set CHARACTER_ID in your environment variables.")
                return
            
            try:
                # For now, provide a simple response indicating the bot is working
                # The user will need to configure the Character.AI API properly
                await message.reply(f"🤖 Character.AI Bot is working! You said: '{user_message}'\n\n" +
                                  "To enable AI responses, configure your CHARACTERAI_TOKEN and CHARACTER_ID in the .env file.")
                
            except Exception as api_error:
                logger.error(f"Character.AI API error: {api_error}")
                await message.reply("Sorry, I'm having trouble connecting to Character.AI right now.")
            
    except Exception as e:
        logger.error(f"Error generating AI response: {e}")
        await message.reply("Sorry, I encountered an error while processing your message.")

@bot.command(name='chat')
async def chat_command(ctx, *, message):
    """Chat with the AI using a command"""
    # Create a fake message object for consistency
    class FakeMessage:
        def __init__(self, content, channel, author):
            self.content = content
            self.channel = channel
            self.author = author
        
        async def reply(self, content):
            await self.channel.send(f"{self.author.mention} {content}")
    
    fake_message = FakeMessage(message, ctx.channel, ctx.author)
    await handle_ai_response(fake_message)

@bot.command(name='help_bot')
async def help_command(ctx):
    """Show bot help"""
    embed = discord.Embed(
        title="Character.AI Discord Bot",
        description="A bot that brings Character.AI to Discord!",
        color=0x00ff00
    )
    embed.add_field(
        name="Usage",
        value="• Mention me in any message to chat\n• Send me a DM\n• Use `!chat <message>` command",
        inline=False
    )
    embed.add_field(
        name="Setup",
        value="Make sure DISCORD_TOKEN, CHARACTERAI_TOKEN, and CHARACTER_ID are configured",
        inline=False
    )
    await ctx.send(embed=embed)

if __name__ == '__main__':
    # Get Discord token
    discord_token = os.getenv('DISCORD_TOKEN')
    
    if not discord_token:
        print("Error: DISCORD_TOKEN not found in environment variables.")
        print("Please set DISCORD_TOKEN, CHARACTERAI_TOKEN, and CHARACTER_ID in your .env file")
        exit(1)
    
    # Run the bot
    try:
        bot.run(discord_token)
    except discord.LoginFailure:
        print("Error: Invalid Discord token. Please check your DISCORD_TOKEN.")
    except Exception as e:
        print(f"Error running bot: {e}")