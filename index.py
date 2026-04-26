import discord
from discord.ext import commands
import os
import json
import asyncio
from datetime import datetime, timezone, timedelta
from dotenv import load_dotenv


load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")

# ========== CONFIGURATION ==========
SEARCH_WORDS = ['rape', 'nigger', 'child porn', 'cp', 'raping']
CASE_SENSITIVE = False
LOG_FILE = 'deleted_messages.json'
CHECKPOINT_FILE = 'scan_checkpoint.json'

# Date range filter (set to None to disable)
SCAN_START_DATE = datetime(2024, 1, 1, tzinfo=timezone.utc)   # Messages after this date
SCAN_END_DATE   = datetime(2024, 12, 31, tzinfo=timezone.utc) # Messages before this date
# To scan all messages, set both to None:
# SCAN_START_DATE = None
# SCAN_END_DATE = None

# ========== BOT SETUP ==========
intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents)

# Global progress tracking (for !status)
scanning_active = False
current_progress = {
    "total_scanned": 0,
    "total_found": 0,
    "processed_channels": 0,
    "total_channels": 0,
    "current_channel": None,
    "start_time": None,
    "last_update_time": None,
    "last_scanned": 0
}

# ========== HELPER FUNCTIONS ==========
def contains_word(text):
    if not text:
        return False
    if not CASE_SENSITIVE:
        text_lower = text.lower()
        return any(word.lower() in text_lower for word in SEARCH_WORDS)
    else:
        return any(word in text for word in SEARCH_WORDS)

def get_matching_keyword(text):
    if not text:
        return None
    if not CASE_SENSITIVE:
        text_lower = text.lower()
        for word in SEARCH_WORDS:
            if word.lower() in text_lower:
                return word
    else:
        for word in SEARCH_WORDS:
            if word in text:
                return word
    return None

def save_log(entries):
    """Atomic write to prevent JSON corruption."""
    temp_file = f"{LOG_FILE}.tmp"
    with open(temp_file, 'w', encoding='utf-8') as f:
        json.dump(entries, f, indent=2, ensure_ascii=False)
    os.replace(temp_file, LOG_FILE)

def load_allowed_channels():
    if not os.path.exists('channels.txt'):
        print("⚠️ channels.txt not found. Bot will scan ALL channels.")
        return None
    with open('channels.txt', 'r') as f:
        ids = {int(line.strip()) for line in f if line.strip().isdigit()}
    if not ids:
        print("⚠️ channels.txt is empty. Scanning ALL channels.")
        return None
    print(f"✅ Loaded {len(ids)} allowed channel IDs from channels.txt")
    return ids

