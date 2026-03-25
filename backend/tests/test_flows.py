"""
L3 流程测试 — 跨接口的完整业务流程验证
每个测试都直接验证数据库状态，不只看 HTTP 返回码
"""
import pytest
import asyncio
import uuid
import json
from sqlalchemy.ext.asyncio import async_sessionmaker
from sqlalchemy import text, select


# ── 辅助函数 ──────────────────────────────────────────────────────────────────

async def get_holding_weight(db_engine, symbol: str) -> float | None:
    """直接查数据库获取持仓权重"""
    sf = async_sessionmaker(db_engine, expire_on_commit=False)
    async with sf() as db:
        from models import PortfolioHolding
        result = await db.execute(
            select(PortfolioHolding).where(PortfolioHolding.symbol == symbol)
        )
        h = result.scalars().first()
        return h.weight if h else None


async def get_snapshot_count(db_engine) -> int:
    sf = async_sessionmaker(db_engine, expire_on_commit=False)
    async with sf() as db:
        result = await db.execute(text("SELECT COUNT(*) FROM portfolio_snapshots"))
        return result.scalar() or 0


async def get_graph_node_count(db_engine) -> int:
    sf = async_sessionmaker(db_engine, expire_on_commit=False)
    async with sf() as db:
        result = await db.execute(text("SELECT COUNT(*) FROM graph_nodes"))
        return result.scalar() or 0


async def insert_decision_with_approval(db_engine, symbol="600519",
                                         current_weight=0.18, recommended_weight=0.20,
                                         final_direction="buy", agent_signals=None):
    """直接插入完整的决策+审批记录，跳过耗时的 pipeline"""
    sf = async_sessionmaker(db_engine, expire_on_commit=False)
    decision_id = str(uuid.uuid4())
    approval_id = str(uuid.uuid4())
    weight_delta = round(recommended_weight - current_weight, 4)

    if agent_signals is None:
        agent_signals = [
            {"agent_type": "technical",   "direction": final_direction, "confidence": 0.75,
             "signal_weight": 0.25, "input_snapshot": {"data_level": "A"}},
            {"agent_type": "fundamental", "direction": final_direction, "confidence": 0.70,
             "signal_weight": 0.25, "input_snapshot": {"data_level": "A"}},
            {"agent_type": "news",        "direction": final_direction, "confidence": 0.65,
             "signal_weight": 0.20, "input_snapshot": {"data_level": "A"}},
            {"agent_type": "sentiment",   "direction": final_direction, "confidence": 0.62,
             "signal_weight": 0.15, "input_snapshot": {"data_level": "A"}},
            {"agent_type": "risk",        "direction": None,            "confidence": 1.0,
             "signal_weight": 0.10, "input_snapshot": {}},
            {"agent_type": "executor",    "direction": final_direction, "confidence": 0.70,
             "signal_weight": 0.05, "input_snapshot": {}},
        ]

    recs = json.dumps([{
        "symbol": symbol,
        "current_weight": current_weight,
        "recommended_weight": recommended_weight,
        "weight_delta": weight_delta,
        "confidence_score": 0.72,
        "similar_cases": [],
    }])

    async with sf() as db:
        await db.execute(text(
            "INSERT INTO decision_runs "
            "(id,status,triggered_by,started_at,symbols,agent_signals,"
            "hallucination_events,recommendations,final_direction,risk_level) "
            "VALUES (:id,'completed','user','2026-01-01T10:00:00',"
            ":syms,:sigs,'[]',:recs,:dir,'low')"
        ), {
            "id": decision_id,
            "syms": json.dumps([symbol]),
            "sigs": json.dumps(agent_signals),
            "recs": recs,
            "dir": final_direction,
        })
        await db.execute(text(
            "INSERT INTO approval_records "
            "(id,decision_run_id,status,recommendations,created_at) "
            "VALUES (:id,:did,'pending',:recs,'2026-01-01T10:00:00')"
        ), {"id": approval_id, "did": decision_id, "recs": recs})
        await db.commit()

    return {"decision_id": decision_id, "approval_id": approval_id,
            "symbol": symbol, "recommended_weight": recommended_weight,
            "current_weight": current_weight}


# ═══════════════════════════════════════════════════════════════════════════════
# Flow-01：完整决策流程 — 触发→审批→持仓更新→快照→图谱
# ═══════════════════════════════════════════════════════════════════════════════

