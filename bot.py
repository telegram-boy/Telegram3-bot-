import os
import sqlite3
from datetime import datetime, timedelta

from telegram import (
    Update,
    ReplyKeyboardMarkup,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)

# =========================
# 🔐 CONFIG
# =========================

TOKEN = os.getenv("TOKEN")
ADMIN_ID = 5447711661
DB_FILE = "bot.db"

DATE_FMT = "%Y-%m-%d %H:%M"

DEFAULT_COUPON_FREE = """🎫 COUPON GRATUIT

⚽ Match : pas de coupon disponible pour le moment
➡️ x
📊 Cote : x

👉 Les meilleures cotes sont dans les VIP 💎"""

DEFAULT_COUPON_VIP = """💎 COUPON VIP

⚽ Match 1 : x
➡️ x
📊 Cote : x

⚽ Match 2 : x
➡️ x
📊 Cote : x

📊 Cote combinée : x
🔥 Probabilité : x
🍀 Good luck"""

DEFAULT_PAY_NUMBER = "+2250789247884"

# =========================
# 🗄️ BASE DE DONNÉES
# =========================

conn = sqlite3.connect(DB_FILE, check_same_thread=False)
cur = conn.cursor()

cur.executescript("""
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY,
    joined_at TEXT,
    last_active TEXT
);

CREATE TABLE IF NOT EXISTS vips (
    id INTEGER PRIMARY KEY,
    added_at TEXT,
    expires_at TEXT
);

CREATE TABLE IF NOT EXISTS payments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    date TEXT,
    status TEXT DEFAULT 'pending'
);

CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT
);

CREATE TABLE IF NOT EXISTS broadcasts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date TEXT,
    type TEXT,
    sent INTEGER,
    failed INTEGER
);
""")
conn.commit()


def get_setting(key, default=None):
    cur.execute("SELECT value FROM settings WHERE key = ?", (key,))
    row = cur.fetchone()
    return row[0] if row else default


def set_setting(key, value):
    cur.execute(
        "INSERT INTO settings (key, value) VALUES (?, ?) "
        "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
        (key, value),
    )
    conn.commit()


# Initialise les réglages par défaut au premier lancement
if get_setting("coupon_free") is None:
    set_setting("coupon_free", DEFAULT_COUPON_FREE)
if get_setting("coupon_vip") is None:
    set_setting("coupon_vip", DEFAULT_COUPON_VIP)
if get_setting("pay_number") is None:
    set_setting("pay_number", DEFAULT_PAY_NUMBER)


# ---- Utilisateurs ----

def add_user(uid):
    now = datetime.now().strftime(DATE_FMT)
    cur.execute(
        "INSERT INTO users (id, joined_at, last_active) VALUES (?, ?, ?) "
        "ON CONFLICT(id) DO UPDATE SET last_active = excluded.last_active",
        (uid, now, now),
    )
    conn.commit()


def touch_user(uid):
    now = datetime.now().strftime(DATE_FMT)
    cur.execute("UPDATE users SET last_active = ? WHERE id = ?", (now, uid))
    conn.commit()


def all_users():
    cur.execute("SELECT id, joined_at, last_active FROM users ORDER BY joined_at DESC")
    return cur.fetchall()


def count_users():
    cur.execute("SELECT COUNT(*) FROM users")
    return cur.fetchone()[0]


# ---- VIP ----

def is_vip(uid):
    cur.execute("SELECT expires_at FROM vips WHERE id = ?", (uid,))
    row = cur.fetchone()
    if not row:
        return False
    expires_at = datetime.strptime(row[0], DATE_FMT)
    if expires_at < datetime.now():
        cur.execute("DELETE FROM vips WHERE id = ?", (uid,))
        conn.commit()
        return False
    return True


def add_vip(uid, days):
    now = datetime.now()
    # Si déjà VIP, on prolonge à partir de la date d'expiration actuelle
    cur.execute("SELECT expires_at FROM vips WHERE id = ?", (uid,))
    row = cur.fetchone()
    base = now
    if row:
        current_exp = datetime.strptime(row[0], DATE_FMT)
        if current_exp > now:
            base = current_exp
    expires_at = base + timedelta(days=days)
    cur.execute(
        "INSERT INTO vips (id, added_at, expires_at) VALUES (?, ?, ?) "
        "ON CONFLICT(id) DO UPDATE SET expires_at = excluded.expires_at",
        (uid, now.strftime(DATE_FMT), expires_at.strftime(DATE_FMT)),
    )
    conn.commit()
    return expires_at


