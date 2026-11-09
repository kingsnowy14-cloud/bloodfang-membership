# BLOODFANG Membership

A separate membership website for the BLOODFANG community for The Isle: Evrima. This repository does not modify or run the existing Evrima bot or the existing website.

## Current status

- Membership landing page with six membership tiers
- Discord OAuth2 login using the `identify` scope
- Session-backed login and logout
- Health endpoint at `/health`
- Stripe checkout code is present; live payments stay disabled until the Stripe secret key, webhook signing secret, and public base URL are configured
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

The production Railway service is already connected to this repository on `main`. Its start command is `bash start.sh`, which starts the Flask website, the Discord bot, and the scheduled GitHub backup worker together. The persistent Railway volume is mounted at `/data` for the SQLite databases and backups.

Production URL: https://bloodfang-membership.up.railway.app/

Keep these settings on the existing service; do not create a duplicate service for the bot.

## Environment variables

- `DISCORD_CLIENT_ID`, `DISCORD_CLIENT_SECRET`, `DISCORD_REDIRECT_URI`: Discord OAuth2 login
- `DISCORD_BOT_TOKEN`, `DISCORD_GUILD_ID`: Discord bot and role assignment
- `SESSION_SECRET`: private session-signing secret
- `PUBLIC_BASE_URL`: public website URL, currently https://bloodfang-membership.up.railway.app
- `STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET`: required together for verified Stripe checkout
- `ENABLE_TEST_PURCHASES`: must remain `false` in production
- `SHOP_API_KEY`, `GITHUB_BACKUP_TOKEN`: private bot API and backup integration

## Membership tiers

| Rank | Monthly price | Listed Bloodpoints/day | Listed storage |
|---|---:|---:|---:|
| STALKER | €4.99 | 25,000 | 5 |
| WARLORD | €12.99 | 100,000 | 8 |
| APEX | €19.99 | 200,000 | 9 |
| BLOOD EMPEROR | €29.99 | 350,000 | 10 |
| BLOOD TITAN | €50.00 | 1,000,000 | 13 |
| BLOOD GOD | €120.00 | 2,000,000 | 20 |

## Security and scope

- Never commit bot tokens, Discord secrets, PayPal secrets, or session secrets.
- OAuth state is checked on callback to reduce CSRF risk.
- Stripe checkout is implemented, but the website only exposes payment forms when the secret key, webhook signing secret, and public base URL are all present.
- Membership roles are assigned only after a verified Stripe payment webhook. Test purchases are disabled in production.
- The points shop is a preview only; point checkout and automatic delivery are not implemented.


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

- `!membership` — all six membership ranks, monthly prices, one-time prices, and listed benefits.
- `!pointshop` — the same eight points packages shown on the website:
    - 2,500,000 points — €10
  - 6,500,000 points — €25
  - 16,500,000 points — €55
  - 45,000,000 points — €115
  - 150,000,000 points — €230
  - 300,000,000 points — €350
  - 500,000,000 points — €500
  - 750,000,000 points — €750
  
The website `/points-shop` and the bot `!pointshop` command display the same seven packages. The €5 / 750,000-point package has been removed. Point-pack checkout and automatic delivery remain disabled until payment and point-delivery integration is implemented.

### Run the Discord bot on Railway

Run the bot as a **separate Railway service** from the website service, using this same repository:

1. Add a new service from this GitHub repository.
2. Set its start command to `python bot.py`.
3. Add `DISCORD_BOT_TOKEN` to that bot service's Variables. Do not paste the token into source code.
4. In Discord Developer Portal → your application → **Bot** → **Privileged Gateway Intents**, enable **Message Content Intent** and save.
5. Ensure the bot is invited to your server with permission to read messages, send messages, embed links, and send direct messages.
6. Deploy the bot service and test `!membership` and `!pointshop` in a server text channel.

Users must allow DMs from server members for the bot to send their offers. The commands display the prices and benefits configured in `bot.py`; update those values if the website's prices or benefits change.
