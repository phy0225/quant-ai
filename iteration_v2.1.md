# v2.1 迭代需求 — 分析洞察与审批效率提升

> 文档用途：提交给 Claude Code 自动实现，完成后由 `auto_fix.py` 自动测试验证
> 预估工作量：后端 3 个新接口 + 前端 2 处 UI 改动
> 测试覆盖：所有新接口必须有对应的 pytest 测试用例

---

## 需求一：标的分析统计接口

### 背景
用户希望知道某个标的历史上被分析了多少次、各 Agent 的平均置信度是多少、最近的方向分布如何，帮助判断信号质量。

### 接口定义

**GET `/api/v1/decisions/stats`**

请求参数：
- `symbol`（可选，str）：过滤指定标的，不传则统计全部
- `days`（可选，int，默认 30）：统计最近 N 天的数据

响应格式：
```json
{
  "total_decisions": 42,
  "symbol_stats": [
    {
      "symbol": "600519",
      "decision_count": 15,
      "direction_dist": {"buy": 8, "sell": 3, "hold": 4},
      "avg_confidence": 0.63,
      "last_direction": "buy",
      "last_analyzed_at": "2026-03-24T10:23:00"
    }
  ],
  "generated_at": "2026-03-24T12:00:00"
}
```

实现要求：
- 从 `decision_runs` 表查询，只统计 `status = 'completed'` 的记录
- `direction_dist` 从 `final_direction` 字段统计
- `avg_confidence` 从 `agent_signals` JSON 中计算所有非 risk/executor agent 的 confidence 均值
- 如果 `agent_signals` 为空或解析失败，该条记录的 confidence 不计入均值
- `symbol` 过滤时匹配 `symbols` JSON 字段中包含该标的的记录

---

## 需求二：审批批量操作接口

### 背景
审批列表经常有大量历史遗留的待审批记录，用户希望能一次批量拒绝多条，而不是一条条点进去操作。

### 接口定义

**POST `/api/v1/approvals/batch-action`**

请求体：
```json
{
  "approval_ids": ["uuid1", "uuid2", "uuid3"],
  "action": "rejected",
  "reviewed_by": "admin",
  "comment": "批量清理历史遗留"
}
```

响应格式：
```json
{
  "succeeded": ["uuid1", "uuid2"],
  "failed": [
    {"id": "uuid3", "reason": "Approval already processed."}
  ],
  "total": 3,
  "success_count": 2,
  "fail_count": 1
}
```

实现要求：
- `action` 只允许 `"rejected"`（批量操作只允许拒绝，批准必须逐条审查）
- 传入其他 action 值时返回 `422`，detail 为 `"批量操作仅支持 rejected"`
- `approval_ids` 为空时返回 `422`
- `approval_ids` 最多 50 条，超出返回 `422`
- 遍历每条记录，单条失败不影响其他条继续执行
- 已处理（非 pending）的记录计入 `failed`，不抛异常
- 系统处于紧急停止状态时，整体返回 `503`
- 不触发 `apply_recommendations`（拒绝不更新持仓）
- 每条成功的拒绝都调用 `add_graph_node`
- 需要在 `schemas.py` 中添加对应的 Pydantic 模型 `BatchActionRequest` 和 `BatchActionResponse`

---

## 需求三：持仓页展示历史分析次数

### 背景
持仓页每个标的旁边显示"该标的被分析了 N 次"，帮助用户快速了解哪些标的关注度更高。

### 前端改动（`frontend/src/pages/PortfolioPage.vue`）

在持仓列表的每行，在「操作」列前面新增一列「分析次数」：

显示格式：
- 有数据时：`12 次` （数字 + 空格 + "次"）
- 加载中：`--`
- 0 次：`0 次`

实现方式：
- 页面加载时调用 `GET /api/v1/decisions/stats` 接口
- 用返回的 `symbol_stats` 数组构建一个 `Map<symbol, count>` 查表
- 渲染时按 holding.symbol 查表，找不到则显示 `--`
- 不需要实时刷新，页面 `onMounted` 时加载一次即可

---

## 需求四：审批列表批量拒绝 UI

### 前端改动（`frontend/src/pages/ApprovalListPage.vue`）

在现有列表基础上，增加批量拒绝功能：

**4.1 多选框**
- 在表格最左侧加一列 checkbox
- 只有 `status === 'pending'` 的行才显示可勾选的 checkbox，其他行该列为空
- 表头有「全选当前页待审批」的 checkbox，点击全选/取消全选当前页所有 pending 记录

**4.2 批量操作栏**
- 勾选数量 > 0 时，在表格上方显示操作栏：
  ```
  已选 3 条  [批量拒绝]  [取消选择]
  ```
- 「批量拒绝」弹出确认弹窗，弹窗内需要填写：
  - 操作人（必填）
  - 拒绝原因（可选）
- 确认后调用 `POST /api/v1/approvals/batch-action`
- 操作完成后刷新列表，清空选中状态，显示 toast：`已拒绝 N 条，M 条操作失败`

---

## 测试要求

**以下测试用例必须在 `backend/tests/test_api.py` 中实现并通过：**

### 统计接口测试
1. `test_stats_empty_returns_zero` — 无数据时返回 `total_decisions: 0`，`symbol_stats: []`
2. `test_stats_counts_completed_only` — 只统计 `status=completed` 的记录，`running` 状态不计入
3. `test_stats_symbol_filter` — 传 `symbol=600519` 只返回包含该标的的统计
4. `test_stats_direction_distribution` — `direction_dist` 正确反映 `final_direction` 分布

### 批量拒绝接口测试
5. `test_batch_reject_success` — 批量拒绝多条 pending 记录，全部成功
6. `test_batch_reject_partial_fail` — 部分已处理的记录计入 failed，不影响其他
7. `test_batch_reject_only_allows_rejected_action` — 传 `action=approved` 返回 422
8. `test_batch_reject_empty_ids` — 空 ids 返回 422
9. `test_batch_reject_too_many_ids` — 超过 50 条返回 422
10. `test_batch_reject_blocked_by_emergency_stop` — 紧急停止时返回 503

---

## 实现注意事项

1. 统计接口的 `avg_confidence` 计算：`agent_signals` 是 JSON 数组，字段类型为 `agent_type`，排除 `agent_type` 为 `risk` 和 `executor` 的条目
2. 批量接口的路由 `/batch-action` 要放在 `/{approval_id}` 路由**之前**注册，否则 `batch-action` 会被当成 approval_id 参数匹配
3. 前端 `PortfolioPage.vue` 的表格列顺序：标的 | 仓位权重 | 成本价 | 最新价 | 浮动盈亏 | 持股数 | 市值 | **分析次数** | 操作
4. 所有新增的后端接口都需要在 `schemas.py` 中有对应的 Pydantic 模型
