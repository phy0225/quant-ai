# 设计文档：AI 自动化研发流水线 v2（GitHub Actions Native）

**日期**：2026-04-01
**状态**：待实现
**替代目标**：`auto_fix.py` + `ai_script_common.py` + `run_nightly.ps1`
**迁移成本**：复制 3 个文件 + 配 1 个 Secret，约 10 分钟

---

## 一、问题与目标

### 现状痛点

| 问题 | 具体表现 |
|------|---------|
| 可迁移性差 | `auto_fix.py` 硬编码 `backend/`、`frontend/` 路径，新项目需要修改 Python 源码 |
| 本地依赖重 | 需要 Python 环境 + venv + 本地机器保持开机 |
| 上下文污染 | 单 Claude session 顺序执行所有 spec，001 的讨论上下文影响 003 的执行质量 |
| 测试保障弱 | 只在全部完成后跑一次全量测试，任务间回归无法及时发现 |
| 可观测性差 | 执行日志在本地，失败时没有结构化通知，次日需要手动查日志 |

### 设计目标

- **零本地依赖**：本机关机也能跑，结果 push 到 git 次日查看
- **上下文隔离**：每个 spec 目录独立 Claude session，干净上下文
- **三层测试门禁**：targeted → regression → review，任务间回归即时发现
- **结构化产出**：成功自动开 PR，失败自动开 Issue，次日一眼看清状态
- **10 分钟迁移**：复制 3 个文件到任意项目即可使用

---

## 二、整体架构

### 文件清单（迁移包）

```
.github/workflows/
├── nightly.yml          ← 执行逻辑（迁移后基本不动）
└── scheduler.yml        ← 触发逻辑（只改 cron 表达式）

.claude/skills/
└── overnight-execute.md ← 执行引擎（替代 auto_fix.py）
```

### 运行时流程

```
scheduler.yml（cron 17:05）
    │
    └── gh workflow run nightly.yml
                │
                ▼
        detect-specs job
        扫描 specs/*/tasks.md → matrix ["001","002","003"]
                │
                ▼（matrix 并行，fail-fast: false）
    ┌───────────┬───────────┬───────────┐
execute-001  execute-002  execute-003
独立 runner   独立 runner   独立 runner
独立上下文    独立上下文    独立上下文
    │            │            │
Step 0: 基线  Step 0: 基线  Step 0: 基线
Task N:       Task N:       Task N:
  L1 指定测试   L1 指定测试   L1 指定测试
  L2 全量回归   L2 全量回归   L2 全量回归
  L3 代码审查   L3 代码审查   L3 代码审查
覆盖率门禁    覆盖率门禁    覆盖率门禁
push branch  push branch  push branch
    └───────────┴───────────┘
                │
        consolidate job
        ├── 成功 → gh pr create（feat/* → dev）
        └── 失败 → gh issue create（附日志链接）
```

---

## 三、GitHub Actions 设计

### `scheduler.yml`（触发，按需修改）

```yaml
name: Nightly Scheduler

on:
  schedule:
    - cron: '5 9 * * 1-5'   # UTC 09:05 = 北京 17:05，工作日
  workflow_dispatch:

jobs:
  trigger:
    runs-on: ubuntu-latest
    steps:
      - name: Trigger nightly execute
        env:
          GH_TOKEN: ${{ secrets.GITHUB_TOKEN }}
        run: |
          gh workflow run nightly.yml \
            --repo ${{ github.repository }} \
            --field specs_filter=""
```

**迁移时唯一需要改的行**：`cron: '5 9 * * 1-5'`

### `nightly.yml`（执行，迁移后不动）

**四个 job 职责：**

