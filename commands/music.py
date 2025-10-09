# commands/music.py
import asyncio
import logging
import discord
from discord import app_commands
from discord.ext import commands
import yt_dlp
import urllib.parse

logger = logging.getLogger(__name__)

# YouTube DL options for audio only with better YouTube Music support
ytdl_format_options = {
    'format': 'bestaudio/best',
    'outtmpl': '%(extractor)s-%(id)s-%(title)s.%(ext)s',
    'restrictfilenames': True,
    'noplaylist': True,
    'nocheckcertificate': True,
    'ignoreerrors': False,
    'logtostderr': False,
    'quiet': True,
    'no_warnings': True,
    'default_search': 'ytsearch',
    'source_address': '0.0.0.0',
    'extractaudio': True,
    'audioformat': 'mp3',
    'extract_flat': False,
    'youtube_include_dash_manifest': False,
}

ffmpeg_options = {
    'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5 -probesize 10M',
    'options': '-vn -bufsize 512k'
}

ytdl = yt_dlp.YoutubeDL(ytdl_format_options)

class YTDLSource(discord.PCMVolumeTransformer):
    def __init__(self, source, *, data, volume=0.5):
        super().__init__(source, volume)
        self.data = data
        self.title = data.get('title')
        self.url = data.get('url')
        self.duration = self.parse_duration(data.get('duration'))
        self.thumbnail = data.get('thumbnail')
        self.uploader = data.get('uploader')

    @classmethod
    async def from_url(cls, url, *, loop=None, stream=False):
        loop = loop or asyncio.get_event_loop()
        
        # Clean the URL/search query
        if not url.startswith(('http', 'ytsearch:')):
            # Use ytsearch for regular searches
            url = f"ytsearch:{url}"
        
        data = await loop.run_in_executor(None, lambda: ytdl.extract_info(url, download=not stream))
        
        if 'entries' in data:
            # Take first item from a playlist or search results
            data = data['entries'][0]
        
        filename = data['url'] if stream else ytdl.prepare_filename(data)
        return cls(discord.FFmpegPCMAudio(filename, **ffmpeg_options), data=data)

    def parse_duration(self, duration_seconds):
        if not duration_seconds:
            return "Unknown"
        
        minutes, seconds = divmod(int(duration_seconds), 60)
        hours, minutes = divmod(minutes, 60)
        
        if hours > 0:
            return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
        else:
            return f"{minutes:02d}:{seconds:02d}"

class MusicQueue:
    def __init__(self):
        self._queue = []
        self.current_song = None
        self.loop = False
        self.now_playing_channel = None
    
    def add(self, song):
        self._queue.append(song)
    
    def next(self):
        if self.loop and self.current_song:
            return self.current_song
        
        if self._queue:
            self.current_song = self._queue.pop(0)
            return self.current_song
        return None
    
    def clear(self):
        self._queue.clear()
        self.current_song = None
    
    def remove(self, index):
        if 0 <= index < len(self._queue):
            return self._queue.pop(index)
        return None
    
    def get_queue(self):
        return self._queue.copy()
    
    def __len__(self):
        return len(self._queue)

class MusicCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.queues = {}  # guild_id -> MusicQueue
        self.voice_clients = {}  # guild_id -> voice_client
    
    def get_queue(self, guild_id):
        if guild_id not in self.queues:
            self.queues[guild_id] = MusicQueue()
        return self.queues[guild_id]
    
    async def play_next(self, guild_id, error=None):
        if error:
            logger.error(f"Player error: {error}")
        
        queue = self.get_queue(guild_id)
        voice_client = self.voice_clients.get(guild_id)
        
        if not voice_client:
            return
        
        next_song = queue.next()
        if next_song:
            try:
                voice_client.play(next_song, after=lambda e: asyncio.run_coroutine_threadsafe(self.play_next(guild_id, e), self.bot.loop))
                
                # Update now playing message
                if queue.now_playing_channel:
                    embed = discord.Embed(
                        title="🎵 Now Playing",
                        description=f"**{next_song.title}**\n👤 **Uploader:** {next_song.uploader}\n⏱️ **Duration:** {next_song.duration}",
                        color=0x00ff00
                    )
                    if next_song.thumbnail:
                        embed.set_thumbnail(url=next_song.thumbnail)
                    await queue.now_playing_channel.send(embed=embed)
            except Exception as e:
                logger.error(f"Error playing next song: {e}")
                await self.play_next(guild_id)
        else:
            # No more songs in queue
            if voice_client.is_connected():
                voice_client.stop()
            if queue.now_playing_channel:
                embed = discord.Embed(
                    title="🎵 Queue Finished",
                    description="The queue is empty! Add more songs to keep the music going!",
                    color=0xffff00
                )
                await queue.now_playing_channel.send(embed=embed)

    @app_commands.command(name='play', description='Play music from YouTube')
    @app_commands.describe(query='Song name or YouTube URL')
    async def slash_play(self, interaction: discord.Interaction, query: str):
        """Play music from YouTube"""
        try:
            await interaction.response.defer()
            
            # Check if user is in a voice channel
            if not interaction.user.voice:
                await interaction.followup.send("❌ You need to be in a voice channel to play music!")
                return
            
            voice_channel = interaction.user.voice.channel
            
            # Check permissions
            if not voice_channel.permissions_for(interaction.guild.me).connect:
                await interaction.followup.send("❌ I don't have permission to join your voice channel!")
                return
            
            # Connect to voice channel if not already connected
            voice_client = self.voice_clients.get(interaction.guild_id)
            if not voice_client or not voice_client.is_connected():
                try:
                    voice_client = await voice_channel.connect()
                    self.voice_clients[interaction.guild_id] = voice_client
                except Exception as e:
                    logger.error(f"Error connecting to voice channel: {e}")
                    await interaction.followup.send("❌ Could not connect to the voice channel!")
                    return
            
            # Search and play
            try:
                player = await YTDLSource.from_url(query, loop=self.bot.loop, stream=True)
                queue = self.get_queue(interaction.guild_id)
                queue.now_playing_channel = interaction.channel
                
                if voice_client.is_playing() or voice_client.is_paused():
                    queue.add(player)
                    embed = discord.Embed(
                        title="🎵 Added to Queue",
                        description=f"**{player.title}**\n👤 **Uploader:** {player.uploader}\n⏱️ **Duration:** {player.duration}\n📋 **Position in queue:** {len(queue)}",
                        color=0x00ff00
                    )
                    if player.thumbnail:
                        embed.set_thumbnail(url=player.thumbnail)
                    await interaction.followup.send(embed=embed)
                else:
                    queue.add(player)
                    await self.play_next(interaction.guild_id)
                    await interaction.followup.send("🎵 Starting playback...")
                    
            except Exception as e:
                logger.error(f"Error playing music: {e}")
                await interaction.followup.send("❌ Could not play the requested song. Please try a different one.")
                
        except Exception as e:
            logger.error(f"Error in play command: {e}")
            await interaction.followup.send("❌ An error occurred while trying to play music.")

    @app_commands.command(name='skip', description='Skip the current song')
    async def slash_skip(self, interaction: discord.Interaction):
        """Skip the current song"""
        try:
            voice_client = self.voice_clients.get(interaction.guild_id)
            if not voice_client or not voice_client.is_playing():
                await interaction.response.send_message("❌ No music is currently playing!", ephemeral=True)
                return
            
            current_song = self.get_queue(interaction.guild_id).current_song
            voice_client.stop()
            
            embed = discord.Embed(
                title="⏭️ Skipped Song",
                description=f"Skipped: **{current_song.title}**",
                color=0xffff00
            )
            await interaction.response.send_message(embed=embed)
            
        except Exception as e:
            logger.error(f"Error in skip command: {e}")
            await interaction.response.send_message("❌ An error occurred while skipping.", ephemeral=True)

    @app_commands.command(name='stop', description='Stop the music and clear the queue')
    async def slash_stop(self, interaction: discord.Interaction):
        """Stop music and clear queue"""
        try:
            voice_client = self.voice_clients.get(interaction.guild_id)
            queue = self.get_queue(interaction.guild_id)
            
            if voice_client:
                voice_client.stop()
            
            queue.clear()
            
            embed = discord.Embed(
                title="⏹️ Stopped Music",
                description="Stopped the music and cleared the queue!",
                color=0xff0000
            )
            await interaction.response.send_message(embed=embed)
            
        except Exception as e:
            logger.error(f"Error in stop command: {e}")
            await interaction.response.send_message("❌ An error occurred while stopping.", ephemeral=True)

    @app_commands.command(name='queue', description='Show the current music queue')
    async def slash_queue(self, interaction: discord.Interaction):
        """Show the current queue"""
        try:
            queue = self.get_queue(interaction.guild_id)
            
            if len(queue) == 0 and not queue.current_song:
                await interaction.response.send_message("🎵 The queue is empty!")
                return
            
            embed = discord.Embed(title="🎵 Music Queue", color=0x00ff00)
            
            # Current song
            if queue.current_song:
                embed.add_field(
                    name="Now Playing",
                    value=f"**{queue.current_song.title}**\n👤 {queue.current_song.uploader} | ⏱️ {queue.current_song.duration}",
                    inline=False
                )
            
            # Upcoming songs
            if len(queue) > 0:
                queue_text = ""
                for i, song in enumerate(queue.get_queue()[:10]):  # Show first 10 songs
                    queue_text += f"`{i+1}.` **{song.title}**\n👤 {song.uploader} | ⏱️ {song.duration}\n\n"
                
                if len(queue) > 10:
                    queue_text += f"\n...and {len(queue) - 10} more songs"
                
                embed.add_field(name="Up Next", value=queue_text, inline=False)
            else:
                embed.add_field(name="Up Next", value="No songs in queue", inline=False)
            
            await interaction.response.send_message(embed=embed)
            
        except Exception as e:
            logger.error(f"Error in queue command: {e}")
            await interaction.response.send_message("❌ An error occurred while showing the queue.", ephemeral=True)

    @app_commands.command(name='pause', description='Pause the current song')
    async def slash_pause(self, interaction: discord.Interaction):
        """Pause the current song"""
        try:
            voice_client = self.voice_clients.get(interaction.guild_id)
            if not voice_client or not voice_client.is_playing():
                await interaction.response.send_message("❌ No music is currently playing!", ephemeral=True)
                return
            
            voice_client.pause()
            await interaction.response.send_message("⏸️ Paused the music!")
            
        except Exception as e:
            logger.error(f"Error in pause command: {e}")
            await interaction.response.send_message("❌ An error occurred while pausing.", ephemeral=True)

    @app_commands.command(name='resume', description='Resume the paused song')
    async def slash_resume(self, interaction: discord.Interaction):
        """Resume the paused song"""
        try:
            voice_client = self.voice_clients.get(interaction.guild_id)
            if not voice_client or not voice_client.is_paused():
                await interaction.response.send_message("❌ No music is currently paused!", ephemeral=True)
                return
            
            voice_client.resume()
            await interaction.response.send_message("▶️ Resumed the music!")
            
        except Exception as e:
            logger.error(f"Error in resume command: {e}")
            await interaction.response.send_message("❌ An error occurred while resuming.", ephemeral=True)

    @app_commands.command(name='volume', description='Adjust the music volume (1-100)')
    @app_commands.describe(level='Volume level (1-100)')
    async def slash_volume(self, interaction: discord.Interaction, level: int):
        """Adjust volume"""
        try:
            if level < 1 or level > 100:
                await interaction.response.send_message("❌ Volume must be between 1 and 100!", ephemeral=True)
                return
            
            voice_client = self.voice_clients.get(interaction.guild_id)
            if not voice_client or not voice_client.is_playing():
                await interaction.response.send_message("❌ No music is currently playing!", ephemeral=True)
                return
            
            # Convert to float between 0.0 and 1.0
            volume = level / 100.0
            
            if voice_client.source:
                voice_client.source.volume = volume
            
            await interaction.response.send_message(f"🔊 Volume set to {level}%")
            
        except Exception as e:
            logger.error(f"Error in volume command: {e}")
            await interaction.response.send_message("❌ An error occurred while adjusting volume.", ephemeral=True)

    @app_commands.command(name='disconnect', description='Disconnect the bot from voice channel')
    async def slash_disconnect(self, interaction: discord.Interaction):
        """Disconnect from voice channel"""
        try:
            voice_client = self.voice_clients.get(interaction.guild_id)
            queue = self.get_queue(interaction.guild_id)
            
            if voice_client:
                voice_client.stop()
                await voice_client.disconnect()
                del self.voice_clients[interaction.guild_id]
            
            queue.clear()
            
            await interaction.response.send_message("🔌 Disconnected from voice channel!")
            
        except Exception as e:
            logger.error(f"Error in disconnect command: {e}")
            await interaction.response.send_message("❌ An error occurred while disconnecting.", ephemeral=True)

    @app_commands.command(name='nowplaying', description='Show the currently playing song')
    async def slash_nowplaying(self, interaction: discord.Interaction):
        """Show currently playing song"""
        try:
            queue = self.get_queue(interaction.guild_id)
            voice_client = self.voice_clients.get(interaction.guild_id)
            
            if not queue.current_song or not voice_client or not voice_client.is_playing():
                await interaction.response.send_message("❌ No music is currently playing!", ephemeral=True)
                return
            
            embed = discord.Embed(
                title="🎵 Now Playing",
                description=f"**{queue.current_song.title}**\n👤 **Uploader:** {queue.current_song.uploader}\n⏱️ **Duration:** {queue.current_song.duration}",
                color=0x00ff00
            )
            if queue.current_song.thumbnail:
                embed.set_thumbnail(url=queue.current_song.thumbnail)
            
            await interaction.response.send_message(embed=embed)
            
        except Exception as e:
            logger.error(f"Error in nowplaying command: {e}")
            await interaction.response.send_message("❌ An error occurred while getting current song.", ephemeral=True)

    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        """Auto-disconnect if bot is alone in voice channel"""
        if member.bot:
            return
        
        voice_client = self.voice_clients.get(member.guild.id)
        if voice_client and voice_client.channel:
            # Check if bot is alone in the channel
            if len(voice_client.channel.members) == 1 and voice_client.channel.members[0] == self.bot.user:
                queue = self.get_queue(member.guild.id)
                voice_client.stop()
                await voice_client.disconnect()
                queue.clear()
                if member.guild.id in self.voice_clients:
                    del self.voice_clients[member.guild.id]
                
                # Find a text channel to send message
                for channel in member.guild.text_channels:
                    if channel.permissions_for(member.guild.me).send_messages:
                        await channel.send("🔌 Disconnected from voice channel due to inactivity.")
                        break

async def setup(bot):
    await bot.add_cog(MusicCommands(bot))