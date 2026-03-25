"""基本面分析师 — 结合持仓成本价评估当前估值吸引力"""
from __future__ import annotations
import json
from datetime import datetime
from agents.base import BaseAgent
from agents.portfolio_context import get_holding, format_holding_context
from services.cn_fundamental_data import fetch_cn_fundamentals, format_for_prompt

def _now_iso():
    return datetime.now().isoformat()


def _assess_data_level(fin):
    if not fin:
        return "C", 0.25
    has_financial = any(fin.get(k) for k in ["revenue_yoy","net_profit_yoy","roe","gross_margin","debt_ratio"])
    has_valuation = any(fin.get(k) for k in ["pe_ratio","pb_ratio","total_mv"])
    if has_financial and has_valuation:
        return "A", 0.80
    if has_financial or has_valuation:
        return "B", 0.60
    return "C", 0.25


class CNFundamentalAnalyst(BaseAgent):
    agent_type = "fundamental"
    weight = 0.25

    async def analyze(self, context: dict) -> dict:
        sym = (context.get("symbols") or ["000001"])[0]
        fin = await fetch_cn_fundamentals(sym)
        level, max_conf = _assess_data_level(fin)

        # 持仓上下文
        holding = get_holding(context, sym)
        holding_ctx = format_holding_context(holding, sym)

        if level == "C":
            return {
                "agent_type": self.agent_type, "direction": "hold", "confidence": 0.25,
                "reasoning_summary": f"⚠️ 【数据缺失】{sym} 暂无可用财务数据，基本面分析无法给出有效判断。",
                "signal_weight": self.weight, "data_sources": ["❌ 无财务数据"],
                "created_at": _now_iso(), "retry_count": 0,
                "_events": [{"agent_type": self.agent_type, "event_type": "data_missing",
                    "description": "财务数据获取失败", "retry_count": 0,
                    "resolved": False, "created_at": _now_iso()}],
                "input_snapshot": {"data_level": "C"},
            }

        data_ctx = format_for_prompt(fin)
        src = f"AKShare财务（Level {level}，{fin.get('report_period','TTM')}）"

        # 持仓成本价 vs 当前 PE/PB，判断估值吸引力
        holding_valuation_note = ""
        if holding and holding.get("cost_price") and holding.get("current_price"):
            cost  = holding["cost_price"]
            curr  = holding["current_price"]
            pnl   = holding.get("pnl_pct", 0)
            pnl_pct = (pnl * 100 if abs(pnl) < 1 else pnl) if pnl else 0
            pe    = fin.get("pe_ratio")
            # 建仓后价格已大幅回落，估值可能更便宜了
            if pnl_pct <= -20 and pe:
                est_cost_pe = pe * curr / cost  # 估算建仓时的 PE
                holding_valuation_note = (
                    f"注：持仓成本¥{cost:.2f}，较成本已跌{abs(pnl_pct):.1f}%，"
                    f"当前PE={pe}，相比建仓时估算PE≈{est_cost_pe:.1f}更具吸引力，"
                    f"请结合基本面判断是否具备加仓条件。"
                )
            elif pnl_pct >= 30 and pe:
                holding_valuation_note = (
                    f"注：持仓成本¥{cost:.2f}，已浮盈{pnl_pct:.1f}%，"
                    f"当前PE={pe}，请评估当前估值是否仍具安全边际。"
                )

        system = f"""你是A股专业基本面分析师。
基于以下真实财务数据和持仓情况判断投资价值，输出JSON：
{{"direction":"buy/sell/hold","confidence":0.0-{max_conf},"reasoning":"2-3句中文，必须引用至少2个具体财务数据，如有持仓需结合成本价分析"}}
只返回JSON。"""

        user_parts = [data_ctx]
        if holding:
            user_parts.append(f"\n{holding_ctx}")
        if holding_valuation_note:
            user_parts.append(f"\n{holding_valuation_note}")
        user_parts.append(f"\n请对 {sym} 给出基本面投资建议：")

        for attempt in range(3):
            try:
                raw = (await self.llm.complete(system, "\n".join(user_parts))).strip().strip("```json").strip("```").strip()
                result = json.loads(raw)
                direction = result.get("direction", "hold")
                if direction not in ("buy","sell","hold"): direction = "hold"
                confidence = min(float(result.get("confidence", 0.55)), max_conf)
                reasoning = result.get("reasoning", "基本面分析完成。")
                if level == "B":
                    reasoning = f"[仅部分数据] {reasoning}"
                ds = [src]
                if holding and holding.get("pnl_pct") is not None:
                    pnl = holding["pnl_pct"]
                    pnl_pct = pnl * 100 if abs(pnl) < 1 else pnl
                    ds.append(f"持仓成本¥{holding.get('cost_price','--')}，浮盈{pnl_pct:+.1f}%")
                return {
                    "agent_type": self.agent_type, "direction": direction,
                    "confidence": confidence, "reasoning_summary": reasoning,
                    "signal_weight": self.weight, "data_sources": ds,
                    "created_at": _now_iso(), "retry_count": attempt, "_events": [],
                    "input_snapshot": {"data_level": level, "holding": holding,
                        **{k: fin.get(k) for k in ["pe_ratio","pb_ratio","total_mv","revenue_yoy","net_profit_yoy","roe"] if fin.get(k)}},
                }
            except Exception as e:
                print(f"[Fundamental] attempt {attempt}: {e}")
                if attempt == 2: break

        return {"agent_type": self.agent_type, "direction": "hold", "confidence": 0.30,
            "reasoning_summary": "基本面分析失败，默认持有。",
            "signal_weight": self.weight, "data_sources": [src],
            "created_at": _now_iso(), "retry_count": 3, "_events": [], "input_snapshot": {}}