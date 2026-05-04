import discord
from discord.ext import commands
import asyncio
import csv
import pickle
import os
from datetime import datetime
from dotenv import load_dotenv
from zoneinfo import ZoneInfo
import random

load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")

# ========== CONFIGURATION ==========
ROLE_IDS = {
    "Green": 1131419419231387729,
    "Yellow": 1362389784349249710,
    "Blue": 1280549802446290964,
    "Orange": 1462074490363318272,
    "Red": 1460166145486360723,
    "Plurple": 1449796274428580032,
    "White": 1462074418665885878,
    "Bronzer": 1464811566854832329,
    "Black": 1363401221968363622,
    "Homo": 1407517283059892255,
    "KB False": 1469141675749408789,
}

CHANNEL_IDS = [
    1038694454552444938,
    1292589709259706398,
    1264230807359455344
]

TZ = ZoneInfo('Asia/Hong_Kong')
START_DATE = datetime(2025, 1, 1, tzinfo=TZ)

CHECKPOINT_FILE = "scan_checkpoint.pkl"

# Change this to a real channel ID where the bot can send error logs
ERROR_CHANNEL_ID = 123456789012345678  # <-- REPLACE WITH YOUR CHANNEL ID

# ========== GLOBAL STATE ==========
scan_progress = {
    "active": False,
    "current_channel": None,
    "users_scanned": 0,
    "total_messages": 0,
    "role_message_counts": {role: 0 for role in ROLE_IDS.keys()},
    "channels_done": 0,
    "total_channels": len(CHANNEL_IDS),
    "completed_channel_ids": set()
}
user_data = {}

intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents)

def save_checkpoint():
    data = {
        "user_data": user_data,
        "scan_progress": {
            "users_scanned": scan_progress["users_scanned"],
            "total_messages": scan_progress["total_messages"],
            "role_message_counts": scan_progress["role_message_counts"],
            "channels_done": scan_progress["channels_done"],
            "completed_channel_ids": scan_progress["completed_channel_ids"]
        }
    }
    with open(CHECKPOINT_FILE, "wb") as f:
        pickle.dump(data, f)

def load_checkpoint():
    global user_data, scan_progress
    if os.path.exists(CHECKPOINT_FILE):
        try:
            with open(CHECKPOINT_FILE, "rb") as f:
                data = pickle.load(f)
            user_data = data["user_data"]
            scan_progress.update(data["scan_progress"])
            scan_progress["active"] = False
            return True
        except Exception as e:
            return False
    return False

def clear_checkpoint():
    if os.path.exists(CHECKPOINT_FILE):
        os.remove(CHECKPOINT_FILE)

async def send_error_log(message: str):
    """Send error message to designated error channel."""
    if ERROR_CHANNEL_ID:
        channel = bot.get_channel(ERROR_CHANNEL_ID)
        if channel:
            await channel.send(f"```\n{message[:1900]}\n```")

async def scan_with_retry(channel):
    max_retries = 5
    base_delay = 2
    for attempt in range(max_retries):
        try:
            async for message in channel.history(limit=None, after=START_DATE):
                yield message
            return
        except discord.HTTPException as e:
            if e.status in (503, 429):
                delay = base_delay * (2 ** attempt) + random.uniform(0, 1)
                print(f"HTTP {e.status} on #{channel.name}, retry in {delay:.1f}s")
                await send_error_log(f"Retry {attempt+1} for #{channel.name}: HTTP {e.status}")
                await asyncio.sleep(delay)
            else:
                raise
        except (discord.GatewayNotFound, discord.ConnectionClosed) as e:
            delay = base_delay * (2 ** attempt) + random.uniform(0, 1)
            print(f"Connection error on #{channel.name}, retry in {delay:.1f}s")
            await send_error_log(f"Connection error on #{channel.name}: {e}")
            await asyncio.sleep(delay)
    await send_error_log(f"Giving up on #{channel.name} after {max_retries} attempts")
    return

async def scan_channel(channel):
    scan_progress["current_channel"] = channel.name
    print(f"Scanning #{channel.name}...")
    await send_error_log(f"Starting scan of #{channel.name}")
    msg_count = 0
    try:
        async for message in scan_with_retry(channel):
            user = message.author
            if user.bot:
                continue
            uid = user.id
            if uid not in user_data:
                roles = []
                for rname, rid in ROLE_IDS.items():
                    if discord.utils.get(user.roles, id=rid):
                        roles.append(rname)
                user_data[uid] = {
                    "name": str(user),
                    "roles": roles,
                    "message_count": 0
                }
                scan_progress["users_scanned"] += 1
            user_data[uid]["message_count"] += 1
            scan_progress["total_messages"] += 1
            msg_count += 1
            for r in user_data[uid]["roles"]:
                scan_progress["role_message_counts"][r] += 1
    except Exception as e:
        error_msg = f"Error in #{channel.name}: {type(e).__name__}: {e}"
        print(error_msg)
        await send_error_log(error_msg)
    finally:
        scan_progress["channels_done"] += 1
        scan_progress["completed_channel_ids"].add(channel.id)
        save_checkpoint()
        print(f"Finished #{channel.name} – {msg_count} messages.")
        await send_error_log(f"Finished #{channel.name} – {msg_count} messages counted.")

