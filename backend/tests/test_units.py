"""
单元测试 — Agent 逻辑、服务层、工具函数
全部 Mock 外部依赖，不需要网络和外部服务
"""
import pytest
import json
from unittest.mock import patch, AsyncMock, MagicMock


def test_mysql_config_has_required_fields(app_settings):
    assert app_settings.DB_HOST
    assert app_settings.DB_PORT == 3306
    assert app_settings.DB_USER
    assert app_settings.DB_NAME
    assert app_settings.mysql_dsn.startswith("mysql+asyncmy://")


def test_mysql_connection_settings_exports_expected_keys():
    from database import mysql_connection_settings

    config = mysql_connection_settings()

    assert config["host"]
    assert config["port"] == 3306
    assert config["user"]
    assert config["database"]
    assert str(config["dsn"]).startswith("mysql+asyncmy://")


class _FakeCursor:
    def __init__(self, fetchone_result=None, fetchall_result=None):
        self.fetchone_result = fetchone_result
        self.fetchall_result = fetchall_result or []
        self.executed = []
        self.description = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def execute(self, sql, params=None):
        self.executed.append((sql, params))
        if "SELECT" in sql:
            self.description = [
                ("id",), ("mode",), ("status",), ("triggered_by",), ("symbols",),
                ("candidate_symbols",), ("current_portfolio",), ("factor_snapshot_id",),
                ("factor_date",), ("strategy_version_id",), ("market_regime",),
                ("final_direction",), ("risk_level",), ("error_message",),
                ("started_at",), ("completed_at",),
            ]

    async def fetchone(self):
        return self.fetchone_result

    async def fetchall(self):
        return self.fetchall_result


class _FakeConnection:
    def __init__(self, cursor):
        self._cursor = cursor

    def cursor(self):
        return self._cursor


@pytest.mark.asyncio
async def test_insert_and_fetch_decision_run_query_helpers():
    from db.queries.decisions import get_decision_run, insert_decision_run

    insert_cursor = _FakeCursor()
    insert_conn = _FakeConnection(insert_cursor)
    decision_id = await insert_decision_run(insert_conn, {
        "id": "decision-1",
        "mode": "targeted",
        "symbols": ["600036"],
        "current_portfolio": {"600036": 0.1},
    })

    assert decision_id == "decision-1"
    assert insert_cursor.executed
    insert_sql, insert_params = insert_cursor.executed[0]
    assert "INSERT INTO decision_runs" in insert_sql
    assert insert_params["mode"] == "targeted"
    assert "600036" in insert_params["symbols"]

    row = (
        "decision-1", "targeted", "running", "user", '["600036"]', "[]", '{"600036": 0.1}',
        None, None, None, None, None, None, None, None, None,
    )
    fetch_cursor = _FakeCursor(fetchone_result=row)
    fetch_conn = _FakeConnection(fetch_cursor)
    fetched = await get_decision_run(fetch_conn, "decision-1")

    assert fetched is not None
    assert fetched["id"] == "decision-1"
    assert fetched["mode"] == "targeted"


# ═══════════════════════════════════════════════════════════════════════════════
# 技术分析规则引擎
# ═══════════════════════════════════════════════════════════════════════════════

