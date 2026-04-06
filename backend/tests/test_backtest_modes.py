import pytest

from services.backtest import run_backtest


def test_signal_based_backtest_uses_historical_decisions():
    result = run_backtest(
        symbols=["600519", "300750"],
        start_date="2024-01-01",
        end_date="2024-06-30",
        initial_capital=1_000_000,
        benchmark="buy_and_hold",
        commission_rate=0.003,
        slippage=0.001,
        rebalance_frequency="weekly",
        backtest_mode="signal_based",
    )
    assert result["mode"] == "signal_based"
    assert "nav_curve" in result and len(result["nav_curve"]) > 0


def test_factor_based_backtest_mode_supported():
    result = run_backtest(
        symbols=["600519", "300750"],
        start_date="2024-01-01",
        end_date="2024-06-30",
        initial_capital=1_000_000,
        benchmark="buy_and_hold",
        commission_rate=0.003,
        slippage=0.001,
        rebalance_frequency="weekly",
        backtest_mode="factor_based",
    )
    assert result["mode"] == "factor_based"
    assert "sharpe_ratio" in result


@pytest.mark.asyncio
async def test_backtest_api_accepts_mode(client):
    resp = await client.post(
        "/api/v1/backtest/",
        json={
            "symbols": ["600519", "300750"],
            "start_date": "2024-01-01",
            "end_date": "2024-06-30",
            "initial_capital": 1_000_000,
            "benchmark": "buy_and_hold",
            "commission_rate": 0.003,
            "slippage": 0.001,
            "rebalance_frequency": "weekly",
            "backtest_mode": "factor_based",
        },
    )
    assert resp.status_code == 200
    assert resp.json()["backtest_mode"] == "factor_based"

