import discord
from discord import app_commands
from discord.ext import commands
import aiohttp

class EmojiCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name='emoji', description='Create a custom emoji from an image')
    @app_commands.describe(
        name='Name for the emoji',
        image_url='URL of the image (optional if attaching a file)'
    )
    async def slash_emoji(self, interaction: discord.Interaction, name: str, image_url: str = None):
        """Create a custom emoji from an image URL or attachment"""
        # Check if user has Manage Channels permission
        if not interaction.user.guild_permissions.manage_channels:
            await interaction.response.send_message("❌ You need **Manage Channels** permission to create emojis.", ephemeral=True)
            return

        await interaction.response.defer()

        try:
            image_data = None
            
            # Check if there's an attachment in the interaction
            if interaction.data.get('resolved', {}).get('attachments'):
                attachment_id = list(interaction.data['resolved']['attachments'].keys())[0]
                attachment = interaction.data['resolved']['attachments'][attachment_id]
                image_url = attachment['url']
            
            # If no image URL provided and no attachment
            if not image_url:
                await interaction.followup.send("❌ Please provide an image URL or attach an image file.", ephemeral=True)
                return

            # Download the image
            async with aiohttp.ClientSession() as session:
                async with session.get(image_url) as resp:
                    if resp.status == 200:
                        image_data = await resp.read()
                        
                        # Check if it's a valid image by content type
                        content_type = resp.headers.get('Content-Type', '')
                        if not content_type.startswith('image/'):
                            await interaction.followup.send("❌ The provided URL is not an image.", ephemeral=True)
                            return
                        
                        # Create the emoji
                        try:
                            emoji = await interaction.guild.create_custom_emoji(
                                name=name,
                                image=image_data,
                                reason=f"Created by {interaction.user}"
                            )
                            
                            await interaction.followup.send(f"✅ Emoji created: {emoji}")
                            
                        except discord.HTTPException as e:
                            if e.code == 30008:  # Maximum emojis reached
                                await interaction.followup.send("❌ This server has reached the maximum number of emojis.")
                            elif e.code == 50035:  # Invalid emoji name
                                await interaction.followup.send("❌ Invalid emoji name. Use only letters, numbers, and underscores.")
                            else:
                                await interaction.followup.send(f"❌ Failed to create emoji: {e}")
                                
                    else:
                        await interaction.followup.send("❌ Failed to download the image. Please check the URL.")

        except Exception as e:
            await interaction.followup.send(f"❌ An error occurred: {e}")

async def setup(bot):
    await bot.add_cog(EmojiCommands(bot))