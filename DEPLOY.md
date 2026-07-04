# Deploy dotx (GitHub + Railway)

Your setup uses **two hosts**:

| What | Where | Push with |
|------|--------|-----------|
| Website (HTML, CSS, login pages) | **GitHub Pages** | `push-github.bat` |
| API + stored data (pins, scans, users) | **Railway** | `push-railway.bat` |
| Discord bot | **Railway** (same service) | `push-railway.bat` |

After you change code, run **`push-all.bat`** to update both.

---

## One-time setup

### 1. GitHub repo + Pages

1. Create a repo on GitHub and push this project.
2. Repo **Settings → Pages → Build and deployment → Source: GitHub Actions** (required — deploy fails without this).
3. Your site URL will be: `https://mitzibua-ai.github.io/smmmdz/`
4. Copy `deploy.config.json.example` → `deploy.config.json` and fill in:
   - `githubPagesUrl` — `https://mitzibua-ai.github.io/smmmdz`
   - `railwayApiUrl` — your Railway API domain (step 2 below)

**If deploy fails with "Deployment failed, try again later":**
- Confirm step 2 above (Source must be **GitHub Actions**, not "Deploy from branch").
- Open **Actions** → failed run → **Re-run all jobs**.
- First deploy sometimes needs one manual re-run after enabling Pages.

### 2. Railway (API + bot only)

1. Run **`setup-railway.bat`** once (links `proactive-nourishment`).
2. Railway → **Settings → Networking → Generate Domain** (e.g. `dotx-api.up.railway.app`).
3. Put that URL in `deploy.config.json` → `railwayApiUrl`.
4. Railway → **Volumes** → mount `/data` (keeps `store.json` across redeploys).
5. Run **`push-railway.bat`** — deploys bot + API (`API_ONLY=1`, no website files served).

### 3. Discord OAuth

Discord Developer Portal → your app → **OAuth2 → Redirects** — add your **GitHub Pages** callback:

```
https://YOUR-USERNAME.github.io/YOUR-REPO/callback.html
```

(Not the Railway URL — the website lives on GitHub now.)

### 4. `web/js/config.js`

Set `apiBaseUrl` to your Railway domain (or use `deploy.config.json`; `push-github.bat` syncs it):

```js
apiBaseUrl: "https://YOUR-RAILWAY-DOMAIN.up.railway.app",
```

PC Check tool downloads also come from Railway (`/downloads/dotx-pc-check.exe`).

---

## Discord license commands (staff only)

| Command | What it does |
|---------|----------------|
| `smky key` | Bot asks unit (months/days/hours/minutes), then amount → generates `SMKY-XXXX-XXXX` key |
| `smky license` | Bot asks customer Discord ID → key → ticket ID → grants Customer + posts receipt in ticket |
| `smky revoke` | Cancel a customer license — removes website access + Discord Customer role |
| `/smky key` | Slash version with amount + unit in one step |
| `/smky license` | Slash version with discord_id, key, and ticket in one step |
| `/smky revoke` | Slash version — pass the customer's Discord user ID |

After `smky license`, the user gets **Customer** on the website (Pins + Reports unlock). Keys are time-limited; expiry is enforced server-side. Use `smky revoke` anytime to cancel access.

---

## Daily workflow

1. Edit files in `web/` (website) and/or `discord_bot/` (bot) and `web/serve.py` (API).
2. Double-click **`push-all.bat`**.
   - Or only **`push-github.bat`** if you changed the website.
   - Or only **`push-railway.bat`** if you changed bot/API/data logic.

---

## What runs where

**GitHub Pages** serves static files only. The browser calls Railway for:

- `/api/pins`, `/api/scans`, `/api/license/...`
- Owner / Admin / Staff dashboards data
- PC Check `.exe` download

**Railway** runs `start_dotx.py`:

- Discord bot (welcome, tickets, auto-role)
- `serve.py` in API-only mode (data + downloads, no HTML)

---

## Local testing

```bash
cd web
python serve.py
```

Open `http://127.0.0.1:8080` — full site + API locally (API_ONLY is off by default).
