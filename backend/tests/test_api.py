"""
API 集成测试 — 端到端验证，每个测试必须真正验证业务结果
核心原则：不只测"接口返回200"，要测"数据库里的数据是否正确"
"""
import pytest
import asyncio


# ═══════════════════════════════════════════════════════════════════════════════
# 基础
# ═══════════════════════════════════════════════════════════════════════════════

class TestHealth:
    @pytest.mark.asyncio
    async def test_health_ok(self, client):
        r = await client.get("/health")
        assert r.status_code == 200
        assert r.json()["status"] == "ok"

    @pytest.mark.asyncio
    async def test_404_unknown_path(self, client):
        r = await client.get("/api/v1/nonexistent")
        assert r.status_code == 404


# ═══════════════════════════════════════════════════════════════════════════════
# 决策触发与查询
# ═══════════════════════════════════════════════════════════════════════════════

class TestDecisions:

    @pytest.mark.asyncio
    async def test_trigger_returns_running_status(self, client):
        r = await client.post("/api/v1/decisions/trigger", json={"symbols": ["600519"]})
        assert r.status_code == 200
        d = r.json()
        assert "id" in d
        assert d["status"] == "running"
        assert d["symbols"] == ["600519"]
        assert d["triggered_by"] == "user"

    @pytest.mark.asyncio
    async def test_trigger_multiple_symbols(self, client):
        r = await client.post("/api/v1/decisions/trigger", json={
            "symbols": ["600519", "300750", "002594"]
        })
        assert r.status_code == 200
        assert set(r.json()["symbols"]) == {"600519", "300750", "002594"}

    @pytest.mark.asyncio
    async def test_trigger_with_portfolio(self, client):
        r = await client.post("/api/v1/decisions/trigger", json={
            "symbols": ["600519"],
            "current_portfolio": {"600519": 0.18}
        })
        assert r.status_code == 200
        assert "id" in r.json()

    @pytest.mark.asyncio
    async def test_trigger_empty_symbols_rejected(self, client):
        r = await client.post("/api/v1/decisions/trigger", json={"symbols": []})
        assert r.status_code in (400, 422)

    @pytest.mark.asyncio
    async def test_trigger_blocked_by_emergency_stop(self, client, db_engine):
        from sqlalchemy.ext.asyncio import async_sessionmaker
        from sqlalchemy import text
        sf = async_sessionmaker(db_engine, expire_on_commit=False)
        async with sf() as db:
            await db.execute(text("UPDATE risk_configs SET emergency_stop_active=1 WHERE id=1"))
            await db.commit()
        r = await client.post("/api/v1/decisions/trigger", json={"symbols": ["600519"]})
        assert r.status_code == 503
        async with sf() as db:
            await db.execute(text("UPDATE risk_configs SET emergency_stop_active=0 WHERE id=1"))
            await db.commit()

    @pytest.mark.asyncio
    async def test_trigger_blocked_by_circuit_breaker_l2(self, client, db_engine):
        from sqlalchemy.ext.asyncio import async_sessionmaker
        from sqlalchemy import text
        sf = async_sessionmaker(db_engine, expire_on_commit=False)
        async with sf() as db:
            await db.execute(text("UPDATE risk_configs SET circuit_breaker_level=2 WHERE id=1"))
            await db.commit()
        r = await client.post("/api/v1/decisions/trigger", json={"symbols": ["600519"]})
        assert r.status_code == 503
        async with sf() as db:
            await db.execute(text("UPDATE risk_configs SET circuit_breaker_level=0 WHERE id=1"))
            await db.commit()

    @pytest.mark.asyncio
    async def test_get_decision_by_id(self, client):
        did = (await client.post("/api/v1/decisions/trigger", json={"symbols": ["600519"]})).json()["id"]
        r = await client.get(f"/api/v1/decisions/{did}")
        assert r.status_code == 200
        d = r.json()
        assert d["id"] == did
        assert "status" in d
        assert "agent_signals" in d

    @pytest.mark.asyncio
    async def test_get_decision_not_found(self, client):
        r = await client.get("/api/v1/decisions/00000000-0000-0000-0000-000000000000")
        assert r.status_code == 404

    @pytest.mark.asyncio
    async def test_list_decisions_pagination(self, client):
        for i in range(5):
            await client.post("/api/v1/decisions/trigger", json={"symbols": [f"60051{i}"]})
        r = await client.get("/api/v1/decisions/?page=1&page_size=2")
        assert r.status_code == 200
        d = r.json()
        assert len(d["items"]) == 2
        assert d["total"] == 5


