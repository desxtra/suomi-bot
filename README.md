# Character.AI Suomi KP-31 Discord Bot

A Discord bot that brings Suomi Kp-31 to your Discord server and provides tools for managing the Gunsmoke Frontline event.

## Features

<<<<<<< HEAD
- Chat with Suomi directly in Discord
- Maintain conversation context per user
- Support for mentions, direct messages, and commands
- Easy setup with environment variables
- Gunsmoke Reminder
- Important Sheets
=======
- **Chat with Suomi**: Engage in conversations with Suomi Kp-31 directly in Discord
- **Maintain conversation context**: The bot remembers conversation history for each user
- **Multiple interaction methods**: Chat via mentions, direct messages, or commands
- **Gunsmoke Frontline Management**: Set up reminders and track the event schedule
- **Google Sheets Integration**: Quick access to important event information
>>>>>>> 259b11f62c6aa23e14f2fbfd897039e273ba8835

## Setup Instructions

### 1. Discord Bot Setup

1. Go to [Discord Developer Portal](https://discord.com/developers/applications)
2. Create a new application
3. Go to the "Bot" section and create a bot
4. Copy the bot token (you'll need this for `DISCORD_TOKEN`)
5. **Important**: Go to "Bot" settings and enable "Message Content Intent" under "Privileged Gateway Intents"
6. Go to "OAuth2" > "URL Generator":
   - Select "bot" scope
   - Select permissions: "Send Messages", "Read Message History", "Use Slash Commands"
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

## Basic Usage

Once the bot is running and invited to your server:

### Chatting with Suomi

- **Send a DM**: Just message the bot directly
- **Mention the bot**: @Suomi KP-31 followed by your message
- **Use commands**:
  - `/chat <message>` - Chat with Suomi
  - `/ai <message>` - Alternative chat command

### Managing Conversations

- `/reset` - Reset your conversation history with Suomi
- `/help` - Show help information

## Gunsmoke Frontline Management

The bot provides tools to help manage the Gunsmoke Frontline event, including:

- **Automatic reminders**: Get notified about event start, end, and reset times
- **Event status**: Check the current status of the event
- **Channel management**: Set up channels for event notifications

### Commands

- `/gunsmoke status` - Check the current Gunsmoke status
- `/gunsmoke enable` - Enable the reminder system
- `/gunsmoke disable` - Disable the reminder system
- `/gunsmoke set_start <date>` - Set the start date (YYYY-MM-DD format)
- `/gunsmoke add_channel <channel>` - Add a channel for notifications
- `/gunsmoke remove_channel <channel>` - Remove a channel from notifications
- `/gunsmoke list_channels` - List all notification channels

### Google Sheets Integration

- `/sheets` - Get a direct link to the Gunsmoke Frontline Google Sheet

## How it Works

The bot maintains separate conversation contexts for each user, so everyone can have their own ongoing conversation with the Character.AI character. Messages are processed through the Character.AI API and responses are sent back to Discord.

The Gunsmoke Frontline management system uses a configuration file to track event dates and notification channels. The bot checks the event status periodically and sends appropriate notifications to configured channels.

## Troubleshooting

**Bot not responding to messages:**
- Make sure "Message Content Intent" is enabled in the Discord Developer Portal
- Restart the bot after enabling the intent

**Character.AI errors:**
- Verify your CHARACTERAI_TOKEN and CHARACTER_ID are correct
- Try using the `/reset` command to start a fresh conversation

**Bot offline:**
- Check that DISCORD_TOKEN is valid and the bot is invited to your server

**Gunsmoke reminders not working:**
- Make sure the reminder system is enabled with `/gunsmoke enable`
- Verify you've set a start date with `/gunsmoke set_start`
- Check that notification channels are properly configured

## Files

- `bot.py` - Main bot code
- `.env.example` - Example environment variables file```

bot.py
