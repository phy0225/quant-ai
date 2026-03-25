"""
基本面分析师 Agent
数据来源：Financial Modeling Prep（FMP）免费 API
FMP 免费版：每天 250 次请求，7 天本地缓存
注册 Key：https://financialmodelingprep.com/developer/docs/
"""
from __future__ import annotations
import json, requests
from datetime import datetime, timedelta
from pathlib import Path
from agents.base import BaseAgent
from config import settings

CACHE_DIR = Path(__file__).parent.parent / ".fundamental_cache"
CACHE_TTL_DAYS = 7  # 季报数据更新慢，7天缓存


def _now_iso():
    return datetime.utcnow().isoformat()


def _cache_path(symbol: str) -> Path:
    CACHE_DIR.mkdir(exist_ok=True)
    return CACHE_DIR / f"{symbol.upper()}_fundamentals.json"


def _is_cache_valid(symbol: str) -> bool:
    p = _cache_path(symbol)
    if not p.exists():
        return False
    age = datetime.utcnow() - datetime.utcfromtimestamp(p.stat().st_mtime)
    return age < timedelta(days=CACHE_TTL_DAYS)


def fetch_fundamentals(symbol: str) -> dict | None:
    """
    从 FMP 获取关键财务指标。
    返回 None 表示获取失败，调用方应降级到 LLM 知识库模式。
    """
    api_key = getattr(settings, "FMP_API_KEY", "")
    if not api_key:
        return None  # 未配置 Key，降级

    # 检查缓存
    if _is_cache_valid(symbol):
        try:
            data = json.loads(_cache_path(symbol).read_text())
            print(f"[fundamental] cache hit: {symbol}")
            return data
        except Exception:
            pass

    try:
        # FMP 关键比率接口
        url = f"https://financialmodelingprep.com/api/v3/key-metrics-ttm/{symbol}?apikey={api_key}"
        resp = requests.get(url, timeout=10)
        if resp.status_code != 200 or not resp.json():
            return None

        raw = resp.json()[0]

        # 成长性数据（YoY）
        growth_url = f"https://financialmodelingprep.com/api/v3/financial-growth/{symbol}?limit=1&apikey={api_key}"
        growth_resp = requests.get(growth_url, timeout=10)
        growth = growth_resp.json()[0] if growth_resp.status_code == 200 and growth_resp.json() else {}

        data = {
            "symbol": symbol,
            "fetched_at": _now_iso(),
            # 估值
            "pe_ratio": raw.get("peRatioTTM"),
            "pb_ratio": raw.get("pbRatioTTM"),
            "ps_ratio": raw.get("priceToSalesRatioTTM"),
            "ev_ebitda": raw.get("enterpriseValueOverEBITDATTM"),
            # 盈利能力
            "gross_margin": raw.get("grossProfitMarginTTM"),
            "net_margin": raw.get("netProfitMarginTTM"),
            "roe": raw.get("roeTTM"),
            "roa": raw.get("returnOnAssetsTTM"),
            # 成长性
            "revenue_growth": growth.get("revenueGrowth"),
            "eps_growth": growth.get("epsgrowth"),
            # 财务健康
            "debt_equity": raw.get("debtToEquityTTM"),
            "current_ratio": raw.get("currentRatioTTM"),
            "fcf_per_share": raw.get("freeCashFlowPerShareTTM"),
            # 元信息
            "period": growth.get("date", "TTM"),
        }

        # 写入缓存
        _cache_path(symbol).write_text(json.dumps(data))
        print(f"[fundamental] fetched {symbol}: PE={data['pe_ratio']:.1f} net_margin={data['net_margin']:.2%}" if data.get('pe_ratio') and data.get('net_margin') else f"[fundamental] fetched {symbol}")
        return data

    except Exception as e:
        print(f"[fundamental] fetch failed for {symbol}: {e}")
        return None


def _format_for_prompt(data: dict) -> str:
    """格式化财务数据为 LLM prompt 输入"""
    lines = [f"📊 {data['symbol']} 最新财务数据（来源：FMP，截至 {data.get('period','TTM')}）"]

    if data.get("pe_ratio"):
        lines.append(f"• 市盈率（PE）：{data['pe_ratio']:.1f}x")
    if data.get("net_margin"):
        lines.append(f"• 净利润率：{data['net_margin']:.1%}")
    if data.get("roe"):
        lines.append(f"• 净资产收益率（ROE）：{data['roe']:.1%}")
    if data.get("revenue_growth") is not None:
        lines.append(f"• 营收增速（YoY）：{data['revenue_growth']:.1%}")
    if data.get("eps_growth") is not None:
        lines.append(f"• EPS 增速（YoY）：{data['eps_growth']:.1%}")
    if data.get("debt_equity") is not None:
        lines.append(f"• 债务/权益比：{data['debt_equity']:.2f}")
    if data.get("fcf_per_share") is not None:
        lines.append(f"• 自由现金流/股：${data['fcf_per_share']:.2f}")

    return "\n".join(lines)


