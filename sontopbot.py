import logging
import random
import sqlite3
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    CallbackQueryHandler, ContextTypes, filters
)
 
# === SOZLAMALAR ===
BOT_TOKEN = "8654793382:AAGQVWb9aw_qh4GsWi2v2O43Pd_W3ssUvAg"
ADMIN_IDS = [6261323164]  # Admin Telegram ID sini shu yerga qo'ying
MIN_NUMBER = 1
MAX_NUMBER = 100
MAX_ATTEMPTS = 7
 
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
 
# === MA'LUMOTLAR BAZASI ===
def init_db():
    conn = sqlite3.connect("game.db")
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            total_games INTEGER DEFAULT 0,
            total_wins INTEGER DEFAULT 0,
            best_attempts INTEGER DEFAULT 999
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS game_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            secret_number INTEGER,
            attempts INTEGER,
            won INTEGER,
            played_at TEXT
        )
    """)
    conn.commit()
    conn.close()
 
def get_or_create_user(user_id, username):
    conn = sqlite3.connect("game.db")
    c = conn.cursor()
    c.execute("INSERT OR IGNORE INTO users (user_id, username) VALUES (?, ?)", (user_id, username))
    c.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
    user = c.fetchone()
    conn.commit()
    conn.close()
    return user
 
def update_stats(user_id, won, attempts):
    conn = sqlite3.connect("game.db")
    c = conn.cursor()
    c.execute("UPDATE users SET total_games = total_games + 1 WHERE user_id = ?", (user_id,))
    if won:
        c.execute("UPDATE users SET total_wins = total_wins + 1 WHERE user_id = ?", (user_id,))
        c.execute("""
            UPDATE users SET best_attempts = ?
            WHERE user_id = ? AND best_attempts > ?
        """, (attempts, user_id, attempts))
    c.execute("""
        INSERT INTO game_history (user_id, secret_number, attempts, won, played_at)
        VALUES (?, ?, ?, ?, ?)
    """, (user_id, 0, attempts, int(won), datetime.now().isoformat()))
    conn.commit()
    conn.close()
 
def get_top_players():
    conn = sqlite3.connect("game.db")
    c = conn.cursor()
    c.execute("""
        SELECT username, total_wins, best_attempts, total_games
        FROM users
        WHERE total_wins > 0
        ORDER BY total_wins DESC, best_attempts ASC
        LIMIT 10
    """)
    rows = c.fetchall()
    conn.close()
    return rows
 
def get_all_users():
    conn = sqlite3.connect("game.db")
    c = conn.cursor()
    c.execute("SELECT user_id, username, total_games, total_wins FROM users")
    rows = c.fetchall()
    conn.close()
    return rows
 
# === O'YIN HOLATI ===
games = {}  # {user_id: {"number": int, "attempts": int}}
 
# === KLAVIATURA ===
def main_menu():
    keyboard = [
        [InlineKeyboardButton("🎮 O'yin boshlash", callback_data="start_game")],
        [InlineKeyboardButton("🏆 Reyting", callback_data="leaderboard")],
        [InlineKeyboardButton("📊 Mening statistikam", callback_data="my_stats")],
        [InlineKeyboardButton("ℹ️ Qoidalar", callback_data="rules")],
    ]
    return InlineKeyboardMarkup(keyboard)
 
def game_menu():
    keyboard = [
        [InlineKeyboardButton("🚪 O'yindan chiqish", callback_data="quit_game")]
    ]
    return InlineKeyboardMarkup(keyboard)
 
# === HANDLERLAR ===
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    get_or_create_user(user.id, user.username or user.first_name)
    await update.message.reply_text(
        f"👋 Salom, *{user.first_name}*!\n\n"
        f"🎯 *Raqam Topish O'yini*ga xush kelibsiz!\n\n"
        f"Men {MIN_NUMBER} dan {MAX_NUMBER} gacha raqam o'ylayman,\n"
        f"siz uni {MAX_ATTEMPTS} ta urinishda topishingiz kerak!",
        parse_mode="Markdown",
        reply_markup=main_menu()
    )
 
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user = query.from_user
    data = query.data
 
    if data == "start_game":
        secret = random.randint(MIN_NUMBER, MAX_NUMBER)
        games[user.id] = {"number": secret, "attempts": 0}
        await query.edit_message_text(
            f"🎮 *O'yin boshlandi!*\n\n"
            f"Men {MIN_NUMBER} va {MAX_NUMBER} orasidagi raqamni o'yladim.\n"
            f"Sizda *{MAX_ATTEMPTS} ta* urinish bor!\n\n"
            f"Raqamni kiriting 👇",
            parse_mode="Markdown",
            reply_markup=game_menu()
        )
 
    elif data == "quit_game":
        if user.id in games:
            del games[user.id]
        await query.edit_message_text(
            "🚪 O'yindan chiqdingiz.",
            reply_markup=main_menu()
        )
 
    elif data == "leaderboard":
        top = get_top_players()
        if not top:
            text = "🏆 *Reyting bo'sh*\nHali hech kim g'alaba qozonmagan!"
        else:
            text = "🏆 *Top O'yinchilar:*\n\n"
            medals = ["🥇", "🥈", "🥉"] + ["🎖️"] * 7
            for i, (uname, wins, best, games_count) in enumerate(top):
                text += f"{medals[i]} *{uname}*: {wins} g'alaba | eng yaxshi: {best} urinish\n"
        await query.edit_message_text(text, parse_mode="Markdown", reply_markup=main_menu())
 
    elif data == "my_stats":
        u = get_or_create_user(user.id, user.username or user.first_name)
        best = u[4] if u[4] != 999 else "—"
        win_rate = round(u[3] / u[2] * 100) if u[2] > 0 else 0
        text = (
            f"📊 *Sizning statistikangiz:*\n\n"
            f"🎮 Jami o'yinlar: {u[2]}\n"
            f"🏆 G'alabalar: {u[3]}\n"
            f"📈 G'alaba foizi: {win_rate}%\n"
            f"⚡ Eng yaxshi natija: {best} urinish"
        )
        await query.edit_message_text(text, parse_mode="Markdown", reply_markup=main_menu())
 
    elif data == "rules":
        text = (
            f"ℹ️ *O'yin Qoidalari:*\n\n"
            f"1️⃣ Bot {MIN_NUMBER}–{MAX_NUMBER} orasida raqam o'ylaydi\n"
            f"2️⃣ Sizda {MAX_ATTEMPTS} ta urinish bor\n"
            f"3️⃣ Har urinishda bot \"katta\" yoki \"kichik\" deydi\n"
            f"4️⃣ Raqamni topsangiz — g'alaba! 🏆\n"
            f"5️⃣ Urinishlar tugasa — yutqazdingiz 😢"
        )
        await query.edit_message_text(text, parse_mode="Markdown", reply_markup=main_menu())
 
    elif data == "admin_stats":
        if user.id not in ADMIN_IDS:
            await query.answer("❌ Ruxsat yo'q!", show_alert=True)
            return
        users = get_all_users()
        text = f"👑 *Admin Panel*\n\nJami foydalanuvchilar: {len(users)}\n\n"
        for uid, uname, tg, tw in users[:20]:
            text += f"• {uname}: {tg} o'yin, {tw} g'alaba\n"
        await query.edit_message_text(text, parse_mode="Markdown", reply_markup=main_menu())
 
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    text = update.message.text.strip()
 
    if user.id not in games:
        await update.message.reply_text(
            "O'yin boshlanmagan. Quyidagi tugmani bosing:",
            reply_markup=main_menu()
        )
        return
 
    try:
        guess = int(text)
    except ValueError:
        await update.message.reply_text("❗ Iltimos, faqat raqam kiriting!")
        return
 
    if guess < MIN_NUMBER or guess > MAX_NUMBER:
        await update.message.reply_text(
            f"❗ Raqam {MIN_NUMBER} va {MAX_NUMBER} orasida bo'lishi kerak!"
        )
        return
 
    game = games[user.id]
    game["attempts"] += 1
    secret = game["number"]
    attempts = game["attempts"]
    remaining = MAX_ATTEMPTS - attempts
 
    if guess == secret:
        del games[user.id]
        update_stats(user.id, True, attempts)
        stars = "⭐" * max(1, MAX_ATTEMPTS - attempts + 1)
        await update.message.reply_text(
            f"🎉 *To'g'ri!* Raqam {secret} edi!\n"
            f"Siz {attempts} ta urinishda topdingiz!\n{stars}",
            parse_mode="Markdown",
            reply_markup=main_menu()
        )
    elif remaining == 0:
        del games[user.id]
        update_stats(user.id, False, attempts)
        await update.message.reply_text(
            f"😢 *Yutqazdingiz!*\nTo'g'ri raqam *{secret}* edi.\nQayta urinib ko'ring!",
            parse_mode="Markdown",
            reply_markup=main_menu()
        )
    elif guess < secret:
        await update.message.reply_text(
            f"📈 *Kattaroq!* {guess} dan katta.\n"
            f"Qolgan urinishlar: *{remaining}*",
            parse_mode="Markdown",
            reply_markup=game_menu()
        )
    else:
        await update.message.reply_text(
            f"📉 *Kichikroq!* {guess} dan kichik.\n"
            f"Qolgan urinishlar: *{remaining}*",
            parse_mode="Markdown",
            reply_markup=game_menu()
        )
 
async def admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if user.id not in ADMIN_IDS:
        await update.message.reply_text("❌ Ruxsat yo'q!")
        return
    users = get_all_users()
    keyboard = [[InlineKeyboardButton("📊 Statistika", callback_data="admin_stats")]]
    await update.message.reply_text(
        f"👑 *Admin Panel*\nJami foydalanuvchilar: *{len(users)}*",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
 
# === ISHGA TUSHIRISH ===
def main():
    init_db()
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("admin", admin_command))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    print("✅ Bot ishga tushdi!")
    app.run_polling()
 
if __name__ == "__main__":
    main()
 