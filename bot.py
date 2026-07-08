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

# 📁 VIP FILE
VIP_FILE = "vip.txt"

# 📁 FICHIER UTILISATEURS
USERS_FILE = "users.txt"

# =========================
# 🎫 COUPONS
# =========================

COUPON_FREE = """
🎫 COUPON GRATUIT

⚽ Match pas de coupon disponible pour le moment 
➡️ x
📊 Cote : x

👉 Les meilleures côtes sont dans les VIP 💎
"""

COUPON_VIP = """
💎 COUPON VIP

⚽ Match 1 : pas de coupon disponible pour le monde 
➡️ x
📊 Cote : x

⚽ Match 2 : x
➡️ x
📊 Cote : x

📊 Cote combinée : x
🔥 Probabilité : x
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
# 👥 USERS SYSTEM
# =========================

def load_users():
    try:
        with open(USERS_FILE, "r") as f:
            return set(map(int, f.read().split()))
    except:
        return set()

def save_users(users):
    with open(USERS_FILE, "w") as f:
        f.write(" ".join(map(str, users)))

users = load_users()

broadcast_mode = {}

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
# 👑 CLAVIER ADMIN COMPLET
# =========================

def admin_keyboard():
    return ReplyKeyboardMarkup([
        ["👥 Utilisateurs", "👑 Liste VIP"],
        ["📊 Statistiques", "💰 Paiements"],
        ["📢 Message Tous", "💎 Message VIP"],
        ["🎫 Coupon Gratuit", "💎 Coupon VIP"],
        ["🧪 Tester Bot", "⚙️ Paramètres"]
    ], resize_keyboard=True)

# =========================
# 🚀 START
# =========================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):

    user_id = update.message.from_user.id

    users.add(user_id)
    save_users(users)

    if user_id == ADMIN_ID:

        await update.message.reply_text(
            "👑 Bienvenue dans ton espace Administrateur\n\n"
            "Ici tu peux gérer et surveiller ton bot.",
            reply_markup=admin_keyboard()
        )

    else:

        await update.message.reply_text(
            "👋 Bienvenue sur COUPON VIP 💎\n"
            "Souscris à un abonnement pour accéder aux VIP 💰\n\n"
            "Choisis une option 👇",
            reply_markup=keyboard()
        )

# =========================
# 💬 HANDLER
# =========================

async def handle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    text = update.message.text

    # 📢 Diffusion admin

    if user_id == ADMIN_ID and user_id in broadcast_mode:

        mode = broadcast_mode[user_id]

        if mode == "all":
            for uid in users:
                try:
                    await context.bot.send_message(uid, text)
                except:
                    pass

        elif mode == "vip":
            for uid in vip_users:
                try:
                    await context.bot.send_message(uid, text)
                except:
                    pass

        del broadcast_mode[user_id]

        await update.message.reply_text("✅ Diffusion terminée.")
        return

    # 👑 MENU ADMIN

    if user_id == ADMIN_ID:

        if text == "👥 Utilisateurs":
            await update.message.reply_text(
                "👥 LISTE UTILISATEURS\n\n"
                + "\n".join(map(str, users))
            )
            return

        elif text == "👑 Liste VIP":
            await listvip(update, context)
            return

        elif text == "📊 Statistiques":
            await stats(update, context)
            return

        elif text == "💰 Paiements":
            await update.message.reply_text(
                "💰 Les paiements arrivent directement ici."
            )
            return

        elif text == "🧪 Tester Bot":
            await update.message.reply_text(
                "✅ Le bot fonctionne correctement."
            )
            return

        elif text == "⚙️ Paramètres":
            await update.message.reply_text(
                "⚙️ Paramètres disponibles prochainement."
            )
            return

        elif text == "📢 Message Tous":
            await broadcast(update, context
            )
            return

        elif text == "💎 Message VIP":
            await broadcastvip(update, context
            )
            return

    # 🎫 FREE
    if text == "🎫 Coupon Gratuit":
        await update.message.reply_text(COUPON_FREE)

    # 💎 VIP
    elif text == "💎 Coupon VIP":
        if user_id == ADMIN_ID or user_id in vip_users:
            await update.message.reply_text(COUPON_VIP)
        else:
            await update.message.reply_text("❌ Accès VIP refusé")

    # 💳 ABONNEMENT
    elif text == "💳 Abonnement":
        await update.message.reply_text(
            "💳 ABONNEMENT VIP\n\n"
            "🗓️ Semaine : 1 500 XOF (7 jours)\n"
            "📅 Mois : 2 500 XOF (30 jours)\n\n"
            "💰 Wave / Orange Money\n"
            f"📞 Numéro : {PAY_NUMBER}\n\n"
            "⚠️ Paiement non remboursable\n"
            "📌 Validation manuelle par admin\n\n"
            "📸 Étapes :\n"
            "1️⃣ ID Telegram\n"
            "2️⃣ Capture paiement\n"
            "3️⃣ Envoyé au contact admin pour validation"
        )

   # ✅ J'AI PAYÉ
    elif text == "✅ J'ai payé":
        if user_id in vip_users:
            await update.message.reply_text(
                "🎉 Vous êtes déjà VIP\n"
                "👉 Cliquez sur 💎 Coupon VIP"
            )
            return

        await update.message.reply_text(
            "📩 Demande reçue\n"
            "⏳ Vérification en cours\n"
            "📞 Si retard > 12h contactez support"
        )

        await context.bot.send_message(
            ADMIN_ID,
            f"💰 Nouvelle demande VIP\n\n"
            f"👤 Utilisateur : {user_id}\n\n"
            "🔎 Vérifier le paiement."
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
# 📸 PHOTO (PAIEMENT)
# =========================

async def photo_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id

    if user_id in vip_users:
        await update.message.reply_text(
            "🎉 Vous êtes déjà VIP.\n"
            "Votre abonnement est toujours actif."
        )
        return

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

    try:
        uid = int(context.args[0])
        vip_users.add(uid)
        save_vips(vip_users)

        await context.bot.send_message(
            chat_id=uid,
            text=(
                "🎉 Félicitations 🎉\n\n"
                "VIP activé : 7 jours\n"
                "💎 Profitez de vos coupons VIP"
            )
        )

        await update.message.reply_text("✅ VIP 7 jours ajouté")
    except:
        await update.message.reply_text("❌ erreur")

# =========================
# 👑 VIP 30 JOURS
# =========================

async def addvip30(update: Update, context: ContextTypes.DEFAULT_TYPE):
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
                "VIP activé : 30 jours\n"
                "💎 Profitez de vos coupons VIP"
            )
        )

        await update.message.reply_text("✅ VIP 30 jours ajouté")
    except:
        await update.message.reply_text("❌ erreur")

# =========================
# ❌ REMOVE VIP
# =========================

async def removevip(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.from_user.id != ADMIN_ID:
        return

    try:
        uid = int(context.args[0])
        vip_users.discard(uid)
        save_vips(vip_users)

        await context.bot.send_message(
            chat_id=uid,
            text="⚠️ VIP terminé. Merci 💙"
        )

        await update.message.reply_text("❌ VIP retiré")
    except:
        await update.message.reply_text("❌ erreur")

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
# 📢 BROADCAST
# =========================

async def broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.from_user.id != ADMIN_ID:
        return

    broadcast_mode[ADMIN_ID] = "all"

    await update.message.reply_text(
        "📢 Envoie maintenant le message à diffuser à tous les utilisateurs."
    )

# =========================
# 💎 BROADCAST VIP
# =========================

async def broadcastvip(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.from_user.id != ADMIN_ID:
        return

    broadcast_mode[ADMIN_ID] = "vip"

    await update.message.reply_text(
        "💎 Envoie maintenant le message réservé aux VIP."
    )

# =========================
# 📊 STATS
# =========================

async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.from_user.id != ADMIN_ID:
        return

    await update.message.reply_text(
        f"📊 STATISTIQUES\n\n"
        f"👥 Utilisateurs : {len(users)}\n"
        f"👑 VIP : {len(vip_users)}"
    )

# =========================
# 🚀 BOT START
# =========================

app = ApplicationBuilder().token(TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle))
app.add_handler(MessageHandler(filters.PHOTO, photo_handler))
app.add_handler(CommandHandler("stats", stats))
app.add_handler(CommandHandler("broadcast", broadcast))
app.add_handler(CommandHandler("broadcastvip", broadcastvip))

app.add_handler(CommandHandler("addvip7", addvip7))
app.add_handler(CommandHandler("addvip30", addvip30))
app.add_handler(CommandHandler("removevip", removevip))
app.add_handler(CommandHandler("listvip", listvip))

print("🤖 BOT VIP OK")
app.run_polling()