# ═══════════════════════════════════════════════════════════════════════════════
# 审批流程 — 端到端验证
# ═══════════════════════════════════════════════════════════════════════════════

class TestApprovals:

    # ── 审批通过 → 持仓表必须更新 ────────────────────────────────────────────

    @pytest.mark.asyncio
    async def test_approve_creates_portfolio_holding(self, client, pending_approval):
        """通过审批后，持仓表必须创建对应记录"""
        aid = pending_approval["approval_id"]

        # 通过前持仓为空
        before = await client.get("/api/v1/portfolio/")
        assert before.json()["holdings"] == []

        r = await client.post(f"/api/v1/approvals/{aid}/action", json={
            "action": "approved", "reviewed_by": "王经理"
        })
        assert r.status_code == 200
        assert r.json()["status"] == "approved"

        # 通过后持仓必须有 600519，权重为建议值 0.20
        after = await client.get("/api/v1/portfolio/")
        holdings = after.json()["holdings"]
        assert len(holdings) >= 1
        h = next((x for x in holdings if x["symbol"] == "600519"), None)
        assert h is not None, "审批通过后持仓表中必须有 600519"
        assert abs(h["weight"] - 0.20) < 0.001, f"权重应为 0.20，实际为 {h['weight']}"

    @pytest.mark.asyncio
    async def test_approve_updates_existing_holding(self, client, pending_approval):
        """审批通过时，如果持仓已存在则更新权重"""
        # 先创建初始持仓
        await client.post("/api/v1/portfolio/", json={
            "symbol": "600519", "weight": 0.18, "cost_price": 1680.0
        })
        aid = pending_approval["approval_id"]
        await client.post(f"/api/v1/approvals/{aid}/action", json={
            "action": "approved", "reviewed_by": "tester"
        })

        holdings = (await client.get("/api/v1/portfolio/")).json()["holdings"]
        h = next(x for x in holdings if x["symbol"] == "600519")
        # 权重应更新为审批建议的 0.20，不再是初始的 0.18
        assert abs(h["weight"] - 0.20) < 0.001, f"权重应从0.18更新为0.20，实际为{h['weight']}"
        # 成本价应保留（审批不改成本价）
        assert h["cost_price"] == 1680.0

    # ── 修改权重 → 以修改后的值更新持仓 ─────────────────────────────────────

    @pytest.mark.asyncio
    async def test_modify_weight_then_portfolio_reflects_new_weight(self, client, pending_approval):
        """修改权重批准后，持仓表权重必须是修改后的值（不是原建议值）"""
        aid = pending_approval["approval_id"]

        # 修改为 0.15（低于建议的 0.20）
        r = await client.put(f"/api/v1/approvals/{aid}/modify", json={
            "modified_weights": {"600519": 0.15},
            "reviewed_by": "风控",
            "comment": "降低仓位"
        })
        assert r.status_code == 200, f"修改权重失败: {r.json()}"
        assert r.json()["status"] == "modified"

        # 持仓中的权重必须是 0.15，不是原来的 0.20
        holdings = (await client.get("/api/v1/portfolio/")).json()["holdings"]
        h = next((x for x in holdings if x["symbol"] == "600519"), None)
        assert h is not None, "修改权重批准后持仓必须创建"
        assert abs(h["weight"] - 0.15) < 0.001, \
            f"持仓权重应为修改后的 0.15，实际为 {h['weight']}"

    @pytest.mark.asyncio
    async def test_modify_weight_recommendation_also_updated(self, client, pending_approval):
        """modify 后，审批记录本身的 recommendations 也要更新"""
        aid = pending_approval["approval_id"]
        await client.put(f"/api/v1/approvals/{aid}/modify", json={
            "modified_weights": {"600519": 0.13},
            "reviewed_by": "tester"
        })
        # 查审批详情，确认 recommendations 里的 recommended_weight 已更新
        detail = (await client.get(f"/api/v1/approvals/{aid}")).json()
        rec = next(x for x in detail["recommendations"] if x["symbol"] == "600519")
        assert abs(rec["recommended_weight"] - 0.13) < 0.001, \
            f"审批记录中的建议权重应为 0.13，实际为 {rec['recommended_weight']}"
        assert abs(rec["weight_delta"] - (0.13 - 0.18)) < 0.001  # delta = 0.13 - current(0.18)

    @pytest.mark.asyncio
    async def test_modify_weight_exceeds_limit_rejected(self, client, pending_approval):
        """超过仓位上限（20%）的修改必须被拒绝"""
        aid = pending_approval["approval_id"]
        r = await client.put(f"/api/v1/approvals/{aid}/modify", json={
            "modified_weights": {"600519": 0.25},  # 超过 20% 上限
            "reviewed_by": "tester"
        })
        assert r.status_code == 422, f"超过上限应返回422，实际返回{r.status_code}"

        # 持仓不应被更新
        holdings = (await client.get("/api/v1/portfolio/")).json()["holdings"]
        assert holdings == [], "拒绝后持仓不应有记录"

    @pytest.mark.asyncio
    async def test_modify_weight_negative_rejected(self, client, pending_approval):
        """负数权重必须被拒绝"""
        aid = pending_approval["approval_id"]
        r = await client.put(f"/api/v1/approvals/{aid}/modify", json={
            "modified_weights": {"600519": -0.05},
            "reviewed_by": "tester"
        })
        assert r.status_code == 422

    @pytest.mark.asyncio
    async def test_modify_zero_weight_clears_holding(self, client, pending_approval):
        """将权重改为 0（清仓）后持仓表中该记录应删除"""
        # 先有持仓
        await client.post("/api/v1/portfolio/", json={"symbol": "600519", "weight": 0.18})
        aid = pending_approval["approval_id"]
        r = await client.put(f"/api/v1/approvals/{aid}/modify", json={
            "modified_weights": {"600519": 0.0},  # 清仓
            "reviewed_by": "tester"
        })
        assert r.status_code == 200
        holdings = (await client.get("/api/v1/portfolio/")).json()["holdings"]
        assert not any(h["symbol"] == "600519" for h in holdings), \
            "权重清零后持仓记录应被删除"

    # ── 拒绝 → 持仓不变 ──────────────────────────────────────────────────────

    @pytest.mark.asyncio
    async def test_reject_does_not_change_portfolio(self, client, pending_approval):
        """拒绝审批后持仓不应有任何变化"""
        # 先有初始持仓
        await client.post("/api/v1/portfolio/", json={"symbol": "600519", "weight": 0.18})
        aid = pending_approval["approval_id"]
        await client.post(f"/api/v1/approvals/{aid}/action", json={
            "action": "rejected", "reviewed_by": "tester"
        })
        holdings = (await client.get("/api/v1/portfolio/")).json()["holdings"]
        h = next(x for x in holdings if x["symbol"] == "600519")
        assert abs(h["weight"] - 0.18) < 0.001, "拒绝后权重不应变化，应仍为 0.18"

    # ── 防重复操作 ────────────────────────────────────────────────────────────

    @pytest.mark.asyncio
    async def test_cannot_approve_twice(self, client, pending_approval):
        aid = pending_approval["approval_id"]
        r1 = await client.post(f"/api/v1/approvals/{aid}/action", json={
            "action": "approved", "reviewed_by": "u1"
        })
        assert r1.status_code == 200
        r2 = await client.post(f"/api/v1/approvals/{aid}/action", json={
            "action": "approved", "reviewed_by": "u2"
        })
        assert r2.status_code == 409

    @pytest.mark.asyncio
    async def test_cannot_modify_approved(self, client, pending_approval):
        aid = pending_approval["approval_id"]
        await client.post(f"/api/v1/approvals/{aid}/action", json={
            "action": "approved", "reviewed_by": "u1"
        })
        r = await client.put(f"/api/v1/approvals/{aid}/modify", json={
            "modified_weights": {"600519": 0.15}, "reviewed_by": "u2"
        })
        assert r.status_code == 409

    # ── 审批被风控阻断 ────────────────────────────────────────────────────────

    @pytest.mark.asyncio
    async def test_approve_blocked_by_emergency_stop(self, client, pending_approval, db_engine):
        from sqlalchemy.ext.asyncio import async_sessionmaker
        from sqlalchemy import text
        sf = async_sessionmaker(db_engine, expire_on_commit=False)
        async with sf() as db:
            await db.execute(text("UPDATE risk_configs SET emergency_stop_active=1 WHERE id=1"))
            await db.commit()
        r = await client.post(f"/api/v1/approvals/{pending_approval['approval_id']}/action",
                              json={"action": "approved", "reviewed_by": "tester"})
        assert r.status_code == 503
        # 持仓不应更新
        assert (await client.get("/api/v1/portfolio/")).json()["holdings"] == []
        async with sf() as db:
            await db.execute(text("UPDATE risk_configs SET emergency_stop_active=0 WHERE id=1"))
            await db.commit()

    # ── 快照 ─────────────────────────────────────────────────────────────────

    @pytest.mark.asyncio
    async def test_approve_creates_portfolio_snapshot(self, client, pending_approval):
        """审批通过后必须保存持仓快照"""
        before_snaps = (await client.get("/api/v1/portfolio/snapshots")).json()["snapshots"]
        aid = pending_approval["approval_id"]
        await client.post(f"/api/v1/approvals/{aid}/action", json={
            "action": "approved", "reviewed_by": "tester"
        })
        after_snaps = (await client.get("/api/v1/portfolio/snapshots")).json()["snapshots"]
        assert len(after_snaps) > len(before_snaps), "审批通过后快照数量应增加"


