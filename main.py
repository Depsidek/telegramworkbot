import os
import csv
from datetime import datetime, timedelta
from flask import Flask
from threading import Thread
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import Updater, CommandHandler, CallbackContext, MessageHandler, Filters

LOG_FILE = 'work_log.csv'
TOKEN = os.getenv('TELEGRAM_API_TOKEN')

app = Flask('')

@app.route('/')
def home():
    return "Bot běží!"

def save_log_row(user_id, date, arrival=None, leave=None, worked=None):
    logs = []

    # Načti existující záznamy
    if os.path.exists(LOG_FILE):
        with open(LOG_FILE, 'r', newline='') as f:
            logs = list(csv.reader(f))

    # Zkontroluj, jestli existuje záznam pro dnešní den
    updated = False
    for i, row in enumerate(logs):
        if row[0] == str(user_id) and row[1] == date:
            if arrival:
                row[2] = arrival
            if leave:
                row[3] = leave
            if worked:
                row[4] = worked
            logs[i] = row
            updated = True
            break

    if not updated:
        logs.append([str(user_id), date, arrival or "", leave or "", worked or ""])

    # Zapiš zpět
    with open(LOG_FILE, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerows(logs)

def start_keyboard():
    keyboard = [
        [KeyboardButton("🟢 Příchod"), KeyboardButton("🔴 Odchod")],
        [KeyboardButton("📅 Zobrazit log"), KeyboardButton("🧼 Smazat log")],
        [KeyboardButton("🕰️ Ruční zápis času")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def handle_buttons(update: Update, context: CallbackContext):
    text = update.message.text
    if text == "🟢 Příchod":
        handle_arrival(update, context)
    elif text == "🔴 Odchod":
        handle_departure(update, context)
    elif text == "📅 Zobrazit log":
        show_log(update, context)
    elif text == "🧼 Smazat log":
        clear_log(update, context)
    elif text == "🕰️ Ruční zápis času":
        update.message.reply_text("Napiš čas a typ (např. 08:00 příchod nebo 16:00 odchod).", reply_markup=start_keyboard())
        return
    else:
        # zpracování ručního zápisu času ve formátu HH:MM příchod/odchod
        parts = text.strip().split()
        if len(parts) == 2:
            time_part, action_part = parts
            action_part = action_part.lower()
            if action_part in ['příchod', 'odchod']:
                try:
                    datetime.strptime(time_part, '%H:%M')
                    handle_manual_time(update, context, time_part, action_part)
                    return
                except ValueError:
                    pass
        update.message.reply_text("Nevím co s tím. Použij tlačítka nebo napiš čas ve formátu HH:MM příchod/odchod.", reply_markup=start_keyboard())

def handle_manual_time(update: Update, context: CallbackContext, time_str, action):
    user_id = update.effective_user.id
    date = datetime.now().strftime('%Y-%m-%d')
    time_full = time_str + ":00"
    
    # Načti aktuální záznamy
    logs = []
    if os.path.exists(LOG_FILE):
        with open(LOG_FILE, 'r', newline='') as f:
            logs = list(csv.reader(f))

    updated = False
    for i, row in enumerate(logs):
        if row[0] == str(user_id) and row[1] == date:
            if action == 'příchod':
                row[2] = time_full
            elif action == 'odchod':
                row[3] = time_full
            # pokud máme oba časy, spočítej odpracovaný čas
            if row[2] and row[3]:
                try:
                    t1 = datetime.strptime(f"{date} {row[2]}", '%Y-%m-%d %H:%M:%S')
                    t2 = datetime.strptime(f"{date} {row[3]}", '%Y-%m-%d %H:%M:%S')
                    diff = t2 - t1
                    hours = diff.seconds // 3600
                    minutes = (diff.seconds % 3600) // 60
                    row[4] = f"{hours}h {minutes}m"
                except:
                    pass
            logs[i] = row
            updated = True
            break
    if not updated:
        if action == 'příchod':
            logs.append([str(user_id), date, time_full, "", ""])
        else:
            logs.append([str(user_id), date, "", time_full, ""])
    with open(LOG_FILE, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerows(logs)

    update.message.reply_text(f"Zapsán {action} v {time_str}", reply_markup=start_keyboard())

def handle_arrival(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    now = datetime.now()
    date = now.strftime('%Y-%m-%d')
    time_str = now.strftime('%H:%M:%S')
    save_log_row(user_id, date, arrival=time_str)
    update.message.reply_text(f"Zapsán příchod v {time_str}", reply_markup=start_keyboard())

def handle_departure(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    now = datetime.now()
    date = now.strftime('%Y-%m-%d')
    time_str = now.strftime('%H:%M:%S')

    arrival_time = None
    if os.path.exists(LOG_FILE):
        with open(LOG_FILE, 'r') as f:
            reader = csv.reader(f)
            for row in reader:
                if row[0] == str(user_id) and row[1] == date and row[2]:
                    try:
                        arrival_time = datetime.strptime(f"{date} {row[2]}", '%Y-%m-%d %H:%M:%S')
                        break
                    except:
                        continue

    if arrival_time:
        diff = now - arrival_time
        hours = diff.seconds // 3600
        minutes = (diff.seconds % 3600) // 60
        worked = f"{hours}h {minutes}m"
        save_log_row(user_id, date, leave=time_str, worked=worked)
        update.message.reply_text(f"Zapsán odchod v {time_str}. Odpracováno: {worked}", reply_markup=start_keyboard())
    else:
        save_log_row(user_id, date, leave=time_str)
        update.message.reply_text(f"Zapsán odchod v {time_str}. (Příchod nebyl zaznamenán)", reply_markup=start_keyboard())

def show_log(update: Update, context: CallbackContext):
    user_id = str(update.effective_user.id)
    if not os.path.exists(LOG_FILE):
        update.message.reply_text("Žádné záznamy.", reply_markup=start_keyboard())
        return

with open(LOG_FILE, 'r') as f:
    reader = csv.reader(f)
    logs = [row for row in reader if row[0] == user_id]

if not logs:
    update.message.reply_text("Žádné záznamy.", reply_markup=start_keyboard())
    return

threshold = datetime.now() - timedelta(days=31)
msg = "📅 Záznamy za posledních 31 dní:\n\n"

for row in logs:
    try:
        row_date = datetime.strptime(row[1], '%Y-%m-%d')
        if row_date >= threshold:
            msg += f"{row[1]} | Příchod: {row[2]} | Odchod: {row[3]} | Odpracováno: {row[4]}\n"
    except:
        continue


    update.message.reply_text(msg, reply_markup=start_keyboard())

def clear_log(update: Update, context: CallbackContext):
    user_id = str(update.effective_user.id)
    if not os.path.exists(LOG_FILE):
        update.message.reply_text("Log neexistuje.", reply_markup=start_keyboard())
        return

    with open(LOG_FILE, 'r') as f:
        rows = [row for row in csv.reader(f) if row[0] != user_id]

    with open(LOG_FILE, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerows(rows)

    update.message.reply_text("Tvůj log byl smazán.", reply_markup=start_keyboard())

def main():
    if not TOKEN:
        print("CHYBA: Není nastaven TELEGRAM_API_TOKEN!")
        return

    server = Thread(target=lambda: app.run(host='0.0.0.0', port=8080))
    server.start()

    updater = Updater(TOKEN)
    dp = updater.dispatcher
    dp.add_handler(MessageHandler(Filters.text & ~Filters.command, handle_buttons))
    dp.add_handler(CommandHandler("start", handle_buttons))
    updater.start_polling()
    updater.idle()

if __name__ == '__main__':
    main()
