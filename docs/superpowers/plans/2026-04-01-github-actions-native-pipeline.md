# GitHub Actions Native Pipeline 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 用 3 个文件（scheduler.yml + nightly.yml + overnight-execute.md）替代 auto_fix.py + ai_script_common.py + run_nightly.ps1，实现零本地依赖、上下文隔离、三层测试门禁的过夜自动执行流水线。

**Architecture:** scheduler.yml 负责 cron 触发，调用 nightly.yml；nightly.yml 用 matrix 并行执行每个 spec（每个 spec 独立 runner + 独立 Claude session）；overnight-execute.md 是执行引擎 Skill，Claude 读取后按 TDD + 三层测试门禁实现任务。

**Tech Stack:** GitHub Actions（ubuntu-latest runner）、Claude Code CLI（`claude --dangerously-skip-permissions --print`）、Python pytest、Node.js tsc + vite

---

## 文件变更清单

| 操作 | 文件 |
|------|------|
| 新建目录 | `.github/workflows/` |
| 新建 | `.github/workflows/scheduler.yml` |
| 新建 | `.github/workflows/nightly.yml` |
| 新建目录 | `.claude/skills/` |
| 新建 | `.claude/skills/overnight-execute.md` |
| 修改 | `.claude/settings.local.json`（新增 allow 规则）|
| 修改 | `AI自动化研发操作手册.md`（追加 v2 迁移说明章节）|
| 标记废弃 | `auto_fix.py`、`ai_script_common.py`、`run_nightly.ps1` |

---

## Task 1：创建 scheduler.yml（触发器）

**Files:**
- Create: `.github/workflows/scheduler.yml`

- [ ] **Step 1：创建目录并写文件**

```bash
mkdir -p .github/workflows
```

写入 `.github/workflows/scheduler.yml`：

```yaml
name: Nightly Scheduler

on:
  schedule:
    - cron: '5 9 * * 1-5'   # UTC 09:05 = 北京时间 17:05，工作日触发
  workflow_dispatch:          # 支持手动触发（调试/临时执行用）

jobs:
  trigger:
    runs-on: ubuntu-latest
    steps:
      - name: Trigger nightly execute workflow
        env:
          GH_TOKEN: ${{ secrets.GITHUB_TOKEN }}
        run: |
          gh workflow run nightly.yml \
            --repo ${{ github.repository }} \
            --field specs_filter=""
```

- [ ] **Step 2：验证 YAML 语法**

```bash
python -c "import yaml; yaml.safe_load(open('.github/workflows/scheduler.yml')); print('YAML OK')"
```

期望输出：`YAML OK`

- [ ] **Step 3：验证关键字段存在**

```bash
python -c "
import yaml
d = yaml.safe_load(open('.github/workflows/scheduler.yml'))
assert 'schedule' in d['on'], 'missing schedule'
assert 'workflow_dispatch' in d['on'], 'missing workflow_dispatch'
assert d['jobs']['trigger']['steps'][0]['name'] == 'Trigger nightly execute workflow'
print('结构检查 PASS')
"
```

期望输出：`结构检查 PASS`

- [ ] **Step 4：commit**

```bash
git add .github/workflows/scheduler.yml
git commit -m "feat: 新增 scheduler.yml（cron 触发器，替代 Task Scheduler）"
```

---

## Task 2：创建 nightly.yml — detect-specs job

**Files:**
- Create: `.github/workflows/nightly.yml`（仅 detect-specs job 部分）

- [ ] **Step 1：写 nightly.yml 头部 + detect-specs job**

写入 `.github/workflows/nightly.yml`：