class TestFlow01CompleteDecisionFlow:

    @pytest.mark.asyncio
    async def test_approve_updates_portfolio_weight(self, client, db_engine):
        """审批通过后，持仓权重必须更新为 recommended_weight"""
        d = await insert_decision_with_approval(
            db_engine, symbol="600519", current_weight=0.18, recommended_weight=0.20
        )
        before_weight = await get_holding_weight(db_engine, "600519")
        assert before_weight is None  # 通过前持仓不存在

        await client.post(f"/api/v1/approvals/{d['approval_id']}/action",
                         json={"action": "approved", "reviewed_by": "tester"})

        after_weight = await get_holding_weight(db_engine, "600519")
        assert after_weight is not None, "审批通过后持仓记录必须存在"
        assert abs(after_weight - 0.20) < 0.001, \
            f"持仓权重应为 0.20，实际为 {after_weight}"

    @pytest.mark.asyncio
    async def test_approve_creates_snapshot(self, client, db_engine):
        """审批通过后必须生成快照"""
        before_count = await get_snapshot_count(db_engine)
        d = await insert_decision_with_approval(db_engine)
        await client.post(f"/api/v1/approvals/{d['approval_id']}/action",
                         json={"action": "approved", "reviewed_by": "tester"})

        after_count = await get_snapshot_count(db_engine)
        assert after_count == before_count + 1

    @pytest.mark.asyncio
    async def test_snapshot_holdings_match_portfolio(self, client, db_engine):
        """快照的 holdings 字段必须与持仓表完全一致"""
        d = await insert_decision_with_approval(
            db_engine, symbol="600519", recommended_weight=0.20
        )
        await client.post(f"/api/v1/approvals/{d['approval_id']}/action",
                         json={"action": "approved", "reviewed_by": "tester"})

        # 获取持仓
        portfolio_r = await client.get("/api/v1/portfolio/")
        holdings_dict = {h["symbol"]: h["weight"]
                        for h in portfolio_r.json()["holdings"]}

        # 获取最新快照
        snap_r = await client.get("/api/v1/portfolio/snapshots")
        latest_snap = snap_r.json()["snapshots"][0]

        for symbol, weight in holdings_dict.items():
            snap_weight = latest_snap["holdings"].get(symbol)
            assert snap_weight is not None, f"快照中缺少标的 {symbol}"
            assert abs(snap_weight - weight) < 0.001, \
                f"{symbol}: 快照权重 {snap_weight} != 持仓权重 {weight}"

    @pytest.mark.asyncio
    async def test_approve_creates_graph_node_with_correct_approved_flag(self, client, db_engine):
        """审批通过 → 图谱节点 approved=True；拒绝 → approved=False"""
        before = await get_graph_node_count(db_engine)

        # 通过一条
        d1 = await insert_decision_with_approval(db_engine, symbol="600519")
        await client.post(f"/api/v1/approvals/{d1['approval_id']}/action",
                         json={"action": "approved", "reviewed_by": "tester"})

        # 拒绝一条
        d2 = await insert_decision_with_approval(db_engine, symbol="600519")
        await client.post(f"/api/v1/approvals/{d2['approval_id']}/action",
                         json={"action": "rejected", "reviewed_by": "tester"})

        after = await get_graph_node_count(db_engine)
        assert after == before + 2

        nodes = (await client.get("/api/v1/graph/nodes")).json()["nodes"]
        approved_nodes = [n for n in nodes if n["approved"] is True]
        rejected_nodes = [n for n in nodes if n["approved"] is False]
        assert len(approved_nodes) >= 1
        assert len(rejected_nodes) >= 1


# ═══════════════════════════════════════════════════════════════════════════════
# Flow-02：修改权重 — 持仓必须反映修改后的值
# ═══════════════════════════════════════════════════════════════════════════════

