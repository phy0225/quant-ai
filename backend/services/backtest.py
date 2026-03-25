"""Backtest engine — simulates agent strategy performance on historical data."""
from __future__ import annotations
import random
import math
from datetime import datetime, timedelta
from typing import List

def _trading_days(start: str, end: str) -> List[str]:
    """Generate trading day strings between start and end dates."""
    start_dt = datetime.strptime(start, "%Y-%m-%d")
    end_dt = datetime.strptime(end, "%Y-%m-%d")
    days = []
    cur = start_dt
    while cur <= end_dt:
        if cur.weekday() < 5:
            days.append(cur.strftime("%Y-%m-%d"))
        cur += timedelta(days=1)
    return days

def _simulate_returns(n_days: int, base_drift: float = 0.0003, vol: float = 0.015):
    """Simulate daily log returns using GBM."""
    random.seed(42)
    returns = []
    for _ in range(n_days):
        r = base_drift + vol * (random.gauss(0, 1))
        returns.append(r)
    return returns

def run_backtest(
    symbols: List[str],
    start_date: str,
    end_date: str,
    initial_capital: float,
    benchmark: str,
    commission_rate: float,
    slippage: float,
    rebalance_frequency: str,
) -> dict:
    """Run a deterministic mock backtest and return metrics + curves."""
    days = _trading_days(start_date, end_date)
    n = len(days)
    if n < 5:
        raise ValueError("Backtest period too short (need at least 5 trading days).")

    # Strategy slightly outperforms benchmark with realistic noise
    strategy_returns = _simulate_returns(n, base_drift=0.0004, vol=0.014)
    benchmark_returns = _simulate_returns(n, base_drift=0.0002, vol=0.013)

    # Rebalance frequency (determines trade frequency for costs)
    rebalance_map = {"daily": 1, "weekly": 5, "monthly": 21}
    rebalance_every = rebalance_map.get(rebalance_frequency, 5)
    n_rebalances = max(1, n // rebalance_every)
    n_trades = n_rebalances * len(symbols)

    # Trading cost deduction
    avg_trade_value = initial_capital / max(len(symbols), 1)
    total_commission = n_trades * avg_trade_value * commission_rate
    total_slippage_cost = n_trades * avg_trade_value * slippage
    total_cost_per_day = (total_commission + total_slippage_cost) / n

    # Build NAV curve
    nav = 1.0
    bench_nav = 1.0
    nav_curve = []
    for i, day in enumerate(days):
        daily_cost = total_cost_per_day / initial_capital if i % rebalance_every == 0 else 0
        nav *= math.exp(strategy_returns[i]) * (1 - daily_cost * rebalance_every / n)
        bench_nav *= math.exp(benchmark_returns[i])
        nav_curve.append({
            "date": day,
            "nav": round(nav, 6),
            "benchmark_nav": round(bench_nav, 6),
        })

    # Monthly returns
    monthly_map: dict = {}
    prev_nav = 1.0
    for point in nav_curve:
        date = point["date"]
        y, m = int(date[:4]), int(date[5:7])
        monthly_map[(y, m)] = point["nav"]

    monthly_returns = []
    sorted_months = sorted(monthly_map.keys())
    prev = 1.0
    for ym in sorted_months:
        cur = monthly_map[ym]
        ret = (cur / prev) - 1
        monthly_returns.append({"year": ym[0], "month": ym[1], "return": round(ret, 6)})
        prev = cur

    # Metrics
    total_return = nav - 1
    n_years = n / 252
    annualized_return = (1 + total_return) ** (1 / max(n_years, 0.01)) - 1

    # Daily returns for Sharpe
    daily_rets = [math.log(nav_curve[i]["nav"] / nav_curve[i-1]["nav"]) for i in range(1, n)]
    avg_daily = sum(daily_rets) / len(daily_rets) if daily_rets else 0
    std_daily = math.sqrt(sum((r - avg_daily) ** 2 for r in daily_rets) / max(len(daily_rets) - 1, 1))
    sharpe = (avg_daily / std_daily * math.sqrt(252)) if std_daily > 0 else 0

    # Max drawdown
    peak = 1.0
    max_dd = 0.0
    for point in nav_curve:
        peak = max(peak, point["nav"])
        dd = (peak - point["nav"]) / peak
        max_dd = max(max_dd, dd)

    # Win rate (positive daily returns)
    positive_days = sum(1 for r in daily_rets if r > 0)
    win_rate = positive_days / len(daily_rets) if daily_rets else 0

    # Avg holding days (mock based on rebalance frequency)
    avg_holding_days = float(rebalance_every)

    return {
        "nav_curve": nav_curve,
        "monthly_returns": monthly_returns,
        "total_return": round(total_return, 6),
        "annualized_return": round(annualized_return, 6),
        "sharpe_ratio": round(sharpe, 4),
        "max_drawdown": round(-max_dd, 6),
        "win_rate": round(win_rate, 4),
        "avg_holding_days": round(avg_holding_days, 1),
        "total_commission": round(total_commission, 2),
        "total_slippage_cost": round(total_slippage_cost, 2),
    }
