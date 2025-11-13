# mygym_bot.py
import os
import json
import logging
import random
from io import BytesIO
from datetime import datetime
from threading import Timer, Lock
from flask import Flask, request
import telebot
import matplotlib.pyplot as plt

# ---------- Настройки ----------
TOKEN = os.getenv("BOT_TOKEN")
if not TOKEN:
    raise RuntimeError("BOT_TOKEN не задан в переменных окружения")

bot = telebot.TeleBot(TOKEN, parse_mode=None)
app = Flask(__name__)

DATA_FILE = "exercises.json"
DATA_LOCK = Lock()
user_sessions = {}

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')

# ---------- Загрузка/сохранение данных ----------
def load_data():
    with DATA_LOCK:
        if not os.path.exists(DATA_FILE):
            default = {day: [] for day in ["понедельник","вторник","среда","четверг","пятница","суббота","воскресенье"]}
            with open(DATA_FILE,"w",encoding="utf-8") as f: json.dump(default,f,ensure_ascii=False,indent=2)
            return default
        with open(DATA_FILE,"r",encoding="utf-8") as f:
            try: return json.load(f)
            except Exception:
                default = {day: [] for day in ["понедельник","вторник","среда","четверг","пятница","суббота","воскресенье"]}
                with open(DATA_FILE,"w",encoding="utf-8") as f2: json.dump(default,f2,ensure_ascii=False,indent=2)
                return default

def save_data(d):
    with DATA_LOCK:
        with open(DATA_FILE,"w",encoding="utf-8") as f: json.dump(d,f,ensure_ascii=False,indent=2)

data = load_data()

# ---------- Интерфейс ----------
MOTIVATION_QUOTES = [
    "🔥 Не жди идеального момента — начни сейчас!","💪 Каждый день ты становишься сильнее!",
    "🏋️ Твое тело — отражение твоего духа.","⚡ Боль — это слабость, покидающая тело.",
    "🥇 Успех — это сумма маленьких усилий, повторяемых каждый день.","🚀 Перестань мечтать, начни действовать!",
    "💥 Никогда не сдавайся. Сегодня трудно — завтра будет легче.","🌟 Сделай то, что другие не хотят, и будешь жить так, как другие не могут.",
    "🔥 Даже если упал — поднимись и сделай еще один подход!","🏃‍♂️ Не сравнивай себя с другими — сравнивай себя с собой вчерашним.",
    "⚡ Консистентность важнее интенсивности — тренируйся регулярно.","🎯 Ставь маленькие цели — и поднимай планку постепенно."
]

STICKERS = [
    "CAACAgIAAxkBAAEIYQtlc8rC5H3kPCE6Mx9R4B0Uo8LskAACFgEAAladvQq5y8D_eMXh2zQE",
    "CAACAgIAAxkBAAEIYQ1lc8rZbWn3IVBymJHxLHzOcvGgCAACIAADrWW8FKkKJj9v1aRgNAQ",
    "CAACAgIAAxkBAAEIYQ9lc8riHHX7xdP8wojWx9DbMSuOIQACSwADrWW8FBv2u6tLV1IZNAQ"
]

def main_menu():
    kb = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.row("🏋️ Режим тренировки","➕ Добавить тренировку")
    kb.row("📊 Статистика","🧪 Тестовый режим")
    kb.row("💡 Советы / Мотивация")
    return kb

def days_keyboard(add_cancel=False):
    kb = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.row("📅 Понедельник","📅 Вторник","📅 Среда")
    kb.row("📅 Четверг","📅 Пятница","📅 Суббота","📅 Воскресенье")
    if add_cancel:
        kb.row("↩️ Назад","❌ Отмена")
    return kb

def cancel_keyboard():
    kb = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.row("↩️ Назад","❌ Отмена")
    return kb

def motivation_keyboard():
    kb = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.row("💬 Следующий совет","🎁 Еще совет")
    kb.row("↩️ Назад")
    return kb

def stats_keyboard():
    kb = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.row("📊 Простая статистика","📈 С графиками")
    kb.row("↩️ Назад")
    return kb

