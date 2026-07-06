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
# 💳 PAIEMENT TEMPORAIRE
# =========================

pending_payment = {}

# =========================
# 📱 CLAVIER PRINCIPAL
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
        "👋 Bienvenue sur COUPON VIP 💎\n\n"
        "Choisis une option ci-dessous 👇",
        reply_markup=keyboard()
    )

# =========================
# 💬 MESSAGE HANDLER (CORRIGÉ)
# =========================

async def handle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    text = update.message.text

    # 🎫 GRATUIT
    if text == "🎫 Coupon Gratuit":
        await update.message.reply_text(COUPON_FREE)
        return

    # 💎 VIP
    elif text == "💎 Coupon VIP":
        if user_id in vip_users:
            await update.message.reply_text(COUPON_VIP)
        else:
            await update.message.reply_text("❌ Accès VIP refusé")
        return

    # 💳 ABONNEMENT
    elif text == "💳 Abonnement":
        await update.message.reply_text(
            "💳 ABONNEMENT VIP\n\n"
            "🗓️ Semaine : 1 500 XOF\n"
            "📅 Mois : 2 500 XOF\n\n"
            "📌 Étapes :\n"
            "1️⃣ Envoie ton ID Telegram\n"
            "2️⃣ Envoie la capture de paiement\n"
            "3️⃣ Validation par l’admin\n\n"
            "⏳ Traitement max : 24h\n"
            "📞 Contact si retard : @HardingMichelle\n"
        )

        pending_payment[user_id] = {"step": "wait_id"}
        return

    # ✅ J'AI PAYÉ
    elif text == "✅ J'ai payé":
        await update.message.reply_text(
            "📩 Demande reçue\n\n"
            "Votre paiement est en cours de vérification.\n"
            "Une fois validé, votre accès VIP sera activé automatiquement.\n\n"
            "⏳ Délai maximum : 12 heures\n"
            "📞 Si aucun retour après 12h, contactez le support."
        )
        return

    # 🆔 ID
    elif text == "🆔 Mon ID":
        await update.message.reply_text(f"🆔 Ton ID Telegram : {user_id}")
        return

    # 📞 CONTACT
    elif text == "📞 Contact Admin":
        await update.message.reply_text(
            "📞 Admin : @HardingMichelle\n"
            "💰 +2250586692183"
        )
        return

    # =========================
    # 💳 FLOW PAIEMENT PROPRE
    # =========================

    if user_id not in pending_payment:
        return

    step = pending_payment[user_id]["step"]

    # 👉 Étape 1 : ID
    if step == "wait_id":

        if not text.isdigit():
            await update.message.reply_text("❌ Envoie uniquement ton ID Telegram (chiffres)")
            return

        uid = int(text)

        pending_payment[user_id]["uid"] = uid
        pending_payment[user_id]["step"] = "wait_photo"

        await update.message.reply_text("📸 Envoie maintenant la capture de paiement")
        return

# =========================
# 📸 PHOTO HANDLER
# =========================

async def photo_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id

    if user_id in pending_payment:
        uid = pending_payment[user_id].get("uid")

        if uid:
            user = update.message.from_user

            await context.bot.send_photo(
                chat_id=ADMIN_ID,
                photo=update.message.photo[-1].file_id,
                caption=(
                    "💰 NOUVEAU PAIEMENT\n\n"
                    f"👤 Nom: {user.first_name}\n"
                    f"🆔 User ID: {user_id}\n"
                    f"🧾 VIP ID: {uid}\n\n"
                    f"✔ /addvip {uid}\n"
                    f"❌ /removevip {uid}"
                )
            )

            await update.message.reply_text(
                "📩 Capture envoyée à l’admin pour validation"
            )

            del pending_payment[user_id]

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

        await update.message.reply_text(f"✅ VIP ajouté : {uid}")

    except:
        await update.message.reply_text("❌ erreur")

async def removevip(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.from_user.id != ADMIN_ID:
        return

    try:
        uid = int(context.args[0])
        vip_users.discard(uid)
        save_vips(vip_users)

        await context.bot.send_message(
            chat_id=uid,
            text=(
                "⚠️ Votre abonnement VIP est terminé.\n\n"
                "Merci pour votre confiance 💙"
            )
        )

        await update.message.reply_text(f"❌ VIP retiré : {uid}")

    except:
        await update.message.reply_text("❌ erreur")

async def listvip(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.from_user.id != ADMIN_ID:
        return

    if vip_users:
        await update.message.reply_text(
            "👑 LISTE VIP:\n" +
            "\n".join(str(x) for x in vip_users)
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
