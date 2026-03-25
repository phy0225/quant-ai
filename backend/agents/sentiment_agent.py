"""
情绪分析师 Agent
数据来源：
  1. Alternative.me Fear & Greed Index（完全免费，无需 Key）
  2. yfinance 个股 RSI 和成交量（已有）
逻辑：恐慌贪婪指数 + 个股 RSI 综合判断，LLM 生成摘要
"""
from __future__ import annotations
import json, requests
from datetime import datetime, timedelta
from pathlib import Path
from agents.base import BaseAgent
from services.market_data import fetch_market_snapshot

CACHE_DIR = Path(__file__).parent.parent / ".sentiment_cache"
CACHE_TTL_HOURS = 4  # 恐慌贪婪指数每天更新一次，4h 缓存够用


def _now_iso():
    return datetime.utcnow().isoformat()


def _fng_cache_path() -> Path:
    CACHE_DIR.mkdir(exist_ok=True)
    return CACHE_DIR / "fear_greed.json"


def _is_fng_cache_valid() -> bool:
    p = _fng_cache_path()
    if not p.exists():
        return False
    age = datetime.utcnow() - datetime.utcfromtimestamp(p.stat().st_mtime)
    return age < timedelta(hours=CACHE_TTL_HOURS)


def fetch_fear_greed_index() -> dict | None:
    """
    获取 CNN Fear & Greed Index。
    完全免费，无需 API Key。
    返回格式：{"value": 72, "classification": "Greed", "timestamp": "..."}
    """
    if _is_fng_cache_valid():
        try:
            data = json.loads(_fng_cache_path().read_text())
            print(f"[sentiment] FNG cache hit: {data.get('value')} {data.get('classification')}")
            return data
        except Exception:
            pass

    try:
        resp = requests.get(
            "https://api.alternative.me/fng/?limit=1",
            timeout=10,
            headers={"User-Agent": "Mozilla/5.0"}
        )
        if resp.status_code != 200:
            return None

        raw = resp.json().get("data", [{}])[0]
        data = {
            "value": int(raw.get("value", 50)),
            "classification": raw.get("value_classification", "Neutral"),
            "timestamp": raw.get("timestamp", _now_iso()),
            "fetched_at": _now_iso(),
        }
        _fng_cache_path().write_text(json.dumps(data))
        print(f"[sentiment] FNG fetched: {data['value']} ({data['classification']})")
        return data

    except Exception as e:
        print(f"[sentiment] FNG fetch failed: {e}")
        return None


def _classify_fng(value: int) -> tuple[str, str]:
    """把数值转成信号方向（逆向情绪指标）"""
    if value <= 20:
        return "buy", "极度恐慌（逆向看多）"
    if value <= 35:
        return "buy", "市场恐慌（轻度看多）"
    if value <= 55:
        return "hold", "市场情绪中性"
    if value <= 75:
        return "sell", "市场贪婪（轻度看空）"
    return "sell", "极度贪婪（逆向看空）"


def _classify_rsi_sentiment(rsi: float) -> str:
    if rsi > 75:
        return "个股极度超买，散户情绪过热"
    if rsi > 62:
        return "个股偏超买，短期情绪偏高"
    if rsi < 25:
        return "个股极度超卖，市场恐慌性抛售"
    if rsi < 38:
        return "个股偏超卖，短期悲观情绪"
    return "个股情绪中性"


def _combine_signals(fng_dir: str, rsi: float, vol_ratio: float) -> tuple[str, float]:
    """
    综合三个维度给出最终方向和置信度
    FNG 权重 50%，RSI 情绪 30%，成交量异常 20%
    """
    scores = {"buy": 0.0, "sell": 0.0, "hold": 0.0}

    # FNG（权重 0.5）
    scores[fng_dir] += 0.5

    # RSI 情绪（权重 0.3）
    if rsi > 70:
        scores["sell"] += 0.3
    elif rsi < 30:
        scores["buy"] += 0.3
    else:
        scores["hold"] += 0.3

    # 成交量异常（权重 0.2）
    if vol_ratio > 2.0:
        # 放量需要结合方向
        if scores["buy"] > scores["sell"]:
            scores["buy"] += 0.2
        else:
            scores["sell"] += 0.2
    else:
        scores["hold"] += 0.2

    direction = max(scores, key=scores.get)
    confidence = round(0.45 + scores[direction] * 0.5, 2)
    return direction, min(confidence, 0.82)


