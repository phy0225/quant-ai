# Specs Workspace

把待执行需求放在 `specs/<编号>-<名称>/` 目录下。

每个 spec 目录至少包含：

- `design.md`：Brainstorm 阶段产出
- `tasks.md`：Plan 阶段产出

`nightly.yml` 只会扫描 `specs/*/tasks.md`。
如果这里只有本文件而没有任何 `tasks.md`，夜间工作流会正常跳过。
