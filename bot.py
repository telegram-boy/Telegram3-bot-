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

# 👑 ADMIN ID
ADMIN_ID = 5447711661

# 💰 NUMÉRO PAIEMENT
PAY_NUMBER = "+2250789247884"

# 📁 VIP FILE
VIP_FILE = "vip.txt"

# =========================
# 🎫 COUPONS
# =========================

COUPON_FREE = """
🎫 COUPON GRATUIT

⚽ Match exemple
➡️ +1.5 buts
📊 Cote : 1.50
"""

COUPON_VIP = """
💎 COUPON VIP

⚽ Match VIP
➡️ Victoire équipe A
📊 Cote : 2.10
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
        "Choisis une option 👇",
        reply_markup=keyboard()
    )

# =========================
# 💬 MESSAGE HANDLER
# =========================

async def handle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    text = update.message.text

    # 🎫 GRATUIT
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
            "🗓️ Semaine : 1 500 XOF\n"
            "📅 Mois : 2 500 XOF\n\n"
            "💰 Moyens de paiement :\n"
            "✔ Wave\n"
            "✔ Orange Money\n"
            f"📞 Numéro : {PAY_NUMBER}\n\n"
            "📌 Étapes :\n"
            "1️⃣ Envoie ton ID Telegram\n"
            "2️⃣ Envoie la capture du paiement\n"
            "3️⃣ Validation admin\n\n"
            "⏳ Traitement max : 24h\n"
            "⚠️ Si retard > 12h contacte le support"
        )

    # ✅ J'AI PAYÉ
    elif text == "✅ J'ai payé":
        await update.message.reply_text(
            "📩 Demande reçue ✅\n\n"
            "Votre paiement est en cours de vérification.\n"
            "Un administrateur va vérifier votre transaction.\n\n"
            "⏳ Délai maximum : 12 heures\n"
            "📞 Si aucun retour après 12h, contactez le support."
        )

    # 🆔 ID
    elif text == "🆔 Mon ID":
        await update.message.reply_text(f"🆔 Ton ID Telegram : {user_id}")

    # 📞 CONTACT
    elif text == "📞 Contact Admin":
        await update.message.reply_text(
            "📞 Admin : @HardingMichelle\n"
            f"💰 Paiement : {PAY_NUMBER}"
        )

# =========================
# 📸 PHOTO HANDLER (CAPTURES)
# =========================

async def photo_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id

    await context.bot.send_photo(
        chat_id=ADMIN_ID,
        photo=update.message.photo[-1].file_id,
        caption=(
            "💰 NOUVEAU PAIEMENT\n\n"
            f"👤 USER ID : {user_id}\n\n"
            "📌 Action admin :\n"
            f"/addvip {user_id}\n"
            f"/removevip {user_id}"
        )
    )

    await update.message.reply_text(
        "📩 Capture envoyée à l’admin. Traitement en cours..."
    )

# =========================
# 👑 ADMIN COMMANDS
# =========================

async def addvip(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.from_user.id != ADMIN_ID:
        return

    try:
        uid = int(context.args[0])
        vip_users.add(uid)
        save_vips(vip_users)

        await context.bot.send_message(
            chat_id=uid,
            text=(
                "🎉 Félicitations 🎉\n\n"
                "Votre abonnement VIP a été activé avec succès.\n"
                "📅 Durée : 7 jours\n\n"
                "💎 Cliquez sur '💎 Coupon VIP' pour voir les pronostics."
            )
        )

        await update.message.reply_text("✅ VIP ajouté avec succès")
    except:
        await update.message.reply_text("❌ Erreur")

async def removevip(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.from_user.id != ADMIN_ID:
        return

    try:
        uid = int(context.args[0])
        vip_users.discard(uid)
        save_vips(vip_users)

        await context.bot.send_message(
            chat_id=uid,
            text="⚠️ Votre abonnement VIP est terminé. Merci 💙"
        )

        await update.message.reply_text("❌ VIP retiré")
    except:
        await update.message.reply_text("❌ Erreur")

async def listvip(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.from_user.id != ADMIN_ID:
        return

    if vip_users:
        await update.message.reply_text(
            "👑 LISTE VIP :\n" + "\n".join(map(str, vip_users))
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

app.add_handler(CommandHandler("addvip", addvip))
app.add_handler(CommandHandler("removevip", removevip))
app.add_handler(CommandHandler("listvip", listvip))

print("🤖 BOT VIP EN LIGNE")
app.run_polling()
