import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
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

⚽ Avenir
➡️ x
📊 Cote : x
"""

COUPON_VIP = """
💎 COUPON VIP

⚽ Avenir
➡️ x
📊 Cote : x
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
# 💳 PAIEMENT EN ATTENTE
# =========================

pending_payment = {}

# =========================
# MENU
# =========================

def menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🎫 Coupon Gratuit", callback_data="free")],
        [InlineKeyboardButton("💎 Coupon VIP", callback_data="vip")],
        [InlineKeyboardButton("💳 Abonnement", callback_data="pay")],
        [InlineKeyboardButton("📞 Admin", callback_data="admin")]
    ])

# =========================
# START
# =========================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Bienvenue sur COUPON VIP 💎. Pour profiter des bonne côte, Prenez un Abonnement 💳.",
        reply_markup=menu()
    )

# =========================
# BOUTONS
# =========================

async def buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id
    data = query.data

    if data == "free":
        await query.message.reply_text(COUPON_FREE)

    elif data == "vip":
        if user_id in vip_users:
            await query.message.reply_text(COUPON_VIP)
        else:
            await query.message.reply_text("❌ VIP requis")

    elif data == "pay":
        pending_payment[user_id] = {"step": "wait_id"}

        await query.message.reply_text(
            "💳 ABONNEMENT VIP\n\n"
            "📌 Tarifs :\n"
            "🗓️ Semaine : 1 500 XOF\n"
            "📅 Mois : 2 500 XOF\n\n"
            "📌 Procédure :\n"
            "1️⃣ Envoie ton ID Telegram\n"
            "2️⃣ Envoie la capture de paiement\n"
            "3️⃣ Validation par l’admin\n\n"
            "⏳ Délai d’activation : maximum 24h\n"
            "⚠️ Si dépassement des 24h, contacte le support\n\n"
            "🔒 GARANTIE :\n"
            "✔ Activation après vérification\n"
            "✔ Paiement sécurisé\n"
            "✔ Aucun accès sans validation"
        )

    elif data == "admin":
        await query.message.reply_text(
            "📞 Admin : @HardingMichelle\n💰 +2250586692183"
        )

# =========================
# ID HANDLER
# =========================

async def handle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    text = update.message.text

    if user_id in pending_payment:
        step = pending_payment[user_id]["step"]

        if step == "wait_id":
            try:
                uid = int(text)

                pending_payment[user_id]["uid"] = uid
                pending_payment[user_id]["step"] = "wait_photo"

                await update.message.reply_text(
                    "📸 Maintenant envoie la capture de paiement"
                )
            except:
                await update.message.reply_text("❌ ID invalide")
            return

# =========================
# PHOTO HANDLER
# =========================

async def photo_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id

    if user_id in pending_payment and update.message.photo:

        uid = pending_payment[user_id]["uid"]

        await context.bot.send_message(
            chat_id=ADMIN_ID,
            text=f"""
💰 NOUVEAU PAIEMENT

👤 USER: {user_id}
🆔 ID VIP: {uid}

✔ /valider {uid}
❌ /refuser {uid}
"""
        )

        await update.message.reply_text(
            "📩 Paiement envoyé à l’admin pour validation"
        )

# =========================
# ADMIN COMMANDES
# =========================

async def valider(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.from_user.id != ADMIN_ID:
        return

    try:
        uid = int(context.args[0])
        vip_users.add(uid)
        save_vips(vip_users)

        await update.message.reply_text(f"✅ VIP activé : {uid}")
    except:
        await update.message.reply_text("❌ erreur")


async def refuser(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.from_user.id != ADMIN_ID:
        return

    try:
        uid = int(context.args[0])
        await update.message.reply_text(f"❌ Refusé : {uid}")
    except:
        await update.message.reply_text("❌ erreur")

# =========================
# BOT START
# =========================

app = ApplicationBuilder().token(TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(CallbackQueryHandler(buttons))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle))
app.add_handler(MessageHandler(filters.PHOTO, photo_handler))
app.add_handler(CommandHandler("valider", valider))
app.add_handler(CommandHandler("refuser", refuser))

print("🤖 BOT VIP EN LIGNE")
app.run_polling()