def remove_vip(uid):
    cur.execute("DELETE FROM vips WHERE id = ?", (uid,))
    conn.commit()


def list_vips():
    cur.execute("SELECT id, expires_at FROM vips ORDER BY expires_at ASC")
    return cur.fetchall()


def count_vips():
    cur.execute("SELECT COUNT(*) FROM vips")
    return cur.fetchone()[0]


# ---- Paiements ----

def add_payment(uid):
    now = datetime.now().strftime(DATE_FMT)
    cur.execute(
        "INSERT INTO payments (user_id, date, status) VALUES (?, ?, 'pending')",
        (uid, now),
    )
    conn.commit()
    return cur.lastrowid


def update_payment_status(pid, status):
    cur.execute("UPDATE payments SET status = ? WHERE id = ?", (status, pid))
    conn.commit()


def get_payment(pid):
    cur.execute("SELECT id, user_id, date, status FROM payments WHERE id = ?", (pid,))
    return cur.fetchone()


def get_pending_payments():
    cur.execute(
        "SELECT id, user_id, date FROM payments WHERE status = 'pending' ORDER BY date DESC"
    )
    return cur.fetchall()


def get_recent_payments(limit=15):
    cur.execute(
        "SELECT id, user_id, date, status FROM payments ORDER BY date DESC LIMIT ?",
        (limit,),
    )
    return cur.fetchall()


def count_payments():
    cur.execute("SELECT COUNT(*) FROM payments")
    return cur.fetchone()[0]


def count_pending_payments():
    cur.execute("SELECT COUNT(*) FROM payments WHERE status = 'pending'")
    return cur.fetchone()[0]


# ---- Diffusions ----

def log_broadcast(btype, sent, failed):
    now = datetime.now().strftime(DATE_FMT)
    cur.execute(
        "INSERT INTO broadcasts (date, type, sent, failed) VALUES (?, ?, ?, ?)",
        (now, btype, sent, failed),
    )
    conn.commit()


def count_broadcasts():
    cur.execute("SELECT COUNT(*) FROM broadcasts")
    return cur.fetchone()[0]


# =========================
# 🧠 ÉTATS DE CONVERSATION (admin)
# =========================

# admin_state[admin_id] = {"action": "..."}
admin_state = {}

# admin_pending_broadcast[admin_id] = {"type": "all"/"vip", "text": "..."}
admin_pending_broadcast = {}


def clear_state(uid):
    admin_state.pop(uid, None)


# =========================
# 📱 CLAVIERS
# =========================

def keyboard():
    return ReplyKeyboardMarkup([
        ["🎫 Coupon Gratuit"],
        ["💎 Coupon VIP"],
        ["🔥 Pourquoi devenir VIP ?"],
        ["💳 Abonnement"],
        ["✅ J'ai payé"],
        ["🆔 Mon ID"],
        ["📞 Contact Admin"],
    ], resize_keyboard=True)


def admin_keyboard():
    return ReplyKeyboardMarkup([
        ["📊 Statistiques", "👥 Utilisateurs"],
        ["👑 Liste VIP", "💰 Paiements"],
        ["🎫 Modifier Coupon Gratuit", "💎 Modifier Coupon VIP"],
        ["➕ Ajouter VIP 7 jours", "➕ Ajouter VIP 30 jours"],
        ["❌ Retirer VIP", "📱 Modifier Numéro"],
        ["📢 Message Tous", "💎 Message VIP"],
        ["🔄 Actualiser"],
    ], resize_keyboard=True)


ADMIN_BUTTONS = {
    "📊 Statistiques", "👥 Utilisateurs", "👑 Liste VIP", "💰 Paiements",
    "🎫 Modifier Coupon Gratuit", "💎 Modifier Coupon VIP",
    "➕ Ajouter VIP 7 jours", "➕ Ajouter VIP 30 jours", "❌ Retirer VIP",
    "📱 Modifier Numéro", "📢 Message Tous", "💎 Message VIP", "🔄 Actualiser",
}

USER_BUTTONS = {
    "🎫 Coupon Gratuit", "💎 Coupon VIP", "🔥 Pourquoi devenir VIP ?",
    "💳 Abonnement", "✅ J'ai payé", "🆔 Mon ID", "📞 Contact Admin",
}