def _assess_fundamentals(data: dict) -> tuple[str, float]:
    """
    基于财务数据做简单规则评分，辅助 LLM 判断方向。
    返回 (bias, score) bias: bullish/bearish/neutral
    """
    score = 0

    # PE 合理性（越低越好，但不能为负）
    pe = data.get("pe_ratio")
    if pe and 0 < pe < 20:
        score += 2
    elif pe and 20 <= pe < 35:
        score += 0
    elif pe and pe >= 35:
        score -= 1

    # 成长性
    rev_growth = data.get("revenue_growth", 0) or 0
    if rev_growth > 0.20:
        score += 2
    elif rev_growth > 0.05:
        score += 1
    elif rev_growth < -0.05:
        score -= 2

    # 盈利能力
    net_margin = data.get("net_margin", 0) or 0
    if net_margin > 0.20:
        score += 1
    elif net_margin < 0:
        score -= 2

    # 财务健康
    debt_eq = data.get("debt_equity", 1) or 1
    if debt_eq < 0.5:
        score += 1
    elif debt_eq > 2.0:
        score -= 1

    if score >= 3:
        return "bullish", 0.72
    if score <= -2:
        return "bearish", 0.68
    return "neutral", 0.55


class FundamentalAnalyst(BaseAgent):
    agent_type = "fundamental"
    weight = 0.25

    async def analyze(self, context: dict) -> dict:
        sym = (context.get("symbols") or ["UNKNOWN"])[0]

        # 1. 获取真实财务数据
        fin_data = fetch_fundamentals(sym)
        use_real_data = fin_data is not None

        if use_real_data:
            # 2a. 规则预判方向（辅助 LLM）
            bias, base_conf = _assess_fundamentals(fin_data)
            data_context = _format_for_prompt(fin_data)
            data_source_label = f"FMP {fin_data.get('period', 'TTM')}"

            system = """你是专业的基本面分析师，擅长价值投资分析。
你将收到真实的财务数据，请基于这些数据判断投资价值，输出 JSON：
{
  "direction": "buy/sell/hold",
  "confidence": 0.0-1.0,
  "reasoning": "2-3句中文，必须引用至少2个具体财务数据"
}
只返回 JSON，不要其他内容。"""

            user = f"""{data_context}

初步量化评估：{bias}（基于规则打分）

请综合以上财务数据，对 {sym} 给出基本面投资建议："""

        else:
            # 2b. 无真实数据，降级到 LLM 知识库
            base_conf = 0.45
            data_source_label = "LLM知识库（无实时数据，仅供参考）"

            system = """你是专业的基本面分析师。
注意：当前没有实时财务数据，请基于你训练数据中对该公司的了解进行分析。
输出 JSON：{"direction": "buy/sell/hold", "confidence": 0.0-1.0, "reasoning": "2-3句中文分析"}
confidence 不得超过 0.55（无实时数据时置信度受限）。只返回 JSON。"""

            user = f"基于你了解的 {sym} 公司基本面情况，给出投资建议（注意：无实时财务数据）："

        # 3. LLM 生成最终判断和摘要
        for attempt in range(3):
            try:
                raw = await self.llm.complete(system, user)
                raw = raw.strip().strip("```json").strip("```").strip()
                result = json.loads(raw)

                direction = result.get("direction", "hold")
                if direction not in ("buy", "sell", "hold"):
                    direction = "hold"

                # 无真实数据时置信度上限 0.55
                confidence = float(result.get("confidence", base_conf))
                if not use_real_data:
                    confidence = min(confidence, 0.55)

                return {
                    "agent_type": self.agent_type,
                    "direction": direction,
                    "confidence": confidence,
                    "reasoning_summary": result.get("reasoning", "基本面分析完成。"),
                    "signal_weight": self.weight,
                    "data_sources": [data_source_label],
                    "created_at": _now_iso(),
                    "retry_count": attempt,
                    "_events": [],
                    "input_snapshot": fin_data or {"mode": "llm_knowledge", "note": "FMP_API_KEY未配置"},
                }
            except Exception as e:
                print(f"[FundamentalAnalyst] attempt {attempt} failed: {e}")
                if attempt == 2:
                    break

        return {
            "agent_type": self.agent_type,
            "direction": "hold",
            "confidence": 0.40,
            "reasoning_summary": "基本面分析失败，默认持有。",
            "signal_weight": self.weight,
            "data_sources": [data_source_label],
            "created_at": _now_iso(),
            "retry_count": 3,
            "_events": [],
            "input_snapshot": {},
        }
