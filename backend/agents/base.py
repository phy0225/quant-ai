"""LLM 客户端抽象 — 支持任意 OpenAI 兼容接口，Mock 模式无需 API Key"""
from __future__ import annotations
import json, random
from datetime import datetime
from config import settings


def _now_iso():
    return datetime.now().isoformat()


class LLMClient:
    async def complete(self, system: str, user: str) -> str:
        """返回字符串，调用方负责解析"""
        if settings.use_mock:
            return self._mock(system, user)
        return await self._openai_compatible(system, user)

    async def _openai_compatible(self, system: str, user: str) -> str:
        try:
            from openai import AsyncOpenAI
        except ImportError:
            print("[LLM] openai 未安装，降级到 Mock 模式")
            return self._mock(system, user)

        base_url = settings.LLM_API_URL.strip() or None
        try:
            client = AsyncOpenAI(api_key=settings.LLM_API_KEY, base_url=base_url)
            resp = await client.chat.completions.create(
                model=settings.LLM_MODEL,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user",   "content": user},
                ],
                temperature=0.3,
                max_tokens=1024,
            )
            return resp.choices[0].message.content or ""
        except Exception as e:
            print(f"[LLM] API 调用失败: {e}，降级到 Mock")
            return self._mock(system, user)

    def _mock(self, system: str, user: str) -> str:
        """
        Mock 模式：根据 prompt 内容判断是 JSON 格式还是纯文本格式。
        - Agent 的方向判断 prompt 期望 JSON → 返回 JSON 字符串
        - 摘要生成 prompt 不期望 JSON → 返回文字摘要
        """
        # 判断调用方期望什么格式
        expects_json = (
            '"direction"' in system or
            'JSON' in system or
            'json' in system or
            '输出JSON' in system or
            '输出 JSON' in system
        )

        direction  = random.choices(["buy", "sell", "hold"], weights=[0.4, 0.3, 0.3])[0]
        confidence = round(random.uniform(0.55, 0.88), 2)

        if expects_json:
            return json.dumps({
                "direction":  direction,
                "confidence": confidence,
                "reasoning":  f"Mock分析：基于当前市场数据，{direction}信号，置信度{confidence:.0%}。",
            }, ensure_ascii=False)
        else:
            # 纯文字摘要（用于技术/情绪 Agent 的摘要生成）
            templates = {
                "buy":  "当前技术指标显示超卖信号，市场情绪偏低迷，存在反弹机会。",
                "sell": "技术指标进入超买区间，成交量有所萎缩，短线压力较大。",
                "hold": "当前均线系统粘合，趋势方向不明朗，建议观望等待信号明朗。",
            }
            return templates[direction]


llm_client = LLMClient()


class BaseAgent:
    agent_type: str = "base"
    weight: float = 0.2

    def __init__(self):
        self.llm = llm_client

    async def analyze(self, context: dict) -> dict:
        raise NotImplementedError

    def _validate(self, output: dict, retry: int = 0):
        events = []
        d = output.get("direction")
        c = output.get("confidence", 0)
        if d not in ("buy", "sell", "hold", None):
            events.append({"agent_type": self.agent_type, "event_type": "structure_violation",
                "description": f"无效方向值: {d}", "retry_count": retry,
                "resolved": True, "created_at": _now_iso()})
            output["direction"] = "hold"
        if not (0 <= float(c or 0) <= 1):
            events.append({"agent_type": self.agent_type, "event_type": "structure_violation",
                "description": f"置信度超出范围: {c}", "retry_count": retry,
                "resolved": True, "created_at": _now_iso()})
            output["confidence"] = max(0.0, min(1.0, float(c or 0)))
        return output, events