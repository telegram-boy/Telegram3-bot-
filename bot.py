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

CREATE TABLE IF NOT EXISTS ambassadors (
    user_id INTEGER PRIMARY KEY,
    code TEXT UNIQUE,
    points INTEGER DEFAULT 0,
    commission INTEGER DEFAULT 0,
    blocked INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS referrals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    parrain INTEGER,
    filleul INTEGER UNIQUE,
    niveau INTEGER,
    date TEXT
);

CREATE TABLE IF NOT EXISTS commissions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    utilisateur INTEGER,
    montant INTEGER,
    raison TEXT,
    date TEXT
);

CREATE TABLE IF NOT EXISTS points_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    utilisateur INTEGER,
    points INTEGER,
    raison TEXT,
    date TEXT
);

CREATE TABLE IF NOT EXISTS withdrawal_requests (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    utilisateur INTEGER,
    montant INTEGER,
    statut TEXT DEFAULT 'en_attente',
    date TEXT
);

CREATE TABLE IF NOT EXISTS ambassador_sales (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    buyer INTEGER,
    parrain1 INTEGER,
    parrain2 INTEGER,
    tier INTEGER,
    date TEXT
);
""")
conn.commit()


def add_column_if_missing(table, column, coltype):
    cur.execute(f"PRAGMA table_info({table})")
    cols = [r[1] for r in cur.fetchall()]
    if column not in cols:
        cur.execute(f"ALTER TABLE {table} ADD COLUMN {column} {coltype}")
        conn.commit()


add_column_if_missing("withdrawal_requests", "wave_number", "TEXT")
add_column_if_missing("withdrawal_requests", "paid_at", "TEXT")


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


def get_int_setting(key, default):
    val = get_setting(key)
    try:
        return int(val) if val is not None else default
    except (ValueError, TypeError):
        return default


# Initialise les réglages par défaut au premier lancement
if get_setting("coupon_free") is None:
    set_setting("coupon_free", DEFAULT_COUPON_FREE)
if get_setting("coupon_vip") is None:
    set_setting("coupon_vip", DEFAULT_COUPON_VIP)
if get_setting("pay_number") is None:
    set_setting("pay_number", DEFAULT_PAY_NUMBER)

# Paramètres ambassadeur par défaut (modifiables ensuite depuis Telegram, sans toucher au code)
AMBASSADOR_DEFAULTS = {
    "amb_signup_points": 10,
    "amb_l1_vip7_points": 100,
    "amb_l1_vip7_commission": 150,
    "amb_l1_vip30_points": 250,
    "amb_l1_vip30_commission": 300,
    "amb_l2_vip7_points": 20,
    "amb_l2_vip30_points": 50,
    "amb_personal_vip7_points": 20,
    "amb_personal_vip30_points": 45,
    "amb_redeem_vip7_points": 1000,
    "amb_redeem_vip30_points": 4000,
    "amb_min_withdrawal": 500,
}
for _k, _v in AMBASSADOR_DEFAULTS.items():
    if get_setting(_k) is None:
        set_setting(_k, str(_v))


def amb_setting(key):
    """Raccourci pour lire un paramètre ambassadeur (entier) avec sa valeur par défaut."""
    return get_int_setting(key, AMBASSADOR_DEFAULTS[key])


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
# 🌟 CLUB AMBASSADEUR
# =========================

# Les récompenses (points, commissions, seuils) sont désormais stockées dans la table
# settings et modifiables depuis Telegram via "⚙️ Param. Ambassadeur" (voir amb_setting()).


def ensure_ambassador(uid):
    cur.execute("SELECT user_id FROM ambassadors WHERE user_id = ?", (uid,))
    if cur.fetchone():
        return
    code = f"CV{uid}"
    cur.execute(
        "INSERT INTO ambassadors (user_id, code, points, commission, blocked) VALUES (?, ?, 0, 0, 0)",
        (uid, code),
    )
    conn.commit()


def get_ambassador(uid):
    cur.execute(
        "SELECT user_id, code, points, commission, blocked FROM ambassadors WHERE user_id = ?",
        (uid,),
    )
    return cur.fetchone()


def is_blocked(uid):
    amb = get_ambassador(uid)
    return bool(amb and amb[4])


def add_points(uid, points, raison):
    cur.execute("UPDATE ambassadors SET points = points + ? WHERE user_id = ?", (points, uid))
    now = datetime.now().strftime(DATE_FMT)
    cur.execute(
        "INSERT INTO points_history (utilisateur, points, raison, date) VALUES (?, ?, ?, ?)",
        (uid, points, raison, now),
    )
    conn.commit()


def add_commission(uid, montant, raison):
    cur.execute("UPDATE ambassadors SET commission = commission + ? WHERE user_id = ?", (montant, uid))
    now = datetime.now().strftime(DATE_FMT)
    cur.execute(
        "INSERT INTO commissions (utilisateur, montant, raison, date) VALUES (?, ?, ?, ?)",
        (uid, montant, raison, now),
    )
    conn.commit()


def get_parrain(uid):
    """Renvoie l'ID du parrain direct de uid, ou None."""
    cur.execute("SELECT parrain FROM referrals WHERE filleul = ?", (uid,))
    row = cur.fetchone()
    return row[0] if row else None


