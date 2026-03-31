# 分析任务状态持久化设计文档

**日期**：2026-03-31
**需求来源**：需求文档-v2.1.md（spec: 001）
**优先级**：P0
**后端改动**：零

---

## 1. 问题

`AnalyzePage.vue` 的运行时状态（`currentRun`、`isPolling`、`pollTimer`）全部存储在组件本地 `ref` 中。路由离开时组件卸载，`onUnmounted` 清除计时器，重新挂载后 `currentRun = null`，分析进度完全丢失。后端 `asyncio.create_task` 从未中断，问题完全出在前端。

---

## 2. 目标

- 用户离开分析页再返回，自动恢复正在进行中的分析任务
- 分析进行中时，侧边栏「触发分析」显示脉冲圆点
- 刷新浏览器后自动恢复（sessionStorage 持久化 run.id）
- 改动文件 ≤ 3，零后端改动

---

## 3. 架构

### 状态持久化层：Pinia Store

新增 `frontend/src/store/analysis.ts`，作为分析任务状态的单一数据源。

```
sessionStorage['activeRunId']
       ↓ 初始化读取
store.activeRunId (ref)
store.currentRun  (ref<DecisionRun | null>)
store.isPolling   (ref<boolean>)
store.isRunning   (computed)
```

### 数据流

```
handleTrigger 成功
  → store.setActiveRun(run)
  → sessionStorage['activeRunId'] = run.id

onUnmounted
  → 停计时器（不清 store）

onMounted
  → if store.activeRunId exists → startPolling(id)  // 刷新/路由返回均适用

轮询拿到 completed/failed
  → store.clearActiveRun()
  → sessionStorage 清除

后端返回 404
  → store.clearActiveRun()（静默）
```

---

## 4. 文件改动

### 4.1 `frontend/src/store/analysis.ts`（新增）

- `activeRunId`：`ref<string | null>`，初始值 `sessionStorage.getItem('activeRunId')`
- `currentRun`：`ref<DecisionRun | null>`，内存状态
- `isPolling`：`ref<boolean>`
- `isRunning`：computed，`isPolling.value || currentRun.value?.status === 'running'`
- `setActiveRun(run: DecisionRun)`：更新两者 + 写 sessionStorage
- `clearActiveRun()`：清两者 + 删 sessionStorage

### 4.2 `frontend/src/pages/AnalyzePage.vue`（修改）

| 改动点 | 原来 | 改后 |
|--------|------|------|
| `currentRun` | 本地 `ref` | `store.currentRun` |
| `isPolling` | 本地 `ref` | `store.isPolling` |
| `onMounted` | 只加载持仓 | 加载持仓 + 若 `store.activeRunId` 存在则 `startPolling(id)` |
| `handleTrigger` 成功 | `currentRun.value = run` | `store.setActiveRun(run)` |
| `onUnmounted` | `stopPolling()`（清计时器+清 `isPolling`） | 只停计时器，保留 store |
| 轮询结束 | 仅停计时器 | 停计时器 + `store.clearActiveRun()` |
| 后端 404 | 忽略 | `store.clearActiveRun()`（静默） |

`stopPolling` 内部行为拆分：计时器清理保留，`store.isPolling = false` 仅在轮询自然结束时调用。

### 4.3 `frontend/src/components/ui/Sidebar.vue`（修改）

- 引入 `useAnalysisStore`
- 「触发分析」菜单项（`item.path === '/analyze'`）旁增加脉冲圆点：
  - 显示条件：`analysisStore.isRunning`
  - 样式：`animate-pulse` 小圆点，品牌色

---

## 5. 验收标准

| AC | 场景 | 预期 |
|----|------|------|
| AC-01 | 触发分析 → 切换页面 → 返回 | 进度面板自动恢复，轮询继续 |
| AC-02 | 分析完成后返回 | 直接显示结果，不再轮询 |
| AC-03 | 分析中查看侧边栏 | 「触发分析」显示脉冲圆点 |
| AC-04 | 刷新浏览器 | 自动恢复轮询 |
| AC-05 | 触发新分析 | 旧 sessionStorage 覆盖 |
| AC-06 | 后端 404 | 静默清除，显示空状态 |
| AC-07 | 分析进行中点击「开始分析」 | 按钮禁用 |

---

## 6. 超出范围

- WebSocket 替代轮询（留 v6.0）
- 跨标签页状态同步
- 多任务并行
- 后端接口变更
