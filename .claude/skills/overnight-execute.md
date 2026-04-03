# Overnight Execute

无人值守自动执行 spec 任务。读取指定 spec 目录的 `tasks.md`，
按 TDD + 三层测试门禁逐一实现，全部通过后输出 `DONE`。

## 调用方式

```
/overnight-execute <spec-path>
/overnight-execute specs/001-analysis-state-persistence
/overnight-execute
```

不传参数时，扫描 `specs/*/tasks.md`，按目录名排序逐个执行。

## 执行流程

### Step 0：建立测试基线

开始任何任务前，先跑全量测试并记录当前状态：

```bash
cd backend && pytest tests/ -v --tb=no -q 2>&1 | tee /tmp/baseline.txt
```

记录已知失败条目，避免把旧失败误判成新回归。

### Step 1：只加载必要上下文

按顺序只读以下文件：

1. `CLAUDE.md`
2. `<spec-path>/tasks.md`
3. `<spec-path>/design.md`，如果存在

除非某个 Task 明确点名文件，否则不要扩散读取无关目录。

### Step 2：逐任务执行

对 `tasks.md` 中每个 `## Task N.N` 按顺序执行：

**[READ]**
只读取该任务显式提到的文件、函数和测试文件。

**[RED]**
先写或补一个失败测试，测试名与任务号对应。
如果仓库已有等价测试，则先运行它并确认当前是红的。

**[GREEN]**
做最小实现让 RED 变成 GREEN。
不做顺手重构，不扩大修改范围。

**[L1 Targeted]**
运行该任务行内写明的“验证”命令。
失败则直接进入 Step 3。

**[L2 Regression]**
运行全量回归并和基线对比：

```bash
cd backend && pytest tests/ -v --tb=short -q 2>&1 | tee /tmp/current.txt
```

如果出现基线之外的新失败，视为本任务失败，进入 Step 3。

**[L3 Review]**
自行做一次代码审查，重点检查：

- 新增行为是否有测试覆盖
- 异常路径和边界条件是否被验证
- 是否破坏 `CLAUDE.md` 中的限制
- 是否引入无关改动

如果审查发现缺口，补测试或补实现后重新从 L1 开始验证。

### Step 3：失败处理

遇到失败时执行系统化排查：

1. 先读失败输出的第一现场
2. 缩小到最小相关代码和测试
3. 给出一个最可能根因
4. 只做一轮聚焦修复
5. 重新从 L1 开始验证

每个 Task 最多重试 3 轮。

3 轮后仍失败时：

```text
TASK_FAILED: <task-id> | <一句话错误摘要>
```

停止当前 spec 的后续任务，并以非 0 退出码结束。

### Step 4：全量验证门禁

所有任务完成后，优先执行 `tasks.md` 末尾“执行约束”段落中的最终验证命令。

如果没有该段落，则执行默认命令：

```bash
cd backend && pytest tests/ --cov --cov-fail-under=70 -q
cd frontend && npm run type-check
cd frontend && npm run build
```

全部通过后输出：

```text
DONE: <spec-path>
```

### Step 5：禁止行为

- 不做任何 git 操作，commit/push 由 GitHub Actions 处理
- 不修改 `tasks.md` 本身
- 不因“顺手优化”修改 Out of Scope 文件
- 不把测试失败含糊归因为“环境问题”然后跳过
- 不删除数据库文件，例如 `quant_ai.db`

## 迁移说明

此 Skill 不依赖 Superpowers 插件；项目差异通过仓库文件注入：

| 项目差异 | 注入位置 |
|---------|---------|
| 代码规范、禁止操作 | `CLAUDE.md` |
| 任务级验证命令 | `tasks.md` 每个 Task 的“验证”行 |
| 全量测试命令 | `tasks.md` 末尾“执行约束”段落 |
| 覆盖率阈值 | `tasks.md` 末尾命令中显式声明 |
