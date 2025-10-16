# commands/help.py
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

    @app_commands.command(name='help', description='Show bot help and usage information')
    async def slash_help(self, interaction: discord.Interaction):
        """Slash command for help"""
        try:
            embed = discord.Embed(title="Suomi KP-31",
                                description="I love rock music!\nMade with <3 by destraxion",
                                color=0x00ff00)
            embed.add_field(name="Usage",
                            value="Use `/chat <message>` to chat with me!.\n`/reset` - Reset your conversation history",
                            inline=False)
            embed.add_field(
                name="Gunsmoke Commands",
                value=
                "`/gunsmoke` - For gunsmoke frontline management~\nUse `enable` to enable reminder system\n`set_start` <date> set gunsmoke date\n`add_channel` <channel> set reminder channel",
                inline=False)
            embed.add_field(
                name="Music Commands",
                value=
                "`/play` <song> - Play music from YouTube\n`/radio` - Toggle radio mode (automatic related songs)\n`/skip` - Skip current song\n`/stop` - Stop music and clear queue\n`/pause` - Pause music\n`/resume` - Resume music\n`/queue` - Show current queue\n`/volume` <1-100> - Adjust volume\n`/nowplaying` - Show current song\n`/disconnect` - Disconnect bot from voice",
                inline=False)
            embed.add_field(
                name="General Commands",
                value=
                "`/help` - Show this help\n`/sheets` - Get links to important sheets",
                inline=False)
            await interaction.response.send_message(embed=embed)
        except Exception as e:
            logger.error(f"Error in slash_help: {e}")
            try:
                if not interaction.response.is_done():
                    await interaction.response.send_message("Error showing help.", ephemeral=True)
            except:
                pass



    @app_commands.command(name='sheets', description='Get a link to important sheets')
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
                title="Important Sheets",
                description=description,
                color=0x00ff00
            )
            await interaction.response.send_message(embed=embed)
        except Exception as e:
            logger.error(f"Error in slash_sheets: {e}")
            try:
                if not interaction.response.is_done():
                    await interaction.response.send_message("Error retrieving sheets.", ephemeral=True)
            except:
                pass

async def setup(bot):
    await bot.add_cog(HelpCommands(bot))