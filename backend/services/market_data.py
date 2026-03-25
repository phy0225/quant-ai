"""
Market data service — fetches real price data via yfinance with local cache.
No API key required.
"""
from __future__ import annotations
import json, math
from datetime import datetime, timedelta, date
from pathlib import Path

CACHE_DIR = Path(__file__).parent.parent / ".market_cache"
CACHE_TTL_HOURS = 6  # 缓存有效期，美股收盘后 6 小时内数据不变

def _cache_path(symbol: str) -> Path:
    CACHE_DIR.mkdir(exist_ok=True)
    return CACHE_DIR / f"{symbol.upper()}.json"

def _is_cache_valid(symbol: str) -> bool:
    p = _cache_path(symbol)
    if not p.exists():
        return False
    age = datetime.utcnow() - datetime.utcfromtimestamp(p.stat().st_mtime)
    return age < timedelta(hours=CACHE_TTL_HOURS)

def _load_cache(symbol: str) -> dict | None:
    try:
        return json.loads(_cache_path(symbol).read_text())
    except Exception:
        return None

def _save_cache(symbol: str, data: dict):
    try:
        _cache_path(symbol).write_text(json.dumps(data))
    except Exception:
        pass

def _calc_rsi(closes: list[float], period: int = 14) -> float:
    if len(closes) < period + 1:
        return 50.0
    deltas = [closes[i] - closes[i-1] for i in range(1, len(closes))]
    gains  = [d for d in deltas if d > 0]
    losses = [-d for d in deltas if d < 0]
    avg_gain = sum(gains[-period:]) / period if gains else 0
    avg_loss = sum(losses[-period:]) / period if losses else 1e-9
    rs = avg_gain / avg_loss
    return round(100 - 100 / (1 + rs), 2)

def _calc_macd(closes: list[float]) -> tuple[float, float]:
    """Returns (macd_line, signal_line)."""
    def ema(data, n):
        k = 2 / (n + 1)
        e = data[0]
        for p in data[1:]:
            e = p * k + e * (1 - k)
        return e
    if len(closes) < 26:
        return 0.0, 0.0
    ema12 = ema(closes[-12:], 12)
    ema26 = ema(closes[-26:], 26)
    macd  = ema12 - ema26
    signal = macd * 0.2  # simplified signal
    return round(macd, 4), round(signal, 4)

def _calc_bollinger(closes: list[float], period: int = 20) -> tuple[float, float, float]:
    """Returns (upper, mid, lower)."""
    if len(closes) < period:
        c = closes[-1]
        return c * 1.02, c, c * 0.98
    window = closes[-period:]
    mid = sum(window) / period
    std = math.sqrt(sum((x - mid)**2 for x in window) / period)
    return round(mid + 2*std, 4), round(mid, 4), round(mid - 2*std, 4)

def fetch_market_snapshot(symbol: str) -> dict:
    """
    Fetch price data for a symbol and compute technical indicators.
    Returns a dict with price summary and indicators.
    Falls back to empty dict if yfinance unavailable.
    """
    # Check cache first
    if _is_cache_valid(symbol):
        cached = _load_cache(symbol)
        if cached:
            print(f"[market_data] cache hit: {symbol}")
            return cached

    try:
        import yfinance as yf
        ticker = yf.Ticker(symbol)
        hist   = ticker.history(period="3mo", interval="1d", auto_adjust=True)

        if hist.empty:
            print(f"[market_data] no data for {symbol}")
            return {}

        closes  = hist["Close"].tolist()
        volumes = hist["Volume"].tolist()
        dates   = [str(d.date()) for d in hist.index]

        current_price = round(closes[-1], 2)
        prev_close    = round(closes[-2], 2) if len(closes) > 1 else current_price
        price_change  = round((current_price - prev_close) / prev_close * 100, 2)

        ma20 = round(sum(closes[-20:]) / min(20, len(closes)), 2)
        ma50 = round(sum(closes[-50:]) / min(50, len(closes)), 2)
        rsi  = _calc_rsi(closes)
        macd_line, macd_signal = _calc_macd(closes)
        bb_upper, bb_mid, bb_lower = _calc_bollinger(closes)

        avg_vol_5 = int(sum(volumes[-5:]) / min(5, len(volumes)))
        avg_vol_20 = int(sum(volumes[-20:]) / min(20, len(volumes)))
        vol_ratio = round(volumes[-1] / avg_vol_20, 2) if avg_vol_20 > 0 else 1.0

        # 52-week high/low
        high_52w = round(max(hist["High"].tolist()), 2)
        low_52w  = round(min(hist["Low"].tolist()), 2)

        # Trend signal
        trend = "BULLISH" if current_price > ma20 > ma50 else \
                "BEARISH"  if current_price < ma20 < ma50 else "NEUTRAL"

        snapshot = {
            "symbol": symbol,
            "fetched_at": datetime.utcnow().isoformat(),
            "current_price": current_price,
            "prev_close": prev_close,
            "price_change_pct": price_change,
            "high_52w": high_52w,
            "low_52w": low_52w,
            "ma20": ma20,
            "ma50": ma50,
            "rsi": rsi,
            "macd": macd_line,
            "macd_signal": macd_signal,
            "bb_upper": bb_upper,
            "bb_mid": bb_mid,
            "bb_lower": bb_lower,
            "volume_today": int(volumes[-1]),
            "volume_avg_20d": avg_vol_20,
            "volume_ratio": vol_ratio,
            "trend": trend,
            # Last 5 closes for context
            "recent_closes": [round(c, 2) for c in closes[-5:]],
            "recent_dates":  dates[-5:],
        }

        _save_cache(symbol, snapshot)
        print(f"[market_data] fetched {symbol}: price={current_price} RSI={rsi} trend={trend}")
        return snapshot

    except ImportError:
        print("[market_data] yfinance not installed, run: pip install yfinance")
        return {}
    except Exception as e:
        print(f"[market_data] fetch failed for {symbol}: {e}")
        return {}


