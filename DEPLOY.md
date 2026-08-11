# Deploy dotx

| What | Where |
|------|--------|
| Website | GitHub Pages (`dotx.store`) |
| Licenses / users / pins | **Supabase database** |
| Discord bot | Your PC (`watch-bot.bat`) — writes to Supabase |

The Discord bot **must** use `SUPABASE_SERVICE_ROLE_KEY` so licenses unlock on the website.

---

## 1. Supabase (database)

1. [Supabase SQL Editor](https://supabase.com/dashboard/project/bumuisxrzbteeymzeidh/sql) → run:
   - `supabase/schema.sql`
   - `supabase/rpc.sql`
   - `supabase/fix_register_preserve_license.sql`
2. **Settings → API Keys** → copy **secret** key (`sb_secret_…`) or legacy **service_role** JWT
   - Paste into `deploy.config.json` as `supabaseServiceRoleKey`
3. Bot needs `supabase>=2.16` (handles new `sb_secret_` keys). Install with Python 3.12:
   `py -3.12 -m pip install -r requirements.txt`
3. Put it in `deploy.config.json`:

```json
{
  "supabaseUrl": "https://bumuisxrzbteeymzeidh.supabase.co",
  "supabaseAnonKey": "<anon key>",
  "supabaseServiceRoleKey": "<service_role key>"
}
```

Without `supabaseServiceRoleKey`, the bot cannot write licenses to the database and the site stays locked.

---

## 2. Discord bot 24/7 (local + Supabase)

Requires **Python 3.12** (`watch-bot.bat` forces it). Python 3.14 breaks discord/aiohttp (`No module named cgi`).

1. Fill `deploy.config.json` (service role key required)
2. Double-click **`watch-bot.bat`** and leave it open (or minimized)
3. Optional: run **`install-bot-autostart.bat`** as Administrator so it starts at Windows logon

Logs should show: `Starting Discord bot (Supabase database)...`

`/smky license` → Supabase `site_users` → user refreshes [dotx.store](https://dotx.store) → Customer unlocked.

---

## 3. Website security

- **Production deploy obfuscates all JavaScript** (`scripts/obfuscate_web.py`) — readable sources stay in the repo; GitHub Pages only gets encrypted/obfuscated `js/` files (RC4 string encoding, self-defending, anti-debug).
- Run locally: **`build-web.bat`** → outputs obfuscated site to `_site/`.
- Panel pages also load `site-guard.js` (blocks F12, right-click, copy, DevTools overlay).
- `serve.py` and `web/_headers` send CSP + anti-clickjacking headers when you self-host the API.

**Important:** browser JavaScript can always be reverse-engineered by skilled attackers — obfuscation makes stealing much harder, not impossible. HTML structure is still visible in Elements. Real protection is:
  - **Never** put `supabaseServiceRoleKey` in the website — bot/server only.
  - Supabase **RLS** + RPC checks (`license_required`, `forbidden`, Discord ID match).
  - Rotate `SITE_API_TOKEN` / `apiToken` if leaked.
  - Licenses and admin actions enforced in Supabase, not in the browser.

---

## 3. Website

`push-github.bat` after site changes. OAuth redirect: `https://dotx.store/callback/`
