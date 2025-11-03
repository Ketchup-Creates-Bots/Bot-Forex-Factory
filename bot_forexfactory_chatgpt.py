import os
import requests
from bs4 import BeautifulSoup
import telegram
from telegram.ext import Updater, CommandHandler
from telegram.error import TelegramError
from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime
from openai import OpenAI
from flask import Flask
import threading

# Pobierz zmienne środowiskowe
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')

if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID or not OPENAI_API_KEY:
    raise Exception("Brak zmiennych środowiskowych TELEGRAM_TOKEN, TELEGRAM_CHAT_ID lub OPENAI_API_KEY")

bot = telegram.Bot(token=TELEGRAM_TOKEN)
client = OpenAI(api_key=OPENAI_API_KEY)

def fetch_forexfactory_events():
    url = "https://www.forexfactory.com/calendar.php"
    response = requests.get(url)
    soup = BeautifulSoup(response.content, 'html.parser')

    events = []
    rows = soup.find_all('tr', class_='calendar__row')
    for row in rows:
        impact_elem = row.find('td', class_='calendar__impact')
        if impact_elem:
            impact_icon = impact_elem.find('span', class_='impact-icon')
            if not impact_icon:
                continue
            if 'impact-high' in impact_icon['class']:
                impact = 'High'
            elif 'impact-medium' in impact_icon['class']:
                impact = 'Medium'
            else:
                continue
            event_title_elem = row.find('td', class_='calendar__event')
            if event_title_elem:
                event_title = event_title_elem.get_text(strip=True)
                events.append({'title': event_title, 'impact': impact})
    return events

def chatgpt_interpret_event(event):
    prompt = (
        f"Jesteś ekspertem rynków finansowych. Oto wydarzenie gospodarcze:\n"
        f"Tytuł wydarzenia: \"{event['title']}\" (wpływ: {event['impact']})\n\n"
        "Proszę, zinterpretuj sens tego wydarzenia w kontekście rynku walutowego i finansowego. "
        "Wyjaśnij, co to oznacza, jak może wpłynąć na dolara i rynki oraz, jeśli są trudne terminy, podaj krótkie wyjaśnienie (np. co to jest CPI). "
        "Napisz odpowiedź w języku polskim, zwięźle i jasno."
    )
    response = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[
            {"role": "system", "content": "Jesteś pomocnym asystentem finansowym."},
            {"role": "user", "content": prompt}
        ],
        max_tokens=300,
        temperature=0.7,
    )
    return response.choices[0].message.content.strip()

def send_telegram_message(text):
    try:
        bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=text)
    except TelegramError as e:
        print(f"Błąd wysyłki do Telegrama: {e}")

def job():
    print(f"Wywołanie zadania o {datetime.now()}")
    events = fetch_forexfactory_events()
    if not events:
        send_telegram_message("Brak istotnych wydarzeń medium/high na dzisiaj.")
        return
    full_message = "Kalendarz Forex Factory (medium i high impact):\n\n"
    for event in events:
        interpretation = chatgpt_interpret_event(event)
        full_message += f"{interpretation}\n\n---\n\n"
    send_telegram_message(full_message)

def start(update, context):
    update.message.reply_text("Bot jest aktywny! Możesz przetestować jego działanie.")

# --- Flask serwer do Render ---
app = Flask(__name__)

@app.route('/')
def home():
    return "✅ Bot działa poprawnie na Render!", 200

def run_flask():
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)


if __name__ == "__main__":
    updater = Updater(TELEGRAM_TOKEN)
    dispatcher = updater.dispatcher

    # Dodaj komendę /start do testów
    dispatcher.add_handler(CommandHandler("start", start))

    # Uruchom je od razu (test natychmiastowy)
    job()

    # Zaplanuj powtarzanie zadań (codziennie o 7 rano)
    scheduler = BackgroundScheduler()
    scheduler.add_job(job, 'cron', hour=7, minute=0)
    scheduler.start()

    print("Bot startuje (polling)...")
    updater.start_polling()
    updater.idle()

    # Uruchom Flask w osobnym wątku, żeby Render widział port
    threading.Thread(target=run_flask).start()

    print("🤖 Bot startuje (polling)...")
    updater.start_polling()
    updater.idle()