class TestTechnicalRules:
    """规则引擎输出必须完全确定性 — 相同输入 = 相同输出"""

    def _snap(self, **kw):
        base = {
            "rsi": 50.0, "current_price": 100.0,
            # 默认均线无明确多空排列：price < ma20，ma20 > ma60（交叉状态）
            "ma20": 102.0, "ma60": 98.0,
            # MACD 空头（确保不触发多头排列）
            "macd": -0.1, "macd_signal": 0.1,
            "bb_upper": 108.0, "bb_lower": 92.0,
            "volume_ratio": 1.0,
        }
        base.update(kw)
        return base

    def _run(self, snap):
        from agents.cn_technical_agent import _run_rules
        return _run_rules(snap)

    # ── 超买超卖 ──────────────────────────────────────────────────────────────

    def test_rsi_80_extreme_overbought_sell(self):
        d, c, rule, _ = self._run(self._snap(rsi=81))
        assert d == "sell" and c == 0.85 and "极度超买" in rule

    def test_rsi_18_extreme_oversold_buy(self):
        d, c, rule, _ = self._run(self._snap(rsi=18))
        assert d == "buy" and c == 0.85 and "极度超卖" in rule

    def test_rsi_75_overbought_with_upper_band(self):
        d, c, _, _ = self._run(self._snap(rsi=75, current_price=106, bb_upper=105))
        assert d == "sell" and c == 0.80

    def test_rsi_75_overbought_without_upper_band(self):
        d, c, _, _ = self._run(self._snap(rsi=75, current_price=100, bb_upper=105))
        assert d == "sell" and c == 0.73

    def test_rsi_25_oversold_with_lower_band(self):
        d, c, _, _ = self._run(self._snap(rsi=25, current_price=93, bb_lower=95))
        assert d == "buy" and c == 0.80

    def test_rsi_25_oversold_without_lower_band(self):
        d, c, _, _ = self._run(self._snap(rsi=25, current_price=100, bb_lower=95))
        assert d == "buy" and c == 0.73

    # ── 趋势排列 ──────────────────────────────────────────────────────────────

    def test_bull_trend_with_volume(self):
        d, c, rule, _ = self._run(self._snap(
            rsi=55, current_price=100, ma20=98, ma60=94,
            macd=0.5, macd_signal=0.3, volume_ratio=1.8
        ))
        assert d == "buy" and c == 0.78 and "量能" in rule

    def test_bull_trend_without_volume(self):
        d, c, rule, _ = self._run(self._snap(
            rsi=55, current_price=100, ma20=98, ma60=94,
            macd=0.5, macd_signal=0.3, volume_ratio=1.0
        ))
        assert d == "buy" and c == 0.68

    def test_bear_trend(self):
        d, c, _, _ = self._run(self._snap(
            rsi=48, current_price=90, ma20=95, ma60=98,
            macd=-0.5, macd_signal=-0.3
        ))
        assert d == "sell" and c == 0.68

    # ── 布林带 ────────────────────────────────────────────────────────────────

    def test_price_above_upper_band(self):
        d, c, _, _ = self._run(self._snap(
            rsi=58, current_price=107, bb_upper=105,
            ma20=90, ma60=88  # 多头排列但幅度不够
        ))
        # rsi 58 不触发超买，没有完整多头排列条件，回退到布林带判断
        assert d in ("buy", "sell")  # 取决于均线条件

    def test_price_below_lower_band(self):
        d, c, _, _ = self._run(self._snap(
            rsi=42, current_price=93, bb_lower=95,
            ma20=100, ma60=102  # 空头排列但价格在下轨
        ))
        assert d in ("buy", "sell")

    # ── 震荡 ─────────────────────────────────────────────────────────────────

    def test_neutral_hold(self):
        d, c, _, _ = self._run(self._snap(rsi=50))
        assert d == "hold" and c == 0.50

    # ── 确定性 ────────────────────────────────────────────────────────────────

    def test_same_input_same_output_10_times(self):
        snap = self._snap(rsi=75, current_price=106, bb_upper=105)
        results = [self._run(snap)[:2] for _ in range(10)]
        assert len(set(results)) == 1  # 全部相同


# ═══════════════════════════════════════════════════════════════════════════════
# 持仓覆盖规则
# ═══════════════════════════════════════════════════════════════════════════════