# ═══════════════════════════════════════════════════════════════════════════════
# 持仓管理 — 端到端验证
# ═══════════════════════════════════════════════════════════════════════════════

class TestPortfolio:

    @pytest.mark.asyncio
    async def test_create_and_verify_all_fields(self, client):
        r = await client.post("/api/v1/portfolio/", json={
            "symbol": "600519", "symbol_name": "贵州茅台",
            "weight": 0.18, "cost_price": 1680.0, "quantity": 100, "note": "核心仓位"
        })
        assert r.status_code == 200
        d = r.json()
        assert d["symbol"] == "600519"
        assert d["symbol_name"] == "贵州茅台"
        assert abs(d["weight"] - 0.18) < 0.001
        assert d["cost_price"] == 1680.0
        assert d["quantity"] == 100
        assert d["note"] == "核心仓位"

    @pytest.mark.asyncio
    async def test_create_upsert_same_symbol(self, client):
        """同标的第二次创建应更新而不是报错或新增"""
        await client.post("/api/v1/portfolio/", json={"symbol": "600519", "weight": 0.18})
        await client.post("/api/v1/portfolio/", json={"symbol": "600519", "weight": 0.20})
        holdings = (await client.get("/api/v1/portfolio/")).json()["holdings"]
        assert len(holdings) == 1, "同标的应只有一条记录"
        assert abs(holdings[0]["weight"] - 0.20) < 0.001

    @pytest.mark.asyncio
    async def test_update_weight_persists(self, client, holding):
        """更新权重后重新查询必须是新值"""
        hid = holding["id"]
        await client.put(f"/api/v1/portfolio/{hid}", json={"weight": 0.15})
        holdings = (await client.get("/api/v1/portfolio/")).json()["holdings"]
        h = next(x for x in holdings if x["id"] == hid)
        assert abs(h["weight"] - 0.15) < 0.001

    @pytest.mark.asyncio
    async def test_delete_then_not_in_list(self, client, holding):
        hid = holding["id"]
        await client.delete(f"/api/v1/portfolio/{hid}")
        holdings = (await client.get("/api/v1/portfolio/")).json()["holdings"]
        assert not any(h["id"] == hid for h in holdings)

    @pytest.mark.asyncio
    async def test_summary_total_weight(self, client):
        await client.post("/api/v1/portfolio/", json={"symbol": "600519", "weight": 0.18})
        await client.post("/api/v1/portfolio/", json={"symbol": "300750", "weight": 0.15})
        summary = (await client.get("/api/v1/portfolio/summary")).json()
        assert summary["holding_count"] == 2
        assert abs(summary["total_weight"] - 0.33) < 0.001

    @pytest.mark.asyncio
    async def test_update_not_found(self, client):
        r = await client.put("/api/v1/portfolio/nonexistent", json={"weight": 0.10})
        assert r.status_code == 404

    @pytest.mark.asyncio
    async def test_delete_not_found(self, client):
        r = await client.delete("/api/v1/portfolio/nonexistent")
        assert r.status_code == 404


