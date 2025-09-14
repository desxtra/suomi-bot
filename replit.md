# Overview

A Discord bot that integrates with Character.AI to bring AI character conversations directly to Discord servers. The bot allows users to chat with Character.AI personalities through Discord mentions, direct messages, and slash commands while maintaining conversation context per user.

# User Preferences

Preferred communication style: Simple, everyday language.

# System Architecture

## Bot Framework
- **Discord.py Library**: Uses the discord.py library for Discord API interactions with command extensions
- **Event-Driven Architecture**: Responds to Discord events (messages, mentions) and user commands
- **Slash Commands**: Implements modern Discord slash commands alongside traditional prefix commands
- **Intent Management**: Configurable message content intents for different deployment scenarios

## Conversation Management
- **Per-User Context**: Maintains separate conversation sessions for each user using in-memory storage
- **Session Persistence**: Stores chat contexts in a dictionary keyed by user ID to maintain conversation continuity
- **Context Reset**: Provides functionality to reset individual user conversation histories

## Command Structure
- **Multiple Interaction Methods**: Supports bot mentions, direct messages, and explicit commands
- **Command Variety**: Implements both traditional prefix commands (!chat, !ai, !reset_chat) and slash commands
- **Help System**: Built-in help command to guide users on bot usage

## Authentication & Security
- **Token-Based Authentication**: Separate authentication tokens for Discord bot and Character.AI service
- **Environment Variable Configuration**: Secure credential management through environment variables
- **Graceful Degradation**: Bot functions even without Character.AI token (with limited functionality)

## Error Handling & Logging
- **Comprehensive Logging**: Python logging module integration for debugging and monitoring
- **Exception Management**: Try-catch blocks around critical operations like authentication and command syncing
- **Startup Validation**: Validates and reports on service initialization status

# External Dependencies

## Discord Integration
- **Discord Developer Portal**: Bot registration and permission management
- **Discord.py Library**: Python wrapper for Discord API
- **Required Permissions**: Send Messages, Read Message History, Use Slash Commands
- **Privileged Intents**: Optional Message Content Intent for enhanced functionality

## Character.AI Integration
- **PyCharacterAI Library**: Python client for Character.AI API interactions
- **Character.AI Platform**: Third-party AI service for character conversations
- **Authentication Token**: Browser-extracted token for API access
- **Character Selection**: Configurable character ID for personality selection

## Development Environment
- **Python Environment**: Python runtime with async/await support
- **Environment Management**: python-dotenv for local development configuration
- **Replit Secrets**: Secure environment variable storage for production deployment

## Configuration Dependencies
- **DISCORD_TOKEN**: Bot authentication token from Discord Developer Portal
- **CHARACTERAI_TOKEN**: User authentication token from Character.AI platform
- **CHARACTER_ID**: Specific character identifier for AI personality selection