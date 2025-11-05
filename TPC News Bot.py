import os
import requests
import threading
import time
import schedule
from flask import Flask
from openai import OpenAI
from telegram import Bot
from datetime import datetime

# Wczytanie kluczy z env
API_KEY_JBLANKED = os.getenv("API_KEY_JBLANKED")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHANNEL_ID = os.getenv("CHANNEL_ID")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# Inicjalizacja OpenAI i Telegrama
openai_client = OpenAI(api_key=OPENAI_API_KEY)
telegram_bot = Bot(token=TELEGRAM_TOKEN)

app = Flask(__name__)

def get_economic_events():
    url = "https://www.jblanked.com/news/api/mql5/calendar/today/"
    headers = {
        "Authorization": f"Api-Key {API_KEY_JBLANKED}",
        "Content-Type": "application/json"
    }
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        events = response.json()
        filtered = [e for e in events if e.get("strength") in ["Medium", "High"]]
        return filtered
    except Exception as e:
        print("Błąd pobierania danych:", e)
        return []

def analyze_event(event):
    prompt = (
        f"Przeanalizuj wpływ wydarzenia ekonomicznego: {event['Name']} "
        f"({event['Currency']}) o sile {event['strength']}. "
        "Jakie mogą być krótkoterminowe lub długoterminowe skutki dla rynku?"
    )
    try:
        response = openai_client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": prompt}]
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print("Błąd analizy ChatGPT:", e)
        return "Brak analizy z powodu błędu."

def send_to_telegram(message):
    try:
        telegram_bot.send_message(chat_id=CHANNEL_ID, text=message, parse_mode="Markdown")
    except Exception as e:
        print("Błąd wysyłki na Telegram:", e)

def daily_job():
    if datetime.today().weekday() < 5:  # Pon-pt
        events = get_economic_events()
        if not events:
            send_to_telegram("Brak ważnych wydarzeń ekonomicznych na dziś.")
            return
        for event in events:
            analysis = analyze_event(event)
            message = f"*{event['Name']}* ({event['Currency']}) - *{event['strength']}*\n\n{analysis}"
            send_to_telegram(message)
    else:
        print("Weekend, brak wiadomości")

def run_scheduler():
    schedule.every().day.at("07:00").do(daily_job)
    while True:
        schedule.run_pending()
        time.sleep(30)

@app.route("/")
def home():
    return "Bot działa"

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    thread = threading.Thread(target=run_scheduler)
    thread.daemon = True
    thread.start()
    app.run(host="0.0.0.0", port=port)
