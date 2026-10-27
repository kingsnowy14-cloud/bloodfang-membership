import os
import secrets
from urllib.parse import urlencode

import aiohttp
from flask import Flask, redirect, render_template, request, session, url_for

app = Flask(__name__)
app.secret_key = os.environ.get("SESSION_SECRET") or secrets.token_hex(32)

DISCORD_CLIENT_ID = os.environ.get("DISCORD_CLIENT_ID", "")
DISCORD_CLIENT_SECRET = os.environ.get("DISCORD_CLIENT_SECRET", "")
DISCORD_REDIRECT_URI = os.environ.get("DISCORD_REDIRECT_URI", "")
PUBLIC_BASE_URL = os.environ.get("PUBLIC_BASE_URL", "").rstrip("/")
DISCORD_BOT_TOKEN = os.environ.get("DISCORD_BOT_TOKEN", "")
DISCORD_GUILD_ID = os.environ.get("DISCORD_GUILD_ID", "1561027077984227371")
ENABLE_TEST_PURCHASES = os.environ.get("ENABLE_TEST_PURCHASES", "false").lower() == "true"

TIERS = [
    {"name":"FANGBORN","emoji":"🩸","price":"2,99","points":"10.000","storage":"4"},
    {"name":"STALKER","emoji":"🦴","price":"4,99","points":"25.000","storage":"5"},
    {"name":"RAVAGER","emoji":"🐺","price":"7,99","points":"50.000","storage":"6"},
    {"name":"WARLORD","emoji":"👑","price":"12,99","points":"100.000","storage":"8"},
    {"name":"APEX","emoji":"☠️","price":"19,99","points":"200.000","storage":"9"},
    {"name":"BLOOD EMPEROR","emoji":"🔥","price":"29,99","points":"350.000","storage":"10"},
    {"name":"BLOOD TITAN","emoji":"💀","price":"50,00","points":"1.000.000","storage":"13"},
    {"name":"BLOOD GOD","emoji":"👹","price":"100,00","points":"1.600.000","storage":"20"},
]

POINT_PACKAGES = [
    {"points":"2.500.000","price":"10,00","featured":False},
    {"points":"6.500.000","price":"25,00","featured":False},
    {"points":"16.500.000","price":"55,00","featured":True},
    {"points":"45.000.000","price":"115,00","featured":False},
    {"points":"150.000.000","price":"230,00","featured":False},
    {"points":"300.000.000","price":"350,00","featured":False},
]

@app.get("/")
def index():
    return render_template("index.html", tiers=TIERS, points=POINT_PACKAGES, user=session.get("discord_user"))

@app.get("/points-shop")
def points_shop():
    return render_template("points.html", points=POINT_PACKAGES, user=session.get("discord_user"))

@app.get("/login")
def login():
    if not DISCORD_CLIENT_ID or not DISCORD_REDIRECT_URI:
        return render_template("message.html", title="Login is not configured yet",
                               message="Discord OAuth2 variables must be configured in Railway first."), 503
    state = secrets.token_urlsafe(24)
    session["oauth_state"] = state
    params = {
        "client_id": DISCORD_CLIENT_ID,
        "redirect_uri": DISCORD_REDIRECT_URI,
        "response_type": "code",
        "scope": "identify",
        "state": state,
    }
    return redirect("https://discord.com/oauth2/authorize?" + urlencode(params))

@app.get("/callback")
def callback():
    code = request.args.get("code")
    state = request.args.get("state")
    if not code or not state or not secrets.compare_digest(state, session.pop("oauth_state", "")):
        return render_template("message.html", title="Login failed",
                               message="The Discord sign-in was invalid or has expired."), 400
    if not DISCORD_CLIENT_ID or not DISCORD_CLIENT_SECRET or not DISCORD_REDIRECT_URI:
        return render_template("message.html", title="Login is not configured",
                               message="Please check the Discord OAuth2 variables in Railway."), 503
    try:
        import asyncio
        user = asyncio.run(fetch_discord_user(code))
    except Exception:
        app.logger.exception("Discord OAuth callback failed")
        return render_template("message.html", title="Login failed",
                               message="Could not reach Discord. Please try again later."), 502
    session["discord_user"] = user
    return redirect(url_for("index"))