class TestHoldingOverride:
    def _run(self, direction, confidence, pnl_pct, cost=100.0):
        from agents.cn_technical_agent import _holding_rule_override
        holding = {"pnl_pct": pnl_pct / 100, "cost_price": cost}
        return _holding_rule_override(direction, confidence, holding, cost * (1 + pnl_pct / 100))

    def test_profit_80_buy_to_hold(self):
        d, c, note = self._run("buy", 0.78, pnl_pct=85)
        assert d == "hold" and c == 0.50 and note

    def test_profit_80_hold_confidence_capped(self):
        d, c, note = self._run("hold", 0.78, pnl_pct=85)
        assert c <= 0.55 and note

    def test_profit_50_60_confidence_capped(self):
        d, c, note = self._run("buy", 0.78, pnl_pct=55)
        assert c <= 0.55 and note

    def test_loss_30_hold_confidence_reduced(self):
        d, c, note = self._run("hold", 0.68, pnl_pct=-35)
        assert d == "hold" and c <= 0.50 and note

    def test_no_holding_no_change(self):
        from agents.cn_technical_agent import _holding_rule_override
        d, c, note = _holding_rule_override("buy", 0.78, None, 100)
        assert d == "buy" and c == 0.78 and note is None

    def test_small_profit_no_override(self):
        d, c, note = self._run("buy", 0.78, pnl_pct=10)
        assert d == "buy" and c == 0.78 and note is None

    def test_small_loss_no_override(self):
        d, c, note = self._run("hold", 0.68, pnl_pct=-10)
        assert note is None

    def test_sell_signal_not_overridden_by_profit(self):
        """卖出信号不被浮盈覆盖（已经是对的方向）"""
        d, c, note = self._run("sell", 0.75, pnl_pct=60)
        assert d == "sell"


# ═══════════════════════════════════════════════════════════════════════════════
# 基本面数据级别判断
# ═══════════════════════════════════════════════════════════════════════════════

class TestFundamentalDataLevel:
    def _assess(self, fin):
        from agents.cn_fundamental_agent import _assess_data_level
        return _assess_data_level(fin)

    def test_none_is_C(self):
        assert self._assess(None) == ("C", 0.25)

    def test_empty_dict_is_C(self):
        assert self._assess({}) == ("C", 0.25)

    def test_only_pe_pb_is_B(self):
        lvl, conf = self._assess({"pe_ratio": 25.0, "pb_ratio": 2.0})
        assert lvl == "B" and conf == 0.60

    def test_only_total_mv_is_B(self):
        lvl, conf = self._assess({"total_mv": 5000.0})
        assert lvl == "B" and conf == 0.60

    def test_only_revenue_yoy_is_B(self):
        lvl, conf = self._assess({"revenue_yoy": "15%"})
        assert lvl == "B" and conf == 0.60

    def test_full_data_is_A(self):
        lvl, conf = self._assess({
            "pe_ratio": 25.0, "pb_ratio": 2.0, "total_mv": 5000.0,
            "revenue_yoy": "15%", "net_profit_yoy": "20%", "roe": "18%"
        })
        assert lvl == "A" and conf == 0.80

    def test_financial_only_is_B(self):
        """只有财务数据没有估值数据也是 B"""
        lvl, conf = self._assess({"revenue_yoy": "15%", "roe": "20%", "debt_ratio": "45%"})
        assert lvl == "B" and conf == 0.60


# ═══════════════════════════════════════════════════════════════════════════════
# 情绪评分逻辑
# ═══════════════════════════════════════════════════════════════════════════════

