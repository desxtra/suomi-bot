import logging
import discord
from discord import app_commands
from discord.ext import commands

logger = logging.getLogger(__name__)

class HelpCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name='help_bot')
    async def help_command(self, ctx):
        """Show bot help"""
        embed = discord.Embed(title="Suomi KP-31 Help",
                            description="Available commands and usage",
                            color=0x00ff00)
        embed.add_field(name="Chat Commands",
                        value="`/chat <message>` - Chat with the AI\n`/reset` - Reset conversation history",
                        inline=False)
        embed.add_field(name="Gunsmoke Commands",
                        value="`/gunsmoke` - Frontline management system",
                        inline=False)
        embed.add_field(name="Music Commands",
                        value="`/play`, `/skip`, `/stop`, `/queue`, `/volume`",
                        inline=False)
        await ctx.send(embed=embed)

    @app_commands.command(name='help', description='Show bot help and usage information')
    async def slash_help(self, interaction: discord.Interaction):
        """Slash command for help"""
        try:
            embed = discord.Embed(title="Suomi KP-31 Help",
                                description="Available commands and usage information\nMade with ❤️ by destraxion",
                                color=0x00ff00)
            
            embed.add_field(name="Chat Commands",
                          value="• `/chat <message>` - Chat with the AI\n• `/reset` - Reset your conversation history",
                          inline=False)
            
            embed.add_field(name="Gunsmoke Commands",
                          value="• `/gunsmoke` - Frontline management system\n• Use `enable` to enable reminders\n• Use `set_start <date>` to set event date\n• Use `add_channel <channel>` to set reminder channel",
                          inline=False)
            
            embed.add_field(name="Music Commands",
                          value="• `/play <song>` - Play music from YouTube\n• `/radio` - Toggle automatic related songs\n• `/skip` - Skip current song\n• `/stop` - Stop music and clear queue\n• `/pause` / `/resume` - Control playback\n• `/queue` - Show current queue\n• `/remove` - Remove spesific song2 in queue\n• `/volume <1-100>` - Adjust volume\n• `/nowplaying` - Show current song\n• `/disconnect` - Disconnect from voice",
                          inline=False)
            
            embed.add_field(name="Utility Commands",
                          value="• `/emoji <name> <image>` - Create custom emoji\n• `/sheets` - Get important document links",
                          inline=False)
            
            embed.add_field(name="General",
                          value="• `/help` - Show this help message",
                          inline=False)
            
            await interaction.response.send_message(embed=embed)
        except Exception as e:
            logger.error(f"Error in slash_help: {e}")
            try:
                if not interaction.response.is_done():
                    await interaction.response.send_message("Error showing help.", ephemeral=True)
            except:
                pass

    @app_commands.command(name='sheets', description='Get links to important documents')
    async def slash_sheets(self, interaction: discord.Interaction):
        """Slash command to get links to important Google Sheets"""
        try:
            sheet1_url = "https://docs.google.com/spreadsheets/d/1-ElgYSa6DscI9FsodU1S3gxLy3Xk7TwrN4IDpnqQfxo/edit?usp=sharing"
            sheet2_url = "https://docs.google.com/spreadsheets/d/1DogyU3K7ZXw2qbhP1EhRXIAw5nCyIV5G5e-QWviBZME/edit?usp=sharing"

            description = (
                f"[Alaris Awesome Support Sheet]({sheet1_url})\n"
                f"[GFL2 Official Release Info Compilation]({sheet2_url})"
            )

            embed = discord.Embed(
                title="Important Documents",
                description=description,
                color=0x00ff00
            )
            await interaction.response.send_message(embed=embed)
        except Exception as e:
            logger.error(f"Error in slash_sheets: {e}")
            try:
                if not interaction.response.is_done():
                    await interaction.response.send_message("Error retrieving documents.", ephemeral=True)
            except:
                pass

async def setup(bot):
    await bot.add_cog(HelpCommands(bot))