"""情绪分析师 — 结合持仓浮盈判断情绪风险（浮盈过高的标的更容易恐慌抛售）"""
from __future__ import annotations
from datetime import datetime
from agents.base import BaseAgent
from agents.portfolio_context import get_holding, format_holding_context
from services.cn_market_data import fetch_cn_snapshot
from services.cn_sentiment_data import build_sentiment_context

def _now_iso():
    return datetime.now().isoformat()

class CNSentimentAnalyst(BaseAgent):
    agent_type = "sentiment"
    weight = 0.15

    async def analyze(self, context: dict) -> dict:
        sym = (context.get("symbols") or ["000001"])[0]
        snap      = await fetch_cn_snapshot(sym)
        rsi       = snap["rsi"]       if snap else 50.0
        vol_ratio = snap["volume_ratio"] if snap else 1.0

        sentiment_ctx, direction, confidence = await build_sentiment_context(sym, rsi, vol_ratio)

        # 持仓上下文
        holding = get_holding(context, sym)
        holding_ctx = format_holding_context(holding, sym)

        # 持仓浮盈对情绪的影响
        holding_sentiment_note = ""
        if holding and holding.get("pnl_pct") is not None:
            pnl = holding["pnl_pct"]
            pnl_pct = pnl * 100 if abs(pnl) < 1 else pnl
            if pnl_pct >= 50:
                # 大幅浮盈 → 市场情绪过热时持有者更容易止盈抛售
                holding_sentiment_note = f"当前浮盈{pnl_pct:.1f}%，大幅浮盈持仓者在情绪过热时抛售压力大，需防范踩踏风险。"
                if direction == "buy":
                    direction = "hold"
                    confidence = min(confidence, 0.52)
            elif pnl_pct <= -25:
                # 大幅浮亏 → 恐慌抛售压力已释放，情绪面底部特征
                holding_sentiment_note = f"当前浮亏{pnl_pct:.1f}%，大幅亏损下持仓者恐慌情绪已部分释放，情绪面具备底部特征。"
                if direction == "sell":
                    direction = "hold"
                    confidence = min(confidence, 0.52)

        system = "你是A股市场情绪分析师。根据以下情绪指标和持仓情况，写2-3句中文摘要，必须引用具体数值，如有持仓需结合持仓盈亏分析情绪风险。直接返回文字。"
        user_parts = [sentiment_ctx]
        if holding:
            user_parts.append(f"\n{holding_ctx}")
        if holding_sentiment_note:
            user_parts.append(f"\n持仓情绪分析：{holding_sentiment_note}")
        user_parts.append(f"\n为 {sym} 写情绪摘要：")

        try:
            summary = (await self.llm.complete(system, "\n".join(user_parts))).strip().strip('"')
        except Exception:
            summary = f"情绪评估：{direction}。RSI={rsi:.1f}，成交量比={vol_ratio:.2f}x。"
            if holding_sentiment_note:
                summary += f" {holding_sentiment_note}"

        ds = ["东财评分+北向资金+涨跌停", f"RSI:{rsi:.1f}", f"量比:{vol_ratio:.2f}x"]
        if holding and holding.get("pnl_pct") is not None:
            pnl = holding["pnl_pct"]
            pnl_pct = pnl * 100 if abs(pnl) < 1 else pnl
            ds.append(f"持仓浮盈{pnl_pct:+.1f}%")

        return {
            "agent_type": self.agent_type, "direction": direction, "confidence": confidence,
            "reasoning_summary": summary, "signal_weight": self.weight,
            "data_sources": ds,
            "created_at": _now_iso(), "retry_count": 0, "_events": [],
            "input_snapshot": {"rsi": rsi, "volume_ratio": vol_ratio, "holding": holding},
        }