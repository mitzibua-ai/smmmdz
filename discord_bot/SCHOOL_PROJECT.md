# Discord School Project Bot

Interactive bot — **no slash commands**. Double-click the `.bat` file and answer the prompts.

## How to run

1. Create a bot at [Discord Developer Portal](https://discord.com/developers/applications) and copy the **token**
2. Get your **server invite link** (right-click channel → Invite People)
3. Get your **server ID** (Developer Mode on → right-click server → Copy Server ID)
4. Double-click **`school-discord-bot.bat`** in the project folder
5. Enter when asked:
   - Discord bot token
   - Discord server invite link
   - Discord server ID
   - New server name
   - Channel name

The bot validates the invite matches the server ID, then renames the server and creates the channel.

## First time only — add bot to server

If the bot is not in your server yet, the window prints a link. Open it in your browser, add the bot, and it continues automatically (waits up to 5 minutes).

Bot needs **Manage Server** and **Manage Channels** permissions.

## Requirements

- Python 3.10+ installed
- `pip install discord.py` (the `.bat` installs this for you)
