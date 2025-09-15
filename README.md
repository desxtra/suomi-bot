# Character.AI Suomi KP-31 Discord Bot

A Discord bot that brings Suomi Kp-31 to your Discord server

## Features

- Chat with Suomi directly in Discord
- Maintain conversation context per user
- Support for mentions, direct messages, and commands
- Easy setup with environment variables
- Gunsmoke Reminder

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

### 4. Usage

Once the bot is running and invited to your server:

- **Send a DM**: Just message the bot directly
- **Use commands**:
  - `/chat <message>` - Chat with the AI
  - `/ai <message>` - Alternative chat command
  - `/help_bot` - Show help information
  - `/reset_chat` - Reset your conversation history

## How it Works

The bot maintains separate conversation contexts for each user, so everyone can have their own ongoing conversation with the Character.AI character. Messages are processed through the Character.AI API and responses are sent back to Discord.

## Troubleshooting

**Bot not responding to messages:**
- Make sure "Message Content Intent" is enabled in the Discord Developer Portal
- Restart the bot after enabling the intent

**Character.AI errors:**
- Verify your CHARACTERAI_TOKEN and CHARACTER_ID are correct
- Try using the `/reset` command to start a fresh conversation

**Bot offline:**
- Check that DISCORD_TOKEN is valid and the bot is invited to your server

## Files

- `bot.py` - Main bot code
- `.env.example` - Example environment variables file