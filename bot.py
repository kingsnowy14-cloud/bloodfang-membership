import logging
import os

import discord
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
bot = commands.Bot(command_prefix="!", intents=intents, status=discord.Status.online, help_command=None)

STATUS_ACTIVITIES = [
    discord.Game(name="!membership"),
    discord.Game(name="!pointshop"),
]
_status_index = 0

MEMBERSHIPS = [
    ("FANGBORN", "€2.99", "10,000 Bloodpoints/day", "4 storage"),
    ("STALKER", "€4.99", "25,000 Bloodpoints/day", "5 storage"),
    ("RAVAGER", "€7.99", "50,000 Bloodpoints/day", "6 storage"),
    ("WARLORD", "€12.99", "100,000 Bloodpoints/day", "8 storage"),
    ("APEX", "€19.99", "200,000 Bloodpoints/day", "9 storage"),
    ("BLOOD EMPEROR", "€29.99", "350,000 Bloodpoints/day", "10 storage"),
    ("BLOOD TITAN", "€50.00", "1,000,000 Bloodpoints/day", "13 storage"),
    ("BLOOD GOD", "€100.00", "1,600,000 Bloodpoints/day", "20 storage"),
]

POINT_PACKAGES = [
    ("2,500,000", "€10.00"),
    ("6,500,000", "€25.00"),
    ("16,500,000", "€55.00"),
    ("45,000,000", "€115.00"),
    ("150,000,000", "€230.00"),
    ("300,000,000", "€350.00"),
]


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
    await ctx.reply("I've sent you the offers in DMs. 🩸", mention_author=False)


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


@tasks.loop(minutes=2)
async def rotate_status():
    global _status_index
    _status_index = (_status_index + 1) % len(STATUS_ACTIVITIES)
    await bot.change_presence(
        status=discord.Status.online,
        activity=STATUS_ACTIVITIES[_status_index],
    )
    log.info("Rotated bot activity to %s", STATUS_ACTIVITIES[_status_index].name)



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