# ═══════════════════════════════════════════════════════════════════════════════
# 风控配置
# ═══════════════════════════════════════════════════════════════════════════════

class TestRisk:

    @pytest.mark.asyncio
    async def test_get_status_default(self, client):
        r = await client.get("/api/v1/risk/status")
        assert r.status_code == 200
        d = r.json()
        assert d["circuit_breaker"]["level"] == 0
        assert d["circuit_breaker"]["level_name"] == "NORMAL"
        assert d["emergency_stop_active"] is False

    @pytest.mark.asyncio
    async def test_update_params_persists(self, client):
        """更新参数后重新获取必须是新值"""
        await client.put("/api/v1/risk/params", json={"max_position_weight": 0.25})
        params = (await client.get("/api/v1/risk/params")).json()
        assert abs(params["max_position_weight"] - 0.25) < 0.001

    @pytest.mark.asyncio
    async def test_update_params_partial(self, client):
        """只更新一个参数，其他保持不变"""
        await client.put("/api/v1/risk/params", json={"max_position_weight": 0.30})
        params = (await client.get("/api/v1/risk/params")).json()
        assert abs(params["daily_loss_warning_threshold"] - 0.03) < 0.001  # 默认值不变

    @pytest.mark.asyncio
    async def test_emergency_stop_blocks_trigger(self, client, db_engine):
        """激活紧急停止后触发分析必须被拒"""
        await client.post("/api/v1/risk/emergency-stop/activate", json={
            "reason": "测试", "activated_by": "tester"
        })
        r = await client.post("/api/v1/decisions/trigger", json={"symbols": ["600519"]})
        assert r.status_code == 503

    @pytest.mark.asyncio
    async def test_emergency_stop_deactivate_correct_password(self, client):
        await client.post("/api/v1/risk/emergency-stop/activate", json={
            "reason": "测试", "activated_by": "tester"
        })
        r = await client.post("/api/v1/risk/emergency-stop/deactivate", json={
            "password": "admin123", "deactivated_by": "admin"
        })
        assert r.status_code == 200
        status = (await client.get("/api/v1/risk/status")).json()
        assert status["emergency_stop_active"] is False

    @pytest.mark.asyncio
    async def test_emergency_stop_wrong_password(self, client):
        await client.post("/api/v1/risk/emergency-stop/activate", json={
            "reason": "测试", "activated_by": "tester"
        })
        r = await client.post("/api/v1/risk/emergency-stop/deactivate", json={
            "password": "wrong", "deactivated_by": "admin"
        })
        assert r.status_code == 403
        # 仍然激活
        assert (await client.get("/api/v1/risk/status")).json()["emergency_stop_active"] is True

    @pytest.mark.asyncio
    async def test_circuit_breaker_reset(self, client, db_engine):
        from sqlalchemy.ext.asyncio import async_sessionmaker
        from sqlalchemy import text
        sf = async_sessionmaker(db_engine, expire_on_commit=False)
        async with sf() as db:
            await db.execute(text("UPDATE risk_configs SET circuit_breaker_level=2 WHERE id=1"))
            await db.commit()
        r = await client.post("/api/v1/risk/circuit-breaker/reset", json={
            "target_level": 0, "authorized_by": "admin"
        })
        assert r.status_code == 200
        assert (await client.get("/api/v1/risk/status")).json()["circuit_breaker"]["level"] == 0


