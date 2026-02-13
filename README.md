# Character.AI Suomi KP-31 Discord Bot

A Discord bot that brings Suomi KP-31 to your Discord server, featuring AI-powered chat, music playback, and access to community resources.

## Features

- **AI Chat System**: Direct interaction with Suomi through Discord using Character.AI
- **Music Player**: Music playback from YouTube using FFmpeg
- **Resource Access**: Quick access to community spreadsheets and resources
- **Multiple Interaction Methods**: Slash commands, mentions, and direct messages

## Setup Instructions

### 1. Discord Bot Setup

1. Go to the Discord Developer Portal  
2. Create a new application  
3. Open the **Bot** section and create a bot  
4. Copy the bot token (used for `DISCORD_TOKEN`)  
5. In **Bot Settings**, enable the following under *Privileged Gateway Intents*:
   - Message Content Intent  
   - Server Members Intent  
   - Voice States (required for music playback)
6. Go to **OAuth2 → URL Generator**:
   - Scope: `bot`
   - Permissions:
     - Send Messages
     - Read Message History
     - Use Slash Commands
     - Connect
     - Speak
     - Use Voice Activity
   - Use the generated URL to invite the bot to your server

### 2. Character.AI Setup

1. Create an account at https://character.ai  
2. Select the character you want to use  
3. Copy the **Character ID** from the character URL  
4. Obtain your Character.AI authentication token using browser developer tools  

### 3. Environment Variables

Set the following environment variables:

- `DISCORD_TOKEN` — Discord bot token  
- `CHARACTERAI_TOKEN` — Character.AI authentication token  
- `CHARACTER_ID` — Character.AI character ID  

### 4. FFmpeg Installation

FFmpeg is required for music playback.

**Linux (Debian / Ubuntu):**
```bash
sudo apt update
sudo apt install ffmpeg
````

**Windows:**

* Download from [https://ffmpeg.org/download.html](https://ffmpeg.org/download.html)
* Add FFmpeg to your system PATH

**macOS:**

```bash
brew install ffmpeg
```

## Available Commands

### AI Chat Commands

* **Direct Messages**: Send messages directly to the bot
* **Mentions**: Mention the bot followed by a message
* `/chat <message>` — Chat with Suomi
* `/reset` — Reset your AI conversation history

### Music Commands

* `/play <song | url>` — Play music from YouTube
* `/pause` — Pause playback
* `/resume` — Resume playback
* `/skip` — Skip the current track
* `/stop` — Stop playback and clear the queue
* `/queue` — Display the current music queue
* `/remove <index>` — Remove a specific track from the queue
* `/volume <1–100>` — Adjust playback volume
* `/nowplaying` — Show information about the current track
* `/disconnect` — Disconnect the bot from the voice channel

### Utility Commands

* `/help` — Display all available commands
* `/sheets` — Access community spreadsheets

## Project Structure

```
main.py                 # Main bot entry point
commands/
├── ai_chat.py          # Character.AI chat logic
├── gunsmoke.py         # Gunsmoke event management
├── music.py            # Music playback commands
└── help.py             # Help and utility commands
```

## Technical Overview

### AI Chat System

* Per-user conversation context
* Integration with the Character.AI API
* Supports direct messages, mentions, and slash commands

### Music Player

* YouTube audio streaming
* Queue-based playback system
* Playback controls and volume management
* Automatic voice channel disconnect

### Resource Management

* Quick access to community spreadsheets
* Discord slash command integration
* Centralized command handling

## Troubleshooting

**Bot does not respond:**

* Ensure Message Content Intent is enabled
* Restart the bot after changing intents

**Music does not play:**

* Verify FFmpeg is installed and accessible inside the runtime environment
* Ensure the bot has permission to connect and speak in the voice channel
* Check network access to YouTube

**Character.AI errors:**

* Verify `CHARACTERAI_TOKEN` and `CHARACTER_ID`
* Use `/reset` to clear the conversation state

**Bot appears offline:**

* Confirm `DISCORD_TOKEN` is valid
* Ensure the bot has been invited to the server

**Gunsmoke reminders not working:**

* Enable the reminder system using `/gunsmoke enable`
* Set a start date using `/gunsmoke set_start`
* Verify notification channels are configured correctly

**Voice connection issues:**

* Confirm the bot has voice permissions
* Check whether the voice channel is full
* Ensure the bot is not connected to another channel

## Support

If issues persist:

1. Review the troubleshooting section
2. Verify all environment variables
3. Check bot permissions
4. Inspect application logs for errors

## License

This project is intended for community use.
Please comply with Discord’s Terms of Service and Character.AI usage policies.