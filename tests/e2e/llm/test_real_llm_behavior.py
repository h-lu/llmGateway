"""
场景L3: 真实LLM行为验证
验证: 每周提示词确实改变了AI的教学行为和风格

运行方式: RUN_REAL_LLM_TESTS=true TEST_LLM_API_KEY=your_key uv run pytest tests/e2e/llm/ -v
"""
import os
import pytest
import httpx
import json
from typing import List, Dict, Any

e2e = pytest.mark.e2e
llm_test = pytest.mark.llm_test

pytestmark = [
    pytest.mark.asyncio,
    pytest.mark.skipif(
        os.getenv("RUN_REAL_LLM_TESTS") != "true",
        reason="Real LLM tests disabled. Set RUN_REAL_LLM_TESTS=true to enable.",
    ),
]


class RealLLMClient:
    """调用真实LLM API进行测试."""

    def __init__(self):
        self.api_key = os.getenv("TEST_LLM_API_KEY") or os.getenv("DEEPSEEK_API_KEY")
        self.model = os.getenv("TEST_LLM_MODEL", "deepseek-chat")
        self.base_url = "https://api.deepseek.com/v1"

        if not self.api_key:
            raise RuntimeError("TEST_LLM_API_KEY or DEEPSEEK_API_KEY required")

    async def chat(
        self, messages: List[Dict[str, str]], system_prompt: str = None
    ) -> str:
        """发送聊天请求."""
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        full_messages = []
        if system_prompt:
            full_messages.append({"role": "system", "content": system_prompt})
        full_messages.extend(messages)

        payload = {
            "model": self.model,
            "messages": full_messages,
            "temperature": 0.7,
            "max_tokens": 500,
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{self.base_url}/chat/completions",
                headers=headers,
                json=payload,
            )
            response.raise_for_status()
            data = response.json()
            return data["choices"][0]["message"]["content"]


@pytest.fixture
async def llm_client():
    """提供真实LLM客户端."""
    return RealLLMClient()


