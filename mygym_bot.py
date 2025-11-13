# mygym_bot.py
import os, json, random, logging
from threading import Timer, Lock
from datetime import datetime
from io import BytesIO
from flask import Flask, request
import telebot
import matplotlib.pyplot as plt

# ---------- Настройки ----------
TOKEN = os.getenv("BOT_TOKEN")
if not TOKEN:
    raise RuntimeError("BOT_TOKEN не задан")
bot = telebot.TeleBot(TOKEN)
app = Flask(__name__)
DATA_FILE = "exercises.json"
DATA_LOCK = Lock()
user_sessions = {}  # сессии пользователей

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')

# ---------- Загрузка / сохранение данных ----------
def load_data():
    with DATA_LOCK:
        if not os.path.exists(DATA_FILE):
            default = {
                "понедельник": [], "вторник": [], "среда": [],
                "четверг": [], "пятница": [], "суббота": [], "воскресенье": []
            }
            with open(DATA_FILE, "w", encoding="utf-8") as f:
                json.dump(default, f, ensure_ascii=False, indent=2)
            return default
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            try:
                return json.load(f)
            except Exception:
                logging.warning("JSON поврежден, восстанавливаем пустой шаблон")
                default = {
                    "понедельник": [], "вторник": [], "среда": [],
                    "четверг": [], "пятница": [], "суббота": [], "воскресенье": []
                }
                return default

def save_data(d):
    with DATA_LOCK:
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(d, f, ensure_ascii=False, indent=2)

data = load_data()

# ---------- Иконки / стикеры / мотивация ----------
MOTIVATION_QUOTES = [
    "🔥 Начни прямо сейчас!", "💪 Каждый день сильнее!",
    "🏋️‍♂️ Твое тело — твой дух", "⚡ Боль — это слабость, уходящая прочь",
    "🥇 Маленькие усилия каждый день — большой результат"
]

STICKERS = [
    "CAACAgIAAxkBAAEIYQtlc8rC5H3kPCE6Mx9R4B0Uo8LskAACFgEAAladvQq5y8D_eMXh2zQE"
]

# ---------- Клавиатуры ----------
def main_menu(): 
    kb = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.row("🏋️ Режим тренировки", "➕ Добавить тренировку")
    kb.row("📊 Статистика", "🧪 Тест")
    kb.row("💡 Советы / Мотивация")
    return kb

def days_keyboard(add_cancel=True):
    kb = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.row("📅 Понедельник", "📅 Вторник", "📅 Среда")
    kb.row("📅 Четверг", "📅 Пятница", "📅 Суббота", "📅 Воскресенье")
    if add_cancel:
        kb.row("↩️ Назад", "❌ Отмена")
    return kb

def cancel_keyboard():
    kb = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.row("↩️ Назад", "❌ Отмена")
    return kb

# ---------- Сессии ----------
def get_session(chat_id):
    if chat_id not in user_sessions:
        user_sessions[chat_id] = {
            'mode':'main', 'training_list':[], 'current_exercise':0,
            'is_test':False, 'temp_data': {}
        }
    return user_sessions[chat_id]

# ---------- Тренировка ----------
def start_training(chat_id, day):
    sess = get_session(chat_id)
    sess['mode'] = 'training'
    sess['current_exercise'] = 0
    sess['training_list'] = []
    source_list = data[day]
    for e in source_list:
        sess['training_list'].append(e.copy())
    if not sess['training_list']:
        bot.send_message(chat_id, "Нет упражнений. Добавь их.", reply_markup=main_menu())
        sess['mode']='main'
        return
    bot.send_message(chat_id, f"🔥 Начинаем тренировку: {day}. Упражнений: {len(sess['training_list'])}")
    send_exercise(chat_id)

def send_exercise(chat_id):
    sess = get_session(chat_id)
    idx = sess['current_exercise']
    if idx >= len(sess['training_list']):
        bot.send_message(chat_id, "🎉 Тренировка завершена!", reply_markup=main_menu())
        sess['mode']='main'
        return
    ex = sess['training_list'][idx]
    msg = f"🔸 {ex['название']} ({ex['тип']})"
    bot.send_message(chat_id, msg)
    if ex.get('media_type')=='photo':
        bot.send_photo(chat_id, ex['media_id'])
    elif ex.get('media_type')=='video':
        bot.send_video(chat_id, ex['media_id'])
    kb = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.row("➡️ Далее")
    bot.send_message(chat_id, "Нажми ➡️ Далее после упражнения", reply_markup=kb)

def next_exercise(chat_id):
    sess = get_session(chat_id)
    if sess['mode']!='training': return
    idx = sess['current_exercise']
    if idx >= len(sess['training_list']):
        bot.send_message(chat_id, "🎉 Тренировка завершена!", reply_markup=main_menu())
        sess['mode']='main'
        return
    # Таймер отдыха
    rest_sec = random.randint(90,180)
    bot.send_message(chat_id, f"⏱ Отдых {rest_sec//60} мин {rest_sec%60} сек.")
    t = Timer(rest_sec, finish_rest, args=(chat_id,))
    t.start()

