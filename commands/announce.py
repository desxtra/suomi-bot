import discord
from discord import app_commands
from discord.ext import commands
import os

class AnnounceCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name='announce', description='Send a message to all servers (Bot Owner Only)')
    @app_commands.describe(message='The message to send to all servers')
    async def slash_announce(self, interaction: discord.Interaction, message: str):
        """Send announcement to all servers"""
        BOT_OWNER_ID = int(os.getenv('BOT_OWNER_ID'))
        
        if interaction.user.id != BOT_OWNER_ID:
            await interaction.response.send_message("❌ This command is only available for the bot owner.", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)
        
        sent_count = 0
        failed_count = 0
        
        for guild in self.bot.guilds:
            try:
                # Try to find a text channel where we can send messages
                channel = None
                for text_channel in guild.text_channels:
                    if text_channel.permissions_for(guild.me).send_messages:
                        channel = text_channel
                        break
                
                if channel:
                    embed = discord.Embed(
                        title="Bot Announcement",
                        description=message,
                        color=0x00ff00
                    )
                    embed.set_footer(text=f"From {interaction.user.display_name}")
                    await channel.send(embed=embed)
                    sent_count += 1
                else:
                    failed_count += 1
                    
            except Exception as e:
                print(f"Failed to send message to {guild.name}: {e}")
                failed_count += 1
        
        await interaction.followup.send(
            f"✅ Announcement sent!\n"
            f"• Success: {sent_count} servers\n"
            f"• Failed: {failed_count} servers",
            ephemeral=True
        )

async def setup(bot):
    await bot.add_cog(AnnounceCommands(bot))