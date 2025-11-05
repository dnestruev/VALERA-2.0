import os
import logging
import datetime
import sqlite3
import requests

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes

from apscheduler.schedulers.asyncio import AsyncIOScheduler

# ----------- CONFIG -----------
BOT_TOKEN = os.getenv("BOT_TOKEN")
WEATHER_API = os.getenv("WEATHER_API")
ADMIN_ID = 6695259570
DB = "data.db"

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler()
scheduler.start()

# ----------- DB -----------
def db_init():
    conn = sqlite3.connect(DB)
    cur = conn.cursor()
    cur.execute("CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY, sub_exp TEXT)")
    cur.execute("CREATE TABLE IF NOT EXISTS notes (user INTEGER, note TEXT)")
    conn.commit()
    conn.close()

def db_add_user(uid):
    conn = sqlite3.connect(DB)
    cur = conn.cursor()
    cur.execute("INSERT OR IGNORE INTO users(id) VALUES (?)", (uid,))
    conn.commit()
    conn.close()

def db_add_note(uid, text):
    conn = sqlite3.connect(DB)
    cur = conn.cursor()
    cur.execute("INSERT INTO notes VALUES (?,?)", (uid, text))
    conn.commit()
    conn.close()

def db_get_notes(uid):
    conn = sqlite3.connect(DB)
    cur = conn.cursor()
    cur.execute("SELECT note FROM notes WHERE user = ?", (uid,))
    rows = cur.fetchall()
    conn.close()
    return [r[0] for r in rows]

def db_set_sub(uid, exp):
    conn = sqlite3.connect(DB)
    cur = conn.cursor()
    cur.execute("INSERT OR REPLACE INTO users(id, sub_exp) VALUES (?,?)", (uid, exp))
    conn.commit()
    conn.close()

def check_subscription(uid):
    conn = sqlite3.connect(DB)
    cur = conn.cursor()
    cur.execute("SELECT sub_exp FROM users WHERE id = ?", (uid,))
    row = cur.fetchone()
    conn.close()
    return row and datetime.datetime.now() < datetime.datetime.fromisoformat(row[0])

# ----------- WEATHER -----------
async def get_weather(city):
    try:
        url = f"https://api.openweathermap.org/data/2.5/weather?q={city}&appid={WEATHER_API}&units=metric&lang=ru"
        data = requests.get(url).json()
        if data.get("cod") != 200:
            return "❌ Город не найден"
        temp = data["main"]["temp"]
        desc = data["weather"][0]["description"]
        return f"🌤 Погода в {city}:\n🌡 {temp}°C\n📜 {desc.capitalize()}"
    except:
        return "⚠️ Ошибка погоды"

# ----------- COMMANDS -----------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    db_add_user(uid)

    keyboard = [
        [InlineKeyboardButton("📝 Заметки", callback_data="notes")],
        [InlineKeyboardButton("🌦 Погода", callback_data="weather")],
        [InlineKeyboardButton("🔐 Премиум", callback_data="premium")]
    ]

    await update.message.reply_text(
        "👋 Привет, я Валера!\nВыбери действие 👇",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def add_note(update: Update, context):
    text = " ".join(context.args)
    if not text:
        return await update.message.reply_text("Пример: `/note купить хлеб`", parse_mode="Markdown")
    
    db_add_note(update.effective_user.id, text)
    await update.message.reply_text("✅ Заметка сохранена")

async def list_notes(update: Update, context):
    n = db_get_notes(update.effective_user.id)
    if not n:
        return await update.message.reply_text("Пусто 🗒️")
    await update.message.reply_text("\n".join(f"• {i}" for i in n))

async def confirm(update, context):
    if update.effective_user.id != ADMIN_ID:
        return await update.message.reply_text("❌ Только админ")

    uid = int(context.args[0])
    exp = datetime.datetime.now() + datetime.timedelta(days=30)
    db_set_sub(uid, exp.isoformat())

    await context.bot.send_message(uid, f"✅ Подписка до {exp}")
    await update.message.reply_text("Выдано ✅")

async def callback(update, context):
    q = update.callback_query
    await q.answer()
    if q.data == "notes":
        return await q.message.reply_text("/note — добавить\n/notes — список")
    if q.data == "weather":
        return await q.message.reply_text("Напиши город: /weather Москва")
    if q.data == "premium":
        return await q.message.reply_text("Запрос на премиум отправлен ✅")

async def weather_cmd(update, context):
    city = " ".join(context.args)
    if not city:
        return await update.message.reply_text("Пример: `/weather Москва`", parse_mode="Markdown")
    w = await get_weather(city)
    await update.message.reply_text(w)

# ----------- RUN BOT -----------

def main():
    db_init()
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("note", add_note))
    app.add_handler(CommandHandler("notes", list_notes))
    app.add_handler(CommandHandler("confirm", confirm))
    app.add_handler(CommandHandler("weather", weather_cmd))
    app.add_handler(CallbackQueryHandler(callback))

    app.run_polling()

if __name__ == "__main__":
    main()