# =========================
# 🚀 START
# =========================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    add_user(user_id)
    clear_state(user_id)

    if user_id == ADMIN_ID:
        await update.message.reply_text(
            "👑 Bienvenue dans ton espace Administrateur\n\n"
            "Toutes les actions se font via les boutons ci-dessous.",
            reply_markup=admin_keyboard(),
        )
    else:
        await update.message.reply_text(
            "👋 Bienvenue sur COUPON VIP 💎\n"
            "Souscris à un abonnement pour accéder aux VIP 💰\n\n"
            "Choisis une option 👇",
            reply_markup=keyboard(),
        )


# =========================
# 💬 GESTION DES ÉTATS ADMIN (saisie après un bouton)
# =========================

async def process_admin_state(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str):
    admin_uid = update.message.from_user.id
    state = admin_state.get(admin_uid)
    if not state:
        return False  # rien à traiter

    action = state["action"]

    if action == "coupon_free":
        set_setting("coupon_free", text)
        await update.message.reply_text("✅ Coupon gratuit mis à jour avec succès.", reply_markup=admin_keyboard())

    elif action == "coupon_vip":
        set_setting("coupon_vip", text)
        await update.message.reply_text("✅ Coupon VIP mis à jour avec succès.", reply_markup=admin_keyboard())

    elif action == "pay_number":
        set_setting("pay_number", text.strip())
        await update.message.reply_text("✅ Numéro de paiement mis à jour.", reply_markup=admin_keyboard())

    elif action in ("vip7", "vip30", "vip_remove"):
        try:
            uid = int(text.strip())
        except ValueError:
            await update.message.reply_text("❌ ID invalide. Envoie uniquement l'ID Telegram (nombre).")
            return True  # on reste dans l'état pour réessayer

        if action == "vip7":
            expires = add_vip(uid, 7)
            await update.message.reply_text(
                f"✅ VIP 7 jours ajouté pour {uid} (expire le {expires.strftime(DATE_FMT)})",
                reply_markup=admin_keyboard(),
            )
            try:
                await context.bot.send_message(
                    uid,
                    "🎉 Félicitations 🎉\n\nVIP activé : 7 jours\n💎 Profite de tes coupons VIP",
                )
            except Exception:
                pass

        elif action == "vip30":
            expires = add_vip(uid, 30)
            await update.message.reply_text(
                f"✅ VIP 30 jours ajouté pour {uid} (expire le {expires.strftime(DATE_FMT)})",
                reply_markup=admin_keyboard(),
            )
            try:
                await context.bot.send_message(
                    uid,
                    "🎉 Félicitations 🎉\n\nVIP activé : 30 jours\n💎 Profite de tes coupons VIP",
                )
            except Exception:
                pass

        elif action == "vip_remove":
            remove_vip(uid)
            await update.message.reply_text(f"❌ VIP retiré pour {uid}", reply_markup=admin_keyboard())
            try:
                await context.bot.send_message(uid, "⚠️ Ton accès VIP a été retiré. Merci 💙")
            except Exception:
                pass

    clear_state(admin_uid)
    return True


# =========================
# 📢 DIFFUSION (avec confirmation)
# =========================

async def handle_broadcast_text(update: Update, context: ContextTypes.DEFAULT_TYPE, btype: str, text: str):
    admin_pending_broadcast[ADMIN_ID] = {"type": btype, "text": text}
    label = "TOUS LES UTILISATEURS" if btype == "all" else "VIP UNIQUEMENT"
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Envoyer", callback_data="bc_send"),
         InlineKeyboardButton("❌ Annuler", callback_data="bc_cancel")]
    ])
    await update.message.reply_text(
        f"👀 APERÇU — diffusion à {label}\n\n{text}\n\nConfirmes-tu l'envoi ?",
        reply_markup=kb,
    )


# =========================
# 💬 HANDLER PRINCIPAL (texte)
# =========================