def process_referral(code, new_uid):
    """Enregistre le parrainage niveau 1 quand un nouvel utilisateur arrive via un lien."""
    if not code:
        return
    cur.execute("SELECT user_id FROM ambassadors WHERE code = ?", (code.strip(),))
    row = cur.fetchone()
    if not row:
        return
    parrain_uid = row[0]

    if parrain_uid == new_uid:
        return  # anti auto-parrainage

    if get_parrain(new_uid) is not None:
        return  # déjà parrainé (un seul parrain autorisé)

    now = datetime.now().strftime(DATE_FMT)
    cur.execute(
        "INSERT INTO referrals (parrain, filleul, niveau, date) VALUES (?, ?, 1, ?)",
        (parrain_uid, new_uid, now),
    )
    conn.commit()

    if not is_blocked(parrain_uid):
        add_points(parrain_uid, amb_setting("amb_signup_points"), "Nouveau filleul inscrit")
        return parrain_uid  # pour notification côté appelant


def count_referrals(parrain_uid):
    cur.execute("SELECT COUNT(*) FROM referrals WHERE parrain = ?", (parrain_uid,))
    return cur.fetchone()[0]


def get_referrals_list(parrain_uid):
    cur.execute("SELECT filleul, date FROM referrals WHERE parrain = ? ORDER BY date DESC", (parrain_uid,))
    return cur.fetchall()  # liste de (filleul_id, date)


def count_vip_referrals(parrain_uid):
    filleuls = [f for f, _ in get_referrals_list(parrain_uid)]
    return sum(1 for uid in filleuls if is_vip(uid))


def count_niveau2(parrain_uid):
    """Nombre de filleuls indirects (filleuls de mes filleuls)."""
    filleuls = [f for f, _ in get_referrals_list(parrain_uid)]
    return sum(count_referrals(f) for f in filleuls)


def count_vip_niveau2(parrain_uid):
    filleuls = [f for f, _ in get_referrals_list(parrain_uid)]
    total = 0
    for f in filleuls:
        sous_filleuls = [sf for sf, _ in get_referrals_list(f)]
        total += sum(1 for uid in sous_filleuls if is_vip(uid))
    return total


def credit_purchase_rewards(buyer_uid, days):
    """À appeler quand un paiement VIP est validé. Crédite le filleul + parrains N1/N2."""
    tier = 7 if days <= 7 else 30
    if tier == 7:
        pts_personal = amb_setting("amb_personal_vip7_points")
        pts_l1 = amb_setting("amb_l1_vip7_points")
        commission_l1 = amb_setting("amb_l1_vip7_commission")
        pts_l2 = amb_setting("amb_l2_vip7_points")
    else:
        pts_personal = amb_setting("amb_personal_vip30_points")
        pts_l1 = amb_setting("amb_l1_vip30_points")
        commission_l1 = amb_setting("amb_l1_vip30_commission")
        pts_l2 = amb_setting("amb_l2_vip30_points")

    ensure_ambassador(buyer_uid)
    add_points(buyer_uid, pts_personal, f"Bonus abonnement personnel VIP {tier}j")

    notify = []  # (uid, message)

    parrain1 = get_parrain(buyer_uid)
    if parrain1 and not is_blocked(parrain1):
        add_points(parrain1, pts_l1, f"Filleul direct VIP {tier}j")
        add_commission(parrain1, commission_l1, f"Commission filleul direct VIP {tier}j")
        notify.append((
            parrain1,
            "💎 Félicitations !\n\nTon filleul vient de prendre un abonnement VIP.\n\n"
            f"⭐ +{pts_l1} points\n💰 +{commission_l1} FCFA commission Wave",
        ))

        parrain2 = get_parrain(parrain1)
        if parrain2 and not is_blocked(parrain2):
            add_points(parrain2, pts_l2, f"Filleul indirect VIP {tier}j")
            notify.append((
                parrain2,
                "💎 Félicitations !\n\nUn filleul de ton réseau (niveau 2) vient de prendre un abonnement VIP.\n\n"
                f"⭐ +{pts_l2} points",
            ))

        now = datetime.now().strftime(DATE_FMT)
        cur.execute(
            "INSERT INTO ambassador_sales (buyer, parrain1, parrain2, tier, date) VALUES (?, ?, ?, ?, ?)",
            (buyer_uid, parrain1, parrain2 if parrain2 else None, tier, now),
        )
        conn.commit()

    return notify


def redeem_points(uid, days):
    """Échange des points contre un VIP gratuit. Renvoie (ok, message)."""
    ambassador = get_ambassador(uid)
    if not ambassador:
        return False, "❌ Compte ambassadeur introuvable."
    if ambassador[4]:  # blocked
        return False, "❌ Ton compte ambassadeur est bloqué."

    cost = amb_setting("amb_redeem_vip7_points") if days == 7 else amb_setting("amb_redeem_vip30_points")
    points = ambassador[2]
    if points < cost:
        return False, f"❌ Points insuffisants. Il te faut {cost} points (tu as {points})."

    add_points(uid, -cost, f"Échange VIP {days}j gratuit")
    add_vip(uid, days)
    return True, f"🎉 Échange réussi ! VIP {days} jours activé.\n⭐ -{cost} points"