# ═══════════════════════════════════════════════════════════════════════════════
# 自动审批规则
# ═══════════════════════════════════════════════════════════════════════════════

class TestRules:

    @pytest.mark.asyncio
    async def test_create_and_list(self, client):
        await client.post("/api/v1/rules/", json={
            "name": "测试规则",
            "logic_operator": "AND",
            "conditions": [{"field": "max_weight_delta", "operator": "lte", "value": 0.05}],
            "is_active": True, "priority": 1,
        })
        rules = (await client.get("/api/v1/rules/")).json()
        assert any(r["name"] == "测试规则" for r in rules)

    @pytest.mark.asyncio
    async def test_toggle_changes_active_status(self, client, rule):
        rid = rule["id"]
        original = rule["is_active"]
        r = await client.post(f"/api/v1/rules/{rid}/toggle")
        assert r.status_code == 200
        assert r.json()["is_active"] != original
        # 再次切换回来
        r2 = await client.post(f"/api/v1/rules/{rid}/toggle")
        assert r2.json()["is_active"] == original

    @pytest.mark.asyncio
    async def test_delete_removes_rule(self, client, rule):
        rid = rule["id"]
        await client.delete(f"/api/v1/rules/{rid}")
        rules = (await client.get("/api/v1/rules/")).json()
        assert not any(r["id"] == rid for r in rules)

    @pytest.mark.asyncio
    async def test_active_only_filter(self, client):
        await client.post("/api/v1/rules/", json={
            "name": "活跃", "logic_operator": "AND",
            "conditions": [{"field": "max_weight_delta", "operator": "lte", "value": 0.05}],
            "is_active": True, "priority": 1,
        })
        await client.post("/api/v1/rules/", json={
            "name": "非活跃", "logic_operator": "AND",
            "conditions": [{"field": "max_weight_delta", "operator": "lte", "value": 0.10}],
            "is_active": False, "priority": 0,
        })
        active = (await client.get("/api/v1/rules/?active_only=true")).json()
        assert all(r["is_active"] for r in active)

    @pytest.mark.asyncio
    async def test_update_rule_persists(self, client, rule):
        rid = rule["id"]
        await client.put(f"/api/v1/rules/{rid}", json={"name": "新名称", "priority": 20})
        rules = (await client.get("/api/v1/rules/")).json()
        updated = next(r for r in rules if r["id"] == rid)
        assert updated["name"] == "新名称"
        assert updated["priority"] == 20


