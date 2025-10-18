import discord
from discord import app_commands
from discord.ext import commands
import sqlite3
import asyncio
import datetime
import math
import os
from typing import Optional

# Database setup
DB_PATH = "database/leveling.db"

def init_db():
    """Initialize the database"""
    # Create database directory if it doesn't exist
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Create table if it doesn't exist
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS user_levels (
            user_id INTEGER,
            guild_id INTEGER,
            xp INTEGER DEFAULT 0,
            level INTEGER DEFAULT 1,
            messages INTEGER DEFAULT 0,
            last_message TIMESTAMP,
            PRIMARY KEY (user_id, guild_id)
        )
    ''')
    
    conn.commit()
    conn.close()

class LevelingCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.cooldown = commands.CooldownMapping.from_cooldown(1, 60, commands.BucketType.user)  # 1 XP per minute
        init_db()

    def get_connection(self):
        """Get database connection"""
        return sqlite3.connect(DB_PATH)

    def calculate_level(self, xp):
        """Calculate level based on XP using a progressive formula"""
        # Fixed formula: level = sqrt(xp/100) + 1
        return max(1, int(((xp / 100) ** 0.5) + 1))

    def calculate_xp_for_level(self, level):
        """Calculate XP required for a specific level"""
        # Fixed formula: XP = (level - 1)^2 * 100
        return ((level - 1) ** 2) * 100

    @commands.Cog.listener()
    async def on_message(self, message):
        # Ignore bot messages and DMs
        if message.author.bot or not message.guild:
            return

        # Check cooldown
        bucket = self.cooldown.get_bucket(message)
        retry_after = bucket.update_rate_limit()
        if retry_after:
            return

        try:
            conn = self.get_connection()
            cursor = conn.cursor()

            # Get current user data
            cursor.execute(
                'SELECT xp, level, messages FROM user_levels WHERE user_id = ? AND guild_id = ?',
                (message.author.id, message.guild.id)
            )
            result = cursor.fetchone()

            if result:
                current_xp, current_level, messages = result
                new_xp = current_xp + 15  # Give 15 XP per message
                new_messages = messages + 1
            else:
                # New user
                new_xp = 15
                new_messages = 1
                current_level = 1

            # Calculate new level
            new_level = self.calculate_level(new_xp)

            # Update or insert user data
            if result:
                cursor.execute(
                    '''UPDATE user_levels 
                    SET xp = ?, level = ?, messages = ?, last_message = ? 
                    WHERE user_id = ? AND guild_id = ?''',
                    (new_xp, new_level, new_messages, datetime.datetime.now(), message.author.id, message.guild.id)
                )
            else:
                cursor.execute(
                    '''INSERT INTO user_levels 
                    (user_id, guild_id, xp, level, messages, last_message) 
                    VALUES (?, ?, ?, ?, ?, ?)''',
                    (message.author.id, message.guild.id, new_xp, new_level, new_messages, datetime.datetime.now())
                )

            conn.commit()
            conn.close()

            # Check for level up
            if new_level > current_level:
                await self.handle_level_up(message, message.author, new_level)

        except Exception as e:
            print(f"Error in leveling system: {e}")

    async def handle_level_up(self, message, user, new_level):
        """Handle level up notifications"""
        embed = discord.Embed(
            title="🎉 Level Up!",
            description=f"**{user.display_name}** reached level **{new_level}**!",
            color=0x00ff00
        )
        embed.set_thumbnail(url=user.display_avatar.url)
        
        try:
            await message.channel.send(embed=embed, delete_after=10)
        except discord.Forbidden:
            # Can't send message in this channel, ignore
            pass

    @app_commands.command(name='level', description='Check your level and XP')
    async def slash_level(self, interaction: discord.Interaction, user: Optional[discord.User] = None):
        """Check your level or another user's level"""
        try:
            target_user = user or interaction.user
            
            conn = self.get_connection()
            cursor = conn.cursor()

            cursor.execute(
                'SELECT xp, level, messages FROM user_levels WHERE user_id = ? AND guild_id = ?',
                (target_user.id, interaction.guild.id)
            )
            result = cursor.fetchone()

            if result:
                xp, level, messages = result
                # Fixed XP calculations
                current_level_xp = self.calculate_xp_for_level(level)
                next_level_xp = self.calculate_xp_for_level(level + 1)
                xp_progress = xp - current_level_xp
                xp_needed = next_level_xp - current_level_xp
                
                # Ensure progress is never negative
                if xp_progress < 0:
                    xp_progress = 0
                
                progress_percentage = (xp_progress / xp_needed) * 100 if xp_needed > 0 else 100

                # Create progress bar
                progress_bar_length = 10
                filled_blocks = min(progress_bar_length, int(progress_percentage / 100 * progress_bar_length))
                progress_bar = "█" * filled_blocks + "░" * (progress_bar_length - filled_blocks)

                embed = discord.Embed(
                    title=f"📊 {target_user.display_name}'s Level Stats",
                    color=0x00ff00
                )
                embed.add_field(name="Level", value=f"**{level}**", inline=True)
                embed.add_field(name="Total XP", value=f"**{xp}**", inline=True)
                embed.add_field(name="Messages", value=f"**{messages}**", inline=True)
                embed.add_field(
                    name="Progress to Level {0}".format(level + 1), 
                    value=f"`{progress_bar}` {progress_percentage:.1f}%", 
                    inline=False
                )
                embed.add_field(
                    name="XP Progress", 
                    value=f"**{xp_progress}** / **{xp_needed}** XP", 
                    inline=False
                )
                embed.set_thumbnail(url=target_user.display_avatar.url)

            else:
                embed = discord.Embed(
                    title="📊 Level Info",
                    description=f"**{target_user.display_name}** hasn't started leveling yet! Send some messages to gain XP.",
                    color=0xffff00
                )

            conn.close()
            await interaction.response.send_message(embed=embed)

        except Exception as e:
            await interaction.response.send_message("❌ An error occurred while fetching level information.", ephemeral=True)
            print(f"Error in level command: {e}")

    @app_commands.command(name='leaderboard', description='Show the server leaderboard')
    async def slash_leaderboard(self, interaction: discord.Interaction):
        """Show the top 10 users by level"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()

            cursor.execute(
                '''SELECT user_id, level, xp, messages 
                FROM user_levels 
                WHERE guild_id = ? 
                ORDER BY xp DESC 
                LIMIT 10''',
                (interaction.guild.id,)
            )
            results = cursor.fetchall()

            embed = discord.Embed(
                title="🏆 Server Leaderboard",
                description="Top 10 users by XP",
                color=0xffd700
            )

            if results:
                leaderboard_text = ""
                for i, (user_id, level, xp, messages) in enumerate(results, 1):
                    # Try to get the member from the guild
                    member = interaction.guild.get_member(user_id)
                    if member:
                        # Use global name (unique) instead of display name
                        username = member.global_name or member.name
                        display_text = f"**{username}**"
                    else:
                        # If member not found, try to fetch user info
                        try:
                            user = await self.bot.fetch_user(user_id)
                            username = user.global_name or user.name
                            display_text = f"**{username}** (Left Server)"
                        except:
                            display_text = f"Unknown User ({user_id})"
                    
                    medal = ""
                    if i == 1:
                        medal = "🥇"
                    elif i == 2:
                        medal = "🥈"
                    elif i == 3:
                        medal = "🥉"
                    else:
                        medal = f"`{i}.`"

                    leaderboard_text += f"{medal} {display_text} - Level {level} | {xp} XP\n"

                embed.description = leaderboard_text
            else:
                embed.description = "No users have leveled up yet!"

            conn.close()
            await interaction.response.send_message(embed=embed)

        except Exception as e:
            await interaction.response.send_message("❌ An error occurred while fetching the leaderboard.", ephemeral=True)
            print(f"Error in leaderboard command: {e}")

    @app_commands.command(name='reset_levels', description='Reset leveling data for this server (Admin only)')
    @app_commands.default_permissions(administrator=True)
    async def slash_reset_levels(self, interaction: discord.Interaction):
        """Reset all leveling data for the server"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            cursor.execute(
                'DELETE FROM user_levels WHERE guild_id = ?',
                (interaction.guild.id,)
            )
            
            conn.commit()
            conn.close()
            
            embed = discord.Embed(
                title="🔄 Level Data Reset",
                description="All leveling data for this server has been reset.",
                color=0x00ff00
            )
            await interaction.response.send_message(embed=embed)
            
        except Exception as e:
            await interaction.response.send_message("❌ An error occurred while resetting level data.", ephemeral=True)
            print(f"Error in reset_levels command: {e}")

async def setup(bot):
    await bot.add_cog(LevelingCommands(bot))