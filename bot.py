import os
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters

# =========================
# 🔐 CONFIG
# =========================
TOKEN = os.getenv("TOKEN")

ADMIN_ID = 5447711661

VIP_FILE = "vip.txt"
USERS_FILE = "users.txt"
COUPON_VIP_FILE = "coupon_vip.txt"
COUPON_FREE_FILE = "coupon_free.txt"

# =========================
# 📦 LOAD / SAVE
# =========================
def load_list(file):
    try:
        with open(file, "r") as f:
            return [int(x) for x in f.read().split()]
    except:
        return []

def save_list(file, data):
    with open(file, "w") as f:
        f.write(" ".join(map(str, data)))

vip_users = load_list(VIP_FILE)
users = load_list(USERS_FILE)

def save_user(user_id):
    if user_id not in users:
        users.append(user_id)
        save_list(USERS_FILE, users)

# =========================
# 🎫 COUPONS
# =========================
def read_file(file):
    try:
        with open(file, "r", encoding="utf-8") as f:
            return f.read()
    except:
        return "Aucun contenu disponible."

# =========================
# 🚀 START
# =========================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    save_user(user_id)

    keyboard = [
        ["🎫 Coupon Gratuit"],
        ["💎 Coupon VIP"],
        ["💳 Paiement"],
        ["🆔 Mon ID"],
        ["📊 Résultats"],
        ["📞 Contact"]
    ]

    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

    await update.message.reply_text(
        "👋 Bienvenue sur COUPON VIP PRO",
        reply_markup=reply_markup
    )

# =========================
# 💬 MESSAGE HANDLER
# =========================
async def handle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    text = update.message.text

    save_user(user_id)

    # 🎫 GRATUIT
    if text == "🎫 Coupon Gratuit":
        await update.message.reply_text(read_file(COUPON_FREE_FILE))

    # 💎 VIP
    elif text == "💎 Coupon VIP":
        if user_id in vip_users:
            await update.message.reply_text(read_file(COUPON_VIP_FILE))
        else:
            await update.message.reply_text("❌ VIP requis")

    # 💳 PAIEMENT
    elif text == "💳 Paiement":
        await update.message.reply_text(
            "💰 Paiement VIP : 2500 FCFA\n\n"
            "📱 Mobile Money : +2250586692183\n"
            "👤 Admin : @HardingMichelle"
        )

    # 🆔 ID
    elif text == "🆔 Mon ID":
        await update.message.reply_text(f"🆔 {user_id}")

    # 📊 RESULTATS
    elif text == "📊 Résultats":
        await update.message.reply_text("📊 Victoires: 12\n❌ Défaites: 2")

    # 📞 CONTACT
    elif text == "📞 Contact":
        await update.message.reply_text(
            "👤 @HardingMichelle\n📱 +2250586692183"
        )

# =========================
# 👑 ADMIN COMMANDS
# =========================

async def addvip(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.from_user.id != ADMIN_ID:
        return

    if context.args:
        uid = int(context.args[0])
        if uid not in vip_users:
            vip_users.append(uid)
            save_list(VIP_FILE, vip_users)
        await update.message.reply_text(f"✅ VIP ajouté : {uid}")

async def delvip(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.from_user.id != ADMIN_ID:
        return

    if context.args:
        uid = int(context.args[0])
        if uid in vip_users:
            vip_users.remove(uid)
            save_list(VIP_FILE, vip_users)
        await update.message.reply_text(f"❌ VIP supprimé : {uid}")

async def listvip(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.from_user.id != ADMIN_ID:
        return

    await update.message.reply_text(
        "👑 VIP LIST:\n" + "\n".join(map(str, vip_users))
    )

# =========================
# 🚀 BOT START
# =========================
app = ApplicationBuilder().token(TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("addvip", addvip))
app.add_handler(CommandHandler("delvip", delvip))
app.add_handler(CommandHandler("listvip", listvip))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle))

print("Bot en ligne...")
app.run_polling()
