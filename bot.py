import asyncio
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters

TOKEN = os.getenv("8641194944:AAEFGeeHS0KVZ2oUuYzWojj88ENl6a5uqtY")

# 👑 LISTE VIP
vip_users = []

# 🎫 COUPON GRATUIT
COUPON_FREE = """
🎫 COUPON GRATUIT

⚽ Match Brazil vs Norway
➡️ +0.5 buts Norway
📊 Cote : 1.41

🎯 Bonne chance 🍀
"""

# 💎 COUPON VIP
COUPON_VIP = """
💎 COUPON VIP

⚽ Match 1
➡️ Victoire équipe A
📊 Cote : 1.85

⚽ Match 2
➡️ +2.5 buts
📊 Cote : 1.95

🎯 Cote totale : 3.61
"""

# 📌 START
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        ["🎫 Coupon Gratuit"],
        ["💎 Coupon VIP"],
        ["💳 S'abonner (2500 FCFA)"],
        ["🆔 Mon ID"],
        ["📊 Résultats"],
        ["📞 Contact Admin"],
        ["ℹ️ À propos"]
    ]

    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

    await update.message.reply_text(
        "👋 Bienvenue sur *COUPON VIP*\n\nChoisis une option 👇",
        reply_markup=reply_markup,
        parse_mode="Markdown"
    )

# 📌 HANDLE MESSAGES
async def handle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    text = update.message.text

    # 🎫 Gratuit
    if text == "🎫 Coupon Gratuit":
        await update.message.reply_text(COUPON_FREE)

    # 💎 VIP
    elif text == "💎 Coupon VIP":
        if user_id in vip_users:
            await update.message.reply_text(COUPON_VIP)
        else:
            await update.message.reply_text(
                "❌ Accès VIP refusé\n\n💳 Abonne-toi pour accéder aux coupons VIP."
            )

    # 💳 Paiement (REMPLACÉ)
    elif text == "💳 S'abonner (2500 FCFA)":
        await update.message.reply_text(
            "💎 *ABONNEMENT VIP*\n\n"
            "💰 Prix : 2500 FCFA\n\n"
            "📱 Paiement Mobile Money : +2250586692183\n\n"
            "⚠️ Après paiement, envoie ton ID + capture à l’admin @HardingMichelle.",
            parse_mode="Markdown"
        )

    # 🆔 ID
    elif text == "🆔 Mon ID":
        await update.message.reply_text(f"🆔 Ton ID Telegram est : {user_id}")

    # 📊 Résultats
    elif text == "📊 Résultats":
        await update.message.reply_text(
            "📊 Résultats récents\n\n"
            "✅ Victoires : 12\n"
            "❌ Défaites : 2\n"
            "🎯 Taux : 85%"
        )

    # 📞 Contact
    elif text == "📞 Contact Admin":
        await update.message.reply_text(
            "📞 Admin\n\n"
            "👤 @HardingMichelle\n"
            "📱 WhatsApp / Mobile Money : +2250586692183"
        )

    # ℹ️ À propos
    elif text == "ℹ️ À propos":
        await update.message.reply_text(
            "ℹ️ COUPON VIP\n\n"
            "✔ Pronostics sportifs\n"
            "✔ Football / Basket / Tennis\n"
            "✔ Cotes 2.00 - 3.00\n\n"
            "⚠️ Jouez responsablement"
        )

# 🚀 LANCEMENT BOT
app = ApplicationBuilder().token(TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle))

print("Bot en ligne...")
app.run_polling(drop_pending_updates=True)
