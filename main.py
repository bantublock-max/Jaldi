import os
import asyncio
import secrets
import string
from datetime import datetime, timedelta, timezone
from telegram import Update, ChatPermissions
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, MessageHandler, filters
from html import escape

# ========== APNA TOKEN AUR OWNER ID YAHAN DAALO ==========
BOT_TOKEN = "8966663581:AAHqxmlM7C2Hkwz8e8JCR14tWfNAaXnhTOk"
OWNER_ID = 8211620138
# =========================================================

generated_keys = {}
active_users = {}
approved_groups = set()
bot_disabled_groups = set()

# ========== ALAG MAX TIME & COOLDOWN ==========
GROUP_MAX_TIME = 180
DM_MAX_TIME = 300
GROUP_COOLDOWN = 0
DM_COOLDOWN = 0

attack_logs = []
active_attacks = {}
log_counter = 0
user_cooldowns = {}

class AttackRecord:
    def __init__(self, log_id, user_id, username, name, ip, port, duration, source, command_text=""):
        self.log_id = log_id
        self.user_id = user_id
        self.username = username
        self.name = name
        self.ip = ip
        self.port = port
        self.duration = duration
        self.source = source
        self.command_text = command_text
        self.started_at = datetime.now(timezone.utc)
        self.completed_at = None
        self.remaining_seconds = duration
        self.status = "running"

def parse_duration_to_minutes(duration_str):
    duration_str = duration_str.lower().strip()
    try:
        if duration_str.endswith('m'):
            return int(duration_str.replace('m', ''))
        elif duration_str.endswith('h'):
            return int(duration_str.replace('h', '')) * 60
        elif duration_str.endswith('d'):
            return int(duration_str.replace('d', '')) * 1440
        else:
            return int(duration_str)
    except ValueError:
        return None

def generate_dynamic_secure_key(duration_label):
    chars = string.ascii_uppercase + string.digits
    part1 = "".join(secrets.choice(chars) for _ in range(4))
    part2 = "".join(secrets.choice(chars) for _ in range(4))
    return f"OWNER1865-FAAA-{duration_label.upper()}-{part1}-{part2}"

def get_target_user_safe(update: Update):
    if update.message.reply_to_message:
        return update.message.reply_to_message.from_user
    if update.message.entities:
        for entity in update.message.entities:
            if entity.type == "text_mention" and entity.user:
                return entity.user
    return None

async def is_group_bot_disabled(update: Update) -> bool:
    chat = update.effective_chat
    if chat.type not in ('group', 'supergroup'):
        return False
    if chat.id in bot_disabled_groups and update.effective_user.id != OWNER_ID:
        return True
    return False

def is_user_premium(user_id):
    if user_id == OWNER_ID:
        return True
    now_time = datetime.now(timezone.utc)
    if user_id in active_users and active_users[user_id]["expiry"] > now_time:
        return True
    return False

def is_user_in_cooldown(user_id, cd_seconds):
    if user_id == OWNER_ID:
        return False
    if cd_seconds <= 0:
        return False
    if user_id in user_cooldowns:
        now = datetime.now(timezone.utc)
        if user_cooldowns[user_id] > now:
            return int((user_cooldowns[user_id] - now).total_seconds())
    return False

def apply_cooldown(user_id, cd_seconds):
    if user_id == OWNER_ID:
        return
    if cd_seconds > 0:
        user_cooldowns[user_id] = datetime.now(timezone.utc) + timedelta(seconds=cd_seconds)

async def botoff_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != OWNER_ID:
        await update.message.reply_text("❌ Ye command sirf Bot Owner use kar sakta hai!")
        return
    chat = update.effective_chat
    if chat.type == 'private':
        await update.message.reply_text("❌ Yeh command sirf group mein kaam karegi!")
        return
    bot_disabled_groups.add(chat.id)
    await update.message.reply_text(f"🔴 **BOT OFF - THIS GROUP ONLY!**\nGroup ID: `{chat.id}`", parse_mode="Markdown")