```yaml
name: Nightly AI Execute

on:
  workflow_dispatch:
    inputs:
      specs_filter:
        description: '指定执行哪个 spec 目录（留空=全部，示例：specs/001-xxx）'
        required: false
        default: ''

jobs:
  # ── Job 1：扫描有哪些待执行的 spec ─────────────────────────
  detect-specs:
    runs-on: ubuntu-latest
    outputs:
      matrix: ${{ steps.scan.outputs.matrix }}
      has-specs: ${{ steps.scan.outputs.has-specs }}
    steps:
      - uses: actions/checkout@v4

      - name: Scan specs directory
        id: scan
        run: |
          FILTER="${{ github.event.inputs.specs_filter }}"

          if [ -n "$FILTER" ]; then
            # 指定了 specs_filter，只处理该目录
            if [ -f "${FILTER}/tasks.md" ]; then
              SPECS_JSON=$(echo "$FILTER" | jq -R '[.]')
            else
              echo "指定目录 ${FILTER}/tasks.md 不存在"
              SPECS_JSON='[]'
            fi
          else
            # 扫描所有 specs/*/tasks.md，排除 archive 子目录
            SPECS_JSON=$(find specs -name "tasks.md" \
              -not -path "*/archive/*" \
              -not -path "*/docs/*" \
              2>/dev/null \
              | sed 's|/tasks.md||' \
              | sort \
              | jq -R -s 'split("\n") | map(select(length > 0))')
          fi

          COUNT=$(echo "$SPECS_JSON" | jq length)
          echo "发现 ${COUNT} 个 spec: $SPECS_JSON"
          echo "matrix={\"spec\":$SPECS_JSON}" >> $GITHUB_OUTPUT
          echo "has-specs=$([ $COUNT -gt 0 ] && echo true || echo false)" >> $GITHUB_OUTPUT

      - name: Skip if no specs found
        if: steps.scan.outputs.has-specs == 'false'
        run: |
          echo "specs/ 目录下无待执行任务，跳过本次执行"
```

- [ ] **Step 2：验证 YAML 语法**

```bash
python -c "import yaml; yaml.safe_load(open('.github/workflows/nightly.yml')); print('YAML OK')"
```

期望输出：`YAML OK`

- [ ] **Step 3：验证 detect-specs job 结构**

```bash
python -c "
import yaml
d = yaml.safe_load(open('.github/workflows/nightly.yml'))
assert 'detect-specs' in d['jobs'], 'missing detect-specs job'
assert 'matrix' in d['jobs']['detect-specs']['outputs'], 'missing matrix output'
assert 'has-specs' in d['jobs']['detect-specs']['outputs'], 'missing has-specs output'
print('detect-specs 结构检查 PASS')
"
```

期望输出：`detect-specs 结构检查 PASS`

- [ ] **Step 4：commit**

```bash
git add .github/workflows/nightly.yml
git commit -m "feat: nightly.yml 新增 detect-specs job（扫描 specs/*/tasks.md）"
```

---

## Task 3：nightly.yml — execute job（matrix 并行执行）

**Files:**
- Modify: `.github/workflows/nightly.yml`（追加 execute job）

- [ ] **Step 1：在 nightly.yml 的 jobs 块末尾追加 execute job**

在 `jobs:` 块中，`detect-specs:` job 之后追加：

```yaml
  # ── Job 2：并行执行每个 spec（独立 runner + 独立 Claude 上下文）──
  execute:
    needs: detect-specs
    if: needs.detect-specs.outputs.has-specs == 'true'
    runs-on: ubuntu-latest
    strategy:
      matrix: ${{ fromJson(needs.detect-specs.outputs.matrix) }}
      fail-fast: false    # 一个 spec 失败不停止其他 spec
    outputs:
      result: ${{ steps.run.outputs.result }}

    steps:
      - uses: actions/checkout@v4

      - name: Setup Node.js（用于安装 claude CLI 和前端依赖）
        uses: actions/setup-node@v4
        with:
          node-version: '20'
          cache: 'npm'
          cache-dependency-path: frontend/package-lock.json

      - name: Install claude CLI
        run: npm install -g @anthropic-ai/claude-code

      - name: Setup Python 3.11（用于后端测试）
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'
          cache: 'pip'
          cache-dependency-path: |
            backend/requirements.txt
            backend/requirements-test.txt

      - name: Install Python dependencies
        run: |
          cd backend
          pip install -r requirements.txt -r requirements-test.txt

      - name: Install frontend dependencies
        run: cd frontend && npm ci

      - name: Execute spec via overnight-execute skill（最多重试 3 次）
        id: run
        env:
          ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
          SPEC_PATH: ${{ matrix.spec }}
        run: |
          for attempt in 1 2 3; do
            echo "========================================="
            echo "Attempt ${attempt}/3 for ${SPEC_PATH}"
            echo "========================================="

            if claude --dangerously-skip-permissions --print \
                 "/overnight-execute ${SPEC_PATH}"; then
              echo "result=success" >> $GITHUB_OUTPUT
              echo "✅ ${SPEC_PATH} 执行成功（第 ${attempt} 次）"
              exit 0
            fi

            echo "❌ Attempt ${attempt} failed"
            if [ $attempt -lt 3 ]; then
              echo "等待 30s 后重试（API 限流保护）..."
              sleep 30
            fi
          done

          echo "result=failure" >> $GITHUB_OUTPUT
          echo "🔴 ${SPEC_PATH} 三次重试全部失败"
          exit 1

      - name: Configure git for bot commit
        if: steps.run.outputs.result == 'success'
        run: |
          git config user.name "github-actions[bot]"
          git config user.email "github-actions[bot]@users.noreply.github.com"

      - name: Create and push feature branch
        if: steps.run.outputs.result == 'success'
        env:
          SPEC_PATH: ${{ matrix.spec }}
        run: |
          LABEL=$(basename "${SPEC_PATH}")
          DATE=$(date +%Y%m%d)
          BRANCH="feat/${LABEL}-${DATE}"

          git checkout -b "${BRANCH}"
          git add -A
          git diff --cached --quiet || git commit -m "feat: ${LABEL} (nightly ${DATE})"
          git push origin "${BRANCH}"
          echo "✅ 已推送分支 ${BRANCH}"

      - name: Upload failure log as artifact
        if: failure()
        uses: actions/upload-artifact@v4
        with:
          name: failure-log-${{ matrix.spec }}
          path: |
            /tmp/claude-*.log
            /tmp/baseline.txt
          retention-days: 7
```

