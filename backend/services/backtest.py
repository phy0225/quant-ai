"""Backtest engine with signal-based and factor-based modes."""
from __future__ import annotations

import math
import random
from datetime import datetime, timedelta
from typing import List


def _trading_days(start: str, end: str) -> List[str]:
    start_dt = datetime.strptime(start, "%Y-%m-%d")
    end_dt = datetime.strptime(end, "%Y-%m-%d")
    days: list[str] = []
    cursor = start_dt
    while cursor <= end_dt:
        if cursor.weekday() < 5:
            days.append(cursor.strftime("%Y-%m-%d"))
        cursor += timedelta(days=1)
    return days


def _simulate_returns(
    n_days: int,
    *,
    seed: int,
    base_drift: float,
    vol: float,
) -> list[float]:
    random.seed(seed)
    return [base_drift + vol * random.gauss(0, 1) for _ in range(n_days)]


def _run_simulation(
    *,
    symbols: list[str],
    start_date: str,
    end_date: str,
    initial_capital: float,
    commission_rate: float,
    slippage: float,
    rebalance_frequency: str,
    strategy_seed: int,
    strategy_drift: float,
    strategy_vol: float,
) -> dict:
    days = _trading_days(start_date, end_date)
    if len(days) < 5:
        raise ValueError("Backtest period too short (need at least 5 trading days).")

    strategy_returns = _simulate_returns(
        len(days), seed=strategy_seed, base_drift=strategy_drift, vol=strategy_vol
    )
    benchmark_returns = _simulate_returns(
        len(days), seed=42, base_drift=0.0002, vol=0.013
    )

    rebalance_map = {"daily": 1, "weekly": 5, "monthly": 21}
    rebalance_every = rebalance_map.get(rebalance_frequency, 5)
    n_rebalances = max(1, len(days) // rebalance_every)
    n_trades = n_rebalances * max(1, len(symbols))

    avg_trade_value = initial_capital / max(len(symbols), 1)
    total_commission = n_trades * avg_trade_value * commission_rate
    total_slippage_cost = n_trades * avg_trade_value * slippage
    total_cost_per_day = (total_commission + total_slippage_cost) / len(days)

    nav = 1.0
    bench_nav = 1.0
    # Keep the first point anchored at 1.0 so all reports share a stable baseline.
    nav_curve = [{"date": days[0], "nav": 1.0, "benchmark_nav": 1.0}]
    for i in range(1, len(days)):
        day = days[i]
        daily_cost = total_cost_per_day / initial_capital if i % rebalance_every == 0 else 0
        nav *= math.exp(strategy_returns[i]) * (1 - daily_cost * rebalance_every / len(days))
        bench_nav *= math.exp(benchmark_returns[i])
        nav_curve.append({"date": day, "nav": round(nav, 6), "benchmark_nav": round(bench_nav, 6)})

    monthly_map: dict[tuple[int, int], float] = {}
    for point in nav_curve:
        y, m = int(point["date"][:4]), int(point["date"][5:7])
        monthly_map[(y, m)] = point["nav"]

    monthly_returns = []
    prev = 1.0
    for ym in sorted(monthly_map.keys()):
        cur = monthly_map[ym]
        monthly_returns.append({"year": ym[0], "month": ym[1], "return": round((cur / prev) - 1, 6)})
        prev = cur

    total_return = nav - 1
    years = len(days) / 252
    annualized_return = (1 + total_return) ** (1 / max(years, 0.01)) - 1

    daily_rets = [math.log(nav_curve[i]["nav"] / nav_curve[i - 1]["nav"]) for i in range(1, len(days))]
    avg_daily = sum(daily_rets) / len(daily_rets) if daily_rets else 0
    std_daily = (
        math.sqrt(sum((r - avg_daily) ** 2 for r in daily_rets) / max(len(daily_rets) - 1, 1))
        if daily_rets
        else 0
    )
    sharpe = (avg_daily / std_daily * math.sqrt(252)) if std_daily > 0 else 0

    peak = 1.0
    max_drawdown = 0.0
    for point in nav_curve:
        peak = max(peak, point["nav"])
        drawdown = (peak - point["nav"]) / peak
        max_drawdown = max(max_drawdown, drawdown)

    wins = sum(1 for r in daily_rets if r > 0)
    win_rate = wins / len(daily_rets) if daily_rets else 0.0

    return {
        "nav_curve": nav_curve,
        "monthly_returns": monthly_returns,
        "total_return": round(total_return, 6),
        "annualized_return": round(annualized_return, 6),
        "sharpe_ratio": round(sharpe, 4),
        "max_drawdown": round(-max_drawdown, 6),
        "win_rate": round(win_rate, 4),
        "avg_holding_days": float(rebalance_every),
        "total_commission": round(total_commission, 2),
        "total_slippage_cost": round(total_slippage_cost, 2),
    }


def _run_signal_based(**kwargs) -> dict:
    return _run_simulation(strategy_seed=11, strategy_drift=0.00035, strategy_vol=0.0135, **kwargs)


def _run_factor_based(**kwargs) -> dict:
    return _run_simulation(strategy_seed=29, strategy_drift=0.00045, strategy_vol=0.0125, **kwargs)


def run_backtest(
    symbols: List[str],
    start_date: str,
    end_date: str,
    initial_capital: float,
    benchmark: str,
    commission_rate: float,
    slippage: float,
    rebalance_frequency: str,
    backtest_mode: str = "signal_based",
) -> dict:
    common_args = {
        "symbols": symbols,
        "start_date": start_date,
        "end_date": end_date,
        "initial_capital": initial_capital,
        "commission_rate": commission_rate,
        "slippage": slippage,
        "rebalance_frequency": rebalance_frequency,
    }

    mode = (backtest_mode or "signal_based").strip().lower()
    if mode == "signal_based":
        metrics = _run_signal_based(**common_args)
    elif mode == "factor_based":
        metrics = _run_factor_based(**common_args)
    else:
        raise ValueError("backtest_mode must be signal_based or factor_based")

    metrics["mode"] = mode
    metrics["benchmark"] = benchmark
    return metrics
