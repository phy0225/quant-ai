"""
新闻分析师 Agent
数据来源：Alpha Vantage News Sentiment API（免费，25次/天）
注册 Key：https://www.alphavantage.co/support/#api-key
缓存：2小时，避免重复消耗每日配额
"""
from __future__ import annotations
import json, requests
from datetime import datetime, timedelta
from pathlib import Path
from agents.base import BaseAgent
from config import settings

CACHE_DIR = Path(__file__).parent.parent / ".news_cache"
CACHE_TTL_HOURS = 2


def _now_iso():
    return datetime.utcnow().isoformat()


def _cache_path(symbol: str) -> Path:
    CACHE_DIR.mkdir(exist_ok=True)
    return CACHE_DIR / f"{symbol.upper()}_news.json"


def _is_cache_valid(symbol: str) -> bool:
    p = _cache_path(symbol)
    if not p.exists():
        return False
    age = datetime.utcnow() - datetime.utcfromtimestamp(p.stat().st_mtime)
    return age < timedelta(hours=CACHE_TTL_HOURS)


def fetch_news(symbol: str, limit: int = 8) -> list[dict]:
    """
    从 Alpha Vantage 获取最近新闻。
    返回空列表表示获取失败，调用方应降级。
    """
    api_key = getattr(settings, "ALPHAVANTAGE_API_KEY", "")
    if not api_key:
        return []

    if _is_cache_valid(symbol):
        try:
            data = json.loads(_cache_path(symbol).read_text())
            print(f"[news] cache hit: {symbol}")
            return data
        except Exception:
            pass

    try:
        url = (
            f"https://www.alphavantage.co/query"
            f"?function=NEWS_SENTIMENT"
            f"&tickers={symbol}"
            f"&limit={limit}"
            f"&sort=LATEST"
            f"&apikey={api_key}"
        )
        resp = requests.get(url, timeout=15)
        if resp.status_code != 200:
            return []

        raw = resp.json()
        feed = raw.get("feed", [])
        if not feed:
            return []

        news = []
        for item in feed[:limit]:
            # 找到与该标的相关的情绪分数
            ticker_sentiment = next(
                (ts for ts in item.get("ticker_sentiment", [])
                 if ts.get("ticker") == symbol),
                {}
            )
            news.append({
                "title": item.get("title", ""),
                "source": item.get("source", ""),
                "published": item.get("time_published", "")[:8],  # YYYYMMDD
                "summary": item.get("summary", "")[:200],
                "sentiment_label": ticker_sentiment.get("ticker_sentiment_label", "Neutral"),
                "sentiment_score": float(ticker_sentiment.get("ticker_sentiment_score", 0)),
                "relevance_score": float(ticker_sentiment.get("relevance_score", 0)),
                "url": item.get("url", ""),
            })

        # 按相关度排序，取最相关的
        news.sort(key=lambda x: x["relevance_score"], reverse=True)

        _cache_path(symbol).write_text(json.dumps(news))
        print(f"[news] fetched {symbol}: {len(news)} articles")
        return news

    except Exception as e:
        print(f"[news] fetch failed for {symbol}: {e}")
        return []


def _format_news_for_prompt(symbol: str, news: list[dict]) -> str:
    if not news:
        return f"近期无 {symbol} 相关新闻数据。"

    lines = [f"📰 {symbol} 近期新闻（最新 {len(news)} 条）："]
    for i, n in enumerate(news[:5], 1):
        date = n["published"]
        date_fmt = f"{date[:4]}-{date[4:6]}-{date[6:]}" if len(date) >= 8 else date
        sentiment_emoji = "📈" if "Bullish" in n["sentiment_label"] else "📉" if "Bearish" in n["sentiment_label"] else "➡️"
        lines.append(
            f"{i}. [{n['source']} {date_fmt}] {sentiment_emoji} {n['title']}"
        )
        if n.get("summary"):
            lines.append(f"   摘要：{n['summary'][:100]}...")

    # 整体情绪统计
    bullish = sum(1 for n in news if "Bullish" in n.get("sentiment_label", ""))
    bearish = sum(1 for n in news if "Bearish" in n.get("sentiment_label", ""))
    lines.append(f"\n情绪分布：看多 {bullish} 条 / 看空 {bearish} 条 / 中性 {len(news)-bullish-bearish} 条")

    return "\n".join(lines)