# ---------- Графики ----------
def generate_progress_chart(chat_id, days):
    plt.figure(figsize=(6,3))
    plotted=False
    for day in days:
        exs = data.get(day,[])
        y=[]
        for e in exs:
            if e.get('вес'):
                try: y.append(float(e['вес'][-1]))
                except: y.append(0)
        if y:
            plt.plot(range(1,len(y)+1),y,marker='o',label=day.capitalize())
            plotted=True
    plt.title("📈 Прогресс по весу")
    plt.xlabel("Порядок упражнений")
    plt.ylabel("Вес (кг)")
    if plotted:
        buf=BytesIO()
        plt.tight_layout()
        plt.savefig(buf,format='png')
        buf.seek(0)
        bot.send_photo(chat_id,buf)
        buf.close()
    else:
        bot.send_message(chat_id,"Нет данных для графиков.",reply_markup=main_menu())
    plt.close()

# ---------- Сессии ----------
def get_session(chat_id):
    if chat_id not in user_sessions:
        user_sessions[chat_id] = {'mode':'main','training_list':[],'current_exercise':0,'is_test':False,'temp_data':{}}
    return user_sessions[chat_id]

# ---------- Тренировка ----------
def start_training_session(chat_id, day):
    sess = get_session(chat_id)
    sess['mode']='training'
    sess['current_exercise']=0
    sess['training_list']=[]
    source_list = sess['temp_data'].get('data_day') if sess['is_test'] else data.get(day,[])
    for e in source_list: sess['training_list'].append(e.copy())
    if not sess['training_list']:
        bot.send_message(chat_id,"В этот день нет упражнений. Добавь их в разделе 'Добавить тренировку'.",reply_markup=main_menu())
        sess['mode']='main'
        return
    bot.send_message(chat_id,f"🔥 Начинаем тренировку: {day.capitalize()}. Упражнений: {len(sess['training_list'])}")
    # Показываем первое упражнение
    training_step(chat_id)

def training_step(chat_id):
    sess = get_session(chat_id)
    if sess['mode'] != 'training': return
    idx = sess['current_exercise']
    exercises = sess['training_list']
    if idx >= len(exercises):
        bot.send_message(chat_id,"🎉 Тренировка завершена! Отличная работа!",reply_markup=main_menu())
        sess['mode']='main'
        return
    ex = exercises[idx]
    text = f"🔸 {ex.get('название','Без названия')} ({ex.get('тип','—')})"
    if ex.get('media_type')=='photo' and ex.get('media_id'): bot.send_photo(chat_id,ex['media_id'])
    if ex.get('media_type')=='video' and ex.get('media_id'): bot.send_video(chat_id,ex['media_id'])
    kb=telebot.types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.row("⏭ Далее")
    bot.send_message(chat_id,text,reply_markup=kb)

def proceed_next_exercise(chat_id):
    sess = get_session(chat_id)
    if sess['mode'] != 'training': return
    idx = sess['current_exercise']
    exercises = sess['training_list']
    if idx >= len(exercises):
        bot.send_message(chat_id,"🎉 Тренировка завершена! Отличная работа!",reply_markup=main_menu())
        sess['mode']='main'
        return
    # Таймер отдыха
    rest_sec = random.randint(90,180)
    bot.send_message(chat_id,f"⏱ Отдых {rest_sec//60} мин {rest_sec%60} сек.")
    t = Timer(rest_sec, auto_next_exercise,args=(chat_id,))
    t.daemon=True
    t.start()
    sess['_last_timer']=t

def auto_next_exercise(chat_id):
    sess = get_session(chat_id)
    if sess['mode'] != 'training': return
    sess['current_exercise']+=1
    if sess['current_exercise'] < len(sess['training_list']):
        next_e = sess['training_list'][sess['current_exercise']]
        bot.send_message(chat_id,f"🏋️ Переходим к следующему упражнению: {next_e.get('название','—')}")
        training_step(chat_id)
    else:
        bot.send_message(chat_id,"🎉 Тренировка завершена! Ты молодец!",reply_markup=main_menu())
        sess['mode']='main'
        if not sess['is_test']: save_data(data)