class TestFlow02ModifyWeightPersistence:

    @pytest.mark.asyncio
    async def test_modified_weight_not_original_recommendation(self, client, db_engine):
        """持仓权重必须是用户修改后的值，不是原建议值"""
        d = await insert_decision_with_approval(
            db_engine, current_weight=0.18, recommended_weight=0.20
        )
        await client.put(f"/api/v1/approvals/{d['approval_id']}/modify", json={
            "modified_weights": {"600519": 0.12},
            "reviewed_by": "tester"
        })

        weight = await get_holding_weight(db_engine, "600519")
        assert weight is not None
        assert abs(weight - 0.12) < 0.001, f"应为修改后的 0.12，实际为 {weight}"
        assert abs(weight - 0.20) > 0.001, "不应是原建议值 0.20"
        assert abs(weight - 0.18) > 0.001, "不应是原始权重 0.18"

    @pytest.mark.asyncio
    async def test_approval_record_reflects_modified_weight(self, client, db_engine):
        """审批记录的 recommendations 也要更新为修改后的值"""
        d = await insert_decision_with_approval(
            db_engine, current_weight=0.18, recommended_weight=0.20
        )
        await client.put(f"/api/v1/approvals/{d['approval_id']}/modify", json={
            "modified_weights": {"600519": 0.13},
            "reviewed_by": "tester"
        })

        detail = (await client.get(f"/api/v1/approvals/{d['approval_id']}")).json()
        rec = next(r for r in detail["recommendations"] if r["symbol"] == "600519")
        assert abs(rec["recommended_weight"] - 0.13) < 0.001
        assert abs(rec["weight_delta"] - (0.13 - 0.18)) < 0.001  # -0.05

    @pytest.mark.asyncio
    async def test_zero_weight_deletes_holding(self, client, db_engine):
        """权重设为 0 等同于清仓，持仓记录应被删除"""
        await client.post("/api/v1/portfolio/", json={"symbol": "600519", "weight": 0.18})
        d = await insert_decision_with_approval(db_engine)

        await client.put(f"/api/v1/approvals/{d['approval_id']}/modify", json={
            "modified_weights": {"600519": 0.0},
            "reviewed_by": "tester"
        })

        weight = await get_holding_weight(db_engine, "600519")
        assert weight is None, "权重为0时持仓记录应被删除"

    @pytest.mark.asyncio
    async def test_modify_then_snapshot_reflects_new_weight(self, client, db_engine):
        """修改权重后，快照也反映修改后的值"""
        d = await insert_decision_with_approval(db_engine, recommended_weight=0.20)
        await client.put(f"/api/v1/approvals/{d['approval_id']}/modify", json={
            "modified_weights": {"600519": 0.11},
            "reviewed_by": "tester"
        })

        snap_r = await client.get("/api/v1/portfolio/snapshots")
        snaps = snap_r.json()["snapshots"]
        assert len(snaps) >= 1
        snap_weight = snaps[0]["holdings"].get("600519")
        assert snap_weight is not None
        assert abs(snap_weight - 0.11) < 0.001


# ═══════════════════════════════════════════════════════════════════════════════
# Flow-03：拒绝审批不改变持仓
# ═══════════════════════════════════════════════════════════════════════════════

class TestFlow03RejectPreservesPortfolio:

    @pytest.mark.asyncio
    async def test_reject_does_not_update_weight(self, client, db_engine):
        """拒绝后持仓权重保持原值"""
        await client.post("/api/v1/portfolio/", json={"symbol": "600519", "weight": 0.18})
        d = await insert_decision_with_approval(db_engine, recommended_weight=0.20)

        await client.post(f"/api/v1/approvals/{d['approval_id']}/action",
                         json={"action": "rejected", "reviewed_by": "tester"})

        weight = await get_holding_weight(db_engine, "600519")
        assert weight is not None
        assert abs(weight - 0.18) < 0.001, f"拒绝后权重应保持 0.18，实际为 {weight}"

    @pytest.mark.asyncio
    async def test_reject_does_not_create_snapshot(self, client, db_engine):
        """拒绝不产生快照"""
        await client.post("/api/v1/portfolio/", json={"symbol": "600519", "weight": 0.18})
        before = await get_snapshot_count(db_engine)

        d = await insert_decision_with_approval(db_engine)
        await client.post(f"/api/v1/approvals/{d['approval_id']}/action",
                         json={"action": "rejected", "reviewed_by": "tester"})

        after = await get_snapshot_count(db_engine)
        assert after == before, "拒绝不应创建快照"


# ═══════════════════════════════════════════════════════════════════════════════
# Flow-04：风控参数联动拦截
# ═══════════════════════════════════════════════════════════════════════════════

