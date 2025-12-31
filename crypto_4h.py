import ccxt
import pandas as pd
from ta.trend import MACD  # Только это нужно
import time
from datetime import datetime
from telegram import Bot
import asyncio


# === НАСТРОЙКИ 4H ===
TIMEFRAME = '4h'
SMA_LENGTH = 110
MACD_FAST = 12
MACD_SLOW = 26
MACD_SIGNAL = 9


# === ФУНКЦИЯ ПОЛУЧЕНИЯ ДАННЫХ ===
def get_ohlcv_4h(symbol, limit = 200):
    exchange = ccxt.binance({
        'timeout': 10000,
        'enableRateLimit': True,
    })
    try:
        ohlcv = exchange.fetch_ohlcv(symbol, TIMEFRAME, limit=limit)
        df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
        return df
    except Exception as e:
        print(f"❌ Ошибка получения данных (4h): {e}")
        return None

# === РАСЧЁТ ИНДИКАТОРОВ ===
def calculate_indicators_4h(df):
    df['sma_110'] = df['close'].rolling(SMA_LENGTH).mean()
    macd_indicator = MACD(df['close'], window_slow=MACD_SLOW, window_fast=MACD_FAST, window_sign=MACD_SIGNAL)
    df['macd'] = macd_indicator.macd()
    df['macd_signal'] = macd_indicator.macd_signal()
    df['macd_hist'] = macd_indicator.macd_diff()
    return df

# === АНАЛИЗ СИГНАЛОВ ===
def analyze_signals_4h(df):
    latest = df.iloc[-1]
    previous = df.iloc[-2]

    price = latest['close']
    sma = latest['sma_110']
    macd_hist = latest['macd_hist']
    macd_hist_prev = previous['macd_hist']
    macd_value = previous['macd']

    # === УСЛОВИЯ СИГНАЛОВ ===
    if pd.isna(sma) or pd.isna(macd_hist) or pd.isna(macd_hist_prev):
        return None

    # BUY: цена > SMA и MACD гистограмма растёт (переходит в плюс или растёт)
    if price > sma and macd_hist > 0 and macd_hist_prev <= 0 and macd_value <= 0:
        return "🟢 BUY SIGNAL (4h)"
    # SELL: цена < SMA и MACD гистограмма падает (переходит в минус или падает)
    elif price < sma and macd_hist < 0 and macd_hist_prev >= 0 and macd_value >= 0:
        return "🔴 SELL SIGNAL (4h)"

    return None