- [ ] **Step 2：验证 YAML 语法**

```bash
python -c "import yaml; yaml.safe_load(open('.github/workflows/nightly.yml')); print('YAML OK')"
```

期望输出：`YAML OK`

- [ ] **Step 3：验证 execute job 结构**

```bash
python -c "
import yaml
d = yaml.safe_load(open('.github/workflows/nightly.yml'))
j = d['jobs']['execute']
assert j['needs'] == 'detect-specs', 'wrong needs'
assert j['strategy']['fail-fast'] == False, 'fail-fast should be False'
assert 'ANTHROPIC_API_KEY' in str(j['steps']), 'missing ANTHROPIC_API_KEY'
print('execute job 结构检查 PASS')
"
```

期望输出：`execute job 结构检查 PASS`

- [ ] **Step 4：commit**

```bash
git add .github/workflows/nightly.yml
git commit -m "feat: nightly.yml 新增 execute job（matrix 并行，3 次重试）"
```

---

## Task 4：nightly.yml — consolidate job（汇总 PR / Issue）

**Files:**
- Modify: `.github/workflows/nightly.yml`（追加 consolidate job）

- [ ] **Step 1：在 nightly.yml 末尾追加 consolidate job**

```yaml
  # ── Job 3：汇总结果，开 PR 或 Issue ────────────────────────
  consolidate:
    needs: [detect-specs, execute]
    if: always() && needs.detect-specs.outputs.has-specs == 'true'
    runs-on: ubuntu-latest

    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0    # 需要获取所有分支信息

      - name: Create PRs for succeeded specs
        env:
          GH_TOKEN: ${{ secrets.GITHUB_TOKEN }}
        run: |
          DATE=$(date +%Y%m%d)
          PR_COUNT=0

          for spec in $(find specs -name "tasks.md" \
                        -not -path "*/archive/*" \
                        2>/dev/null \
                        | sed 's|/tasks.md||' | sort); do
            LABEL=$(basename "$spec")
            BRANCH="feat/${LABEL}-${DATE}"

            # 检查分支是否存在于远端
            if git ls-remote --heads origin "${BRANCH}" | grep -q "${BRANCH}"; then
              echo "为 ${BRANCH} 创建 PR..."

              # 取 tasks.md 前 20 行作为 PR 描述
              BODY=$(head -20 "${spec}/tasks.md" 2>/dev/null || echo "详见 ${spec}/tasks.md")

              gh pr create \
                --title "feat: ${LABEL} (nightly ${DATE})" \
                --body "${BODY}

---
🤖 由 Nightly AI Execute 自动生成" \
                --base dev \
                --head "${BRANCH}" \
                --label "nightly,ai-generated" \
                2>/dev/null && PR_COUNT=$((PR_COUNT + 1)) || true
            fi
          done

          echo "共创建 ${PR_COUNT} 个 PR"

      - name: Create failure Issue if any spec failed
        if: needs.execute.result == 'failure'
        env:
          GH_TOKEN: ${{ secrets.GITHUB_TOKEN }}
          RUN_URL: ${{ github.server_url }}/${{ github.repository }}/actions/runs/${{ github.run_id }}
        run: |
          gh issue create \
            --title "🔴 Nightly Execute 失败：$(date +%Y-%m-%d)" \
            --body "过夜自动执行出现失败。

**Actions 日志**：${RUN_URL}

**处理方式**：
1. 查看上方日志，定位失败的 spec
2. 修正 tasks.md 或代码后，手动触发：\`gh workflow run nightly.yml\`
3. 或重新 Plan：\`/superpowers:write-plan\`

> 此 Issue 由 GitHub Actions 自动创建" \
            --label "nightly-failure,needs-attention"
```

