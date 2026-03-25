"""
L4 场景测试 — 边界条件、极端情况、数据一致性验证
"""
import pytest
import asyncio
import uuid
import json
from sqlalchemy.ext.asyncio import async_sessionmaker
from sqlalchemy import text, select


# ── 复用辅助函数（从 test_flows 引入思路，本文件自包含）─────────────────────

async def _insert_completed_decision(db_engine, symbol="600519",
                                     final_direction="buy",
                                     recommended_weight=0.20,
                                     current_weight=0.18):
    sf = async_sessionmaker(db_engine, expire_on_commit=False)
    decision_id = str(uuid.uuid4())
    approval_id = str(uuid.uuid4())
    recs = json.dumps([{
        "symbol": symbol,
        "current_weight": current_weight,
        "recommended_weight": recommended_weight,
        "weight_delta": round(recommended_weight - current_weight, 4),
        "confidence_score": 0.70,
        "similar_cases": [],
    }])
    async with sf() as db:
        await db.execute(text(
            "INSERT INTO decision_runs "
            "(id,status,triggered_by,started_at,symbols,agent_signals,"
            "hallucination_events,recommendations,final_direction,risk_level) "
            "VALUES (:id,'completed','user','2026-01-01T10:00:00',"
            ":syms,'[]','[]',:recs,:dir,'low')"
        ), {"id": decision_id, "syms": json.dumps([symbol]),
            "recs": recs, "dir": final_direction})
        await db.execute(text(
            "INSERT INTO approval_records "
            "(id,decision_run_id,status,recommendations,created_at) "
            "VALUES (:id,:did,'pending',:recs,'2026-01-01T10:00:00')"
        ), {"id": approval_id, "did": decision_id, "recs": recs})
        await db.commit()
    return {"decision_id": decision_id, "approval_id": approval_id}


async def _get_weight(db_engine, symbol):
    sf = async_sessionmaker(db_engine, expire_on_commit=False)
    async with sf() as db:
        from models import PortfolioHolding
        r = await db.execute(select(PortfolioHolding).where(
            PortfolioHolding.symbol == symbol))
        h = r.scalars().first()
        return h.weight if h else None


# ═══════════════════════════════════════════════════════════════════════════════
# Scenario-01：重复触发分析
# ═══════════════════════════════════════════════════════════════════════════════

class TestScenario01RepeatAnalysis:

    @pytest.mark.asyncio
    async def test_multiple_triggers_create_separate_decisions(self, client):
        """连续触发3次，每次都是独立的决策记录"""
        ids = set()
        for _ in range(3):
            r = await client.post("/api/v1/decisions/trigger",
                                 json={"symbols": ["600519"]})
            assert r.status_code == 200
            ids.add(r.json()["id"])

        assert len(ids) == 3, "3次触发应产生3个不同的 decision_id"

        r = await client.get("/api/v1/decisions/")
        assert r.json()["total"] == 3

    @pytest.mark.asyncio
    async def test_each_trigger_creates_separate_approval(self, client, db_engine):
        """每次分析完成后，各自创建独立的待审批记录"""
        for _ in range(3):
            d = await _insert_completed_decision(db_engine)

        r = await client.get("/api/v1/approvals/?status=pending")
        assert r.json()["total"] == 3


# ═══════════════════════════════════════════════════════════════════════════════
# Scenario-02：权重边界值
# ═══════════════════════════════════════════════════════════════════════════════