async def boton_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != OWNER_ID:
        await update.message.reply_text("❌ Ye command sirf Bot Owner use kar sakta hai!")
        return
    chat = update.effective_chat
    if chat.type == 'private':
        await update.message.reply_text("❌ Yeh command sirf group mein kaam karegi!")
        return
    if chat.id in bot_disabled_groups:
        bot_disabled_groups.discard(chat.id)
        await update.message.reply_text(f"🟢 **BOT ON - THIS GROUP ONLY!**", parse_mode="Markdown")
    else:
        await update.message.reply_text("✅ Bot already ON hai!")

async def approve_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await is_group_bot_disabled(update): return
    if update.effective_user.id != OWNER_ID:
        await update.message.reply_text("❌ Sirf Owner!")
        return
    args = context.args
    chat = update.effective_chat
    if not args and chat.type in ('group', 'supergroup'):
        approved_groups.add(chat.id)
        await update.message.reply_text(f"✅ **GROUP APPROVED!**\nGroup ID: `{chat.id}`\n\nAb group mein koi bhi /fa kar sakta hai bina key redeem kiye!\n⏱️ Group Max: <code>{GROUP_MAX_TIME}s</code> | ⏳ Group CD: <code>{GROUP_COOLDOWN}s</code>", parse_mode="Markdown")
        return
    if args:
        try:
            approved_groups.add(int(args[0]))
            await update.message.reply_text(f"✅ **GROUP APPROVED!**\nGroup ID: `{args[0]}`", parse_mode="Markdown")
        except:
            await update.message.reply_text("❌ Galat ID!")

async def disapprove_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await is_group_bot_disabled(update): return
    if update.effective_user.id != OWNER_ID:
        return
    args = context.args
    chat = update.effective_chat
    group_id = None
    if not args and chat.type in ('group', 'supergroup'):
        group_id = chat.id
    elif args:
        try:
            group_id = int(args[0])
        except:
            await update.message.reply_text("❌ Galat ID!")
            return
    if group_id and group_id in approved_groups:
        approved_groups.discard(group_id)
        await update.message.reply_text(f"❌ **GROUP DISAPPROVED!** `{group_id}`", parse_mode="Markdown")
    else:
        await update.message.reply_text("❌ Approved nahi hai!")

async def approve_list_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await is_group_bot_disabled(update): return
    if update.effective_user.id != OWNER_ID:
        return
    if not approved_groups:
        await update.message.reply_text("📭 Koi group approved nahi.")
        return
    text = "✅ **APPROVED GROUPS:**\n\n"
    for gid in approved_groups:
        text += f"• `{gid}`\n"
    text += f"\nTotal: {len(approved_groups)}"
    await update.message.reply_text(text, parse_mode="Markdown")

async def max_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global GROUP_MAX_TIME
    if await is_group_bot_disabled(update): return
    if update.effective_user.id != OWNER_ID:
        await update.message.reply_text("❌ Sirf Owner!")
        return
    args = context.args
    if len(args) < 1:
        await update.message.reply_text("❌ <code>/max SECONDS</code>\nExample: <code>/max 180</code>", parse_mode="HTML")
        return
    try:
        new_max = int(args[0])
    except:
        await update.message.reply_text("❌ Seconds number mein do!")
        return
    if new_max < 1 or new_max > 86400:
        await update.message.reply_text("❌ Range: 1 - 86400s")
        return
    GROUP_MAX_TIME = new_max
    await update.message.reply_text(f"✅ **GROUP MAX TIME UPDATED!**\n🏘️ Group max: <code>{GROUP_MAX_TIME}s</code>", parse_mode="HTML")