async def fetch_discord_user(code):
    async with aiohttp.ClientSession() as client:
        async with client.post("https://discord.com/api/oauth2/token", data={
            "client_id": DISCORD_CLIENT_ID,
            "client_secret": DISCORD_CLIENT_SECRET,
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": DISCORD_REDIRECT_URI,
        }, headers={"Content-Type": "application/x-www-form-urlencoded"}) as response:
            if response.status != 200:
                raise RuntimeError("Discord token exchange rejected")
            token_data = await response.json()
        async with client.get("https://discord.com/api/users/@me",
                              headers={"Authorization": f"Bearer {token_data['access_token']}"}) as response:
            if response.status != 200:
                raise RuntimeError("Discord user lookup rejected")
            data = await response.json()
    return {"id": data["id"], "username": data["username"],
            "global_name": data.get("global_name") or data["username"],
            "avatar": data.get("avatar")}

@app.route("/checkout/<tier_name>", methods=["GET", "POST"])
def checkout(tier_name):
    user = session.get("discord_user")
    if not user:
        return redirect(url_for("login"))
    tier = next((t for t in TIERS if t["name"].lower().replace(" ", "-") == tier_name), None)
    if not tier:
        return render_template("message.html", title="Rank not found", message="This membership rank does not exist."), 404
    if request.method == "GET":
        session["checkout_csrf"] = secrets.token_urlsafe(24)
        return render_template("message.html", title="Membership checkout", tier=tier, user=user,
                               test_mode=ENABLE_TEST_PURCHASES, csrf_token=session["checkout_csrf"],
                               payment_mode=True, paypal_enabled=bool(PAYPAL_CLIENT_ID and PAYPAL_CLIENT_SECRET))
    submitted_token = request.form.get("csrf_token", "")
    saved_token = session.pop("checkout_csrf", "")
    if not submitted_token or not saved_token or not secrets.compare_digest(submitted_token, saved_token):
        return render_template("message.html", title="Checkout expired", message="Please return and try again."), 400
    purchase_type = request.form.get("purchase_type", "subscription")
    provider = request.form.get("provider", "").lower()
    if purchase_type not in ("one_time", "subscription"):
        return render_template("message.html", title="Invalid purchase type", message="Choose a one-time purchase or monthly subscription."), 400
    if provider != "paypal":
        return render_template("message.html", title="Invalid payment provider", message="Only PayPal payments are supported."), 400
    if not PUBLIC_BASE_URL:
        return render_template("message.html", title="Website URL missing", message="Set PUBLIC_BASE_URL in Railway to your public https:// website URL."), 503
    if not DISCORD_BOT_TOKEN or not DISCORD_GUILD_ID:
        return render_template("message.html", title="Discord role assignment is not configured", message="Set DISCORD_BOT_TOKEN and DISCORD_GUILD_ID in Railway."), 503
    if ENABLE_TEST_PURCHASES and request.form.get("test_purchase") == "yes":
        import asyncio
        try:
            asyncio.run(assign_membership_role(user["id"], tier["name"]))
            save_purchase(user["id"], tier["name"], "test-" + secrets.token_hex(8), purchase_type,
                          int(time.time()) + 30 * 86400 if purchase_type in ("subscription", "one_time") else None, "test")
        except Exception as exc:
            app.logger.exception("Test role assignment failed")
            return render_template("message.html", title="Could not activate test membership", message=str(exc)), 502
        return render_template("message.html", title="Test membership activated",
                               message=f"TEST ONLY: {tier['name']} role assigned. No payment was taken.")
    try:
        import asyncio
        checkout_url = asyncio.run(create_paypal_checkout(user, tier, purchase_type))
    except Exception as exc:
        app.logger.exception("Could not create %s checkout", provider)
        return render_template("message.html", title="Checkout could not be started", message=str(exc)), 502
    return redirect(checkout_url)


