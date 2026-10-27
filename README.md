# BLOODFANG Membership

A separate membership website for the BLOODFANG community for The Isle: Evrima. This repository does not modify or run the existing Evrima bot or the existing website.

## Current status

- Membership landing page with eight proposed tiers
- Discord OAuth2 login using the `identify` scope
- Session-backed login and logout
- Health endpoint at `/health`
- PayPal and membership payments are **not implemented or enabled**
- In-game Bloodpoints and storage benefits are displayed as proposed and must not be promised until the server integration supports them

## Run locally

Python 3.11+ is recommended.

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Set environment variables from `.env` in your local shell or use a local environment loader. Do not commit real credentials. Then run:

```bash
python app.py
```

## Railway deployment

1. Create a new Railway service connected only to this repository.
2. Set the start command to `gunicorn app:app --bind 0.0.0.0:$PORT` if Railway does not detect the Procfile.
3. Generate a public domain for this service.
4. Set `SESSION_SECRET` to a long random secret.
5. Set `DISCORD_CLIENT_ID` and `DISCORD_CLIENT_SECRET` from the existing Discord application.
6. Set `DISCORD_REDIRECT_URI` to `https://YOUR-RAILWAY-DOMAIN/callback`.
7. In Discord Developer Portal → OAuth2, register that exact redirect URL.
8. Redeploy and test `/health`, then the Discord login.

Only set variables on this new service that it needs. Do not change the existing bot or website service variables.

## Environment variables

- `DISCORD_CLIENT_ID`: Discord application ID
- `DISCORD_CLIENT_SECRET`: Discord OAuth2 client secret
- `DISCORD_REDIRECT_URI`: exact OAuth callback URL ending in `/callback`
- `SESSION_SECRET`: private random session-signing secret
- `PUBLIC_BASE_URL`: public URL for this website (optional for the current starter)

## Membership tiers

| Rank | Monthly price | Proposed Bloodpoints/day | Proposed storage |
|---|---:|---:|---:|
| FANGBORN | €2.99 | 10,000 | 4 |
| STALKER | €4.99 | 25,000 | 5 |
| RAVAGER | €7.99 | 50,000 | 6 |
| WARLORD | €12.99 | 100,000 | 8 |
| APEX | €19.99 | 200,000 | 9 |
| BLOOD EMPEROR | €29.99 | 350,000 | 10 |
| BLOOD TITAN | €50.00 | 1,000,000 | 13 |
| BLOOD GOD | €100.00 | 1,600,000 | 20 |

## Security and scope

- Never commit bot tokens, Discord secrets, PayPal secrets, or session secrets.
- OAuth state is checked on callback to reduce CSRF risk.
- The website currently only identifies a Discord user; it does not grant roles or process payments.
- PayPal integration will be added separately later, starting with sandbox mode and verified webhooks.