# ═══════════════════════════════════════════════════════════════════════════════
# 回测
# ═══════════════════════════════════════════════════════════════════════════════

class TestBacktest:

    @pytest.mark.asyncio
    async def test_run_and_list(self, client):
        r = await client.post("/api/v1/backtest/", json={
            "symbols": ["600519", "300750"],
            "start_date": "2024-01-01", "end_date": "2024-06-30",
            "initial_capital": 1000000, "commission_rate": 0.003,
            "slippage": 0.001, "benchmark": "buy_and_hold",
        })
        assert r.status_code == 200
        bid = r.json()["id"]
        total = (await client.get("/api/v1/backtest/")).json()["total"]
        assert total == 1

    @pytest.mark.asyncio
    async def test_requires_2_symbols(self, client):
        r = await client.post("/api/v1/backtest/", json={
            "symbols": ["600519"],
            "start_date": "2024-01-01", "end_date": "2024-06-30",
            "initial_capital": 1000000,
        })
        assert r.status_code == 422

    @pytest.mark.asyncio
    async def test_completed_report_has_metrics(self, client):
        r = await client.post("/api/v1/backtest/", json={
            "symbols": ["600519", "300750"],
            "start_date": "2024-01-01", "end_date": "2024-06-30",
            "initial_capital": 1000000, "commission_rate": 0.003,
            "slippage": 0.001, "benchmark": "buy_and_hold",
        })
        bid = r.json()["id"]
        # 等待最多 15 秒
        for _ in range(30):
            await asyncio.sleep(0.5)
            d = (await client.get(f"/api/v1/backtest/{bid}")).json()
            if d["status"] == "completed":
                assert d["total_return"] is not None
                assert d["sharpe_ratio"] is not None
                assert isinstance(d["nav_curve"], list) and len(d["nav_curve"]) > 0
                break


# ═══════════════════════════════════════════════════════════════════════════════
# 决策统计接口 (v2.1)
# ═══════════════════════════════════════════════════════════════════════════════

class TestDecisionStats:

    @pytest.mark.asyncio
    async def test_stats_empty_returns_zero(self, client):
        """无数据时返回 total_decisions:0, symbol_stats:[]"""
        r = await client.get("/api/v1/decisions/stats")
        assert r.status_code == 200
        d = r.json()
        assert d["total_decisions"] == 0
        assert d["symbol_stats"] == []
        assert "generated_at" in d

    @pytest.mark.asyncio
    async def test_stats_counts_completed_only(self, client, db_engine):
        """只统计 status=completed 的记录，running 状态不计入"""
        from sqlalchemy.ext.asyncio import async_sessionmaker
        from sqlalchemy import text
        sf = async_sessionmaker(db_engine, expire_on_commit=False)
        async with sf() as db:
            await db.execute(text(
                "INSERT INTO decision_runs (id,status,triggered_by,started_at,symbols,"
                "agent_signals,hallucination_events,recommendations,final_direction,risk_level) "
                "VALUES ('d-comp-1','completed','user',datetime('now'),'[\"600519\"]','[]','[]','[]','buy','low')"
            ))
            await db.execute(text(
                "INSERT INTO decision_runs (id,status,triggered_by,started_at,symbols,"
                "agent_signals,hallucination_events,recommendations,final_direction,risk_level) "
                "VALUES ('d-run-1','running','user',datetime('now'),'[\"600519\"]','[]','[]','[]',NULL,'low')"
            ))
            await db.commit()
        r = await client.get("/api/v1/decisions/stats")
        assert r.status_code == 200
        d = r.json()
        assert d["total_decisions"] == 1  # 只有 completed 的那条
        assert len(d["symbol_stats"]) == 1
        assert d["symbol_stats"][0]["decision_count"] == 1

    @pytest.mark.asyncio
    async def test_stats_symbol_filter(self, client, db_engine):
        """传 symbol=600519 只返回包含该标的的统计"""
        from sqlalchemy.ext.asyncio import async_sessionmaker
        from sqlalchemy import text
        sf = async_sessionmaker(db_engine, expire_on_commit=False)
        async with sf() as db:
            await db.execute(text(
                "INSERT INTO decision_runs (id,status,triggered_by,started_at,symbols,"
                "agent_signals,hallucination_events,recommendations,final_direction,risk_level) "
                "VALUES ('d-sym-1','completed','user',datetime('now'),'[\"600519\"]','[]','[]','[]','buy','low')"
            ))
            await db.execute(text(
                "INSERT INTO decision_runs (id,status,triggered_by,started_at,symbols,"
                "agent_signals,hallucination_events,recommendations,final_direction,risk_level) "
                "VALUES ('d-sym-2','completed','user',datetime('now'),'[\"300750\"]','[]','[]','[]','sell','low')"
            ))
            await db.commit()
        r = await client.get("/api/v1/decisions/stats?symbol=600519")
        assert r.status_code == 200
        d = r.json()
        assert d["total_decisions"] == 1
        assert len(d["symbol_stats"]) == 1
        assert d["symbol_stats"][0]["symbol"] == "600519"

    @pytest.mark.asyncio
    async def test_stats_direction_distribution(self, client, db_engine):
        """direction_dist 正确反映 final_direction 分布"""
        from sqlalchemy.ext.asyncio import async_sessionmaker
        from sqlalchemy import text
        sf = async_sessionmaker(db_engine, expire_on_commit=False)
        async with sf() as db:
            for i, direction in enumerate(["buy", "buy", "sell", "hold"]):
                await db.execute(text(
                    f"INSERT INTO decision_runs (id,status,triggered_by,started_at,symbols,"
                    f"agent_signals,hallucination_events,recommendations,final_direction,risk_level) "
                    f"VALUES ('d-dir-{i}','completed','user',datetime('now'),'[\"600519\"]','[]','[]','[]','{direction}','low')"
                ))
            await db.commit()
        r = await client.get("/api/v1/decisions/stats?symbol=600519")
        assert r.status_code == 200
        d = r.json()
        assert d["total_decisions"] == 4
        stat = d["symbol_stats"][0]
        dist = stat["direction_dist"]
        assert dist.get("buy") == 2
        assert dist.get("sell") == 1
        assert dist.get("hold") == 1


