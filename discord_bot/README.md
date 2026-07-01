# dotx Discord Bot

Features:

- **Auto-role** on join (assigns role(s) automatically)
- **Welcome / leave** cards with banner + avatar
- **Support tickets** with button panel, private channels, and close button
- **24/7 hosting** on Railway (see below)

## Discord setup

1. Create a bot at [Discord Developer Portal](https://discord.com/developers/applications).
2. Enable **Server Members Intent** and **Message Content Intent**.
3. Invite the bot with permissions:
   - Manage Channels
   - Manage Roles
   - Send Messages
   - Embed Links
   - Attach Files
   - Read Message History
   - Use Slash Commands
4. Create a **Tickets** category in your server.
5. (Optional) Create a `#ticket-logs` channel for open/close logs.

## Local config

Copy `config.example.json` to `config.json` and fill in:

| Field | Description |
|-------|-------------|
| `token` | Bot token |
| `guild_id` | Your server ID |
| `welcome_channel_id` | Welcome messages channel |
| `leave_channel_id` | Leave messages channel |
| `ticket_category_id` | Category where ticket channels are created |
| `ticket_staff_role_ids` | Role IDs that can close any ticket |
| `ticket_log_channel_id` | Logs when tickets open/close |
| `auto_role_ids` | Role ID(s) given automatically when someone joins |
| `brand.banner_url` | Image URL for welcome/leave banner (Discord CDN link works) |
| `brand.logo_url` | Optional logo URL (for future use) |

Install and run from repo root:

```bash
python -m pip install -r discord_bot/requirements.txt
python -m discord_bot.bot
```

## Ticket commands

- `/ticket-panel` — post the Open Ticket button panel (Manage Server)
- `!ticketpanel` — same as above (prefix command)

Users click **Open Ticket** → private channel is created.  
Staff or the ticket owner can click **Close Ticket** to delete the channel.

## Deploy on Railway (24/7)

1. Push this repo to GitHub.
2. Go to [railway.app](https://railway.app) → **New Project** → **Deploy from GitHub**.
3. Select this repository.
4. Set **Root Directory** to the repo root (not `web/`).
5. Add these **Variables**:

```
DISCORD_BOT_TOKEN=your_bot_token
DISCORD_GUILD_ID=your_server_id
DISCORD_WELCOME_CHANNEL_ID=welcome_channel_id
DISCORD_LEAVE_CHANNEL_ID=leave_channel_id
DISCORD_TICKET_CATEGORY_ID=ticket_category_id
DISCORD_TICKET_STAFF_ROLE_IDS=role_id_1,role_id_2
DISCORD_TICKET_LOG_CHANNEL_ID=log_channel_id
DISCORD_AUTO_ROLE_IDS=role_id_1,role_id_2
BOT_STATE_PATH=/tmp/state.json
```

6. Railway will use `Procfile` / `nixpacks.toml` to run:

```bash
python -m discord_bot.bot
```

7. Deploy — the bot stays online 24/7 and restarts on failure.

### Quick deploy from Windows

After `railway login` and `railway link` once, double-click or run from repo root:

```bat
push-railway.bat
```

This uploads your latest code with `railway up --detach`.

### Railway notes

- Do **not** commit `config.json` with your real token; use Railway env vars.
- `BOT_STATE_PATH=/tmp/state.json` keeps ticket state between restarts on the same instance (ephemeral). For persistent ticket mapping across redeploys, attach a Railway volume and set `BOT_STATE_PATH=/data/state.json`.
- After first deploy, run `/ticket-panel` in your support channel once.