class TestSentimentScoring:

    @pytest.mark.asyncio
    async def test_buy_signal_when_score_high(self):
        with patch("services.cn_sentiment_data._fetch_comment_sync", return_value={"score": 72.0}), \
             patch("services.cn_sentiment_data._fetch_north_flow_sync", return_value={"total_flow": 50.0}), \
             patch("services.cn_sentiment_data._fetch_breadth_sync", return_value={
                 "limit_up_count": 120, "limit_down_count": 20, "sentiment_ratio": 0.86
             }):
            from services.cn_sentiment_data import build_sentiment_context
            _, direction, confidence = await build_sentiment_context("600519", rsi=50, vol_ratio=1.0)
            # score=72>65→+1.5, north=50>30→+1.0, ratio=0.86>0.7→+0.5, rsi=50→0 共+3.0
            assert direction == "buy"
            assert confidence > 0.50

    @pytest.mark.asyncio
    async def test_sell_signal_when_score_low(self):
        with patch("services.cn_sentiment_data._fetch_comment_sync", return_value={"score": 30.0}), \
             patch("services.cn_sentiment_data._fetch_north_flow_sync", return_value={"total_flow": -60.0}), \
             patch("services.cn_sentiment_data._fetch_breadth_sync", return_value={
                 "limit_up_count": 15, "limit_down_count": 80, "sentiment_ratio": 0.16
             }):
            from services.cn_sentiment_data import build_sentiment_context
            _, direction, _ = await build_sentiment_context("600519", rsi=75, vol_ratio=1.0)
            # score=30<40→-1.0, north=-60<-30→-1.0, ratio=0.16<0.3→-0.5, rsi=75>72→-2.0 共-4.5
            assert direction == "sell"

    @pytest.mark.asyncio
    async def test_hold_when_neutral(self):
        with patch("services.cn_sentiment_data._fetch_comment_sync", return_value={"score": 52.0}), \
             patch("services.cn_sentiment_data._fetch_north_flow_sync", return_value={"total_flow": 5.0}), \
             patch("services.cn_sentiment_data._fetch_breadth_sync", return_value={
                 "limit_up_count": 80, "limit_down_count": 60, "sentiment_ratio": 0.57
             }):
            from services.cn_sentiment_data import build_sentiment_context
            _, direction, confidence = await build_sentiment_context("600519", rsi=50, vol_ratio=1.0)
            assert direction == "hold"
            assert confidence == 0.48

    @pytest.mark.asyncio
    async def test_rsi_overbought_contributes_negative(self):
        with patch("services.cn_sentiment_data._fetch_comment_sync", return_value={"score": 52.0}), \
             patch("services.cn_sentiment_data._fetch_north_flow_sync", return_value={"total_flow": 0.0}), \
             patch("services.cn_sentiment_data._fetch_breadth_sync", return_value={
                 "limit_up_count": 60, "limit_down_count": 60, "sentiment_ratio": 0.50
             }):
            from services.cn_sentiment_data import build_sentiment_context
            _, direction_normal, _ = await build_sentiment_context("600519", rsi=50, vol_ratio=1.0)
            _, direction_overbought, _ = await build_sentiment_context("600519", rsi=75, vol_ratio=1.0)
            # rsi=75 会 -2.0 分，应该更倾向 sell 或 hold
            assert direction_overbought in ("sell", "hold")

    @pytest.mark.asyncio
    async def test_missing_data_no_crash(self):
        """部分数据获取失败时不应崩溃"""
        with patch("services.cn_sentiment_data._fetch_comment_sync", return_value=None), \
             patch("services.cn_sentiment_data._fetch_north_flow_sync", return_value=None), \
             patch("services.cn_sentiment_data._fetch_breadth_sync", return_value=None):
            from services.cn_sentiment_data import build_sentiment_context
            ctx, direction, confidence = await build_sentiment_context("600519", rsi=50, vol_ratio=1.0)
            assert direction in ("buy", "sell", "hold")
            assert 0 <= confidence <= 1


# ═══════════════════════════════════════════════════════════════════════════════
# Pipeline 投票逻辑
# ═══════════════════════════════════════════════════════════════════════════════

