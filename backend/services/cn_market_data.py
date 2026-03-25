"""A股行情数据 — AKShare，同步函数统一放线程池执行，不阻塞事件循环"""
from __future__ import annotations
import json, math
from datetime import datetime, timedelta
from pathlib import Path

CACHE_DIR = Path(__file__).parent.parent / ".cn_market_cache"
CACHE_TTL_HOURS = 4


def _normalize_symbol(symbol: str) -> str:
    """sz000629 / SH600519 / 000629 → 000629"""
    s = symbol.strip().upper()
    for prefix in ("SZ", "SH", "BJ"):
        if s.startswith(prefix):
            s = s[len(prefix):]
            break
    return s


def _cache_path(symbol: str) -> Path:
    CACHE_DIR.mkdir(exist_ok=True)
    return CACHE_DIR / f"{symbol}_snapshot.json"


def _is_cache_valid(symbol: str) -> bool:
    p = _cache_path(symbol)
    if not p.exists():
        return False
    return datetime.now() - datetime.fromtimestamp(p.stat().st_mtime) < timedelta(hours=CACHE_TTL_HOURS)


def _calc_rsi(closes, period=14):
    if len(closes) < period + 1:
        return 50.0
    deltas = [closes[i] - closes[i-1] for i in range(1, len(closes))]
    gains  = [d for d in deltas[-period:] if d > 0]
    losses = [-d for d in deltas[-period:] if d < 0]
    avg_g = sum(gains) / period if gains else 0
    avg_l = sum(losses) / period if losses else 1e-9
    return round(100 - 100 / (1 + avg_g / avg_l), 2)


def _calc_macd(closes):
    def ema(data, n):
        k = 2 / (n + 1); e = data[0]
        for p in data[1:]: e = p * k + e * (1 - k)
        return e
    if len(closes) < 26:
        return 0.0, 0.0
    macd = ema(closes[-12:], 12) - ema(closes[-26:], 26)
    return round(macd, 4), round(macd * 0.2, 4)


def _calc_bollinger(closes, period=20):
    if len(closes) < period:
        c = closes[-1]
        return c * 1.02, c, c * 0.98
    w = closes[-period:]
    mid = sum(w) / period
    std = math.sqrt(sum((x - mid)**2 for x in w) / period)
    return round(mid + 2*std, 4), round(mid, 4), round(mid - 2*std, 4)


def _fetch_snapshot_sync(symbol: str) -> dict:
    """
    同步函数，由调用方通过 asyncio.to_thread() 在线程池执行。
    绝对不能直接在 async 函数里 await 以外的地方调用。
    """
    symbol = _normalize_symbol(symbol)

    # 先查缓存
    if _is_cache_valid(symbol):
        try:
            data = json.loads(_cache_path(symbol).read_text())
            print(f"[cn_market] cache hit: {symbol}")
            return data
        except Exception:
            pass

    end   = datetime.now().strftime("%Y%m%d")
    start = (datetime.now() - timedelta(days=120)).strftime("%Y%m%d")

    try:
        import akshare as ak
        df = ak.stock_zh_a_hist(
            symbol=symbol, period="daily",
            start_date=start, end_date=end, adjust="qfq",
        )
        if df is None or df.empty:
            print(f"[cn_market] 无数据: {symbol}")
            return {}

        df = df.rename(columns={
            "日期": "date", "开盘": "open", "收盘": "close",
            "最高": "high", "最低": "low", "成交量": "volume",
            "涨跌幅": "change_pct",
        })

        closes  = df["close"].tolist()
        volumes = df["volume"].tolist()
        dates   = df["date"].astype(str).tolist()

        cp   = round(closes[-1], 2)
        prev = round(closes[-2], 2) if len(closes) > 1 else cp
        chg  = round((cp - prev) / prev * 100, 2)

        ma5  = round(sum(closes[-5:])  / min(5,  len(closes)), 2)
        ma10 = round(sum(closes[-10:]) / min(10, len(closes)), 2)
        ma20 = round(sum(closes[-20:]) / min(20, len(closes)), 2)
        ma60 = round(sum(closes[-60:]) / min(60, len(closes)), 2)

        rsi = _calc_rsi(closes)
        macd_line, macd_sig = _calc_macd(closes)
        bb_upper, bb_mid, bb_lower = _calc_bollinger(closes)

        avg_vol   = int(sum(volumes[-20:]) / min(20, len(volumes)))
        vol_ratio = round(volumes[-1] / avg_vol, 2) if avg_vol > 0 else 1.0

        trend = "多头" if cp > ma20 > ma60 else "空头" if cp < ma20 < ma60 else "震荡"

        snapshot = {
            "symbol": symbol, "fetched_at": datetime.now().isoformat(),
            "current_price": cp, "prev_close": prev, "change_pct": chg,
            "high_52w": round(max(df["high"].tolist()), 2),
            "low_52w":  round(min(df["low"].tolist()),  2),
            "ma5": ma5, "ma10": ma10, "ma20": ma20, "ma60": ma60,
            "rsi": rsi, "macd": macd_line, "macd_signal": macd_sig,
            "bb_upper": bb_upper, "bb_mid": bb_mid, "bb_lower": bb_lower,
            "volume_today": int(volumes[-1]),
            "volume_avg_20d": avg_vol,
            "volume_ratio": vol_ratio,
            "trend": trend,
            "recent_closes": [round(c, 2) for c in closes[-5:]],
            "recent_dates":  dates[-5:],
        }
        _cache_path(symbol).write_text(json.dumps(snapshot, ensure_ascii=False))
        print(f"[cn_market] {symbol}: 价格={cp} RSI={rsi} 趋势={trend} 涨跌={chg}%")
        return snapshot

    except ImportError:
        print("[cn_market] akshare 未安装，请运行: pip install akshare")
        return {}
    except Exception as e:
        print(f"[cn_market] 获取 {symbol} 失败: {type(e).__name__}: {str(e)[:120]}")
        return {}


async def fetch_cn_snapshot(symbol: str) -> dict:
    """
    异步入口 — 在线程池中运行同步的 AKShare 调用，不阻塞事件循环。
    所有调用方都使用这个 async 版本。
    """
    import asyncio
    return await asyncio.to_thread(_fetch_snapshot_sync, symbol)