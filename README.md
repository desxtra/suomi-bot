# Character.AI Suomi KP-31 Discord Bot

A Discord bot that brings Suomi Kp-31 to your Discord server and provides tools for managing the Gunsmoke Frontline event, plus a full-featured music player.

## Features

- **🤖 AI Chat**: Chat with Suomi directly in Discord using Character.AI
- **🎵 Music Player**: High-quality music streaming from YouTube
- **📅 Gunsmoke Reminder**: Automated event management and notifications
- **📊 Important Sheets**: Quick access to community resources
- **💬 Multiple Interaction Methods**: Slash commands, mentions, and DMs

## Setup Instructions

### 1. Discord Bot Setup

1. Go to [Discord Developer Portal](https://discord.com/developers/applications)
2. Create a new application
3. Go to the "Bot" section and create a bot
4. Copy the bot token (you'll need this for `DISCORD_TOKEN`)
5. **Important**: Go to "Bot" settings and enable:
   - "Message Content Intent" under "Privileged Gateway Intents"
   - "Server Members Intent" 
   - "Voice States" (required for music functionality)
6. Go to "OAuth2" > "URL Generator":
   - Select "bot" scope
   - Select permissions: "Send Messages", "Read Message History", "Use Slash Commands", "Connect", "Speak", "Use Voice Activity"
   - Use the generated URL to invite the bot to your server

### 2. Character.AI Setup

1. Create an account at [Character.AI](https://character.ai/)
2. Find the character you want to use and copy its Character ID from the URL
3. Get your Character.AI authentication token (this requires browser dev tools)

### 3. Environment Variables

Set up these environment variables in Replit Secrets:
- `DISCORD_TOKEN`: Your Discord bot token
- `CHARACTERAI_TOKEN`: Your Character.AI authentication token
- `CHARACTER_ID`: The ID of the Character.AI character to use

### 4. FFmpeg Installation

The music player requires FFmpeg:

**Windows:**
- Download from https://ffmpeg.org/download.html
- Add to system PATH

**Linux (Ubuntu/Debian):**
```bash
sudo apt update
sudo apt install ffmpeg
```

**macOS:**
```bash
brew install ffmpeg
```

**Replit:**
```bash
npm install @ffmpeg/ffmpeg @ffmpeg/core
```

## Basic Usage

Once the bot is running and invited to your server:

### Chatting with Suomi

- **Send a DM**: Just message the bot directly
- **Mention the bot**: @Suomi KP-31 followed by your message
- **Use commands**:
  - `/chat <message>` - Chat with Suomi
  - `/reset` - Reset your conversation history

### Music Player

- `/play <song/url>` - Play music from YouTube
- `/skip` - Skip the current song
- `/stop` - Stop music and clear queue
- `/pause` - Pause playback
- `/resume` - Resume playback
- `/queue` - Show current music queue
- `/volume <1-100>` - Adjust volume (1-100)
- `/nowplaying` - Show currently playing song
- `/disconnect` - Disconnect bot from voice channel

### Gunsmoke Frontline Management

The bot provides tools to help manage the Gunsmoke Frontline event:

- **Automatic reminders**: Get notified about event start, end, and reset times
- **Event status**: Check the current status of the event
- **Channel management**: Set up channels for event notifications

#### Commands

- `/gunsmoke status` - Check the current Gunsmoke status
- `/gunsmoke enable` - Enable the reminder system
- `/gunsmoke disable` - Disable the reminder system
- `/gunsmoke set_start <date>` - Set the start date (YYYY-MM-DD format)
- `/gunsmoke add_channel <channel>` - Add a channel for notifications
- `/gunsmoke remove_channel <channel>` - Remove a channel from notifications
- `/gunsmoke list_channels` - List all notification channels

### Utility Commands

- `/help` - Show all available commands
- `/sheets` - Get direct links to important Google Sheets
- `/reset` - Reset your AI conversation history

## File Structure

```
main.py                 # Main bot file
commands/
├── ai_chat.py         # AI chat functionality
├── gunsmoke.py        # Gunsmoke event management
├── music.py           # Music player commands
└── help.py            # Help and utility commands
```

## How it Works

### AI Chat System
- Maintains separate conversation contexts for each user
- Uses Character.AI API for realistic responses
- Supports both text commands and slash commands

### Music Player
- Streams high-quality audio from YouTube
- Supports playlists and search queries
- Automatic queue management
- Volume control and playback controls
- Auto-disconnects when alone in voice channel

### Gunsmoke Management
- Tracks event dates and schedules
- Sends automated reminders
- Configurable notification channels
- Automatic scheduling of recurring events

## Troubleshooting

**Bot not responding to messages:**
- Make sure "Message Content Intent" is enabled in the Discord Developer Portal
- Restart the bot after enabling the intent

**Music not playing:**
- Ensure FFmpeg is installed and accessible
- Check that the bot has "Connect" and "Speak" permissions in the voice channel
- Verify your internet connection can access YouTube

**Character.AI errors:**
- Verify your CHARACTERAI_TOKEN and CHARACTER_ID are correct
- Try using the `/reset` command to start a fresh conversation

**Bot offline:**
- Check that DISCORD_TOKEN is valid and the bot is invited to your server

**Gunsmoke reminders not working:**
- Make sure the reminder system is enabled with `/gunsmoke enable`
- Verify you've set a start date with `/gunsmoke set_start`
- Check that notification channels are properly configured

**Voice connection issues:**
- Ensure the bot has proper voice permissions
- Check if the voice channel is full
- Verify the bot isn't already connected to another voice channel

## Support

If you encounter any issues:
1. Check the troubleshooting section above
2. Verify all environment variables are set correctly
3. Ensure all required permissions are granted
4. Check the console logs for specific error messages

## License

This project is for community use. Please respect Discord's Terms of Service and Character.AI's usage policies.