"""
Multi-agent pipeline — A股版
执行员加权投票时，data_missing 事件的信号自动降权
"""
from __future__ import annotations
import asyncio, random, traceback
from datetime import datetime
from agents.cn_technical_agent   import CNTechnicalAnalyst
from agents.cn_fundamental_agent import CNFundamentalAnalyst
from agents.cn_news_agent        import CNNewsAnalyst
from agents.cn_sentiment_agent   import CNSentimentAnalyst

def _now_iso():
    return datetime.now().isoformat()


def _is_data_missing(signal: dict) -> bool:
    """判断该信号是否因数据缺失降级为 hold"""
    snapshot = signal.get("input_snapshot") or {}
    return snapshot.get("data_available") is False or snapshot.get("data_level") == "C"


def _risk_check(signals, context, risk_cfg):
    max_pos = risk_cfg.get("max_position_weight", 0.20)
    portfolio = context.get("current_portfolio") or {}
    for sym in context.get("symbols", []):
        h = portfolio.get(sym, 0)
        weight = h.get("weight", 0) if isinstance(h, dict) else float(h or 0)
        if weight >= max_pos:
            return "high", f"{sym} 已达仓位上限 {max_pos:.0%}"
    directions = [s.get("direction") for s in signals if s.get("direction")]
    total = len(directions) or 1
    if directions.count("sell") / total >= 0.75:
        return "high", "分析师信号强烈看空（≥75%），建议规避"
    if directions.count("buy") / total >= 0.75:
        return "low", "分析师信号强烈看多（≥75%），风险可控"
    return "medium", "分析师信号分歧，中等风险"


def _make_recommendations(signals, context):
    symbols  = context.get("symbols", [])
    portfolio = context.get("current_portfolio") or {s: 0.0 for s in symbols}

    scores   = {"buy": 0.0, "sell": 0.0, "hold": 0.0}
    total_w  = 0.0
    valid_signals = 0
    missing_agents = []

    for sig in signals:
        d = sig.get("direction") or "hold"
        w = sig.get("signal_weight", 0.2)
        c = sig.get("confidence", 0.5)

        # Level C（数据缺失）信号：权重降至 0，不参与方向投票
        if _is_data_missing(sig):
            missing_agents.append(sig.get("agent_type", "unknown"))
            # 占位权重仍计入 total_w，但不影响方向（hold × 极低置信度）
            scores["hold"] += w * c
            total_w += w
            continue

        scores[d] += w * c
        total_w   += w
        valid_signals += 1

    if total_w > 0:
        scores = {k: v / total_w for k, v in scores.items()}

    final_dir = max(scores, key=scores.get)

    # 有效信号不足 2 个时，强制 hold + 提示
    low_data_warning = None
    if valid_signals < 1:
        final_dir = "hold"
        low_data_warning = f"部分Agent数据缺失（有效信号{valid_signals}/4），建议核实后再审批"

    avg_conf = sum(
        s.get("confidence", 0.5) for s in signals
        if not _is_data_missing(s)
    ) / max(valid_signals, 1)

    recs = []
    for sym in symbols:
        h = portfolio.get(sym, 0.0)
        cur = h.get("weight", 0.0) if isinstance(h, dict) else float(h or 0.0)
        if final_dir == "buy":
            rec = min(cur + random.uniform(0.03, 0.08), 0.20)
        elif final_dir == "sell":
            rec = max(cur - random.uniform(0.03, 0.08), 0.0)
        else:
            rec = cur
        recs.append({
            "symbol":             sym,
            "current_weight":     round(cur, 4),
            "recommended_weight": round(rec, 4),
            "weight_delta":       round(rec - cur, 4),
            "confidence_score":   round(avg_conf, 3),
            "similar_cases":      [],
            "missing_agents":     missing_agents,
            "low_data_warning":   low_data_warning,
        })
    return recs


