# commands/ai_chat.py
import os
import asyncio
import logging
import discord
from discord import app_commands
from discord.ext import commands
from PyCharacterAI import Client

logger = logging.getLogger(__name__)

# Character.AI client and chat storage
client = None
user_chats = {}

class AIChatCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self._initialize_character_ai()

    def _initialize_character_ai(self):
        """Initialize Character.AI client"""
        global client
        try:
            char_token = os.getenv('CHARACTERAI_TOKEN')
            if char_token:
                client = Client()
                asyncio.create_task(self._authenticate_character_ai())
            else:
                logger.warning('No Character.AI token found. Bot will work without AI responses.')
        except Exception as e:
            logger.error(f'Error initializing Character.AI client: {e}')

    async def _authenticate_character_ai(self):
        """Authenticate with Character.AI"""
        global client
        try:
            await client.authenticate(os.getenv('CHARACTERAI_TOKEN'))
            logger.info('Character.AI client initialized and authenticated successfully!')
        except Exception as e:
            logger.error(f'Error authenticating Character.AI client: {e}')

    async def handle_ai_response(self, message):
        """Handle AI response generation"""
        global client
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
            elif self.bot.user and self.bot.user.mentioned_in(message):
                user_message = message.content.replace(f'<@{self.bot.user.id}>', '').strip()
            else:
                user_message = message.content.strip()

            if not user_message:
                await message.reply("Hi! Ask me anything!")
                return

            # Show typing indicator
            async with message.channel.typing():
                character_id = os.getenv('CHARACTER_ID')
                if not character_id:
                    await message.reply("Character ID not configured. Please set CHARACTER_ID in your environment variables.")
                    return

                try:
                    if not client:
                        await message.reply("Character.AI client not available. Please restart the bot.")
                        return

                    # Get or create chat session for this user
                    user_id = str(message.author.id)
                    if user_id not in user_chats:
                        chat, greeting = await client.chat.create_chat(character_id)
                        user_chats[user_id] = chat.chat_id
                        logger.info(f"Created new chat session for user {user_id}: {chat.chat_id}")

                    chat_id = user_chats[user_id]

                    # Send message and get response
                    response = await client.chat.send_message(character_id, chat_id, user_message)

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
                        f"I heard you say: '{user_message}'\nBut sorry, I can't think anything. I'll try to fix this... :D"
                    )

        except Exception as e:
            logger.error(f"Error generating AI response: {e}")
            await message.reply("Sorry, my brain explode while trying to talk with you. T_T")

    @commands.command(name='chat')
    async def chat_command(self, ctx, *, message):
        """Chat with Suomi using a command"""
        class FakeMessage:
            def __init__(self, content, channel, author):
                self.content = content
                self.channel = channel
                self.author = author
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
        await self.handle_ai_response(fake_message)

    @commands.command(name='reset_chat')
    async def reset_chat_command(self, ctx):
        """Reset user's chat history with the AI"""
        user_id = str(ctx.author.id)
        if user_id in user_chats:
            del user_chats[user_id]
            await ctx.send("Your conversation history has been reset!")
        else:
            await ctx.send("You don't have an active conversation to reset.")

    @app_commands.command(name='chat', description='Chat with the AI character')
    async def slash_chat(self, interaction: discord.Interaction, message: str):
        """Slash command to chat with AI"""
        global client
        try:
            await interaction.response.defer(thinking=True)
            
            if not client:
                await interaction.followup.send("Character.AI is not configured. Please set up CHARACTERAI_TOKEN and CHARACTER_ID.")
                return

            character_id = os.getenv('CHARACTER_ID')
            if not character_id:
                await interaction.followup.send("Character ID not configured. Please set CHARACTER_ID in your environment variables.")
                return

            user_id = str(interaction.user.id)
            
            try:
                if user_id not in user_chats:
                    chat, greeting = await client.chat.create_chat(character_id)
                    user_chats[user_id] = chat.chat_id
                    logger.info(f"Created new chat session for user {user_id}: {chat.chat_id}")

                chat_id = user_chats[user_id]

                try:
                    response = await asyncio.wait_for(
                        client.chat.send_message(character_id, chat_id, message),
                        timeout=30.0
                    )
                    
                    primary_candidate = response.get_primary_candidate()
                    ai_response = primary_candidate.text if primary_candidate else "Sorry, I can't think anything. I'm confused. TwT"

                    if len(ai_response) > 1900:
                        ai_response = ai_response[:1900] + "..."

                    await interaction.followup.send(ai_response)
                    
                except asyncio.TimeoutError:
                    await interaction.followup.send("Sorry, the AI is taking too long to respond. Please try again later.")
                    
            except Exception as api_error:
                logger.error(f"Character.AI API error: {api_error}")
                if user_id in user_chats:
                    del user_chats[user_id]
                await interaction.followup.send("Sorry, I encountered an error while processing your message. Please try again.")

        except Exception as e:
            logger.error(f"Error in slash_chat: {e}")
            try:
                if interaction.response.is_done():
                    await interaction.followup.send("Sorry, something went wrong. Please try again.")
                else:
                    await interaction.response.send_message("Sorry, something went wrong. Please try again.")
            except:
                pass

    @app_commands.command(name='reset', description='Reset your conversation history')
    async def slash_reset(self, interaction: discord.Interaction):
        """Slash command to reset chat history"""
        try:
            await interaction.response.defer(ephemeral=True)
            user_id = str(interaction.user.id)
            if user_id in user_chats:
                del user_chats[user_id]
                await interaction.followup.send("Your conversation history has been reset!")
            else:
                await interaction.followup.send("You don't have an active conversation to reset.")
        except Exception as e:
            logger.error(f"Error in slash_reset: {e}")
            try:
                if interaction.response.is_done():
                    await interaction.followup.send("Error resetting chat history.", ephemeral=True)
                else:
                    await interaction.response.send_message("Error resetting chat history.", ephemeral=True)
            except:
                pass

async def setup(bot):
    await bot.add_cog(AIChatCommands(bot))