class TestPipelineVoting:

    def _sig(self, direction, confidence, weight, level="A"):
        snap = {"data_level": level}
        if level == "C":
            snap["data_available"] = False
        return {
            "agent_type": "test",
            "direction": direction,
            "confidence": confidence,
            "signal_weight": weight,
            "input_snapshot": snap,
        }

    def _context(self, weight=0.18):
        return {
            "symbols": ["600519"],
            "current_portfolio": {"600519": {"weight": weight}}
        }

    def test_buy_majority_increases_weight(self):
        from agents.pipeline import _make_recommendations
        signals = [
            self._sig("buy", 0.75, 0.25),
            self._sig("buy", 0.70, 0.25),
            self._sig("hold", 0.50, 0.20),
            self._sig("hold", 0.50, 0.15),
        ]
        recs = _make_recommendations(signals, self._context())
        assert recs[0]["weight_delta"] >= 0

    def test_sell_majority_decreases_weight(self):
        from agents.pipeline import _make_recommendations
        signals = [
            self._sig("sell", 0.75, 0.25),
            self._sig("sell", 0.70, 0.25),
            self._sig("sell", 0.65, 0.20),
            self._sig("hold", 0.50, 0.15),
        ]
        recs = _make_recommendations(signals, self._context())
        assert recs[0]["weight_delta"] <= 0

    def test_level_c_excluded_from_voting(self):
        from agents.pipeline import _make_recommendations
        signals = [
            self._sig("buy", 0.80, 0.25, "A"),
            self._sig("buy", 0.75, 0.25, "A"),
            self._sig("sell", 0.25, 0.20, "C"),  # 不参与
            self._sig("sell", 0.25, 0.15, "C"),  # 不参与
        ]
        recs = _make_recommendations(signals, self._context())
        # 2个buy（A级）应胜过2个sell（C级不参与）
        assert recs[0]["weight_delta"] >= 0

    def test_missing_agents_recorded(self):
        from agents.pipeline import _make_recommendations
        signals = [
            {"agent_type": "fundamental", "direction": "hold", "confidence": 0.25,
             "signal_weight": 0.25, "input_snapshot": {"data_level": "C", "data_available": False}},
        ]
        recs = _make_recommendations(signals, self._context())
        assert "fundamental" in recs[0]["missing_agents"]

    def test_no_valid_signals_forced_hold(self):
        from agents.pipeline import _make_recommendations
        signals = [
            self._sig("buy", 0.25, 0.25, "C"),
            self._sig("sell", 0.25, 0.25, "C"),
        ]
        recs = _make_recommendations(signals, self._context())
        assert recs[0]["weight_delta"] == 0.0  # hold 时不变

    def test_risk_check_position_limit(self):
        from agents.pipeline import _risk_check
        context = {
            "symbols": ["600519"],
            "current_portfolio": {"600519": {"weight": 0.20}}
        }
        level, _ = _risk_check([], context, {"max_position_weight": 0.20})
        assert level == "high"

    def test_risk_check_sell_majority(self):
        from agents.pipeline import _risk_check
        signals = [self._sig("sell", 0.75, 0.25)] * 3 + [self._sig("buy", 0.60, 0.25)]
        level, _ = _risk_check(signals, {"symbols": ["600519"], "current_portfolio": {}}, {})
        assert level == "high"

    def test_risk_check_buy_majority(self):
        from agents.pipeline import _risk_check
        signals = [self._sig("buy", 0.75, 0.25)] * 4
        level, _ = _risk_check(signals, {"symbols": ["600519"], "current_portfolio": {}}, {})
        assert level == "low"

    def test_risk_check_mixed_signals(self):
        from agents.pipeline import _risk_check
        signals = [
            self._sig("buy", 0.75, 0.25),
            self._sig("sell", 0.65, 0.25),
            self._sig("hold", 0.50, 0.20),
        ]
        level, _ = _risk_check(signals, {"symbols": ["600519"], "current_portfolio": {}}, {})
        assert level == "medium"

    def test_is_data_missing_c_level(self):
        from agents.pipeline import _is_data_missing
        assert _is_data_missing({"input_snapshot": {"data_level": "C", "data_available": False}})

    def test_is_data_missing_a_level(self):
        from agents.pipeline import _is_data_missing
        assert not _is_data_missing({"input_snapshot": {"data_level": "A"}})

    def test_is_data_missing_no_snapshot(self):
        from agents.pipeline import _is_data_missing
        assert not _is_data_missing({})


# ═══════════════════════════════════════════════════════════════════════════════
# 持仓上下文
# ═══════════════════════════════════════════════════════════════════════════════

