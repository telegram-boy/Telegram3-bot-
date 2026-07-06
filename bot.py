import os
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters

# 🔐 TOKEN (Railway / Termux env)
TOKEN = os.getenv("TOKEN")

# 👑 ID ADMIN (REMPLACE PAR TON ID)
ADMIN_ID = 5447711661

# 📁 FICHIER VIP
VIP_FILE = "vip.txt"

# =========================
# 🎫 COUPONS (MODIFIABLES ICI)
# =========================

COUPON_FREE = """
🎫 COUPON GRATUIT

⚽ Match 
➡️ x
📊 Cote : x
"""

COUPON_VIP = """
💎 COUPON VIP

⚽ Match 1
➡️ x
📊 Cote : x

⚽ Match 2
➡️ x
📊 Cote : x

🎯 Cote totale : x
"""

# =========================
# 👑 VIP SYSTEM
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
# 🚀 START MENU
# =========================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        ["🎫 Coupon Gratuit"],
        ["💎 Coupon VIP"],
        ["Abonnement 💳"],
        ["🆔 Mon ID"],
        ["📞 Contact Admin"]
    ]

    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

    await update.message.reply_text(
        "👋 Bienvenue sur COUPON VIP. Pour profiter des meilleurs côte prends un abonnement sur le bouton Abonnement💳",
        reply_markup=reply_markup
    )

# =========================
# 💬 HANDLE MESSAGES
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
            await update.message.reply_text(COUPON_VIP)
        else:
            await update.message.reply_text("❌ Accès VIP refusé")

    # 💳 PAIEMENT
    elif text == "Abonnement 💳":
        await update.message.reply_text(
            " L'abonnement Mois est de 2,500XOF et l'abonnement semaine est 1,500XOF."
            "📩 Envoie ton ID Telegram suivie de la capture du paiement à l'admin pour validation."
            " Après paiement si vous contacter que le service mets plus de temps à vous acceptez dans l'onglet COUPON VIP, recontacter le service"
        )

    # 🆔 ID
    elif text == "🆔 Mon ID":
        await update.message.reply_text(f"🆔 Ton ID : {user_id}")

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

print("🤖 Bot en ligne...")
app.run_polling()
