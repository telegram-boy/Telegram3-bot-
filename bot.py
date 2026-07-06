import os
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters
)

# 🔐 TOKEN
TOKEN = os.getenv("TOKEN")

# 👑 ADMIN
ADMIN_ID = 5447711661

# 💰 PAIEMENT
PAY_NUMBER = "+2250789247884"

# 📁 VIP STORAGE
VIP_FILE = "vip.txt"

# =========================
# 🎫 COUPONS
# =========================

COUPON_FREE = """
🎫 COUPON GRATUIT

⚽ Match Portugal vs Espagne
➡️ +0.5 but Portugal
📊 Cote : 1.41

👉 Les meilleures côtes sont dans les Coupons VIP 💎
"""

COUPON_VIP = """
💎 COUPON VIP

⚽ Match 1 : BK Hacken vs Djurgarden
➡️ -3.5 buts
📊 Cote : 1.57

⚽ Match 2 : Portugal vs Espagne
➡️ VN 1ère mi-temps
📊 Cote : 1.52

📊 Cote combinée : 2.73
🔥 Probabilité : 80%
🍀 Good luck
"""

# =========================
# 👑 VIP SYSTEM
# =========================

def load_vips():
    try:
        with open(VIP_FILE, "r") as f:
            return set(map(int, f.read().split()))
    except:
        return set()

def save_vips(vips):
    with open(VIP_FILE, "w") as f:
        f.write(" ".join(map(str, vips)))

vip_users = load_vips()

# =========================
# 📱 MENU
# =========================

def keyboard():
    return ReplyKeyboardMarkup([
        ["🎫 Coupon Gratuit"],
        ["💎 Coupon VIP"],
        ["💳 Abonnement"],
        ["✅ J'ai payé"],
        ["🆔 Mon ID"],
        ["📞 Contact Admin"]
    ], resize_keyboard=True)

# =========================
# 🚀 START
# =========================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Bienvenue sur COUPON VIP 💎\n"
        "Pour profiter de meilleures côtes, souscris à un abonnement 💳\n\n"
        "Choisis une option 👇",
        reply_markup=keyboard()
    )

# =========================
# 💬 HANDLER
# =========================

async def handle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    text = update.message.text

    # 🎫 FREE
    if text == "🎫 Coupon Gratuit":
        await update.message.reply_text(COUPON_FREE)

    # 💎 VIP
    elif text == "💎 Coupon VIP":
        if user_id in vip_users:
            await update.message.reply_text(COUPON_VIP)
        else:
            await update.message.reply_text("❌ Accès VIP refusé")

    # 💳 ABONNEMENT
    elif text == "💳 Abonnement":
        await update.message.reply_text(
            "💳 ABONNEMENT VIP\n\n"
            "🗓️ Semaine : 1 500 XOF (7 jours)\n"
            "📅 Mois : 2 500 XOF (30 jours)\n\n"
            "💰 Paiement : Wave / Orange Money\n"
            f"📞 Numéro : {PAY_NUMBER}\n\n"
            "⚠️ Paiement non remboursable\n"
            "📌 L’admin choisit la formule (7 ou 30 jours)\n\n"
            "📌 Étapes :\n"
            "1️⃣ Envoie ton ID Telegram\n"
            "2️⃣ Envoie la capture de paiement\n"
            "3️⃣ Validation admin\n\n"
            "⏳ Délai max : 24h"
        )

    # ✅ J'AI PAYÉ
    elif text == "✅ J'ai payé":

        if user_id in vip_users:
            await update.message.reply_text(
                "🎉 Vous êtes déjà abonné VIP\n"
                "👉 Cliquez sur 💎 Coupon VIP"
            )
            return

        await update.message.reply_text(
            "📩 Demande reçue\n\n"
            "Votre paiement est en cours de vérification\n"
            "⏳ Délai max : 12h\n"
            "📞 Contact support si retard"
        )

    # 🆔 ID
    elif text == "🆔 Mon ID":
        await update.message.reply_text(f"🆔 Ton ID : {user_id}")

    # 📞 CONTACT
    elif text == "📞 Contact Admin":
        await update.message.reply_text(
            f"📞 Admin : @HardingMichelle\n💰 {PAY_NUMBER}"
        )

# =========================
# 📸 PHOTO HANDLER
# =========================

async def photo_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id

    await context.bot.send_photo(
        chat_id=ADMIN_ID,
        photo=update.message.photo[-1].file_id,
        caption=(
            "💰 NOUVEAU PAIEMENT\n\n"
            f"👤 USER ID : {user_id}\n\n"
            f"✔ /addvip7 {user_id}\n"
            f"✔ /addvip30 {user_id}\n"
            f"❌ /removevip {user_id}"
        )
    )

    await update.message.reply_text("📩 Capture envoyée à l’admin")

# =========================
# 👑 VIP 7 JOURS
# =========================

async def addvip7(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.from_user.id != ADMIN_ID:
        return

    uid = int(context.args[0])
    vip_users.add(uid)
    save_vips(vip_users)

    await context.bot.send_message(
        chat_id=uid,
        text=(
            "🎉 Félicitations 🎉\n\n"
            "Votre abonnement VIP 7 jours est activé\n"
            "💎 Profitez de vos pronostics"
        )
    )

    await update.message.reply_text("✅ VIP 7 jours ajouté")

# =========================
# 👑 VIP 30 JOURS
# =========================

async def addvip30(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.from_user.id != ADMIN_ID:
        return

    uid = int(context.args[0])
    vip_users.add(uid)
    save_vips(vip_users)

    await context.bot.send_message(
        chat_id=uid,
        text=(
            "🎉 Félicitations 🎉\n\n"
            "Votre abonnement VIP 30 jours est activé\n"
            "💎 Profitez de vos pronostics"
        )
    )

    await update.message.reply_text("✅ VIP 30 jours ajouté")

# =========================
# ❌ REMOVE VIP
# =========================

async def removevip(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.from_user.id != ADMIN_ID:
        return

    uid = int(context.args[0])
    vip_users.discard(uid)
    save_vips(vip_users)

    await context.bot.send_message(
        chat_id=uid,
        text="⚠️ Votre VIP est terminé. Merci 💙"
    )

    await update.message.reply_text("❌ VIP retiré")

# =========================
# 📋 LIST VIP
# =========================

async def listvip(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.from_user.id != ADMIN_ID:
        return

    if vip_users:
        await update.message.reply_text(
            "👑 VIP LIST:\n" + "\n".join(map(str, vip_users))
        )
    else:
        await update.message.reply_text("Aucun VIP")

# =========================
# 🚀 BOT START
# =========================

app = ApplicationBuilder().token(TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle))
app.add_handler(MessageHandler(filters.PHOTO, photo_handler))

app.add_handler(CommandHandler("addvip7", addvip7))
app.add_handler(CommandHandler("addvip30", addvip30))
app.add_handler(CommandHandler("removevip", removevip))
app.add_handler(CommandHandler("listvip", listvip))

print("🤖 BOT VIP OK")
app.run_polling()
