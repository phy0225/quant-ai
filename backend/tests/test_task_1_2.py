"""
Task 1.2 RED phase — 验证 AnalyzePage.vue 已迁移到 analysisStore

运行：
  pytest tests/test_task_1_2.py -v
"""
import re
from pathlib import Path

PAGE_PATH = Path(__file__).resolve().parents[2] / "frontend" / "src" / "pages" / "AnalyzePage.vue"


def _read() -> str:
    assert PAGE_PATH.exists(), f"文件不存在: {PAGE_PATH}"
    return PAGE_PATH.read_text(encoding="utf-8")


class TestTask12AnalyzePage:
    """Task 1.2: AnalyzePage.vue 接入 analysisStore，支持离页恢复和刷新恢复"""

    def test_imports_use_analysis_store(self):
        content = _read()
        assert "useAnalysisStore" in content, \
            "必须从 @/store/analysis 导入 useAnalysisStore"

    def test_imports_store_to_refs(self):
        content = _read()
        assert "storeToRefs" in content, \
            "必须从 pinia 导入 storeToRefs"

    def test_imports_from_store_analysis(self):
        content = _read()
        assert re.search(r"from\s+['\"]@/store/analysis['\"]", content), \
            "必须 import { useAnalysisStore } from '@/store/analysis'"

    def test_current_run_from_store_refs(self):
        """currentRun 必须通过 storeToRefs 解构自 store，而非本地 ref()"""
        content = _read()
        # 不应再有 const currentRun = ref(...)
        assert not re.search(r"const\s+currentRun\s*=\s*ref\s*[(<]", content), \
            "currentRun 不应是本地 ref，应通过 storeToRefs(store) 解构"
        # 应通过 storeToRefs 解构
        assert re.search(r"storeToRefs\s*\(\s*store\s*\)", content), \
            "必须使用 storeToRefs(store) 解构 currentRun / isPolling"

    def test_is_polling_from_store_refs(self):
        """isPolling 必须通过 storeToRefs 解构自 store，而非本地 ref()"""
        content = _read()
        assert not re.search(r"const\s+isPolling\s*=\s*ref\s*\(", content), \
            "isPolling 不应是本地 ref，应通过 storeToRefs(store) 解构"

    def test_on_unmounted_calls_clear_timer_not_stop_polling(self):
        """onUnmounted 应注册 clearTimer（只清计时器），不再注册 stopPolling"""
        content = _read()
        assert re.search(r"onUnmounted\s*\(\s*clearTimer\s*\)", content), \
            "onUnmounted 必须注册 clearTimer，而非 stopPolling"
        assert not re.search(r"onUnmounted\s*\(\s*stopPolling\s*\)", content), \
            "onUnmounted 不应注册 stopPolling（会清空 store 状态，破坏恢复能力）"

    def test_on_mounted_restores_from_active_run_id(self):
        """onMounted 若检测到 store.activeRunId 则恢复轮询"""
        content = _read()
        assert "store.activeRunId" in content, \
            "onMounted 必须检查 store.activeRunId 以恢复未完成任务"

    def test_handle_trigger_calls_store_set_active_run(self):
        """handleTrigger 成功后必须调用 store.setActiveRun(run)"""
        content = _read()
        assert "store.setActiveRun" in content, \
            "handleTrigger 成功后必须调用 store.setActiveRun(run)"

    def test_stop_polling_calls_store_clear_active_run(self):
        """stopPolling/完成轮询时必须调用 store.clearActiveRun()"""
        content = _read()
        assert "store.clearActiveRun" in content, \
            "轮询结束时必须调用 store.clearActiveRun()"

    def test_has_clear_timer_function(self):
        """必须有 clearTimer 函数（仅清计时器，不动 store）"""
        content = _read()
        assert re.search(r"function\s+clearTimer\s*\(", content), \
            "必须定义 clearTimer() 函数（仅清计时器，store 状态保留）"

    def test_stop_polling_calls_clear_timer(self):
        """stopPolling 内部应调用 clearTimer() 而非直接操作计时器"""
        content = _read()
        # stopPolling 应存在且调用 clearTimer
        assert re.search(r"function\s+stopPolling\s*\(", content), \
            "必须定义 stopPolling() 函数"
        # Find stopPolling body and check it calls clearTimer
        match = re.search(
            r"function\s+stopPolling\s*\(\s*\)\s*\{([^}]+)\}", content, re.DOTALL
        )
        assert match, "stopPolling 函数体无法解析"
        body = match.group(1)
        assert "clearTimer" in body, \
            "stopPolling() 内部必须调用 clearTimer()"
        assert "store.clearActiveRun" in body, \
            "stopPolling() 内部必须调用 store.clearActiveRun()"
