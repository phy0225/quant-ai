#!/usr/bin/env python3
"""
自动化开发流水线
用法：python dev_pipeline.py <需求文档.md> [--no-commit]

流程：
  1. 读取需求文档
  2. 调用 Claude Code 实现需求
  3. 运行后端测试
  4. 运行前端类型检查
  5. 如果测试失败，重试最多 3 次
  6. 全部通过后 git commit
"""
import subprocess
import sys
import os
from pathlib import Path


def run(cmd: str, cwd: str = None) -> tuple[int, str, str]:
    """运行命令，返回 (returncode, stdout, stderr)"""
    result = subprocess.run(
        cmd, shell=True, cwd=cwd,
        capture_output=True, text=True, encoding="utf-8"
    )
    return result.returncode, result.stdout, result.stderr


def run_tests(backend_dir: str) -> tuple[bool, str]:
    """运行后端测试，返回 (passed, output)"""
    print("\n🧪 运行后端测试...")
    code, out, err = run("pytest tests/ -v --tb=short", cwd=backend_dir)
    output = out + err
    passed = code == 0
    if passed:
        print("  ✅ 后端测试全部通过")
    else:
        print("  ❌ 后端测试失败")
        # 提取失败的测试名
        for line in output.split("\n"):
            if "FAILED" in line or "ERROR" in line:
                print(f"     {line.strip()}")
    return passed, output


def run_ts_check(frontend_dir: str) -> tuple[bool, str]:
    """运行前端 TypeScript 类型检查"""
    print("\n📝 运行前端类型检查...")
    code, out, err = run("npx tsc --noEmit", cwd=frontend_dir)
    output = out + err
    passed = code == 0
    if passed:
        print("  ✅ TypeScript 类型检查通过")
    else:
        print("  ❌ TypeScript 类型错误")
        for line in output.split("\n")[:10]:
            if line.strip():
                print(f"     {line.strip()}")
    return passed, output


def git_commit(root_dir: str, message: str) -> bool:
    """提交代码"""
    print(f"\n📦 提交代码: {message}")
    code, _, err = run("git add -A", cwd=root_dir)
    if code != 0:
        print(f"  ❌ git add 失败: {err}")
        return False
    code, out, err = run(f'git commit -m "{message}"', cwd=root_dir)
    if code != 0:
        if "nothing to commit" in out + err:
            print("  ℹ️  没有变更需要提交")
            return True
        print(f"  ❌ git commit 失败: {err}")
        return False
    print(f"  ✅ 提交成功")
    return True


def main():
    if len(sys.argv) < 2:
        print("用法: python dev_pipeline.py <需求文档.md> [--no-commit]")
        sys.exit(1)

    req_file = Path(sys.argv[1])
    no_commit = "--no-commit" in sys.argv

    if not req_file.exists():
        print(f"❌ 需求文档不存在: {req_file}")
        sys.exit(1)

    # 路径配置
    script_dir   = Path(__file__).parent
    backend_dir  = str(script_dir / "backend")
    frontend_dir = str(script_dir / "frontend")
    root_dir     = str(script_dir)

    req_content = req_file.read_text(encoding="utf-8")
    print(f"📋 读取需求文档: {req_file.name}")
    print(f"   字数: {len(req_content)} 字符")

    # ── 第一步：先跑一次测试，确认基线 ────────────────────────────────────
    print("\n" + "="*60)
    print("步骤 1/4：确认当前测试基线")
    print("="*60)
    baseline_pass, _ = run_tests(backend_dir)
    if not baseline_pass:
        print("\n⚠️  基线测试已失败，请先修复现有问题再进行迭代开发")
        print("   提示：运行 pytest tests/ -v 查看详细错误")
        # 继续执行，Claude Code 会处理

    # ── 第二步：调用 Claude Code 实现需求 ────────────────────────────────
    print("\n" + "="*60)
    print("步骤 2/4：Claude Code 实现需求")
    print("="*60)
    print(f"\n🤖 启动 Claude Code（非交互模式）...")
    print("   提示：如需交互式开发，直接运行 'claude' 命令")

    # 构建 Claude Code 指令
    claude_prompt = f"""请阅读并实现以下需求文档中的所有需求。

需求文档内容：
---
{req_content}
---

实现要求：
1. 严格遵守 CLAUDE.md 中的代码规范
2. 新增的 AKShare 调用必须用 asyncio.to_thread 包裹
3. Agent 无数据时不调 LLM，返回 hold + 低置信度
4. 新增数据库模型必须同步更新 models.py
5. 新增前端页面必须在 router/index.ts 注册路由
6. 实现完成后，确保 backend/tests/ 中的相关测试能通过
"""

    # 尝试运行 Claude Code（需要已安装）
    code, out, err = run(
        f'claude --print "{claude_prompt.replace(chr(34), chr(39))}"',
        cwd=root_dir
    )
    if code != 0:
        print(f"  ⚠️  Claude Code 命令行工具未找到或出错")
        print(f"  请手动运行: cd {root_dir} && claude")
        print(f"  然后粘贴需求文档内容")

    # ── 第三步：运行测试，最多重试 3 次 ───────────────────────────────────
    print("\n" + "="*60)
    print("步骤 3/4：验证测试")
    print("="*60)

    max_retries = 3
    for attempt in range(1, max_retries + 1):
        print(f"\n  第 {attempt}/{max_retries} 次测试...")
        backend_ok, backend_output = run_tests(backend_dir)
        ts_ok, ts_output = run_ts_check(frontend_dir)

        if backend_ok and ts_ok:
            print(f"\n✅ 所有测试通过（第 {attempt} 次）")
            break

        if attempt < max_retries:
            print(f"\n  🔧 测试失败，让 Claude Code 修复...")
            fix_errors = []
            if not backend_ok:
                fix_errors.append(f"后端测试错误：\n{backend_output[-2000:]}")
            if not ts_ok:
                fix_errors.append(f"TypeScript 错误：\n{ts_output[-1000:]}")

            fix_prompt = f"""测试失败，请修复以下错误：

{"".join(fix_errors)}

修复后重新确认代码符合 CLAUDE.md 规范。"""

            run(f'claude --print "{fix_prompt.replace(chr(34), chr(39))}"', cwd=root_dir)
    else:
        print(f"\n❌ 经过 {max_retries} 次尝试仍有测试失败")
        print("   请手动检查并修复，然后重新运行此脚本")
        sys.exit(1)

    # ── 第四步：提交代码 ───────────────────────────────────────────────────
    print("\n" + "="*60)
    print("步骤 4/4：提交代码")
    print("="*60)

    if no_commit:
        print("  ⏭️  跳过提交（--no-commit）")
    else:
        commit_msg = f"feat: {req_file.stem}"
        git_commit(root_dir, commit_msg)

    print("\n" + "="*60)
    print("🎉 流水线完成！")
    print("="*60)


if __name__ == "__main__":
    main()