| Job | 职责 | 触发条件 |
|-----|------|---------|
| `detect-specs` | 扫描 specs/*/tasks.md，输出 matrix | 始终 |
| `execute`（matrix）| 每个 spec 独立执行，失败重试 3 次 | detect-specs 成功 |
| `consolidate` | 成功 → PR，失败 → Issue | 始终（even on failure）|

**关键设计决策：**

- `fail-fast: false`：001 失败不停止 002/003
- 每个 job 独立 `checkout`：真正隔离，无共享目录污染
- `workflow_dispatch` + `specs_filter` 输入：支持手动触发单个 spec
- failure artifact upload：失败时保存 claude 日志供事后分析

**重试策略：**
```bash
for attempt in 1 2 3; do
  if claude --dangerously-skip-permissions --print "/overnight-execute $SPEC_PATH"; then
    exit 0
  fi
  sleep 30  # 等待 API 限流恢复
done
exit 1
```

**Git 配置（bot 提交）：**
```bash
git config user.name "github-actions[bot]"
git config user.email "github-actions[bot]@users.noreply.github.com"
```

---

## 四、overnight-execute Skill 设计

**文件路径**：`.claude/skills/overnight-execute.md`
**调用方式**：`/overnight-execute specs/001-xxx`

### 执行流程

#### Step 0：建立测试基线
```bash
pytest tests/ -v --tb=no -q 2>&1 | tee /tmp/baseline.txt
```
记录执行前已知的通过/失败状态，防止误判"旧有失败"为新引入回归。

#### Step 1：上下文加载（保持干净）
1. 读 `CLAUDE.md` → 项目约束、禁止操作、代码规范
2. 读 `<spec-path>/tasks.md` → 任务列表和验证命令
3. 读 `<spec-path>/design.md`（如存在）→ 技术背景
4. **不读取其他文件**，避免上下文污染

#### Step 2：逐任务执行（三层测试门禁）

对每个 `## Task N.N` 顺序执行：

```
[READ]   精确定位涉及的文件和函数（tasks.md 已标注）
[RED]    invoke superpowers:test-driven-development → 写失败测试
[GREEN]  最小实现让测试通过，不多写一行
[L1]     运行 tasks.md 该任务指定的验证命令（快速反馈）
[L2]     运行全量 pytest，与基线对比（回归安全网）
         → 新增失败条目 = 本任务失败，触发 systematic-debugging
[L3]     invoke superpowers:requesting-code-review
         关注：新增代码有对应测试？覆盖异常路径？无脆弱测试？
         → 审查不通过 → 补测试 → 重回 L1
```

#### Step 3：失败处理
```
invoke superpowers:systematic-debugging
  最多分析 3 轮，每轮修复后重新从 L1 验证
  3 轮后仍失败：
    输出 TASK_FAILED: <task-id> <error-summary>
    停止当前 spec，退出码非 0
```

#### Step 4：全量验证门禁
所有任务完成后：
```bash
pytest tests/ --cov --cov-fail-under=70   # 覆盖率门禁
npx tsc --noEmit                           # 前端类型检查
npm run build                              # 构建验证
```

全部通过 → 输出 `DONE: <spec-path>` → 退出码 0

#### 禁止行为
- ❌ 不做 git 操作（由 GitHub Actions 处理）
- ❌ 不修改 tasks.md 以外的文档
- ❌ 不因"优化"修改 Out of Scope 的文件
- ❌ 不在测试失败时编造"环境问题"跳过验证

### 可迁移性设计

| 项目差异 | 注入方式 |
|---------|---------|
| 代码规范、禁止操作 | 读 `CLAUDE.md` |
| 任务级验证命令 | 读 `tasks.md` 每个任务的验证行 |
| 全量测试命令 | 读 `tasks.md` 末尾"执行约束"段落 |
| 覆盖率阈值 | `tasks.md` 末尾可配置（默认 70%）|

**零硬编码，Skill 文件本身无任何项目特定内容。**

---

## 五、与旧方案对比

| 维度 | 旧方案（auto_fix.py）| 新方案（GitHub Actions Native）|
|------|---------------------|-------------------------------|
| 代码量 | ~300 行 Python | 0 行 Python，~80 行 YAML |
| 本地依赖 | Python + venv + 开机 | 无 |
| 上下文隔离 | ❌ 单 session 全部跑 | ✅ 每 spec 独立 session |
| 测试门禁 | 仅最后全量一次 | 每任务三层：targeted/regression/review |
| 失败通知 | 本地日志，手动查 | GitHub Issue 自动创建 |
| 成功产出 | push 分支（手动开 PR）| 自动开 PR |
| 迁移成本 | 修改 Python 源码 | 复制 3 文件 + 1 Secret |
| 并行执行 | ❌ 顺序 | ✅ matrix 并行 |
| 可观测性 | 本地 .test_reports/ | GitHub Actions UI 完整日志 |

---

## 六、迁移到新项目（完整步骤）

```bash
# 1. 复制文件（2 分钟）
cp .github/workflows/nightly.yml    <新项目>/.github/workflows/
cp .github/workflows/scheduler.yml  <新项目>/.github/workflows/
cp .claude/skills/overnight-execute.md <新项目>/.claude/skills/

# 2. 配 GitHub Secret（2 分钟）
# 仓库 → Settings → Secrets → ANTHROPIC_API_KEY

# 3. 按项目调整（5 分钟）
# scheduler.yml：改 cron 表达式
# overnight-execute.md 末尾：填写项目的全量测试命令

# 4. 验证
# GitHub → Actions → 手动触发 nightly.yml
```

---

## 七、删除清单

新方案落地后可移除：

```
auto_fix.py          ← overnight-execute.md 替代
ai_script_common.py  ← auto_fix.py 的依赖
run_nightly.ps1      ← scheduler.yml 替代
```

`specs/` 目录结构、`tasks.md` 格式、`CLAUDE.md` 均**保持不变**。
