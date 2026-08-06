# dotx Discord Bot

Features:

- **Auto-role** on join (assigns role(s) automatically)
- **Welcome / leave** cards with banner + avatar
- **Support tickets** with button panel, private channels, and close button
- **License commands** (`smky key`, `smky license`, `smky revoke`) — stored in **Supabase**

## Discord setup

1. Create a bot at [Discord Developer Portal](https://discord.com/developers/applications).
2. Enable **Server Members Intent** and **Message Content Intent**.
3. Invite the bot with permissions: Manage Channels, Manage Roles, Send Messages, Embed Links, Read Message History, Use Slash Commands.
4. Create a **Tickets** category in your server.
5. (Optional) Create a `#ticket-logs` channel for open/close logs.

## Local config

Copy `config.example.json` to `config.json` and fill in token, guild ID, channels, and roles.

Set Supabase in `deploy.config.json` (`supabaseServiceRoleKey`) or env:

```
SUPABASE_URL=https://bumuisxrzbteeymzeidh.supabase.co
SUPABASE_SERVICE_ROLE_KEY=your_service_role_key
```

## Run the bot

From repo root:

```bat
run-bot.bat
```

Or:

```bash
python -m pip install -r requirements.txt
python run_dotx.py
```

The bot must stay running on your PC (or any server) for Discord commands and ticket buttons. Website data (pins, scans) lives in Supabase and is served by the Supabase Edge API.

## Ticket commands

- `/ticket-panel` — post the Open Ticket button panel (Manage Server)
- `!ticketpanel` — same as above (prefix command)

Users click **Open Ticket** → private channel is created.  
Staff or the ticket owner can click **Close Ticket** to delete the channel.
