# AI 自动化研发操作手册

> **工具链**：Claude Code + Superpowers Skills + auto_fix.py + GitHub Actions
> **工作模式**：人工做 Brainstorm + Plan（1-2h）→ 过夜自动 Execute + Push → CI 自动验证 → 次日人工验收 + Merge

---

## 核心流程（端到端）

```
需求文档
    │
    ▼
【Brainstorm】  /superpowers:brainstorm          人工，15-30 min
    │  输入：需求文档 + 问题描述
    │  产出：specs/xxx/design.md
    ▼
【Plan】        /superpowers:write-plan           人工，30-60 min
    │  输入：design.md
    │  产出：specs/xxx/tasks.md（2-5 min 微任务 + 验证命令）
    ▼  ↑ 17:00 前确认，下班
【Execute】     auto_fix.py --plan specs/ --push  过夜自动，2-8h
    │  输入：specs/*/tasks.md
    │  产出：feat/* 分支 commit → push origin
    ▼
【CI】          GitHub Actions ci.yml             自动，push 触发
    │  pytest + tsc + vite build
    │  产出：CI 通过/失败状态
    ▼
【验收】        Chrome MCP 辅助验收               次日，15-30 min
    │  人工检查报告 + 浏览器验收
    ▼
【Merge + Deploy】  PR: feat → dev → master       人工，5 min
    │  push master → 触发 deploy.yml（Docker 构建 + SSH 部署）
    ▼
【Release】     git tag vX.Y.Z + push tag         按需，人工
               push v* tag → 触发 release.yml（GitHub Release）
```

---

## 一、工具安装（一次性）

### Claude Code

```powershell
npm install -g @anthropic-ai/claude-code
claude   # 首次运行，浏览器登录
```

### Superpowers（必装）

```
# 在 Claude Code 交互式会话中（二选一）

# 方式 A：官方
/plugin install superpowers

# 方式 B：社区 Marketplace
/plugin marketplace add obra/superpowers-marketplace
/plugin install superpowers@superpowers-marketplace
```

验证：执行 `/help`，看到 `/superpowers:brainstorm`、`/superpowers:write-plan` 则成功。

### 后端环境

```powershell
cd backend
python -m venv .venv && .venv\Scripts\activate
pip install -r requirements.txt -r requirements-test.txt
```

### Playwright E2E（可选）

```powershell
cd frontend
npm install -D @playwright/test
npx playwright install chromium
mkdir e2e
```

---

## 二、阶段一：Brainstorm

**输入**：需求文档（`需求文档-v2.0.md`）+ 你的问题描述
**产出**：`specs/xxx/design.md`

```
claude输入:使用 superpowers brainstorming skill 来分析需求文档-v2.1.md 并实现需求
```

`brainstorming` Skill 自动激活，通过追问引导你明确：涉及文件/函数、方案选型、Out of Scope。
遇到需要复现的 bug，让 Claude 用 Chrome MCP 在浏览器里实际操作截图，不靠文字描述。

**完成标准**：
```
□ 问题已实际复现，截图存证
□ design.md 生成，涉及文件/函数定位到函数名
□ 方案已选定，Out of Scope 已明确
```

---

## 三、阶段二：Plan

**输入**：`specs/xxx/design.md`
**产出**：`specs/xxx/tasks.md`

```
在claude中按引导完成审核后会自动调用/superpowers:write-plan
```

`writing-plans` Skill 自动激活，将 design 拆成 2-5 分钟微任务，每个任务含：
- 精确文件路径（精确到函数名）
- 验证命令（pytest 测试函数名级别）

**任务粒度对比**：
```
❌ 太粗：## Task 1：实现仓位合计约束

✅ 正确：## Task 1.1：仓位上限校验
   在 backend/routers/approvals.py 的 modify_weights() 中，
   在现有单标的校验后新增 other_weight 求和（约 8 行）。
   验证：pytest tests/test_api.py::test_modify_over_100pct_returns_422
```

**完成标准（17:00 前确认，下班）**：
```
□ 每个任务 ≤ 5 分钟，精确到函数名
□ 每个任务有 pytest 验证命令（函数名级别）
□ 末尾有"执行约束"段落（CLAUDE.md 关键规范引用）
□ 文件保存到 specs/xxx/tasks.md
```

