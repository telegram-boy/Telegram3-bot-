import os
import time
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

# 📁 VIP FILE
VIP_FILE = "vip.txt"

# =========================
# 🎫 COUPONS
# =========================

COUPON_FREE = """
🎫 COUPON GRATUIT

⚽ Match Portugal vs Espagne
➡️ +0.5 but Portugal
📊 Cote : 1.41
"""

COUPON_VIP = """
💎 COUPON VIP

⚽ Match VIP du jour
➡️ Analyse premium
📊 Cote : 2.00+
🔥 Bonne chance
"""

# =========================
# 👑 VIP SYSTEM (EXPIRATION)
# =========================

def load_vips():
    try:
        with open(VIP_FILE, "r") as f:
            data = f.read().splitlines()

        vips = {}
        for line in data:
            if ":" in line:
                uid, exp = line.split(":")
                vips[int(uid)] = float(exp)

        return vips
    except:
        return {}

def save_vips(vips):
    with open(VIP_FILE, "w") as f:
        for uid, exp in vips.items():
            f.write(f"{uid}:{exp}\n")

vip_users = load_vips()

def is_vip(uid):
    if uid not in vip_users:
        return False

    # ❌ VIP expiré
    if vip_users[uid] < time.time():
        del vip_users[uid]
        save_vips(vip_users)
        return False

    return True

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
        if is_vip(user_id):
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
            "📌 L’admin choisit la durée\n\n"
            "⏳ Délai max : 24h"
        )

    # ✅ J'AI PAYÉ
    elif text == "✅ J'ai payé":
        if is_vip(user_id):
            await update.message.reply_text(
                "🎉 Vous êtes déjà abonné VIP\n"
                "👉 Cliquez sur 💎 Coupon VIP"
            )
            return

        await update.message.reply_text(
            "📩 Demande reçue\n"
            "⏳ Vérification en cours (max 12h)\n"
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
# 📸 PHOTO PAIEMENT
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

    await update.message.reply_text("📩 Envoyé à l’admin")

# =========================
# 👑 VIP 7 JOURS
# =========================

async def addvip7(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.from_user.id != ADMIN_ID:
        return

    uid = int(context.args[0])
    exp = time.time() + (7 * 24 * 60 * 60)

    vip_users[uid] = exp
    save_vips(vip_users)

    await context.bot.send_message(
        chat_id=uid,
        text=(
            "🎉 Félicitations 🎉\n\n"
            "VIP ACTIVÉ : 7 JOURS\n"
            "💎 Profitez de vos coupons\n\n"
            "👉 Cliquez sur 💎 Coupon VIP"
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
    exp = time.time() + (30 * 24 * 60 * 60)

    vip_users[uid] = exp
    save_vips(vip_users)

    await context.bot.send_message(
        chat_id=uid,
        text=(
            "🎉 Félicitations 🎉\n\n"
            "VIP ACTIVÉ : 30 JOURS\n"
            "💎 Profitez de vos coupons\n\n"
            "👉 Cliquez sur 💎 Coupon VIP"
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

    if uid in vip_users:
        del vip_users[uid]
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
            "👑 VIP LIST:\n" +
            "\n".join([f"{k}" for k in vip_users.keys()])
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

print("🤖 BOT VIP PRO EN LIGNE")
app.run_polling()
