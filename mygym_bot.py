import telebot
import json
import os
from flask import Flask
from threading import Thread, Timer
import logging
from datetime import datetime
import random
from io import BytesIO
import matplotlib.pyplot as plt

# ---------- Настройки ----------
TOKEN = os.getenv("BOT_TOKEN")
if not TOKEN:
    raise Exception("BOT_TOKEN не задан")

bot = telebot.TeleBot(TOKEN)
app = Flask(__name__)

DATA_FILE = "exercises.json"
user_sessions = {}

logging.basicConfig(level=logging.INFO)

# ---------- Работа с данными ----------
def load_data():
    if not os.path.exists(DATA_FILE):
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump({day: [] for day in
                       ["понедельник","вторник","среда","четверг","пятница","суббота","воскресенье"]},
                      f, ensure_ascii=False, indent=2)
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_data(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

data = load_data()

# ---------- Мотивационные советы ----------
motivation_quotes = [
    "🏃‍♂️ Держись! Каждый день лучше вчера!",
    "💪 Сильный не тот, кто никогда не падает, а кто поднимается!",
    "🔥 Не жди мотивации — действуй, и мотивация появится сама!",
    "🏋️‍♂️ Каждый подход приближает тебя к цели!",
    "⚡ Даже маленький прогресс лучше, чем отсутствие действий!",
    "🏆 Твоя дисциплина — твой успех!",
    "💡 Сегодня ты можешь сделать на один повтор больше, чем вчера!",
    "🌟 Не сравнивай себя с другими, сравни себя с собой вчерашним!",
    "💥 Боль временна, гордость вечна!",
    "🥇 Ты создаёшь свои победы тренировками и упорством!",
    "🏃‍♀️ Маленькие шаги каждый день приводят к большим результатам!",
    "🔥 Не останавливайся, когда тяжело — останавливайся, когда достигнешь цели!",
    "💪 Сила не в том, чтобы никогда не падать, а в том, чтобы каждый раз подниматься!",
    "⚡ Твои усилия сегодня — твоя победа завтра!",
    "🌟 Начни сегодня, чтобы завтра не жалеть!"
]

stickers = [
    "CAACAgIAAxkBAAEIYQtlc8rC5H3kPCE6Mx9R4B0Uo8LskAACFgEAAladvQq5y8D_eMXh2zQE",  # power
    "CAACAgIAAxkBAAEIYQ1lc8rZbWn3IVBymJHxLHzOcvGgCAACIAADrWW8FKkKJj9v1aRgNAQ",  # smile muscle
    "CAACAgIAAxkBAAEIYQ9lc8riHHX7xdP8wojWx9DbMSuOIQACSwADrWW8FBv2u6tLV1IZNAQ",  # run man
    "CAACAgIAAxkBAAEIYRFlc8r8ztyI48r1MBPkE0KZZda2gAACDgADrWW8FKO_8t6XpcPnNAQ",  # fire
]

# ---------- Клавиатуры ----------
def main_menu():
    kb = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.row("🏋️ Режим тренировки", "➕ Добавить тренировку")
    kb.row("📊 Статистика", "🧪 Тестовый режим")
    kb.row("💡 Советы / Мотивация")
    return kb

def cancel_keyboard():
    kb = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.row("↩️ Назад", "❌ Отмена")
    return kb

def motivation_keyboard():
    kb = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.row("💬 Следующий совет", "↩️ Назад")
    return kb

def days_keyboard():
    kb = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.row("📅 Понедельник", "📅 Вторник", "📅 Среда")
    kb.row("📅 Четверг", "📅 Пятница", "📅 Суббота", "📅 Воскресенье")
    kb.row("❌ Отмена")
    return kb

# ---------- Flask ----------
@app.route('/')
def home():
    logging.info(f"Ping received at {datetime.now()}")
    return "Bot is running"

def run_flask():
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))

# ---------- Графики ----------
def generate_progress_chart(chat_id, day_list):
    plt.figure(figsize=(5,3))
    for day in day_list:
        exs = data.get(day, [])
        weights = [sum(e['вес'])/len(e['вес']) if e['вес'] else 0 for e in exs if e['вес']]
        plt.plot(range(len(weights)), weights, label=day.capitalize())
    plt.title("📈 Прогресс по весу")
    plt.xlabel("Подходы")
    plt.ylabel("Вес (кг)")
    plt.legend()
    buf = BytesIO()
    plt.savefig(buf, format='png')
    buf.seek(0)
    bot.send_photo(chat_id, buf)
    buf.close()
    plt.close()