def request_withdrawal(uid, montant, wave_number):
    ambassador = get_ambassador(uid)
    if not ambassador:
        return False, "❌ Compte ambassadeur introuvable."
    if ambassador[4]:
        return False, "❌ Ton compte ambassadeur est bloqué."
    min_withdrawal = amb_setting("amb_min_withdrawal")
    if montant < min_withdrawal:
        return False, f"❌ Le retrait minimum est de {min_withdrawal} FCFA."
    if montant > ambassador[3]:
        return False, f"❌ Solde insuffisant. Ton solde est de {ambassador[3]} FCFA."

    now = datetime.now().strftime(DATE_FMT)
    cur.execute(
        "INSERT INTO withdrawal_requests (utilisateur, montant, statut, date, wave_number) "
        "VALUES (?, ?, 'en_attente', ?, ?)",
        (uid, montant, now, wave_number),
    )
    conn.commit()
    return True, cur.lastrowid


def get_withdrawal(wid):
    cur.execute(
        "SELECT id, utilisateur, montant, statut, date, wave_number, paid_at "
        "FROM withdrawal_requests WHERE id = ?",
        (wid,),
    )
    return cur.fetchone()


def update_withdrawal_status(wid, statut, deduct_on_paid=False):
    row = get_withdrawal(wid)
    if not row:
        return
    _, uid, montant, _, _, _, _ = row
    if statut == "payée":
        now = datetime.now().strftime(DATE_FMT)
        cur.execute("UPDATE withdrawal_requests SET statut = ?, paid_at = ? WHERE id = ?", (statut, now, wid))
    else:
        cur.execute("UPDATE withdrawal_requests SET statut = ? WHERE id = ?", (statut, wid))
    if deduct_on_paid:
        cur.execute("UPDATE ambassadors SET commission = commission - ? WHERE user_id = ?", (montant, uid))
    conn.commit()


def get_pending_withdrawals():
    cur.execute(
        "SELECT id, utilisateur, montant, date, wave_number FROM withdrawal_requests "
        "WHERE statut = 'en_attente' ORDER BY date ASC"
    )
    return cur.fetchall()


def get_user_withdrawals(uid, limit=15):
    cur.execute(
        "SELECT id, montant, statut, date, paid_at FROM withdrawal_requests "
        "WHERE utilisateur = ? ORDER BY date DESC LIMIT ?",
        (uid, limit),
    )
    return cur.fetchall()


def get_user_points_history(uid, limit=5):
    cur.execute(
        "SELECT points, raison, date FROM points_history WHERE utilisateur = ? ORDER BY date DESC LIMIT ?",
        (uid, limit),
    )
    return cur.fetchall()


def total_paiements_effectues():
    cur.execute("SELECT COALESCE(SUM(montant), 0) FROM withdrawal_requests WHERE statut = 'payée'")
    return cur.fetchone()[0]


def list_ambassadors(limit=30):
    cur.execute(
        "SELECT user_id, code, points, commission, blocked FROM ambassadors "
        "ORDER BY points DESC LIMIT ?",
        (limit,),
    )
    return cur.fetchall()


def total_ambassadors_actifs():
    cur.execute("SELECT COUNT(*) FROM ambassadors WHERE user_id IN (SELECT DISTINCT parrain FROM referrals)")
    return cur.fetchone()[0]


def total_filleuls_global():
    cur.execute("SELECT COUNT(*) FROM referrals")
    return cur.fetchone()[0]


def total_ventes_ambassadeurs():
    cur.execute("SELECT COUNT(*) FROM ambassador_sales")
    return cur.fetchone()[0]


def total_commissions_distribuees():
    cur.execute("SELECT COALESCE(SUM(montant), 0) FROM commissions")
    return cur.fetchone()[0]


def top_ambassadors(limit=10):
    cur.execute(
        "SELECT user_id, code, points, commission FROM ambassadors ORDER BY points DESC LIMIT ?",
        (limit,),
    )
    return cur.fetchall()


def set_blocked(uid, blocked):
    ensure_ambassador(uid)
    cur.execute("UPDATE ambassadors SET blocked = ? WHERE user_id = ?", (1 if blocked else 0, uid))
    conn.commit()


def admin_remove_points(uid, points):
    ensure_ambassador(uid)
    cur.execute("UPDATE ambassadors SET points = MAX(points - ?, 0) WHERE user_id = ?", (points, uid))
    now = datetime.now().strftime(DATE_FMT)
    cur.execute(
        "INSERT INTO points_history (utilisateur, points, raison, date) VALUES (?, ?, ?, ?)",
        (uid, -points, "Retrait manuel par admin", now),
    )
    conn.commit()


# =========================
# 🧠 ÉTATS DE CONVERSATION (admin)
# =========================

# admin_state[admin_id] = {"action": "..."}
admin_state = {}

# admin_pending_broadcast[admin_id] = {"type": "all"/"vip", "text": "..."}
admin_pending_broadcast = {}

# user_state[user_id] = {"action": "..."}  (ex: saisie du montant de retrait)
user_state = {}


def clear_state(uid):
    admin_state.pop(uid, None)
    user_state.pop(uid, None)


# =========================
# 📱 CLAVIERS
# =========================

BOT_USERNAME = "Couponvip_support_bot"


def keyboard():
    return ReplyKeyboardMarkup([
        ["🎫 Coupon Gratuit"],
        ["💎 Coupon VIP"],
        ["🔥 Pourquoi devenir VIP ?"],
        ["🌟 CLUB AMBASSADEUR"],
        ["📖 Comment marche le Club Ambassadeur ?"],
        ["💳 Abonnement"],
        ["✅ J'ai payé"],
        ["🆔 Mon ID"],
        ["📞 Contact Admin"],
        ["🔄 Actualiser mon menu"],
    ], resize_keyboard=True)