class TestPortfolioContext:

    def test_get_holding_dict_format(self):
        from agents.portfolio_context import get_holding
        ctx = {"current_portfolio": {"600519": {"weight": 0.18, "cost_price": 1680.0, "pnl_pct": -0.15}}}
        h = get_holding(ctx, "600519")
        assert h["weight"] == 0.18
        assert h["cost_price"] == 1680.0

    def test_get_holding_float_format(self):
        """兼容旧格式"""
        from agents.portfolio_context import get_holding
        ctx = {"current_portfolio": {"600519": 0.18}}
        h = get_holding(ctx, "600519")
        assert h["weight"] == 0.18

    def test_get_holding_missing_symbol(self):
        from agents.portfolio_context import get_holding
        h = get_holding({"current_portfolio": {}}, "600519")
        assert h is None

    def test_get_holding_no_portfolio(self):
        from agents.portfolio_context import get_holding
        h = get_holding({}, "600519")
        assert h is None

    def test_format_holding_with_profit(self):
        from agents.portfolio_context import format_holding_context
        holding = {"weight": 0.18, "cost_price": 100.0, "current_price": 150.0,
                   "pnl_pct": 0.50, "quantity": 1000, "symbol_name": "贵州茅台"}
        text = format_holding_context(holding, "600519")
        assert "18.0%" in text
        assert "100" in text
        assert "+50" in text
        assert "浮盈" in text

    def test_format_holding_with_loss(self):
        from agents.portfolio_context import format_holding_context
        holding = {"weight": 0.10, "cost_price": 200.0, "current_price": 140.0, "pnl_pct": -0.30}
        text = format_holding_context(holding, "000001")
        assert "-30" in text

    def test_format_holding_none(self):
        from agents.portfolio_context import format_holding_context
        text = format_holding_context(None, "600519")
        assert "未持有" in text

    def test_format_holding_large_profit_warning(self):
        from agents.portfolio_context import format_holding_context
        holding = {"weight": 0.15, "cost_price": 100.0, "current_price": 160.0, "pnl_pct": 0.60}
        text = format_holding_context(holding, "600519")
        assert "止盈" in text or "浮盈" in text

    def test_format_holding_large_loss_warning(self):
        from agents.portfolio_context import format_holding_context
        holding = {"weight": 0.10, "cost_price": 100.0, "current_price": 65.0, "pnl_pct": -0.35}
        text = format_holding_context(holding, "600519")
        assert "止损" in text or "亏损" in text

    def test_portfolio_summary_format(self):
        from agents.portfolio_context import format_portfolio_summary
        ctx = {"current_portfolio": {
            "600519": {"weight": 0.18, "pnl_pct": -0.15, "symbol_name": "贵州茅台"},
            "300750": {"weight": 0.15, "pnl_pct": 1.07, "symbol_name": "宁德时代"},
        }}
        text = format_portfolio_summary(ctx)
        assert "18.0%" in text
        assert "15.0%" in text
        assert "总仓位" in text

    def test_portfolio_summary_empty(self):
        from agents.portfolio_context import format_portfolio_summary
        text = format_portfolio_summary({})
        assert "无持仓" in text


# ═══════════════════════════════════════════════════════════════════════════════
# 数据工具函数
# ═══════════════════════════════════════════════════════════════════════════════

class TestSymbolNormalization:
    def _n(self, s):
        from services.cn_market_data import _normalize_symbol
        return _normalize_symbol(s)

    def test_sz_lower(self): assert self._n("sz000629") == "000629"
    def test_sz_upper(self): assert self._n("SZ000629") == "000629"
    def test_sh_lower(self): assert self._n("sh600519") == "600519"
    def test_sh_upper(self): assert self._n("SH600519") == "600519"
    def test_bj_lower(self): assert self._n("bj430047") == "430047"
    def test_no_prefix(self): assert self._n("600519") == "600519"
    def test_whitespace(self): assert self._n("  600519  ") == "600519"
    def test_leading_zero_preserved(self): assert self._n("000001") == "000001"