# ---------- Тренировка ----------
def start_training(chat_id):
    user_sessions[chat_id]['mode'] = 'training'
    bot.send_message(chat_id, "Выбери день для тренировки:", reply_markup=days_keyboard())

def training_step(chat_id):
    session = user_sessions[chat_id]
    exercises = session['training_list']
    idx = session['current_exercise']
    if idx >= len(exercises):
        bot.send_message(chat_id, "🎉 Тренировка завершена! Отличная работа!", reply_markup=main_menu())
        session['mode'] = 'main'
        return
    ex = exercises[idx]
    msg_text = f"🔸 {ex['название']} ({ex['тип']})"
    if ex['тип'] == 'силовое':
        if ex['вес']:
            msg_text += f"\nВес: {ex['вес'][-1]} кг, Подходы: {ex['подходы'][-1]}"
    bot.send_message(chat_id, msg_text)
    rest_time = random.randint(90, 180)
    bot.send_message(chat_id, f"⏱ Отдых {rest_time//60} мин {rest_time%60} сек.")
    Timer(rest_time, next_exercise, args=(chat_id,)).start()

def next_exercise(chat_id):
    if chat_id not in user_sessions or user_sessions[chat_id]['mode'] != 'training':
        return
    user_sessions[chat_id]['current_exercise'] += 1
    training_step(chat_id)

# ---------- Основные команды ----------
@bot.message_handler(commands=['start'])
def start(message):
    chat_id = message.chat.id
    user_sessions.setdefault(chat_id, {'mode':'main', 'training_list':[], 'current_exercise':0, 'is_test':False})
    bot.send_message(chat_id, "Привет! Я твой фитнес-помощник 💪", reply_markup=main_menu())

@bot.message_handler(func=lambda m: True)
def main_handler(message):
    chat_id = message.chat.id
    text = message.text
    session = user_sessions.setdefault(chat_id, {'mode':'main', 'training_list':[], 'current_exercise':0, 'is_test':False})

    # Главное меню
    if session['mode'] == 'main':
        if text == "🏋️ Режим тренировки":
            session['mode'] = 'training_select'
            bot.send_message(chat_id, "Выбери день недели для тренировки:", reply_markup=days_keyboard())
        elif text == "➕ Добавить тренировку":
            bot.send_message(chat_id, "Функция добавления тренировок в разработке ⚙️", reply_markup=cancel_keyboard())
        elif text == "📊 Статистика":
            kb = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True)
            kb.row("📊 Простая статистика", "📈 Прогресс с графиками")
            kb.row("↩️ Назад")
            session['mode'] = 'stats'
            bot.send_message(chat_id, "Выберите тип статистики:", reply_markup=kb)
        elif text == "💡 Советы / Мотивация":
            session['mode'] = 'motivation'
            send_motivation(chat_id)
        elif text == "🧪 Тестовый режим":
            session['mode'] = 'test'
            session['is_test'] = True
            bot.send_message(chat_id, "Тестовый режим активирован. Все данные не сохраняются.", reply_markup=main_menu())
        return

    # Мотивация
    if session['mode'] == 'motivation':
        if text == "💬 Следующий совет":
            send_motivation(chat_id)
        elif text == "↩️ Назад":
            session['mode'] = 'main'
            bot.send_message(chat_id, "Главное меню:", reply_markup=main_menu())
        return

    # Статистика
    if session['mode'] == 'stats':
        if text == "📊 Простая статистика":
            msg = "📊 Статистика:\n"
            for day, exs in data.items():
                msg += f"\n📅 {day.capitalize()}:\n"
                if not exs:
                    msg += "  — Нет упражнений\n"
                    continue
                for e in exs:
                    msg += f"  🔸 {e['название']} ({e['тип']})\n"
                    if e['подходы']:
                        msg += f"     Подходы: {e['подходы']}  Вес: {e['вес']}\n"
            bot.send_message(chat_id, msg, reply_markup=main_menu())
        elif text == "📈 Прогресс с графиками":
            generate_progress_chart(chat_id, list(data.keys()))
        elif text == "↩️ Назад":
            session['mode'] = 'main'
            bot.send_message(chat_id, "Главное меню:", reply_markup=main_menu())
        return

def send_motivation(chat_id):
    quote = random.choice(motivation_quotes)
    bot.send_message(chat_id, quote, reply_markup=motivation_keyboard())
    sticker = random.choice(stickers)
    bot.send_sticker(chat_id, sticker)

# ---------- Запуск ----------
def run_bot():
    bot.polling(none_stop=True)

if __name__ == "__main__":
    Thread(target=run_flask).start()
    Thread(target=run_bot).start()