多需求时按编号建目录：
```
specs/
├── 001-position-constraint/
│   ├── design.md
│   └── tasks.md
├── 002-graph-integration/
│   ├── design.md
│   └── tasks.md
└── 003-rl-optimizer/
    ├── design.md
    └── tasks.md
```

---

## 四、阶段三：Execute（过夜自动）

**输入**：`specs/*/tasks.md`
**产出**：`feat/*` 分支 → commit → push → 触发 CI

### 触发命令

```powershell
# 标准：读 specs/ 下所有 tasks.md，完成后自动创建 feature 分支、commit、push（触发 CI）
python -X utf8 auto_fix.py --plan specs/ --push --skip-e2e

# 不 push，只 commit（适合无网络/调试时）
python -X utf8 auto_fix.py --plan specs/ --commit --skip-e2e

# 只跑单个需求
python -X utf8 auto_fix.py --plan specs/001-position-constraint/ --push --skip-e2e

# 查看将执行的步骤（不实际执行）
python -X utf8 auto_fix.py --dry-run --plan specs/

# 只跑测试，不实现
python -X utf8 auto_fix.py --test-only
```

`--push` = `--commit` + 创建 `feat/<label>-<date>` 分支 + `git push origin` → 触发 GitHub Actions CI。

### Execute 内部流程

```
解析 specs/*/tasks.md → 按 001→002→003 顺序执行

每个 Task（Skills 自动激活）：
  [TDD RED]   先写失败测试          ← test-driven-development Skill
  [TDD GREEN] 最小实现让测试通过
  [VERIFY]    运行 Task 内嵌验证命令 ← verification-before-completion Skill

全量测试：pytest + tsc + vite build + Playwright E2E

失败时重试 ≤5 次：
  [DEBUG] 4 阶段根因分析            ← systematic-debugging Skill
  [REVIEW] 任务完成质量门禁         ← requesting-code-review Skill

全部通过 →
  git checkout -b feat/<label>-<date>
  git commit "feat: <label>"
  git push -u origin feat/<label>-<date>
  ↓ 触发 GitHub Actions ci.yml
```

### 定时触发

**推荐：让 Claude 创建定时任务**
```
帮我创建每天 17:05 自动运行的任务：
  cd D:\work\Quant_Trading\sdd_full && python -X utf8 auto_fix.py --plan specs/ --push --skip-e2e
```

**备选：Windows Task Scheduler**
```powershell
$action = New-ScheduledTaskAction `
    -Execute "powershell.exe" `
    -Argument "-NonInteractive -File D:\work\Quant_Trading\sdd_full\run_nightly.ps1" `
    -WorkingDirectory "D:\work\Quant_Trading\sdd_full"