- [ ] **Step 2：验证完整 nightly.yml 语法**

```bash
python -c "import yaml; yaml.safe_load(open('.github/workflows/nightly.yml')); print('YAML OK')"
```

期望输出：`YAML OK`

- [ ] **Step 3：验证三个 job 全部存在**

```bash
python -c "
import yaml
d = yaml.safe_load(open('.github/workflows/nightly.yml'))
jobs = list(d['jobs'].keys())
assert 'detect-specs' in jobs, 'missing detect-specs'
assert 'execute' in jobs, 'missing execute'
assert 'consolidate' in jobs, 'missing consolidate'
assert len(jobs) == 3, f'期望 3 个 job，实际 {len(jobs)} 个'
print(f'三个 job 全部存在：{jobs} ✅')
"
```

期望输出：`三个 job 全部存在：['detect-specs', 'execute', 'consolidate'] ✅`

- [ ] **Step 4：commit**

```bash
git add .github/workflows/nightly.yml
git commit -m "feat: nightly.yml 新增 consolidate job（自动开 PR / Issue）"
```

---

## Task 5：创建 overnight-execute.md Skill（执行引擎）

**Files:**
- Create: `.claude/skills/overnight-execute.md`

- [ ] **Step 1：创建目录并写 Skill 文件**

```bash
mkdir -p .claude/skills
```

写入 `.claude/skills/overnight-execute.md`：

````markdown
# Overnight Execute

无人值守自动执行 spec 任务。读取指定 spec 目录的 tasks.md，
按 TDD + 三层测试门禁逐一实现，全部通过后输出 DONE。

## 调用方式

```
/overnight-execute <spec-path>
/overnight-execute specs/001-analysis-state-persistence
/overnight-execute          ← 不传参数则扫描所有 specs/*/tasks.md
```

## 执行流程

### Step 0：建立测试基线

在开始任何任务前，先跑全量测试并记录当前状态：

```bash
cd backend && pytest tests/ -v --tb=no -q 2>&1 | tee /tmp/baseline.txt
```

记录已知的失败条目，防止把旧有失败误判为新引入回归。

### Step 1：上下文加载（保持干净）

按顺序只读以下文件，不读其他任何文件：

1. `CLAUDE.md` → 项目约束、禁止操作、代码规范
2. `<spec-path>/tasks.md` → 任务列表和每个任务的验证命令
3. `<spec-path>/design.md`（如存在）→ 技术背景

### Step 2：逐任务执行（三层测试门禁）

对 tasks.md 中每个 `## Task N.N` 按顺序执行以下流程：

**[READ]** 精确定位 tasks.md 中标注的涉及文件和函数，只读这些文件

**[RED]** invoke `superpowers:test-driven-development`
- 先写失败测试，运行确认它确实失败

**[GREEN]** 最小实现让测试通过，不多写一行代码

**[L1 Targeted]** 运行 tasks.md 该任务指定的验证命令
- 快速反馈，确认任务本身实现正确
- 失败 → 直接进入 Step 3 失败处理

**[L2 Regression]** 运行全量测试，与基线对比：
```bash
cd backend && pytest tests/ -v --tb=short -q 2>&1 | tee /tmp/current.txt
# 对比 /tmp/baseline.txt 和 /tmp/current.txt
# 新增失败条目 = 本任务引入了回归
```
- 有新增失败 → 本任务失败，进入 Step 3 失败处理

**[L3 Review]** invoke `superpowers:requesting-code-review`
- 关注：新增代码是否有对应测试？是否覆盖异常路径？是否存在脆弱测试？
- 审查不通过 → 补测试 → 重回 L1

### Step 3：失败处理