async def maxtime_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global DM_MAX_TIME
    if await is_group_bot_disabled(update): return
    if update.effective_user.id != OWNER_ID:
        await update.message.reply_text("❌ Sirf Owner!")
        return
    args = context.args
    if len(args) < 1:
        await update.message.reply_text("❌ <code>/maxtime SECONDS</code>\nExample: <code>/maxtime 300</code>", parse_mode="HTML")
        return
    try:
        new_max = int(args[0])
    except:
        await update.message.reply_text("❌ Seconds number mein do!")
        return
    if new_max < 1 or new_max > 86400:
        await update.message.reply_text("❌ Range: 1 - 86400s")
        return
    DM_MAX_TIME = new_max
    await update.message.reply_text(f"✅ **DM MAX TIME UPDATED!**\n💬 DM max: <code>{DM_MAX_TIME}s</code>", parse_mode="HTML")

async def gcd_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global GROUP_COOLDOWN
    if await is_group_bot_disabled(update): return
    if update.effective_user.id != OWNER_ID:
        await update.message.reply_text("❌ Sirf Owner!")
        return
    args = context.args
    if len(args) < 1:
        await update.message.reply_text("❌ <code>/gcd SECONDS</code>\nExample: <code>/gcd 30</code>", parse_mode="HTML")
        return
    try:
        new_cd = int(args[0])
    except:
        await update.message.reply_text("❌ Seconds number mein do!")
        return
    if new_cd < 0 or new_cd > 86400:
        await update.message.reply_text("❌ Range: 0 - 86400s")
        return
    GROUP_COOLDOWN = new_cd
    if new_cd == 0:
        await update.message.reply_text(f"✅ **GROUP COOLDOWN DISABLED!**", parse_mode="HTML")
    else:
        await update.message.reply_text(f"✅ **GROUP COOLDOWN UPDATED!**\n⏳ <code>{GROUP_COOLDOWN}s</code>", parse_mode="HTML")

async def dmcd_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global DM_COOLDOWN
    if await is_group_bot_disabled(update): return
    if update.effective_user.id != OWNER_ID:
        await update.message.reply_text("❌ Sirf Owner!")
        return
    args = context.args
    if len(args) < 1:
        await update.message.reply_text("❌ <code>/dmcd SECONDS</code>\nExample: <code>/dmcd 60</code>", parse_mode="HTML")
        return
    try:
        new_cd = int(args[0])
    except:
        await update.message.reply_text("❌ Seconds number mein do!")
        return
    if new_cd < 0 or new_cd > 86400:
        await update.message.reply_text("❌ Range: 0 - 86400s")
        return
    DM_COOLDOWN = new_cd
    if new_cd == 0:
        await update.message.reply_text(f"✅ **DM COOLDOWN DISABLED!**", parse_mode="HTML")
    else:
        await update.message.reply_text(f"✅ **DM COOLDOWN UPDATED!**\n⏳ <code>{DM_COOLDOWN}s</code>", parse_mode="HTML")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await is_group_bot_disabled(update): return
    menu = (
        "<b>FAAA ATTACK BOT</b> 💥\n\n"
        "✅ <b>Group mein FREE hai!</b> - Bina key redeem kiye koi bhi /fa kar sakta hai\n\n"
        "👉 <code>/fa IP PORT TIME</code> - Attack karein\n"
        "👉 <code>/max SECONDS</code> - Group max time (Owner)\n"
        "👉 <code>/maxtime SECONDS</code> - DM max time (Owner)\n"
        "👉 <code>/gcd SECONDS</code> - Group cooldown (Owner)\n"
        "👉 <code>/dmcd SECONDS</code> - DM cooldown (Owner)\n"
        "👉 <code>/status</code> - Pura record\n"
        "👉 <code>/redeem KEY</code> - Plan activate (DM)\n"
        "👉 <code>/user</code> - Apna plan\n"
        "👉 <code>/start</code> - Menu"
    )
    if update.effective_user.id == OWNER_ID:
        menu += (
            "\n\n👑 <b>OWNER:</b>\n"
            f"🏘️ Group Max: <code>{GROUP_MAX_TIME}s</code> | ⏳ Group CD: <code>{GROUP_COOLDOWN}s</code>\n"
            f"💬 DM Max: <code>{DM_MAX_TIME}s</code> | ⏳ DM CD: <code>{DM_COOLDOWN}s</code>\n"
            "👉 <code>/gen TIME QTY</code>\n"
            "👉 <code>/id</code> / <code>/mute</code>\n"
            "👉 <code>/approve /disapprove /approve_list</code>\n"
            "👉 <code>/botoff /boton</code>\n"
            "👉 <code>/clearlogs</code>"
        )
    await update.message.reply_text(menu, parse_mode="HTML")

