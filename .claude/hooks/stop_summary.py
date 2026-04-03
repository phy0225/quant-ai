#!/usr/bin/env python3
"""
Stop hook: displays a checklist reminder when Claude finishes a session.
"""
import json
import sys


def main() -> None:
    print(json.dumps({
        "systemMessage": (
            "📋 Harness 提醒 | "
            "① 有完成的任务？→ 更新 specs/*/tasks.md 勾选进度  "
            "② 有新增路由/字段？→ 确认 schemas.py + conftest.py 同步更新  "
            "③ AKShare 调用？→ 确认用了 asyncio.to_thread()  "
            "④ 查看改动：git diff --stat"
        )
    }))
    sys.exit(0)


if __name__ == "__main__":
    main()
