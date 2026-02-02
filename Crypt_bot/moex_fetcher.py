import requests
import pandas as pd
from datetime import datetime, timedelta, timezone
import time
import os

TOKEN = os.getenv('TINKOFF_API_TOKEN')

if not TOKEN:
    raise ValueError("❌ TINKOFF_API_TOKEN не найден в .env")

BASE_URL = "https://invest-public-api.tinkoff.ru/rest/"
HEADERS = {
    "Authorization": f"Bearer {TOKEN}",
    "Content-Type": "application/json",
    "Accept": "application/json"
}

class Tinkoff4hFetcher:
    def __init__(self):
        self.headers = HEADERS.copy()
        self.token = TOKEN

    def _quotation_to_float(self, quotation: dict) -> float:
        """Конвертирует Quotation в float"""
        units = quotation.get('units', '0')
        nano = quotation.get('nano', '0')

        if isinstance(units, str):
            units = int(units) if units.lstrip('-').isdigit() else 0
        if isinstance(nano, str):
            nano = int(nano) if nano.lstrip('-').isdigit() else 0

        return units + nano / 1e9

    def find_figi(self, ticker: str, instrument_type: str = "shares") -> str:
        """Находит FIGI по тикеру"""

        endpoint_map = {
            "shares": "tinkoff.public.invest.api.contract.v1.InstrumentsService/Shares",
            "futures": "tinkoff.public.invest.api.contract.v1.InstrumentsService/Futures",
            "bonds": "tinkoff.public.invest.api.contract.v1.InstrumentsService/Bonds",
            "etfs": "tinkoff.public.invest.api.contract.v1.InstrumentsService/Etfs"
        }

        endpoint = endpoint_map.get(instrument_type, endpoint_map["shares"])
        payload = {"instrument_status": "INSTRUMENT_STATUS_BASE"}

        try:
            response = requests.post(
                BASE_URL + endpoint,
                headers=self.headers,
                json=payload,
                timeout=10
            )

            if response.status_code == 200:
                data = response.json()
                if 'instruments' in data:  
                    for inst in data['instruments']:
                        if inst['ticker'] == ticker:
                            if instrument_type == "shares" and inst.get('classCode') != 'TQBR':
                                continue
                            return inst['figi']

        except Exception as e:
            print(f"❌ Ошибка поиска {ticker}: {e}")

        raise ValueError(f"Инструмент {ticker} не найден")

    def get_4h_data(self, ticker: str, days: int = 120, instrument_type: str = "shares") -> dict:
        print(f"📊 Получаю 4-часовые данные для {ticker}...")

        # 1. Получаем FIGI
        try:
            figi = self.find_figi(ticker, instrument_type)
        except ValueError as e:
            print(f"❌ {e}")
            return None

        # 2. Получаем свечи с пагинацией
        df = self._get_candles_paginated(figi, days)
        if df.empty or len(df) < 2:
            print(f"❌ Недостаточно данных для {ticker} (нужно минимум 2 свечи)")
            return None

        print(f"✅ Получено свечей: {len(df)}")

        # 3. Рассчитываем индикаторы
        df = self._calculate_indicators(df)

        # 4. Формируем сигнал (с учётом предыдущей свечи)
        last_row = df.iloc[-1]
        prev_row = df.iloc[-2]

        signal = self._generate_signal(last_row, prev_row)

        # 5. Формируем результат
        result = {
            'ticker': ticker,
            'figi': figi,
            'current_price': last_row['close'],
            'current_volume': last_row['volume'],
            'sma110': last_row.get('SMA110'),
            'macd': last_row.get('MACD'),
            'macd_signal': last_row.get('MACD_signal'),
            'macd_hist': last_row.get('MACD_hist'),
            'signal': signal,
            'dataframe': df,
            'has_enough_data': len(df) >= 110,
            'last_candle_time': last_row['time'],
            'timestamp': datetime.now(timezone.utc).isoformat()
        }

        return result

    def _get_candles_paginated(self, figi: str, total_days: int) -> pd.DataFrame:
        """Получает свечи с пагинацией"""
        all_candles = []
        chunk_days = 30

        end_time = datetime.now(timezone.utc)
        start_time = end_time - timedelta(days=total_days)

        current_end = end_time
        chunks = []

        while current_end > start_time:
            chunk_start = current_end - timedelta(days=chunk_days)
            if chunk_start < start_time:
                chunk_start = start_time

            chunks.append((chunk_start, current_end))
            current_end = chunk_start

        chunks.reverse()

        for i, (chunk_start, chunk_end) in enumerate(chunks, 1):
            payload = {
                "figi": figi,
                "from": chunk_start.isoformat(),
                "to": chunk_end.isoformat(),
                "interval": "CANDLE_INTERVAL_4_HOUR"
            }

            try:
                response = requests.post(
                    BASE_URL + "tinkoff.public.invest.api.contract.v1.MarketDataService/GetCandles",
                    headers=self.headers,
                    json=payload,
                    timeout=15
                )

                if response.status_code == 200:
                    data = response.json()
                    if 'candles' in data and data['candles']:
                        all_candles.extend(data['candles'])

                time.sleep(0.3)

            except Exception as e:
                print(f"⚠️ Ошибка запроса: {e}")
                continue

        return self._process_candles(all_candles)

    def _process_candles(self, candles: list) -> pd.DataFrame:
        """Обрабатывает свечи"""
        if not candles:
            return pd.DataFrame()

        data = []
        for candle in candles:
            try:
                data.append({
                    'time': candle['time'],
                    'open': self._quotation_to_float(candle['open']),
                    'high': self._quotation_to_float(candle['high']),
                    'low': self._quotation_to_float(candle['low']),
                    'close': self._quotation_to_float(candle['close']),
                    'volume': int(candle['volume']) if isinstance(candle['volume'], str) else candle['volume']
                })
            except:
                continue

        df = pd.DataFrame(data)
        df['time'] = pd.to_datetime(df['time'])
        df = df.sort_values('time').reset_index(drop=True)
        df = df.drop_duplicates('time')

        return df

    def _calculate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """Рассчитывает индикаторы"""
        if df.empty:
            return df

        # SMA110
        if len(df) >= 110:
            df['SMA110'] = df['close'].rolling(window=110, min_periods=110).mean()

        # MACD (12, 26, 9)
        if len(df) >= 26:
            exp12 = df['close'].ewm(span=12, adjust=False).mean()
            exp26 = df['close'].ewm(span=26, adjust=False).mean()
            df['MACD'] = exp12 - exp26
            df['MACD_signal'] = df['MACD'].ewm(span=9, adjust=False).mean()
            df['MACD_hist'] = df['MACD'] - df['MACD_signal']

        return df

    def _generate_signal(self, last_row: pd.Series, prev_row: pd.Series) -> str:
        """Генерирует торговый сигнал с учётом всех критериев"""
        
        # Проверяем, что есть все данные
        required_fields = ['SMA110', 'MACD_hist', 'MACD', 'MACD_signal', 'close']
        for field in required_fields:
            if pd.isna(last_row.get(field)):
                return "NO_DATA"
        
        # Если нет предыдущей строки, не можем проверить пересечение
        if prev_row is None or pd.isna(prev_row.get('MACD_hist')):
            return "INSUFFICIENT_DATA"
        
        # Условия для BUY:
        # 1. Цена выше SMA110
        price_above_sma = last_row['close'] > last_row['SMA110']
        
        # 2. MACD гистограмма пересекает 0 снизу вверх (т.е. предыдущая < 0, текущая > 0)
        hist_crossed_up = prev_row['MACD_hist'] < 0 and last_row['MACD_hist'] > 0
        
        # 3. MACD и Signal линии ниже нуля (рынок внизу)
        macd_lines_below_zero = last_row['MACD'] < 0 and last_row['MACD_signal'] < 0
        
        # Условия для SELL (обратные):
        price_below_sma = last_row['close'] < last_row['SMA110']
        hist_crossed_down = prev_row['MACD_hist'] > 0 and last_row['MACD_hist'] < 0
        macd_lines_above_zero = last_row['MACD'] > 0 and last_row['MACD_signal'] > 0
        
        if price_above_sma and hist_crossed_up and macd_lines_below_zero:
            return "BULLISH"
        elif price_below_sma and hist_crossed_down and macd_lines_above_zero:
            return "BEARISH"
        else:
            return "NEUTRAL"