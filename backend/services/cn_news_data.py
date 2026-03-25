"""A股新闻数据 — 同步函数通过线程池执行"""
from __future__ import annotations
import json
from datetime import datetime, timedelta
from pathlib import Path
from services.cn_market_data import _normalize_symbol

CACHE_DIR = Path(__file__).parent.parent / ".cn_news_cache"
CACHE_TTL_HOURS = 2


def _cache_path(symbol: str) -> Path:
    CACHE_DIR.mkdir(exist_ok=True)
    return CACHE_DIR / f"{symbol}_news.json"


def _is_cache_valid(symbol: str) -> bool:
    p = _cache_path(symbol)
    if not p.exists():
        return False
    return datetime.now() - datetime.fromtimestamp(p.stat().st_mtime) < timedelta(hours=CACHE_TTL_HOURS)


def _fetch_news_sync(symbol: str, limit: int = 10) -> list[dict]:
    symbol = _normalize_symbol(symbol)

    if _is_cache_valid(symbol):
        try:
            return json.loads(_cache_path(symbol).read_text())
        except Exception:
            pass

    news = []
    try:
        import akshare as ak
        try:
            df = ak.stock_news_em(symbol=symbol)
            if df is not None and not df.empty:
                for _, row in df.head(limit).iterrows():
                    news.append({
                        "title":     str(row.get("新闻标题", "")),
                        "source":    str(row.get("新闻来源", "东方财富")),
                        "published": str(row.get("发布时间", ""))[:10],
                        "content":   str(row.get("新闻内容", ""))[:200],
                    })
                print(f"[cn_news] {symbol}: {len(news)} 条")
        except Exception as e:
            print(f"[cn_news] 东财新闻失败 {symbol}: {e}")

        if news:
            _cache_path(symbol).write_text(json.dumps(news, ensure_ascii=False))
    except ImportError:
        pass
    except Exception as e:
        print(f"[cn_news] {symbol}: {e}")

    return news


def _fetch_telegraph_sync() -> list[dict]:
    try:
        import akshare as ak
        for func_name in ["stock_telegraph_cls", "stock_cls_telegraph", "cls_telegraph"]:
            func = getattr(ak, func_name, None)
            if func is None:
                continue
            try:
                df = func()
                if df is None or df.empty:
                    continue
                title_col   = next((c for c in df.columns if "标题" in c or "title" in c.lower()), None)
                time_col    = next((c for c in df.columns if "时间" in c or "time" in c.lower()), None)
                content_col = next((c for c in df.columns if "内容" in c or "content" in c.lower()), None)
                result = []
                for _, row in df.head(6).iterrows():
                    result.append({
                        "title":     str(row[title_col]) if title_col else str(row.iloc[0]),
                        "published": str(row[time_col])[:16] if time_col else "",
                        "content":   str(row[content_col])[:150] if content_col else "",
                    })
                print(f"[cn_news] 财联社 {func_name}: {len(result)} 条")
                return result
            except Exception as e:
                print(f"[cn_news] {func_name}: {e}")
    except Exception:
        pass
    return []


async def fetch_cn_news(symbol: str, limit: int = 10) -> list[dict]:
    import asyncio
    return await asyncio.to_thread(_fetch_news_sync, symbol, limit)


async def fetch_cls_telegraph() -> list[dict]:
    import asyncio
    return await asyncio.to_thread(_fetch_telegraph_sync)


def format_news_for_prompt(symbol: str, news: list[dict]) -> str:
    if not news:
        return f"近期无 {symbol} 相关新闻数据。"
    lines = [f"📰 {symbol} 近期新闻（{len(news)} 条）："]
    for i, n in enumerate(news[:6], 1):
        lines.append(f"{i}. [{n['source']} {n['published']}] {n['title']}")
        if n.get("content") and n["content"] != n["title"]:
            lines.append(f"   摘要：{n['content'][:80]}...")
    return "\n".join(lines)