async def gen_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await is_group_bot_disabled(update): return
    if update.effective_user.id != OWNER_ID:
        await update.message.reply_text("❌ Sirf Owner!")
        return
    args = context.args
    if len(args) < 2:
        await update.message.reply_text("❌ Format: <code>/gen 30m 10</code>", parse_mode="HTML")
        return
    minutes = parse_duration_to_minutes(args[0])
    if not minutes or minutes <= 0:
        await update.message.reply_text("❌ Galat time!")
        return
    try:
        qty = int(args[1])
    except:
        await update.message.reply_text("❌ Quantity number mein!")
        return
    if qty > 30:
        await update.message.reply_text("❌ Max 30 keys ek baar!")
        return
    keys = []
    for _ in range(qty):
        key = generate_dynamic_secure_key(args[0])
        generated_keys[key] = minutes
        keys.append(key)
    text = f"🔑 <b>KEYS GENERATED</b>\n⏰ {args[0].upper()} ({minutes} min)\n📊 {qty} keys\n\n"
    for i, k in enumerate(keys, 1):
        text += f"{i}. <code>{k}</code>\n"
    await update.message.reply_text(text, parse_mode="HTML")

async def id_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await is_group_bot_disabled(update): return
    if update.effective_user.id != OWNER_ID:
        return
    target = get_target_user_safe(update)
    if target:
        await update.message.reply_text(f"👤 {escape(target.first_name)}\n🆔 <code>{target.id}</code>", parse_mode="HTML")
    else:
        u = update.effective_user
        await update.message.reply_text(f"👑 {escape(u.first_name)}\n🆔 <code>{u.id}</code>", parse_mode="HTML")

async def mute_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await is_group_bot_disabled(update): return
    if update.effective_user.id != OWNER_ID:
        return
    chat = update.effective_chat
    if chat.type == 'private':
        await update.message.reply_text("❌ Sirf group mein!")
        return
    target = get_target_user_safe(update)
    if not target:
        await update.message.reply_text("❌ Reply karo!")
        return
    if target.id == OWNER_ID:
        await update.message.reply_text("❌ Khud ko nahi!")
        return
    until = datetime.now(timezone.utc) + timedelta(days=3)
    perms = ChatPermissions(can_send_messages=False)
    try:
        await chat.restrict_member(target.id, permissions=perms, until_date=until)
        await update.message.reply_text(f"🤐 {escape(target.first_name)} muted 3 din!")
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {e}")

async def redeem_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await is_group_bot_disabled(update): return
    if update.effective_chat.type != 'private':
        await update.message.reply_text("❌ DM mein karo!")
        return
    args = context.args
    if not args:
        await update.message.reply_text("❌ Key do!")
        return
    key = args[0].strip()
    if key not in generated_keys:
        await update.message.reply_text("❌ Invalid key!")
        return
    mins = generated_keys[key]
    uid = update.effective_user.id
    now = datetime.now(timezone.utc)
    if uid in active_users and active_users[uid]["expiry"] > now:
        new_exp = active_users[uid]["expiry"] + timedelta(minutes=mins)
    else:
        new_exp = now + timedelta(minutes=mins)
    active_users[uid] = {"expiry": new_exp, "key_used": key}
    del generated_keys[key]
    await update.message.reply_text(f"✅ **ACTIVATED!**\n⏳ +{mins} min\n📅 {new_exp.strftime('%Y-%m-%d %H:%M:%S')} UTC", parse_mode="HTML")

