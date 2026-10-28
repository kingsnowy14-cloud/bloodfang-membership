import logging
import os
import asyncio
import random
import sqlite3
import time

import discord
import aiohttp
from discord.ext import commands, tasks

logging.basicConfig(
    level=os.environ.get("LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
log = logging.getLogger("bloodfang-bot")

TOKEN = os.environ.get("DISCORD_BOT_TOKEN", "").strip()
if not TOKEN:
    raise RuntimeError("DISCORD_BOT_TOKEN is missing. Add it to the Railway bot service variables.")

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix=[".", "!"], intents=intents, status=discord.Status.online, help_command=None)

@bot.command(name="help", aliases=["hilfe", "commands", "befehle"])
async def help_command(ctx):
    """Show all available BLOODFANG bot commands."""
    embed = discord.Embed(
        title="🩸 BLOODFANG Bot — Hilfe",
        description="Hier findest du alle verfügbaren Befehle. Prefixe: `!` oder `.`",
        color=discord.Color.dark_red(),
    )
    embed.add_field(
        name="💰 Economy",
        value=(
            "`!balance` / `!bal` / `!konto` [@User] — Kontostand anzeigen\n"
            "`!work` / `!w` — Coins verdienen (3 Stunden Cooldown)\n"
            "`!crime` / `!c` — Verbrechen versuchen (3 Stunden Cooldown)\n"
            "`!cheat` — Coins gewinnen oder verlieren (3 Stunden Cooldown)\n"
            "`!pay` / `!transfer` @User Betrag — Coins überweisen"
        ),
        inline=False,
    )
    embed.add_field(
        name="🩸 Shop & Mitgliedschaft",
        value=(
            "`!membership` — Mitgliedschafts-Ränge und Preise per DM\n"
            "`!pointshop` — Points-Pakete und Preise per DM\n"
            "`!donat` — Donation-Ränge und Storage-Boni per DM\n"
            "`/mymembership` — Eigene Mitgliedschaft prüfen"
        ),
        inline=False,
    )
    embed.add_field(
        name="🛠️ Administration",
        value="`/shoplog` — Shop-Log-Webhook einrichten (Berechtigung: Server verwalten)",
        inline=False,
    )
    embed.set_footer(text="Bei Fragen oder Problemen wende dich an das BLOODFANG-Team.")
    await ctx.send(embed=embed)

STATUS_ACTIVITIES = [
    discord.Game(name="!membership"),
    discord.Game(name="!pointshop"),
    discord.Game(name="!donat"),
]
_status_index = 0

MEMBERSHIPS = [
    ("STALKER", "€4.99", "25,000 Bloodpoints/day", "5 storage"),
    ("WARLORD", "€12.99", "100,000 Bloodpoints/day", "8 storage"),
    ("APEX", "€19.99", "200,000 Bloodpoints/day", "9 storage"),
    ("BLOOD EMPEROR", "€29.99", "350,000 Bloodpoints/day", "10 storage"),
    ("BLOOD TITAN", "€50.00", "1,000,000 Bloodpoints/day", "13 storage"),
    ("BLOOD GOD", "€120.00", "2,000,000 Bloodpoints/day", "20 storage"),
]

POINT_PACKAGES = [
    ("2,500,000", "€10.00"),
    ("6,500,000", "€25.00"),
    ("16,500,000", "€55.00"),
    ("45,000,000", "€115.00"),
    ("150,000,000", "€230.00"),
    ("300,000,000", "€350.00"),
]


# Lightweight persistent Discord economy copied from Evrima-bot.
# Mount a Railway Volume at /data, or set ECONOMY_DB to a persistent file path.
ECONOMY_DB_PATH = os.path.abspath(os.environ.get("ECONOMY_DB", "/data/economy.db"))
os.makedirs(os.path.dirname(ECONOMY_DB_PATH), exist_ok=True)
economy_db = sqlite3.connect(ECONOMY_DB_PATH, timeout=30, check_same_thread=False)
economy_db.execute("PRAGMA busy_timeout = 30000")
economy_db.execute("PRAGMA journal_mode = WAL")
economy_db.execute("CREATE TABLE IF NOT EXISTS accounts (user_id INTEGER PRIMARY KEY, balance INTEGER NOT NULL DEFAULT 100)")
economy_db.execute("""CREATE TABLE IF NOT EXISTS economy_cooldowns (
    user_id INTEGER NOT NULL, command TEXT NOT NULL, last_used REAL NOT NULL,
    PRIMARY KEY(user_id, command))""")
economy_db.commit()
ECONOMY_COOLDOWN_SECONDS = 3 * 60 * 60
ECONOMY_ACTION_MIN = 1500
ECONOMY_ACTION_MAX = 10000


def get_balance(user_id: int) -> int:
    row = economy_db.execute("SELECT balance FROM accounts WHERE user_id = ?", (user_id,)).fetchone()
    if row is None:
        with economy_db:
            economy_db.execute("INSERT OR IGNORE INTO accounts (user_id, balance) VALUES (?, 100)", (user_id,))
        row = economy_db.execute("SELECT balance FROM accounts WHERE user_id = ?", (user_id,)).fetchone()
    return int(row[0])


def change_balance(user_id: int, amount: int) -> int:
    get_balance(user_id)
    with economy_db:
        economy_db.execute("UPDATE accounts SET balance = balance + ? WHERE user_id = ?", (amount, user_id))
    return get_balance(user_id)


def cooldown_left(user_id: int, command: str) -> int:
    row = economy_db.execute("SELECT last_used FROM economy_cooldowns WHERE user_id = ? AND command = ?",
                             (user_id, command)).fetchone()
    if row is None:
        return 0
    return max(0, int(ECONOMY_COOLDOWN_SECONDS - (time.time() - row[0]) + 0.999))


def use_cooldown(user_id: int, command: str) -> None:
    with economy_db:
        economy_db.execute(
            """INSERT INTO economy_cooldowns (user_id, command, last_used) VALUES (?, ?, ?)
               ON CONFLICT(user_id, command) DO UPDATE SET last_used = excluded.last_used""",
            (user_id, command, time.time()))


def economy_cooldown_message(left: int, command: str) -> str:
    names = {"work": ".w/.work", "crime": ".crime", "cheat": ".cheat"}
    return f"⏳ **{names.get(command, command)}** will be available again in **{left // 3600}h {(left % 3600) // 60}m {left % 60}s**."


@bot.command(name="balance", aliases=["bal", "konto"])
async def balance(ctx, member: discord.Member = None):
    """Show your own balance or the balance of a mentioned member."""
    member = member or ctx.author
    amount = get_balance(member.id)
    embed = discord.Embed(title="🏦 Balance",
        description=f"**Player:** {member.mention}\n**Balance:** **{amount:,} Coins**".replace(",", "."),
        color=discord.Color.gold())
    embed.set_thumbnail(url=member.display_avatar.url)
    await ctx.send(embed=embed)


@bot.command(name="w", aliases=["work"])
async def work(ctx):
    left = cooldown_left(ctx.author.id, "work")
    if left:
        return await ctx.send(economy_cooldown_message(left, "work"))
    use_cooldown(ctx.author.id, "work")
    earned = random.randint(ECONOMY_ACTION_MIN, ECONOMY_ACTION_MAX)
    total = change_balance(ctx.author.id, earned)
    await ctx.send(f"🛠️ Work complete! You earned **{earned:,} Coins**. Balance: **{total:,} Coins**.".replace(",", "."))


@bot.command(name="crime", aliases=["c"])
async def crime(ctx):
    left = cooldown_left(ctx.author.id, "crime")
    if left:
        return await ctx.send(economy_cooldown_message(left, "crime"))
    current = get_balance(ctx.author.id)
    if current < ECONOMY_ACTION_MIN:
        return await ctx.send(f"❌ You need at least **{ECONOMY_ACTION_MIN:,} Coins** in your balance to use .crime.".replace(",", "."))
    use_cooldown(ctx.author.id, "crime")
    if random.random() < 0.45:
        amount = random.randint(ECONOMY_ACTION_MIN, ECONOMY_ACTION_MAX)
        total = change_balance(ctx.author.id, amount)
        await ctx.send(f"🚨 The heist was successful! **+{amount:,} Coins**. Balance: **{total:,} Coins**.".replace(",", "."))
    else:
        amount = random.randint(ECONOMY_ACTION_MIN, min(ECONOMY_ACTION_MAX, current))
        total = change_balance(ctx.author.id, -amount)
        await ctx.send(f"👮 You were caught! You lost **{amount:,} Coins**. Balance: **{total:,} Coins**.".replace(",", "."))


@bot.command(name="cheat")
async def cheat(ctx):
    left = cooldown_left(ctx.author.id, "cheat")
    if left:
        return await ctx.send(economy_cooldown_message(left, "cheat"))
    current = get_balance(ctx.author.id)
    if current < ECONOMY_ACTION_MIN:
        return await ctx.send(f"❌ You need at least **{ECONOMY_ACTION_MIN:,} Coins** in your balance to use .cheat.".replace(",", "."))
    use_cooldown(ctx.author.id, "cheat")
    if random.random() < 0.5:
        amount = random.randint(ECONOMY_ACTION_MIN, ECONOMY_ACTION_MAX)
        total = change_balance(ctx.author.id, amount)
        await ctx.send(f"🎲 Lucky! **+{amount:,} Coins**. Balance: **{total:,} Coins**.".replace(",", "."))
    else:
        amount = random.randint(ECONOMY_ACTION_MIN, min(ECONOMY_ACTION_MAX, current))
        total = change_balance(ctx.author.id, -amount)
        await ctx.send(f"💸 Unlucky! You lost **{amount:,} Coins**. Balance: **{total:,} Coins**.".replace(",", "."))


@bot.command(name="pay", aliases=["transfer"])
async def pay(ctx, member: discord.Member, amount: int):
    if member.bot:
        return await ctx.send("❌ You cannot transfer money to bots.")
    if member.id == ctx.author.id:
        return await ctx.send("❌ You cannot transfer money to yourself.")
    if amount <= 0:
        return await ctx.send("❌ The amount must be greater than 0.")
    if get_balance(ctx.author.id) < amount:
        return await ctx.send(f"❌ You do not have enough Coins. Balance: **{get_balance(ctx.author.id)} Coins**.")
    try:
        with economy_db:
            get_balance(ctx.author.id)
            get_balance(member.id)
            sender_balance = economy_db.execute("SELECT balance FROM accounts WHERE user_id = ?", (ctx.author.id,)).fetchone()[0]
            if sender_balance < amount:
                return await ctx.send(f"❌ You do not have enough Coins. Balance: **{sender_balance} Coins**.")
            economy_db.execute("UPDATE accounts SET balance = balance - ? WHERE user_id = ?", (amount, ctx.author.id))
            economy_db.execute("UPDATE accounts SET balance = balance + ? WHERE user_id = ?", (amount, member.id))
        await ctx.send(f"💸 {ctx.author.mention} transferred **{amount:,} Coins** to {member.mention}. New balance: **{get_balance(ctx.author.id):,} Coins**.".replace(",", "."))
    except sqlite3.Error:
        log.exception("Economy transfer failed")
        await ctx.send("❌ The transfer failed. Please try again later.")


async def send_offer_dm(ctx, title, description, fields, footer):
    embed = discord.Embed(title=title, description=description, color=discord.Color.dark_red())
    for name, value in fields:
        embed.add_field(name=name, value=value, inline=False)
    embed.set_footer(text=footer)
    try:
        await ctx.author.send(embed=embed)
    except discord.Forbidden:
        await ctx.reply(
            "I couldn't DM you. Please enable direct messages from server members, then try again.",
            mention_author=False,
        )
        return
    # Remove the public prefix command so it doesn't clutter the channel.
    try:
        await ctx.message.delete()
    except (discord.Forbidden, discord.NotFound):
        pass
    await ctx.send(f"{ctx.author.mention} I've sent you the offers in DMs. 🩸", delete_after=8)


@bot.command(name="membership")
@commands.guild_only()
async def membership(ctx):
    fields = []
    for name, price, points, storage in MEMBERSHIPS:
        fields.append((
            f"🩸 {name} — {price}",
            f"**Monthly subscription:** {price}/month\n"
            f"**One-time purchase:** {price} (permanent role)\n"
            f"**Listed benefits:** {points}; {storage}.",
        ))
    await send_offer_dm(
        ctx,
        "BLOODFANG Memberships",
        "All membership ranks and prices in EUR. Monthly subscriptions renew every month.",
        fields,
        "Purchase through the official BLOODFANG website. Confirm benefits with server staff.",
    )


@bot.command(name="pointshop")
@commands.guild_only()
async def pointshop(ctx):
    fields = [
        (f"💎 {points} Points — {price}", f"Receive **{points} points** for **{price}**.")
        for points, price in POINT_PACKAGES
    ]
    await send_offer_dm(
        ctx,
        "BLOODFANG Points Shop",
        "Available points packages and prices (EUR):",
        fields,
        "Purchase through the official BLOODFANG Points Shop.",
    )


@bot.command(name="donat")
@commands.guild_only()
async def donation_ranks(ctx):
    fields = [
        ("🩸 Donator — €1–5", "Storage bonus at this lifetime donation total: **+1 slot**"),
        ("🥉 Bronze — €6–14", "Total storage bonus: **+2 slots**"),
        ("🥈 Silver — €15–24", "Total storage bonus: **+3 slots**"),
        ("🥇 Gold — €25–49", "Total storage bonus: **+4 slots**"),
        ("💎 Platinum — €50–74", "Total storage bonus: **+5 slots**"),
        ("💠 Diamond — €75–99", "Total storage bonus: **+6 slots**"),
        ("🔷 Sapphire — €100–149", "Total storage bonus: **+7 slots**"),
        ("🟢 Emerald — €150–199", "Total storage bonus: **+8 slots**"),
        ("🔴 Ruby — €200–299", "Total storage bonus: **+9 slots**"),
        ("⚫ Obsidian — €300–499", "Total storage bonus: **+10 slots**"),
        ("🟣 Amethyst — €500–749", "Total storage bonus: **+12 slots**"),
        ("🌑 Dark Matter — €750–999", "Total storage bonus: **+14 slots**"),
        ("👑 Blood God — €1,000+", "Total storage bonus: **+16 slots**"),
    ]
    await send_offer_dm(
        ctx,
        "BLOODFANG Donation Ranks",
        "Your lifetime confirmed donation total determines your rank. Storage bonuses are total bonuses added to your existing membership storage; they are not stacked again at every rank-up.",
        fields,
        "Donate through the official BLOODFANG website: " + os.environ.get("PUBLIC_BASE_URL", "https://bloodfang-membership.up.railway.app").rstrip("/") + "/donate",
    )


@tasks.loop(minutes=2)
async def rotate_status():
    global _status_index
    _status_index = (_status_index + 1) % len(STATUS_ACTIVITIES)
    await bot.change_presence(
        status=discord.Status.online,
        activity=STATUS_ACTIVITIES[_status_index],
    )
    log.info("Rotated bot activity to %s", STATUS_ACTIVITIES[_status_index].name)



@bot.tree.command(name="mymembership", description="Show your BLOODFANG membership status")
async def mymembership(interaction: discord.Interaction):
    if not interaction.guild or interaction.guild.id != int(os.environ.get("DISCORD_GUILD_ID", "1561027077984227371")):
        await interaction.response.send_message("This command can only be used in the configured BLOODFANG server.", ephemeral=True)
        return

    api_url = os.environ.get("MEMBERSHIP_API_URL", "https://bloodfang-membership.up.railway.app").rstrip("/")
    api_key = os.environ.get("SHOP_API_KEY", "").strip()
    if not api_key:
        await interaction.response.send_message(
            "Membership lookup is not configured yet. Please contact BLOODFANG staff.", ephemeral=True
        )
        log.error("SHOP_API_KEY is missing from the bot service variables")
        return

    await interaction.response.defer(ephemeral=True, thinking=True)
    try:
        timeout = aiohttp.ClientTimeout(total=12)
        async with aiohttp.ClientSession(timeout=timeout) as client:
            async with client.get(
                f"{api_url}/api/discord/membership/{interaction.user.id}",
                headers={"X-Shop-API-Key": api_key},
            ) as response:
                if response.status == 404:
                    await interaction.followup.send(
                        "I couldn't find any membership purchases linked to your Discord account. "
                        "If you recently purchased one, please wait a moment or contact staff.", ephemeral=True
                    )
                    return
                if response.status != 200:
                    log.warning("Membership API returned HTTP %s", response.status)
                    await interaction.followup.send(
                        "I couldn't check your membership right now. Please try again later.", ephemeral=True
                    )
                    return
                data = await response.json()

        purchases = data.get("memberships", [])
        if not purchases:
            await interaction.followup.send(
                "You don't have any membership records yet. Purchases made before shop records were enabled may not appear.", ephemeral=True
            )
            return

        embed = discord.Embed(
            title="🩸 Your BLOODFANG Membership",
            color=discord.Color.dark_red(),
            description=f"Membership records for {interaction.user.mention}",
        )
        labels = {
            "active": "🟢 Active",
            "pending": "🟡 Pending payment confirmation",
            "expired": "⚫ Expired",
            "cancelled": "⚪ Cancelled",
            "suspended": "🟠 Suspended",
        }
        for purchase in purchases[:10]:
            status = str(purchase.get("status", "unknown")).lower()
            expiry = purchase.get("expires_at")
            expiry_text = f"<t:{int(expiry)}:F> (<t:{int(expiry)}:R>)" if expiry else "Not recorded"
            purchase_type = str(purchase.get("purchase_type", "unknown")).replace("_", " ").title()
            embed.add_field(
                name=f"{purchase.get('tier_name', 'Membership')} — {labels.get(status, status.title())}",
                value=f"**Type:** {purchase_type}\n**Expires:** {expiry_text}",
                inline=False,
            )
        embed.set_footer(text="If these details look wrong, contact BLOODFANG staff.")
        await interaction.followup.send(embed=embed, ephemeral=True)
    except (aiohttp.ClientError, asyncio.TimeoutError, ValueError):
        log.exception("Membership lookup failed for Discord user %s", interaction.user.id)
        await interaction.followup.send(
            "The membership service is temporarily unavailable. Please try again later.", ephemeral=True
        )


@bot.command(name="website", aliases=["site"])
async def website(ctx):
    """Show the official BLOODFANG website link."""
    website_url = os.environ.get("PUBLIC_BASE_URL", "https://bloodfang-membership.up.railway.app").rstrip("/")
    await ctx.reply(f"🌐 **BLOODFANG Website:** {website_url}", mention_author=False)

@bot.tree.command(name="donat", description="Set up the pinned BLOODFANG donation leaderboard in this channel")
@discord.app_commands.default_permissions(manage_guild=True)
async def donat(interaction: discord.Interaction):
    if not interaction.guild or interaction.guild.id != int(os.environ.get("DISCORD_GUILD_ID", "1561027077984227371")):
        await interaction.response.send_message("This command can only be used in the configured BLOODFANG server.", ephemeral=True)
        return
    if not interaction.user.guild_permissions.manage_guild:
        await interaction.response.send_message("You need Manage Server permission to configure the donation leaderboard.", ephemeral=True)
        return
    channel = interaction.channel
    if not channel or not channel.permissions_for(interaction.guild.me).manage_webhooks:
        await interaction.response.send_message("I need Manage Webhooks permission in this channel.", ephemeral=True)
        return
    try:
        webhook = await channel.create_webhook(name="BLOODFANG Donations", reason=f"Donation leaderboard configured by {interaction.user}")
    except discord.Forbidden:
        await interaction.response.send_message("I cannot create a webhook here. Give me Manage Webhooks permission and try again.", ephemeral=True)
        return
    await interaction.response.send_message("Donation channel configured. Add these variables to the WEBSITE service in Railway, then redeploy:\nDONATION_WEBHOOK_URL = " + webhook.url + "\nDONATION_CHANNEL_ID = " + str(channel.id) + "\nKeep the webhook URL secret. The leaderboard is created and pinned after the first confirmed PayPal donation.", ephemeral=True)

@bot.tree.command(name="shoplog", description="Create the BLOODFANG purchase log in this channel")
@discord.app_commands.default_permissions(manage_guild=True)
async def shoplog(interaction: discord.Interaction):
    if not interaction.guild or interaction.guild.id != int(os.environ.get("DISCORD_GUILD_ID", "1561027077984227371")):
        await interaction.response.send_message("This command can only be used in the configured BLOODFANG server.", ephemeral=True)
        return
    if not interaction.user.guild_permissions.manage_guild:
        await interaction.response.send_message("You need Manage Server permission to configure shop logs.", ephemeral=True)
        return
    if not interaction.channel or not interaction.channel.permissions_for(interaction.guild.me).manage_webhooks:
        await interaction.response.send_message("I need the Manage Webhooks permission in this channel to set up purchase logs.", ephemeral=True)
        return
    try:
        # Discord does not return webhook tokens when listing existing webhooks,
        # so create a fresh one to ensure the secret URL can be shown to the admin.
        webhook = await interaction.channel.create_webhook(name="BLOODFANG Shop Logs", reason=f"Shop logs configured by {interaction.user}")
    except discord.Forbidden:
        await interaction.response.send_message("I cannot create a webhook here. Give me Manage Webhooks permission and try again.", ephemeral=True)
        return
    await interaction.response.send_message(
        "✅ Shop-log webhook is ready for this channel. One final setup step is required: copy the webhook URL below into the Railway website/membership service as the variable SHOPLOG_WEBHOOK_URL, then redeploy. Treat this URL like a password.\n\n"
        + f"||{webhook.url}||",
        ephemeral=True,
    )


DONATION_ROLES = [
    ("💸 Donator", "#95A5A6", ["Donator", "🩸 Donator"]),
    ("🥉 Bronze", "#CD7F32", ["Bronze", "🩸 Bronze"]),
    ("🥈 Silver", "#C0C0C0", ["Silver", "🩸 Silver"]),
    ("🥇 Gold", "#FFD700", ["Gold", "🩸 Gold"]),
    ("💎 Platinum", "#7FDBFF", ["Platinum", "🩸 Platinum"]),
    ("💠 Diamond", "#00BFFF", ["Diamond", "🩸 Diamond"]),
    ("🔹 Sapphire", "#0F52BA", ["Sapphire", "🩸 Sapphire"]),
    ("🟢 Emerald", "#50C878", ["Emerald", "🩸 Emerald"]),
    ("❤️ Ruby", "#E0115F", ["Ruby", "🩸 Ruby"]),
    ("⚫ Obsidian", "#343434", ["Obsidian", "🩸 Obsidian"]),
    ("🟣 Amethyst", "#9966CC", ["Amethyst", "🩸 Amethyst"]),
    ("🌌 Dark Matter", "#301934", ["Dark Matter", "🩸 Dark Matter"]),
    ("👑 Blood God", "#8B0000", ["Blood God", "🩸 Blood God"]),
]

async def ensure_donation_roles(guild: discord.Guild) -> None:
    """Create, style, and order donation ranks below the configured anchor role."""
    anchor_id = 1564594346370670612
    anchor = guild.get_role(anchor_id)
    if anchor is None:
        log.error("Donation-role anchor %s was not found in guild %s", anchor_id, guild.id)
        return
    role_map = {role.name: role for role in guild.roles}
    donation_roles = []
    for full_name, color_hex, old_names in DONATION_ROLES:
        role = next((role_map[n] for n in [full_name, *old_names] if n in role_map), None)
        color = discord.Colour(int(color_hex.lstrip('#'), 16))
        try:
            if role is None:
                role = await guild.create_role(name=full_name, colour=color, hoist=True, mentionable=False, reason="Set up BLOODFANG donation ranks")
                log.info('Created donation role %s', full_name)
            else:
                await role.edit(name=full_name, colour=color, hoist=True, mentionable=False, reason="Style and group BLOODFANG donation rank")
            donation_roles.append(role)
        except discord.Forbidden:
            log.error("Cannot create or update %s: bot needs Manage Roles permission and a higher role position", full_name)
            return
        except discord.HTTPException:
            log.exception("Discord rejected create/update for donation role %s", full_name)
            return
    if guild.me is None or guild.me.top_role <= anchor:
        log.error("Move the bot highest role above anchor role %s before arranging donation roles", anchor_id)
        return
    # Blood God is closest to the anchor; Donator is lowest.
    positions = {}
    position = anchor.position - 1
    for role in reversed(donation_roles):
        if position <= 0:
            log.error("Not enough role positions below anchor role %s", anchor_id)
            return
        positions[role] = position
        position -= 1
    try:
        await guild.edit_role_positions(positions=positions, reason="Arrange donation ranks below configured role")
        log.info("Donation roles styled and ordered below role %s", anchor_id)
    except discord.Forbidden:
        log.error("Cannot reorder roles; ensure the bot highest role is above the anchor role")
    except discord.HTTPException:
        log.exception("Discord rejected donation-role position update")
@bot.event
async def on_ready():
    # Apply the first status immediately, then switch to the other every 2 minutes.
    await bot.change_presence(
        status=discord.Status.online,
        activity=STATUS_ACTIVITIES[_status_index],
    )
    if not rotate_status.is_running():
        rotate_status.start()
    try:
        guild_id = int(os.environ.get("DISCORD_GUILD_ID", "1561027077984227371"))
        live_guild = bot.get_guild(guild_id)
        if live_guild is not None:
            await ensure_donation_roles(live_guild)
        else:
            log.error("Configured Discord guild %s is not available to the bot", guild_id)
        guild = discord.Object(id=guild_id)
        bot.tree.copy_global_to(guild=guild)
        synced = await bot.tree.sync(guild=guild)
        log.info("Synced %s guild slash commands for guild %s", len(synced), guild_id)
    except Exception:
        log.exception("Could not sync slash commands")
    log.info("BLOODFANG bot is online as %s (ID: %s)", bot.user, bot.user.id)


@bot.event
async def on_disconnect():
    log.warning("Disconnected from Discord gateway; discord.py will try to reconnect.")


bot.run(TOKEN, log_handler=None)
