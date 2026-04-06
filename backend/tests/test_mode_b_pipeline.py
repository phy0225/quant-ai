import pytest


def _sig(direction, confidence, weight, level="A"):
    snapshot = {"data_level": level}
    if level == "C":
        snapshot["data_available"] = False
    return {
        "agent_type": "test",
        "direction": direction,
        "confidence": confidence,
        "signal_weight": weight,
        "input_snapshot": snapshot,
    }


def _context(weight=0.18, factor_score=0.76):
    return {
        "symbols": ["600519"],
        "current_portfolio": {"600519": {"weight": weight}},
        "factor_context": {
            "factor_date": "2026-04-03",
            "market_regime": "bullish",
            "scored_stocks": {"600519": factor_score},
        },
    }


def test_mode_b_same_input_produces_same_rebalance_orders():
    from agents.pipeline import _make_recommendations

    signals = [
        _sig("buy", 0.75, 0.25),
        _sig("buy", 0.70, 0.25),
        _sig("hold", 0.50, 0.20),
        _sig("hold", 0.50, 0.15),
    ]
    context = _context()

    first = _make_recommendations(signals, context)
    second = _make_recommendations(signals, context)

    assert first == second


@pytest.mark.asyncio
async def test_build_factor_context_returns_scores_for_symbols():
    from agents.factor_context import build_factor_context

    context = await build_factor_context(
        symbols=["600519"],
        candidate_symbols=["300750"],
        factor_snapshot={
            "trade_date": "2026-04-03",
            "market_regime": "bullish",
            "effective_factors": [{"factor_key": "momentum_20d"}],
            "stock_scores": {"600519": 0.81, "300750": 0.44},
        },
    )

    assert context["factor_date"] == "2026-04-03"
    assert context["market_regime"] == "bullish"
    assert context["scored_stocks"]["600519"] == 0.81
    assert context["scored_stocks"]["300750"] == 0.44


def test_base_agent_factor_hint_formats_snapshot():
    from agents.base import BaseAgent

    agent = BaseAgent()
    hint, snapshot = agent._factor_hint(
        {
            "factor_context": {
                "factor_date": "2026-04-03",
                "market_regime": "bullish",
                "factor_count": 3,
                "scored_stocks": {"600519": 0.81},
            }
        },
        "600519",
    )

    assert hint is not None
    assert "score=0.81" in hint
    assert snapshot["factor_bias"] == "positive"