async def assign_membership_role(user_id, tier_name):
    headers = {"Authorization": f"Bot {DISCORD_BOT_TOKEN}", "Content-Type": "application/json"}
    base_url = "https://discord.com/api/v10"
    timeout = aiohttp.ClientTimeout(total=15)
    async with aiohttp.ClientSession(timeout=timeout) as client:
        async with client.get(f"{base_url}/guilds/{DISCORD_GUILD_ID}/roles", headers=headers) as response:
            if response.status != 200:
                raise RuntimeError(f"Discord could not list server roles (HTTP {response.status}). Check bot token and server access.")
            roles = await response.json()
        role = next((r for r in roles if r.get("name", "").casefold() == tier_name.casefold()), None)
        if not role:
            raise RuntimeError(f"The Discord role '{tier_name}' does not exist. Create it first.")
        async with client.put(f"{base_url}/guilds/{DISCORD_GUILD_ID}/members/{user_id}/roles/{role['id']}",
                              headers=headers, json={}) as response:
            if response.status in (200, 204):
                return
            if response.status == 404:
                raise RuntimeError("Your Discord account must already be a member of the BLOODFANG server.")
            if response.status == 403:
                raise RuntimeError("The bot needs Manage Roles and its highest role must be above the membership role.")
            raise RuntimeError(f"Discord rejected role assignment (HTTP {response.status}).")


async def remove_membership_role(user_id, tier_name):
    headers = {"Authorization": f"Bot {DISCORD_BOT_TOKEN}"}
    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=15)) as client:
        async with client.get(f"https://discord.com/api/v10/guilds/{DISCORD_GUILD_ID}/roles", headers=headers) as response:
            if response.status != 200:
                raise RuntimeError(f"Discord role lookup failed (HTTP {response.status}).")
            roles = await response.json()
        role = next((r for r in roles if r.get("name", "").casefold() == tier_name.casefold()), None)
        if not role:
            return
        async with client.delete(f"https://discord.com/api/v10/guilds/{DISCORD_GUILD_ID}/members/{user_id}/roles/{role['id']}",
                                headers=headers) as response:
            if response.status not in (200, 204, 404):
                raise RuntimeError(f"Discord rejected role removal (HTTP {response.status}).")


import sqlite3
import time
import hmac
import hashlib
import json
from apscheduler.schedulers.background import BackgroundScheduler

DB_PATH = os.environ.get("MEMBERSHIP_DB_PATH", "/data/membership.sqlite3")
PAYPAL_CLIENT_ID = os.environ.get("PAYPAL_CLIENT_ID", "")
PAYPAL_CLIENT_SECRET = os.environ.get("PAYPAL_CLIENT_SECRET", "")
PAYPAL_WEBHOOK_ID = os.environ.get("PAYPAL_WEBHOOK_ID", "")
PAYPAL_MODE = os.environ.get("PAYPAL_MODE", "sandbox").lower()
PAYPAL_API = "https://api-m.paypal.com" if PAYPAL_MODE == "live" else "https://api-m.sandbox.paypal.com"


def db_connect():
    os.makedirs(os.path.dirname(DB_PATH) or ".", exist_ok=True)
    connection = sqlite3.connect(DB_PATH, timeout=15)
    connection.row_factory = sqlite3.Row
    return connection


def init_db():
    with db_connect() as db:
        db.execute("""CREATE TABLE IF NOT EXISTS memberships (
            id INTEGER PRIMARY KEY AUTOINCREMENT, user_id TEXT NOT NULL, tier_name TEXT NOT NULL,
            provider TEXT NOT NULL, provider_ref TEXT NOT NULL UNIQUE, purchase_type TEXT NOT NULL,
            status TEXT NOT NULL, expires_at INTEGER, created_at INTEGER NOT NULL,
            last_event TEXT
        )""")
        db.execute("CREATE INDEX IF NOT EXISTS idx_memberships_expiry ON memberships(status, purchase_type, expires_at)")