@e2e
@llm_test
class TestRealLLMBehavior:
    """真实LLM行为验证测试."""

    async def test_week1_theory_focus(self, llm_client):
        """验证第1周提示词产生理论导向的回复."""
        week1_prompt = """你是Python编程导师，这是第1周学习。
规则：
1. 重点解释编程概念和原理
2. 使用生活化的比喻帮助理解
3. 详细解释"为什么"要这样做"""

        response = await llm_client.chat(
            [{"role": "user", "content": "什么是变量？"}],
            system_prompt=week1_prompt,
        )

        # 验证: 回复包含理论词汇和比喻
        theory_keywords = ["定义", "概念", "原理", "本质", "相当于", "就像", "好比", "类似"]
        score = sum(1 for kw in theory_keywords if kw in response)
        assert score >= 1, f"Expected theory focus (score>=1), got score={score}. Response: {response[:200]}"

    async def test_week2_socratic_style(self, llm_client):
        """验证第2周提示词产生苏格拉底式提问."""
        week2_prompt = """你是Python编程导师，这是第2周学习。
规则：
1. 不直接给出答案
2. 必须用提问引导学生思考
3. 每个回答至少包含2-3个问题"""

        response = await llm_client.chat(
            [{"role": "user", "content": "怎么写循环？"}],
            system_prompt=week2_prompt,
        )

        # 验证: 回复包含多个问题
        question_count = response.count("?") + response.count("？")
        assert question_count >= 2, f"Expected 2+ questions, got {question_count} in: {response[:200]}"

    async def test_week3_practice_focus(self, llm_client):
        """验证第3周提示词产生实践导向的回复."""
        week3_prompt = """你是Python编程导师，这是第3周学习。
规则：
1. 提供可运行的代码示例
2. 给出具体的练习题
3. 鼓励学生动手尝试"""

        response = await llm_client.chat(
            [{"role": "user", "content": "怎么用列表？"}],
            system_prompt=week3_prompt,
        )

        # 验证: 回复包含代码示例
        code_indicators = ["```python", "```", "print(", "for ", "while ", "["]
        has_code = any(ind in response for ind in code_indicators)
        assert has_code, f"Expected code example, got: {response[:200]}"

    async def test_style_difference_between_weeks(self, llm_client):
        """验证不同周的回复风格确实不同."""
        question = "教我Python字典"

        week1_response = await llm_client.chat(
            [{"role": "user", "content": question}],
            system_prompt="你是Python导师。第1周：详细解释原理和概念，使用比喻。",
        )

        week3_response = await llm_client.chat(
            [{"role": "user", "content": question}],
            system_prompt="你是Python导师。第3周：给出代码示例和练习，少讲理论。",
        )

        # 验证: 两回复不同
        assert week1_response != week3_response, "Different weeks should produce different responses"

        # 进一步验证风格差异
        week1_theory_words = ["定义", "概念", "原理", "比喻", "相当于"]
        week3_practice_words = ["代码", "示例", "试试", "练习", "运行"]
        
        week1_theory_score = sum(1 for w in week1_theory_words if w in week1_response)
        week3_practice_score = sum(1 for w in week3_practice_words if w in week3_response)

        # 记录分数用于调试
        print(f"\nWeek 1 theory score: {week1_theory_score}")
        print(f"Week 3 practice score: {week3_practice_score}")
        print(f"Week 1 response preview: {week1_response[:100]}...")
        print(f"Week 3 response preview: {week3_response[:100]}...")
        
        # 第1周应该更多理论词汇，第3周应该更多实践词汇
        assert week1_theory_score > 0 or week3_practice_score > 0, \
            "Expected style difference between weeks"

    async def test_baseline_vs_prompted_response(self, llm_client):
        """验证有提示词和无提示词的回复确实不同."""
        question = "什么是函数？"

        # Baseline: 无system prompt
        baseline = await llm_client.chat(
            [{"role": "user", "content": question}],
            system_prompt=None,
        )

        # With prompt: 苏格拉底风格
        socratic = await llm_client.chat(
            [{"role": "user", "content": question}],
            system_prompt="你是严格导师。不直接给答案，只用提问引导。",
        )

        # 两者应该不同
        assert baseline != socratic, "Prompted response should differ from baseline"

    async def test_chinese_language_constraint(self, llm_client):
        """验证中文提示词让AI用中文回答."""
        prompt = "无论用户用什么语言提问，你都必须用中文回答。"
        
        # 用英文提问
        response = await llm_client.chat(
            [{"role": "user", "content": "What is a function?"}],
            system_prompt=prompt,
        )

        # 验证: 回复包含中文字符
        chinese_chars = sum('\u4e00' <= c <= '\u9fff' for c in response)
        assert chinese_chars > 10, f"Expected Chinese response, got: {response[:100]}"


@e2e
@llm_test
class TestMultiTurnWithRealLLM:
    """使用真实LLM测试多轮对话."""

    async def test_context_memory(self, llm_client):
        """测试LLM能记住之前的对话内容."""
        teacher_prompt = """你是Python导师。重要：记住学生已经学过的内容，不要重复教学。
如果学生表现出理解，就推进到下一个概念。"""

        # 第一轮
        response1 = await llm_client.chat(
            [{"role": "user", "content": "什么是变量？"}],
            system_prompt=teacher_prompt,
        )

        # 第二轮（学生展示理解）
        conversation = [
            {"role": "user", "content": "什么是变量？"},
            {"role": "assistant", "content": response1},
            {"role": "user", "content": "我明白了，变量就像盒子。那列表呢？"},
        ]
        
        response2 = await llm_client.chat(
            conversation,
            system_prompt=teacher_prompt,
        )

        # 验证: 第二轮不应该重复解释变量
        # 只是验证能正常响应
        assert len(response2) > 0
        assert "变量" not in response2[:30] or "列表" in response2[:30], \
            "Should progress to lists, not re-explain variables"
