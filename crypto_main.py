import ccxt
import time
from datetime import datetime
from telegram import Bot
import asyncio
from crypto_30m import get_ohlcv_30m, calculate_indicators_30m, analyze_signals_30m
from crypto_4h import get_ohlcv_4h, calculate_indicators_4h, analyze_signals_4h
import os
from dotenv import load_dotenv

load_dotenv() 

# === TELEGRAM ===
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
CHAT_ID = os.getenv('CHAT_ID')

if not TELEGRAM_TOKEN or not CHAT_ID:
    raise ValueError("Ошибка чтения TELEGRAM_TOKEN и CHAT_ID из переменных окружения")

async def send_telegram_message(message):
    bot = Bot(token=TELEGRAM_TOKEN)
    await bot.send_message(chat_id=CHAT_ID, text=message)




# === ОСНОВНАЯ ФУНКЦИЯ СОЗДАНИЯ СИГНАЛОВ ===
def check_signal(symbol, timeframe, ohlcv_func, calc_func, analyze_func, interval):
            df = ohlcv_func(symbol)
            if df is None:
                print(f"⚠️ Не удалось получить данные TF = {timeframe}.")
                return None

            df = calc_func(df)
            signal = analyze_func(df)

            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            latest = df.iloc[-1]
            price = latest['close']
            sma = latest['sma_110']
            macd_hist = latest['macd_hist']
            macd_value=latest['macd']

            print(f"[{timestamp}] Цена: {price:.2f}, SMA110: {sma:.2f}, MACD_Hist: {macd_hist:.5f} MACD_Value: {macd_value:.5f}")

            if signal:
                print(f"🔔 СИГНАЛ: {signal} для {symbol}")
                # === ОТПРАВКА В ТЕЛЕГРАМ ===
                message = f"🔔 СИГНАЛ: {signal} для {symbol}\n\nЦена: {price:.2f}\nSMA110: {sma:.2f}\nMACD_Hist: {macd_hist:.5f}\nMACD_Value: {macd_value:.5f}\nВремя: {timestamp}"
                asyncio.run(send_telegram_message(message))
            else:
                print(f"📊 Нет сигнала ({symbol, timeframe})")

            return signal

        
# === СПИСОК ПАР ===
SYMBOLS = ['BTC/USDT', 'ETH/USDT', 'BNB/USDT']

def main():
    print("🚀 Запуск криптобота. Проверка 4h каждые 2 часа, 30m каждые 30 минут...")
    asyncio.run(send_telegram_message("Успешный запуск"))
    last_check_4h = {symbol: 0 for symbol in SYMBOLS}
    last_check_30m = {symbol: 0 for symbol in SYMBOLS}
    while True:
        current_time=time.time()

        for symbol in SYMBOLS:

            # === 4H ===
            if current_time - last_check_4h[symbol] >= 7200: # 7200 = 2 часа
                print (f"\n🔄 Проверка 4H сигнала для {symbol}...")
                check_signal(symbol, '4H', get_ohlcv_4h, calculate_indicators_4h, analyze_signals_4h, 7200)
                last_check_4h[symbol] = current_time

            # === 30m ===
            if current_time - last_check_30m[symbol] >= 1600: # 1800 = 30 минут
                print (f"\n🔄 Проверка 30m сигнала для {symbol}...")
                check_signal(symbol, '30m', get_ohlcv_30m, calculate_indicators_30m, analyze_signals_30m, 1800)
                last_check_30m[symbol] = current_time
        print("Ожидание 10 m")
        time.sleep(360)
    

if __name__ == "__main__":

    main()