async def user_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await is_group_bot_disabled(update): return
    u = update.effective_user
    uid = u.id
    if uid == OWNER_ID:
        await update.message.reply_text(f"👤 {escape(u.first_name)}\n🆔 <code>{uid}</code>\n👑 Owner\n⏳ Lifetime", parse_mode="HTML")
        return
    now = datetime.now(timezone.utc)
    if uid in active_users and active_users[uid]["expiry"] > now:
        left = active_users[uid]["expiry"] - now
        total_sec = int(left.total_seconds())
        h = total_sec // 3600
        m = (total_sec % 3600) // 60
        await update.message.reply_text(f"👤 {escape(u.first_name)}\n🆔 <code>{uid}</code>\n🔑 <code>{active_users[uid]['key_used']}</code>\n⏳ {h}h {m}m", parse_mode="HTML")
    else:
        await update.message.reply_text(f"👤 {escape(u.first_name)}\n🆔 <code>{uid}</code>\n🔒 No plan", parse_mode="HTML")

async def run_attack(update, context, target_ip, target_port, duration, source, command_text=""):
    global log_counter
    user = update.effective_user
    uid = user.id
    uname = user.username or "NoUsername"
    name = user.first_name or "Unknown"
    log_counter += 1
    log_id = f"ATK-{log_counter:04d}"
    rec = AttackRecord(log_id, uid, uname, name, target_ip, target_port, duration, source, command_text)
    active_attacks[log_id] = rec
    location = "GROUP" if update.effective_chat.type in ('group','supergroup') else "DM"
    mention = f"@{uname}" if user.username else f'<a href="tg://user?id={uid}">{escape(name)}</a>'
    def msg_fmt(sec):
        return (f"⚡ <b>ATTACK RUNNING</b>\n🆔 <code>{log_id}</code>\n📍 {location}\n🎯 <code>{target_ip}:{target_port}</code>\n⏱️ <code>{sec}s</code>\n👤 {mention}")
    msg = await update.message.reply_text(msg_fmt(duration), parse_mode="HTML")
    for sec in range(duration - 1, -1, -1):
        await asyncio.sleep(1)
        rec.remaining_seconds = sec
        try:
            await msg.edit_text(msg_fmt(sec), parse_mode="HTML")
        except:
            break
    rec.completed_at = datetime.now(timezone.utc)
    rec.remaining_seconds = 0
    rec.status = "completed"
    attack_logs.append(rec)
    if log_id in active_attacks:
        del active_attacks[log_id]
    try:
        await msg.edit_text(f"✅ <b>COMPLETE!</b>\n🆔 <code>{log_id}</code>\n🎯 <code>{target_ip}:{target_port}</code>\n⏱️ {duration}s\n👤 {mention}", parse_mode="HTML")
    except:
        pass

async def fa_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await is_group_bot_disabled(update): return
    
    user = update.effective_user
    uid = user.id
    chat = update.effective_chat
    
    if chat.type in ('group', 'supergroup'):
        if chat.id not in approved_groups:
            await update.message.reply_text("❌ Group approved nahi! Owner se /approve karwaiye.", parse_mode="Markdown")
            return
        max_time = GROUP_MAX_TIME
        cd_seconds = GROUP_COOLDOWN
        src = "group"
    else:
        if not is_user_premium(uid):
            await update.message.reply_text("❌ DM mein /fa sirf premium users ke liye!\n🔑 /redeem KEY karke plan active karein.", parse_mode="HTML")
            return
        cd_seconds = DM_COOLDOWN
        cd_remaining = is_user_in_cooldown(uid, cd_seconds)
        if cd_remaining:
            await update.message.reply_text(f"⏳ **COOLDOWN ACTIVE!**\n👤 {escape(user.first_name)}, aapko <code>{cd_remaining}s</code> wait karna hoga.", parse_mode="HTML")
            return
        max_time = DM_MAX_TIME
        src = "dm"
    
    args = context.args
    if len(args) < 3:
        await update.message.reply_text("❌ /fa IP PORT TIME")
        return
    
    target_ip = str(args[0])
    target_port = str(args[1])
    
    try:
        duration = int(args[2])
    except:
        await update.message.reply_text("❌ Time number mein!")
        return
    
    if duration > max_time:
        location_name = "Group" if src == "group" else "DM"
        await update.message.reply_text(f"❌ **MAX TIME EXCEEDED!**\n📍 {location_name} max: <code>{max_time}s</code>", parse_mode="HTML")
        return
    if duration < 1:
        await update.message.reply_text("❌ Min 1s!")
        return
    
    cmd = f"/fa {target_ip} {target_port} {duration}"
    
    if cd_seconds > 0:
        apply_cooldown(uid, cd_seconds)
    
    await run_attack(update, context, target_ip, target_port, duration, src, command_text=cmd)

