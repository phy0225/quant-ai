# AI 自动化研发操作手册 v2

> **工具链**：Claude Code + 仓库内置 overnight-execute skill + GitHub Actions
> **工作模式**：人工做 Brainstorm + Plan（1-2h）→ push tasks.md → 过夜 GitHub Actions 自动执行 → 次日看 PR 或 Issue 验收 → Merge

---

## 核心流程（端到端）

```
需求/Bug 描述
      │
      ▼
【Brainstorm】        /superpowers:brainstorming    人工，15-30 min
      │  产出：specs/NNN-xxx/design.md
      ▼
【Plan】              /superpowers:writing-plans    人工，30-60 min
      │  产出：specs/NNN-xxx/tasks.md
      ▼  ← 17:00 前 git push，下班
【自动 Execute】      nightly.yml（GitHub Actions）  过夜，2-8h
      │  scheduler.yml 17:05 cron → nightly.yml
      │    → 每个 spec 独立 runner + overnight-execute skill
      │    → 三层测试门禁（L1 targeted / L2 regression / L3 review）
      │    → 成功：push feat/* 分支 + 自动开 PR（feat → dev）
      │    → 失败：自动开 GitHub Issue
      ▼
【CI 自动验证】       ci.yml（GitHub Actions）       自动，push/PR 触发
      │  pytest（后端）+ npm run type-check + vite build（前端）
      │  PR 以 CI 通过作为合并门禁
      ▼
【次日验收】          GitHub PR + CI 状态           次日 09:00，15-30 min
      │  Chrome MCP 辅助功能验收
      ▼
【Merge feat → dev】  人工合并 PR                   5 min
      │  push dev → 再次触发 ci.yml
      ▼
【Merge dev → master】人工合并                      5 min
      │  push master → 触发 deploy.yml
      ▼
【自动部署】          deploy.yml（GitHub Actions）   自动，5-10 min
      │  Docker 构建 + SSH 部署到服务器
      ▼
【Release（按需）】   git tag vX.Y.Z → release.yml  人工
```

---

## 一、一次性环境准备

> 只需在首次使用时完成，之后无需重复。

### 1.1 安装 Claude Code

```powershell
npm install -g @anthropic-ai/claude-code
claude   # 首次运行，浏览器登录 Anthropic 账户
```

### 1.2 安装 Superpowers Skills（可选，但推荐）

在 Claude Code 交互式会话中执行（二选一）：

```
# 方式 A：官方
/plugin install superpowers

# 方式 B：社区 Marketplace
/plugin marketplace add obra/superpowers-marketplace
/plugin install superpowers@superpowers-marketplace
```

验证：执行 `/help`，看到 `/superpowers:brainstorming`、`/superpowers:writing-plans` 则成功。

> **说明**：
> Brainstorm / Plan 阶段可以使用 Superpowers。
> 但夜间 GitHub Actions 执行阶段依赖的是仓库内的 `.claude/skills/overnight-execute.md`，
> 不要求 runner 再安装额外的 Superpowers 子技能。

### 1.3 配置 GitHub Secret（必须）

新流程的过夜执行在 GitHub Actions 云端运行，需要你的 Anthropic API Key：

1. 打开仓库页面 → **Settings** → **Secrets and variables** → **Actions**
2. 点击 **New repository secret**
3. 填写：
   - Name：`ANTHROPIC_API_KEY`
   - Value：`sk-ant-xxxxxxxxxx`（你的 Anthropic API Key）
4. 点击 **Add secret**

> **注意**：`GITHUB_TOKEN` 是 GitHub 自动提供的，无需手动配置。

### 1.4 确认 dev 分支存在

过夜执行成功后会自动开 PR 合并到 `dev` 分支，确认仓库有 `dev`：

```bash
git branch -a | findstr dev
# 如果没有：
git checkout -b dev && git push origin dev
```

### 1.5 本地开发环境（可选，本地调试时需要）

