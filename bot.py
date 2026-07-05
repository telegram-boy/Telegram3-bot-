import os
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters

TOKEN = os.getenv("TOKEN")

# 👑 TON ID ADMIN (REMPLACE)
ADMIN_ID = 5447711661

# 📁 VIP STORAGE
VIP_FILE = "vip.txt"

# =========================
# 🔧 VIP FUNCTIONS
# =========================
def load_vips():
    try:
        with open(VIP_FILE, "r") as f:
            return [int(x) for x in f.read().split()]
    except:
        return []

def save_vips(vips):
    with open(VIP_FILE, "w") as f:
        f.write(" ".join(map(str, vips)))

vip_users = load_vips()

# =========================
# 🎫 COUPONS
# =========================
COUPON_FREE = """
🎫 COUPON GRATUIT

⚽ Match Example
➡️ +1.5 buts
📊 Cote : 1.60

🎯 Bonne chance 🍀
"""

def get_coupon():
    try:
        with open("coupon.txt", "r", encoding="utf-8") as f:
            return f.read()
    except:
        return "❌ Aucun coupon disponible."

# =========================
# 🚀 START
# =========================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        ["🎫 Coupon Gratuit"],
        ["💎 Coupon VIP"],
        ["💳 J'ai payé"],
        ["🆔 Mon ID"],
        ["📊 Résultats"],
        ["📞 Contact Admin"]
    ]

    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

    await update.message.reply_text(
        "👋 Bienvenue sur COUPON VIP",
        reply_markup=reply_markup
    )

# =========================
# 💬 HANDLE
# =========================
async def handle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    text = update.message.text

    global vip_users

    # 🎫 GRATUIT
    if text == "🎫 Coupon Gratuit":
        await update.message.reply_text(COUPON_FREE)

    # 💎 VIP
    elif text == "💎 Coupon VIP":
        if user_id in vip_users:
            await update.message.reply_text(get_coupon())
        else:
            await update.message.reply_text("❌ Accès VIP refusé")

    # 💳 PAYÉ
    elif text == "💳 J'ai payé":
        await update.message.reply_text(
            "📩 Envoie ton ID Telegram ici.\n"
            "👉 Admin vérifiera ton paiement."
        )

    # 🆔 ID
    elif text == "🆔 Mon ID":
        await update.message.reply_text(f"🆔 Ton ID : {user_id}")

    # 📊 RESULTATS
    elif text == "📊 Résultats":
        await update.message.reply_text(
            "📊 Stats :\n"
            "✅ Victoires : 12\n"
            "❌ Défaites : 2"
        )

    # 📞 CONTACT
    elif text == "📞 Contact Admin":
        await update.message.reply_text(
            "📞 Admin : @HardingMichelle\n"
            "💰 Paiement : +2250586692183"
        )

# =========================
# 👑 ADD VIP (ADMIN ONLY)
# =========================
async def addvip(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global vip_users

    if update.message.from_user.id != ADMIN_ID:
        return

    if context.args:
        try:
            uid = int(context.args[0])

            if uid not in vip_users:
                vip_users.append(uid)
                save_vips(vip_users)

            await update.message.reply_text(f"✅ VIP ajouté : {uid}")
        except:
            await update.message.reply_text("❌ ID invalide")

# =========================
# 🚀 BOT START
# =========================
app = ApplicationBuilder().token(TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("addvip", addvip))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle))

print("Bot en ligne...")
app.run_polling()
