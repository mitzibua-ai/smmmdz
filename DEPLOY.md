# Deploy dotx (GitHub Pages + Supabase + Railway bot)

| What | Where | How |
|------|--------|-----|
| Website | **GitHub Pages** (`dotx.store`) | `push-github.bat` |
| Database + license unlock | **Supabase** | SQL + service role |
| Discord bot **24/7** | **Railway** | Railway dashboard / `setup-railway-bot.bat` |

---

## Discord bot 24/7 (Railway + Supabase)

The bot runs in the cloud with **`SUPABASE_SERVICE_ROLE_KEY`** so `/smky license` writes to Supabase and the website unlocks Customer access. Do not rely on a PC window for production.

### One-time Railway setup

1. Go to [railway.app](https://railway.app) → **New Project** → **Deploy from GitHub** → this repo.
2. Set **Variables**:

```
DISCORD_BOT_TOKEN=<your bot token>
SUPABASE_URL=https://bumuisxrzbteeymzeidh.supabase.co
SUPABASE_SERVICE_ROLE_KEY=<Supabase service_role secret>
DISCORD_GUILD_ID=<your guild id>
DISCORD_CUSTOMER_ROLE_ID=<customer role id>
```

Optional: `DISCORD_WELCOME_CHANNEL_ID`, `DISCORD_TICKET_CATEGORY_ID`, `DISCORD_PURCHASE_LOG_CHANNEL_ID`, etc.

3. **Settings → Deploy**
   - Start command: `python start_dotx.py`
   - Restart: **Always**

4. Check **Deployments → Logs** for:  
   `Discord bot starting (Supabase = licenses / users / keys)`

Or run **`setup-railway-bot.bat`** if the Railway CLI is installed (`npm i -g @railway/cli`).

### After granting a license

1. Staff: `/smky license` (saves to Supabase `site_users`)
2. User: refresh / re-login on [dotx.store](https://dotx.store)
3. Pins / Reports / EXE customize unlock from the database

---

## Supabase

1. SQL Editor → run `supabase/schema.sql`, `supabase/rpc.sql`, `supabase/fix_register_preserve_license.sql`
2. Put **service_role** in Railway Variables (required for the bot)

---

## Website

Repo **Settings → Pages → GitHub Actions**. OAuth redirect: `https://dotx.store/callback/`

Use `push-github.bat` after site changes.

---

## Local bot (testing only)

```bash
# needs supabaseServiceRoleKey in deploy.config.json
run-bot.bat
```
