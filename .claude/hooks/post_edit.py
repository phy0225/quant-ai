#!/usr/bin/env python3
"""
PostToolUse hook: runs tests after Edit/Write tool calls.

- backend/*.py  -> pytest tests/test_units.py -x -q --tb=short
- frontend/src/*.ts or *.vue -> npx tsc --noEmit
- Other files: silent exit(0)

On failure: outputs JSON with additionalContext and exits with code 2
so Claude Code triggers asyncRewake.
"""
import json
import os
import subprocess
import sys


def main() -> None:
    # Read the hook event payload from stdin
    try:
        payload = json.load(sys.stdin)
    except Exception:
        payload = {}

    # Extract the file path that was just written/edited
    tool_input = payload.get("toolInput") or payload.get("tool_input") or {}
    file_path: str = tool_input.get("file_path") or tool_input.get("path") or ""

    if not file_path:
        sys.exit(0)

    # Normalise to forward slashes for comparison
    norm = file_path.replace("\\", "/")

    # Derive project root: this file lives at <root>/.claude/hooks/post_edit.py
    hooks_dir = os.path.dirname(os.path.abspath(__file__))
    claude_dir = os.path.dirname(hooks_dir)
    project_root = os.path.dirname(claude_dir)

    # Decide what to run
    if "/backend/" in norm and norm.endswith(".py"):
        cmd = [
            sys.executable, "-m", "pytest",
            "tests/test_units.py",
            "-x", "-q", "--tb=short",
        ]
        cwd = os.path.join(project_root, "backend")
        label = "pytest tests/test_units.py"
    elif "/frontend/src/" in norm and (norm.endswith(".ts") or norm.endswith(".vue")):
        npx = "npx.cmd" if sys.platform == "win32" else "npx"
        cmd = [npx, "tsc", "--noEmit"]
        cwd = os.path.join(project_root, "frontend")
        label = "npx tsc --noEmit"
    else:
        # Not a file we watch
        sys.exit(0)

    # Run the command
    try:
        result = subprocess.run(
            cmd,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=90,
        )
    except subprocess.TimeoutExpired:
        _fail("命令超时（>90s）", label, "TimeoutExpired")
        return
    except FileNotFoundError as exc:
        _fail(f"命令未找到: {exc}", label, "")
        return

    combined = (result.stdout or "") + (result.stderr or "")
    lines = combined.splitlines()

    if result.returncode == 0:
        print(f"✅ 测试通过 [{label}]")
        sys.exit(0)
    else:
        # Keep last 30 lines to avoid flooding Claude context
        tail = "\n".join(lines[-30:]) if len(lines) > 30 else combined
        _fail(tail, label, f"exit code {result.returncode}")


def _fail(output: str, label: str, detail: str) -> None:
    context = (
        f"[post_edit hook] `{label}` 失败（{detail}）。\n"
        f"请分析以下错误并修复：\n\n"
        f"```\n{output}\n```"
    )
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PostToolUse",
            "additionalContext": context,
        }
    }))
    sys.exit(2)


if __name__ == "__main__":
    main()