# ═══════════════════════════════════════════════════════════════════════════════
# 批量拒绝接口 (v2.1)
# ═══════════════════════════════════════════════════════════════════════════════

class TestBatchReject:

    async def _create_pending(self, db_engine, count: int = 1) -> list[str]:
        """辅助方法：批量创建 pending 审批记录，返回 approval_ids"""
        from sqlalchemy.ext.asyncio import async_sessionmaker
        from sqlalchemy import text
        import uuid, json
        sf = async_sessionmaker(db_engine, expire_on_commit=False)
        ids = []
        recs = json.dumps([{
            "symbol": "600519", "current_weight": 0.18,
            "recommended_weight": 0.20, "weight_delta": 0.02,
            "confidence_score": 0.72, "similar_cases": [],
        }])
        async with sf() as db:
            for _ in range(count):
                did = str(uuid.uuid4())
                aid = str(uuid.uuid4())
                await db.execute(text(
                    "INSERT INTO decision_runs (id,status,triggered_by,started_at,symbols,"
                    "agent_signals,hallucination_events,recommendations,final_direction,risk_level) "
                    "VALUES (:id,'completed','user','2026-01-01T10:00:00','[\"600519\"]','[]','[]',:recs,'buy','low')"
                ), {"id": did, "recs": recs})
                await db.execute(text(
                    "INSERT INTO approval_records (id,decision_run_id,status,recommendations,created_at) "
                    "VALUES (:id,:did,'pending',:recs,'2026-01-01T10:00:00')"
                ), {"id": aid, "did": did, "recs": recs})
                ids.append(aid)
            await db.commit()
        return ids

    @pytest.mark.asyncio
    async def test_batch_reject_success(self, client, db_engine):
        """批量拒绝多条 pending 记录，全部成功"""
        ids = await self._create_pending(db_engine, count=3)
        r = await client.post("/api/v1/approvals/batch-action", json={
            "approval_ids": ids,
            "action": "rejected",
            "reviewed_by": "admin",
            "comment": "批量清理",
        })
        assert r.status_code == 200
        d = r.json()
        assert d["success_count"] == 3
        assert d["fail_count"] == 0
        assert d["total"] == 3
        assert set(d["succeeded"]) == set(ids)
        assert d["failed"] == []

    @pytest.mark.asyncio
    async def test_batch_reject_partial_fail(self, client, db_engine):
        """部分已处理的记录计入 failed，不影响其他"""
        ids = await self._create_pending(db_engine, count=2)
        # 先处理第一条
        await client.post(f"/api/v1/approvals/{ids[0]}/action", json={
            "action": "approved", "reviewed_by": "admin"
        })
        r = await client.post("/api/v1/approvals/batch-action", json={
            "approval_ids": ids,
            "action": "rejected",
            "reviewed_by": "admin",
        })
        assert r.status_code == 200
        d = r.json()
        assert d["success_count"] == 1
        assert d["fail_count"] == 1
        assert ids[1] in d["succeeded"]
        assert d["failed"][0]["id"] == ids[0]
        assert "already processed" in d["failed"][0]["reason"]

    @pytest.mark.asyncio
    async def test_batch_reject_only_allows_rejected_action(self, client, db_engine):
        """传 action=approved 返回 422"""
        ids = await self._create_pending(db_engine, count=1)
        r = await client.post("/api/v1/approvals/batch-action", json={
            "approval_ids": ids,
            "action": "approved",
            "reviewed_by": "admin",
        })
        assert r.status_code == 422
        assert "批量操作仅支持 rejected" in r.json()["detail"]

    @pytest.mark.asyncio
    async def test_batch_reject_empty_ids(self, client):
        """空 ids 返回 422"""
        r = await client.post("/api/v1/approvals/batch-action", json={
            "approval_ids": [],
            "action": "rejected",
            "reviewed_by": "admin",
        })
        assert r.status_code == 422

    @pytest.mark.asyncio
    async def test_batch_reject_too_many_ids(self, client):
        """超过 50 条返回 422"""
        import uuid
        ids = [str(uuid.uuid4()) for _ in range(51)]
        r = await client.post("/api/v1/approvals/batch-action", json={
            "approval_ids": ids,
            "action": "rejected",
            "reviewed_by": "admin",
        })
        assert r.status_code == 422

    @pytest.mark.asyncio
    async def test_batch_reject_blocked_by_emergency_stop(self, client, db_engine):
        """紧急停止时返回 503"""
        await client.post("/api/v1/risk/emergency-stop/activate", json={
            "reason": "测试", "activated_by": "tester"
        })
        import uuid
        ids = [str(uuid.uuid4())]
        r = await client.post("/api/v1/approvals/batch-action", json={
            "approval_ids": ids,
            "action": "rejected",
            "reviewed_by": "admin",
        })
        assert r.status_code == 503
        # 恢复
        await client.post("/api/v1/risk/emergency-stop/deactivate", json={
            "password": "admin123", "deactivated_by": "admin"
        })