class TestTechnicalIndicators:
    """RSI、MACD、布林带计算正确性"""

    def test_rsi_neutral_when_insufficient_data(self):
        from services.cn_market_data import _calc_rsi
        assert _calc_rsi([100.0] * 5) == 50.0  # 数据不足

    def test_rsi_100_all_up(self):
        from services.cn_market_data import _calc_rsi
        closes = list(range(100, 120))  # 一直涨
        rsi = _calc_rsi(closes)
        assert rsi > 70  # 应该超买

    def test_rsi_0_all_down(self):
        from services.cn_market_data import _calc_rsi
        closes = list(range(120, 100, -1))  # 一直跌
        rsi = _calc_rsi(closes)
        assert rsi < 30  # 应该超卖

    def test_rsi_range(self):
        from services.cn_market_data import _calc_rsi
        import random
        random.seed(42)
        closes = [100 + random.gauss(0, 2) for _ in range(30)]
        rsi = _calc_rsi(closes)
        assert 0 <= rsi <= 100

    def test_macd_positive_when_short_above_long(self):
        from services.cn_market_data import _calc_macd
        # 最近12天价格高于最近26天
        closes = [90.0] * 14 + [110.0] * 12
        macd, signal = _calc_macd(closes)
        assert macd > 0  # 短期均线在长期均线上方

    def test_bollinger_width(self):
        from services.cn_market_data import _calc_bollinger
        closes = [100.0] * 20
        upper, mid, lower = _calc_bollinger(closes)
        # 完全平坦时布林带应该很窄（标准差为0）
        assert upper == mid == lower

    def test_bollinger_volatile(self):
        from services.cn_market_data import _calc_bollinger
        import math
        closes = [100 + 5 * math.sin(i) for i in range(25)]
        upper, mid, lower = _calc_bollinger(closes)
        assert upper > mid > lower


# ═══════════════════════════════════════════════════════════════════════════════
# LLM 客户端 Mock 模式
# ═══════════════════════════════════════════════════════════════════════════════

class TestLLMClientMock:

    def test_mock_json_prompt_returns_valid_json(self):
        from agents.base import LLMClient
        client = LLMClient()
        with patch("agents.base.settings") as s:
            s.use_mock = True
            for _ in range(10):
                result = client._mock("请输出JSON格式分析", "分析600519")
                data = json.loads(result)
                assert data["direction"] in ("buy", "sell", "hold")
                assert 0 <= data["confidence"] <= 1
                assert "reasoning" in data

    def test_mock_text_prompt_returns_non_json(self):
        from agents.base import LLMClient
        client = LLMClient()
        with patch("agents.base.settings") as s:
            s.use_mock = True
            result = client._mock("写一段分析摘要，直接返回文字", "技术指标数据")
            try:
                json.loads(result)
                assert False, "应该是文字而非JSON"
            except json.JSONDecodeError:
                pass  # 正确

    def test_mock_json_confidence_in_range(self):
        from agents.base import LLMClient
        client = LLMClient()
        with patch("agents.base.settings") as s:
            s.use_mock = True
            for _ in range(20):
                result = client._mock("输出JSON", "data")
                data = json.loads(result)
                assert 0.0 <= data["confidence"] <= 1.0


# ═══════════════════════════════════════════════════════════════════════════════
# 回测引擎
# ═══════════════════════════════════════════════════════════════════════════════