# ---------- Добавление упражнений ----------
def start_add_flow(chat_id):
    sess=get_session(chat_id)
    sess['mode']='add_select_day'
    bot.send_message(chat_id,"📅 На какой день добавить упражнение?",reply_markup=days_keyboard(add_cancel=True))

def handle_add_day(chat_id, day_text):
    day = day_text.lower().replace("📅 ","").strip()
    sess=get_session(chat_id)
    if day not in data:
        bot.send_message(chat_id,"Неверный день. Главное меню.",reply_markup=main_menu())
        sess['mode']='main'
        return
    sess['mode']='add_wait_name'
    sess['add_day']=day
    bot.send_message(chat_id,f"Введи название упражнения для {day}:",reply_markup=cancel_keyboard())

def handle_add_name(chat_id,name_text):
    sess=get_session(chat_id)
    if not name_text or name_text.lower() in ["❌ отмена","↩️ назад"]:
        sess['mode']='main'
        bot.send_message(chat_id,"Отмена добавления.",reply_markup=main_menu())
        return
    sess['add_name']=name_text
    sess['mode']='add_wait_type'
    bot.send_message(chat_id,"Это силовое упражнение? (да/нет)",reply_markup=cancel_keyboard())

def handle_add_type(chat_id,text):
    sess=get_session(chat_id)
    is_power=text.lower() in ['да','д','yes','y']
    sess['add_type']='силовое' if is_power else 'кардио'
    sess['mode']='add_wait_media'
    bot.send_message(chat_id,"Пришли фото/видео или 'нет', чтобы пропустить.",reply_markup=cancel_keyboard())

def handle_add_media(chat_id,message):
    sess=get_session(chat_id)
    media_id=None
    media_type=None
    if message.content_type=='photo':
        media_id=message.photo[-1].file_id
        media_type='photo'
    elif message.content_type=='video':
        media_id=message.video.file_id
        media_type='video'
    elif message.text and message.text.lower()=='нет':
        media_id=None
        media_type=None
    else:
        bot.send_message(chat_id,"Не распознал медиа. Фото/видео или 'нет'.")
        return
    new_ex={"название":sess.get('add_name'),"тип":sess.get('add_type'),"media_type":media_type,"media_id":media_id,"подходы":[],"вес":[]}
    day=sess.get('add_day')
    if not sess.get('is_test',False):
        data[day].append(new_ex)
        save_data(data)
    else:
        sess.setdefault('temp_data',{})
        sess['temp_data'].setdefault('data_day',data.get(day,[]).copy())
        sess['temp_data']['data_day'].append(new_ex)
    sess['mode']='main'
    bot.send_message(chat_id,f"✅ Упражнение '{new_ex['название']}' добавлено в {day}.",reply_markup=main_menu())

# ---------- Статистика ----------
def send_simple_stats(chat_id):
    lines=["📊 Твоя статистика:"]
    for day,exs in data.items():
        lines.append(f"\n📅 {day.capitalize()}:")
        if not exs:
            lines.append("  — Нет упражнений")
            continue
        for e in exs:
            part=f"  🔸 {e.get('название','—')} ({e.get('тип','—')})"
            if e.get('подходы'): part+=f"  Подходы: {e.get('подходы')}  Вес: {e.get('вес')}"
            lines.append(part)
    bot.send_message(chat_id,"\n".join(lines),reply_markup=main_menu())

# ---------- Мотивация ----------
def send_motivation_once(chat_id):
    quote=random.choice(MOTIVATION_QUOTES)
    bot.send_message(chat_id,quote,reply_markup=motivation_keyboard())
    try: bot.send_sticker(chat_id,random.choice(STICKERS))
    except: pass

# ---------- Handlers ----------
@bot.message_handler(commands=['start'])
def cmd_start(message):
    sess=get_session(message.chat.id)
    sess['mode']='main'
    sess['is_test']=False
    bot.send_message(message.chat.id,"Привет! Я твой фитнес-бот. Выбери действие:",reply_markup=main_menu())

