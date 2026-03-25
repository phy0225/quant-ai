#!/usr/bin/env python3
"""
自动化测试 + 自动修复流水线
用法：
  python auto_fix.py                    # 只跑测试，自动修复失败项
  python auto_fix.py --req 需求.md      # 先实现需求，再测试修复
  python auto_fix.py --commit           # 全部通过后 git commit
  python auto_fix.py --test-only        # 只跑测试，不修复，看报告

流程：
  1. 跑测试，收集所有失败
  2. 分析报错，判断是哪类问题
  3. 生成精准的修复 prompt 给 Claude Code
  4. Claude Code 修改代码
  5. 重新跑测试，循环直到通过
"""
import subprocess
import sys
import re
import json
from pathlib import Path
from datetime import datetime


ROOT      = Path(__file__).parent
BACKEND   = ROOT / "backend"
FRONTEND  = ROOT / "frontend"
MAX_RETRY = 5  # 最多重试次数


# ─── 颜色输出 ────────────────────────────────────────────────────────────────

def green(s):  return f"\033[92m{s}\033[0m"
def red(s):    return f"\033[91m{s}\033[0m"
def yellow(s): return f"\033[93m{s}\033[0m"
def cyan(s):   return f"\033[96m{s}\033[0m"
def bold(s):   return f"\033[1m{s}\033[0m"


# ─── 运行命令 ────────────────────────────────────────────────────────────────

def run(cmd: str, cwd: Path = None, timeout: int = 120) -> tuple[int, str, str]:
    try:
        r = subprocess.run(
            cmd, shell=True, cwd=str(cwd or ROOT),
            capture_output=True, text=True,
            encoding="utf-8", errors="replace",  # 非UTF-8字符替换为?，不报错
            timeout=timeout
        )
        # 防御性处理：确保返回值不为 None
        return r.returncode, r.stdout or "", r.stderr or ""
    except subprocess.TimeoutExpired:
        return -1, "", f"命令超时（>{timeout}s）: {cmd}"
    except Exception as e:
        return -1, "", f"命令执行异常: {e}"


# ─── 测试执行 ────────────────────────────────────────────────────────────────

class TestResult:
    def __init__(self, passed: bool, output: str, failures: list[dict]):
        self.passed   = passed
        self.output   = output
        self.failures = failures  # [{name, type, error, file, line}]

    @property
    def fail_count(self): return len(self.failures)
    @property
    def fail_names(self): return [f["name"] for f in self.failures]



def check_test_files_exist() -> list[str]:
    """
    tests/ 디렉토리에 필요한 테스트 파일이 있는지 확인
    없으면 경고 반환
    """
    expected = ["test_api.py", "test_units.py", "test_flows.py", "test_scenarios.py"]
    test_dir = BACKEND / "tests"
    missing = [f for f in expected if not (test_dir / f).exists()]
    return missing

def run_backend_tests(extra_args: str = "") -> TestResult:
    """运行后端 pytest，解析失败详情，包括 collection error"""
    code, out, err = run(
        f"pytest tests/ -v --tb=short --no-header {extra_args}",
        cwd=BACKEND, timeout=180
    )
    output = out + err
    failures = _parse_pytest_failures(output)

    # 检测 collection error（pytest 崩溃但没有 FAILED 行）
    if code != 0 and not failures:
        collection_errors = []
        for line in output.split("\n"):
            if "ERROR" in line and ("collecting" in line or "ImportError" in line
                                    or "ModuleNotFound" in line or "SyntaxError" in line):
                collection_errors.append({
                    "name": "pytest_collection_error",
                    "file": "tests/",
                    "type": "import" if "Import" in line or "Module" in line else "syntax",
                    "error": line.strip(),
                    "detail": output[-2000:],
                })
        if collection_errors:
            failures = collection_errors
            print(f"  {yellow('⚠')} 发现 pytest collection 错误（测试未能运行）")

    return TestResult(code == 0, output, failures)


