import os
import sys
import time
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


# Абсолютный путь для импорта
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(current_dir)

try:
    from crypto_fetcher import CryptoFetcher
except ImportError as e:
    print(f"❌ Ошибка импорта: {e}")
    print(f"📁 Текущая директория: {os.getcwd()}")
    print(f"📁 Путь к скрипту: {__file__}")
    sys.exit(1)

async def send_telegram_message(message):
    bot = Bot(token=TELEGRAM_TOKEN)
    await bot.send_message(chat_id=CHAT_ID, text=message)


# === ЗАГРУЗКА ТИКЕРОВ ИЗ ФАЙЛА ===
def load_crypto_tickers():
    """Загружаем крипто-тикеры из файла"""
    tickers = []
    try:
        # Используем правильный путь
        tickers_path = os.path.join(current_dir, 'tickers.txt')
        print(f"📁 Ищу файл tickers.txt по пути: {tickers_path}")
        
        with open(tickers_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#'):
                    tickers.append(line)
    except FileNotFoundError:
        print(f"⚠️ Файл tickers.txt не найден по пути: {tickers_path}")
        print(f"📁 Содержимое папки {current_dir}:")
        try:
            for file in os.listdir(current_dir):
                print(f"  - {file}")
        except:
            pass
        return []
    
    if not tickers:
        print("⚠️ Файл tickers.txt пуст или содержит только комментарии")
    
    print(f"✅ Загружено {len(tickers)} тикеров")
    return tickers





async def main():
    print("🚀 Запуск криптобота.")

    await send_telegram_message("✅ Запуск Crypto-бота")

    tickers = load_crypto_tickers()
    
    if not tickers:
        await send_telegram_message("❌ В файле tickers.txt нет криптопар для проверки")
        return

    print(f"📋 Загружено криптопар: {len(tickers)}")
    print(f"📊 Пары: {tickers}")

    # Создаем фетчер
    fetcher = CryptoFetcher()
    # === Собираем статусы ===
    statuses = []
    signals = []

    for symbol in tickers:
        print(f"\n🔄 Проверка {symbol}...")

        try:
            # Получаем данные
            data = fetcher.get_4h_data(symbol, days=120)

            if not data:
                status = f"❌ {symbol} - Нет данных"
                statuses.append(status)
                print(f"❌ Нет данных для {symbol}")
                continue

            # Анализируем сигнал
            signal = data['signal']

            # Формируем статус
            if signal in ["BUY SIGNAL", "SELL SIGNAL"]:
                status = f"🟢 {symbol} - OK"
                statuses.append(status)
                # Добавляем сигнал
                signal_info = {
                    'symbol': symbol,
                    'signal_type': 'BUY' if signal == "BUY SIGNAL" else 'SELL',
                    'price': data['current_price'],
                    'sma': data['sma110'],
                    'macd_hist': data['macd_hist'],
                    'time': data['last_candle_time']
                }
                signals.append(signal_info)
            elif signal == "NEUTRAL":
                status = f"⚪ {symbol} - OK"
                statuses.append(status)
            else:
                status = f"⚪ {symbol} - OK ({signal})"
                statuses.append(status)

            print(f"🔔 Сигнал: {signal} для {symbol}")
            
        except Exception as e:
            error_msg = f"❌ {symbol} - Ошибка: {str(e)[:100]}"
            statuses.append(error_msg)
            print(error_msg)
            
        # Небольшая пауза между запросами
        time.sleep(1)

    # === ОТПРАВЛЯЕМ СТАТУСЫ ===
    if statuses:
        status_message = "📊 Статусы проверки крипты:\n" + "\n".join(statuses)
        await send_telegram_message(status_message)

    # === ОТПРАВЛЯЕМ СИГНАЛЫ ===
    if signals:
        for sig in signals:
            signal_msg = f"🎯 КРИПТО СИГНАЛ: {sig['signal_type']} {sig['symbol']}\n"
            signal_msg += f"💰 Цена: {sig['price']:.2f}\n"
            signal_msg += f"📊 SMA110: {sig['sma']:.2f}\n"
            signal_msg += f"📈 MACD Hist: {sig['macd_hist']:.5f}\n"
            signal_msg += f"🕒 Время: {sig['time']}"
            await send_telegram_message(signal_msg)
    else:
        await send_telegram_message("📊 Нет крипто-сигналов")

    print(f"\n✅ Проверка завершена. Проверено: {len(tickers)}, Сигналов: {len(signals)}")

if __name__ == "__main__":
    asyncio.run(main())