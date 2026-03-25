"""A股情绪数据 — 同步函数通过线程池执行"""
from __future__ import annotations
import json
from datetime import datetime, timedelta
from pathlib import Path
from services.cn_market_data import _normalize_symbol

CACHE_DIR = Path(__file__).parent.parent / ".cn_sentiment_cache"
CACHE_TTL_HOURS = 2


def _cache_path(key: str) -> Path:
    CACHE_DIR.mkdir(exist_ok=True)
    return CACHE_DIR / f"{key}_sentiment.json"


def _is_cache_valid(key: str) -> bool:
    p = _cache_path(key)
    if not p.exists():
        return False
    return datetime.now() - datetime.fromtimestamp(p.stat().st_mtime) < timedelta(hours=CACHE_TTL_HOURS)


def _fetch_comment_sync(symbol: str) -> dict | None:
    symbol = _normalize_symbol(symbol)
    key = f"{symbol}_comment"
    if _is_cache_valid(key):
        try:
            return json.loads(_cache_path(key).read_text())
        except Exception:
            pass
    try:
        import akshare as ak
        df = None
        for kwargs in [{"code": symbol}, {"symbol": symbol}]:
            try:
                df = ak.stock_comment_em(**kwargs)
                if df is not None and not df.empty:
                    break
            except TypeError:
                continue
            except Exception:
                break
        if df is None or df.empty:
            return None
        latest = df.iloc[0]
        score_col = next((c for c in df.columns if "得分" in c or "评分" in c), None)
        win_col   = next((c for c in df.columns if "胜率" in c), None)
        data = {
            "score":    float(latest[score_col]) if score_col and latest[score_col] else 50.0,
            "win_rate": str(latest[win_col]) if win_col else "",
        }
        _cache_path(key).write_text(json.dumps(data, ensure_ascii=False))
        return data
    except Exception as e:
        print(f"[cn_sentiment] 股评失败 {symbol}: {e}")
        return None


def _fetch_north_flow_sync() -> dict | None:
    if _is_cache_valid("north_flow"):
        try:
            return json.loads(_cache_path("north_flow").read_text())
        except Exception:
            pass
    try:
        import akshare as ak
        for func_name in [
            "stock_em_hsgt_north_net_flow_in",
            "stock_hsgt_north_net_flow_in_em",
            "stock_hsgt_fund_flow_summary_em",
        ]:
            func = getattr(ak, func_name, None)
            if func is None:
                continue
            try:
                df = func(indicator="今日")
                if df is None or df.empty:
                    continue
                latest = df.iloc[-1]
                north_col = next((c for c in df.columns if "北向" in c), None)
                total = float(latest[north_col]) if north_col else 0.0
                data = {"total_flow": total, "fetched_at": datetime.now().isoformat()}
                _cache_path("north_flow").write_text(json.dumps(data, ensure_ascii=False))
                print(f"[cn_sentiment] 北向资金 {func_name}: {total} 亿")
                return data
            except Exception as e:
                print(f"[cn_sentiment] {func_name}: {e}")
        return None
    except Exception as e:
        print(f"[cn_sentiment] 北向资金失败: {e}")
        return None


def _fetch_breadth_sync() -> dict | None:
    if _is_cache_valid("market_breadth"):
        try:
            return json.loads(_cache_path("market_breadth").read_text())
        except Exception:
            pass
    try:
        import akshare as ak
        today = datetime.now().strftime("%Y%m%d")
        zt, dt = 0, 0
        for fn in ["stock_zt_pool_em", "stock_limit_up_pool_em"]:
            f = getattr(ak, fn, None)
            if f:
                try:
                    df = f(date=today)
                    if df is not None and not df.empty:
                        zt = len(df); break
                except Exception as e:
                    print(f"[cn_sentiment] {fn}: {e}")
        for fn in ["stock_dt_pool_em", "stock_limit_down_pool_em"]:
            f = getattr(ak, fn, None)
            if f:
                try:
                    df = f(date=today)
                    if df is not None and not df.empty:
                        dt = len(df); break
                except Exception as e:
                    print(f"[cn_sentiment] {fn}: {e}")
        data = {
            "limit_up_count": zt, "limit_down_count": dt,
            "sentiment_ratio": round(zt / max(zt + dt, 1), 2),
        }
        if zt > 0 or dt > 0:
            _cache_path("market_breadth").write_text(json.dumps(data, ensure_ascii=False))
        print(f"[cn_sentiment] 涨停:{zt} 跌停:{dt}")
        return data
    except Exception as e:
        print(f"[cn_sentiment] 涨跌停失败: {e}")
        return None


async def fetch_stock_comment(symbol: str) -> dict | None:
    import asyncio
    return await asyncio.to_thread(_fetch_comment_sync, symbol)


async def fetch_north_flow() -> dict | None:
    import asyncio
    return await asyncio.to_thread(_fetch_north_flow_sync)


async def fetch_market_breadth() -> dict | None:
    import asyncio
    return await asyncio.to_thread(_fetch_breadth_sync)


async def build_sentiment_context(symbol: str, rsi: float, vol_ratio: float) -> tuple[str, str, float]:
    symbol  = _normalize_symbol(symbol)
    comment = await fetch_stock_comment(symbol)
    north   = await fetch_north_flow()
    breadth = await fetch_market_breadth()

    lines = [f"🧠 {symbol} 市场情绪指标："]
    score_signal = 0.0

    if comment and comment.get("score"):
        score = comment["score"]
        lines.append(f"• 东财评分：{score:.0f}/100")
        score_signal += 1.5 if score > 65 else (-1.0 if score < 40 else 0)

    lines.append(f"• RSI(14)：{rsi:.1f}")
    if rsi > 72:   score_signal -= 2.0
    elif rsi < 28: score_signal += 2.0

    lines.append(f"• 成交量比：{vol_ratio:.2f}x")

    if north and north.get("total_flow") is not None:
        flow = north["total_flow"]
        lines.append(f"• 北向资金：{flow:+.1f} 亿元")
        score_signal += (1.0 if flow > 30 else (-1.0 if flow < -30 else 0))

    if breadth:
        zt, dt = breadth["limit_up_count"], breadth["limit_down_count"]
        ratio  = breadth["sentiment_ratio"]
        lines.append(f"• 涨停 {zt} / 跌停 {dt}（情绪比 {ratio:.0%}）")
        score_signal += (0.5 if ratio > 0.7 else (-0.5 if ratio < 0.3 else 0))

    if score_signal >= 2.0:
        direction, confidence = "buy",  round(min(0.50 + score_signal * 0.05, 0.78), 2)
    elif score_signal <= -2.0:
        direction, confidence = "sell", round(min(0.50 + abs(score_signal) * 0.05, 0.75), 2)
    else:
        direction, confidence = "hold", 0.48

    lines.append(f"\n综合得分：{score_signal:+.1f} → {direction}")
    return "\n".join(lines), direction, confidence