def run_frontend_check() -> TestResult:
    """运行前端检查：TypeScript 类型检查 + Vite 编译检查（捕获 Vue 模板语法错误）"""
    failures = []
    combined_output = ""

    # 1. TypeScript 类型检查
    code, out, err = run("npx tsc --noEmit", cwd=FRONTEND, timeout=60)
    output = out + err
    combined_output += output
    if code != 0:
        for line in output.split("\n"):
            if ": error TS" in line:
                failures.append({
                    "name": line.strip(),
                    "type": "typescript",
                    "error": line.strip(),
                    "file": line.split("(")[0] if "(" in line else "",
                    "line": "",
                })

    # 2. Vite 编译检查 — 捕获 Vue 模板语法错误（missing end tag 等）
    code2, out2, err2 = run("npx vite build --mode development 2>&1", cwd=FRONTEND, timeout=120)
    output2 = out2 + err2
    combined_output += "\n" + output2
    if code2 != 0:
        # 提取 Vue 模板错误
        for line in output2.split("\n"):
            if any(kw in line for kw in ["Element is missing", "plugin:vite:vue", "error", "Error"]):
                if line.strip() and len(line.strip()) > 5:
                    failures.append({
                        "name": f"vite_build_error",
                        "type": "vue_template",
                        "error": line.strip(),
                        "file": "",
                        "line": "",
                    })
                    break  # 只取第一个错误，避免重复
        if not any(f["type"] == "vue_template" for f in failures):
            failures.append({
                "name": "vite_build_error",
                "type": "vue_template",
                "error": output2[-500:],
                "file": "frontend/",
                "line": "",
            })

    passed = len(failures) == 0
    return TestResult(passed, combined_output, failures)


def _parse_pytest_failures(output: str) -> list[dict]:
    """解析 pytest 输出，提取每个失败测试的详细信息（兼容 Windows 反斜杠路径）"""
    failures = []
    # 找 FAILED 行（Windows 路径用反斜杠，Linux 用正斜杠，都支持）
    failed_lines = [l for l in output.split("\n") if l.startswith("FAILED")]
    # 找每个 FAILED 对应的错误块
    blocks = re.split(r"_{10,}", output)

    for line in failed_lines:
        # 格式: FAILED tests\test_api.py::TestClass::test_name - AssertionError
        # 或:   FAILED tests/test_api.py::TestClass::test_name - AssertionError
        m = re.match(r"FAILED ([\w/\\.\-]+)::([\w:]+) - (.+)", line)
        if not m:
            # 最后兜底：只要有 :: 就提取
            parts = line[7:].split(" - ", 1)
            if "::" in parts[0]:
                file_and_path = parts[0].strip()
                error_summary = parts[1].strip() if len(parts) > 1 else "unknown error"
                test_path = file_and_path.split("::", 1)[1]
                file_path = file_and_path.split("::")[0]
            else:
                continue
        else:
            file_path, test_path, error_summary = m.groups()

        # 在 blocks 里找对应的详细错误
        detail = ""
        for block in blocks:
            if test_path.split("::")[-1] in block:
                detail = block.strip()
                break

        # 提取错误类型
        error_type = "unknown"
        if "AssertionError" in error_summary or "assert" in detail.lower():
            error_type = "assertion"
        elif "AttributeError" in error_summary:
            error_type = "attribute"
        elif "ImportError" in error_summary or "ModuleNotFound" in error_summary:
            error_type = "import"
        elif "TypeError" in error_summary:
            error_type = "type"
        elif "HTTPException" in detail or "status_code" in detail:
            error_type = "http_status"
        elif "KeyError" in error_summary:
            error_type = "key"

        failures.append({
            "name":     test_path,
            "file":     file_path,
            "type":     error_type,
            "error":    error_summary,
            "detail":   detail[:1500],  # 限制长度
        })

    return failures


# ─── 问题分类 ────────────────────────────────────────────────────────────────