class TestScenario02WeightBoundaries:

    @pytest.mark.asyncio
    @pytest.mark.parametrize("weight,expected_status", [
        (0.20,  200),   # 等于上限，合法
        (0.19,  200),   # 小于上限，合法
        (0.001, 200),   # 极小正数，合法
        (0.201, 422),   # 超过上限，非法
        (-0.01, 422),   # 负数，非法
    ])
    async def test_weight_boundary_values(self, client, db_engine, weight, expected_status):
        d = await _insert_completed_decision(db_engine)
        r = await client.put(f"/api/v1/approvals/{d['approval_id']}/modify", json={
            "modified_weights": {"600519": weight},
            "reviewed_by": "tester"
        })
        assert r.status_code == expected_status, \
            f"权重 {weight} 期望 {expected_status}，实际 {r.status_code}: {r.json()}"

    @pytest.mark.asyncio
    async def test_zero_weight_clears_holding(self, client, db_engine):
        """权重为 0 → 持仓记录删除"""
        await client.post("/api/v1/portfolio/", json={"symbol": "600519", "weight": 0.18})
        d = await _insert_completed_decision(db_engine)
        await client.put(f"/api/v1/approvals/{d['approval_id']}/modify", json={
            "modified_weights": {"600519": 0.0}, "reviewed_by": "tester"
        })
        assert await _get_weight(db_engine, "600519") is None, "权重为0时持仓应被删除"

    @pytest.mark.asyncio
    async def test_weight_at_exact_limit_is_allowed(self, client, db_engine):
        """恰好等于仓位上限时应该通过"""
        # 先确认上限是 0.20
        params = (await client.get("/api/v1/risk/params")).json()
        limit = params["max_position_weight"]

        d = await _insert_completed_decision(db_engine)
        r = await client.put(f"/api/v1/approvals/{d['approval_id']}/modify", json={
            "modified_weights": {"600519": limit},
            "reviewed_by": "tester"
        })
        assert r.status_code == 200, f"恰好等于上限 {limit} 应通过"


# ═══════════════════════════════════════════════════════════════════════════════
# Scenario-03：熔断等级对流程的影响
# ═══════════════════════════════════════════════════════════════════════════════

class TestScenario03CircuitBreakerLevels:

    @pytest.mark.asyncio
    @pytest.mark.parametrize("level,trigger_ok,approve_ok", [
        (0, True,  True),   # NORMAL：全部正常
        (1, True,  True),   # WARNING：允许操作
        (2, False, False),  # SUSPENDED：全部阻断
        (3, False, False),  # EMERGENCY：全部阻断
    ])
    async def test_circuit_breaker_behavior(self, client, db_engine, level, trigger_ok, approve_ok):
        sf = async_sessionmaker(db_engine, expire_on_commit=False)
        async with sf() as db:
            await db.execute(text(
                f"UPDATE risk_configs SET circuit_breaker_level={level} WHERE id=1"))
            await db.commit()

        trigger_r = await client.post("/api/v1/decisions/trigger",
                                     json={"symbols": ["600519"]})
        if trigger_ok:
            assert trigger_r.status_code == 200, \
                f"L{level} 时触发应返回 200，实际 {trigger_r.status_code}"
        else:
            assert trigger_r.status_code == 503, \
                f"L{level} 时触发应返回 503，实际 {trigger_r.status_code}"

        d = await _insert_completed_decision(db_engine)
        approve_r = await client.post(f"/api/v1/approvals/{d['approval_id']}/action",
                                     json={"action": "approved", "reviewed_by": "tester"})
        if approve_ok:
            assert approve_r.status_code == 200
        else:
            assert approve_r.status_code == 503

        # 恢复
        async with sf() as db:
            await db.execute(text("UPDATE risk_configs SET circuit_breaker_level=0 WHERE id=1"))
            await db.commit()


# ═══════════════════════════════════════════════════════════════════════════════
# Scenario-04：并发请求稳定性
# ═══════════════════════════════════════════════════════════════════════════════

class TestScenario04ConcurrentRequests:

    @pytest.mark.asyncio
    async def test_concurrent_triggers_all_succeed(self, client):
        """并发触发3次分析，系统不崩溃，全部返回独立 ID"""
        tasks = [
            client.post("/api/v1/decisions/trigger", json={"symbols": ["600519"]}),
            client.post("/api/v1/decisions/trigger", json={"symbols": ["300750"]}),
            client.post("/api/v1/decisions/trigger", json={"symbols": ["002594"]}),
        ]
        results = await asyncio.gather(*tasks)

        for r in results:
            assert r.status_code == 200
        ids = [r.json()["id"] for r in results]
        assert len(set(ids)) == 3, "并发触发应产生3个不同的 decision_id"

    @pytest.mark.asyncio
    async def test_concurrent_approvals_final_state_consistent(self, client, db_engine):
        """对同一审批多次操作，最终状态一致（只有一个生效）"""
        d = await _insert_completed_decision(db_engine)
        aid = d["approval_id"]

        # 串行操作（SQLite不支持真正的并发行锁）
        r1 = await client.post(f"/api/v1/approvals/{aid}/action",
                               json={"action": "approved", "reviewed_by": "user0"})
        r2 = await client.post(f"/api/v1/approvals/{aid}/action",
                               json={"action": "approved", "reviewed_by": "user1"})

        # 第一次成功，第二次409
        assert r1.status_code == 200
        assert r2.status_code == 409

        # 最终只有一个生效，审批状态确定
        detail = (await client.get(f"/api/v1/approvals/{aid}")).json()
        assert detail["status"] == "approved"
        assert detail["reviewed_by"] == "user0"  # 第一个操作者


