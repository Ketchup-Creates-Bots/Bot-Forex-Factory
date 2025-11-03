import os
import requests
from bs4 import BeautifulSoup
import telegram
from telegram.error import TelegramError
from apscheduler.schedulers.blocking import BlockingScheduler
from datetime import datetime
from openai import OpenAI

# Pobierz zmienne środowiskowe
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')

if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID or not OPENAI_API_KEY:
    raise Exception("Brak niezbędnych zmiennych środowiskowych: TELEGRAM_TOKEN, TELEGRAM_CHAT_ID, OPENAI_API_KEY")

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
    print(f"Uruchomiono zadanie o {datetime.now()}")
    events = fetch_forexfactory_events()
    if not events:
        send_telegram_message("Brak istotnych wydarzeń medium/high na dzisiaj.")
        return

    full_message = "Kalendarz Forex Factory (medium i high impact) na dziś:\n\n"
    for event in events:
        interpretation = chatgpt_interpret_event(event)
        full_message += f"{interpretation}\n\n---\n\n"

    send_telegram_message(full_message)

if __name__ == "__main__":
    scheduler = BlockingScheduler()
    scheduler.add_job(job, 'cron', hour=7, minute=0)
    print("Bot uruchomiony, czeka na zadania...")
    scheduler.start()