```
invoke superpowers:systematic-debugging
  输入：失败的测试输出 + 当前改动的代码片段
  最多分析 3 轮，每轮修复后重新从 [L1] 开始验证

  3 轮后仍失败：
    输出：TASK_FAILED: <task-id> | <一句话错误摘要>
    停止当前 spec 的所有后续任务
    退出码非 0（让 GitHub Actions 感知失败）
```

### Step 4：全量验证门禁（所有任务完成后）

运行 tasks.md 末尾"执行约束"段落中列出的命令。
若 tasks.md 无此段落，则运行以下默认命令：

```bash
# 后端覆盖率门禁
cd backend && pytest tests/ --cov --cov-fail-under=70 -q

# 前端类型检查
cd frontend && npx tsc --noEmit

# 前端构建验证
cd frontend && npm run build
```

全部通过 → 输出 `DONE: <spec-path>` → 退出码 0

### Step 5：禁止行为

- ❌ 不做任何 git 操作（commit/push 由 GitHub Actions 处理）
- ❌ 不修改 tasks.md 本身的内容
- ❌ 不因"顺手优化"修改 Out of Scope 的文件
- ❌ 不在测试失败时编造"环境问题"跳过验证
- ❌ 不删除数据库文件（quant_ai.db 等）

## 迁移到新项目

此 Skill 零硬编码，项目差异通过以下方式注入：

| 项目差异 | 注入位置 |
|---------|---------|
| 代码规范、禁止操作 | 项目根目录的 `CLAUDE.md` |
| 任务级验证命令 | `tasks.md` 每个 Task 的"验证："行 |
| 全量测试命令 | `tasks.md` 末尾"执行约束"段落 |
| 覆盖率阈值 | `tasks.md` 末尾可配置（默认 70%）|
````

- [ ] **Step 2：验证文件存在且包含关键内容**

```bash
python -c "
content = open('.claude/skills/overnight-execute.md').read()
checks = [
    ('调用方式', '/overnight-execute'),
    ('Step 0 基线', 'baseline.txt'),
    ('三层门禁', 'L1'),
    ('失败处理', 'TASK_FAILED'),
    ('全量验证', 'cov-fail-under'),
    ('禁止行为', '不做任何 git 操作'),
]
for label, keyword in checks:
    assert keyword in content, f'缺少 {label}（关键词：{keyword}）'
    print(f'✅ {label}')
print('overnight-execute.md 内容检查全部通过')
"
```

期望输出：6 行 `✅` + `overnight-execute.md 内容检查全部通过`

- [ ] **Step 3：commit**

```bash
git add .claude/skills/overnight-execute.md
git commit -m "feat: 新增 overnight-execute skill（替代 auto_fix.py 执行引擎）"
```

---

## Task 6：更新 settings.local.json + 废弃旧文件

**Files:**
- Modify: `.claude/settings.local.json`
- Modify: `auto_fix.py`（添加废弃头注释）
- Modify: `ai_script_common.py`（添加废弃头注释）
- Modify: `run_nightly.ps1`（添加废弃头注释）

- [ ] **Step 1：更新 settings.local.json，新增 claude CLI 相关 allow 规则**

读取现有 `.claude/settings.local.json`，在 `permissions.allow` 数组中追加：

```json
"Bash(claude:*)",
"Bash(gh:*)",
"Bash(find:*)",
"Bash(mkdir:*)",
"Bash(ls:*)"
```

更新后完整内容：

```json
{
  "permissions": {
    "allow": [
      "Bash(head:*)",
      "Bash(tail:*)",
      "Bash(grep:*)",
      "Bash(git:*)",
      "Bash(python:*)",
      "Bash(pytest:*)",
      "Bash(npm:*)",
      "Bash(npx:*)",
      "Bash(uvicorn:*)",
      "Bash(pip:*)",
      "Bash(claude:*)",
      "Bash(gh:*)",
      "Bash(find:*)",
      "Bash(mkdir:*)",
      "Bash(ls:*)"
    ],
    "defaultMode": "bypassPermissions"
  }
}
```

- [ ] **Step 2：验证 settings.local.json 合法 JSON 且包含新规则**