# ═══════════════════════════════════════════════════════════════════════════════
# Scenario-05：数据一致性验证
# ═══════════════════════════════════════════════════════════════════════════════

class TestScenario05DataConsistency:

    @pytest.mark.asyncio
    async def test_portfolio_and_snapshot_always_consistent(self, client, db_engine):
        """每次审批通过后，持仓表和最新快照必须一致"""
        weights = [0.15, 0.18, 0.12]  # 三次不同权重

        for i, target_weight in enumerate(weights):
            d = await _insert_completed_decision(
                db_engine, recommended_weight=target_weight
            )
            if i % 2 == 0:
                # 偶数次：直接通过
                await client.post(f"/api/v1/approvals/{d['approval_id']}/action",
                                 json={"action": "approved", "reviewed_by": "tester"})
            else:
                # 奇数次：修改后通过
                await client.put(f"/api/v1/approvals/{d['approval_id']}/modify", json={
                    "modified_weights": {"600519": target_weight},
                    "reviewed_by": "tester"
                })

            # 每次都验证一致性
            portfolio = (await client.get("/api/v1/portfolio/")).json()["holdings"]
            portfolio_dict = {h["symbol"]: h["weight"] for h in portfolio}

            snaps = (await client.get("/api/v1/portfolio/snapshots")).json()["snapshots"]
            snap_holdings = snaps[0]["holdings"] if snaps else {}

            for sym, w in portfolio_dict.items():
                snap_w = snap_holdings.get(sym, -1)
                assert abs(snap_w - w) < 0.001, \
                    f"第{i+1}次操作后：{sym} 持仓={w} 快照={snap_w} 不一致"

    @pytest.mark.asyncio
    async def test_graph_node_count_matches_processed_approvals(self, client, db_engine):
        """每次审批操作（通过/拒绝）都创建一个图谱节点"""
        # 记录操作前的数量
        before = (await client.get("/api/v1/graph/nodes")).json()["total"]
        actions = ["approved", "rejected", "approved"]

        for action in actions:
            d = await _insert_completed_decision(db_engine)
            await client.post(f"/api/v1/approvals/{d['approval_id']}/action",
                             json={"action": action, "reviewed_by": "tester"})

        after = (await client.get("/api/v1/graph/nodes")).json()["total"]
        assert after == before + len(actions), \
            f"3次操作应新增3个节点，实际新增 {after - before} 个"


# ═══════════════════════════════════════════════════════════════════════════════
# Scenario-06：分页与列表查询
# ═══════════════════════════════════════════════════════════════════════════════

