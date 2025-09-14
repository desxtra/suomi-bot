import os
import asyncio
import logging
import discord
from discord import app_commands
from discord.ext import commands
from PyCharacterAI import Client
from dotenv import load_dotenv

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


@bot.event
async def on_ready():
    global client
    print(f'{bot.user} has landed!')

    # Sync slash commands
    try:
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
                    chat, greeting = await client.chat.create_chat(character_id)
                    user_chats[user_id] = chat.chat_id
                    logger.info(f"Created new chat session for user {user_id}: {chat.chat_id}")

                chat_id = user_chats[user_id]

                # Send message and get response
                response = await client.chat.send_message(character_id, chat_id, user_message)

                # Get the AI's response text from primary candidate
                primary_candidate = response.get_primary_candidate()
                ai_response = primary_candidate.text if primary_candidate else "Sorry, I didn't get a response."

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
                    f"🤖 I heard you say: '{user_message}'\n\nSorry, I'm having trouble connecting to Character.AI right now. I'll try to reset our conversation."
                )

    except Exception as e:
        logger.error(f"Error generating AI response: {e}")
        await message.reply(
            "Sorry, I encountered an error while processing your message.")


@bot.command(name='chat')
async def chat_command(ctx, *, message):
    """Chat with the AI using a command"""

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
    embed = discord.Embed(
        title="Character.AI Discord Bot",
        description="A bot that brings Character.AI to Discord!",
        color=0x00ff00)
    embed.add_field(
        name="Usage",
        value=
        "• Mention me in any message to chat\n• Send me a DM\n• Use `!chat <message>` command\n• Use `!ai <message>` command",
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
        await ctx.send("✅ Your conversation history has been reset!")
    else:
        await ctx.send("ℹ️ You don't have an active conversation to reset.")


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
            "✅ Your conversation history has been reset!")
    else:
        await interaction.response.send_message(
            "ℹ️ You don't have an active conversation to reset.")


@bot.tree.command(name='help',
                  description='Show bot help and usage information')
async def slash_help(interaction: discord.Interaction):
    """Slash command for help"""
    embed = discord.Embed(
        title="Character.AI Discord Bot",
        description="A bot that brings Character.AI to Discord!",
        color=0x00ff00)
    embed.add_field(
        name="Slash Commands",
        value=
        "`/chat <message>` - Chat with the AI\n`/reset` - Reset conversation history\n`/help` - Show this help",
        inline=False)
    embed.add_field(
        name="Other Ways to Chat",
        value=
        "• Send me a direct message\n• Use prefix commands: `!chat <message>`",
        inline=False)
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