```powershell
# 后端
cd backend
python -m venv .venv && .venv\Scripts\activate
pip install -r requirements.txt -r requirements-test.txt

# 前端
cd frontend && npm install
npm run type-check
```

### 1.6 本地快速验收入口（推荐先跑）

```powershell
python auto_fix.py --test-only --skip-e2e --provider codex --model gpt-5.4
```

如果只想预览流程，不执行：

```powershell
python auto_fix.py --req 需求文档-v2_0.md --provider codex --model gpt-5.4 --dry-run
```

---

## 二、阶段一：Brainstorm（需求分析）

**输入**：需求文档 或 Bug 描述
**产出**：`specs/NNN-xxx/design.md`
**时间**：15-30 分钟
**工具**：Claude Code 交互式会话

### 操作步骤

1. 打开 Claude Code，进入项目目录

2. 告诉 Claude 你要做什么：

```
使用 superpowers brainstorming skill 分析以下需求并做技术设计：

【需求描述】
用户在触发分析后跳到其他页面再回来，分析状态丢失。
需要在离页和刷新后恢复分析状态。
```

3. `brainstorming` Skill 会自动引导追问，帮你明确：
   - 涉及哪些文件/函数（精确到函数名）
   - 技术方案选型
   - Out of Scope（不做什么）
   - 验收标准（EARS 格式）

4. 遇到需要复现的 Bug，让 Claude 用 Chrome MCP 截图：

```
帮我在浏览器打开 http://localhost:5174，复现这个问题并截图
```

### 完成标准

```
□ 问题已实际复现，截图存证（如有 Bug）
□ design.md 已生成：specs/NNN-xxx/design.md
□ 涉及文件/函数定位到函数名
□ 方案已选定，Out of Scope 已明确
□ 验收标准已写清楚
```

### specs 目录结构

多个需求按编号建目录：

```
specs/
├── 001-analysis-state-persistence/
│   ├── design.md    ← Brainstorm 产出
│   └── tasks.md     ← Plan 产出（执行前确认存在）
├── 002-risk-limit-v2/
│   ├── design.md
│   └── tasks.md
└── 003-backtest-history/
    ├── design.md
    └── tasks.md
```

---

## 三、阶段二：Plan（任务拆解）

**输入**：`specs/NNN-xxx/design.md`
**产出**：`specs/NNN-xxx/tasks.md`
**时间**：30-60 分钟
**工具**：Claude Code 交互式会话

### 操作步骤

1. 在 Claude Code 中继续（或新开会话）：

```
使用 superpowers writing-plans skill，基于 specs/001-analysis-state-persistence/design.md 生成实现计划
```

2. `writing-plans` Skill 自动将 design 拆成 2-5 分钟微任务，每个任务包含：
   - 精确文件路径（精确到函数名）
   - 实现描述（约 5-10 行代码）
   - 验证命令（pytest 测试函数名级别）

### 任务粒度标准

```
❌ 太粗（AI 无法确定实现范围）：
## Task 1：修复分析状态丢失

✅ 正确（精确到函数名 + 验证命令）：
## Task 1.1：创建 analysisStore.ts
在 frontend/src/stores/analysisStore.ts 新建 Pinia store，
包含 activeRunId (string|null) 和 isAnalyzing (boolean) 两个 state，
持久化到 sessionStorage。（约 30 行）
验证：npx tsc --noEmit（无类型报错）
```

### 末尾必须有"执行约束"段落

tasks.md 末尾需要告诉过夜执行引擎做哪些最终验证：

```markdown
## 执行约束

- 不删除 quant_ai.db
- 所有 AKShare 调用用 asyncio.to_thread() 包裹

最终验证命令（按顺序执行，全部通过才算完成）：
1. `cd backend && pytest tests/ --cov --cov-fail-under=70 -q`
2. `cd frontend && npx tsc --noEmit`
3. `cd frontend && npm run build`
```

