"""技术分析师 — 结合持仓成本价和浮盈做止盈止损判断"""
from __future__ import annotations
from datetime import datetime
from agents.base import BaseAgent
from agents.portfolio_context import get_holding, format_holding_context
from services.cn_market_data import fetch_cn_snapshot

def _now_iso():
    return datetime.now().isoformat()

def _run_rules(snap) -> tuple[str, float, str, list]:
    rsi, price = snap["rsi"], snap["current_price"]
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


def _holding_rule_override(direction: str, confidence: float,
                            holding: dict | None, current_price: float) -> tuple[str, float, str | None]:
    """
    基于持仓成本价和浮盈做规则覆盖：
    大幅浮盈时技术面偏弱也建议止盈；大幅亏损时重新评估方向
    """
    if not holding:
        return direction, confidence, None

    pnl = holding.get("pnl_pct")
    cost = holding.get("cost_price")
    if pnl is None or cost is None:
        return direction, confidence, None

    pnl_pct = pnl * 100 if abs(pnl) < 1 else pnl
    override_note = None

    # 浮盈 > 50%：技术面持有或买入信号 → 降低置信度，提示止盈
    if pnl_pct >= 50 and direction in ("buy", "hold"):
        confidence = min(confidence, 0.55)
        override_note = f"注意：当前浮盈已达{pnl_pct:.1f}%，建议结合止盈策略评估"

    # 浮盈 > 80%：技术面继续看多 → 明确降权，提示减仓
    if pnl_pct >= 80 and direction == "buy":
        direction = "hold"
        confidence = 0.50
        override_note = f"大幅浮盈{pnl_pct:.1f}%，技术看多信号已降权，建议考虑分批止盈"

    # 浮亏 > 30%：技术面持有 → 提示关注止损
    if pnl_pct <= -30 and direction == "hold":
        confidence = min(confidence, 0.50)
        override_note = f"当前浮亏{pnl_pct:.1f}%（成本¥{cost:.2f}），建议重新评估止损位"

    return direction, confidence, override_note


class CNTechnicalAnalyst(BaseAgent):
    agent_type = "technical"
    weight = 0.25

    async def analyze(self, context: dict) -> dict:
        sym = (context.get("symbols") or ["000001"])[0]
        snap = await fetch_cn_snapshot(sym)
        if not snap:
            return self._fallback(sym)

        direction, confidence, rule_name, reasons = _run_rules(snap)
        reason_text = "；".join(reasons)

        # 持仓上下文
        holding = get_holding(context, sym)
        holding_ctx = format_holding_context(holding, sym)

        # 持仓规则覆盖（大幅浮盈/亏损时调整信号）
        direction, confidence, override_note = _holding_rule_override(
            direction, confidence, holding, snap["current_price"]
        )

        # LLM 生成摘要，融入持仓信息
        system = "你是A股量化技术分析师。根据以下技术指标和持仓情况，写2-3句专业中文摘要，必须引用具体数值，如有持仓需结合成本价和盈亏分析。"
        user_parts = [f"标的：{sym}", f"命中规则：{rule_name}", f"技术依据：{reason_text}"]
        if holding:
            user_parts.append(f"\n{holding_ctx}")
        if override_note:
            user_parts.append(f"\n⚠️ 持仓提示：{override_note}")
        user_parts.append("\n摘要：")

        try:
            summary = (await self.llm.complete(system, "\n".join(user_parts))).strip().strip('"')
        except Exception:
            summary = f"【{rule_name}】{reason_text}"
            if override_note:
                summary += f" {override_note}"

        data_sources = [
            f"AKShare {snap['fetched_at'][:16]}",
            f"价格：{snap['current_price']} ({snap['change_pct']:+.2f}%)",
            f"RSI:{snap['rsi']} MACD:{snap['macd']} 趋势:{snap['trend']}",
        ]
        if holding and holding.get("pnl_pct") is not None:
            pnl = holding["pnl_pct"]
            pnl_pct = pnl * 100 if abs(pnl) < 1 else pnl
            data_sources.append(f"持仓成本¥{holding.get('cost_price','--')}，浮盈{pnl_pct:+.1f}%")

        return {
            "agent_type": self.agent_type, "direction": direction, "confidence": confidence,
            "reasoning_summary": summary, "signal_weight": self.weight,
            "support_level": snap["bb_lower"], "resistance_level": snap["bb_upper"],
            "data_sources": data_sources,
            "created_at": _now_iso(), "retry_count": 0, "_events": [],
            "input_snapshot": {
                "rule_triggered": rule_name,
                "holding": holding,
                "override_note": override_note,
                **snap,
            },
        }

    def _fallback(self, sym):
        return {"agent_type": self.agent_type, "direction": "hold", "confidence": 0.40,
            "reasoning_summary": "技术分析数据获取失败，默认持有。",
            "signal_weight": self.weight, "data_sources": ["数据获取失败"],
            "created_at": _now_iso(), "retry_count": 0, "_events": [], "input_snapshot": {}}