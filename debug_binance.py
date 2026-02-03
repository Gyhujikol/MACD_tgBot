#!/usr/bin/env python3
import ccxt
import pandas as pd
import sys
import os

print("=" * 50)
print("🔍 DEBUG BINANCE API IN GITHUB ACTIONS")
print("=" * 50)

# 1. Окружение
print("\n1. 🐍 ПРОВЕРКА ОКРУЖЕНИЯ:")
print(f"Python version: {sys.version}")
print(f"Current dir: {os.getcwd()}")
print(f"Files: {os.listdir('.')}")
if os.path.exists('tickers.txt'):
    with open('tickers.txt') as f:
        print(f"\n📄 tickers.txt:\n{f.read()}")
else:
    print("\n❌ tickers.txt не найден!")

# 2. Тест Binance
print("\n2. 🔗 ТЕСТ BINANCE API")
try:
    exchange = ccxt.binance({
        'timeout': 30000,
        'enableRateLimit': True,
        'options': {'defaultType': 'spot'}
    })
    print("✅ Exchange создан")

    markets = exchange.load_markets()
    print(f"✅ Загружено {len(markets)} пар")

    # Ищем BTC/USDT
    btc_usdt = [s for s in markets if 'BTC' in s and 'USDT' in s]
    print(f"BTC/USDT пары: {len(btc_usdt)}")
    if btc_usdt:
        symbol = btc_usdt[0]
        print(f"Пробуем: {symbol}")
        ohlcv = exchange.fetch_ohlcv(symbol, '4h', limit=2)
        print(f"✅ Получено {len(ohlcv)} свечей")
        df = pd.DataFrame(ohlcv, columns=['ts','o','h','l','c','v'])
        df['ts'] = pd.to_datetime(df['ts'], unit='ms')
        print(df[['ts','c']].to_string(index=False))
    else:
        print("⚠️ BTC/USDT не найдены")

except Exception as e:
    print(f"💥 ОШИБКА: {type(e).__name__}: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "=" * 50)
print("✅ ДЕБАГ ЗАВЕРШЕН")
