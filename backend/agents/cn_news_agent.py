"""新闻分析师 — 结合持仓情况判断新闻对持仓者的影响"""
from __future__ import annotations
import json
from datetime import datetime
from agents.base import BaseAgent
from agents.portfolio_context import get_holding, format_holding_context
from services.cn_news_data import fetch_cn_news, fetch_cls_telegraph, format_news_for_prompt

def _now_iso():
    return datetime.now().isoformat()

class CNNewsAnalyst(BaseAgent):
    agent_type = "news"
    weight = 0.20

    async def analyze(self, context: dict) -> dict:
        sym = (context.get("symbols") or ["000001"])[0]
        news      = await fetch_cn_news(sym)
        telegraph = await fetch_cls_telegraph()
        n_news    = len(news)
        holding   = get_holding(context, sym)
        holding_ctx = format_holding_context(holding, sym)
        factor_hint, factor_snapshot = self._factor_hint(context, sym)

        if n_news >= 3:   level, max_conf = "A", 0.75
        elif n_news >= 1: level, max_conf = "B", 0.55
        else:             level, max_conf = "C", 0.20

        if level == "C":
            return {
                "agent_type": self.agent_type, "direction": "hold", "confidence": 0.20,
                "reasoning_summary": f"⚠️ 【数据缺失】{sym} 暂无新闻数据，无法给出有效判断。",
                "signal_weight": self.weight, "data_sources": ["❌ 无新闻数据"],
                "created_at": _now_iso(), "retry_count": 0,
                "_events": [{"agent_type": self.agent_type, "event_type": "data_missing",
                    "description": "新闻数据获取失败", "retry_count": 0,
                    "resolved": False, "created_at": _now_iso()}],
                "input_snapshot": {"data_level": "C", "news_count": 0},
            }

        news_ctx = format_news_for_prompt(sym, news)
        if telegraph:
            news_ctx += "\n\n📡 财联社快讯：\n" + "\n".join(f"• {t.get('title','')}" for t in telegraph[:3])
        src = f"东方财富新闻（{n_news}条，Level {level}）"

        # 持仓信息帮助 LLM 判断：同一条新闻对有持仓 vs 无持仓的分析者意义不同
        holding_news_note = ""
        if holding:
            pnl = holding.get("pnl_pct")
            if pnl is not None:
                pnl_pct = pnl * 100 if abs(pnl) < 1 else pnl
                if pnl_pct <= -20:
                    holding_news_note = f"注意：当前持仓已浮亏{abs(pnl_pct):.1f}%，新闻利空信号对持仓者而言需要更严肃对待。"
                elif pnl_pct >= 30:
                    holding_news_note = f"注意：当前持仓浮盈{pnl_pct:.1f}%，新闻利好信号可结合止盈策略综合考量。"

        system = f"""你是A股新闻事件驱动分析师。
基于以下真实新闻和持仓情况，判断短期（1-5交易日）股价影响，输出JSON：
{{"direction":"buy/sell/hold","confidence":0.0-{max_conf},"reasoning":"2-3句中文，必须引用具体新闻事件，如有持仓需说明对持仓的影响"}}
只返回JSON。"""

        user_parts = [news_ctx]
        if factor_hint:
            user_parts.append(f"\n{factor_hint}")
        if holding:
            user_parts.append(f"\n{holding_ctx}")
        if holding_news_note:
            user_parts.append(f"\n{holding_news_note}")
        user_parts.append(f"\n判断对 {sym} 短期股价的影响：")

        for attempt in range(3):
            try:
                raw = (await self.llm.complete(system, "\n".join(user_parts))).strip().strip("```json").strip("```").strip()
                result = json.loads(raw)
                direction = result.get("direction", "hold")
                if direction not in ("buy","sell","hold"): direction = "hold"
                confidence = min(float(result.get("confidence", 0.45)), max_conf)
                reasoning = result.get("reasoning", "新闻分析完成。")
                if level == "B": reasoning = f"[新闻样本少] {reasoning}"
                ds = [src] + [n["title"][:35]+"..." for n in news[:3]]
                if holding and holding.get("pnl_pct") is not None:
                    pnl = holding["pnl_pct"]
                    pnl_pct = pnl * 100 if abs(pnl) < 1 else pnl
                    ds.append(f"持仓浮盈{pnl_pct:+.1f}%")
                return {
                    "agent_type": self.agent_type, "direction": direction,
                    "confidence": confidence, "reasoning_summary": reasoning,
                    "signal_weight": self.weight, "data_sources": ds,
                    "created_at": _now_iso(), "retry_count": attempt, "_events": [],
                    "input_snapshot": {"data_level": level, "news_count": n_news,
                        "headlines": [n["title"] for n in news[:5]], "holding": holding, "factor_context": factor_snapshot},
                }
            except Exception as e:
                print(f"[News] attempt {attempt}: {e}")
                if attempt == 2: break

        return {"agent_type": self.agent_type, "direction": "hold", "confidence": 0.20,
            "reasoning_summary": "新闻分析失败，默认持有。",
            "signal_weight": self.weight, "data_sources": [src],
            "created_at": _now_iso(), "retry_count": 3, "_events": [], "input_snapshot": {}}