class TestBacktestEngine:

    def test_run_backtest_returns_all_metrics(self):
        from services.backtest import run_backtest
        result = run_backtest(
            symbols=["600519", "300750"],
            start_date="2024-01-01",
            end_date="2024-06-30",
            initial_capital=1_000_000,
            benchmark="buy_and_hold",
            commission_rate=0.003,
            slippage=0.001,
            rebalance_frequency="weekly",
        )
        for key in ["total_return", "annualized_return", "sharpe_ratio",
                    "max_drawdown", "win_rate", "nav_curve"]:
            assert key in result, f"缺少字段: {key}"

    def test_run_backtest_nav_curve_starts_at_1(self):
        from services.backtest import run_backtest
        result = run_backtest(
            symbols=["600519", "300750"],
            start_date="2024-01-01",
            end_date="2024-03-31",
            initial_capital=1_000_000,
            benchmark="buy_and_hold",
            commission_rate=0.003,
            slippage=0.001,
            rebalance_frequency="weekly",
        )
        nav_curve = result["nav_curve"]
        assert len(nav_curve) > 0
        first_nav = nav_curve[0]["nav"] if isinstance(nav_curve[0], dict) else nav_curve[0]
        assert abs(first_nav - 1.0) < 0.01

    def test_run_backtest_too_short_raises(self):
        from services.backtest import run_backtest
        with pytest.raises(ValueError, match="too short"):
            run_backtest(
                symbols=["600519", "300750"],
                start_date="2024-01-01",
                end_date="2024-01-02",
                initial_capital=1_000_000,
                benchmark="buy_and_hold",
                commission_rate=0.003,
                slippage=0.001,
                rebalance_frequency="weekly",
            )

    def test_run_backtest_deterministic_with_same_seed(self):
        from services.backtest import run_backtest
        kwargs = dict(
            symbols=["600519", "300750"],
            start_date="2024-01-01",
            end_date="2024-06-30",
            initial_capital=1_000_000,
            benchmark="buy_and_hold",
            commission_rate=0.003,
            slippage=0.001,
            rebalance_frequency="weekly",
        )
        r1 = run_backtest(**kwargs)
        r2 = run_backtest(**kwargs)
        assert r1["total_return"] == r2["total_return"]

    def test_max_drawdown_non_positive(self):
        from services.backtest import run_backtest
        result = run_backtest(
            symbols=["600519", "300750"],
            start_date="2024-01-01",
            end_date="2024-06-30",
            initial_capital=1_000_000,
            benchmark="buy_and_hold",
            commission_rate=0.003,
            slippage=0.001,
            rebalance_frequency="weekly",
        )
        assert result["max_drawdown"] <= 0


# ═══════════════════════════════════════════════════════════════════════════════
# 经验图谱服务
# ═══════════════════════════════════════════════════════════════════════════════

class TestGraphService:

    def test_cosine_similarity_identical(self):
        from services.graph import _cosine_similarity
        v = [1.0, 2.0, 3.0]
        assert abs(_cosine_similarity(v, v) - 1.0) < 1e-6

    def test_cosine_similarity_orthogonal(self):
        from services.graph import _cosine_similarity
        a = [1.0, 0.0]
        b = [0.0, 1.0]
        assert abs(_cosine_similarity(a, b)) < 1e-6

    def test_cosine_similarity_empty(self):
        from services.graph import _cosine_similarity
        assert _cosine_similarity([], []) == 0.0

    def test_cosine_similarity_different_length(self):
        from services.graph import _cosine_similarity
        assert _cosine_similarity([1.0, 2.0], [1.0]) == 0.0

    def test_make_embedding_deterministic(self):
        from services.graph import _make_embedding
        e1 = _make_embedding(["600519"], "buy")
        e2 = _make_embedding(["600519"], "buy")
        assert e1 == e2

    def test_make_embedding_different_for_different_input(self):
        from services.graph import _make_embedding
        e1 = _make_embedding(["600519"], "buy")
        e2 = _make_embedding(["300750"], "buy")
        assert e1 != e2

    def test_make_embedding_length_32(self):
        from services.graph import _make_embedding
        e = _make_embedding(["600519"], "hold")
        assert len(e) == 32


class TestSchedulerAndNav:

    def test_scheduler_registers_factor_nav_and_settlement_jobs(self):
        from services.scheduler import build_scheduler

        jobs = build_scheduler().get_jobs()
        job_ids = {job.id for job in jobs}

        assert "factor_engine_daily" in job_ids
        assert "portfolio_nav_daily" in job_ids
        assert "t5_settlement_daily" in job_ids

    def test_build_nav_snapshot_is_deterministic(self):
        from services.nav_calculator import build_nav_snapshot

        holdings = [
            {"symbol": "600519", "weight": 0.20, "market_value": 200000, "pnl_pct": 0.10},
            {"symbol": "300750", "weight": 0.15, "market_value": 150000, "pnl_pct": -0.05},
        ]
        snapshot = build_nav_snapshot(holdings, "2026-04-03")

        assert snapshot["trade_date"] == "2026-04-03"
        assert snapshot["holding_count"] == 2
        assert snapshot["gross_exposure"] == 0.35
        assert snapshot["nav"] == 1.0125
        assert snapshot["cash_weight"] == 0.65
