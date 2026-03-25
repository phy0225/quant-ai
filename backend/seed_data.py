"""
一键生成演示数据脚本
运行方式：python seed_data.py
"""
import asyncio
import uuid
import random
import json
import math
from datetime import datetime, timedelta

from database import AsyncSessionLocal, init_db
from models import DecisionRun, ApprovalRecord, BacktestReport, GraphNode, RiskEvent, AutoApprovalRule

SYMBOLS_POOL = ["AAPL", "GOOGL", "MSFT", "TSLA", "NVDA", "AMZN", "META", "NFLX"]

def uid():
    return str(uuid.uuid4())

def dt(days_ago=0, hours_ago=0):
    return datetime.utcnow() - timedelta(days=days_ago, hours=hours_ago)

def rand_direction():
    return random.choices(["buy", "sell", "hold"], weights=[0.45, 0.25, 0.30])[0]

def rand_confidence():
    return round(random.uniform(0.55, 0.92), 2)

def make_agent_signals(symbols, final_dir):
    agents = [
        ("technical",   0.25, ["RSI", "MACD", "Bollinger Bands"]),
        ("fundamental", 0.25, ["10-K", "Earnings reports"]),
        ("news",        0.20, ["Reuters", "Bloomberg"]),
        ("sentiment",   0.15, ["Twitter/X", "Reddit"]),
    ]
    signals = []
    base_dt = datetime.utcnow()
    for i, (agent_type, weight, sources) in enumerate(agents):
        d = rand_direction()
        signals.append({
            "agent_type": agent_type,
            "direction": d,
            "confidence": rand_confidence(),
            "reasoning_summary": f"{agent_type.title()} analysis for {', '.join(symbols)}: signal is {d} based on current market data.",
            "signal_weight": weight,
            "created_at": (base_dt + timedelta(seconds=i*2)).isoformat(),
            "retry_count": random.choices([0, 0, 0, 1], weights=[7, 1, 1, 1])[0],
            "data_sources": sources,
        })
    # risk
    signals.append({
        "agent_type": "risk",
        "direction": None,
        "confidence": 1.0,
        "reasoning_summary": "Risk check passed. Position limits within bounds.",
        "signal_weight": 0.10,
        "created_at": (base_dt + timedelta(seconds=9)).isoformat(),
        "retry_count": 0,
    })
    # executor
    signals.append({
        "agent_type": "executor",
        "direction": final_dir,
        "confidence": rand_confidence(),
        "reasoning_summary": f"Final decision: {final_dir}. Aggregated from analyst consensus.",
        "signal_weight": 0.05,
        "created_at": (base_dt + timedelta(seconds=11)).isoformat(),
        "retry_count": 0,
    })
    return signals

def make_recommendations(symbols, direction):
    recs = []
    for sym in symbols:
        cur = round(random.uniform(0, 0.25), 4)
        if direction == "buy":
            rec = min(cur + round(random.uniform(0.03, 0.08), 4), 0.20)
        elif direction == "sell":
            rec = max(cur - round(random.uniform(0.03, 0.08), 4), 0.0)
        else:
            rec = cur
        recs.append({
            "symbol": sym,
            "current_weight": cur,
            "recommended_weight": round(rec, 4),
            "weight_delta": round(rec - cur, 4),
            "confidence_score": rand_confidence(),
            "similar_cases": [],
        })
    return recs

def make_nav_curve(start_date, end_date, total_return):
    from datetime import date
    start = datetime.strptime(start_date, "%Y-%m-%d")
    end   = datetime.strptime(end_date,   "%Y-%m-%d")
    days  = []
    cur = start
    while cur <= end:
        if cur.weekday() < 5:
            days.append(cur.strftime("%Y-%m-%d"))
        cur += timedelta(days=1)

    n = len(days)
    if n < 2:
        return []

    random.seed(42)
    nav, bench = 1.0, 1.0
    curve = []
    target_daily = (1 + total_return) ** (1 / n) - 1
    for day in days:
        nav   *= (1 + target_daily + random.gauss(0, 0.008))
        bench *= (1 + random.gauss(0.0002, 0.007))
        curve.append({"date": day, "nav": round(nav, 6), "benchmark_nav": round(bench, 6)})
    return curve