$trigger = New-ScheduledTaskTrigger -Daily -At "17:05"
Register-ScheduledTask -TaskName "QuantAI-Nightly" -Action $action -Trigger $trigger -RunLevel Highest -Force
```

---

## 五、CI（自动，Push 触发）

`git push feat/*` 自动触发 `.github/workflows/ci.yml`：

```
CI 执行内容：
  ✓ pytest（后端）
  ✓ npm run type-check（前端 TypeScript）
  ✓ npm run build（前端构建）
```

次日早上到公司第一件事：**先看 CI 是否通过**，再看 auto_fix 报告。

---

## 六、次日早上验收

### 09:00 看报告和 CI 状态（10 分钟）

```powershell
# 看 auto_fix 本地报告
Get-ChildItem -File .test_reports\ | Sort-Object LastWriteTime -Descending | Select-Object -First 1 | Get-Content
```

同时在浏览器打开 GitHub → Actions，确认 CI 状态。

### 09:10 Chrome MCP 辅助验收（15 分钟）

```
帮我验收仓位约束功能：
打开 http://localhost:5174/approvals，
把某标的权重调到超出剩余空间，
验证提交是否禁用、红色警告是否出现，截图存证
```

### 分情况处理

| 情况 | 操作 |
|------|------|
| 本地报告 PASS + CI PASS + 验收通过 | → 走 Merge 流程 |
| 本地报告 FAIL | 重跑 `auto_fix.py --plan specs/ --push --skip-e2e` |
| CI FAIL（本地通过） | 看 CI 日志，通常是环境差异，让 Claude 修复 |
| 需求理解偏差 | `/superpowers:brainstorm` 重新澄清，修改 tasks.md |

---

## 七、Merge + Deploy（人工，5 分钟）

验收通过后走完整 git 链路：

```powershell
# 1. 在 GitHub 上提 PR：feat/* → dev，CI 作为合并门禁
#    （或本地 merge）
git checkout dev
git merge --ff-only feat/<label>-<date>
git push origin dev          # 触发 ci.yml（dev 分支 CI）

# 2. dev 验证通过后 merge 到 master，触发部署
git checkout master
git merge --ff-only dev
git push origin master       # 触发 deploy.yml → Docker 构建 + SSH 部署
```

`.github/workflows/deploy.yml` 会自动：
- 构建前后端 Docker 镜像
- SSH 上传到服务器
- 执行部署脚本

### 打 Release Tag（按版本发布时）

```powershell
git tag -a v2.1.0 -m "Release v2.1.0：仓位约束 + 图谱集成"
git push origin v2.1.0       # 触发 release.yml → GitHub Release
```

---

## 八、每日节奏

| 时间 | 做什么 | 工具 |
|------|--------|------|
| 09:00 | 看本地报告 + GitHub CI 状态 | PowerShell + GitHub |
| 09:10 | Chrome MCP 辅助验收 | Claude + Chrome MCP |
| 09:30 | Merge PR：feat → dev → master | git |
| 09:35 | 确认 Deploy 成功（deploy.yml 日志） | GitHub Actions |
| 下午 | Brainstorm 下一个需求 | `/superpowers:brainstorm` |
| 下午 | Plan，审查 tasks.md | `/superpowers:write-plan` |
| **17:00** | **确认 tasks.md，下班** | — |
| 17:05 | Execute 自动触发，push feature 分支 | `auto_fix.py --plan specs/ --push` |
| 次日 09:00 | 循环 | — |

---

## 九、GitHub Actions 触发规则速查

| Git 动作 | 触发的 Workflow | 结果 |
|---------|--------------|------|
| `push feat/*` | `ci.yml` | pytest + tsc + build |
| `push dev` | `ci.yml` | 同上 |
| Pull Request | `ci.yml` | CI 作为合并门禁 |
| `push master` | `ci.yml` + `deploy.yml` | CI + Docker 构建 + SSH 部署 |
| `push v*` tag | `release.yml` | 测试 + 构建 + GitHub Release |

---

## 十、CLAUDE.md 维护

新发现的坑立刻加进去，过夜 Execute 时 Agent 读取并遵守。

```markdown
| 时间 | 问题 | 正确做法 |
|------|------|---------|
| 2026-03 | rm 删除了 quant_ai.db | Schema 变更只用 ALTER TABLE，禁止删库 |
| 2026-03 | AKShare 同步调用阻塞事件循环 | 所有 AKShare 调用用 asyncio.to_thread() |
| 2026-03 | portfolio router 被 include 两次 | 每个 router 只 include_router 一次 |
| 2026-03 | Vue 模板缺闭合标签，tsc 不报错 | 改完 Vue 文件后必须跑 npm run build |
```

---

## 十一、常见问题

| 问题 | 解答 |
|------|------|
| 为什么不用 `/superpowers:execute-plan` 过夜？ | 它是交互式命令，遇到分支合并决策会暂停，无人值守会卡死。`auto_fix.py --plan` 调 `claude --print`，Skills 同样生效但不阻塞。 |
| `--push` 和 `--commit` 区别？ | `--commit` 只本地 commit；`--push` 额外创建 `feat/*` 分支并 push 到 origin，触发 GitHub CI。 |
| push 失败（no upstream / permission denied）？ | 确认 `git remote -v` 有 origin；确认 SSH key 或 PAT 已配置；手动 `git push -u origin <branch>`。 |
| CI FAIL 但本地测试通过？ | 通常是 Python/Node 版本差异或环境变量缺失，查 CI 日志确认，让 Claude 修复后重新 push。 |
| tasks.md 粒度太粗 AI 乱猜？ | 每个任务精确到函数名和大概行数，重新 `/superpowers:write-plan`。 |
| Skills 没有自动激活？ | 安装 Superpowers 后需重启 Claude Code；确认 `.claude/skills/` 目录有 `.md` 文件。 |
| 早上 CI 还在跑 / 超时？ | CI 默认超时 10 分钟，检查 `.github/workflows/ci.yml` 的 `timeout-minutes` 配置。 |
