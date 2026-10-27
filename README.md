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


## Legal launch checklist (Germany / international audience)

The legal pages in the website are **draft templates only** and do not establish legal compliance. The operator has currently indicated: Germany, private individual, no registered business, and international target audience. This does not itself determine whether the planned recurring paid membership is a trade/business or which tax, consumer, privacy, or registration duties apply.

Before accepting any payment:
- Replace every bracketed placeholder on `/imprint`, `/privacy`, `/terms`, and `/withdrawal`. Do not publish invented identity or contact details.
- Obtain advice on whether the planned ongoing paid membership requires Gewerbeanmeldung, tax registration, invoicing/VAT steps, or other formalities in Germany.
- Confirm the operator's legal name, a legally valid postal address, email and an additional direct/rapid contact method, plus any applicable register, VAT, supervisory, chamber, or media-law disclosures.
- Verify the privacy notice against GDPR Article 13, the real Discord OAuth fields/scopes, Railway/hosting logs, session-cookie settings, provider terms, retention, and any international transfers.
- Prepare accurate pre-contract information, total prices/tax treatment, recurring billing/renewal and cancellation terms, payment details, consumer withdrawal notice and statutory model form, and complaint/support contact details.
- Assess whether a German online cancellation button and confirmation process under § 312k BGB is required for the subscription model.
- Ensure all advertised benefits are actually implemented before promising them. Add no analytics, advertising cookies, payment processors, or extra data collection without updating the privacy review.
- Obtain a qualified legal/tax review for the operator's actual circumstances and the countries targeted. International targeting can trigger additional consumer and tax requirements.

Until this checklist is reviewed and all placeholders are completed, keep payment processing disabled. The website currently does not take payments.


## Discord offer DM commands

The repository also includes `bot.py`, which responds to these commands in a server and sends the offer lists to the command user's DMs:

- `!membership` — all eight membership ranks, monthly prices, one-time prices, and listed benefits.
- `!pointshop` — all points packages and prices.

### Run the Discord bot on Railway

Run the bot as a **separate Railway service** from the website service, using this same repository:

1. Add a new service from this GitHub repository.
2. Set its start command to `python bot.py`.
3. Add `DISCORD_BOT_TOKEN` to that bot service's Variables. Do not paste the token into source code.
4. In Discord Developer Portal → your application → **Bot** → **Privileged Gateway Intents**, enable **Message Content Intent** and save.
5. Ensure the bot is invited to your server with permission to read messages, send messages, embed links, and send direct messages.
6. Deploy the bot service and test `!membership` and `!pointshop` in a server text channel.

Users must allow DMs from server members for the bot to send their offers. The commands display the prices and benefits configured in `bot.py`; update those values if the website's prices or benefits change.