def make_monthly_returns(nav_curve):
    monthly = {}
    prev = 1.0
    for p in nav_curve:
        y, m = int(p["date"][:4]), int(p["date"][5:7])
        monthly[(y, m)] = p["nav"]
    result = []
    prev = 1.0
    for (y, m), val in sorted(monthly.items()):
        result.append({"year": y, "month": m, "return": round(val / prev - 1, 6)})
        prev = val
    return result

async def seed():
    await init_db()
    async with AsyncSessionLocal() as db:

        # ── 1. Auto-approval rules ────────────────────────────────────────
        rules = [
            AutoApprovalRule(
                id=uid(), name="小幅调仓自动批准", is_active=True, priority=10,
                logic_operator="AND",
                conditions=[
                    {"field": "max_weight_delta", "operator": "lte", "value": 0.05},
                    {"field": "min_confidence_score", "operator": "gte", "value": 0.6},
                ],
                action="auto_approve", trigger_count=7,
                last_triggered_at=dt(days_ago=1),
                description="调仓幅度小且置信度较高时自动批准",
            ),
            AutoApprovalRule(
                id=uid(), name="高置信度自动批准", is_active=True, priority=20,
                logic_operator="AND",
                conditions=[{"field": "min_confidence_score", "operator": "gte", "value": 0.85}],
                action="auto_approve", trigger_count=3,
                last_triggered_at=dt(days_ago=3),
                description="Agent 置信度极高时自动批准",
            ),
        ]
        for r in rules:
            db.add(r)

        # ── 2. Risk events ────────────────────────────────────────────────
        risk_events_data = [
            ("position_limit_check", "warning",  "TSLA 持仓达到 18%，接近上限",       0.18, 0.20, 5),
            ("position_limit_check", "warning",  "NVDA 持仓达到 16%，接近上限",       0.16, 0.20, 8),
            ("circuit_breaker_reset","warning",  "熔断等级由 L1 重置为 L0，操作人: admin", None, None, 12),
        ]
        for ev_type, severity, desc, tval, thval, days_ago in risk_events_data:
            db.add(RiskEvent(
                id=uid(), event_type=ev_type, severity=severity,
                description=desc, triggered_value=tval, threshold_value=thval,
                created_at=dt(days_ago=days_ago),
            ))

        # ── 3. Decision runs + approvals ──────────────────────────────────
        decision_configs = [
            # (symbols, direction, approval_status, days_ago, hours_ago)
            (["AAPL"],              "buy",  "approved",       14, 2),
            (["GOOGL", "MSFT"],     "hold", "approved",       12, 4),
            (["TSLA"],              "sell", "rejected",       10, 1),
            (["NVDA"],              "buy",  "auto_approved",   8, 3),
            (["AAPL", "AMZN"],      "buy",  "approved",        7, 5),
            (["META"],              "hold", "auto_approved",   6, 2),
            (["NFLX"],              "sell", "approved",        5, 1),
            (["GOOGL"],             "buy",  "approved",        4, 6),
            (["MSFT", "NVDA"],      "buy",  "modified",        3, 2),
            (["AAPL"],              "hold", "approved",        2, 4),
            (["TSLA", "META"],      "buy",  "approved",        1, 3),
            (["AMZN"],              "buy",  "pending",         0, 2),
            (["GOOGL", "AAPL"],     "sell", "pending",         0, 1),
            (["NVDA"],              "buy",  "pending",         0, 0),
        ]

        graph_nodes = []
        for symbols, direction, appr_status, days_ago, hours_ago in decision_configs:
            run_id   = uid()
            start_dt = dt(days_ago=days_ago, hours_ago=hours_ago)
            end_dt   = start_dt + timedelta(seconds=random.randint(8, 25))
            signals  = make_agent_signals(symbols, direction)
            recs     = make_recommendations(symbols, direction)

            run = DecisionRun(
                id=run_id,
                status="completed",
                triggered_by="user",
                started_at=start_dt,
                completed_at=end_dt,
                symbols=symbols,
                agent_signals=signals,
                hallucination_events=[],
                recommendations=recs,
                final_direction=direction,
                risk_level=random.choice(["low", "medium", "medium", "high"]),
                error_message=None,
            )
            db.add(run)

            # Approval record
            appr_id  = uid()
            reviewed = appr_status in ("approved", "rejected", "auto_approved", "modified")
            appr = ApprovalRecord(
                id=appr_id,
                decision_run_id=run_id,
                status=appr_status,
                reviewed_by="admin" if reviewed else None,
                reviewed_at=end_dt + timedelta(minutes=random.randint(5, 120)) if reviewed else None,
                comment=random.choice([None, None, "符合预期，批准", "风险可控"]) if reviewed else None,
                recommendations=recs,
                created_at=end_dt,
            )
            db.add(appr)

            # Graph node for approved decisions
            if appr_status in ("approved", "auto_approved", "modified"):
                outcome = round(random.uniform(-0.05, 0.15), 4)
                graph_nodes.append(GraphNode(
                    node_id=uid(),
                    approval_id=appr_id,
                    timestamp=appr.reviewed_at or end_dt,
                    approved=True,
                    outcome_return=outcome,
                    outcome_sharpe=round(random.uniform(0.5, 3.5), 2),
                    symbols=symbols,
                    embedding=[round(random.gauss(0, 1), 4) for _ in range(32)],
                ))

        for gn in graph_nodes:
            db.add(gn)

        # ── 4. Backtest reports ───────────────────────────────────────────
        backtest_configs = [
            ("2024-07-01", "2024-09-30", ["AAPL", "GOOGL", "MSFT"], 0.187, 2.1),
            ("2024-10-01", "2024-12-31", ["NVDA", "TSLA", "META"],  0.243, 2.8),
            ("2025-01-01", "2025-03-31", ["AAPL", "AMZN", "NFLX"], 0.112, 1.6),
        ]
        for start_d, end_d, syms, total_ret, sharpe in backtest_configs:
            nav_curve = make_nav_curve(start_d, end_d, total_ret)
            monthly   = make_monthly_returns(nav_curve)
            n_days    = len(nav_curve)
            n_years   = n_days / 252
            ann_ret   = (1 + total_ret) ** (1 / max(n_years, 0.01)) - 1

            # Max drawdown
            peak, max_dd = 1.0, 0.0
            for p in nav_curve:
                peak  = max(peak, p["nav"])
                max_dd = max(max_dd, (peak - p["nav"]) / peak)

            initial = 1_000_000
            n_trades = n_days // 5 * len(syms)
            comm_rate, slip = 0.003, 0.001
            avg_trade = initial / len(syms)
            total_comm = n_trades * avg_trade * comm_rate
            total_slip = n_trades * avg_trade * slip

            days_ago = random.randint(5, 20)
            db.add(BacktestReport(
                id=uid(),
                status="completed",
                symbols=syms,
                start_date=start_d,
                end_date=end_d,
                initial_capital=initial,
                benchmark="buy_and_hold",
                commission_rate=comm_rate,
                slippage=slip,
                rebalance_frequency="weekly",
                nav_curve=nav_curve,
                monthly_returns=monthly,
                total_return=round(total_ret, 6),
                annualized_return=round(ann_ret, 6),
                sharpe_ratio=round(sharpe, 4),
                max_drawdown=round(-max_dd, 6),
                win_rate=round(random.uniform(0.52, 0.68), 4),
                avg_holding_days=round(random.uniform(3, 12), 1),
                total_commission=round(total_comm, 2),
                total_slippage_cost=round(total_slip, 2),
                created_at=dt(days_ago=days_ago),
                completed_at=dt(days_ago=days_ago) + timedelta(seconds=45),
            ))

        await db.commit()
        print("✅ 演示数据生成完成！")
        print(f"   决策记录：{len(decision_configs)} 条（3 条待审批）")
        print(f"   经验图谱节点：{len(graph_nodes)} 个")
        print(f"   回测报告：{len(backtest_configs)} 份")
        print(f"   自动审批规则：{len(rules)} 条")
        print(f"   风险事件：{len(risk_events_data)} 条")

if __name__ == "__main__":
    asyncio.run(seed())