def ambassador_keyboard():
    return ReplyKeyboardMarkup([
        ["📊 Voir mes filleuls"],
        ["🎁 Échanger mes points"],
        ["💸 Retirer ma prime"],
        ["📜 Historique des paiements"],
        ["⬅️ Retour au menu"],
    ], resize_keyboard=True)


def amb_settings_keyboard():
    return ReplyKeyboardMarkup([
        ["💰 Retrait Min"],
        ["⭐ Récompenses Points"],
        ["💵 Commissions"],
        ["🎁 Récompenses VIP (points)"],
        ["⬅️ Retour Admin"],
    ], resize_keyboard=True)


def admin_keyboard():
    return ReplyKeyboardMarkup([
        ["📊 Statistiques", "👥 Utilisateurs"],
        ["👑 Liste VIP", "💰 Paiements"],
        ["🎫 Modifier Coupon Gratuit", "💎 Modifier Coupon VIP"],
        ["➕ Ajouter VIP 7 jours", "➕ Ajouter VIP 30 jours"],
        ["❌ Retirer VIP", "📱 Modifier Numéro"],
        ["📢 Message Tous", "💎 Message VIP"],
        ["🌟 Ambassadeurs", "🏆 Classement"],
        ["💸 Demandes paiement ambassadeurs"],
        ["⚙️ Param. Ambassadeur"],
        ["🔄 Actualiser"],
    ], resize_keyboard=True)


ADMIN_BUTTONS = {
    "📊 Statistiques", "👥 Utilisateurs", "👑 Liste VIP", "💰 Paiements",
    "🎫 Modifier Coupon Gratuit", "💎 Modifier Coupon VIP",
    "➕ Ajouter VIP 7 jours", "➕ Ajouter VIP 30 jours", "❌ Retirer VIP",
    "📱 Modifier Numéro", "📢 Message Tous", "💎 Message VIP", "🔄 Actualiser",
    "🌟 Ambassadeurs", "🏆 Classement", "💸 Demandes paiement ambassadeurs",
    "⚙️ Param. Ambassadeur", "💰 Retrait Min", "⭐ Récompenses Points",
    "💵 Commissions", "🎁 Récompenses VIP (points)", "⬅️ Retour Admin",
}

USER_BUTTONS = {
    "🎫 Coupon Gratuit", "💎 Coupon VIP", "🔥 Pourquoi devenir VIP ?",
    "💳 Abonnement", "✅ J'ai payé", "🆔 Mon ID", "📞 Contact Admin",
    "🌟 CLUB AMBASSADEUR", "📊 Voir mes filleuls", "🎁 Échanger mes points",
    "💸 Retirer ma prime", "📜 Historique des paiements", "⬅️ Retour au menu",
    "📖 Comment marche le Club Ambassadeur ?", "🔄 Actualiser mon menu",
}


def is_redeem_button(text):
    return text.startswith("🎁 VIP 7j (") or text.startswith("🎁 VIP 30j (")