async def handle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    text = update.message.text
    touch_user(user_id)

    # Si l'admin est en train de saisir un message à diffuser
    if user_id == ADMIN_ID and user_id in admin_pending_broadcast and text not in ADMIN_BUTTONS:
        # ne devrait pas arriver normalement (l'étape de saisie initiale déclenche déjà l'aperçu)
        pass

    # Si le texte correspond à un bouton connu, on annule tout état en cours
    if text in ADMIN_BUTTONS or text in USER_BUTTONS:
        clear_state(user_id)

    # Si l'admin a un état en attente (saisie suite à un bouton "Modifier ...")
    elif user_id == ADMIN_ID and user_id in admin_state:
        handled = await process_admin_state(update, context, text)
        if handled:
            return

    # =========================
    # 👑 MENU ADMIN
    # =========================
    if user_id == ADMIN_ID:

        if text == "📊 Statistiques":
            await stats(update, context)
            return

        elif text == "👥 Utilisateurs":
            users = all_users()
            if not users:
                await update.message.reply_text("Aucun utilisateur pour le moment.")
                return
            lines = [f"👥 UTILISATEURS ({len(users)})\n"]
            for uid, joined, last in users[:30]:
                vip_tag = "💎 VIP" if is_vip(uid) else "—"
                lines.append(f"🆔 {uid} | inscrit: {joined} | actif: {last} | {vip_tag}")
            if len(users) > 30:
                lines.append(f"\n... et {len(users) - 30} autres")
            await update.message.reply_text("\n".join(lines))
            return

        elif text == "👑 Liste VIP":
            await listvip(update, context)
            return

        elif text == "💰 Paiements":
            await show_payments(update, context)
            return

        elif text == "🎫 Modifier Coupon Gratuit":
            admin_state[user_id] = {"action": "coupon_free"}
            await update.message.reply_text(
                "✏️ Envoie le nouveau texte du COUPON GRATUIT :"
            )
            return

        elif text == "💎 Modifier Coupon VIP":
            admin_state[user_id] = {"action": "coupon_vip"}
            await update.message.reply_text(
                "✏️ Envoie le nouveau texte du COUPON VIP :"
            )
            return

        elif text == "➕ Ajouter VIP 7 jours":
            admin_state[user_id] = {"action": "vip7"}
            await update.message.reply_text("🆔 Envoie l'ID Telegram de l'utilisateur à passer VIP 7 jours :")
            return

        elif text == "➕ Ajouter VIP 30 jours":
            admin_state[user_id] = {"action": "vip30"}
            await update.message.reply_text("🆔 Envoie l'ID Telegram de l'utilisateur à passer VIP 30 jours :")
            return

        elif text == "❌ Retirer VIP":
            admin_state[user_id] = {"action": "vip_remove"}
            await update.message.reply_text("🆔 Envoie l'ID Telegram de l'utilisateur à retirer des VIP :")
            return

        elif text == "📱 Modifier Numéro":
            admin_state[user_id] = {"action": "pay_number"}
            current = get_setting("pay_number")
            await update.message.reply_text(
                f"📱 Numéro actuel : {current}\n\nEnvoie le nouveau numéro Wave / Orange Money :"
            )
            return

        elif text == "📢 Message Tous":
            admin_state[user_id] = {"action": "broadcast_all"}
            await update.message.reply_text("📢 Envoie le message à diffuser à TOUS les utilisateurs.")
            return

        elif text == "💎 Message VIP":
            admin_state[user_id] = {"action": "broadcast_vip"}
            await update.message.reply_text("💎 Envoie le message réservé aux VIP.")
            return

        elif text == "🔄 Actualiser":
            await update.message.reply_text("🔄 Tableau de bord actualisé.", reply_markup=admin_keyboard())
            return

        # Réception du texte de diffusion (après clic sur "Message Tous" / "Message VIP")
        elif user_id in admin_state and admin_state[user_id]["action"] in ("broadcast_all", "broadcast_vip"):
            btype = "all" if admin_state[user_id]["action"] == "broadcast_all" else "vip"
            clear_state(user_id)
            await handle_broadcast_text(update, context, btype, text)
            return

    # =========================
    # 👤 MENU UTILISATEUR
    # =========================

    if text == "🎫 Coupon Gratuit":
        await update.message.reply_text(get_setting("coupon_free"))

    elif text == "💎 Coupon VIP":
        if user_id == ADMIN_ID or is_vip(user_id):
            await update.message.reply_text(get_setting("coupon_vip"))
        else:
            await update.message.reply_text("❌ Accès VIP refusé")

    elif text == "🔥 Pourquoi devenir VIP ?":
        pay_number = get_setting("pay_number")
        await update.message.reply_text(
            "🔥 POURQUOI DEVENIR VIP ? 💎\n\n"
            "✅ Les meilleures cotes, sélectionnées avec soin\n"
            "✅ Des coupons combinés à forte probabilité\n"
            "✅ Des pronostics premium, analysés en détail\n"
            "✅ Un accès prioritaire avant tout le monde\n\n"
            "💳 TARIFS\n"
            "🗓️ Semaine : 1 500 XOF (7 jours)\n"
            "📅 Mois : 2 500 XOF (30 jours)\n\n"
            f"💰 Paiement Wave / Orange Money : {pay_number}\n\n"
            "👉 Clique sur 💳 Abonnement pour souscrire dès maintenant !"
        )

    elif text == "💳 Abonnement":
        pay_number = get_setting("pay_number")
        await update.message.reply_text(
            "💳 ABONNEMENT VIP\n\n"
            "🗓️ Semaine : 1 500 XOF (7 jours)\n"
            "📅 Mois : 2 500 XOF (30 jours)\n\n"
            "💰 Wave / Orange Money\n"
            f"📞 Numéro : {pay_number}\n\n"
            "⚠️ Paiement non remboursable\n"
            "📌 Validation manuelle par admin\n\n"
            "📸 Étapes :\n"
            "1️⃣ ID Telegram\n"
            "2️⃣ Capture paiement\n"
            "3️⃣ Envoyé au contact admin pour validation"
        )

    elif text == "✅ J'ai payé":
        if is_vip(user_id):
            await update.message.reply_text("🎉 Tu es déjà VIP\n👉 Clique sur 💎 Coupon VIP")
            return

        pid = add_payment(user_id)

        await update.message.reply_text(
            "📩 Demande reçue\n⏳ Vérification en cours\n📞 Si retard > 12h contacte le support"
        )

        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ VIP 7j", callback_data=f"pv7:{pid}"),
             InlineKeyboardButton("✅ VIP 30j", callback_data=f"pv30:{pid}"),
             InlineKeyboardButton("❌ Refuser", callback_data=f"pvref:{pid}")]
        ])
        await context.bot.send_message(
            ADMIN_ID,
            f"💰 Nouvelle demande VIP (#{pid})\n\n👤 Utilisateur : {user_id}\n\n🔎 Vérifie le paiement puis choisis une action.",
            reply_markup=kb,
        )

    elif text == "🆔 Mon ID":
        await update.message.reply_text(f"🆔 Ton ID : {user_id}")

    elif text == "📞 Contact Admin":
        pay_number = get_setting("pay_number")
        await update.message.reply_text(f"📞 Admin : @HardingMichelle\n💰 {pay_number}")