### 完成标准（17:00 前确认，下班）

```
□ 每个 Task ≤ 5 分钟，精确到函数名
□ 每个 Task 有验证命令（pytest 函数名级别或 tsc/build）
□ 末尾有"执行约束"段落
□ 文件保存到 specs/NNN-xxx/tasks.md
```

---

## 四、触发过夜执行（Git Push）

**操作**：把 tasks.md push 到 GitHub，GitHub Actions 会在 17:05 自动执行
**时间**：2 分钟（人工），2-8h（自动执行）

### 操作步骤

```bash
# 把 specs/ 下的所有新文件提交并推送
git add specs/
git commit -m "plan: 新增 001-analysis-state-persistence 任务计划"
git push origin master   # 或 dev，只要文件在远端即可
```

推送后：
- **17:05（北京时间）**：`scheduler.yml` 触发 `nightly.yml`
- `detect-specs` job 自动扫描 `specs/*/tasks.md`
- 发现 1 个待执行 spec → 启动 `execute` job
- `overnight-execute` skill 按 TDD + 三层测试门禁逐任务实现
- 完成后自动推送 `feat/001-analysis-state-persistence-20260401-<run_number>` 分支

> **如果需要立即执行（不等 17:05）**：
> 在 GitHub 仓库页面 → **Actions** → **Nightly AI Execute** → **Run workflow**

### GitHub Actions 执行过程

```
detect-specs job
  └── 扫描 specs/ 目录 → 发现 N 个 tasks.md

execute job（每个 spec 独立 runner）
  ├── 安装 Claude Code CLI + Python + Node.js
  ├── overnight-execute skill 执行：
  │     Step 0: 建立测试基线（记录当前失败项）
  │     Step 1: 读 CLAUDE.md + tasks.md（保持干净上下文）
  │     Step 2: 逐任务 TDD（RED→GREEN→L1→L2→L3）
  │     Step 3: 失败时最多重试 3 轮（systematic debugging）
  │     Step 4: 全量验证门禁（coverage + tsc + build）
  └── 成功 → push feat/* 分支
      失败 → 上传失败日志 artifact

consolidate job
  ├── 成功的 spec → 自动 gh pr create（feat/* → dev）
  └── 失败的 spec → 自动 gh issue create（含失败链接）
```

### 三层测试门禁说明

| 层级 | 时机 | 内容 |
|------|------|------|
| L1 Targeted | 每个 Task 完成后 | 运行 tasks.md 该 Task 的验证命令 |
| L2 Regression | 每个 Task 完成后 | 全量 pytest，与基线对比，无新增失败 |
| L3 Review | 每个 Task 完成后 | 代码自审，检查测试覆盖、异常路径与越界改动 |

---

## 五、次日早上验收

### 09:00 检查 GitHub（5 分钟）

打开 GitHub 仓库，两种情况：

**情况 A：看到 PR（执行成功）**

```
仓库 → Pull requests → feat/001-analysis-state-persistence-20260401-123
```

点开 PR，查看：
- **CI 是否通过**（绿色 ✅ = ci.yml 中 pytest + tsc + build 全部通过）
- 改动文件列表是否符合预期
- PR 描述（取自 tasks.md 前 20 行）

