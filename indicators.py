"""
indicators.py - Базовые индикаторы (упрощённая версия)
"""
import time
import logging
from typing import Optional, Dict, List, Tuple
from collections import defaultdict
import httpx

logger = logging.getLogger(__name__)

class CandleStorage:
    def __init__(self):
        self.candles: Dict[str, Dict[str, list]] = defaultdict(lambda: defaultdict(list))
    
    def add_candle(self, pair: str, tf: str, candle: dict):
        self.candles[pair][tf].append(candle)
        if len(self.candles[pair][tf]) > 500:
            self.candles[pair][tf] = self.candles[pair][tf][-500:]
    
    def get_candles(self, pair: str, tf: str) -> List[dict]:
        return self.candles[pair].get(tf, [])

CANDLES = CandleStorage()

class PriceCache:
    def __init__(self, ttl: int = 30):
        self.cache = {}
        self.ttl = ttl
    
    def get(self, pair: str):
        if pair in self.cache:
            price, volume, cached_at = self.cache[pair]
            if time.time() - cached_at < self.ttl:
                return price, volume
        return None
    
    def set(self, pair: str, price: float, volume: float):
        self.cache[pair] = (price, volume, time.time())
    
    def clear_old(self):
        now = time.time()
        self.cache = {k: v for k, v in self.cache.items() if now - v[2] < self.ttl}

PRICE_CACHE = PriceCache()

# ==================== API FUNCTIONS ====================
async def fetch_price(client: httpx.AsyncClient, pair: str) -> Optional[Tuple[float, float]]:
    """Получить цену с Binance"""
    cached = PRICE_CACHE.get(pair)
    if cached:
        return cached
    
    try:
        url = f"https://api.binance.com/api/v3/ticker/24hr?symbol={pair.upper()}"
        resp = await client.get(url, timeout=5.0)
        resp.raise_for_status()
        data = resp.json()
        price = float(data["lastPrice"])
        volume = float(data["volume"])
        
        PRICE_CACHE.set(pair, price, volume)
        return price, volume
    except Exception as e:
        logger.error(f"Error fetching {pair}: {e}")
        return None

async def fetch_candles_binance(pair: str, tf: str, limit: int = 100):
    """Получение свечей с Binance"""
    try:
        async with httpx.AsyncClient() as client:
            tf_map = {"1h": "1h", "4h": "4h", "1d": "1d"}
            interval = tf_map.get(tf, "1h")
            
            url = f"https://api.binance.com/api/v3/klines"
            params = {
                "symbol": pair,
                "interval": interval,
                "limit": limit
            }
            
            response = await client.get(url, params=params, timeout=10.0)
            response.raise_for_status()
            
            klines = response.json()
            candles = []
            
            for kline in klines:
                candle = {
                    't': kline[0] / 1000,
                    'o': float(kline[1]),
                    'h': float(kline[2]),
                    'l': float(kline[3]),
                    'c': float(kline[4]),
                    'v': float(kline[5])
                }
                candles.append(candle)
            
            return candles
            
    except Exception as e:
        logger.error(f"Error fetching candles {pair} {tf}: {e}")
        return None

# ==================== БАЗОВЫЕ ИНДИКАТОРЫ ====================
def calculate_rsi(closes: List[float], period: int = 14) -> Optional[float]:
    """Расчёт RSI"""
    if len(closes) < period + 1:
        return None
    
    gains = []
    losses = []
    for i in range(1, len(closes)):
        change = closes[i] - closes[i-1]
        gains.append(max(0, change))
        losses.append(max(0, -change))
    
    if len(gains) < period:
        return None
    
    avg_gain = sum(gains[-period:]) / period
    avg_loss = sum(losses[-period:]) / period
    
    if avg_loss == 0:
        return 100.0
    
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))

def calculate_ema(values: List[float], period: int) -> Optional[float]:
    """Exponential Moving Average"""
    if len(values) < period:
        return None
    
    k = 2 / (period + 1)
    ema = values[0]
    for value in values[1:]:
        ema = value * k + ema * (1 - k)
    return ema

# Совместимость со старым кодом
def analyze_signal(pair: str) -> Optional[Dict]:
    """Заглушка для совместимости - теперь используем professional_analyzer"""
    return None

def quick_screen(pair: str) -> bool:
    """Быстрый скрининг - для совместимости"""
    candles = CANDLES.get_candles(pair, "1h")
    return len(candles) >= 50