def classify_failures(failures: list[dict]) -> dict[str, list[dict]]:
    """
    把失败按根本原因分组，同根因的一起修
    避免每次只修一个测试，下次又报同样的错
    """
    groups: dict[str, list] = {}

    for f in failures:
        # 推断根本原因
        if f["type"] == "import":
            key = "import_error"
        elif f["type"] == "http_status" and "404" in f.get("detail", ""):
            key = "route_missing"
        elif f["type"] == "http_status" and "422" in f.get("detail", ""):
            key = "validation_error"
        elif f["type"] == "http_status" and "409" in f.get("detail", ""):
            key = "business_logic"
        elif f["type"] == "assertion":
            # 按测试文件分组
            key = f"assertion_{f['file'].replace('/', '_')}"
        elif f["type"] == "attribute":
            key = "attribute_error"
        elif f["type"] == "type":
            key = "type_error"
        else:
            key = f"other_{f['type']}"

        groups.setdefault(key, []).append(f)

    return groups


# ─── 生成修复 Prompt ─────────────────────────────────────────────────────────

def build_fix_prompt(group_name: str, failures: list[dict], attempt: int) -> str:
    """
    为一组同类错误生成精准的修复 prompt
    包含：失败测试名、完整报错、相关文件路径、修复约束
    """
    fail_names = "\n".join(f"  - {f['name']}" for f in failures)
    errors = "\n\n".join(
        f"【{f['name']}】\n错误类型: {f['type']}\n错误信息: {f['error']}\n详细:\n{f['detail']}"
        for f in failures
    )

    # 按错误类型给出针对性指导
    hints = {
        "import_error": "检查 import 语句，确认模块路径是否正确，是否有循环导入",
        "route_missing": "检查 router/index.ts 是否注册了对应路由，检查后端 router prefix 是否正确",
        "validation_error": "检查 Pydantic schema 定义，检查接口参数是否与测试期望一致",
        "business_logic": "检查业务逻辑，如防重复操作的 status 检查，审批状态机流转是否正确",
        "type_error": "检查类型，尤其是 dict/float 混用的持仓数据格式，使用 isinstance 兼容处理",
        "attribute_error": "检查对象属性是否存在，可能是 model 字段未定义或 None 未处理",
    }.get(group_name.split("_")[0], "分析根本原因，修改相关代码")

    prompt = f"""
以下 {len(failures)} 个测试失败（第 {attempt} 次尝试修复），错误类型分组: [{group_name}]

失败的测试：
{fail_names}

完整报错信息：
{errors}

修复指导：
- {hints}
- 优先修改业务代码（routers/、agents/、services/），而不是修改测试
- 如果是接口返回值格式问题，对齐 schemas.py 里的定义
- 修改后确保不影响其他已通过的测试
- 遵守 CLAUDE.md 中的代码规范

请直接修改相关文件，不要解释，修改完立即可以重新运行测试。
""".strip()

    return prompt


# ─── 调用 Claude Code ────────────────────────────────────────────────────────

def call_claude_code(prompt: str) -> bool:
    """
    调用 Claude Code 执行修复
    返回 True=调用成功，False=claude 未安装或调用失败

    Windows 注意：不用 stdin 传 prompt（会卡死），改用文件重定向
    """
    prompt_file = ROOT / ".fix_prompt.txt"
    prompt_file.write_text(prompt, encoding="utf-8")

    print(f"\n  {cyan('→')} 调用 Claude Code 修复...", flush=True)

    try:
        # 检查 claude 是否安装
        check = subprocess.run("claude --version", shell=True,
                               capture_output=True, text=True, timeout=10)
        if check.returncode != 0:
            raise FileNotFoundError("claude not found")
    except (FileNotFoundError, subprocess.TimeoutExpired):
        prompt_file.unlink(missing_ok=True)
        print(f"  {red('✗')} claude 命令未找到，请先安装: npm install -g @anthropic-ai/claude-code")
        return False

    try:
        # 用文件重定向代替 stdin（Windows 兼容）
        if sys.platform == "win32":
            cmd = f'claude --dangerously-skip-permissions --print < "{prompt_file}"' 
        else:
            cmd = f'claude --dangerously-skip-permissions --print < "{prompt_file}"' 

        result = subprocess.run(
            cmd,
            shell=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
            cwd=str(ROOT),
            timeout=600,
        )
        prompt_file.unlink(missing_ok=True)

        if result.returncode == 0:
            print(f"  {green('✓')} Claude Code 执行完成")
            # 打印 Claude 的输出摘要（前 300 字）
            if result.stdout.strip():
                preview = result.stdout.strip()[:300]
                for line in preview.split("\n")[:5]:
                    print(f"  {line}")
            return True
        else:
            print(f"  {yellow('⚠')} Claude Code 返回非零: {result.stderr[:300]}")
            # 非零退出不一定是失败（claude 可能改了文件但退出码不为0）
            return True  # 乐观继续，让测试判断是否真的修好了

    except subprocess.TimeoutExpired:
        prompt_file.unlink(missing_ok=True)
        print(f"  {yellow('⚠')} Claude Code 超时（>10分钟），继续运行测试")
        return True  # 超时也可能已经改了部分文件
    except Exception as e:
        prompt_file.unlink(missing_ok=True)
        print(f"  {red('✗')} 调用异常: {e}")
        return False