def save_purchase(user_id, tier_name, provider_ref, purchase_type, expires_at, provider):
    now = int(time.time())
    with db_connect() as db:
        db.execute("""INSERT INTO memberships(user_id,tier_name,provider,provider_ref,purchase_type,status,expires_at,created_at)
                      VALUES(?,?,?,?,?,'active',?,?) ON CONFLICT(provider_ref) DO UPDATE SET
                      status='active', expires_at=excluded.expires_at, last_event=NULL""",
                   (str(user_id), tier_name, provider, str(provider_ref), purchase_type, expires_at, now))


async def paypal_access_token(client):
    if not PAYPAL_CLIENT_ID or not PAYPAL_CLIENT_SECRET:
        raise RuntimeError("PayPal is not configured: set PAYPAL_CLIENT_ID and PAYPAL_CLIENT_SECRET.")
    async with client.post(PAYPAL_API + "/v1/oauth2/token", data={"grant_type": "client_credentials"},
                           auth=aiohttp.BasicAuth(PAYPAL_CLIENT_ID, PAYPAL_CLIENT_SECRET)) as response:
        data = await response.json()
        if response.status >= 300:
            raise RuntimeError("PayPal OAuth failed. Check credentials and PAYPAL_MODE.")
        return data["access_token"]


async def create_paypal_checkout(user, tier, purchase_type):
    async with aiohttp.ClientSession() as client:
        token = await paypal_access_token(client)
        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
        custom_id = json.dumps({"user_id": str(user["id"]), "tier": tier["name"], "type": purchase_type})
        if purchase_type == "one_time":
            payload = {"intent": "CAPTURE", "purchase_units": [{
                "custom_id": custom_id, "description": "BLOODFANG " + tier["name"],
                "amount": {"currency_code": "EUR", "value": tier["price"].replace(",", ".")}
            }], "application_context": {"return_url": PUBLIC_BASE_URL + "/paypal/return",
                                         "cancel_url": PUBLIC_BASE_URL + "/checkout/" + tier["name"].lower().replace(" ", "-")}}
            async with client.post(PAYPAL_API + "/v2/checkout/orders", headers=headers, json=payload) as response:
                data = await response.json()
                if response.status >= 300:
                    raise RuntimeError("PayPal order creation failed: " + str(data.get("message", "check PayPal setup")))
                return next(link["href"] for link in data["links"] if link["rel"] == "approve")
        plan_id = os.environ.get("PAYPAL_PLAN_" + tier["name"].upper().replace(" ", "_"), "")
        if not plan_id:
            raise RuntimeError("Set the PayPal monthly plan ID environment variable PAYPAL_PLAN_" + tier["name"].upper().replace(" ", "_") + " first. Create a monthly EUR plan for this tier in PayPal.")
        payload = {"plan_id": plan_id, "custom_id": custom_id,
                   "application_context": {"brand_name": "BLOODFANG", "user_action": "SUBSCRIBE_NOW",
                                           "return_url": PUBLIC_BASE_URL + "/paypal/return",
                                           "cancel_url": PUBLIC_BASE_URL + "/checkout/" + tier["name"].lower().replace(" ", "-")}}
        async with client.post(PAYPAL_API + "/v1/billing/subscriptions", headers=headers, json=payload) as response:
            data = await response.json()
            if response.status >= 300:
                raise RuntimeError("PayPal subscription creation failed: " + str(data.get("message", "check plan ID and PayPal setup")))
            return next(link["href"] for link in data["links"] if link["rel"] == "approve")


@app.get("/payment/success")
def payment_success():
    return render_template("message.html", title="Payment processing",
                           message="Thank you. Your payment is being verified. Your Discord role is assigned only after the provider confirms payment. If it does not appear shortly, contact staff.")