```bash
python -c "
import json
d = json.load(open('.claude/settings.local.json'))
allows = d['permissions']['allow']
for rule in ['Bash(claude:*)', 'Bash(gh:*)', 'Bash(find:*)']:
    assert rule in allows, f'缺少 {rule}'
    print(f'✅ {rule}')
assert d['permissions']['defaultMode'] == 'bypassPermissions'
print('✅ defaultMode = bypassPermissions')
print('settings.local.json 检查 PASS')
"
```

期望输出：4 行 `✅` + `settings.local.json 检查 PASS`

- [ ] **Step 3：在 auto_fix.py 头部添加废弃声明**

在 `auto_fix.py` 第 1 行之前插入：

```python
# ⚠️  DEPRECATED（2026-04-01）
# 此文件已被 GitHub Actions Native Pipeline 替代。
# 新流程：.github/workflows/nightly.yml + .claude/skills/overnight-execute.md
# 保留此文件仅供回滚参考，请勿在新项目中使用。
# 详见：docs/superpowers/specs/2026-04-01-github-actions-native-pipeline-design.md
```

- [ ] **Step 4：在 ai_script_common.py 头部添加废弃声明**

在 `ai_script_common.py` 第 1 行之前插入：

```python
# ⚠️  DEPRECATED（2026-04-01）
# 此文件是 auto_fix.py 的依赖，随 auto_fix.py 一同废弃。
# 新流程无需此文件。保留仅供回滚参考。
```

- [ ] **Step 5：在 run_nightly.ps1 头部添加废弃声明**

在 `run_nightly.ps1` 第 1 行之前插入：

```powershell
# ⚠️  DEPRECATED（2026-04-01）
# 此脚本已被 .github/workflows/scheduler.yml 替代。
# 新流程通过 GitHub Actions cron 自动触发，无需本地脚本。
# 保留仅供回滚参考。
```

- [ ] **Step 6：commit**

```bash
git add .claude/settings.local.json auto_fix.py ai_script_common.py run_nightly.ps1
git commit -m "chore: 废弃 auto_fix.py 三件套，更新 settings.local.json 权限规则"
```

---

## Task 7：更新操作手册（新增 v2 迁移说明）

**Files:**
- Modify: `AI自动化研发操作手册.md`（末尾追加新章节）

- [ ] **Step 1：在 AI自动化研发操作手册.md 末尾追加以下内容**

```markdown

---

## 十二、v2 迁移说明（GitHub Actions Native）

> **适用**：已按本手册配置好旧流程，想迁移到新流程的用户

### 新旧流程对比

| 环节 | 旧流程（v1）| 新流程（v2）|
|------|------------|------------|
| Execute 触发 | Windows Task Scheduler → run_nightly.ps1 | GitHub Actions cron → scheduler.yml |
| Execute 执行 | python auto_fix.py（本地运行）| GitHub Actions runner（云端运行）|
| 上下文 | 单 session，顺序执行所有 spec | 每个 spec 独立 session，并行执行 |
| 失败通知 | 本地 .test_reports/ 日志 | GitHub Issue 自动创建 |
| 成功产出 | push 分支，手动开 PR | 自动开 PR（feat/* → dev）|
| 本地依赖 | Python + venv + 机器开机 | 无（GitHub Actions 云端执行）|

### 迁移步骤（约 10 分钟）

**已有旧流程 → 迁移到 v2：**

```bash
# 1. 确认新文件已存在（本次实现后自动完成）
ls .github/workflows/scheduler.yml    # ✅ 触发器
ls .github/workflows/nightly.yml      # ✅ 执行逻辑
ls .claude/skills/overnight-execute.md # ✅ 执行引擎

# 2. 在 GitHub 仓库配置 Secret（一次性）
# 仓库 → Settings → Secrets and variables → Actions → New repository secret
# Name:  ANTHROPIC_API_KEY
# Value: sk-ant-xxxxxxxxxx（你的 Anthropic API Key）

# 3. 确认仓库有 dev 分支（PR 目标分支）
git branch -a | grep dev

# 4. 手动验证一次
gh workflow run nightly.yml
gh run list --workflow=nightly.yml   # 查看执行状态
```

### 迁移到新项目（3 文件 + 1 Secret）

```bash
# 复制迁移包（在新项目根目录执行）
mkdir -p .github/workflows .claude/skills

cp <本项目>/.github/workflows/scheduler.yml  .github/workflows/
cp <本项目>/.github/workflows/nightly.yml    .github/workflows/
cp <本项目>/.claude/skills/overnight-execute.md .claude/skills/

