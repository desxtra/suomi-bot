# commands/music.py
import asyncio
import logging
import discord
from discord import app_commands
from discord.ext import commands
import yt_dlp
import urllib.parse
import random
import os
import time
import glob
import aiofiles
from pathlib import Path

logger = logging.getLogger(__name__)

# Create cache directory
CACHE_DIR = "./music_cache"
os.makedirs(CACHE_DIR, exist_ok=True)

# Cache cleanup settings
CACHE_MAX_AGE = 3600  # 1 hour in seconds
CACHE_MAX_SIZE = 500 * 1024 * 1024  # 500 MB

# YouTube DL options for audio only with better caching
ytdl_format_options = {
    'format': 'bestaudio/best',
    'outtmpl': os.path.join(CACHE_DIR, '%(id)s.%(ext)s'),  # Simplified filename
    'restrictfilenames': True,
    'noplaylist': False,
    'nocheckcertificate': True,
    'ignoreerrors': True,
    'logtostderr': False,
    'quiet': True,
    'no_warnings': True,
    'default_search': 'ytsearch',
    'source_address': '0.0.0.0',
    'extractaudio': True,
    'audioformat': 'mp3',
    'extract_flat': False,
    'youtube_include_dash_manifest': False,
    'socket_timeout': 30,
    'retries': 10,
    'fragment_retries': 10,
    'skip_unavailable_fragments': True,
    'continue_dl': True,
    # Force download for caching
    'cachedir': os.path.join(CACHE_DIR, 'yt_dlp_cache'),
}

ffmpeg_options = {
    'before_options': (
        '-reconnect 1 '
        '-reconnect_streamed 1 '
        '-reconnect_delay_max 30 '
        '-timeout 30000000 '
        '-protocol_whitelist "file,http,https,tcp,tls" '
        '-probesize 32M '
        '-analyzeduration 0 '
        '-nostdin '
        '-multiple_requests 1 '
        '-user_agent "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"'
    ),
    'options': '-vn -bufsize 1024k -af "volume=0.5"'
}

ffmpeg_local_options = {
    'before_options': '-nostdin',
    'options': '-vn -bufsize 512k'
}

ytdl = yt_dlp.YoutubeDL(ytdl_format_options)