def format_technical_context(snapshot: dict) -> str:
    """Format market snapshot into a readable string for LLM prompt injection."""
    if not snapshot:
        return "No real-time market data available."

    sym = snapshot.get("symbol", "")
    return f"""
Real-time market data for {sym} (as of {snapshot.get('fetched_at','')[:10]}):

Price: ${snapshot['current_price']} ({'+' if snapshot['price_change_pct'] >= 0 else ''}{snapshot['price_change_pct']}% today)
52-week range: ${snapshot['low_52w']} - ${snapshot['high_52w']}
Recent closes: {snapshot['recent_closes']} ({', '.join(snapshot['recent_dates'])})

Technical Indicators:
- MA20: ${snapshot['ma20']} | MA50: ${snapshot['ma50']}
- RSI(14): {snapshot['rsi']} {'(OVERBOUGHT>70)' if snapshot['rsi'] > 70 else '(OVERSOLD<30)' if snapshot['rsi'] < 30 else '(NEUTRAL)'}
- MACD: {snapshot['macd']} | Signal: {snapshot['macd_signal']} {'(BULLISH crossover)' if snapshot['macd'] > snapshot['macd_signal'] else '(BEARISH crossover)'}
- Bollinger Bands: Upper=${snapshot['bb_upper']} | Mid=${snapshot['bb_mid']} | Lower=${snapshot['bb_lower']}
  Price position: {'Near upper band (overbought)' if snapshot['current_price'] > snapshot['bb_upper'] * 0.98 else 'Near lower band (oversold)' if snapshot['current_price'] < snapshot['bb_lower'] * 1.02 else 'Within bands'}
- Volume ratio vs 20d avg: {snapshot['volume_ratio']}x {'(HIGH volume)' if snapshot['volume_ratio'] > 1.5 else '(LOW volume)' if snapshot['volume_ratio'] < 0.5 else '(normal)'}

Overall trend: {snapshot['trend']}
""".strip()


def format_fundamental_context(snapshot: dict) -> str:
    """Format for fundamental analyst — price as reference only."""
    if not snapshot:
        return "No market reference data available."
    sym = snapshot.get("symbol","")
    return f"""
Market reference for {sym}:
Current price: ${snapshot['current_price']} ({'+' if snapshot['price_change_pct'] >= 0 else ''}{snapshot['price_change_pct']}% today)
52-week range: ${snapshot['low_52w']} - ${snapshot['high_52w']}
Price vs MA50: {'Above MA50 (positive momentum)' if snapshot['current_price'] > snapshot['ma50'] else 'Below MA50 (negative momentum)'}
""".strip()


def format_sentiment_context(snapshot: dict) -> str:
    """Format for sentiment analyst — volume and momentum signals."""
    if not snapshot:
        return "No market data available."
    sym = snapshot.get("symbol","")
    rsi = snapshot.get("rsi", 50)
    vol_ratio = snapshot.get("volume_ratio", 1.0)
    sentiment = "EXTREME GREED" if rsi > 75 else \
                "GREED"         if rsi > 60 else \
                "FEAR"          if rsi < 40 else \
                "EXTREME FEAR"  if rsi < 25 else "NEUTRAL"
    return f"""
Market sentiment indicators for {sym}:
RSI-based sentiment: {sentiment} (RSI={rsi})
Volume activity: {vol_ratio}x average ({'unusually high activity' if vol_ratio > 1.5 else 'low interest' if vol_ratio < 0.5 else 'normal activity'})
Price momentum: {snapshot['trend']}
Price change today: {'+' if snapshot['price_change_pct'] >= 0 else ''}{snapshot['price_change_pct']}%
""".strip()