# 按新项目调整（约 5 分钟）：
# 1. scheduler.yml：改 cron 时间（第 4 行）
# 2. overnight-execute.md 末尾：改全量测试命令（默认已是 pytest + tsc + build）
# 3. GitHub → Settings → Secrets → 添加 ANTHROPIC_API_KEY
```

### 每日节奏变化

| 时间 | 旧流程 | 新流程 |
|------|--------|--------|
| 17:00 | 确认 tasks.md，**手动确认 Task Scheduler 已配置** | 确认 tasks.md，**什么都不用做** |
| 17:05 | Task Scheduler 触发 run_nightly.ps1 | scheduler.yml cron 自动触发 |
| 次日 09:00 | 看本地 .test_reports/ 报告 | 看 **GitHub PR** 或 **GitHub Issue** |

### 废弃文件说明

以下文件已标记废弃，保留仅供回滚：

```
auto_fix.py          ← 被 overnight-execute.md 替代
ai_script_common.py  ← auto_fix.py 的依赖
run_nightly.ps1      ← 被 scheduler.yml 替代
```
```

- [ ] **Step 2：验证章节已追加**

```bash
python -c "
content = open('AI自动化研发操作手册.md', encoding='utf-8').read()
assert '十二、v2 迁移说明' in content, '缺少 v2 迁移章节'
assert 'ANTHROPIC_API_KEY' in content, '缺少 Secret 配置说明'
assert 'scheduler.yml' in content, '缺少 scheduler.yml 引用'
print('✅ v2 迁移章节已追加')
"
```

期望输出：`✅ v2 迁移章节已追加`

- [ ] **Step 3：commit**

```bash
git add AI自动化研发操作手册.md
git commit -m "docs: 操作手册新增 v2 迁移说明章节（GitHub Actions Native）"
```

---

## Task 8：端到端验证

**验证所有文件就位并通过语法检查**

- [ ] **Step 1：全文件清单验证**

```bash
python -c "
import os
files = [
    '.github/workflows/scheduler.yml',
    '.github/workflows/nightly.yml',
    '.claude/skills/overnight-execute.md',
    '.claude/settings.local.json',
    'AI自动化研发操作手册.md',
]
for f in files:
    exists = os.path.exists(f)
    print(f'{'✅' if exists else '❌'} {f}')
    assert exists, f'文件不存在：{f}'
print('所有文件就位 ✅')
"
```

- [ ] **Step 2：全 YAML 语法验证**

```bash
python -c "
import yaml
for f in ['.github/workflows/scheduler.yml', '.github/workflows/nightly.yml']:
    yaml.safe_load(open(f))
    print(f'✅ YAML 合法：{f}')
"
```

- [ ] **Step 3：废弃标记验证**

```bash
python -c "
for fname, keyword in [
    ('auto_fix.py', 'DEPRECATED'),
    ('ai_script_common.py', 'DEPRECATED'),
    ('run_nightly.ps1', 'DEPRECATED'),
]:
    content = open(fname, encoding='utf-8').read()
    assert keyword in content[:500], f'{fname} 缺少废弃标记'
    print(f'✅ {fname} 已标记废弃')
"
```

- [ ] **Step 4：git log 确认 commit 历史**

```bash
git log --oneline -8
```

期望看到（顺序可能不同）：
```
xxxxxxx docs: 操作手册新增 v2 迁移说明章节
xxxxxxx chore: 废弃 auto_fix.py 三件套，更新 settings.local.json 权限规则
xxxxxxx feat: 新增 overnight-execute skill
xxxxxxx feat: nightly.yml 新增 consolidate job
xxxxxxx feat: nightly.yml 新增 execute job
xxxxxxx feat: nightly.yml 新增 detect-specs job
xxxxxxx feat: 新增 scheduler.yml
```

- [ ] **Step 5：最终 commit（如有未提交的改动）**

```bash
git status
# 若有未提交文件：
git add -A
git commit -m "chore: GitHub Actions Native Pipeline 实现完成"
```

---

## 执行约束

- 所有 Python 验证脚本使用 `python`（已在 `.venv` 或系统 PATH 中）
- YAML 文件使用 2 空格缩进，不使用 Tab
- 不删除 `specs/` 目录和 `quant_ai.db`
- `settings.local.json` 修改时保留已有的 `defaultMode: bypassPermissions`
- git commit message 使用中文，格式：`类型: 描述`