# =========================
# 📸 PHOTO (PAIEMENT)
# =========================

async def photo_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    touch_user(user_id)

    if is_vip(user_id):
        await update.message.reply_text("🎉 Tu es déjà VIP.\nTon abonnement est toujours actif.")
        return

    pid = add_payment(user_id)

    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ VIP 7j", callback_data=f"pv7:{pid}"),
         InlineKeyboardButton("✅ VIP 30j", callback_data=f"pv30:{pid}"),
         InlineKeyboardButton("❌ Refuser", callback_data=f"pvref:{pid}")]
    ])

    await context.bot.send_photo(
        chat_id=ADMIN_ID,
        photo=update.message.photo[-1].file_id,
        caption=f"💰 NOUVEAU PAIEMENT (#{pid})\n\n👤 USER ID : {user_id}\n\n🔎 Vérifie puis choisis une action.",
        reply_markup=kb,
    )

    await update.message.reply_text("📩 Capture envoyée à l'admin")


# =========================
# 🔘 CALLBACKS (boutons inline)
# =========================

async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.from_user.id != ADMIN_ID:
        return

    data = query.data

    # ---- Paiements ----
    if data.startswith("pv7:") or data.startswith("pv30:") or data.startswith("pvref:"):
        action, pid_str = data.split(":")
        pid = int(pid_str)
        payment = get_payment(pid)

        if not payment:
            await query.edit_message_text("⚠️ Paiement introuvable (déjà traité ?).")
            return

        _, uid, date, status = payment

        if status != "pending":
            await query.edit_message_caption(caption=f"⚠️ Ce paiement a déjà été traité ({status}).") if query.message.photo else \
                await query.edit_message_text(f"⚠️ Ce paiement a déjà été traité ({status}).")
            return

        if action == "pv7":
            expires = add_vip(uid, 7)
            update_payment_status(pid, "validé")
            result_text = f"✅ Paiement #{pid} validé — VIP 7 jours pour {uid} (expire {expires.strftime(DATE_FMT)})"
            try:
                await context.bot.send_message(uid, "🎉 Félicitations 🎉\n\nVIP activé : 7 jours\n💎 Profite de tes coupons VIP")
            except Exception:
                pass

        elif action == "pv30":
            expires = add_vip(uid, 30)
            update_payment_status(pid, "validé")
            result_text = f"✅ Paiement #{pid} validé — VIP 30 jours pour {uid} (expire {expires.strftime(DATE_FMT)})"
            try:
                await context.bot.send_message(uid, "🎉 Félicitations 🎉\n\nVIP activé : 30 jours\n💎 Profite de tes coupons VIP")
            except Exception:
                pass

        else:  # pvref
            update_payment_status(pid, "refusé")
            result_text = f"❌ Paiement #{pid} refusé pour {uid}"
            try:
                await context.bot.send_message(uid, "❌ Ton paiement n'a pas pu être validé. Contacte l'admin pour plus d'infos.")
            except Exception:
                pass

        if query.message.photo:
            await query.edit_message_caption(caption=result_text)
        else:
            await query.edit_message_text(result_text)
        return

    # ---- Diffusion ----
    if data == "bc_cancel":
        admin_pending_broadcast.pop(ADMIN_ID, None)
        await query.edit_message_text("❌ Diffusion annulée.")
        return

    if data == "bc_send":
        pending = admin_pending_broadcast.pop(ADMIN_ID, None)
        if not pending:
            await query.edit_message_text("⚠️ Rien à envoyer.")
            return

        btype = pending["type"]
        msg_text = pending["text"]

        if btype == "all":
            targets = [u[0] for u in all_users()]
        else:
            targets = [v[0] for v in list_vips()]

        sent, failed = 0, 0
        for uid in targets:
            try:
                await context.bot.send_message(uid, msg_text)
                sent += 1
            except Exception:
                failed += 1

        log_broadcast(btype, sent, failed)
        label = "TOUS" if btype == "all" else "VIP"
        await query.edit_message_text(
            f"✅ Diffusion {label} terminée.\n\n📤 Envoyés : {sent}\n⚠️ Échecs : {failed}"
        )
        return


