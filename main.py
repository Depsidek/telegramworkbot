import os
import csv
from datetime import datetime, timedelta
from flask import Flask
from threading import Thread
from telegram import Update
from telegram.ext import Updater, CommandHandler, CallbackContext

LOG_FILE = 'work_log.csv'
TOKEN = os.getenv('TELEGRAM_API_TOKEN')

app = Flask('')

@app.route('/')
def home():
    return "Bot běží!"

def save_time(user_id, action, time_str):
    with open(LOG_FILE, 'a', newline='') as f:
        writer = csv.writer(f)
        writer.writerow([user_id, action, time_str])

def start(update: Update, context: CallbackContext):
    update.message.reply_text(
        "Ahoj! Použij /in pro příchod, /out pro odchod, "
        "/settime HH:MM in|out pro nastavení vlastního času, /log pro přehled za posledních 31 dní "
        "a /clearlog pro smazání tvých záznamů."
    )

def in_command(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    save_time(user_id, 'IN', now_str)
    update.message.reply_text(f"Zapsán příchod v {now_str}")

def out_command(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    now = datetime.now()
    now_str = now.strftime('%Y-%m-%d %H:%M:%S')

    if not os.path.exists(LOG_FILE):
        update.message.reply_text("Žádné předchozí záznamy, nejde spočítat odpracovaný čas.")
        save_time(user_id, 'OUT', now_str)
        return

    with open(LOG_FILE, 'r') as f:
        reader = list(csv.reader(f))

    last_in_time = None
    for row in reversed(reader):
        if row[0] == str(user_id) and row[1] == 'IN':
            try:
                last_in_time = datetime.strptime(row[2], '%Y-%m-%d %H:%M:%S')
                break
            except:
                continue

    save_time(user_id, 'OUT', now_str)

    if last_in_time is None:
        update.message.reply_text(f"Zapsán odchod v {now_str}, ale nenašel jsem poslední příchod pro výpočet odpracovaného času.")
        return

    diff = now - last_in_time
    hodiny = diff.seconds // 3600
    minuty = (diff.seconds % 3600) // 60

    update.message.reply_text(f"Zapsán odchod v {now_str}. Odpracováno: {hodiny} hodin a {minuty} minut.")

def settime_command(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    args = context.args
    if len(args) != 2:
        update.message.reply_text("Použití: /settime HH:MM in|out")
        return

    time_part, action = args
    action = action.upper()
    if action not in ['IN', 'OUT']:
        update.message.reply_text("Druhý parametr musí být 'in' nebo 'out'.")
        return

    try:
        datetime.strptime(time_part, '%H:%M')
    except ValueError:
        update.message.reply_text("Čas musí být ve formátu HH:MM (např. 08:30).")
        return

    today = datetime.now().strftime('%Y-%m-%d')
    full_time = f"{today} {time_part}:00"
    save_time(user_id, action, full_time)
    update.message.reply_text(f"Zapsán {action.lower()} v {full_time}")

def log_command(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    if not os.path.exists(LOG_FILE):
        update.message.reply_text("Žádné záznamy.")
        return

    with open(LOG_FILE, 'r') as f:
        reader = csv.reader(f)
        logs = [row for row in reader if row[0] == str(user_id)]

    if not logs:
        update.message.reply_text("Žádné záznamy pro tebe.")
        return

    now = datetime.now()
    threshold = now - timedelta(days=31)

    filtered_logs = []
    for row in logs:
        try:
            log_time = datetime.strptime(row[2], '%Y-%m-%d %H:%M:%S')
            if log_time >= threshold:
                filtered_logs.append(row)
        except:
            continue

    if not filtered_logs:
        update.message.reply_text("Žádné záznamy za posledních 31 dní.")
        return

    msg = f"Tvoje záznamy za posledních 31 dní (celkem {len(filtered_logs)}):\n"
    for row in filtered_logs:
        msg += f"{row[1]}: {row[2]}\n"

    update.message.reply_text(msg)

def clearlog_command(update: Update, context: CallbackContext):
    user_id = str(update.effective_user.id)
    if not os.path.exists(LOG_FILE):
        update.message.reply_text("Log zatím neexistuje, nic nebylo smazáno.")
        return

    with open(LOG_FILE, 'r', newline='') as f:
        reader = csv.reader(f)
        rows = [row for row in reader if row[0] != user_id]

    with open(LOG_FILE, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerows(rows)

    update.message.reply_text("Tvoje záznamy byly smazány.")

def main():
    if not TOKEN:
        print("CHYBA: Není nastaven TELEGRAM_API_TOKEN!")
        return

    server = Thread(target=lambda: app.run(host='0.0.0.0', port=8080))
    server.start()

    updater = Updater(TOKEN)
    dp = updater.dispatcher
    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CommandHandler("in", in_command))
    dp.add_handler(CommandHandler("out", out_command))
    dp.add_handler(CommandHandler("settime", settime_command))
    dp.add_handler(CommandHandler("log", log_command))
    dp.add_handler(CommandHandler("clearlog", clearlog_command))
    updater.start_polling()
    updater.idle()

if __name__ == '__main__':
    main()