@app.get("/paypal/return")
def paypal_return():
    order_id = request.args.get("token")
    subscription_id = request.args.get("subscription_id")
    if not order_id and not subscription_id:
        return redirect(url_for("index"))
    import asyncio
    try:
        if order_id:
            result = asyncio.run(capture_paypal_order(order_id))
            if result:
                user_id, tier_name, ref = result
                asyncio.run(assign_membership_role(user_id, tier_name))
                save_purchase(user_id, tier_name, ref, "one_time", int(time.time()) + 30 * 86400, "paypal")
                return render_template("message.html", title="Purchase complete",
                                       message=f"Your {tier_name} role has been activated. This was a one-time purchase.")
        return render_template("message.html", title="Subscription pending",
                               message="PayPal is confirming your subscription. Your role will be activated after a verified payment webhook.")
    except Exception:
        app.logger.exception("PayPal return processing failed")
        return render_template("message.html", title="Payment verification pending",
                               message="We could not verify the payment yet. Please contact staff before paying again."), 502


async def capture_paypal_order(order_id):
    async with aiohttp.ClientSession() as client:
        token = await paypal_access_token(client)
        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
        async with client.post(f"{PAYPAL_API}/v2/checkout/orders/{order_id}/capture", headers=headers, json={}) as response:
            data = await response.json()
            if response.status >= 300 and data.get("status") != "COMPLETED":
                raise RuntimeError("PayPal capture was not successful.")
        unit = data.get("purchase_units", [{}])[0]
        custom = json.loads(unit.get("payments", {}).get("captures", [{}])[0].get("custom_id") or unit.get("custom_id") or "{}")
        if data.get("status") != "COMPLETED" or not custom.get("user_id") or not custom.get("tier"):
            return None
        return str(custom["user_id"]), custom["tier"], "paypal-order-" + order_id


async def verify_paypal_webhook(headers, event):
    if not PAYPAL_WEBHOOK_ID:
        return False
    async with aiohttp.ClientSession() as client:
        token = await paypal_access_token(client)
        payload = {"auth_algo": headers.get("PAYPAL-AUTH-ALGO"), "cert_url": headers.get("PAYPAL-CERT-URL"),
                   "transmission_id": headers.get("PAYPAL-TRANSMISSION-ID"), "transmission_sig": headers.get("PAYPAL-TRANSMISSION-SIG"),
                   "transmission_time": headers.get("PAYPAL-TRANSMISSION-TIME"), "webhook_id": PAYPAL_WEBHOOK_ID, "webhook_event": event}
        async with client.post(PAYPAL_API + "/v1/notifications/verify-webhook-signature",
                               headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
                               json=payload) as response:
            data = await response.json()
            return response.status == 200 and data.get("verification_status") == "SUCCESS"


