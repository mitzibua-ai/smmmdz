# dotx — Discord login

Click **Login with Discord** → Discord authorize screen → **Authorize** → logged in.

dotx appears in Discord → Settings → **Authorized Apps**.

## Setup

1. https://discord.com/developers/applications → create app named **dotx**
2. OAuth2 → Redirects → add your callback URL (shown on login page when opened in browser)
3. Put **Client ID** in `js/config.js`

## Pages

- `login.html` — Discord authorize
- `callback.html` — after you approve
- `dashboard.html` — panel