@bot.message_handler(func=lambda m: True, content_types=['text','photo','video'])
def all_messages_handler(message):
    chat_id=message.chat.id
    text=message.text.strip() if message.text else None
    sess=get_session(chat_id)

    if text and text.lower()=="/exit_test":
        sess['is_test']=False
        sess['mode']='main'
        sess['temp_data']={}
        bot.send_message(chat_id,"Выход из тестового режима.",reply_markup=main_menu())
        return

    # main menu
    if sess['mode']=='main':
        if text=="🏋️ Режим тренировки":
            sess['mode']='training_select'
            bot.send_message(chat_id,"Выбери день:",reply_markup=days_keyboard())
            return
        if text=="➕ Добавить тренировку":
            start_add_flow(chat_id)
            return
        if text=="📊 Статистика":
            sess['mode']='stats'
            bot.send_message(chat_id,"Выбери тип статистики:",reply_markup=stats_keyboard())
            return
        if text=="🧪 Тестовый режим":
            sess['is_test']=True
            sess['mode']='main'
            bot.send_message(chat_id,"Тестовый режим активирован.",reply_markup=main_menu())
            return
        if text=="💡 Советы / Мотивация":
            sess['mode']='motivation'
            send_motivation_once(chat_id)
            return
        bot.send_message(chat_id,"Выбери действие из меню.",reply_markup=main_menu())
        return

    if sess['mode']=='training_select':
        chosen=text.lower().replace("📅 ","") if text else ""
        if chosen in data:
            start_training_session(chat_id,chosen)
        else:
            bot.send_message(chat_id,"Неверный день.",reply_markup=days_keyboard())
        return

    if sess['mode']=='training' and text=="⏭ Далее":
        proceed_next_exercise(chat_id)
        return

    # Add flow
    if sess['mode']=='add_select_day':
        handle_add_day(chat_id,text)
        return
    if sess['mode']=='add_wait_name':
        handle_add_name(chat_id,text)
        return
    if sess['mode']=='add_wait_type':
        handle_add_type(chat_id,text)
        return
    if sess['mode']=='add_wait_media':
        handle_add_media(chat_id,message)
        return

    # stats
    if sess['mode']=='stats':
        if text=="📊 Простая статистика":
            send_simple_stats(chat_id)
            sess['mode']='main'
            return
        if text=="📈 С графиками":
            generate_progress_chart(chat_id,list(data.keys()))
            sess['mode']='main'
            return
        if text=="↩️ Назад":
            sess['mode']='main'
            bot.send_message(chat_id,"Главное меню:",reply_markup=main_menu())
            return

    # motivation
    if sess['mode']=='motivation':
        if text in ["💬 Следующий совет","🎁 Еще совет"]:
            send_motivation_once(chat_id)
            return
        if text=="↩️ Назад":
            sess['mode']='main'
            bot.send_message(chat_id,"Главное меню:",reply_markup=main_menu())
            return

    bot.send_message(chat_id,"Я тебя не понял.",reply_markup=main_menu())

# ---------- Flask webhook ----------
@app.route('/'+TOKEN,methods=['POST'])
def receive_update():
    json_str=request.get_data().decode('utf-8')
    update=telebot.types.Update.de_json(json_str)
    bot.process_new_updates([update])
    return "OK",200

@app.route('/',methods=['GET','HEAD'])
def index():
    try:
        url=os.getenv('APP_URL') or f"https://{os.getenv('RENDER_SERVICE_NAME','mygymbot2')}.onrender.com"
        webhook_url=url.rstrip('/')+'/'+TOKEN
        bot.remove_webhook()
        bot.set_webhook(url=webhook_url)
        logging.info("Webhook set to %s",webhook_url)
    except Exception as e:
        logging.exception("Ошибка установки webhook: %s",e)
    logging.info("Ping received at %s",datetime.utcnow().isoformat())
    return "Bot is running",200

# ---------- Запуск ----------
if __name__=='__main__':
    port=int(os.environ.get("PORT",10000))
    logging.info("Starting Flask on port %s",port)
    app.run(host='0.0.0.0',port=port)
