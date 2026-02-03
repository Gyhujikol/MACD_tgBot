import os
from datetime import datetime
from telegram import Bot
import asyncio
from dotenv import load_dotenv

load_dotenv()

# === TELEGRAM ===
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
CHAT_ID = os.getenv('CHAT_ID')

if not TELEGRAM_TOKEN or not CHAT_ID:
    raise ValueError("❌ TELEGRAM_TOKEN и CHAT_ID обязательны в .env")

# ✅ Абсолютный путь к файлу
import sys
sys.path.append(os.path.dirname(os.path.abspath(__file__)))  # Добавляем текущую директорию
from moex_4h import Tinkoff4hFetcher  # Теперь можно импортировать

async def send_telegram_message(message):
    bot = Bot(token=TELEGRAM_TOKEN)
    await bot.send_message(chat_id=CHAT_ID, text=message)

def load_tickers():
    """Загружаем тикеры из файла, разделяя по типу"""
    all_tickers = []    
    current_section = None
    
    with open('tickers.txt', 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            
            if line.startswith('#'):
                if 'SHARES' in line.upper():
                    current_section = 'shares'
                elif 'FUTURES' in line.upper():
                    current_section = 'futures'
            elif line and not line.startswith('#'):
                if current_section:
                    all_tickers.append({'ticker':line, 'type': current_section})
    
    return all_tickers

def main():
    print("🚀 Запуск Tinkoff-бота с MACD-стратегией...")

    # Отправляем сообщение о запуске
    asyncio.run(send_telegram_message("Запуск Tinkoff-бота"))

    all_tickers = load_tickers()

    print(f"📋 Загружено тикеров: {len(all_tickers)}")
    print(f"📊 Тикеры: {[t['ticker'] for t in all_tickers]}")

    # Создаем фетчер
    fetcher = Tinkoff4hFetcher()

    # === Собираем статусы ===
    statuses = []
    signals = []

    for instrument in all_tickers:
        ticker = instrument["ticker"]
        instr_type = instrument["type"]

        print(f"\n🔄 Проверка {ticker} ({instr_type})...")

        try:
            # Получаем данные
            data = fetcher.get_4h_data(ticker, days=120, instrument_type=instr_type)

            if not data:
                status = f"❌ {ticker} ({instr_type}) - Нет данных"
                statuses.append(status)
                print(f"❌ Нет данных для {ticker}")
                continue

            # Анализируем сигнал
            signal = data['signal']

            # Формируем статус
            if signal in ["BULLISH", "BEARISH"]:
                status = f"🟢 {ticker} ({instr_type}) - OK"
                statuses.append(status)
                # Добавляем сигнал
                signal_info = {
                    'ticker': ticker,
                    'type': instr_type,
                    'signal_type': 'LONG' if signal == "BULLISH" else 'SHORT',
                    'price': data['current_price'],
                    'time': data['last_candle_time']
                }
                signals.append(signal_info)
            else:
                status = f"⚪ {ticker} ({instr_type}) - OK"
                statuses.append(status)

            print(f"🔔 Сигнал: {signal} для {ticker}")
        except Exception as e:
            error_msg = f"❌ {ticker} ({instr_type}) - Ошибка: {e}"
            statuses.append(error_msg)
            print(error_msg)

    # === ОТПРАВЛЯЕМ СТАТУСЫ ===
    if statuses:
        status_message = "📊 Статусы проверки:\n" + "\n".join(statuses)
        asyncio.run(send_telegram_message(status_message))

    # === ОТПРАВЛЯЕМ СИГНАЛЫ ===
    if signals:
        for sig in signals:
            signal_msg = f"🎯 СИГНАЛ: {sig['signal_type']} {sig['ticker']} ({sig['type']})\n"
            signal_msg += f"💰 Цена: {sig['price']:.2f}\n"
            signal_msg += f"🕒 Время: {sig['time']}"
            asyncio.run(send_telegram_message(signal_msg))
    else:
        asyncio.run(send_telegram_message("📊 Нет новых сигналов"))

    print("\n✅ Проверка завершена")

if __name__ == "__main__":

    main()
