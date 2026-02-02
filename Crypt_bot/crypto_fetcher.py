import ccxt
import pandas as pd
from ta.trend import MACD
import time
from datetime import datetime, timezone
import warnings
warnings.filterwarnings('ignore')

class CryptoFetcher:
    def __init__(self):
        self.exchange = ccxt.binance({
            'timeout': 30000,
            'enableRateLimit': True,
            'options': {
                'defaultType': 'spot'
            }
        })
    
    def get_4h_data(self, symbol: str, days: int = 120) -> dict:
        print(f"📊 Получаю 4-часовые данные для {symbol}...")
        
        # 1. Получаем свечи
        df = self._get_candles(symbol, days)
        if df.empty or len(df) < 2:
            print(f"❌ Недостаточно данных для {symbol} (получено {len(df)} свечей)")
            return None
        
        print(f"✅ Получено свечей: {len(df)}")
        
        # 2. Рассчитываем индикаторы
        df = self._calculate_indicators(df)
        
        # 3. Формируем сигнал
        signal = self._generate_signal(df)
        
        # 4. Формируем результат
        last_row = df.iloc[-1]
        
        result = {
            'symbol': symbol,
            'current_price': last_row['close'],
            'current_volume': last_row['volume'],
            'sma110': last_row.get('sma_110'),
            'macd': last_row.get('macd'),
            'macd_signal': last_row.get('macd_signal'),
            'macd_hist': last_row.get('macd_hist'),
            'signal': signal,
            'has_enough_data': len(df) >= 110,
            'last_candle_time': last_row['timestamp'].strftime('%Y-%m-%d %H:%M:%S'),
            'timestamp': datetime.now(timezone.utc).isoformat()
        }
        
        return result
    
    def _get_candles(self, symbol: str, days: int) -> pd.DataFrame:
        """Получает свечи за указанное количество дней"""
        try:
            # Вычисляем timestamp для 'days' дней назад
            since = self.exchange.parse8601(
                (datetime.now(timezone.utc) - pd.Timedelta(days=days)).isoformat()
            )
            
            # Получаем все свечи за период
            all_ohlcv = []
            while True:
                ohlcv = self.exchange.fetch_ohlcv(
                    symbol=symbol,
                    timeframe='4h',
                    since=since,
                    limit=1000
                )
                
                if not ohlcv:
                    break
                    
                all_ohlcv.extend(ohlcv)
                
                # Обновляем since для следующего запроса
                since = ohlcv[-1][0] + 1
                
                # Если получили меньше 1000 свечей, значит это конец данных
                if len(ohlcv) < 1000:
                    break
                    
                # Пауза для rate limiting
                time.sleep(0.5)
            
            return self._process_candles(all_ohlcv)
            
        except Exception as e:
            print(f"❌ Ошибка получения данных для {symbol}: {e}")
            return pd.DataFrame()
    
    def _process_candles(self, candles: list) -> pd.DataFrame:
        """Обрабатывает сырые свечи в DataFrame"""
        if not candles:
            return pd.DataFrame()
        
        data = []
        for candle in candles:
            try:
                data.append({
                    'timestamp': pd.to_datetime(candle[0], unit='ms', utc=True),
                    'open': float(candle[1]),
                    'high': float(candle[2]),
                    'low': float(candle[3]),
                    'close': float(candle[4]),
                    'volume': float(candle[5])
                })
            except Exception as e:
                print(f"⚠️ Ошибка обработки свечи: {e}")
                continue
        
        if not data:
            return pd.DataFrame()
            
        df = pd.DataFrame(data)
        df = df.sort_values('timestamp').reset_index(drop=True)
        df = df.drop_duplicates('timestamp').reset_index(drop=True)
        
        return df
    
    def _calculate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """Рассчитывает технические индикаторы"""
        if df.empty:
            return df
        
        # SMA110
        if len(df) >= 110:
            df['sma_110'] = df['close'].rolling(window=110, min_periods=1).mean()
        else:
            df['sma_110'] = pd.NA
        
        # MACD (12, 26, 9)
        if len(df) >= 26:
            try:
                macd_indicator = MACD(
                    df['close'], 
                    window_slow=26, 
                    window_fast=12, 
                    window_sign=9
                )
                df['macd'] = macd_indicator.macd()
                df['macd_signal'] = macd_indicator.macd_signal()
                df['macd_hist'] = macd_indicator.macd_diff()
            except Exception as e:
                print(f"⚠️ Ошибка расчета MACD: {e}")
                df['macd'] = pd.NA
                df['macd_signal'] = pd.NA
                df['macd_hist'] = pd.NA
        else:
            df['macd'] = pd.NA
            df['macd_signal'] = pd.NA
            df['macd_hist'] = pd.NA
        
        return df
    
    def _generate_signal(self, df: pd.DataFrame) -> str:
        """Генерирует торговый сигнал на основе индикаторов"""
        if df.empty or len(df) < 2:
            return "INSUFFICIENT_DATA"
        
        last_row = df.iloc[-1]
        prev_row = df.iloc[-2]
        
        # Проверяем наличие необходимых данных
        required = ['sma_110', 'macd_hist', 'macd']
        for field in required:
            if pd.isna(last_row.get(field)) or pd.isna(prev_row.get(field)):
                return "NO_DATA"
        
        price = last_row['close']
        sma = last_row['sma_110']
        macd_hist = last_row['macd_hist']
        macd_hist_prev = prev_row['macd_hist']
        macd_value = prev_row['macd']
        
        # BUY сигнал
        buy_conditions = (
            price > sma and
            macd_hist_prev <= 0 and
            macd_hist > 0 and
            macd_value <= 0
        )
        
        # SELL сигнал
        sell_conditions = (
            price < sma and
            macd_hist_prev >= 0 and
            macd_hist < 0 and
            macd_value >= 0
        )
        
        if buy_conditions:
            return "BUY SIGNAL"
        elif sell_conditions:
            return "SELL SIGNAL"
        else:
            return "NEUTRAL"