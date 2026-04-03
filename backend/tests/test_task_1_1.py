"""
Task 1.1 RED phase — 验证 frontend/src/store/analysis.ts 存在且包含规范接口

运行：
  pytest tests/test_task_1_1.py -v
"""
import re
from pathlib import Path

STORE_PATH = Path(__file__).resolve().parents[2] / "frontend" / "src" / "store" / "analysis.ts"


def _read() -> str:
    assert STORE_PATH.exists(), (
        f"文件不存在: {STORE_PATH}\n"
        "请先创建 frontend/src/store/analysis.ts"
    )
    return STORE_PATH.read_text(encoding="utf-8")


class TestTask11AnalysisStore:
    """Task 1.1: 新增 Pinia store — analysis.ts 必须存在且暴露规定接口"""

    def test_file_exists(self):
        assert STORE_PATH.exists(), f"文件不存在: {STORE_PATH}"

    def test_exports_use_analysis_store(self):
        content = _read()
        assert "useAnalysisStore" in content, "必须导出 useAnalysisStore"

    def test_uses_define_store(self):
        content = _read()
        assert "defineStore" in content, "必须使用 Pinia defineStore"

    def test_store_name_is_analysis(self):
        content = _read()
        assert re.search(r"defineStore\(['\"]analysis['\"]", content), \
            "store name 必须为 'analysis'"

    def test_has_active_run_id(self):
        content = _read()
        assert "activeRunId" in content, "必须有 activeRunId state"

    def test_active_run_id_reads_session_storage(self):
        content = _read()
        assert "sessionStorage.getItem('activeRunId')" in content, \
            "activeRunId 初始值必须从 sessionStorage.getItem('activeRunId') 读取"

    def test_has_current_run(self):
        content = _read()
        assert "currentRun" in content, "必须有 currentRun state"

    def test_has_is_polling(self):
        content = _read()
        assert "isPolling" in content, "必须有 isPolling state"

    def test_has_is_running_computed(self):
        content = _read()
        assert "isRunning" in content, "必须有 isRunning computed"

    def test_has_set_active_run(self):
        content = _read()
        assert "setActiveRun" in content, "必须有 setActiveRun 方法"

    def test_set_active_run_writes_session_storage(self):
        content = _read()
        assert "sessionStorage.setItem('activeRunId'" in content, \
            "setActiveRun 必须调用 sessionStorage.setItem('activeRunId', ...)"

    def test_has_clear_active_run(self):
        content = _read()
        assert "clearActiveRun" in content, "必须有 clearActiveRun 方法"

    def test_clear_active_run_removes_session_storage(self):
        content = _read()
        assert "sessionStorage.removeItem('activeRunId')" in content, \
            "clearActiveRun 必须调用 sessionStorage.removeItem('activeRunId')"

    def test_imports_decision_run_type(self):
        content = _read()
        assert "DecisionRun" in content, "必须从 @/types/decision 导入 DecisionRun 类型"
