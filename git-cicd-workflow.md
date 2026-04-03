# 需求文档到 CI/CD 的 Git 流程梳理

本文档只梳理本项目中和 `git` 直接相关的流程，不展开业务设计、实现细节和部署脚本内部逻辑。

当前仓库实际生效的主线是 GitHub 流程：

- 自动化入口脚本：`scripts/run_speckit_flow.sh`
- CI/CD 工作流：`.github/workflows/ci.yml`、`.github/workflows/deploy.yml`、`.github/workflows/release.yml`

`docs/gitcode-speckit-workflow.md` 属于 GitCode 版本说明，可参考，但不是当前仓库主线。

## 1. Git 视角下的主流程

```text
需求文档
  -> 运行 scripts/run_speckit_flow.sh --doc <需求文档>
  -> 创建/切换到 feature 分支
  -> 在 feature 分支上生成/修改代码
  -> 本地校验
  -> git add + git commit
  -> git push feature 分支
  -> 触发 CI
  -> 合并到 dev / master
  -> push 目标分支
  -> 触发 CI 或 Deploy
  -> git tag vX.Y.Z
  -> git push origin vX.Y.Z
  -> 触发 Release
```

## 2. 从需求文档进入 Git 流程

入口命令通常是：

```bash
./scripts/run_speckit_flow.sh \
  --doc docs/QUANT实体与特征设计.md \
  --short-name quant-release
```

这个脚本和 Git 直接相关的行为是：

1. 读取 `--doc` 指定的需求文档。
2. 调用 `.specify` 工作流创建新的 feature 分支。
3. 在该分支上生成或修改 `specs/<feature>/` 和业务代码。
4. 本地执行校验。
5. 如果有文件变更，执行 `git add -A` 和 `git commit`。
6. 根据参数决定是否 `push`、`merge`、`tag`、`push tag`。

脚本默认要求：

- 当前目录必须是 Git 仓库。
- 工作区默认必须干净，否则会中止。
- 如需推送，必须已配置 `origin`。

## 3. 脚本里的 Git 关键步骤

### 3.1 创建 feature 分支

在 `specify` 阶段，脚本会通过 `.specify/scripts/bash/create-new-feature.sh --json` 创建 feature 分支。

结果是：

- 当前工作分支切到新的 feature 分支
- 后续所有文档和代码修改都发生在这个分支上

### 3.2 本地提交

实现和校验完成后，`scripts/run_speckit_flow.sh` 会在检测到变更时执行：

```bash
git add -A
git commit -m "feat: <branch-suffix>"
```

这里的提交是整条自动化链路进入远端 CI/CD 的起点。

### 3.3 推送 feature 分支

如果命令里带了 `--push`，脚本会执行：

```bash
git push -u origin <current-branch>
```

这一步会把 feature 分支推到远端，并触发 CI。

### 3.4 合并目标分支

如果带了 `--merge-to <branch>`，脚本会：

1. `git fetch origin <branch>`
2. 切换到目标分支
3. 同步远端目标分支
4. 执行 `git merge --ff-only <feature-branch>`

这里使用的是 `--ff-only`，即：

- 只允许快进合并
- 不自动制造 merge commit
- 如果分支历史不满足快进条件，脚本会失败

### 3.5 推送目标分支

如果同时带了 `--push-target`，脚本会执行：

```bash
git push origin <target-branch>
```

在当前仓库配置下，推送 `master` 会触发部署。

### 3.6 创建和推送版本 Tag

如果带了 `--tag vX.Y.Z`，脚本会执行：

```bash
git tag -a vX.Y.Z -m "Release vX.Y.Z"
```

然后在满足推送条件时执行：

```bash
git push origin vX.Y.Z
```

推送 `v*` tag 会触发 Release 工作流。

## 4. Git 动作和 GitHub Actions 的对应关系

### 4.1 推送 feature 分支

当你 push 到形如 `0**-*` 的 feature 分支时，会触发 `.github/workflows/ci.yml`。

CI 执行内容：

- 后端 `pytest`
- 前端 `npm run type-check`
- 前端 `npm run build`

### 4.2 提交 Pull Request

当前配置中，任意 Pull Request 也会触发 `.github/workflows/ci.yml`。

这意味着：

- feature 分支提 PR 时会跑 CI
- 合并前可以用 CI 作为门禁

### 4.3 推送 `dev`

push 到 `dev` 也会触发 `.github/workflows/ci.yml`。

适合把 `dev` 作为集成验证分支。

### 4.4 推送 `master`

push 到 `master` 会触发两个结果：

1. `.github/workflows/ci.yml`
2. `.github/workflows/deploy.yml`

其中 `deploy.yml` 负责：

- 构建前后端 Docker 镜像
- 通过 SSH 上传部署文件和镜像
- 在服务器执行部署脚本

所以从 Git 视角看，`master` 是部署触发分支。

### 4.5 推送版本 Tag

push `v*` tag 会触发 `.github/workflows/release.yml`。

Release 工作流会：

- 再跑一次测试和构建
- 调用 `gh release create` 创建 GitHub Release

所以从 Git 视角看，版本发布的触发器是 tag，而不是 branch。

## 5. 推荐的 Git 流程顺序

### 方案 A：先走 feature 分支 CI，再合并

```text
需求文档
  -> 创建 feature 分支
  -> 本地实现
  -> commit
  -> push feature 分支
  -> CI
  -> 提 PR
  -> 合并到 dev 或 master
  -> push 目标分支
  -> CI / Deploy
  -> 打 tag
  -> push tag
  -> Release
```

适合正常团队协作。

### 方案 B：脚本直接推进到 master

```bash
./scripts/run_speckit_flow.sh \
  --doc docs/QUANT实体与特征设计.md \
  --short-name quant-release \
  --merge-to master \
  --push-target \
  --tag v0.1.0
```

这条链路对应的 Git 动作是：

1. 创建 feature 分支并完成修改。
2. 自动提交当前 feature 分支。
3. fast-forward 合并到 `master`。
4. push `master`，触发 Deploy。
5. 创建并 push `v0.1.0` tag，触发 Release。

这种方式更快，但要求操作者对 `master` 有直接推送权限。

## 6. 一句话总结

如果只看 Git 相关 CI/CD，这个项目的主线就是：

`需求文档 -> feature 分支 -> commit -> push -> CI -> merge 到 master -> push master -> Deploy -> tag -> push tag -> Release`

## 7. 相关文件

- `scripts/run_speckit_flow.sh`
- `.github/workflows/ci.yml`
- `.github/workflows/deploy.yml`
- `.github/workflows/release.yml`
- `docs/requirements-to-cicd-workflow.md`
