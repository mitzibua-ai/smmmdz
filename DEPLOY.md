# Deploy dotx (GitHub Pages + Supabase)

| What | Where | Push with |
|------|--------|-----------|
| Website (HTML, CSS, login) | **GitHub Pages** (`dotx.store`) | `push-github.bat` |
| PC Check `.exe` download | **GitHub Pages** (`/downloads/`) | `push-github.bat` |
| Database (pins, scans, users, licenses) | **Supabase** | `push-supabase.bat` |
| API (pins, scans, license checks) | **Supabase Edge Function** | `push-supabase.bat` |
| Discord bot | **Your PC** (local) | `run-bot.bat` |

After code changes, run **`push-all.bat`** (or **`push-supabase.bat`**) to update everything.

---

## One-time setup

### 1. Supabase database + API

1. Open [your Supabase project](https://supabase.com/dashboard/project/bumuisxrzbteeymzeidh).
2. **SQL Editor** → run **`supabase/schema.sql`**, then **`supabase/rpc.sql`**.
3. **Settings → API** → copy:
   - **anon public** key → `deploy.config.json` → `supabaseAnonKey`
   - **service_role** key → `deploy.config.json` → `supabaseServiceRoleKey`

Or double-click **`setup-supabase.bat`** — it opens the SQL Editor and API settings.

### 2. `deploy.config.json`

Copy `deploy.config.json.example` → `deploy.config.json` and fill in:

```json
{
  "githubPagesUrl": "https://mitzibua-ai.github.io/smmmdz",
  "customSiteUrl": "https://dotx.store",
  "siteApiToken": "your-random-secret",
  "supabaseUrl": "https://bumuisxrzbteeymzeidh.supabase.co",
  "supabaseServiceRoleKey": "eyJ..."
}
```

### 3. Supabase Edge Function (API)

Install the [Supabase CLI](https://supabase.com/docs/guides/cli), then:

```bash
supabase login
supabase functions deploy dotx --project-ref bumuisxrzbteeymzeidh
```

Or run **`push-supabase.bat`** — it deploys the function and sets secrets when the CLI is installed.

### 4. GitHub Pages

Repo **Settings → Pages → Source: GitHub Actions**.

Discord OAuth redirect: `https://dotx.store/callback/`

### 5. Discord bot (local)

Run **`run-bot.bat`** on your PC. The bot uses Supabase for licenses.

---

## Daily workflow

1. Edit code.
2. Run **`push-all.bat`**.
3. Verify: `https://bumuisxrzbteeymzeidh.supabase.co/functions/v1/dotx/api/health` → `{"ok":true}`

---

## Local testing

```bash
cd web
python serve.py
```

Set `SUPABASE_SERVICE_ROLE_KEY` in `web/.env` for Supabase-backed local API.