def finish_rest(chat_id):
    sess = get_session(chat_id)
    sess['current_exercise']+=1
    if sess['current_exercise'] < len(sess['training_list']):
        send_exercise(chat_id)
    else:
        bot.send_message(chat_id, "🎉 Тренировка завершена!", reply_markup=main_menu())
        sess['mode']='main'

# ---------- Добавление упражнений ----------
def start_add(chat_id):
    sess = get_session(chat_id)
    sess['mode']='add_select_day'
    bot.send_message(chat_id,"На какой день добавить?", reply_markup=days_keyboard())

def handle_add_day(chat_id,text):
    sess = get_session(chat_id)
    day = text.replace("📅 ","").lower()
    if day not in data: return
    sess['add_day']=day
    sess['mode']='add_wait_name'
    bot.send_message(chat_id,"Название упражнения?", reply_markup=cancel_keyboard())

def handle_add_name(chat_id,text):
    sess = get_session(chat_id)
    if text.lower() in ["↩️ назад","❌ отмена"]:
        sess['mode']='main'
        bot.send_message(chat_id,"Отмена", reply_markup=main_menu())
        return
    sess['add_name']=text
    sess['mode']='add_wait_type'
    bot.send_message(chat_id,"Силовое? да/нет", reply_markup=cancel_keyboard())

def handle_add_type(chat_id,text):
    sess = get_session(chat_id)
    is_power=text.lower() in ["да","д","yes","y"]
    sess['add_type']="силовое" if is_power else "кардио"
    sess['mode']='add_wait_media'
    bot.send_message(chat_id,"Отправь фото/видео или 'нет'", reply_markup=cancel_keyboard())

def handle_add_media(chat_id,message):
    sess = get_session(chat_id)
    media_id=None
    media_type=None
    if message.content_type=='photo':
        media_id=message.photo[-1].file_id
        media_type='photo'
    elif message.content_type=='video':
        media_id=message.video.file_id
        media_type='video'
    elif message.text.lower()=='нет':
        media_id=None
        media_type=None
    new_ex={"название":sess['add_name'],"тип":sess['add_type'],
            "media_type":media_type,"media_id":media_id,"подходы":[],"вес":[]}
    day=sess['add_day']
    if not sess['is_test']:
        data[day].append(new_ex)
        save_data(data)
    sess['mode']='main'
    bot.send_message(chat_id,f"✅ Упражнение '{new_ex['название']}' добавлено в {day}", reply_markup=main_menu())

# ---------- Мотивация ----------
def send_motivation(chat_id):
    quote=random.choice(MOTIVATION_QUOTES)
    bot.send_message(chat_id,quote)
    try:
        bot.send_sticker(chat_id,random.choice(STICKERS))
    except: pass

# ---------- Статистика ----------
def send_stats(chat_id):
    msg="📊 Статистика:\n"
    for day,exs in data.items():
        msg+=f"\n📅 {day.capitalize()}:\n"
        if not exs:
            msg+=" — Нет упражнений\n"
            continue
        for e in exs:
            msg+=f" 🔸 {e['название']} ({e['тип']}) Подходы:{e['подходы']} Вес:{e['вес']}\n"
    bot.send_message(chat_id,msg, reply_markup=main_menu())

# ---------- Основной хендлер ----------
@bot.message_handler(func=lambda m: True, content_types=['text','photo','video'])
def all_messages(message):
    chat_id=message.chat.id
    text=message.text if message.text else ""
    sess=get_session(chat_id)
    # Главное меню
    if sess['mode']=='main':
        if text=="🏋️ Режим тренировки": sess['mode']='training_select'; bot.send_message(chat_id,"Выбери день:", reply_markup=days_keyboard(False)); return
        if text=="➕ Добавить тренировку": start_add(chat_id); return
        if text=="📊 Статистика": send_stats(chat_id); return
        if text=="💡 Советы / Мотивация": send_motivation(chat_id); return
    # Выбор дня тренировки
    if sess['mode']=='training_select':
        day=text.replace("📅 ","").lower()
        if day in data: start_training(chat_id,day); return
    # Тренировка — кнопка Далее
    if sess['mode']=='training' and text=="➡️ Далее": next_exercise(chat_id); return
    # Добавление
    if sess['mode']=='add_select_day': handle_add_day(chat_id,text); return
    if sess['mode']=='add_wait_name': handle_add_name(chat_id,text); return
    if sess['mode']=='add_wait_type': handle_add_type(chat_id,text); return
    if sess['mode']=='add_wait_media': handle_add_media(chat_id,message); return
    bot.send_message(chat_id,"Выбери из меню", reply_markup=main_menu())

# ---------- Flask endpoints ----------
@app.route('/', methods=['GET','HEAD'])
def index(): return "Bot is running",200

@app.route('/'+TOKEN, methods=['POST'])
def webhook(): 
    json_str=request.get_data().decode('utf-8')
    update=telebot.types.Update.de_json(json_str)
    bot.process_new_updates([update])
    return "OK",200

if __name__=="__main__":
    port=int(os.environ.get("PORT",10000))
    app.run(host="0.0.0.0", port=port)