# =========================
# 🚀 START
# =========================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id

    # On vérifie si c'est un tout nouvel utilisateur AVANT de l'enregistrer
    cur.execute("SELECT id FROM users WHERE id = ?", (user_id,))
    is_new_user = cur.fetchone() is None

    add_user(user_id)
    ensure_ambassador(user_id)
    clear_state(user_id)

    # Lien de parrainage : /start CODE_UTILISATEUR
    if is_new_user and context.args:
        referral_code = context.args[0]
        parrain_uid = process_referral(referral_code, user_id)
        if parrain_uid:
            try:
                await context.bot.send_message(
                    parrain_uid,
                    "🎉 Nouveau filleul !\n\n"
                    "Une personne vient de rejoindre COUPON VIP grâce à ton lien.\n\n"
                    "⭐ +10 points ajoutés.",
                )
            except Exception:
                pass

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

    elif action == "set_min_withdrawal":
        try:
            val = int(text.strip())
        except ValueError:
            await update.message.reply_text("❌ Envoie un nombre valide.")
            return True
        set_setting("amb_min_withdrawal", str(val))
        await update.message.reply_text(f"✅ Retrait minimum mis à jour : {val} FCFA", reply_markup=amb_settings_keyboard())

    elif action == "set_points_rewards":
        parts = text.strip().split()
        if len(parts) != 7 or not all(p.lstrip("-").isdigit() for p in parts):
            await update.message.reply_text(
                "❌ Format invalide. Envoie 7 nombres séparés par des espaces, dans l'ordre :\n"
                "Inscription N1_VIP7 N1_VIP30 N2_VIP7 N2_VIP30 Bonus_perso_VIP7 Bonus_perso_VIP30"
            )
            return True
        keys = [
            "amb_signup_points", "amb_l1_vip7_points", "amb_l1_vip30_points",
            "amb_l2_vip7_points", "amb_l2_vip30_points",
            "amb_personal_vip7_points", "amb_personal_vip30_points",
        ]
        for k, v in zip(keys, parts):
            set_setting(k, v)
        await update.message.reply_text("✅ Récompenses en points mises à jour.", reply_markup=amb_settings_keyboard())

    elif action == "set_commissions":
        parts = text.strip().split()
        if len(parts) != 2 or not all(p.lstrip("-").isdigit() for p in parts):
            await update.message.reply_text("❌ Format invalide. Envoie 2 nombres : Commission_VIP7 Commission_VIP30")
            return True
        set_setting("amb_l1_vip7_commission", parts[0])
        set_setting("amb_l1_vip30_commission", parts[1])
        await update.message.reply_text("✅ Commissions mises à jour.", reply_markup=amb_settings_keyboard())

    elif action == "set_redeem_thresholds":
        parts = text.strip().split()
        if len(parts) != 2 or not all(p.lstrip("-").isdigit() for p in parts):
            await update.message.reply_text("❌ Format invalide. Envoie 2 nombres : Points_pour_VIP7 Points_pour_VIP30")
            return True
        set_setting("amb_redeem_vip7_points", parts[0])
        set_setting("amb_redeem_vip30_points", parts[1])
        await update.message.reply_text("✅ Seuils de conversion mis à jour.", reply_markup=amb_settings_keyboard())

    elif action in ("broadcast_all", "broadcast_vip"):
        btype = "all" if action == "broadcast_all" else "vip"
        await handle_broadcast_text(update, context, btype, text)

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

    # Si le texte correspond à un bouton connu, on annule tout état en cours
    if text in ADMIN_BUTTONS or text in USER_BUTTONS or is_redeem_button(text):
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

        elif text == "🌟 Ambassadeurs":
            await update.message.reply_text(
                "🌟 GESTION AMBASSADEURS\n\n"
                f"👥 Ambassadeurs actifs (≥1 filleul) : {total_ambassadors_actifs()}\n"
                f"👥 Total filleuls (niveau 1) : {total_filleuls_global()}\n"
                f"💎 Abonnements obtenus grâce aux ambassadeurs : {total_ventes_ambassadeurs()}\n"
                f"💰 Total commissions distribuées : {total_commissions_distribuees()} FCFA\n"
                f"💸 Total paiements effectués : {total_paiements_effectues()} FCFA"
            )
            return

        elif text == "🏆 Classement":
            ambs = top_ambassadors(10)
            if not ambs:
                await update.message.reply_text("Aucun ambassadeur pour le moment.")
                return
            medals = ["🥇", "🥈", "🥉"]
            lines = ["🏆 TOP AMBASSADEURS\n"]
            for i, (uid, code, points, commission) in enumerate(ambs, start=1):
                rank = medals[i - 1] if i <= 3 else f"{i}-"
                nb1 = count_referrals(uid)
                nbvip = count_vip_referrals(uid) + count_vip_niveau2(uid)
                lines.append(
                    f"{rank} 🆔 {uid}\n👥 Filleuls : {nb1}\n💎 VIP apportés : {nbvip}\n"
                    f"⭐ Points : {points}\n💰 Commission : {commission} FCFA\n"
                )
            await update.message.reply_text("\n".join(lines))
            return

        elif text == "💸 Demandes paiement ambassadeurs":
            pending = get_pending_withdrawals()
            if not pending:
                await update.message.reply_text("Aucune demande de paiement en attente.")
                return
            lines = ["💸 DEMANDES EN ATTENTE\n"]
            for wid, uid, montant, date, wave_number in pending:
                lines.append(f"#{wid} | 🆔 {uid} | {montant} FCFA | 📱 {wave_number or 'non fourni'} | {date}")
            lines.append("\n👉 Utilise les boutons envoyés au moment de chaque demande pour Paiement effectué / Refuser.")
            await update.message.reply_text("\n".join(lines))
            return

        elif text == "⚙️ Param. Ambassadeur":
            await update.message.reply_text(
                "⚙️ PARAMÈTRES AMBASSADEUR ACTUELS\n\n"
                f"💰 Retrait minimum : {amb_setting('amb_min_withdrawal')} FCFA\n\n"
                f"⭐ Inscription (N1) : {amb_setting('amb_signup_points')} pts\n"
                f"⭐ Achat VIP7 par un filleul N1 : {amb_setting('amb_l1_vip7_points')} pts\n"
                f"⭐ Achat VIP30 par un filleul N1 : {amb_setting('amb_l1_vip30_points')} pts\n"
                f"⭐ Achat VIP7 par un filleul N2 : {amb_setting('amb_l2_vip7_points')} pts\n"
                f"⭐ Achat VIP30 par un filleul N2 : {amb_setting('amb_l2_vip30_points')} pts\n"
                f"⭐ Bonus perso VIP7 : {amb_setting('amb_personal_vip7_points')} pts\n"
                f"⭐ Bonus perso VIP30 : {amb_setting('amb_personal_vip30_points')} pts\n\n"
                f"💵 Commission N1 VIP7 : {amb_setting('amb_l1_vip7_commission')} FCFA\n"
                f"💵 Commission N1 VIP30 : {amb_setting('amb_l1_vip30_commission')} FCFA\n\n"
                f"🎁 Points requis VIP7 gratuit : {amb_setting('amb_redeem_vip7_points')} pts\n"
                f"🎁 Points requis VIP30 gratuit : {amb_setting('amb_redeem_vip30_points')} pts\n\n"
                "👉 Choisis ce que tu veux modifier :",
                reply_markup=amb_settings_keyboard(),
            )
            return

        elif text == "💰 Retrait Min":
            admin_state[user_id] = {"action": "set_min_withdrawal"}
            await update.message.reply_text(
                f"💰 Montant minimum actuel : {amb_setting('amb_min_withdrawal')} FCFA\n\n"
                "Envoie le nouveau montant minimum de retrait (nombre) :"
            )
            return

        elif text == "⭐ Récompenses Points":
            admin_state[user_id] = {"action": "set_points_rewards"}
            await update.message.reply_text(
                "⭐ RÉCOMPENSES EN POINTS\n\n"
                "Envoie les 6 valeurs dans cet ordre, séparées par des espaces :\n"
                "Inscription | N1_VIP7 | N1_VIP30 | N2_VIP7 | N2_VIP30 | Bonus_perso_VIP7 | Bonus_perso_VIP30\n\n"
                f"Valeurs actuelles :\n{amb_setting('amb_signup_points')} {amb_setting('amb_l1_vip7_points')} "
                f"{amb_setting('amb_l1_vip30_points')} {amb_setting('amb_l2_vip7_points')} "
                f"{amb_setting('amb_l2_vip30_points')} {amb_setting('amb_personal_vip7_points')} "
                f"{amb_setting('amb_personal_vip30_points')}\n\n"
                "⚠️ Ce sont 7 valeurs à envoyer, dans cet ordre exact."
            )
            return

        elif text == "💵 Commissions":
            admin_state[user_id] = {"action": "set_commissions"}
            await update.message.reply_text(
                "💵 COMMISSIONS (FCFA)\n\n"
                "Envoie les 2 valeurs séparées par un espace : Commission_VIP7 Commission_VIP30\n\n"
                f"Valeurs actuelles : {amb_setting('amb_l1_vip7_commission')} {amb_setting('amb_l1_vip30_commission')}"
            )
            return

        elif text == "🎁 Récompenses VIP (points)":
            admin_state[user_id] = {"action": "set_redeem_thresholds"}
            await update.message.reply_text(
                "🎁 SEUILS DE CONVERSION POINTS → VIP GRATUIT\n\n"
                "Envoie les 2 valeurs séparées par un espace : Points_pour_VIP7 Points_pour_VIP30\n\n"
                f"Valeurs actuelles : {amb_setting('amb_redeem_vip7_points')} {amb_setting('amb_redeem_vip30_points')}"
            )
            return

        elif text == "⬅️ Retour Admin":
            clear_state(user_id)
            await update.message.reply_text("Tableau de bord admin 👇", reply_markup=admin_keyboard())
            return

        elif text == "🔄 Actualiser":
            await update.message.reply_text("🔄 Tableau de bord actualisé.", reply_markup=admin_keyboard())
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

    elif text == "🔄 Actualiser mon menu":
        await update.message.reply_text(
            "🔄 Ton menu a été actualisé ! Tu as maintenant accès aux dernières nouveautés 👇",
            reply_markup=keyboard(),
        )

    # =========================
    # 🌟 CLUB AMBASSADEUR
    # =========================

    elif text == "📖 Comment marche le Club Ambassadeur ?":
        await update.message.reply_text(
            "📖 CLUB AMBASSADEUR — COMMENT ÇA MARCHE ?\n\n"
            "🌟 CLUB AMBASSADEUR te permet de gagner des points et de l'argent "
            "en invitant d'autres personnes sur COUPON VIP.\n\n"
            "1️⃣ Récupère ton lien personnel dans 🌟 CLUB AMBASSADEUR.\n\n"
            "2️⃣ Partage-le. Chaque personne qui rejoint via ton lien devient ton filleul.\n"
            f"   ⭐ +{amb_setting('amb_signup_points')} points dès son inscription.\n\n"
            "3️⃣ Si ton filleul prend un abonnement VIP, tu gagnes encore plus :\n"
            f"   • VIP 7 jours → ⭐ {amb_setting('amb_l1_vip7_points')} points + 💰 {amb_setting('amb_l1_vip7_commission')} FCFA\n"
            f"   • VIP 30 jours → ⭐ {amb_setting('amb_l1_vip30_points')} points + 💰 {amb_setting('amb_l1_vip30_commission')} FCFA\n\n"
            "4️⃣ Même si ton filleul invite quelqu'un d'autre (niveau 2), tu touches "
            "encore des points (sans commission à ce niveau).\n\n"
            "⭐ Les points servent à obtenir un VIP gratuit :\n"
            f"   • {amb_setting('amb_redeem_vip7_points')} points → VIP 7 jours gratuit\n"
            f"   • {amb_setting('amb_redeem_vip30_points')} points → VIP 30 jours gratuit\n\n"
            "💰 Les commissions se retirent en FCFA via Wave "
            f"(minimum {amb_setting('amb_min_withdrawal')} FCFA).\n\n"
            "👉 Clique sur 🌟 CLUB AMBASSADEUR pour voir ton code, ton lien et ton solde !"
        )

    elif text == "🌟 CLUB AMBASSADEUR":
        ensure_ambassador(user_id)
        amb = get_ambassador(user_id)
        _, code, points, commission, blocked = amb
        nb_n1 = count_referrals(user_id)
        nb_n2 = count_niveau2(user_id)
        nb_vip_total = count_vip_referrals(user_id) + count_vip_niveau2(user_id)
        lien = f"https://t.me/{BOT_USERNAME}?start={code}"

        blocked_note = "\n\n🚫 Ton compte ambassadeur est actuellement bloqué." if blocked else ""

        await update.message.reply_text(
            "🌟 Mon Club Ambassadeur\n\n"
            f"🆔 Mon code :\n{code}\n\n"
            f"🔗 Mon lien :\n{lien}\n\n"
            f"👥 Mes filleuls :\nNiveau 1 : {nb_n1}\nNiveau 2 : {nb_n2}\n\n"
            f"💎 Clients VIP apportés : {nb_vip_total}\n\n"
            f"⭐ Mes points : {points}\n\n"
            f"💰 Ma commission : {commission} FCFA\n\n"
            "📈 Objectifs :\n"
            "1000 points = VIP 7 jours\n"
            "4000 points = VIP 30 jours"
            f"{blocked_note}",
            reply_markup=ambassador_keyboard(),
        )

    elif text == "⬅️ Retour au menu":
        clear_state(user_id)
        await update.message.reply_text("Menu principal 👇", reply_markup=keyboard())

    elif text == "📊 Voir mes filleuls":
        filleuls_n1 = get_referrals_list(user_id)
        entries = [(fid, fdate, 1) for fid, fdate in filleuls_n1]
        for fid, _ in filleuls_n1:
            for sfid, sfdate in get_referrals_list(fid):
                entries.append((sfid, sfdate, 2))

        if not entries:
            await update.message.reply_text("Tu n'as pas encore de filleul. Partage ton lien pour commencer !")
            return

        entries.sort(key=lambda e: e[1], reverse=True)
        lines = ["👥 MES FILLEULS\n"]
        for i, (fid, fdate, niveau) in enumerate(entries, start=1):
            statut = "💎 VIP actif" if is_vip(fid) else "✅ Utilisateur gratuit"
            lines.append(f"{i}. 🆔 {fid} — Niveau {niveau} — inscrit le {fdate} — {statut}")
        await update.message.reply_text("\n".join(lines))

    elif text == "🎁 Échanger mes points":
        amb = get_ambassador(user_id)
        points = amb[2] if amb else 0
        cost7 = amb_setting("amb_redeem_vip7_points")
        cost40 = amb_setting("amb_redeem_vip30_points")
        kb = ReplyKeyboardMarkup([
            [f"🎁 VIP 7j ({cost7} pts)"],
            [f"🎁 VIP 30j ({cost40} pts)"],
            ["⬅️ Retour au menu"],
        ], resize_keyboard=True)

        historique = get_user_points_history(user_id, 5)
        histo_lines = ""
        if historique:
            histo_lines = "\n\n📜 Derniers mouvements :\n" + "\n".join(
                f"{'+' if p > 0 else ''}{p} pts — {r} ({d})" for p, r, d in historique
            )

        await update.message.reply_text(
            f"🎁 ÉCHANGE DE POINTS\n\n⭐ Ton solde : {points} points\n\n"
            f"• {cost7} points → VIP gratuit 7 jours\n"
            f"• {cost40} points → VIP gratuit 30 jours"
            f"{histo_lines}",
            reply_markup=kb,
        )

    elif is_redeem_button(text):
        days = 7 if text.startswith("🎁 VIP 7j (") else 30
        ok, msg = redeem_points(user_id, days)
        await update.message.reply_text(msg, reply_markup=ambassador_keyboard())

    elif text == "💸 Retirer ma prime":
        amb = get_ambassador(user_id)
        commission = amb[3] if amb else 0
        min_withdrawal = amb_setting("amb_min_withdrawal")
        if commission < min_withdrawal:
            await update.message.reply_text(
                f"💰 Ton solde est de {commission} FCFA.\n"
                f"Le retrait minimum est de {min_withdrawal} FCFA."
            )
            return
        user_state[user_id] = {"action": "withdraw_amount"}
        await update.message.reply_text(
            "💰 DEMANDE DE PAIEMENT\n\n"
            f"Commission disponible : {commission} FCFA\n"
            f"Montant minimum : {min_withdrawal} FCFA\n\n"
            "Envoie le montant que tu souhaites retirer :"
        )

    elif text == "📜 Historique des paiements":
        historique = get_user_withdrawals(user_id)
        if not historique:
            await update.message.reply_text("📜 Aucun paiement pour le moment.")
            return
        icons = {"payée": "✅", "en_attente": "⏳", "refusée": "❌"}
        lines = ["📜 HISTORIQUE DE MES PAIEMENTS\n"]
        for wid, montant, statut, date, paid_at in historique:
            icon = icons.get(statut, "•")
            if statut == "payée":
                lines.append(f"{icon} {montant} FCFA\nPayé le {paid_at}\n")
            elif statut == "refusée":
                lines.append(f"{icon} {montant} FCFA\nRefusé\n")
            else:
                lines.append(f"{icon} {montant} FCFA\nEn attente\n")
        await update.message.reply_text("\n".join(lines))

    elif user_id in user_state and user_state[user_id].get("action") == "withdraw_amount":
        try:
            montant = int(text.strip())
        except ValueError:
            await update.message.reply_text("❌ Montant invalide. Réessaie avec un nombre.")
            return

        amb = get_ambassador(user_id)
        min_withdrawal = amb_setting("amb_min_withdrawal")
        if montant < min_withdrawal:
            await update.message.reply_text(f"❌ Le retrait minimum est de {min_withdrawal} FCFA.")
            return
        if amb and montant > amb[3]:
            await update.message.reply_text(f"❌ Solde insuffisant. Ton solde est de {amb[3]} FCFA.")
            return

        user_state[user_id] = {"action": "withdraw_wave_number", "montant": montant}
        await update.message.reply_text("📱 Envoie ton numéro Wave pour recevoir ton paiement :")

    elif user_id in user_state and user_state[user_id].get("action") == "withdraw_wave_number":
        montant = user_state[user_id].get("montant")
        wave_number = text.strip()
        user_state.pop(user_id, None)

        ok, result = request_withdrawal(user_id, montant, wave_number)
        if not ok:
            await update.message.reply_text(result, reply_markup=ambassador_keyboard())
            return

        wid = result
        amb = get_ambassador(user_id)
        await update.message.reply_text(
            f"✅ Demande de paiement envoyée (#{wid}). Traitement sous 24h.",
            reply_markup=ambassador_keyboard(),
        )
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ Paiement effectué", callback_data=f"wd:paid:{wid}"),
             InlineKeyboardButton("❌ Refuser", callback_data=f"wd:refuse:{wid}")]
        ])
        await context.bot.send_message(
            ADMIN_ID,
            "💸 Nouvelle demande de retrait\n\n"
            f"👤 Utilisateur : {user_id}\n"
            f"💰 Montant : {montant} FCFA\n"
            f"📱 Numéro Wave : {wave_number}\n"
            f"💼 Solde disponible : {amb[3]} FCFA\n"
            f"📅 Date : {datetime.now().strftime(DATE_FMT)}",
            reply_markup=kb,
        )

    else:
        # Texte non reconnu : probablement un ancien bouton mis en cache sur le
        # téléphone de l'utilisateur (clavier pas encore rafraîchi après un déploiement).
        # On renvoie le menu à jour au lieu de rester silencieux.
        if user_id == ADMIN_ID:
            await update.message.reply_text(
                "🔄 Menu mis à jour ! Utilise les boutons ci-dessous 👇",
                reply_markup=admin_keyboard(),
            )
        else:
            await update.message.reply_text(
                "🔄 Menu mis à jour ! Utilise les boutons ci-dessous 👇",
                reply_markup=keyboard(),
            )


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
            for notify_uid, notify_text in credit_purchase_rewards(uid, 7):
                try:
                    await context.bot.send_message(notify_uid, notify_text)
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
            for notify_uid, notify_text in credit_purchase_rewards(uid, 30):
                try:
                    await context.bot.send_message(notify_uid, notify_text)
                except Exception:
                    pass

        else:  # pvref
            update_payment_status(pid, "refusé")
            result_text = f"❌ Paiement #{pid} refusé pour {uid}"
            try:
                await context.bot.send_message(uid, "❌ Ton paiement n'a pas pu être validé. Contacte l'admin pour plus d'infos.")
                await context.bot.send_message(
                    uid,
                    "En attendant, profite quand même de nos 🎫 coupons gratuits et de nos "
                    "coupons flash ⚡ disponibles régulièrement !"
                )
            except Exception:
                pass

        if query.message.photo:
            await query.edit_message_caption(caption=result_text)
        else:
            await query.edit_message_text(result_text)
        return

    # ---- Demandes de retrait (commissions) ----
    if data.startswith("wd:"):
        _, wd_action, wid_str = data.split(":")
        wid = int(wid_str)
        wd = get_withdrawal(wid)

        if not wd:
            await query.edit_message_text("⚠️ Demande introuvable.")
            return

        _, uid, montant, statut, date, wave_number, paid_at = wd

        if statut != "en_attente":
            await query.edit_message_text(f"⚠️ Demande déjà traitée ({statut}).")
            return

        if wd_action == "refuse":
            update_withdrawal_status(wid, "refusée")
            result_text = f"❌ Demande #{wid} refusée — {montant} FCFA pour {uid}"
            try:
                await context.bot.send_message(uid, f"❌ Ta demande de paiement de {montant} FCFA a été refusée. Contacte l'admin pour plus d'infos.")
            except Exception:
                pass

        else:  # paid
            update_withdrawal_status(wid, "payée", deduct_on_paid=True)
            result_text = f"✅ Demande #{wid} marquée comme PAYÉE — {montant} FCFA pour {uid} (Wave : {wave_number})"
            try:
                await context.bot.send_message(
                    uid,
                    "🎉 Paiement validé !\n\n"
                    "Bonjour 👋\n\n"
                    f"Ta demande de paiement de {montant} FCFA a été traitée avec succès.\n\n"
                    f"💰 Montant payé :\n{montant} FCFA\n\n"
                    "📱 Mode :\nWave\n\n"
                    "Merci pour ton implication dans le Club Ambassadeur Coupon VIP ⭐\n\n"
                    "Continue à développer ton réseau pour gagner encore plus de récompenses.",
                )
            except Exception:
                pass

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

async def error_handler(update, context):
    """Log toute exception dans les logs Railway au lieu de l'avaler silencieusement."""
    import traceback
    print("⚠️ ERREUR NON GÉRÉE :")
    traceback.print_exception(type(context.error), context.error, context.error.__traceback__)
    if update and hasattr(update, "message") and update.message:
        try:
            await update.message.reply_text(
                "⚠️ Une erreur est survenue pendant le traitement de ta demande. Réessaie ou contacte le support."
            )
        except Exception:
            pass


app = ApplicationBuilder().token(TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("stats", stats))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle))
app.add_handler(MessageHandler(filters.PHOTO, photo_handler))
app.add_handler(CallbackQueryHandler(callback_handler))
app.add_error_handler(error_handler)

print("🤖 BOT VIP OK (SQLite + panneau admin)")
app.run_polling()