@app.post("/webhooks/paypal")
def paypal_webhook():
    event = request.get_json(silent=True) or {}
    import asyncio
    try:
        if not asyncio.run(verify_paypal_webhook(request.headers, event)):
            return {"error": "invalid PayPal signature"}, 400
    except Exception:
        app.logger.exception("PayPal webhook verification failed")
        return {"error": "verification failed"}, 400
    event_type = event.get("event_type", "")
    resource = event.get("resource", {})
    if event_type == "BILLING.SUBSCRIPTION.ACTIVATED":
        custom = resource.get("custom_id") or ""
        try:
            meta = json.loads(custom)
            user_id, tier_name = str(meta["user_id"]), meta["tier"]
            sub_id = str(resource["id"])
            # Activation alone is not proof that the first billing payment succeeded.
            with db_connect() as db:
                db.execute("""INSERT INTO memberships(user_id,tier_name,provider,provider_ref,purchase_type,status,expires_at,created_at)
                              VALUES(?,?, 'paypal', ?, 'subscription','pending',NULL,?)
                              ON CONFLICT(provider_ref) DO NOTHING""",
                           (user_id, tier_name, "paypal-sub-" + sub_id, int(time.time())))
        except Exception:
            app.logger.exception("Could not activate PayPal subscription")
            return {"error": "activation failed"}, 500
    elif event_type in ("PAYMENT.SALE.COMPLETED", "PAYMENT.CAPTURE.COMPLETED"):
        # For subscriptions, a completed sale extends the access window from its payment time.
        billing_agreement_id = resource.get("billing_agreement_id") or resource.get("supplementary_data", {}).get("related_ids", {}).get("subscription_id")
        if billing_agreement_id:
            provider_ref = "paypal-sub-" + str(billing_agreement_id)
            with db_connect() as db:
                row = db.execute("SELECT user_id,tier_name FROM memberships WHERE provider_ref=?", (provider_ref,)).fetchone()
            if row:
                expires_at = int(time.time()) + 30 * 86400
                import asyncio
                try:
                    asyncio.run(assign_membership_role(row["user_id"], row["tier_name"]))
                    with db_connect() as db:
                        db.execute("UPDATE memberships SET status='active', expires_at=?, last_event=? WHERE provider_ref=?",
                                   (expires_at, str(event.get("id", "")), provider_ref))
                except Exception:
                    app.logger.exception("Could not extend PayPal subscription")
                    return {"error": "activation failed"}, 500
    elif event_type in ("BILLING.SUBSCRIPTION.CANCELLED", "BILLING.SUBSCRIPTION.EXPIRED", "BILLING.SUBSCRIPTION.SUSPENDED"):
        sub_id = str(resource.get("id", ""))
        # Keep the current paid-through expiry; the expiry worker removes the role then.
        with db_connect() as db:
            db.execute("UPDATE memberships SET last_event=? WHERE provider_ref=?",
                       ("paypal-cancelled", "paypal-sub-" + sub_id))
    return {"received": True}


def expire_memberships():
    now = int(time.time())
    with db_connect() as db:
        rows = db.execute("""SELECT id,user_id,tier_name,provider_ref FROM memberships
                             WHERE status='active' AND expires_at IS NOT NULL AND expires_at<=?""",
                          (now,)).fetchall()
    import asyncio
    for row in rows:
        try:
            asyncio.run(remove_membership_role(row["user_id"], row["tier_name"]))
            with db_connect() as db:
                db.execute("UPDATE memberships SET status='expired', last_event='expiry-job' WHERE id=? AND status='active'", (row["id"],))
            app.logger.info("Expired membership role removed user=%s tier=%s", row["user_id"], row["tier_name"])
        except Exception:
            app.logger.exception("Could not expire membership id=%s; will retry", row["id"])


init_db()
_scheduler = BackgroundScheduler(daemon=True)
_scheduler.add_job(expire_memberships, "interval", minutes=5, id="expire_memberships", max_instances=1, replace_existing=True)
_scheduler.start()
@app.get("/logout")
def logout():
    session.clear()
    return redirect(url_for("index"))

@app.get("/imprint")
def imprint():
    return render_template("legal.html", page="imprint", title="Legal Notice")

@app.get("/privacy")
def privacy():
    return render_template("legal.html", page="privacy", title="Privacy Policy")

@app.get("/terms")
def terms():
    return render_template("legal.html", page="terms", title="Terms of Service")

@app.get("/withdrawal")
def withdrawal():
    return render_template("legal.html", page="withdrawal", title="Withdrawal & Cancellation")

@app.get("/health")
def health():
    return {
        "status": "ok",
        "paypal_configured": bool(PAYPAL_CLIENT_ID and PAYPAL_CLIENT_SECRET and PAYPAL_WEBHOOK_ID),
        "discord_roles_configured": bool(DISCORD_BOT_TOKEN and DISCORD_GUILD_ID),
        "database_path": DB_PATH,
    }

if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8080"))
    app.run(host="0.0.0.0", port=port)