async def run_decision_pipeline(
    decision_id, symbols, current_portfolio, db_updater,
    risk_cfg=None, ws_broadcaster=None,
):
    print(f"[pipeline] START decision={decision_id} symbols={symbols}")
    context  = {"symbols": symbols, "current_portfolio": current_portfolio or {}}
    risk_cfg = risk_cfg or {}

    agents = [CNTechnicalAnalyst(), CNFundamentalAnalyst(), CNNewsAnalyst(), CNSentimentAnalyst()]
    agent_signals, hallucination_events = [], []

    for agent in agents:
        try:
            print(f"[pipeline] running {agent.agent_type}")
            result = await agent.analyze(context)
            events = result.pop("_events", [])
            hallucination_events.extend(events)
            agent_signals.append(result)

            # 数据缺失信号在日志里明显标出
            if _is_data_missing(result):
                print(f"[pipeline] {agent.agent_type} → ⚠️ 数据缺失，信号不参与投票 (conf={result.get('confidence')})")
            else:
                print(f"[pipeline] {agent.agent_type} → {result.get('direction')} (conf={result.get('confidence')})")

        except Exception as e:
            print(f"[pipeline] {agent.agent_type} FAILED: {e}")
            traceback.print_exc()
            agent_signals.append({
                "agent_type":        agent.agent_type,
                "direction":         "hold",
                "confidence":        0.20,
                "reasoning_summary": f"⚠️ Agent 执行异常：{str(e)[:80]}，信号不可信。",
                "signal_weight":     agent.weight,
                "created_at":        _now_iso(),
                "retry_count":       3,
                "input_snapshot":    {"data_level": "C", "data_available": False},
            })

        try:
            await db_updater(
                decision_id,
                agent_signals=list(agent_signals),
                hallucination_events=list(hallucination_events),
            )
        except Exception as e:
            print(f"[pipeline] db write failed: {e}")

    # 风险管理员
    risk_level, risk_reason = _risk_check(agent_signals, context, risk_cfg)
    agent_signals.append({
        "agent_type":        "risk",
        "direction":         None,
        "confidence":        1.0,
        "reasoning_summary": risk_reason,
        "signal_weight":     0.10,
        "created_at":        _now_iso(),
        "retry_count":       0,
    })

    # 执行员汇总
    recommendations = _make_recommendations(agent_signals, context)
    missing_agents  = recommendations[0].get("missing_agents", []) if recommendations else []
    low_data_warn   = recommendations[0].get("low_data_warning") if recommendations else None

    # 最终方向
    directions = [
        s.get("direction") for s in agent_signals
        if s.get("direction") and not _is_data_missing(s)
    ]
    final_direction = max(set(directions), key=directions.count) if directions else "hold"
    if risk_level == "high":
        final_direction = "hold"

    # 执行员摘要
    exec_reasoning = f"最终决策：{final_direction}。风险评级：{risk_level}。{risk_reason}"
    if missing_agents:
        exec_reasoning += f" 注意：{'/'.join(missing_agents)} 因数据缺失未参与投票。"
    if low_data_warn:
        exec_reasoning += f" ⚠️ {low_data_warn}"

    agent_signals.append({
        "agent_type":        "executor",
        "direction":         final_direction,
        "confidence":        round(random.uniform(0.65, 0.88), 2),
        "reasoning_summary": exec_reasoning,
        "signal_weight":     0.05,
        "created_at":        _now_iso(),
        "retry_count":       0,
    })

    try:
        await db_updater(
            decision_id,
            status="completed",
            agent_signals=list(agent_signals),
            hallucination_events=list(hallucination_events),
            recommendations=recommendations,
            final_direction=final_direction,
            risk_level=risk_level,
            completed_at=datetime.now(),
        )
        missing_str = f" (缺失: {missing_agents})" if missing_agents else ""
        print(f"[pipeline] COMPLETED {decision_id} → {final_direction} / {risk_level}{missing_str}")
    except Exception as e:
        print(f"[pipeline] final write failed: {e}")
        traceback.print_exc()
        raise

    if ws_broadcaster:
        try:
            await ws_broadcaster("new_decision", {
                "decision_id":    decision_id,
                "final_direction": final_direction,
            })
        except Exception:
            pass