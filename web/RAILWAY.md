# Railway (API + bot only)

Railway **does not host your public website** anymore. See **[DEPLOY.md](../DEPLOY.md)** for the full setup.

## What Railway runs

- **Discord bot** (welcome, leave, tickets, auto-role)
- **API + data** (`serve.py` with `API_ONLY=1`) — pins, scans, users, PC Check download
- **Persistent storage** — attach a Volume at `/data`

## Deploy

Double-click **`push-railway.bat`** (API + bot only).

For website changes, use **`push-github.bat`**.

To update both after any change: **`push-all.bat`**.

## Railway domain

Use your Railway domain only for:

- `apiBaseUrl` in `web/js/config.js`
- PC Check tool download URL (served from Railway)

Discord OAuth redirect must point to **GitHub Pages** (`callback.html`), not Railway.