# ─── 报告生成 ────────────────────────────────────────────────────────────────

def save_report(attempt: int, backend_result: TestResult, ts_result: TestResult):
    """保存测试报告到文件，方便后续查看"""
    report_dir = ROOT / ".test_reports"
    report_dir.mkdir(exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_path = report_dir / f"report_{ts}_attempt{attempt}.txt"

    lines = [
        f"测试报告 — 第 {attempt} 次尝试",
        f"时间: {datetime.now().isoformat()}",
        "=" * 60,
        f"后端测试: {'通过' if backend_result.passed else f'失败 ({backend_result.fail_count} 个)'}",
        f"前端类型检查: {'通过' if ts_result.passed else f'失败 ({ts_result.fail_count} 个)'}",
    ]

    if backend_result.failures:
        lines += ["\n失败的后端测试:"]
        for f in backend_result.failures:
            lines.append(f"  [{f['type']}] {f['name']}: {f['error']}")

    if ts_result.failures:
        lines += ["\n失败的前端检查:"]
        for f in ts_result.failures:
            lines.append(f"  {f['error']}")

    lines += ["\n完整输出:", "=" * 60, backend_result.output]

    report_path.write_text("\n".join(lines), encoding="utf-8")
    return report_path


# ─── Git 操作 ────────────────────────────────────────────────────────────────

def git_commit(message: str) -> bool:
    code, _, err = run("git add -A")
    if code != 0:
        print(red(f"  git add 失败: {err}"))
        return False
    code, out, err = run(f'git commit -m "{message}"')
    if code != 0:
        if "nothing to commit" in (out + err):
            print(yellow("  没有变更需要提交"))
            return True
        print(red(f"  git commit 失败: {err}"))
        return False
    print(green(f"  ✓ 已提交: {message}"))
    return True


# ─── 主流程 ─────────────────────────────────────────────────────────────────

def _split_requirements(content: str) -> list[tuple[str, str]]:
    """
    把需求文档按 ## 需求N 切分成独立任务
    返回 [(标题, 内容), ...] 列表
    如果找不到分隔符，整体作为一个任务返回
    """
    import re
    # 匹配 ## 需求一/二/三/四 或 ## 需求 1/2/3/4 等
    pattern = r'(##\s+需求[一二三四五六七八九十\d]+[^\n]*)'
    parts = re.split(pattern, content)

    if len(parts) <= 1:
        # 没有分隔符，整体返回
        return [("完整需求", content)]

    tasks = []
    # parts 格式: [前言, 标题1, 内容1, 标题2, 内容2, ...]
    preamble = parts[0].strip()
    i = 1
    while i < len(parts) - 1:
        title   = parts[i].strip()
        body    = parts[i + 1].strip()
        # 把前言（背景说明）拼到每个任务里，提供上下文
        context = f"{preamble}\n\n{title}\n{body}" if preamble else f"{title}\n{body}"
        tasks.append((title, context))
        i += 2

    return tasks


def implement_requirements(req_file: Path):
    """
    全自动实现需求：把需求文档拆成小任务逐个调用 claude --print
    每个任务独立、改动小，不会触发超时
    """
    print(bold(f"\n{'='*60}"))
    print(bold("步骤 0：实现需求文档"))
    print(bold(f"{'='*60}"))

    content = req_file.read_text(encoding="utf-8")
    tasks = _split_requirements(content)

    print(f"  需求文档已拆分为 {len(tasks)} 个子任务")

    for idx, (title, task_content) in enumerate(tasks, 1):
        print(f"\n  {cyan(f'[{idx}/{len(tasks)}]')} {title}")

        prompt = f"""请实现以下需求，严格遵守 CLAUDE.md 中的代码规范：

{task_content}

实现要求：
- 只实现上述需求，不改动其他无关代码
- 新增后端接口必须在 schemas.py 定义对应 Pydantic 模型
- 新增前端页面必须在 router/index.ts 注册路由
- AKShare 调用必须用 asyncio.to_thread 包裹
- 完成后不需要运行测试"""

        success = call_claude_code(prompt)
        if not success:
            print(f"  {red('✗')} 子任务 {idx} 调用失败，跳过继续")
            continue

        # 每实现一个子任务，快速跑一次测试看是否引入语法错误
        print(f"  {cyan('→')} 快速语法检查...")
        code, out, err = run("python -m py_compile backend/agents/pipeline.py backend/main.py", cwd=ROOT, timeout=10)
        if code != 0:
            print(f"  {yellow('⚠')} 检测到语法错误，让 Claude 修复...")
            fix_prompt = f"刚才实现的代码有语法错误，请修复：\n{(out+err)[:500]}"
            call_claude_code(fix_prompt)

    print(f"\n  {green('✓')} 所有子任务实现完毕")


def auto_fix_loop(
    req_file: Path = None,
    do_commit: bool = False,
    test_only: bool = False,
):
    print(bold(f"\n{'='*60}"))
    print(bold(" Quant AI — 自动化测试 & 修复流水线"))
    print(bold(f"{'='*60}"))
    print(f"  最大重试次数: {MAX_RETRY}")
    print(f"  测试目录: {BACKEND / 'tests'}")

    # 0. 先实现需求（如果有）
    if req_file:
        implement_requirements(req_file)

    # 0.5 检查测试文件是否齐全
    missing_files = check_test_files_exist()
    if missing_files:
        print(yellow(f"\n  ⚠ 以下测试文件不存在，相关测试不会运行："))
        for f in missing_files:
            print(yellow(f"    - backend/tests/{f}"))
        print(yellow(f"\n  提示：将对应文件放入 backend/tests/ 后重新运行"))
        print()

    # 1. 记录起始状态
    print(bold(f"\n{'='*60}"))
    print(bold("步骤 1：初始测试状态"))
    print(bold(f"{'='*60}"))

    backend = run_backend_tests()
    frontend = run_frontend_check()

    # 额外检查：passed=False 但 failures 为空，说明解析失败，打印原始输出
    if not backend.passed and not backend.failures:
        print(yellow("\n  ⚠ 后端测试失败但未能解析具体错误，输出末尾："))
        for line in backend.output.split("\n")[-20:]:
            if line.strip():
                print(f"    {line}")
        # 把整个输出当成一个失败
        backend.failures.append({
            "name": "unknown_failures",
            "file": "tests/",
            "type": "assertion",
            "error": "pytest 报告有失败但解析失败，请查看上方输出",
            "detail": backend.output[-3000:],
        })

    if backend.passed and frontend.passed:
        print(green("\n✅ 所有测试已通过，无需修复"))
        if do_commit:
            git_commit("test: all tests passing")
        return True

    print(f"\n后端: {red(f'{backend.fail_count} 个失败') if not backend.passed else green('通过')}")
    print(f"前端: {red(f'{frontend.fail_count} 个失败') if not frontend.passed else green('通过')}")

    if test_only:
        # 只看报告，不修复
        print(bold("\n测试失败详情:"))
        for f in backend.failures:
            print(f"  {red('✗')} [{f['type']}] {f['name']}")
            print(f"      {f['error']}")
        for f in frontend.failures:
            print(f"  {red('✗')} [ts] {f['name']}")
        return False

    # 2. 修复循环
    history: list[dict] = []  # 记录每次修复历史，避免反复犯同样错误

    for attempt in range(1, MAX_RETRY + 1):
        print(bold(f"\n{'='*60}"))
        print(bold(f"步骤 2.{attempt}：自动修复（第 {attempt}/{MAX_RETRY} 次）"))
        print(bold(f"{'='*60}"))

        all_failures = backend.failures + frontend.failures
        if not all_failures:
            break

        # 按根本原因分组
        groups = classify_failures(all_failures)
        print(f"\n  失败分组: {list(groups.keys())}")

        # 构建修复 prompt，包含历史上下文防止反复错误
        history_ctx = ""
        if history:
            history_ctx = "\n\n历史修复记录（请避免重复同样的错误）:\n" + "\n".join(
                f"第{h['attempt']}次修复了 {h['group']}，结果: {h['result']}"
                for h in history[-3:]  # 只取最近3次
            )

        # 优先修最严重的：import error > type error > assertion
        priority_order = ["import_error", "type_error", "attribute_error",
                          "route_missing", "validation_error", "business_logic"]
        sorted_groups = sorted(
            groups.items(),
            key=lambda x: next((i for i, p in enumerate(priority_order) if x[0].startswith(p)), 99)
        )

        fix_applied = False
        for group_name, group_failures in sorted_groups[:2]:  # 每次最多修2组，避免改太多
            print(f"\n  {cyan(f'修复: [{group_name}]')} ({len(group_failures)} 个失败)")
            prompt = build_fix_prompt(group_name, group_failures, attempt) + history_ctx
            success = call_claude_code(prompt)
            if success:
                fix_applied = True
                history.append({
                    "attempt": attempt,
                    "group": group_name,
                    "failures": [f["name"] for f in group_failures],
                    "result": "已提交修复"
                })

        if not fix_applied:
            print(red("\n  Claude Code 不可用，退出修复循环"))
            print(yellow("  提示：手动安装 claude code 后重新运行"))
            break

        # 重新跑测试
        print(f"\n  {cyan('→')} 重新运行测试...")
        backend = run_backend_tests()
        frontend = run_frontend_check()

        report_path = save_report(attempt, backend, frontend)
        print(f"  报告已保存: {report_path.name}")

        still_failing = backend.fail_count + frontend.fail_count
        prev_failing  = len(all_failures)

        if backend.passed and frontend.passed:
            print(green(f"\n✅ 第 {attempt} 次修复后全部通过！"))
            break
        elif still_failing < prev_failing:
            print(yellow(f"\n  进展: {prev_failing} → {still_failing} 个失败，继续修复..."))
            # 更新历史记录
            history[-1]["result"] = f"从{prev_failing}减少到{still_failing}个失败"
        else:
            print(red(f"\n  第 {attempt} 次修复后失败数未减少 ({still_failing} 个)"))
            if attempt >= 3:
                print(yellow("  提示：考虑手动介入，查看 .test_reports/ 目录下的报告"))

    # 3. 最终结果
    print(bold(f"\n{'='*60}"))
    print(bold("最终结果"))
    print(bold(f"{'='*60}"))

    if backend.passed and frontend.passed:
        print(green("\n✅ 所有测试通过"))
        if do_commit:
            msg = f"fix: auto-fix {datetime.now().strftime('%Y%m%d_%H%M')}"
            if req_file:
                msg = f"feat: {req_file.stem}"
            git_commit(msg)
        return True
    else:
        print(red(f"\n❌ 仍有 {backend.fail_count + frontend.fail_count} 个测试失败"))
        print(yellow("\n剩余失败："))
        for f in backend.failures + frontend.failures:
            print(f"  {red('✗')} {f['name']}: {f['error'][:80]}")
        print(yellow(f"\n查看详细报告: {ROOT / '.test_reports'}"))
        print(yellow("如需手动修复，运行: pytest tests/ -v --tb=long"))
        return False


# ─── 入口 ────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    req_file  = None
    do_commit = "--commit"    in sys.argv
    test_only = "--test-only" in sys.argv

    # 解析 --req 参数
    if "--req" in sys.argv:
        idx = sys.argv.index("--req")
        if idx + 1 < len(sys.argv):
            req_file = Path(sys.argv[idx + 1])
            if not req_file.exists():
                print(red(f"需求文件不存在: {req_file}"))
                sys.exit(1)

    success = auto_fix_loop(
        req_file=req_file,
        do_commit=do_commit,
        test_only=test_only,
    )
    sys.exit(0 if success else 1)