def safe_load_json(filename, default=None):
    """Safely load JSON, return default (empty list) if file missing or corrupted."""
    if default is None:
        default = []
    if not os.path.exists(filename):
        return default
    try:
        with open(filename, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (json.JSONDecodeError, UnicodeDecodeError) as e:
        print(f"⚠️ Corrupted JSON in {filename}: {e}")
        # Backup the corrupted file
        backup = f"{filename}.corrupted"
        os.rename(filename, backup)
        print(f"   Backed up to {backup}")
        return default

# ========== CHECKPOINT FUNCTIONS ==========
def save_checkpoint(channel_id, message_id, total_scanned, total_found, processed_channels):
    checkpoint_data = {
        "channel_id": channel_id,
        "message_id": message_id,
        "total_scanned": total_scanned,
        "total_found": total_found,
        "processed_channels": processed_channels
    }
    temp_file = f"{CHECKPOINT_FILE}.tmp"
    with open(temp_file, 'w', encoding='utf-8') as f:
        json.dump(checkpoint_data, f, indent=2)
    os.replace(temp_file, CHECKPOINT_FILE)
    print(f"Checkpoint saved: Channel {channel_id}, Message {message_id}")

def load_checkpoint():
    if not os.path.exists(CHECKPOINT_FILE):
        return None
    with open(CHECKPOINT_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)

def clear_checkpoint():
    if os.path.exists(CHECKPOINT_FILE):
        os.remove(CHECKPOINT_FILE)

# ========== RETRY HELPER ==========
async def fetch_history_with_retry(channel, after_id=None, after_date=None, before_date=None, retries=3):
    """Generator that yields messages from channel.history with retry on 503."""
    for attempt in range(retries):
        try:
            kwargs = {"limit": None}
            if after_date:
                kwargs["after"] = after_date
            elif after_id:
                kwargs["after"] = discord.Object(id=after_id)
            if before_date:
                kwargs["before"] = before_date

            async for message in channel.history(**kwargs):
                yield message
            return
        except discord.HTTPException as e:
            if e.status == 503 and attempt < retries - 1:
                wait_time = 2 ** attempt
                await asyncio.sleep(wait_time)
                continue
            else:
                raise

# ========== SAFE DELETE HELPERS ==========
async def safe_delete_message(ctx, message):
    """Delete a single message with rate limit handling. Returns True on success."""
    try:
        await message.delete()
        await asyncio.sleep(1.2)  # ~50 req/min safe zone for individual deletes
        return True
    except discord.Forbidden:
        await ctx.send(f"❌ Cannot delete {message.id} – permissions.")
        return False
    except discord.NotFound:
        return True  # Already deleted, treat as success
    except discord.HTTPException as e:
        if e.status == 429:
            retry_after = float(e.response.headers.get('Retry-After', 5))
            await ctx.send(f"⏳ Rate limited. Waiting {retry_after:.1f}s...")
            await asyncio.sleep(retry_after + 0.5)
            try:
                await message.delete()
                await asyncio.sleep(1.2)
                return True
            except Exception:
                return False
        else:
            await ctx.send(f"⚠️ Delete failed {message.id}: {e}")
            return False

async def safe_bulk_delete(ctx, channel, messages):
    """Bulk delete a list of messages (must be under 14 days old, max 100). Returns True on success."""
    if not messages:
        return True
    try:
        await channel.delete_messages(messages)
        await asyncio.sleep(1.5)  # Pause after bulk op
        return True
    except discord.HTTPException as e:
        if e.status == 429:
            retry_after = float(e.response.headers.get('Retry-After', 5))
            await ctx.send(f"⏳ Rate limited on bulk delete. Waiting {retry_after:.1f}s...")
            await asyncio.sleep(retry_after + 0.5)
            try:
                await channel.delete_messages(messages)
                await asyncio.sleep(1.5)
                return True
            except Exception as e2:
                await ctx.send(f"⚠️ Bulk delete retry failed: {e2}")
                return False
        else:
            await ctx.send(f"⚠️ Bulk delete failed: {e}")
            return False

# ========== SCAN & DELETE LOGIC ==========
async def scan_and_purge_embeds(ctx, should_delete=False):
    """Scan for messages with embeds or attachments within date range, optionally delete them."""
    global scanning_active, current_progress
    scanning_active = True

    # Reset progress tracking for this scan
    current_progress.update({
        "total_scanned": 0,
        "total_found": 0,
        "processed_channels": 0,
        "total_channels": 0,
        "current_channel": None,
        "start_time": asyncio.get_event_loop().time(),
        "last_update_time": asyncio.get_event_loop().time(),
        "last_scanned": 0
    })

    PURGE_CHECKPOINT_FILE = 'purge_checkpoint.json'
    PURGE_LOG_FILE = 'purged_embeds.json'

    # Load channels
    guild = ctx.guild
    allowed_ids = load_allowed_channels()
    if allowed_ids is None:
        channels = [ch for ch in guild.text_channels if ch.permissions_for(guild.me).read_message_history]
    else:
        channels = [ch for ch in guild.text_channels
                    if ch.id in allowed_ids and ch.permissions_for(guild.me).read_message_history]
    total_channels = len(channels)

    # ---- Checkpoint helpers (local to this function) ----
    def save_purge_checkpoint(channel_id, message_id, total_scanned, total_found, processed_channels):
        data = {
            "channel_id": channel_id,
            "message_id": message_id,
            "total_scanned": total_scanned,
            "total_found": total_found,
            "processed_channels": processed_channels
        }
        temp_file = f"{PURGE_CHECKPOINT_FILE}.tmp"
        with open(temp_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)
        os.replace(temp_file, PURGE_CHECKPOINT_FILE)
        print(f"Purge checkpoint saved: Channel {channel_id}, Message {message_id}")

    def load_purge_checkpoint():
        if not os.path.exists(PURGE_CHECKPOINT_FILE):
            return None
        with open(PURGE_CHECKPOINT_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)

    def clear_purge_checkpoint():
        if os.path.exists(PURGE_CHECKPOINT_FILE):
            os.remove(PURGE_CHECKPOINT_FILE)

    # Load checkpoint
    checkpoint = load_purge_checkpoint()
    start_from_channel_id = None
    start_from_message_id = None
    total_scanned = 0
    total_found = 0
    processed_channels = 0
    found_messages = []

    if checkpoint:
        await ctx.send(f"📌 Found saved purge checkpoint:\n"
                       f"   Channels processed: {checkpoint['processed_channels']}\n"
                       f"   Messages scanned: {checkpoint['total_scanned']:,}\n"
                       f"   Messages found: {checkpoint['total_found']:,}\n"
                       f"Resume from checkpoint? (yes/no)")
        try:
            msg = await bot.wait_for('message', timeout=30,
                                     check=lambda m: m.author == ctx.author and m.content.lower() in ['yes', 'no'])
            if msg.content.lower() == 'yes':
                start_from_channel_id = checkpoint['channel_id']
                start_from_message_id = checkpoint['message_id']
                total_scanned = checkpoint['total_scanned']
                total_found = checkpoint['total_found']
                processed_channels = checkpoint['processed_channels']
                if os.path.exists(PURGE_LOG_FILE):
                    found_messages = safe_load_json(PURGE_LOG_FILE)
                    total_found = len(found_messages)
                    await ctx.send(f"📂 Loaded {total_found} existing media log entries.")
                await ctx.send("✅ Resuming purge from checkpoint...")
            else:
                clear_purge_checkpoint()
                if os.path.exists(PURGE_LOG_FILE):
                    os.remove(PURGE_LOG_FILE)
                await ctx.send("🔄 Starting fresh purge (checkpoint cleared).")
        except asyncio.TimeoutError:
            await ctx.send("⏱️ No response. Starting fresh purge.")
            clear_purge_checkpoint()
            if os.path.exists(PURGE_LOG_FILE):
                os.remove(PURGE_LOG_FILE)

    # Build channel list
    channel_list = []
    start_processing = (start_from_channel_id is None)
    for ch in channels:
        if ch.id == start_from_channel_id:
            start_processing = True
        if start_processing:
            channel_list.append(ch)
        else:
            processed_channels += 1

    current_progress.update({
        "total_scanned": total_scanned,
        "total_found": total_found,
        "processed_channels": processed_channels,
        "total_channels": total_channels
    })

    # Display date range
    date_info = ""
    if SCAN_START_DATE or SCAN_END_DATE:
        start_str = SCAN_START_DATE.strftime("%Y-%m-%d") if SCAN_START_DATE else "beginning"
        end_str = SCAN_END_DATE.strftime("%Y-%m-%d") if SCAN_END_DATE else "now"
        date_info = f"📅 Date range: {start_str} → {end_str}\n"
    await ctx.send(f"🔍 Starting {'purge and delete' if should_delete else 'purge scan (dry run)'} for messages with media (embeds or attachments)\n"
                   f"{date_info}Found {total_channels} text channels to scan.")

    # ---- Main scanning loop ----
    for idx, channel in enumerate(channel_list, start=processed_channels + 1):
        if not scanning_active:
            save_purge_checkpoint(channel.id, None, total_scanned, total_found, processed_channels)
            await ctx.send(f"⏹️ Stopped. Progress saved. Use `!purge embed no/yes` to resume.")
            with open(PURGE_LOG_FILE, 'w', encoding='utf-8') as f:
                json.dump(found_messages, f, indent=2, ensure_ascii=False)
            scanning_active = False
            return

        current_progress["current_channel"] = channel.name

        if should_delete and not channel.permissions_for(guild.me).manage_messages:
            await ctx.send(f"⚠️ Skipping #{channel.name} – missing Manage Messages.")
            processed_channels += 1
            continue

        max_attempts = 20
        attempt = 0
        channel_success = False
        last_successful_message_id = start_from_message_id if channel.id == start_from_channel_id else None

        while not channel_success and attempt < max_attempts and scanning_active:
            attempt += 1
            try:
                if attempt > 1:
                    wait_time = min(30, 2 ** attempt)
                    await ctx.send(f"🔄 Retry {attempt}/{max_attempts} for #{channel.name} after {wait_time}s...")
                    await asyncio.sleep(wait_time)

                await ctx.send(f"🔎 Scanning #{channel.name} for media (attempt {attempt})...")

                after_id = last_successful_message_id if channel.id == start_from_channel_id else None
                use_after_date = SCAN_START_DATE if after_id is None else None

                # Buckets for smart deletion
                bulk_candidates = []   # Messages < 14 days old (can bulk delete)
                old_messages = []      # Messages >= 14 days old (must delete individually)
                now = datetime.now(timezone.utc)

                async for message in fetch_history_with_retry(
                    channel,
                    after_id=after_id,
                    after_date=use_after_date,
                    before_date=SCAN_END_DATE
                ):
                    if not scanning_active:
                        save_purge_checkpoint(channel.id, message.id, total_scanned, total_found, processed_channels)
                        await ctx.send(f"⏹️ Stopped mid-channel. Progress saved.")
                        with open(PURGE_LOG_FILE, 'w', encoding='utf-8') as f:
                            json.dump(found_messages, f, indent=2, ensure_ascii=False)
                        scanning_active = False
                        return

                    total_scanned += 1

                    # Detect media: embeds or attachments
                    has_media = False
                    media_type = None
                    if message.embeds:
                        has_media = True
                        media_type = "embed"
                    elif message.attachments:
                        has_media = True
                        media_type = "attachment"

                    if has_media:
                        total_found += 1
                        log_entry = {
                            "message_id": message.id,
                            "channel": channel.name,
                            "channel_id": channel.id,
                            "author": str(message.author),
                            "author_id": message.author.id,
                            "content": message.content,
                            "timestamp": message.created_at.isoformat(),
                            "deleted": False,
                            "match_location": media_type,
                            "embed_count": len(message.embeds) if message.embeds else 0,
                            "attachment_count": len(message.attachments) if message.attachments else 0
                        }
                        found_messages.append(log_entry)

                        if should_delete:
                            age = now - message.created_at
                            if age < timedelta(days=14):
                                bulk_candidates.append(message)
                                # Flush bulk batch when we hit 100
                                if len(bulk_candidates) >= 100:
                                    success = await safe_bulk_delete(ctx, channel, bulk_candidates)
                                    if success:
                                        for entry in found_messages[-100:]:
                                            entry["deleted"] = True
                                    bulk_candidates.clear()
                            else:
                                old_messages.append(message)

                    last_successful_message_id = message.id

                    if total_scanned % 100 == 0:
                        current_progress.update({
                            "total_scanned": total_scanned,
                            "total_found": total_found,
                            "processed_channels": processed_channels
                        })

                # ---- After scanning channel: flush remaining deletes ----
                if should_delete:
                    # Flush remaining bulk candidates
                    if bulk_candidates:
                        success = await safe_bulk_delete(ctx, channel, bulk_candidates)
                        if success:
                            for entry in found_messages[-len(bulk_candidates):]:
                                entry["deleted"] = True
                        bulk_candidates.clear()

                    # Delete old messages one by one with safe delay
                    if old_messages:
                        await ctx.send(f"🗑️ Deleting {len(old_messages)} old media messages individually in #{channel.name}...")
                        for msg in old_messages:
                            if not scanning_active:
                                break
                            success = await safe_delete_message(ctx, msg)
                            if success:
                                for entry in found_messages:
                                    if entry["message_id"] == msg.id:
                                        entry["deleted"] = True
                                        break
                        old_messages.clear()

                # Channel done
                channel_success = True
                processed_channels += 1
                start_from_message_id = None
                save_purge_checkpoint(channel.id, None, total_scanned, total_found, processed_channels)
                # Atomic write for log file
                temp_log = f"{PURGE_LOG_FILE}.tmp"
                with open(temp_log, 'w', encoding='utf-8') as f:
                    json.dump(found_messages, f, indent=2, ensure_ascii=False)
                os.replace(temp_log, PURGE_LOG_FILE)
                await ctx.send(f"📊 Progress: #{channel.name} done | {total_scanned:,} scanned, {total_found} media messages found")

            except discord.Forbidden:
                await ctx.send(f"⛔ Cannot read history in #{channel.name} – skipping.")
                processed_channels += 1
                channel_success = True
                break
            except Exception as e:
                await ctx.send(f"⚠️ Error in #{channel.name} (attempt {attempt}/{max_attempts}): {e}")
                if attempt >= max_attempts:
                    await ctx.send(f"❌ Giving up on #{channel.name} after {max_attempts} attempts.")
                    save_purge_checkpoint(channel.id, last_successful_message_id, total_scanned, total_found, processed_channels)
                    scanning_active = False
                    return

    # Complete
    clear_purge_checkpoint()
    temp_log = f"{PURGE_LOG_FILE}.tmp"
    with open(temp_log, 'w', encoding='utf-8') as f:
        json.dump(found_messages, f, indent=2, ensure_ascii=False)
    os.replace(temp_log, PURGE_LOG_FILE)
    await ctx.send(f"✅ {'Purge' if should_delete else 'Scan'} Complete\n"
                   f"   Channels: {processed_channels}/{total_channels}\n"
                   f"   Messages scanned: {total_scanned:,}\n"
                   f"   Media messages found: {total_found:,}\n"
                   f"   Log: {PURGE_LOG_FILE}")
    scanning_active = False


async def scan_and_delete(ctx, should_delete=False):
    global scanning_active, current_progress
    scanning_active = True

    current_progress.update({
        "total_scanned": 0,
        "total_found": 0,
        "processed_channels": 0,
        "total_channels": 0,
        "current_channel": None,
        "start_time": asyncio.get_event_loop().time(),
        "last_update_time": asyncio.get_event_loop().time(),
        "last_scanned": 0
    })

    guild = ctx.guild
    allowed_ids = load_allowed_channels()
    if allowed_ids is None:
        channels = [ch for ch in guild.text_channels if ch.permissions_for(guild.me).read_message_history]
    else:
        channels = [ch for ch in guild.text_channels
                    if ch.id in allowed_ids and ch.permissions_for(guild.me).read_message_history]
    total_channels = len(channels)

    checkpoint = load_checkpoint()
    start_from_channel_id = None
    start_from_message_id = None
    total_scanned = 0
    total_found = 0
    processed_channels = 0
    found_messages = []

    if checkpoint:
        await ctx.send(f"📌 Found saved checkpoint from previous scan:\n"
                       f"   Channels processed: {checkpoint['processed_channels']}\n"
                       f"   Messages scanned: {checkpoint['total_scanned']:,}\n"
                       f"   Messages found: {checkpoint['total_found']:,}\n"
                       f"Resume from checkpoint? (yes/no)")
        try:
            msg = await bot.wait_for('message', timeout=30,
                                     check=lambda m: m.author == ctx.author and m.content.lower() in ['yes', 'no'])
            if msg.content.lower() == 'yes':
                start_from_channel_id = checkpoint['channel_id']
                start_from_message_id = checkpoint['message_id']
                total_scanned = checkpoint['total_scanned']
                total_found = checkpoint['total_found']
                processed_channels = checkpoint['processed_channels']
                if os.path.exists(LOG_FILE):
                    found_messages = safe_load_json(LOG_FILE)   # ✅ FIXED: use LOG_FILE, not PURGE_LOG_FILE
                    await ctx.send(f"📂 Loaded {len(found_messages)} existing log entries.")
                else:
                    await ctx.send("⚠️ No existing log file found. Starting with empty log.")
                await ctx.send("✅ Resuming scan from checkpoint...")
            else:
                clear_checkpoint()
                if os.path.exists(LOG_FILE):
                    os.remove(LOG_FILE)
                    await ctx.send("Removed old log file for fresh scan.")
                await ctx.send("🔄 Starting fresh scan (checkpoint cleared).")
        except asyncio.TimeoutError:
            await ctx.send("No response. Starting fresh scan.")
            clear_checkpoint()
            if os.path.exists(LOG_FILE):
                os.remove(LOG_FILE)

    channel_list = []
    start_processing = (start_from_channel_id is None)
    for ch in channels:
        if ch.id == start_from_channel_id:
            start_processing = True
        if start_processing:
            channel_list.append(ch)
        else:
            processed_channels += 1

    current_progress.update({
        "total_scanned": total_scanned,
        "total_found": total_found,
        "processed_channels": processed_channels,
        "total_channels": total_channels
    })

    words_display = ', '.join(SEARCH_WORDS)
    await ctx.send(f"🔍 Starting {'scan and delete' if should_delete else 'scan only'} for words: `{words_display}`\n"
                   f"Found {total_channels} text channels to scan.")

    for idx, channel in enumerate(channel_list, start=processed_channels + 1):
        if not scanning_active:
            save_checkpoint(channel.id, None, total_scanned, total_found, processed_channels)
            await ctx.send(f"⏹️ Stopped. Progress saved. Use `!scan` to resume.")
            save_log(found_messages)
            scanning_active = False
            return

        current_progress["current_channel"] = channel.name

        if should_delete and not channel.permissions_for(guild.me).manage_messages:
            await ctx.send(f"⚠️ Skipping #{channel.name} – missing Manage Messages.")
            processed_channels += 1
            continue

        max_attempts = 20
        attempt = 0
        channel_success = False
        last_successful_message_id = start_from_message_id if channel.id == start_from_channel_id else None

        while not channel_success and attempt < max_attempts and scanning_active:
            attempt += 1
            try:
                if attempt > 1:
                    wait_time = min(30, 2 ** attempt)
                    await ctx.send(f"🔄 Retry {attempt}/{max_attempts} for #{channel.name} after {wait_time}s...")
                    await asyncio.sleep(wait_time)

                await ctx.send(f"🔎 Scanning #{channel.name} (attempt {attempt})...")

                after_id = last_successful_message_id if channel.id == start_from_channel_id else None
                use_after_date = SCAN_START_DATE if after_id is None else None

                async for message in fetch_history_with_retry(
                    channel,
                    after_id=after_id,
                    after_date=use_after_date,
                    before_date=SCAN_END_DATE
                ):
                    if not scanning_active:
                        save_checkpoint(channel.id, message.id, total_scanned, total_found, processed_channels)
                        await ctx.send(f"⏹️ Stopped mid-channel. Progress saved.")
                        save_log(found_messages)
                        scanning_active = False
                        return

                    total_scanned += 1

                    word_found = False
                    match_location = "content"
                    matched_word = None

                    if contains_word(message.content):
                        word_found = True
                        match_location = "content"
                        matched_word = get_matching_keyword(message.content)
                    elif message.embeds:
                        for embed in message.embeds:
                            if contains_word(embed.title or ""):
                                word_found = True
                                match_location = "embed_title"
                                matched_word = get_matching_keyword(embed.title or "")
                                break
                            if contains_word(embed.description or ""):
                                word_found = True
                                match_location = "embed_description"
                                matched_word = get_matching_keyword(embed.description or "")
                                break
                    elif message.attachments:
                        for attachment in message.attachments:
                            if contains_word(attachment.filename):
                                word_found = True
                                match_location = "attachment_filename"
                                matched_word = get_matching_keyword(attachment.filename)
                                break

                    if word_found:
                        total_found += 1
                        log_entry = {
                            "message_id": message.id,
                            "channel": channel.name,
                            "channel_id": channel.id,
                            "author": str(message.author),
                            "author_id": message.author.id,
                            "content": message.content,
                            "timestamp": message.created_at.isoformat(),
                            "deleted": should_delete,
                            "match_location": match_location,
                            "matched_keyword": matched_word
                        }
                        found_messages.append(log_entry)

                        if should_delete:
                            await safe_delete_message(ctx, message)

                    last_successful_message_id = message.id

                    if total_scanned % 100 == 0:
                        current_progress.update({
                            "total_scanned": total_scanned,
                            "total_found": total_found,
                            "processed_channels": processed_channels
                        })

                channel_success = True
                processed_channels += 1
                start_from_message_id = None
                save_checkpoint(channel.id, None, total_scanned, total_found, processed_channels)
                save_log(found_messages)
                await ctx.send(f"📊 Progress: #{channel.name} done | {total_scanned:,} scanned, {total_found} found")

            except discord.Forbidden:
                await ctx.send(f"⛔ Cannot read history in #{channel.name} – skipping.")
                processed_channels += 1
                channel_success = True
                break
            except Exception as e:
                await ctx.send(f"⚠️ Error in #{channel.name} (attempt {attempt}/{max_attempts}): {e}")
                if attempt >= max_attempts:
                    await ctx.send(f"❌ Giving up on #{channel.name} after {max_attempts} attempts.")
                    save_checkpoint(channel.id, last_successful_message_id, total_scanned, total_found, processed_channels)
                    scanning_active = False
                    return

    clear_checkpoint()
    save_log(found_messages)
    await ctx.send(f"✅ {'Deletion' if should_delete else 'Scan'} Complete\n"
                   f"   Channels: {processed_channels}/{total_channels}\n"
                   f"   Scanned: {total_scanned:,}\n"
                   f"   {'Deleted' if should_delete else 'Found'}: {total_found:,}\n"
                   f"   Log: {LOG_FILE}")
    scanning_active = False


# ========== COMMANDS ==========
@bot.command()
async def scan(ctx, delete: str = None):
    if delete not in ['no', 'yes']:
        await ctx.send("Usage: `!scan no` (test) or `!scan yes` (delete)")
        return
    if scanning_active:
        await ctx.send("⚠️ Scan already running. Use `!stop` first.")
        return
    should_delete = (delete == 'yes')
    if should_delete:
        await ctx.send("⚠️ **WARNING**: This will permanently delete messages. Type `confirm` within 30s.")
        try:
            await bot.wait_for('message', timeout=30,
                               check=lambda m: m.author == ctx.author and m.content.lower() == 'confirm')
        except asyncio.TimeoutError:
            await ctx.send("Cancelled.")
            return
    await scan_and_delete(ctx, should_delete)

@bot.command()
async def purge(ctx, arg1: str = None, arg2: str = None):
    """!purge embed no – dry run (count embeds)
       !purge embed yes – delete all messages with embeds within date range"""
    # Check if the command is called correctly
    if arg1 != 'embed' or arg2 not in ['no', 'yes']:
        await ctx.send("Usage: `!purge embed no` (test) or `!purge embed yes` (delete)")
        return
    
    if scanning_active:
        await ctx.send("⚠️ A scan is already running. Use `!stop` first.")
        return
    
    should_delete = (arg2 == 'yes')
    
    if should_delete:
        await ctx.send("⚠️ **WARNING**: This will delete ALL messages containing embeds within the date range.\n"
                       "Type `confirm purge` within 30 seconds to proceed.")
        try:
            await bot.wait_for('message', timeout=30,
                               check=lambda m: m.author == ctx.author and m.content.lower() == 'confirm purge')
        except asyncio.TimeoutError:
            await ctx.send("Cancelled.")
            return
    
    await scan_and_purge_embeds(ctx, should_delete)


@bot.command()
async def stop(ctx):
    global scanning_active
    if scanning_active:
        scanning_active = False
        await ctx.send("⏹️ Stopping... progress saved. Use `!scan` to resume.")
    else:
        await ctx.send("No scan running.")


@bot.command()
async def status(ctx):
    """!status - Show detailed scan progress including current channel and date filter"""
    if not scanning_active:
        await ctx.send("No scan is currently running.")
        return

    prog = current_progress
    if prog["total_channels"] == 0:
        await ctx.send("Scan is initializing...")
        return

    channels_done = prog["processed_channels"]
    channels_total = prog["total_channels"]
    channels_percent = (channels_done / channels_total * 100) if channels_total > 0 else 0

    scanned = prog["total_scanned"]
    found = prog["total_found"]
    current_channel = prog.get("current_channel", "unknown")

    date_range_str = "No date filter"
    if SCAN_START_DATE or SCAN_END_DATE:
        start_str = SCAN_START_DATE.strftime("%Y-%m-%d") if SCAN_START_DATE else "beginning"
        end_str = SCAN_END_DATE.strftime("%Y-%m-%d") if SCAN_END_DATE else "now"
        date_range_str = f"{start_str} → {end_str}"

    await ctx.send(
        f"📊 **Scan Progress**\n"
        f"```\n"
        f"Current channel: #{current_channel}\n"
        f"Channels: {channels_done}/{channels_total} ({channels_percent:.1f}%)\n"
        f"Messages scanned: {scanned:,}\n"
        f"Messages found: {found:,}\n"
        f"Date filter: {date_range_str}\n"
        f"```\n"
        f"Use `!stop` to save progress and exit."
    )


@bot.command()
async def save(ctx):
    if scanning_active:
        await ctx.send("💾 Progress is saved automatically after each channel. Use `!stop` to save and exit.")
    else:
        await ctx.send("No scan active.")


@bot.command()
async def delete(ctx):
    """!delete - Delete all messages previously found by !scan no or !purge embed no"""
    global scanning_active

    PURGE_LOG_FILE = 'purged_embeds.json'

    if scanning_active:
        await ctx.send("⚠️ A scan is currently running. Use `!stop` first.")
        return

    # Load both logs safely
    scan_entries = safe_load_json(LOG_FILE)
    purge_entries = safe_load_json(PURGE_LOG_FILE)

    if not scan_entries and not purge_entries:
        await ctx.send("❌ No log files found. Run `!scan no` or `!purge embed no` first.")
        return

    # Filter out already deleted messages
    scan_to_delete = [e for e in scan_entries if not e.get("deleted", False)]
    purge_to_delete = [e for e in purge_entries if not e.get("deleted", False)]
    total_to_delete = len(scan_to_delete) + len(purge_to_delete)

    if total_to_delete == 0:
        await ctx.send("✅ All logged messages have already been deleted.")
        return

    # Confirmation
    await ctx.send(f"⚠️ **WARNING**: This will delete {total_to_delete} messages permanently.\n"
                   f"   (`{len(scan_to_delete)}` from keyword scan, `{len(purge_to_delete)}` from embed purge)\n"
                   f"Type `confirm delete` within 30 seconds to proceed.")
    try:
        await bot.wait_for('message', timeout=30,
                           check=lambda m: m.author == ctx.author and m.channel == ctx.channel and m.content.lower() == 'confirm delete')
    except asyncio.TimeoutError:
        await ctx.send("Cancelled.")
        return

    # Start deletion
    await ctx.send(f"🗑️ Starting deletion of {total_to_delete} messages. "
                   f"Progress every 25 deletions...")

    deleted_count = 0
    failed_count = 0
    skipped_count = 0
    start_time = asyncio.get_event_loop().time()

    all_entries = scan_to_delete + purge_to_delete
    total = len(all_entries)

    await ctx.send(f"⏳ Processing 0/{total}... (0 deleted, 0 failed)")

    for i, entry in enumerate(all_entries, start=1):
        try:
            channel = bot.get_channel(entry["channel_id"])
            if channel is None:
                channel = await bot.fetch_channel(entry["channel_id"])

            # Try to fetch the message
            try:
                message = await channel.fetch_message(entry["message_id"])
            except discord.NotFound:
                entry["deleted"] = True
                skipped_count += 1
                if i % 25 == 0:
                    if scan_entries:
                        save_log(scan_entries)
                    if purge_entries:
                        temp_file = f"{PURGE_LOG_FILE}.tmp"
                        with open(temp_file, 'w', encoding='utf-8') as f:
                            json.dump(purge_entries, f, indent=2, ensure_ascii=False)
                        os.replace(temp_file, PURGE_LOG_FILE)
                continue

            # Delete with retry on rate limit (no fixed delay)
            while True:
                try:
                    await message.delete()
                    entry["deleted"] = True
                    deleted_count += 1
                    break
                except discord.HTTPException as e:
                    if e.status == 429:  # Rate limited
                        retry_after = e.response.headers.get('Retry-After', 1)
                        try:
                            retry_after = float(retry_after)
                        except:
                            retry_after = 1
                        await ctx.send(f"⏸ Rate limited! Waiting {retry_after:.1f}s before retrying the same message...")
                        await asyncio.sleep(retry_after)
                        # retry deletion (loop continues)
                    else:
                        await ctx.send(f"⚠️ HTTP error deleting {entry['message_id']}: {e.status}")
                        failed_count += 1
                        break
                except discord.Forbidden:
                    await ctx.send(f"❌ No permission to delete {entry['message_id']} in #{entry['channel']}.")
                    failed_count += 1
                    break
                except Exception as e:
                    await ctx.send(f"⚠️ Unexpected error deleting {entry['message_id']}: {e}")
                    failed_count += 1
                    break

        except discord.Forbidden:
            await ctx.send(f"❌ Cannot access channel #{entry['channel']} (missing permissions).")
            failed_count += 1
        except Exception as e:
            await ctx.send(f"⚠️ Unexpected error processing {entry['message_id']}: {e}")
            failed_count += 1

        # Progress update every 25 messages
        if i % 25 == 0 or i == total:
            elapsed = asyncio.get_event_loop().time() - start_time
            rate = i / elapsed if elapsed > 0 else 0
            await ctx.send(
                f"📊 Progress: **{i}/{total}** processed | "
                f"✅ Deleted: {deleted_count} | ❌ Failed: {failed_count} | ⏭️ Skipped: {skipped_count}\n"
            )
            # Save logs periodically
            if scan_entries:
                save_log(scan_entries)
            if purge_entries:
                temp_file = f"{PURGE_LOG_FILE}.tmp"
                with open(temp_file, 'w', encoding='utf-8') as f:
                    json.dump(purge_entries, f, indent=2, ensure_ascii=False)
                os.replace(temp_file, PURGE_LOG_FILE)

    # Final save
    if scan_entries:
        save_log(scan_entries)
    if purge_entries:
        temp_file = f"{PURGE_LOG_FILE}.tmp"
        with open(temp_file, 'w', encoding='utf-8') as f:
            json.dump(purge_entries, f, indent=2, ensure_ascii=False)
        os.replace(temp_file, PURGE_LOG_FILE)

    elapsed_total = asyncio.get_event_loop().time() - start_time
    await ctx.send(
        f"✅ **Deletion complete**\n"
        f"   └ Total processed: {total}\n"
        f"   └ Deleted: {deleted_count}\n"
        f"   └ Failed: {failed_count}\n"
        f"   └ Already gone: {skipped_count}\n"
    )

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user} (ID: {bot.user.id})")
    
    # Clear any old slash commands (global)
    bot.tree.clear_commands(guild=None)   # <-- no await here
    await bot.tree.sync()                 # <-- only sync is async
    print("Cleared old slash commands.")
    
    # Rest of your existing on_ready code...
    print(f"Target words: {', '.join(SEARCH_WORDS)}")
    print(f"Case sensitive: {CASE_SENSITIVE}")
    print(f"Log file: {LOG_FILE}")
    print("------")
    print(f"Bot is in {len(bot.guilds)} guild(s)")
    for guild in bot.guilds:
        print(f"  - {guild.name} (ID: {guild.id})")

@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CommandNotFound):
        return
    raise error


# ========== RUN ==========
def main():
    if not TOKEN:
        raise ValueError("Bot token not found. Set DISCORD_TOKEN in .env")
    bot.run(TOKEN)

if __name__ == "__main__":
    main()