# =========================
# 👑 FONCTIONS ADMIN (affichage)
# =========================

async def listvip(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.from_user.id != ADMIN_ID:
        return
    vips = list_vips()
    if vips:
        lines = ["👑 LISTE VIP\n"]
        for uid, expires_at in vips:
            lines.append(f"🆔 {uid} — expire le {expires_at}")
        await update.message.reply_text("\n".join(lines))
    else:
        await update.message.reply_text("Aucun VIP pour le moment.")


async def show_payments(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.from_user.id != ADMIN_ID:
        return

    pending = get_pending_payments()
    recent = get_recent_payments(15)

    lines = [f"💰 PAIEMENTS\n\n⏳ En attente : {len(pending)}\n"]

    if pending:
        lines.append("— EN ATTENTE —")
        for pid, uid, date in pending:
            lines.append(f"#{pid} | 🆔 {uid} | {date} | 🟡 En attente")

    lines.append("\n— HISTORIQUE RÉCENT —")
    status_icon = {"validé": "🟢", "refusé": "🔴", "pending": "🟡"}
    for pid, uid, date, status in recent:
        icon = status_icon.get(status, "⚪")
        lines.append(f"#{pid} | 🆔 {uid} | {date} | {icon} {status}")

    await update.message.reply_text("\n".join(lines))

    if pending:
        await update.message.reply_text(
            "👉 Pour valider/refuser un paiement en attente, utilise les boutons envoyés "
            "au moment de la demande (message ✅/❌ ci-dessus dans le fil de discussion)."
        )


async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.from_user.id != ADMIN_ID:
        return

    await update.message.reply_text(
        "📊 STATISTIQUES\n\n"
        f"👥 Utilisateurs : {count_users()}\n"
        f"👑 VIP actifs : {count_vips()}\n"
        f"💰 Paiements (total) : {count_payments()}\n"
        f"⏳ Paiements en attente : {count_pending_payments()}\n"
        f"📢 Diffusions effectuées : {count_broadcasts()}"
    )


# =========================
# 🚀 LANCEMENT DU BOT
# =========================

app = ApplicationBuilder().token(TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("stats", stats))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle))
app.add_handler(MessageHandler(filters.PHOTO, photo_handler))
app.add_handler(CallbackQueryHandler(callback_handler))

print("🤖 BOT VIP OK (SQLite + panneau admin)")
app.run_polling()
