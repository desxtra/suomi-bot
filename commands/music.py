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
import re
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
        '-timeout 15000000  '
        '-protocol_whitelist "file,http,https,tcp,tls" '
        '-probesize 16M '
        '-analyzeduration 0 '
        '-nostdin '
        '-multiple_requests 1 '
        '-user_agent "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"'
    ),
    'options': '-vn -bufsize 512k -af volume=0.5'
}

ffmpeg_local_options = {
    'before_options': '-nostdin',
    'options': '-vn -bufsize 256k'
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

    def clean_song_title(self, title):
        """Clean song title for better comparison"""
        if not title:
            return ""
            
        # Remove common YouTube suffixes and parentheses content
        clean = title.lower()
        
        # Remove content in parentheses and brackets
        clean = re.sub(r'[\[\(].*?[\]\)]', '', clean)
        
        # Remove common suffixes
        suffixes = ['official video', 'official audio', 'lyrics', 'hd', '4k', 'upload']
        for suffix in suffixes:
            clean = clean.replace(suffix, '')
            
        # Remove extra spaces and trim
        clean = re.sub(r'\s+', ' ', clean).strip()
        
        return clean

    def clean_artist_name(self, artist):
        """Clean artist name for better searching"""
        if not artist:
            return ""
            
        # Remove common YouTube channel suffixes
        clean = artist.lower()
        
        # Remove channel indicators
        channel_indicators = ['topic', 'vevo', 'official', 'channel']
        for indicator in channel_indicators:
            clean = clean.replace(indicator, '')
            
        # Remove extra spaces and trim
        clean = re.sub(r'\s+', ' ', clean).strip()
        
        return clean

    def is_similar_title(self, title1, title2):
        """Check if two titles are too similar (likely duplicates)"""
        if not title1 or not title2:
            return False
            
        clean1 = self.clean_song_title(title1)
        clean2 = self.clean_song_title(title2)
        
        # If cleaned titles are identical, they're similar
        if clean1 == clean2:
            return True
            
        # If one contains the other (with small differences)
        if clean1 in clean2 or clean2 in clean1:
            # Allow some differences for remixes, etc.
            diff_length = abs(len(clean1) - len(clean2))
            if diff_length < 10:  # If length difference is small
                return True
                
        return False

    def get_title_key(self, title):
        """Create a key for title comparison to avoid near-duplicates"""
        if not title:
            return ""
            
        # Remove common words and get first few meaningful words
        words = title.split()
        common_words = {'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by'}
        meaningful_words = [w for w in words if w not in common_words][:3]  # First 3 meaningful words
        
        return ' '.join(meaningful_words)

    def get_song_era(self, title):
        """Try to determine song era for better recommendations"""
        # This is a simple implementation - you could expand this
        era_keywords = {
            '80s': ['80s', 'eighties', '1980'],
            '90s': ['90s', 'nineties', '1990'],
            '2000s': ['2000s', '2000', 'millennium'],
            'modern': ['202', '201']  # 2020, 2019, etc.
        }
        
        title_lower = title.lower()
        for era, keywords in era_keywords.items():
            if any(keyword in title_lower for keyword in keywords):
                return era
                
        return ""

    async def search_related_music(self, current_title, current_artist, count=5):
        """Search for music related to the query for radio mode with better filtering"""
        try:
            loop = asyncio.get_event_loop()
            
            # Clean the current title for better searching
            clean_title = self.clean_song_title(current_title)
            clean_artist = self.clean_artist_name(current_artist)
            
            # Define unwanted terms that indicate duplicates or low-quality versions
            unwanted_terms = [
                'lyrics', 'lyric', 'official music video', 'official video', 
                'official audio', 'audio only', 'slowed', 'reverb', 'sped up',
                'nightcore', 'cover', 'covers', 'remix', 'remixes', 'live',
                'performance', 'acoustic', 'instrumental', 'karaoke'
            ]
            
            # Define preferred terms that indicate good versions
            preferred_terms = [
                'official', 'original', 'album version', 'studio version'
            ]
            
            # Multiple search strategies for better variety
            search_strategies = [
                # Search by artist for other songs by the same artist
                f"{clean_artist} songs",
                # Search for similar artists/genres
                f"music like {clean_artist}",
                f"{clean_artist} genre music",
                # Search for the song's album or era
                f"{clean_artist} {self.get_song_era(clean_title)}",
                # Search for similar mood/type
                f"{clean_artist} similar to {clean_title}"
            ]
            
            all_video_ids = []
            seen_titles = set()
            
            for search_query in search_strategies:
                if len(all_video_ids) >= count:
                    break
                    
                search_url = f"ytsearch{count*2}:{search_query}"
                data = await loop.run_in_executor(None, lambda: ytdl.extract_info(search_url, download=False))

                if 'entries' in data:
                    for entry in data['entries']:
                        video_id = entry.get('id')
                        title = entry.get('title', '').lower()
                        uploader = entry.get('uploader', '').lower()
                        
                        # Skip if we already have this video
                        if video_id in all_video_ids:
                            continue
                            
                        # Skip if title is too similar to current song (avoid duplicates)
                        if self.is_similar_title(title, clean_title):
                            continue
                            
                        # Skip if it contains unwanted terms (lyrics, slowed, etc.)
                        if any(unwanted in title for unwanted in unwanted_terms):
                            continue
                            
                        # Skip if it's the exact same title (different uploader)
                        clean_entry_title = self.clean_song_title(title)
                        if clean_entry_title == clean_title.lower():
                            continue
                            
                        # Skip if we've already seen a very similar title
                        title_key = self.get_title_key(clean_entry_title)
                        if title_key in seen_titles:
                            continue
                            
                        # Prefer versions with preferred terms
                        has_preferred = any(pref in title for pref in preferred_terms)
                        
                        # Add to results
                        all_video_ids.append(video_id)
                        seen_titles.add(title_key)
                        
                        if len(all_video_ids) >= count:
                            break
            
            # If we don't have enough results, try a broader search
            if len(all_video_ids) < count:
                broader_searches = [
                    f"{clean_artist} popular songs",
                    f"{clean_artist} best songs",
                    f"{clean_artist} hits"
                ]
                
                for broad_search in broader_searches:
                    if len(all_video_ids) >= count:
                        break
                        
                    search_url = f"ytsearch{count}:{broad_search}"
                    data = await loop.run_in_executor(None, lambda: ytdl.extract_info(search_url, download=False))
                    
                    if 'entries' in data:
                        for entry in data['entries']:
                            video_id = entry.get('id')
                            title = entry.get('title', '').lower()
                            
                            if (video_id not in all_video_ids and 
                                not self.is_similar_title(title, clean_title) and
                                not any(unwanted in title for unwanted in unwanted_terms)):
                                
                                clean_entry_title = self.clean_song_title(title)
                                title_key = self.get_title_key(clean_entry_title)
                                
                                if title_key not in seen_titles:
                                    all_video_ids.append(video_id)
                                    seen_titles.add(title_key)
                                    
                                    if len(all_video_ids) >= count:
                                        break

            return all_video_ids[:count]
            
        except Exception as e:
            logger.error(f"Error searching related music: {e}")
            return []

    async def add_radio_songs(self, guild_id, seed_video_id=None, seed_query=None):
        """Add radio songs to the queue based on seed with better filtering"""
        queue = self.get_queue(guild_id)

        if not queue.radio_mode:
            return

        try:
            video_ids = []

            if seed_video_id:
                # Get current song info for better recommendations
                current_song = queue.current_song
                if current_song:
                    current_title = current_song.title
                    current_artist = current_song.uploader
                    
                    # Use improved search with current song context
                    video_ids = await self.search_related_music(current_title, current_artist, 5)
                else:
                    # Fallback to related videos if no current song
                    video_ids = await self.get_related_videos(seed_video_id, 5)
                    
            elif seed_query:
                # For seed queries, use the query as both title and artist
                video_ids = await self.search_related_music(seed_query, seed_query, 5)

            # Add videos to queue with download fallback
            added_count = 0
            for video_id in video_ids:
                try:
                    player = await YTDLSource.from_video_id(
                        video_id, 
                        loop=self.bot.loop, 
                        stream=False,
                        fallback_to_download=True
                    )
                    
                    # Additional check: skip if title is too similar to current song
                    if queue.current_song and self.is_similar_title(player.title, queue.current_song.title):
                        logger.info(f"Skipping similar song: {player.title}")
                        continue
                        
                    queue.add(player)
                    added_count += 1
                    logger.info(f"Added radio song: {player.title} by {player.uploader}")
                    
                    if added_count >= 3:  # Limit to 3 songs per radio cycle
                        break
                        
                except Exception as e:
                    logger.error(f"Error adding radio song {video_id}: {e}")
                    continue

            # Send notification
            if queue.now_playing_channel and added_count > 0:
                embed = discord.Embed(
                    title="🎵 Radio Mode",
                    description=f"Added {added_count} related songs to the queue!",
                    color=0x00ff00
                )
                await queue.now_playing_channel.send(embed=embed)
                
            elif queue.now_playing_channel and added_count == 0:
                embed = discord.Embed(
                    title="🎵 Radio Mode",
                    description="Could not find suitable related songs. Try a different song!",
                    color=0xffff00
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

    @app_commands.command(name='skip', description='Skip the current song')
    async def slash_skip(self, interaction: discord.Interaction):
        """Skip the current song"""
        try:
            voice_client = self.voice_clients.get(interaction.guild_id)
            if not voice_client or not voice_client.is_playing():
                await interaction.response.send_message("❌ No song is currently playing!", ephemeral=True)
                return

            queue = self.get_queue(interaction.guild_id)
            current_song = queue.current_song
            
            voice_client.stop()
            
            embed = discord.Embed(
                title="⏭️ Song Skipped",
                description=f"Skipped **{current_song.title}**",
                color=0xffff00
            )
            await interaction.response.send_message(embed=embed)
            
        except Exception as e:
            logger.error(f"Error in skip command: {e}")
            await interaction.response.send_message("❌ An error occurred while skipping the song.", ephemeral=True)

    @app_commands.command(name='pause', description='Pause the current song')
    async def slash_pause(self, interaction: discord.Interaction):
        """Pause the current song"""
        try:
            voice_client = self.voice_clients.get(interaction.guild_id)
            if not voice_client or not voice_client.is_playing():
                await interaction.response.send_message("❌ No song is currently playing!", ephemeral=True)
                return

            if voice_client.is_paused():
                await interaction.response.send_message("❌ The player is already paused!", ephemeral=True)
                return

            voice_client.pause()
            
            queue = self.get_queue(interaction.guild_id)
            embed = discord.Embed(
                title="⏸️ Playback Paused",
                description=f"Paused **{queue.current_song.title}**",
                color=0xffff00
            )
            await interaction.response.send_message(embed=embed)
            
        except Exception as e:
            logger.error(f"Error in pause command: {e}")
            await interaction.response.send_message("❌ An error occurred while pausing the player.", ephemeral=True)

    @app_commands.command(name='resume', description='Resume the paused song')
    async def slash_resume(self, interaction: discord.Interaction):
        """Resume the paused song"""
        try:
            voice_client = self.voice_clients.get(interaction.guild_id)
            if not voice_client or not voice_client.is_paused():
                await interaction.response.send_message("❌ No song is currently paused!", ephemeral=True)
                return

            voice_client.resume()
            
            queue = self.get_queue(interaction.guild_id)
            embed = discord.Embed(
                title="▶️ Playback Resumed",
                description=f"Resumed **{queue.current_song.title}**",
                color=0x00ff00
            )
            await interaction.response.send_message(embed=embed)
            
        except Exception as e:
            logger.error(f"Error in resume command: {e}")
            await interaction.response.send_message("❌ An error occurred while resuming the player.", ephemeral=True)

    @app_commands.command(name='nowplaying', description='Show the currently playing song')
    async def slash_nowplaying(self, interaction: discord.Interaction):
        """Show the currently playing song"""
        try:
            queue = self.get_queue(interaction.guild_id)
            voice_client = self.voice_clients.get(interaction.guild_id)

            if not voice_client or not voice_client.is_playing() or not queue.current_song:
                await interaction.response.send_message("❌ No song is currently playing!", ephemeral=True)
                return

            current_song = queue.current_song
            radio_indicator = " 📻" if queue.radio_mode else ""
            cache_indicator = " 💾" if current_song.is_cached else " 🌐"
            
            embed = discord.Embed(
                title=f"🎵 Now Playing{radio_indicator}{cache_indicator}",
                description=f"**{current_song.title}**\n👤 **Uploader:** {current_song.uploader}\n⏱️ **Duration:** {current_song.duration}",
                color=0x00ff00
            )
            
            if current_song.thumbnail:
                embed.set_thumbnail(url=current_song.thumbnail)
                
            if queue.radio_mode:
                embed.set_footer(text="Radio mode is active")
            if current_song.is_cached:
                embed.set_footer(text=(embed.footer.text + " | Using cached audio" if embed.footer.text else "Using cached audio"))

            await interaction.response.send_message(embed=embed)
            
        except Exception as e:
            logger.error(f"Error in nowplaying command: {e}")
            await interaction.response.send_message("❌ An error occurred while getting the current song info.", ephemeral=True)

    @app_commands.command(name='remove', description='Remove a specific song from the queue')
    @app_commands.describe(position='Position of the song in queue to remove (1 for first in queue)')
    async def slash_remove(self, interaction: discord.Interaction, position: int):
        """Remove a specific song from the queue"""
        try:
            queue = self.get_queue(interaction.guild_id)
            
            if len(queue) == 0:
                await interaction.response.send_message("❌ The queue is empty!", ephemeral=True)
                return

            # Convert to 0-based index
            index = position - 1
            
            if index < 0 or index >= len(queue):
                await interaction.response.send_message(f"❌ Please provide a valid position between 1 and {len(queue)}", ephemeral=True)
                return

            removed_song = queue.remove(index)
            
            embed = discord.Embed(
                title="🗑️ Song Removed",
                description=f"Removed **{removed_song.title}** from position {position}",
                color=0xffff00
            )
            await interaction.response.send_message(embed=embed)
            
        except Exception as e:
            logger.error(f"Error in remove command: {e}")
            await interaction.response.send_message("❌ An error occurred while removing the song.", ephemeral=True)

    @app_commands.command(name='queue', description='Show the current music queue')
    async def slash_queue(self, interaction: discord.Interaction):
        """Show the current music queue"""
        try:
            queue = self.get_queue(interaction.guild_id)
            voice_client = self.voice_clients.get(interaction.guild_id)

            if not queue.current_song and len(queue) == 0:
                await interaction.response.send_message("❌ The queue is empty! Use `/play` to add songs.", ephemeral=True)
                return

            embed = discord.Embed(title="📋 Music Queue", color=0x00ff00)
            
            # Add currently playing song
            if queue.current_song:
                current_status = "⏸️ Paused" if voice_client and voice_client.is_paused() else "▶️ Playing"
                embed.add_field(
                    name=f"{current_status} - Now Playing:",
                    value=f"**{queue.current_song.title}**\n👤 {queue.current_song.uploader} | ⏱️ {queue.current_song.duration}",
                    inline=False
                )
            
            # Add queued songs
            queue_list = queue.get_queue()
            if queue_list:
                queue_text = ""
                for i, song in enumerate(queue_list, 1):
                    cache_indicator = " 💾" if song.is_cached else ""
                    queue_text += f"`{i}.` **{song.title}** - {song.uploader} | {song.duration}{cache_indicator}\n"
                    # Limit to first 10 songs to avoid embed field limits
                    if i >= 10:
                        queue_text += f"\n... and {len(queue_list) - 10} more songs"
                        break
                
                embed.add_field(
                    name=f"Up Next ({len(queue_list)} songs):",
                    value=queue_text,
                    inline=False
                )
            else:
                embed.add_field(
                    name="Up Next:",
                    value="No songs in queue",
                    inline=False
                )
            
            # Add queue info
            total_songs = len(queue_list)
            radio_status = "Enabled 📻" if queue.radio_mode else "Disabled"
            embed.set_footer(text=f"Total songs in queue: {total_songs} | Radio mode: {radio_status}")

            await interaction.response.send_message(embed=embed)
            
        except Exception as e:
            logger.error(f"Error in queue command: {e}")
            await interaction.response.send_message("❌ An error occurred while displaying the queue.", ephemeral=True)

    @app_commands.command(name='stop', description='Stop playback and clear the queue')
    async def slash_stop(self, interaction: discord.Interaction):
        """Stop playback and clear the queue"""
        try:
            voice_client = self.voice_clients.get(interaction.guild_id)
            queue = self.get_queue(interaction.guild_id)

            if not voice_client or not voice_client.is_playing():
                await interaction.response.send_message("❌ No music is currently playing!", ephemeral=True)
                return

            queue.clear()
            voice_client.stop()

            embed = discord.Embed(
                title="⏹️ Playback Stopped",
                description="The queue has been cleared and playback has stopped.",
                color=0xff0000
            )
            await interaction.response.send_message(embed=embed)

        except Exception as e:
            logger.error(f"Error in stop command: {e}")
            await interaction.response.send_message("❌ An error occurred while stopping playback.", ephemeral=True)

    @app_commands.command(name='volume', description='Adjust the playback volume (0-100)')
    @app_commands.describe(level='Volume level (0-100)')
    async def slash_volume(self, interaction: discord.Interaction, level: int):
        """Adjust the playback volume"""
        try:
            if level < 0 or level > 100:
                await interaction.response.send_message("❌ Volume must be between 0 and 100!", ephemeral=True)
                return

            voice_client = self.voice_clients.get(interaction.guild_id)
            if not voice_client or not voice_client.is_playing():
                await interaction.response.send_message("❌ No music is currently playing!", ephemeral=True)
                return

            # Convert to float between 0.0 and 1.0
            volume_level = level / 100.0

            if hasattr(voice_client.source, 'volume'):
                voice_client.source.volume = volume_level

            embed = discord.Embed(
                title="🔊 Volume Adjusted",
                description=f"Volume set to **{level}%**",
                color=0x00ff00
            )
            await interaction.response.send_message(embed=embed)

        except Exception as e:
            logger.error(f"Error in volume command: {e}")
            await interaction.response.send_message("❌ An error occurred while adjusting volume.", ephemeral=True)

    @app_commands.command(name='disconnect', description='Disconnect the bot from voice channel')
    async def slash_disconnect(self, interaction: discord.Interaction):
        """Disconnect the bot from voice channel"""
        try:
            voice_client = self.voice_clients.get(interaction.guild_id)
            queue = self.get_queue(interaction.guild_id)

            if not voice_client or not voice_client.is_connected():
                await interaction.response.send_message("❌ I'm not connected to a voice channel!", ephemeral=True)
                return

            queue.clear()
            voice_client.stop()
            await voice_client.disconnect()
            del self.voice_clients[interaction.guild_id]

            embed = discord.Embed(
                title="🔌 Disconnected",
                description="Disconnected from the voice channel and cleared the queue.",
                color=0xff0000
            )
            await interaction.response.send_message(embed=embed)

        except Exception as e:
            logger.error(f"Error in disconnect command: {e}")
            await interaction.response.send_message("❌ An error occurred while disconnecting.", ephemeral=True)

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

    @app_commands.command(name='clearcache', description='Clear the music cache (admin only)')
    @app_commands.default_permissions(administrator=True)
    async def slash_clearcache(self, interaction: discord.Interaction):
        """Clear the music cache"""
        try:
            deleted_count = 0
            total_size = 0

            for file_path in glob.glob(os.path.join(CACHE_DIR, "*")):
                if os.path.isfile(file_path) and not file_path.endswith(('.part', '.json')) and 'yt_dlp_cache' not in file_path:
                    try:
                        file_size = os.path.getsize(file_path)
                        os.remove(file_path)
                        deleted_count += 1
                        total_size += file_size
                    except Exception as e:
                        logger.error(f"Error deleting cache file {file_path}: {e}")

            embed = discord.Embed(
                title="🗑️ Cache Cleared",
                description=f"Removed {deleted_count} files and freed {total_size / (1024*1024):.2f} MB",
                color=0x00ff00
            )
            await interaction.response.send_message(embed=embed)

        except Exception as e:
            logger.error(f"Error in clearcache command: {e}")
            await interaction.response.send_message("❌ An error occurred while clearing the cache.", ephemeral=True)

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