class TestFlow04RiskParamsEnforcement:

    @pytest.mark.asyncio
    async def test_lower_limit_blocks_previously_valid_weight(self, client, db_engine):
        """降低仓位上限后，之前合法的权重变为非法"""
        # 先确认默认上限 0.20 时 0.18 是合法的
        d1 = await insert_decision_with_approval(db_engine, recommended_weight=0.18)
        r1 = await client.put(f"/api/v1/approvals/{d1['approval_id']}/modify", json={
            "modified_weights": {"600519": 0.18}, "reviewed_by": "tester"
        })
        assert r1.status_code == 200

        # 调低上限到 0.10
        await client.put("/api/v1/risk/params", json={"max_position_weight": 0.10})

        # 现在 0.18 应该被拒绝
        d2 = await insert_decision_with_approval(db_engine, recommended_weight=0.18)
        r2 = await client.put(f"/api/v1/approvals/{d2['approval_id']}/modify", json={
            "modified_weights": {"600519": 0.18}, "reviewed_by": "tester"
        })
        assert r2.status_code == 422, f"调低上限后 0.18 应被拒绝，实际返回 {r2.status_code}"

        # 恢复默认
        await client.put("/api/v1/risk/params", json={"max_position_weight": 0.20})

    @pytest.mark.asyncio
    async def test_raise_limit_allows_previously_blocked_weight(self, client, db_engine):
        """提高仓位上限后，之前被拦截的权重变为合法"""
        # 先确认 0.20 上限时 0.25 是非法的
        d1 = await insert_decision_with_approval(db_engine)
        r1 = await client.put(f"/api/v1/approvals/{d1['approval_id']}/modify", json={
            "modified_weights": {"600519": 0.25}, "reviewed_by": "tester"
        })
        assert r1.status_code == 422

        # 调高上限到 0.30
        await client.put("/api/v1/risk/params", json={"max_position_weight": 0.30})

        # 现在 0.25 应该合法
        d2 = await insert_decision_with_approval(db_engine)
        r2 = await client.put(f"/api/v1/approvals/{d2['approval_id']}/modify", json={
            "modified_weights": {"600519": 0.25}, "reviewed_by": "tester"
        })
        assert r2.status_code == 200, f"调高上限后 0.25 应成功，实际返回 {r2.status_code}"

        # 恢复
        await client.put("/api/v1/risk/params", json={"max_position_weight": 0.20})


# ═══════════════════════════════════════════════════════════════════════════════
# Flow-05：紧急停止全链路阻断
# ═══════════════════════════════════════════════════════════════════════════════

class TestFlow05EmergencyStopBlocksAll:

    @pytest.mark.asyncio
    async def test_emergency_stop_blocks_trigger_and_approve(self, client, db_engine):
        """紧急停止激活后，触发分析和审批都被阻断，且持仓不变"""
        await client.post("/api/v1/portfolio/", json={"symbol": "600519", "weight": 0.18})
        d = await insert_decision_with_approval(db_engine)

        # 激活紧急停止
        await client.post("/api/v1/risk/emergency-stop/activate",
                         json={"reason": "测试", "activated_by": "tester"})

        # 触发分析被阻断
        r1 = await client.post("/api/v1/decisions/trigger", json={"symbols": ["600519"]})
        assert r1.status_code == 503

        # 审批被阻断
        r2 = await client.post(f"/api/v1/approvals/{d['approval_id']}/action",
                               json={"action": "approved", "reviewed_by": "tester"})
        assert r2.status_code == 503

        # 持仓未变
        weight = await get_holding_weight(db_engine, "600519")
        assert abs(weight - 0.18) < 0.001

        # 解除
        await client.post("/api/v1/risk/emergency-stop/deactivate",
                         json={"password": "admin123", "deactivated_by": "admin"})

    @pytest.mark.asyncio
    async def test_operations_resume_after_deactivation(self, client, db_engine):
        """解除紧急停止后，操作恢复正常"""
        await client.post("/api/v1/risk/emergency-stop/activate",
                         json={"reason": "测试", "activated_by": "tester"})
        await client.post("/api/v1/risk/emergency-stop/deactivate",
                         json={"password": "admin123", "deactivated_by": "admin"})

        # 解除后可以正常触发
        r = await client.post("/api/v1/decisions/trigger", json={"symbols": ["600519"]})
        assert r.status_code == 200

        # 解除后可以正常审批
        d = await insert_decision_with_approval(db_engine)
        r2 = await client.post(f"/api/v1/approvals/{d['approval_id']}/action",
                               json={"action": "approved", "reviewed_by": "tester"})
        assert r2.status_code == 200


# ═══════════════════════════════════════════════════════════════════════════════
# Flow-06：多标的分析，只更新分析范围内的标的
# ═══════════════════════════════════════════════════════════════════════════════

class TestFlow06MultiSymbolIsolation:

    @pytest.mark.asyncio
    async def test_unapproved_symbol_weight_unchanged(self, client, db_engine):
        """未参与本次分析的标的，权重不受影响"""
        # 创建3个持仓
        await client.post("/api/v1/portfolio/", json={"symbol": "600519", "weight": 0.18})
        await client.post("/api/v1/portfolio/", json={"symbol": "300750", "weight": 0.15})
        await client.post("/api/v1/portfolio/", json={"symbol": "002594", "weight": 0.13})

        # 只分析 600519，审批通过并增仓到 0.20
        d = await insert_decision_with_approval(
            db_engine, symbol="600519",
            current_weight=0.18, recommended_weight=0.20
        )
        await client.post(f"/api/v1/approvals/{d['approval_id']}/action",
                         json={"action": "approved", "reviewed_by": "tester"})

        # 600519 权重更新
        assert abs((await get_holding_weight(db_engine, "600519")) - 0.20) < 0.001

        # 300750 和 002594 权重不变
        assert abs((await get_holding_weight(db_engine, "300750")) - 0.15) < 0.001, \
            "300750 未参与分析，权重应保持 0.15"
        assert abs((await get_holding_weight(db_engine, "002594")) - 0.13) < 0.001, \
            "002594 未参与分析，权重应保持 0.13"