class YTDLSource(discord.PCMVolumeTransformer):
    def __init__(self, source, *, data, volume=0.5, is_cached=False):
        super().__init__(source, volume)
        self.data = data
        self.title = data.get('title')
        self.url = data.get('url')
        self.duration = self.parse_duration(data.get('duration'))
        self.thumbnail = data.get('thumbnail')
        self.uploader = data.get('uploader')
        self.video_id = data.get('id')
        self.is_cached = is_cached
        self.filename = None

    @classmethod
    async def from_url(cls, url, *, loop=None, stream=False, fallback_to_download=True):
        loop = loop or asyncio.get_event_loop()

        # Clean the URL/search query
        if not url.startswith(('http', 'ytsearch:')):
            url = f"ytsearch:{url}"

        try:
            # First, check if we already have this file cached
            data = await loop.run_in_executor(None, lambda: ytdl.extract_info(url, download=False))
            if 'entries' in data:
                data = data['entries'][0]
            
            video_id = data.get('id')
            if video_id:
                # Look for cached file
                cached_files = glob.glob(os.path.join(CACHE_DIR, f"{video_id}.*"))
                # Filter out non-audio files and yt-dlp cache directories
                cached_files = [f for f in cached_files if not f.endswith(('.json', '.part')) and 'yt_dlp_cache' not in f]
                
                if cached_files:
                    # Use cached file
                    cached_file = cached_files[0]
                    source = cls(discord.FFmpegPCMAudio(cached_file, **ffmpeg_local_options), data=data, is_cached=True)
                    source.filename = cached_file
                    logger.info(f"Using cached audio: {source.title} from {cached_file}")
                    return source

            # If no cache found or streaming requested, try streaming first
            if stream:
                try:
                    filename = data['url']
                    source = cls(discord.FFmpegPCMAudio(filename, **ffmpeg_options), data=data, is_cached=False)
                    logger.info(f"Streaming audio: {source.title}")
                    return source
                except Exception as stream_error:
                    logger.warning(f"Streaming failed for {url}, falling back to download: {stream_error}")
                    if not fallback_to_download:
                        raise stream_error
                    # Fall through to download

            # Download the audio (this will use cache if available via yt-dlp)
            downloaded_data = await loop.run_in_executor(None, lambda: ytdl.extract_info(url, download=True))
            if 'entries' in downloaded_data:
                downloaded_data = downloaded_data['entries'][0]

            # Find the downloaded file
            downloaded_video_id = downloaded_data.get('id')
            if downloaded_video_id:
                downloaded_files = glob.glob(os.path.join(CACHE_DIR, f"{downloaded_video_id}.*"))
                downloaded_files = [f for f in downloaded_files if not f.endswith(('.json', '.part')) and 'yt_dlp_cache' not in f]
                
                if downloaded_files:
                    filename = downloaded_files[0]
                else:
                    filename = ytdl.prepare_filename(downloaded_data)
            else:
                filename = ytdl.prepare_filename(downloaded_data)

            source = cls(discord.FFmpegPCMAudio(filename, **ffmpeg_local_options), data=downloaded_data, is_cached=True)
            source.filename = filename
            logger.info(f"Downloaded and cached audio: {source.title} to {filename}")
            return source

        except Exception as e:
            logger.error(f"Error in from_url for {url}: {e}")
            raise

    @classmethod
    async def from_video_id(cls, video_id, *, loop=None, stream=False, fallback_to_download=True):
        """Create source directly from video ID for radio mode"""
        loop = loop or asyncio.get_event_loop()
        url = f"https://www.youtube.com/watch?v={video_id}"
        return await cls.from_url(url, loop=loop, stream=stream, fallback_to_download=fallback_to_download)

    def parse_duration(self, duration_seconds):
        if not duration_seconds:
            return "Unknown"

        minutes, seconds = divmod(int(duration_seconds), 60)
        hours, minutes = divmod(minutes, 60)

        if hours > 0:
            return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
        else:
            return f"{minutes:02d}:{seconds:02d}"

    def cleanup(self):
        """Remove cached file if it exists - but we'll keep files for caching"""
        # Don't cleanup immediately - keep files cached for future use
        # We'll rely on the periodic cleanup task instead
        pass

class MusicQueue:
    def __init__(self):
        self._queue = []
        self.current_song = None
        self.loop = False
        self.now_playing_channel = None
        self.radio_mode = False
        self.radio_seed = None

    def add(self, song):
        self._queue.append(song)

    def next(self):
        if self.loop and self.current_song:
            return self.current_song

        # Clean up previous song (but keep the file for caching)
        if self.current_song:
            # We don't cleanup immediately to allow caching
            pass

        if self._queue:
            self.current_song = self._queue.pop(0)
            return self.current_song
        return None

    def clear(self):
        # Don't cleanup files - keep them cached
        self._queue.clear()
        self.current_song = None
        self.radio_mode = False
        self.radio_seed = None

    def remove(self, index):
        """Remove a specific song from queue by index (1-based)"""
        if 0 <= index < len(self._queue):
            song = self._queue.pop(index)
            # Don't cleanup the file - keep it cached
            return song
        return None

    def get_queue(self):
        return self._queue.copy()

    def __len__(self):
        return len(self._queue)

class MusicCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.queues = {}
        self.voice_clients = {}
        self.cleanup_task = None
        
    async def cog_load(self):
        """Start cleanup task when cog loads"""
        self.cleanup_task = self.bot.loop.create_task(self.periodic_cache_cleanup())

    async def cog_unload(self):
        """Stop cleanup task when cog unloads"""
        if self.cleanup_task:
            self.cleanup_task.cancel()
            try:
                await self.cleanup_task
            except asyncio.CancelledError:
                pass

    async def periodic_cache_cleanup(self):
        """Periodically clean up old cache files"""
        await self.bot.wait_until_ready()
        while not self.bot.is_closed():
            try:
                await self.cleanup_old_cache()
                await asyncio.sleep(3600)  # Run every hour
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in cache cleanup: {e}")
                await asyncio.sleep(300)  # Wait 5 minutes on error

    async def cleanup_old_cache(self):
        """Remove cache files older than CACHE_MAX_AGE"""
        try:
            current_time = time.time()
            deleted_count = 0
            total_size = 0

            # Calculate total cache size first
            cache_files = []
            for file_path in glob.glob(os.path.join(CACHE_DIR, "*")):
                if os.path.isfile(file_path) and not file_path.endswith(('.part', '.json')) and 'yt_dlp_cache' not in file_path:
                    try:
                        file_stats = os.stat(file_path)
                        cache_files.append((file_path, file_stats.st_mtime, file_stats.st_size))
                        total_size += file_stats.st_size
                    except OSError:
                        continue

            # Sort by modification time (oldest first)
            cache_files.sort(key=lambda x: x[1])

            # Delete files if cache is too large or files are too old
            for file_path, mtime, file_size in cache_files:
                file_age = current_time - mtime

                should_delete = False
                reason = ""
                if file_age > CACHE_MAX_AGE:
                    should_delete = True
                    reason = "age"
                elif total_size > CACHE_MAX_SIZE:
                    should_delete = True
                    reason = "size"
                    total_size -= file_size  # Reduce total size

                if should_delete:
                    try:
                        os.remove(file_path)
                        deleted_count += 1
                        logger.info(f"Cleaned up cache file ({reason}): {os.path.basename(file_path)}")
                    except Exception as e:
                        logger.error(f"Error deleting cache file {file_path}: {e}")

            if deleted_count > 0:
                logger.info(f"Cleaned up {deleted_count} cache files. Current cache size: {total_size / (1024*1024):.2f} MB")

        except Exception as e:
            logger.error(f"Error in cleanup_old_cache: {e}")

    def get_queue(self, guild_id):
        if guild_id not in self.queues:
            self.queues[guild_id] = MusicQueue()
        return self.queues[guild_id]

    async def get_related_videos(self, video_id, count=5):
        """Get related videos for radio mode"""
        try:
            loop = asyncio.get_event_loop()
            url = f"https://www.youtube.com/watch?v={video_id}"

            data = await loop.run_in_executor(None, lambda: ytdl.extract_info(url, download=False))

            related_videos = []
            if 'related_videos' in data:
                related_videos = data['related_videos'][:count]
            elif 'entries' in data and len(data['entries']) > 1:
                related_videos = data['entries'][1:1+count]

            return [video.get('id') for video in related_videos if video.get('id')]
        except Exception as e:
            logger.error(f"Error getting related videos: {e}")
            return []

    async def search_related_music(self, query, count=5):
        """Search for music related to the query for radio mode"""
        try:
            loop = asyncio.get_event_loop()
            search_url = f"ytsearch{count}:{query}"

            data = await loop.run_in_executor(None, lambda: ytdl.extract_info(search_url, download=False))

            if 'entries' in data:
                return [entry.get('id') for entry in data['entries'] if entry.get('id')]
            return []
        except Exception as e:
            logger.error(f"Error searching related music: {e}")
            return []

    async def add_radio_songs(self, guild_id, seed_video_id=None, seed_query=None):
        """Add radio songs to the queue based on seed"""
        queue = self.get_queue(guild_id)

        if not queue.radio_mode:
            return

        try:
            video_ids = []

            if seed_video_id:
                video_ids = await self.get_related_videos(seed_video_id, 3)
            elif seed_query:
                video_ids = await self.search_related_music(seed_query, 3)

            # Add videos to queue with download fallback
            for video_id in video_ids:
                try:
                    player = await YTDLSource.from_video_id(
                        video_id, 
                        loop=self.bot.loop, 
                        stream=False,  # Force download for radio mode to build cache
                        fallback_to_download=True
                    )
                    queue.add(player)
                    logger.info(f"Added radio song: {player.title} (cached: {player.is_cached})")
                except Exception as e:
                    logger.error(f"Error adding radio song {video_id}: {e}")
                    continue

            # Fallback search
            if not video_ids and seed_query:
                fallback_query = f"music {seed_query}" if len(seed_query.split()) < 3 else seed_query
                fallback_ids = await self.search_related_music(fallback_query, 3)
                for video_id in fallback_ids:
                    try:
                        player = await YTDLSource.from_video_id(
                            video_id, 
                            loop=self.bot.loop, 
                            stream=False,  # Force download
                            fallback_to_download=True
                        )
                        queue.add(player)
                        logger.info(f"Added fallback radio song: {player.title} (cached: {player.is_cached})")
                    except Exception as e:
                        logger.error(f"Error adding fallback radio song {video_id}: {e}")
                        continue

            # Send notification
            if queue.now_playing_channel and (video_ids or fallback_ids):
                added_count = len([v for v in video_ids + (fallback_ids or []) if v])
                embed = discord.Embed(
                    title="🎵 Radio Mode",
                    description=f"Added {added_count} related songs to the queue!",
                    color=0x00ff00
                )
                await queue.now_playing_channel.send(embed=embed)

        except Exception as e:
            logger.error(f"Error in add_radio_songs: {e}")

    async def play_next(self, guild_id, error=None):
        if error:
            logger.error(f"Player error: {error}")

        queue = self.get_queue(guild_id)
        voice_client = self.voice_clients.get(guild_id)

        if not voice_client:
            return

        next_song = queue.next()

        # Radio mode handling
        if not next_song and queue.radio_mode:
            if queue.now_playing_channel:
                embed = discord.Embed(
                    title="🎵 Radio Mode",
                    description="Finding related songs...",
                    color=0xffff00
                )
                await queue.now_playing_channel.send(embed=embed)

            seed_video_id = queue.current_song.video_id if queue.current_song else None
            seed_query = queue.radio_seed

            await self.add_radio_songs(guild_id, seed_video_id, seed_query)
            next_song = queue.next()

        if next_song:
            try:
                voice_client.play(next_song, after=lambda e: asyncio.run_coroutine_threadsafe(self.play_next(guild_id, e), self.bot.loop))

                # Update now playing message
                if queue.now_playing_channel:
                    radio_indicator = " 📻" if queue.radio_mode else ""
                    cache_indicator = " 💾" if next_song.is_cached else " 🌐"
                    embed = discord.Embed(
                        title=f"🎵 Now Playing{radio_indicator}{cache_indicator}",
                        description=f"**{next_song.title}**\n👤 **Uploader:** {next_song.uploader}\n⏱️ **Duration:** {next_song.duration}",
                        color=0x00ff00
                    )
                    if next_song.thumbnail:
                        embed.set_thumbnail(url=next_song.thumbnail)

                    if queue.radio_mode:
                        embed.set_footer(text="Radio mode is active - related songs will play automatically")
                    if next_song.is_cached:
                        embed.set_footer(text=(embed.footer.text + " | Using cached audio" if embed.footer.text else "Using cached audio"))

                    await queue.now_playing_channel.send(embed=embed)
            except Exception as e:
                logger.error(f"Error playing next song: {e}")
                await self.play_next(guild_id)
        else:
            # No more songs in queue
            if voice_client.is_connected():
                voice_client.stop()
            if queue.now_playing_channel:
                if queue.radio_mode:
                    embed = discord.Embed(
                        title="🎵 Radio Mode Issue",
                        description="Could not find related songs. Radio mode has been disabled.",
                        color=0xff0000
                    )
                    queue.radio_mode = False
                else:
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

            if not interaction.user.voice:
                await interaction.followup.send("❌ You need to be in a voice channel to play music!")
                return

            voice_channel = interaction.user.voice.channel

            if not voice_channel.permissions_for(interaction.guild.me).connect:
                await interaction.followup.send("❌ I don't have permission to join your voice channel!")
                return

            # Connect to voice channel
            voice_client = self.voice_clients.get(interaction.guild_id)
            if not voice_client or not voice_client.is_connected():
                try:
                    voice_client = await voice_channel.connect()
                    self.voice_clients[interaction.guild_id] = voice_client
                except Exception as e:
                    logger.error(f"Error connecting to voice channel: {e}")
                    await interaction.followup.send("❌ Could not connect to the voice channel!")
                    return

            # Try to use cached version first, fallback to streaming
            try:
                player = await YTDLSource.from_url(
                    query, 
                    loop=self.bot.loop, 
                    stream=False,  # Try cached/download first
                    fallback_to_download=True
                )
                
                queue = self.get_queue(interaction.guild_id)
                queue.now_playing_channel = interaction.channel

                if voice_client.is_playing() or voice_client.is_paused():
                    queue.add(player)
                    cache_indicator = " 💾" if player.is_cached else " 🌐"
                    embed = discord.Embed(
                        title=f"🎵 Added to Queue{cache_indicator}",
                        description=f"**{player.title}**\n👤 **Uploader:** {player.uploader}\n⏱️ **Duration:** {player.duration}\n📋 **Position in queue:** {len(queue)}",
                        color=0x00ff00
                    )
                    if player.thumbnail:
                        embed.set_thumbnail(url=player.thumbnail)
                    await interaction.followup.send(embed=embed)
                else:
                    queue.add(player)
                    await self.play_next(interaction.guild_id)
                    cache_indicator = " 💾" if player.is_cached else " 🌐"
                    await interaction.followup.send(f"🎵 Starting playback...{cache_indicator}")

            except Exception as e:
                logger.error(f"Error playing music: {e}")
                await interaction.followup.send("❌ Could not play the requested song. Please try a different one.")

        except Exception as e:
            logger.error(f"Error in play command: {e}")
            await interaction.followup.send("❌ An error occurred while trying to play music.")

    @app_commands.command(name='radio', description='Toggle radio mode (automatically play related songs)')
    async def slash_radio(self, interaction: discord.Interaction):
        """Toggle radio mode"""
        try:
            queue = self.get_queue(interaction.guild_id)
            queue.radio_mode = not queue.radio_mode

            if queue.radio_mode:
                if queue.current_song:
                    queue.radio_seed = queue.current_song.title
                else:
                    queue.radio_seed = "music"

                embed = discord.Embed(
                    title="📻 Radio Mode Enabled",
                    description="The bot will automatically play related songs when the queue ends!\nUse `/radio` again to disable.",
                    color=0x00ff00
                )
            else:
                embed = discord.Embed(
                    title="📻 Radio Mode Disabled",
                    description="Automatic song playback has been disabled.",
                    color=0xffff00
                )

            await interaction.response.send_message(embed=embed)

        except Exception as e:
            logger.error(f"Error in radio command: {e}")
            await interaction.response.send_message("❌ An error occurred while toggling radio mode.", ephemeral=True)

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

            if queue.radio_mode:
                embed.set_footer(text="📻 Radio mode is active - related songs will play automatically")

            if queue.current_song:
                radio_indicator = " 📻" if queue.radio_mode else ""
                cache_indicator = " 💾" if queue.current_song.is_cached else " 🌐"
                embed.add_field(
                    name=f"Now Playing{radio_indicator}{cache_indicator}",
                    value=f"**{queue.current_song.title}**\n👤 {queue.current_song.uploader} | ⏱️ {queue.current_song.duration}",
                    inline=False
                )

            if len(queue) > 0:
                queue_text = ""
                for i, song in enumerate(queue.get_queue()[:10]):
                    cache_indicator = " 💾" if song.is_cached else " 🌐"
                    queue_text += f"`{i+1}.` **{song.title}**{cache_indicator}\n👤 {song.uploader} | ⏱️ {song.duration}\n\n"

                if len(queue) > 10:
                    queue_text += f"\n...and {len(queue) - 10} more songs"

                embed.add_field(name="Up Next", value=queue_text, inline=False)
            else:
                embed.add_field(name="Up Next", value="No songs in queue", inline=False)

            await interaction.response.send_message(embed=embed)

        except Exception as e:
            logger.error(f"Error in queue command: {e}")
            await interaction.response.send_message("❌ An error occurred while showing the queue.", ephemeral=True)

    @app_commands.command(name='remove', description='Remove a specific song from the queue')
    @app_commands.describe(position='Position of the song in the queue (use /queue to see positions)')
    async def slash_remove(self, interaction: discord.Interaction, position: int):
        """Remove a specific song from the queue"""
        try:
            queue = self.get_queue(interaction.guild_id)
            
            if len(queue) == 0:
                await interaction.response.send_message("❌ The queue is empty!", ephemeral=True)
                return
                
            if position < 1 or position > len(queue):
                await interaction.response.send_message(
                    f"❌ Invalid position! Please use a number between 1 and {len(queue)}.", 
                    ephemeral=True
                )
                return

            # Remove the song (position is 1-based, list is 0-based)
            removed_song = queue.remove(position - 1)
            
            if removed_song:
                embed = discord.Embed(
                    title="🗑️ Removed from Queue",
                    description=f"Removed **{removed_song.title}** from position {position}",
                    color=0x00ff00
                )
                await interaction.response.send_message(embed=embed)
            else:
                await interaction.response.send_message("❌ Failed to remove the song.", ephemeral=True)

        except Exception as e:
            logger.error(f"Error in remove command: {e}")
            await interaction.response.send_message("❌ An error occurred while removing the song.", ephemeral=True)

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

            radio_indicator = " 📻" if queue.radio_mode else ""
            cache_indicator = " 💾" if queue.current_song.is_cached else " 🌐"
            embed = discord.Embed(
                title=f"🎵 Now Playing{radio_indicator}{cache_indicator}",
                description=f"**{queue.current_song.title}**\n👤 **Uploader:** {queue.current_song.uploader}\n⏱️ **Duration:** {queue.current_song.duration}",
                color=0x00ff00
            )
            if queue.current_song.thumbnail:
                embed.set_thumbnail(url=queue.current_song.thumbnail)

            footer_text = ""
            if queue.radio_mode:
                footer_text += "Radio mode is active - related songs will play automatically"
            if queue.current_song.is_cached:
                if footer_text:
                    footer_text += " | "
                footer_text += "Using cached audio"
            
            if footer_text:
                embed.set_footer(text=footer_text)

            await interaction.response.send_message(embed=embed)

        except Exception as e:
            logger.error(f"Error in nowplaying command: {e}")
            await interaction.response.send_message("❌ An error occurred while getting current song.", ephemeral=True)

    @app_commands.command(name='clearcache', description='Clear all cached music files')
    async def slash_clearcache(self, interaction: discord.Interaction):
        """Clear music cache"""
        try:
            await interaction.response.defer()
            
            deleted_count = 0
            for file_path in glob.glob(os.path.join(CACHE_DIR, "*")):
                if os.path.isfile(file_path) and not file_path.endswith(('.part', '.json')) and 'yt_dlp_cache' not in file_path:
                    try:
                        os.remove(file_path)
                        deleted_count += 1
                    except Exception as e:
                        logger.error(f"Error deleting cache file {file_path}: {e}")

            embed = discord.Embed(
                title="🗑️ Cache Cleared",
                description=f"Successfully cleared {deleted_count} cached music files.",
                color=0x00ff00
            )
            await interaction.followup.send(embed=embed)

        except Exception as e:
            logger.error(f"Error in clearcache command: {e}")
            await interaction.followup.send("❌ An error occurred while clearing cache.")

    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        """Auto-disconnect if bot is alone in voice channel"""
        if member.bot:
            return

        voice_client = self.voice_clients.get(member.guild.id)
        if voice_client and voice_client.channel:
            if len(voice_client.channel.members) == 1 and voice_client.channel.members[0] == self.bot.user:
                queue = self.get_queue(member.guild.id)
                voice_client.stop()
                await voice_client.disconnect()
                queue.clear()
                if member.guild.id in self.voice_clients:
                    del self.voice_clients[member.guild.id]

                for channel in member.guild.text_channels:
                    if channel.permissions_for(member.guild.me).send_messages:
                        await channel.send("🔌 Disconnected from voice channel due to inactivity.")
                        break

async def setup(bot):
    await bot.add_cog(MusicCommands(bot))