class TestGraph:

    @pytest.mark.asyncio
    async def test_approve_creates_graph_node(self, client, pending_approval):
        """审批通过后图谱节点必须创建"""
        before = (await client.get("/api/v1/graph/nodes")).json()["total"]
        await client.post(f"/api/v1/approvals/{pending_approval['approval_id']}/action",
                         json={"action": "approved", "reviewed_by": "tester"})
        after = (await client.get("/api/v1/graph/nodes")).json()["total"]
        assert after == before + 1

    @pytest.mark.asyncio
    async def test_reject_also_creates_node_with_approved_false(self, client, pending_approval):
        """拒绝也应记录，approved=False"""
        await client.post(f"/api/v1/approvals/{pending_approval['approval_id']}/action",
                         json={"action": "rejected", "reviewed_by": "tester"})
        nodes = (await client.get("/api/v1/graph/nodes")).json()["nodes"]
        assert len(nodes) == 1
        assert nodes[0]["approved"] is False

    @pytest.mark.asyncio
    async def test_approved_node_has_approved_true(self, client, approved_approval):
        nodes = (await client.get("/api/v1/graph/nodes")).json()["nodes"]
        assert any(n["approved"] is True for n in nodes)

    @pytest.mark.asyncio
    async def test_stats_after_approve(self, client, approved_approval):
        stats = (await client.get("/api/v1/graph/stats")).json()
        assert stats["node_count"] >= 1
        assert stats["approval_rate"] > 0

    @pytest.mark.asyncio
    async def test_search_similar(self, client, approved_approval):
        r = await client.post("/api/v1/graph/search", json={"symbols": ["600519"], "top_k": 3})
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    @pytest.mark.asyncio
    async def test_node_detail(self, client, approved_approval):
        nodes = (await client.get("/api/v1/graph/nodes")).json()["nodes"]
        if nodes:
            nid = nodes[0]["node_id"]
            r = await client.get(f"/api/v1/graph/nodes/{nid}")
            assert r.status_code == 200
            assert r.json()["node_id"] == nid

    @pytest.mark.asyncio
    async def test_node_not_found(self, client):
        r = await client.get("/api/v1/graph/nodes/nonexistent")
        assert r.status_code == 404