# ═══════════════════════════════════════════════════════════════════════════════
# Flow-07：连续审批的权重累积
# ═══════════════════════════════════════════════════════════════════════════════

class TestFlow07CumulativeApprovals:

    @pytest.mark.asyncio
    async def test_consecutive_approvals_accumulate(self, client, db_engine):
        """连续3次审批，持仓权重正确反映最后一次的结果"""
        # 第1次审批：0.10 → 0.15
        d1 = await insert_decision_with_approval(
            db_engine, current_weight=0.10, recommended_weight=0.15
        )
        await client.post(f"/api/v1/approvals/{d1['approval_id']}/action",
                         json={"action": "approved", "reviewed_by": "tester"})
        assert abs((await get_holding_weight(db_engine, "600519")) - 0.15) < 0.001

        # 第2次审批：0.15 → 0.18
        d2 = await insert_decision_with_approval(
            db_engine, current_weight=0.15, recommended_weight=0.18
        )
        await client.post(f"/api/v1/approvals/{d2['approval_id']}/action",
                         json={"action": "approved", "reviewed_by": "tester"})
        assert abs((await get_holding_weight(db_engine, "600519")) - 0.18) < 0.001

        # 第3次审批：修改为 0.12
        d3 = await insert_decision_with_approval(
            db_engine, current_weight=0.18, recommended_weight=0.20
        )
        await client.put(f"/api/v1/approvals/{d3['approval_id']}/modify", json={
            "modified_weights": {"600519": 0.12}, "reviewed_by": "tester"
        })
        assert abs((await get_holding_weight(db_engine, "600519")) - 0.12) < 0.001

        # 共3条快照
        assert (await get_snapshot_count(db_engine)) == 3


# ═══════════════════════════════════════════════════════════════════════════════
# Flow-08：审批状态机完整性
# ═══════════════════════════════════════════════════════════════════════════════

class TestFlow08ApprovalStateMachine:

    @pytest.mark.asyncio
    async def test_all_illegal_transitions_rejected(self, client, db_engine):
        """所有非法状态转换都必须返回 409"""
        illegal_cases = [
            # (先执行的操作, 再尝试的操作)
            ("approved", "approved"),
            ("approved", "rejected"),
            ("rejected", "approved"),
            ("rejected", "rejected"),
        ]

        for first_action, second_action in illegal_cases:
            # 每次都用新的审批记录
            d = await insert_decision_with_approval(db_engine)
            await client.post(f"/api/v1/approvals/{d['approval_id']}/action",
                             json={"action": first_action, "reviewed_by": "u1"})
            r = await client.post(f"/api/v1/approvals/{d['approval_id']}/action",
                                  json={"action": second_action, "reviewed_by": "u2"})
            assert r.status_code == 409, \
                f"状态 {first_action} 后再 {second_action} 应返回 409，实际 {r.status_code}"

    @pytest.mark.asyncio
    async def test_modify_then_action_rejected(self, client, db_engine):
        """已 modified 的审批不能再次操作"""
        d = await insert_decision_with_approval(db_engine)
        await client.put(f"/api/v1/approvals/{d['approval_id']}/modify",
                        json={"modified_weights": {"600519": 0.15}, "reviewed_by": "u1"})

        r = await client.post(f"/api/v1/approvals/{d['approval_id']}/action",
                             json={"action": "approved", "reviewed_by": "u2"})
        assert r.status_code == 409

    @pytest.mark.asyncio
    async def test_modify_already_approved_rejected(self, client, db_engine):
        """已通过的审批不能再修改权重"""
        d = await insert_decision_with_approval(db_engine)
        await client.post(f"/api/v1/approvals/{d['approval_id']}/action",
                         json={"action": "approved", "reviewed_by": "u1"})

        r = await client.put(f"/api/v1/approvals/{d['approval_id']}/modify",
                            json={"modified_weights": {"600519": 0.10}, "reviewed_by": "u2"})
        assert r.status_code == 409