class TestScenario06PaginationAndFiltering:

    @pytest.mark.asyncio
    async def test_decisions_pagination(self, client, db_engine):
        """100条记录时分页正确"""
        sf = async_sessionmaker(db_engine, expire_on_commit=False)
        async with sf() as db:
            for i in range(25):
                await db.execute(text(
                    "INSERT INTO decision_runs "
                    "(id,status,triggered_by,started_at,symbols,agent_signals,"
                    "hallucination_events,recommendations) "
                    "VALUES (:id,'completed','user','2026-01-01T10:00:00',"
                    "'[\"600519\"]','[]','[]','[]')"
                ), {"id": str(uuid.uuid4())})
            await db.commit()

        r = await client.get("/api/v1/decisions/?page=1&page_size=10")
        assert r.status_code == 200
        d = r.json()
        assert len(d["items"]) == 10
        assert d["total"] == 25

        r2 = await client.get("/api/v1/decisions/?page=3&page_size=10")
        d2 = r2.json()
        assert len(d2["items"]) == 5  # 最后一页只有5条

    @pytest.mark.asyncio
    async def test_approvals_filter_by_status(self, client, db_engine):
        """按状态筛选审批列表"""
        # 创建3个待审批
        for _ in range(3):
            await _insert_completed_decision(db_engine)

        # 通过第1个
        approvals = (await client.get("/api/v1/approvals/?status=pending")).json()
        first_id = approvals["items"][0]["id"]
        await client.post(f"/api/v1/approvals/{first_id}/action",
                         json={"action": "approved", "reviewed_by": "tester"})

        # 验证筛选结果
        pending_r = (await client.get("/api/v1/approvals/?status=pending")).json()
        approved_r = (await client.get("/api/v1/approvals/?status=approved")).json()

        assert pending_r["total"] == 2
        assert approved_r["total"] == 1
        assert all(i["status"] == "pending" for i in pending_r["items"])
        assert all(i["status"] == "approved" for i in approved_r["items"])


# ═══════════════════════════════════════════════════════════════════════════════
# Scenario-07：持仓更新时保留非权重字段
# ═══════════════════════════════════════════════════════════════════════════════

class TestScenario07HoldingFieldPreservation:

    @pytest.mark.asyncio
    async def test_approve_preserves_cost_price_and_quantity(self, client, db_engine):
        """审批通过更新权重时，成本价和持股数量不被清空"""
        await client.post("/api/v1/portfolio/", json={
            "symbol": "600519",
            "weight": 0.18,
            "cost_price": 1680.0,
            "quantity": 100,
            "note": "核心仓位"
        })

        d = await _insert_completed_decision(
            db_engine, current_weight=0.18, recommended_weight=0.20
        )
        await client.post(f"/api/v1/approvals/{d['approval_id']}/action",
                         json={"action": "approved", "reviewed_by": "tester"})

        holdings = (await client.get("/api/v1/portfolio/")).json()["holdings"]
        h = next(x for x in holdings if x["symbol"] == "600519")

        assert abs(h["weight"] - 0.20) < 0.001, "权重应更新"
        assert h["cost_price"] == 1680.0, "成本价不应被清空"
        assert h["quantity"] == 100, "持股数量不应被清空"
        assert h["note"] == "核心仓位", "备注不应被清空"


# ═══════════════════════════════════════════════════════════════════════════════
# Scenario-08：风控参数变更隔离性
# ═══════════════════════════════════════════════════════════════════════════════

class TestScenario08RiskParamIsolation:

    @pytest.mark.asyncio
    async def test_risk_param_change_does_not_affect_existing_holdings(self, client, db_engine):
        """修改风控参数不会影响已有的持仓记录"""
        # 创建持仓 0.18
        await client.post("/api/v1/portfolio/", json={"symbol": "600519", "weight": 0.18})

        # 调低上限到 0.10（低于现有持仓）
        await client.put("/api/v1/risk/params", json={"max_position_weight": 0.10})

        # 已有持仓不受影响
        weight = await _get_weight(db_engine, "600519")
        assert abs(weight - 0.18) < 0.001, "修改风控参数不应改变已有持仓"

        # 恢复
        await client.put("/api/v1/risk/params", json={"max_position_weight": 0.20})

    @pytest.mark.asyncio
    async def test_updated_risk_params_persist_across_requests(self, client):
        """更新后的风控参数在后续请求中持久生效"""
        await client.put("/api/v1/risk/params", json={
            "max_position_weight": 0.25,
            "daily_loss_warning_threshold": 0.05
        })

        # 多次查询，确认参数持久
        for _ in range(3):
            params = (await client.get("/api/v1/risk/params")).json()
            assert abs(params["max_position_weight"] - 0.25) < 0.001
            assert abs(params["daily_loss_warning_threshold"] - 0.05) < 0.001

        # 恢复
        await client.put("/api/v1/risk/params", json={
            "max_position_weight": 0.20,
            "daily_loss_warning_threshold": 0.03
        })