class SentimentAnalyst(BaseAgent):
    agent_type = "sentiment"
    weight = 0.15

    async def analyze(self, context: dict) -> dict:
        sym = (context.get("symbols") or ["UNKNOWN"])[0]

        # 1. 获取恐慌贪婪指数
        fng = fetch_fear_greed_index()

        # 2. 获取个股 RSI 和成交量（yfinance 已有）
        snapshot = fetch_market_snapshot(sym)
        rsi = snapshot.get("rsi", 50) if snapshot else 50
        vol_ratio = snapshot.get("volume_ratio", 1.0) if snapshot else 1.0

        # 3. 规则合并信号
        if fng:
            fng_dir, fng_label = _classify_fng(fng["value"])
            direction, confidence = _combine_signals(fng_dir, rsi, vol_ratio)

            # 构建 Prompt 上下文
            rsi_label = _classify_rsi_sentiment(rsi)
            sentiment_context = f"""市场情绪指标（实时数据）：

🌡️ CNN 恐慌贪婪指数：{fng['value']}/100（{fng['classification']}）
   → {fng_label}

📈 {sym} 个股 RSI(14)：{rsi:.1f}
   → {rsi_label}

📊 成交量比（vs 20日均量）：{vol_ratio:.2f}x
   → {"成交量显著放大，情绪活跃" if vol_ratio > 1.5 else "成交量偏低，市场观望" if vol_ratio < 0.7 else "成交量正常"}

综合量化评分：倾向 {direction}"""

            data_sources = [
                f"Fear & Greed Index: {fng['value']} ({fng['classification']})",
                f"{sym} RSI(14): {rsi:.1f}",
                f"成交量比: {vol_ratio:.2f}x",
            ]
            input_snapshot = {
                "fng_value": fng["value"],
                "fng_classification": fng["classification"],
                "rsi": rsi,
                "volume_ratio": vol_ratio,
                "data_time": fng.get("fetched_at", _now_iso()),
            }

        else:
            # FNG 获取失败，纯靠 RSI
            if rsi > 72:
                direction, confidence = "sell", 0.62
            elif rsi < 28:
                direction, confidence = "buy", 0.62
            else:
                direction, confidence = "hold", 0.45

            sentiment_context = f"""市场情绪指标（恐慌贪婪指数获取失败，仅个股数据）：

📈 {sym} RSI(14)：{rsi:.1f}（{_classify_rsi_sentiment(rsi)}）
📊 成交量比：{vol_ratio:.2f}x"""

            data_sources = [f"{sym} RSI(14): {rsi:.1f}", "FNG数据不可用"]
            input_snapshot = {"rsi": rsi, "volume_ratio": vol_ratio, "fng_available": False}

        # 4. LLM 生成自然语言摘要
        system = """你是市场情绪分析师，擅长解读情绪指标的投资含义。
请根据给定的情绪指标数据，用2句中文写出分析摘要，必须引用具体的指数数值。
直接返回文字摘要，不要 JSON 格式。"""

        user = f"""{sentiment_context}

请为 {sym} 写出情绪面分析摘要（2句）："""

        try:
            summary = await self.llm.complete(system, user)
            summary = summary.strip().strip('"').strip("'")
        except Exception:
            rsi_desc = _classify_rsi_sentiment(rsi)
            fng_desc = f"恐慌贪婪指数{fng['value']}（{fng['classification']}）" if fng else ""
            summary = f"{rsi_desc}。{fng_desc}"

        return {
            "agent_type": self.agent_type,
            "direction": direction,
            "confidence": confidence,
            "reasoning_summary": summary,
            "signal_weight": self.weight,
            "data_sources": data_sources,
            "created_at": _now_iso(),
            "retry_count": 0,
            "_events": [],
            "input_snapshot": input_snapshot,
        }
