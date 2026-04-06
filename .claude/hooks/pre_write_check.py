#!/usr/bin/env python3
"""
PreToolUse hook: validates AKShare async conventions before Write/Edit.

For any .py file under backend/, checks that ak.<func>(...) calls
are always wrapped in asyncio.to_thread / to_thread within 5 lines.

Outputs JSON with permissionDecision = "block" or "allow".
Always exits with code 0; blocking is communicated via the JSON payload.
"""
import json
import re
import sys


# Regex to detect a direct ak.<something>( call
AK_CALL_RE = re.compile(r'\bak\.\w+\s*\(')
# Regex to detect asyncio.to_thread / to_thread usage
TO_THREAD_RE = re.compile(r'to_thread')


def _allow() -> None:
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "allow",
        }
    }))
    sys.exit(0)


def _block(reason: str) -> None:
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "block",
            "permissionDecisionReason": reason,
        }
    }))
    sys.exit(0)


def is_comment_or_string_line(line: str) -> bool:
    """Simple heuristic: skip lines that are pure comments or string literals."""
    stripped = line.strip()
    if stripped.startswith("#"):
        return True
    # Lines that start with a quote character are likely string/docstring lines
    if stripped and stripped[0] in ('"', "'"):
        return True
    return False


def check_content(content: str) -> tuple[bool, str]:
    """
    Returns (violation_found, message).
    violation_found=True means we detected an ak.xxx() without to_thread nearby.
    """
    lines = content.splitlines()
    total = len(lines)

    violations = []
    for idx, line in enumerate(lines):
        if is_comment_or_string_line(line):
            continue
        if not AK_CALL_RE.search(line):
            continue

        # Check a 5-line window around this line (inclusive) for to_thread
        window_start = max(0, idx - 5)
        window_end = min(total, idx + 6)
        window = "\n".join(lines[window_start:window_end])

        if not TO_THREAD_RE.search(window):
            line_no = idx + 1  # 1-based
            violations.append(f"第{line_no}行：{line.rstrip()}")

    if violations:
        details = "\n".join(violations)
        reason = (
            f"❌ AKShare 违规：ak.xxx() 必须用 asyncio.to_thread() 包裹。\n"
            f"违规位置：\n{details}\n"
            f"正确写法：await asyncio.to_thread(_fetch_sync, ...)"
        )
        return True, reason

    return False, ""


def main() -> None:
    try:
        payload = json.load(sys.stdin)
    except Exception:
        _allow()
        return

    tool_name: str = payload.get("toolName") or payload.get("tool_name") or ""
    tool_input: dict = payload.get("toolInput") or payload.get("tool_input") or {}

    # Only care about Write and Edit tools
    if tool_name not in ("Write", "Edit"):
        _allow()
        return

    file_path: str = tool_input.get("file_path") or tool_input.get("path") or ""

    # Normalise separators
    norm = file_path.replace("\\", "/")

    # Only check Python files under backend/
    if "/backend/" not in norm or not norm.endswith(".py"):
        _allow()
        return

    # Extract the content to check
    # Write tool uses "content"; Edit tool uses "new_string"
    content: str = tool_input.get("content") or tool_input.get("new_string") or ""

    if not content:
        _allow()
        return

    violation, reason = check_content(content)
    if violation:
        _block(reason)
    else:
        _allow()


if __name__ == "__main__":
    main()
