"""技术分析师 — A股版"""
from __future__ import annotations
from datetime import datetime
from agents.base import BaseAgent
from services.cn_market_data import fetch_cn_snapshot  # async

def _now_iso():
    return datetime.now().isoformat()

def _run_rules(snap):
    rsi, price  = snap["rsi"], snap["current_price"]
    ma20, ma60  = snap["ma20"], snap["ma60"]
    macd, sig   = snap["macd"], snap["macd_signal"]
    bbu, bbl    = snap["bb_upper"], snap["bb_lower"]
    vol_ratio   = snap["volume_ratio"]
    reasons = []

    if rsi > 80:
        reasons.append(f"RSI={rsi:.1f} 极度超买")
        return "sell", 0.85, "RSI极度超买", reasons
    if rsi < 20:
        reasons.append(f"RSI={rsi:.1f} 极度超卖")
        return "buy", 0.85, "RSI极度超卖", reasons
    if rsi > 72:
        reasons.append(f"RSI={rsi:.1f} 超买")
        if price > bbu:
            reasons.append(f"价格{price}突破布林上轨{bbu:.2f}")
            return "sell", 0.80, "RSI超买+布林上轨", reasons
        return "sell", 0.73, "RSI超买", reasons
    if rsi < 28:
        reasons.append(f"RSI={rsi:.1f} 超卖")
        if price < bbl:
            reasons.append(f"价格{price}跌破布林下轨{bbl:.2f}")
            return "buy", 0.80, "RSI超卖+布林下轨", reasons
        return "buy", 0.73, "RSI超卖", reasons

    bull = price > ma20 > ma60 and macd > sig
    bear = price < ma20 < ma60 and macd < sig
    if bull:
        reasons.append(f"多头排列({price}>{ma20:.2f}>{ma60:.2f})，MACD金叉")
        if vol_ratio > 1.5:
            reasons.append(f"量能放大{vol_ratio:.1f}x")
            return "buy", 0.78, "多头排列+量能", reasons
        return "buy", 0.68, "多头排列", reasons
    if bear:
        reasons.append(f"空头排列({price}<{ma20:.2f}<{ma60:.2f})，MACD死叉")
        return "sell", 0.68, "空头排列", reasons
    if price > bbu:
        reasons.append(f"价格{price}突破布林上轨{bbu:.2f}")
        return "sell", 0.62, "突破布林上轨", reasons
    if price < bbl:
        reasons.append(f"价格{price}跌破布林下轨{bbl:.2f}")
        return "buy", 0.62, "跌破布林下轨", reasons
    reasons.append(f"RSI={rsi:.1f} 中性区间，趋势不明朗")
    return "hold", 0.50, "震荡整理", reasons


class CNTechnicalAnalyst(BaseAgent):
    agent_type = "technical"
    weight = 0.25

    async def analyze(self, context: dict) -> dict:
        sym = (context.get("symbols") or ["000001"])[0]
        snap = await fetch_cn_snapshot(sym)   # ← await async 函数
        if not snap:
            return {"agent_type": self.agent_type, "direction": "hold", "confidence": 0.40,
                "reasoning_summary": "技术分析数据获取失败，默认持有。",
                "signal_weight": self.weight, "data_sources": ["数据获取失败"],
                "created_at": _now_iso(), "retry_count": 0, "_events": [], "input_snapshot": {}}

        direction, confidence, rule_name, reasons = _run_rules(snap)
        reason_text = "；".join(reasons)
        system = "你是A股量化技术分析师。根据以下技术指标，写2句专业中文摘要，必须引用具体数值。"
        user   = f"标的：{sym}\n命中规则：{rule_name}\n依据：{reason_text}\n摘要："
        try:
            summary = (await self.llm.complete(system, user)).strip().strip('"')
        except Exception:
            summary = f"【{rule_name}】{reason_text}"

        return {
            "agent_type": self.agent_type, "direction": direction, "confidence": confidence,
            "reasoning_summary": summary, "signal_weight": self.weight,
            "support_level": snap["bb_lower"], "resistance_level": snap["bb_upper"],
            "data_sources": [
                f"AKShare {snap['fetched_at'][:16]}",
                f"价格：{snap['current_price']} ({snap['change_pct']:+.2f}%)",
                f"RSI:{snap['rsi']} MACD:{snap['macd']} 趋势:{snap['trend']}",
            ],
            "created_at": _now_iso(), "retry_count": 0, "_events": [],
            "input_snapshot": {"rule_triggered": rule_name, **snap},
        }