async def run_scan():
    scan_progress["active"] = True
    await send_error_log("Scan started/resumed.")
    try:
        for cid in CHANNEL_IDS:
            if cid in scan_progress["completed_channel_ids"]:
                await send_error_log(f"Skipping already completed channel {cid}")
                continue
            channel = bot.get_channel(cid)
            if not channel:
                await send_error_log(f"Channel {cid} not found (bot may not see it). Marking as done and skipping.")
                scan_progress["completed_channel_ids"].add(cid)
                scan_progress["channels_done"] += 1
                save_checkpoint()
                continue
            if not isinstance(channel, discord.TextChannel):
                await send_error_log(f"Channel {cid} (#{channel.name}) is not a text channel. Skipping.")
                scan_progress["completed_channel_ids"].add(cid)
                scan_progress["channels_done"] += 1
                save_checkpoint()
                continue
            # Check permissions
            perms = channel.permissions_for(channel.guild.me)
            if not perms.read_message_history or not perms.view_channel:
                await send_error_log(f"Missing permissions in #{channel.name} (need Read Message History & View Channel). Skipping.")
                scan_progress["completed_channel_ids"].add(cid)
                scan_progress["channels_done"] += 1
                save_checkpoint()
                continue
            await scan_channel(channel)
        
        # Export CSV after all channels
        out_file = f"message_counts_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        with open(out_file, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(["User ID", "Username", "Colour Roles", "Message Count"])
            for uid, data in user_data.items():
                writer.writerow([uid, data["name"], ", ".join(data["roles"]) if data["roles"] else "None", data["message_count"]])
        await send_error_log(f"Scan complete. Saved to {out_file}")
        clear_checkpoint()
    except Exception as e:
        error_msg = f"Fatal scan error: {type(e).__name__}: {e}"
        print(error_msg)
        await send_error_log(error_msg)
    finally:
        scan_progress["active"] = False
        await send_error_log("Scan status set to inactive.")

@bot.command()
async def scan(ctx):
    """Start or resume the message count scan."""
    if scan_progress["active"]:
        await ctx.send("Scan is already running.")
        return
    if load_checkpoint():
        await ctx.send("Resuming previous scan...")
    else:
        await ctx.send("Starting new scan...")
    bot.loop.create_task(run_scan())

@bot.command()
async def status(ctx):
    """Show current scan progress."""
    if not scan_progress["active"]:
        await ctx.send("No scan is running. Use !scan to start.")
        return
    embed = discord.Embed(title="Message Scan Progress", color=0x00ff00)
    embed.add_field(name="Status", value="Scanning...", inline=False)
    embed.add_field(name="Current Channel", value=f"#{scan_progress['current_channel']}", inline=True)
    embed.add_field(name="Users Found", value=scan_progress["users_scanned"], inline=True)
    embed.add_field(name="Total Messages", value=scan_progress["total_messages"], inline=True)
    embed.add_field(name="Channels Done", value=f"{scan_progress['channels_done']}/{scan_progress['total_channels']}", inline=True)
    embed.add_field(name="Timezone", value="UTC+8 (Hong Kong)", inline=True)
    embed.add_field(name="Since", value=START_DATE.strftime("%Y-%m-%d %H:%M:%S"), inline=True)
    role_counts = scan_progress["role_message_counts"]
    sorted_roles = sorted(role_counts.items(), key=lambda x: x[1], reverse=True)[:5]
    role_text = "\n".join(f"{r}: {c} msgs" for r, c in sorted_roles)
    embed.add_field(name="Top Colour Roles by Messages", value=role_text or "No data", inline=False)
    await ctx.send(embed=embed)

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")
    # Optionally send a startup message to error channel
    if ERROR_CHANNEL_ID:
        ch = bot.get_channel(ERROR_CHANNEL_ID)
        if ch:
            await ch.send("Bot is ready. Use `!scan` to start scanning.")
    print("Use !scan to start/resume scan, !status to check progress.")

def main():
    if not TOKEN:
        raise ValueError("DISCORD_TOKEN missing in .env")
    if ERROR_CHANNEL_ID == 123456789012345678:
        print("WARNING: You did not set a real ERROR_CHANNEL_ID. Error logs will not be sent to Discord.")
    bot.run(TOKEN)

if __name__ == "__main__":
    main()