async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await is_group_bot_disabled(update): return
    text = "<b>📊 FULL STATUS REPORT</b>\n\n"
    text += f"⚙️ <b>Config:</b>\n"
    text += f"   🏘️ Group Max: <code>{GROUP_MAX_TIME}s</code> | ⏳ Group CD: <code>{GROUP_COOLDOWN}s</code>\n"
    text += f"   💬 DM Max: <code>{DM_MAX_TIME}s</code> | ⏳ DM CD: <code>{DM_COOLDOWN}s</code>\n\n"
    text += "━━━ <b>🔥 ACTIVE ATTACKS</b> ━━━\n\n"
    if active_attacks:
        for log_id, rec in active_attacks.items():
            text += f"⚡ <code>{log_id}</code> | 👤 @{rec.username} | 🎯 <code>{rec.ip}:{rec.port}</code> | ⏱️ <b>{rec.remaining_seconds}s</b>\n"
    else:
        text += "❌ Koi active attack nahi.\n"
    text += "\n━━━ <b>📋 HISTORY (Last 10)</b> ━━━\n\n"
    if attack_logs:
        for rec in attack_logs[-10:]:
            text += f"📌 <code>{rec.log_id}</code> | 👤 @{rec.username} | 🎯 <code>{rec.ip}:{rec.port}</code> | ⏱️ {rec.duration}s ✅\n"
    else:
        text += "❌ Koi history nahi.\n"
    text += f"\n━━━ SUMMARY ━━━\n⚡ Active: {len(active_attacks)} | 📋 Total: {len(attack_logs)}"
    await update.message.reply_text(text, parse_mode="HTML")

async def clearlogs_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await is_group_bot_disabled(update): return
    if update.effective_user.id != OWNER_ID:
        return
    attack_logs.clear()
    await update.message.reply_text("✅ **ALL LOGS CLEARED!**", parse_mode="Markdown")

async def dm_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await is_group_bot_disabled(update): return
    if update.effective_chat.type == 'private':
        await update.message.reply_text("Content admin")

app = ApplicationBuilder().token(BOT_TOKEN).build()
app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("gen", gen_command))
app.add_handler(CommandHandler("id", id_command))
app.add_handler(CommandHandler("mute", mute_command))
app.add_handler(CommandHandler("redeem", redeem_command))
app.add_handler(CommandHandler("user", user_command))
app.add_handler(CommandHandler("fa", fa_command))
app.add_handler(CommandHandler("approve", approve_command))
app.add_handler(CommandHandler("disapprove", disapprove_command))
app.add_handler(CommandHandler("approve_list", approve_list_command))
app.add_handler(CommandHandler("botoff", botoff_command))
app.add_handler(CommandHandler("boton", boton_command))
app.add_handler(CommandHandler("max", max_command))
app.add_handler(CommandHandler("maxtime", maxtime_command))
app.add_handler(CommandHandler("gcd", gcd_command))
app.add_handler(CommandHandler("dmcd", dmcd_command))
app.add_handler(CommandHandler("status", status_command))
app.add_handler(CommandHandler("clearlogs", clearlogs_command))
app.add_handler(MessageHandler(filters.ChatType.PRIVATE & ~filters.COMMAND, dm_handler))
print("FAAA BOT Active...")
app.run_polling()