> CI 未通过时 PR 无法合并。先看 CI 日志，让 Claude 修复后 push 到同一 feat/* 分支，CI 会重新跑。

**情况 B：看到 Issue（执行失败）**

```
仓库 → Issues → "🔴 Nightly Execute 失败：2026-04-01"
```

Issue 里有 Actions 日志链接，点进去看哪个 Task 失败了。

> **查看详细执行日志**：
> 仓库 → Actions → Nightly AI Execute → 选择运行记录 → 展开 execute job → 查看日志

### 09:10 Chrome MCP 辅助功能验收（15 分钟）

```
帮我验收分析状态持久化功能：
打开 http://localhost:5174/analyze，
点击"开始分析"，然后切换到"持仓管理"页面，
再切换回来，验证分析状态是否已恢复，截图存证
```

### 分情况处理

| 情况 | 操作 |
|------|------|
| PR 存在 + CI 通过 + 验收通过 | → 走 Merge 流程（§六）|
| PR 存在 + CI 失败 | 看 CI 日志，让 Claude 修复，push 到同一分支 |
| Issue 存在（执行失败）| 看失败 Task，修改 tasks.md，手动重触发 |
| 功能验收不通过（理解偏差）| 修改 tasks.md，手动重触发 nightly.yml |

### 手动重触发执行

```bash
# 重跑所有 spec
gh workflow run nightly.yml

# 只跑某个 spec
gh workflow run nightly.yml --field specs_filter="specs/001-analysis-state-persistence"

# 查看执行状态
gh run list --workflow=nightly.yml
```

---

## 六、Merge + Deploy（人工，5 分钟）

验收通过后，在 GitHub 上合并 PR，或本地 merge：

```bash
# PR 在 GitHub 上合并（推荐）
# 打开 PR 页面 → "Merge pull request"

# 或本地 merge
git checkout dev
git merge --ff-only feat/001-analysis-state-persistence-20260401-123
git push origin dev      # 触发 CI（dev 分支）

# dev 验证通过后 merge 到 master，触发部署
git checkout master
git merge --ff-only dev
git push origin master   # 触发 deploy.yml → Docker + SSH 部署
```

### 打 Release Tag（版本发布时）

```bash
git tag -a v2.1.0 -m "Release v2.1.0：分析状态持久化"
git push origin v2.1.0   # 触发 release.yml → GitHub Release
```

---

## 七、每日节奏

| 时间 | 做什么 | 工具 |
|------|--------|------|
| 09:00 | 检查 GitHub PR 或 Issue | 浏览器 |
| 09:05 | Chrome MCP 辅助功能验收 | Claude + Chrome MCP |
| 09:30 | Merge PR：feat → dev → master | git / GitHub |
| 09:35 | 确认 deploy.yml 成功（GitHub Actions 日志） | GitHub Actions |
| 下午 | Brainstorm 下一个需求 | `/superpowers:brainstorming` |
| 下午 | Plan，审查 tasks.md | `/superpowers:writing-plans` |
| **17:00** | **git push tasks.md，下班** | git |
| 17:05 | scheduler.yml 自动触发 nightly.yml | GitHub Actions |
| 次日 09:00 | 循环 | — |

---

## 八、GitHub Actions Workflow 说明

### 五个 Workflow 的职责

| Workflow | 触发条件 | 作用 | 是否自动 |
|----------|---------|------|---------|
| `scheduler.yml` | 每工作日 17:05（北京时间） | 定时触发 nightly.yml | ✅ 全自动 |
| `nightly.yml` | scheduler.yml 或手动 | 扫描 specs、AI 执行任务、开 PR/Issue | ✅ 全自动 |
| `ci.yml` | push feat/* / dev / master，PR | pytest + `npm run type-check` + vite build，质量门禁 | ✅ 全自动 |
| `deploy.yml` | push master | Docker 构建 + SSH 部署到服务器 | ✅ 全自动 |
| `release.yml` | push v* tag | 构建 + 发布 GitHub Release | 人工打 tag 触发 |

### CI 流程说明

**nightly.yml 内置三层测试门禁**（过夜执行时）：
```
L1 Targeted  — 每个 Task 完成后跑该任务的验证命令
L2 Regression — 每个 Task 完成后跑全量 pytest，与基线对比
L3 Review     — 每个 Task 完成后做一次代码自审，检查测试覆盖
```

**ci.yml 独立验证**（push 触发）：
```
Push feat/* → ci.yml 自动运行（pytest + npm run type-check + build）
PR merge 门禁：CI 未通过无法合并
Push master → ci.yml + deploy.yml（部署到服务器）
```

两层测试互补：nightly 保证实现正确性，ci.yml 保证环境兼容性（Python/Node 版本、依赖）。

---

## 九、CLAUDE.md 维护

`CLAUDE.md` 是过夜执行引擎的约束来源，新发现的坑立刻记录：

```markdown
## 已知坑（禁止操作）

| 时间 | 问题 | 正确做法 |
|------|------|---------|
| 2026-03 | rm 删除 quant_ai.db | Schema 变更只用 ALTER TABLE，禁止删库 |
| 2026-03 | AKShare 同步调用阻塞事件循环 | 所有 AKShare 调用用 asyncio.to_thread() |
| 2026-03 | portfolio router 被 include 两次 | 每个 router 只 include_router 一次 |
```

格式：`| 日期 | 踩的坑 | 正确做法 |`，直接加一行即可。

---

## 十、常见问题

| 问题 | 解答 |
|------|------|
| 没有看到 PR，也没有 Issue？ | 可能是 scheduler.yml 还没触发（北京时间 17:05），或 `specs/` 下没有 `tasks.md`。去 Actions 页面手动触发确认。 |
| nightly.yml 找不到 specs？ | 确认 `specs/NNN-xxx/tasks.md` 已 push 到 GitHub（不是只在本地）。PowerShell 可用 `Get-ChildItem specs -Recurse -Filter tasks.md` 本地验证。 |
| 执行失败，Issue 说哪个 Task 失败了？ | Issue 里有 Actions 运行链接，点进去展开 execute job，搜索 `TASK_FAILED` 或 `❌` 找到失败位置。 |
| 想只重跑某一个 spec？ | `gh workflow run nightly.yml --field specs_filter="specs/001-xxx"` |
| PR 的目标分支不是 dev？ | 修改 `.github/workflows/nightly.yml` consolidate job 中 `--base dev` 为你需要的分支。 |
| CI 失败（本地通过）？ | 通常是 Python/Node 版本或环境变量差异，查 CI 日志，让 Claude 修复后 push 到同一分支。 |
| tasks.md 写完了，但觉得描述不够精确怎么办？ | 重新 `/superpowers:writing-plans`，或直接编辑 tasks.md 补充函数名和验证命令，再 push。 |
| overnight-execute skill 在哪里？能修改吗？ | `.claude/skills/overnight-execute.md`，纯 Markdown，直接编辑即可修改执行行为。 |
| 想换一个不同的 cron 时间？ | 编辑 `.github/workflows/scheduler.yml` 第 4 行的 cron 表达式（UTC 时间）。 |
| Skills 没有自动激活？ | 手工阶段的 Superpowers 安装后可重启 Claude Code；夜间执行只需确认 `.claude/skills/overnight-execute.md` 已提交到仓库。 |

---

## 十一、迁移到新项目（3 文件 + 1 Secret）

把这个流程复制到任何 GitHub 项目，只需要 3 个文件：

```bash
# 在新项目根目录执行
mkdir -p .github/workflows .claude/skills

cp <本项目>/.github/workflows/scheduler.yml  .github/workflows/
cp <本项目>/.github/workflows/nightly.yml    .github/workflows/
cp <本项目>/.claude/skills/overnight-execute.md .claude/skills/
```

然后按新项目调整（约 5 分钟）：

1. `scheduler.yml` 第 4 行：改 cron 时间
2. `overnight-execute.md` Step 4：改全量测试命令（默认已适配 pytest + tsc + build）
3. 新项目 GitHub → Settings → Secrets → 添加 `ANTHROPIC_API_KEY`
4. 确保新项目有 `dev` 分支

> 如果新项目还要复用自动部署链路，再额外复制：
> `deploy.yml`、`docker-compose.prod.yml`、`backend/Dockerfile`、`frontend/Dockerfile`、`scripts/deploy_loaded_images.sh`