def _pre_assess_news(news: list[dict]) -> tuple[str, float]:
    """基于新闻情绪分数做预判"""
    if not news:
        return "neutral", 0.45

    avg_score = sum(n["sentiment_score"] for n in news) / len(news)
    bullish = sum(1 for n in news if "Bullish" in n.get("sentiment_label", ""))
    bearish = sum(1 for n in news if "Bearish" in n.get("sentiment_label", ""))

    if avg_score > 0.2 and bullish > bearish:
        return "bullish", 0.65
    if avg_score < -0.2 and bearish > bullish:
        return "bearish", 0.65
    return "neutral", 0.50


class NewsAnalyst(BaseAgent):
    agent_type = "news"
    weight = 0.20

    async def analyze(self, context: dict) -> dict:
        sym = (context.get("symbols") or ["UNKNOWN"])[0]

        # 1. 获取真实新闻
        news = fetch_news(sym)
        has_news = len(news) > 0

        if has_news:
            news_context = _format_news_for_prompt(sym, news)
            bias, base_conf = _pre_assess_news(news)
            data_source_label = f"Alpha Vantage News（{len(news)}条）"

            system = """你是专业的新闻事件驱动分析师。
你将收到标的的真实最新新闻，请基于这些新闻判断短期（1-5天）投资方向，输出 JSON：
{
  "direction": "buy/sell/hold",
  "confidence": 0.0-1.0,
  "reasoning": "2-3句中文，必须引用具体新闻事件或数据"
}
只返回 JSON，不要其他内容。"""

            user = f"""{news_context}

初步情绪评估：{bias}
请基于以上新闻，判断 {sym} 短期走势："""

        else:
            # 无实时新闻，降级到 LLM 知识
            base_conf = 0.40
            data_source_label = "LLM知识库（ALPHAVANTAGE_API_KEY未配置或无新闻）"

            system = """你是新闻事件驱动分析师。
当前没有实时新闻数据，请基于你对该公司近期状况的了解进行判断。
输出 JSON：{"direction": "buy/sell/hold", "confidence": 0.0-1.0, "reasoning": "2-3句中文"}
confidence 不得超过 0.50。只返回 JSON。"""

            user = f"基于你了解的 {sym} 近期新闻和事件，给出短期走势判断（无实时新闻数据）："

        # 2. LLM 生成判断
        for attempt in range(3):
            try:
                raw = await self.llm.complete(system, user)
                raw = raw.strip().strip("```json").strip("```").strip()
                result = json.loads(raw)

                direction = result.get("direction", "hold")
                if direction not in ("buy", "sell", "hold"):
                    direction = "hold"

                confidence = float(result.get("confidence", base_conf))
                if not has_news:
                    confidence = min(confidence, 0.50)

                return {
                    "agent_type": self.agent_type,
                    "direction": direction,
                    "confidence": confidence,
                    "reasoning_summary": result.get("reasoning", "新闻分析完成。"),
                    "signal_weight": self.weight,
                    "data_sources": [data_source_label] + [
                        f"[{n['source']}] {n['title'][:40]}..."
                        for n in news[:3]
                    ],
                    "created_at": _now_iso(),
                    "retry_count": attempt,
                    "_events": [],
                    "input_snapshot": {
                        "news_count": len(news),
                        "top_headlines": [n["title"] for n in news[:3]],
                        "sentiment_distribution": {
                            "bullish": sum(1 for n in news if "Bullish" in n.get("sentiment_label", "")),
                            "bearish": sum(1 for n in news if "Bearish" in n.get("sentiment_label", "")),
                        },
                        "data_time": _now_iso(),
                    },
                }
            except Exception as e:
                print(f"[NewsAnalyst] attempt {attempt} failed: {e}")
                if attempt == 2:
                    break

        return {
            "agent_type": self.agent_type,
            "direction": "hold",
            "confidence": 0.40,
            "reasoning_summary": "新闻分析失败，默认持有。",
            "signal_weight": self.weight,
            "data_sources": [data_source_label],
            "created_at": _now_iso(),
            "retry_count": 3,
            "_events": [],
            "input_snapshot": {},
        }
