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

@app.get("/checkout/<tier_name>")
def checkout(tier_name):
    if not session.get("discord_user"):
        return redirect(url_for("login"))
    tier = next((tier for tier in TIERS if tier["name"].lower().replace(" ", "-") == tier_name), None)
    if not tier:
        return render_template("message.html", title="Rank not found",
                               message="This membership rank does not exist."), 404
    return render_template("message.html", title="Monthly checkout is not enabled yet",
                           message=f"You are signed in with Discord. The {tier['name']} subscription costs €{tier['price']} per month. Payments are not enabled yet; you will not be charged."), 503

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
    return {"status": "ok", "payments": "not_configured"}

if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8080"))
    app.run(host="0.0.0.0", port=port)
