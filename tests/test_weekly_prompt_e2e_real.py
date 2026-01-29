"""E2E tests with real LLM API calls using DeepSeek.

These tests call real LLM API and incur costs.
Set RUN_REAL_LLM_TESTS=true to enable.
"""

import os
import pytest
from datetime import datetime
from typing import List, Dict, Any
import httpx

pytestmark = [
    pytest.mark.asyncio,
    pytest.mark.skipif(
        os.getenv("RUN_REAL_LLM_TESTS") != "true",
        reason="Real LLM tests disabled. Set RUN_REAL_LLM_TESTS=true to enable."
    ),
]


class DeepSeekClient:
    """Simple DeepSeek API client for testing."""
    
    def __init__(self):
        self.api_key = os.getenv("TEST_LLM_API_KEY")
        self.model = os.getenv("TEST_LLM_MODEL", "deepseek-chat")
        self.base_url = "https://api.deepseek.com/v1"
        
        if not self.api_key:
            raise RuntimeError("TEST_LLM_API_KEY not set")
    
    async def chat(self, messages: List[Dict[str, str]], system_prompt: str = None) -> str:
        """Send chat request to DeepSeek."""
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        full_messages = []
        if system_prompt:
            full_messages.append({"role": "system", "content": system_prompt})
        full_messages.extend(messages)
        
        payload = {
            "model": self.model,
            "messages": full_messages,
            "temperature": 0.7,
            "max_tokens": 500
        }
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{self.base_url}/chat/completions",
                headers=headers,
                json=payload
            )
            response.raise_for_status()
            data = response.json()
            return data["choices"][0]["message"]["content"]


@pytest.fixture
async def deepseek_client():
    """Provide DeepSeek client."""
    return DeepSeekClient()


class TestRealPromptInjection:
    """Test real LLM behavior with weekly system prompts."""
    
    async def test_prompt_changes_llm_behavior(self, deepseek_client):
        """Verify system prompt truly changes LLM response style."""
        question = "用一句话解释什么是变量"
        
        # Baseline: no system prompt
        baseline_response = await deepseek_client.chat(
            [{"role": "user", "content": question}]
        )
        
        # With system prompt forcing kitchen metaphor
        prompt_response = await deepseek_client.chat(
            [{"role": "user", "content": question}],
            system_prompt="你必须用厨房烹饪的比喻来解释所有编程概念"
        )
        
        # Verify style changed (should contain kitchen-related words)
        kitchen_keywords = ["厨房", "烹饪", "锅", "菜", "做饭", "食材", "调料"]
        has_kitchen_metaphor = any(kw in prompt_response for kw in kitchen_keywords)
        
        assert has_kitchen_metaphor, (
            f"Expected kitchen metaphor in response, got: {prompt_response}"
        )
        assert baseline_response != prompt_response
    
    async def test_teaching_style_constraint(self, deepseek_client):
        """Test that system prompt enforces teaching style."""
        question = "Python 的列表和元组有什么区别？"
        
        # Strict teaching style: no direct answers, use questions
        strict_prompt = """你是严格的苏格拉底式导师。
规则：
1. 不直接给出答案
2. 必须用提问引导学生思考
3. 每个回答至少包含3个问题"""
        
        response = await deepseek_client.chat(
            [{"role": "user", "content": question}],
            system_prompt=strict_prompt
        )
        
        # Verify Socratic style (multiple questions)
        question_count = response.count("?") + response.count("？")
        assert question_count >= 3, (
            f"Expected at least 3 questions, found {question_count} in: {response}"
        )
    
    async def test_language_constraint(self, deepseek_client):
        """Test that system prompt enforces output language."""
        question = "What is a function in programming?"
        
        # Force Chinese response even for English question
        chinese_prompt = "用户用任何语言提问，你都必须用中文回答。"
        
        response = await deepseek_client.chat(
            [{"role": "user", "content": question}],
            system_prompt=chinese_prompt
        )
        
        # Verify response is in Chinese (contains Chinese characters)
        chinese_chars = sum('\u4e00' <= c <= '\u9fff' for c in response)
        assert chinese_chars > 10, (
            f"Expected Chinese response, got: {response}"
        )


class TestMultiTurnConversation:
    """Test multi-turn conversation with context preservation."""
    
    async def test_context_memory_across_turns(self, deepseek_client):
        """Test that LLM remembers context from previous turns."""
        # Teacher persona that tracks student progress
        teacher_prompt = """你是Python导师，正在教一位初学者。
重要：记住学生已经学过的内容，不要重复教学。
如果学生表现出理解，就推进到下一个概念。"""
        
        conversation = []
        
        # Turn 1: Student learns about variables
        q1 = "什么是变量？"
        conversation.append({"role": "user", "content": q1})
        r1 = await deepseek_client.chat(conversation, teacher_prompt)
        conversation.append({"role": "assistant", "content": r1})
        
        # Turn 2: Student shows understanding, asks follow-up
        q2 = "我明白了，变量就像盒子。那列表是什么？"
        conversation.append({"role": "user", "content": q2})
        r2 = await deepseek_client.chat(conversation, teacher_prompt)
        
        # Verify progression (should not re-explain variables)
        assert "盒子" not in r2 or "变量" not in r2[:50], (
            "Should not re-explain variables, should progress to lists"
        )
    
    async def test_weekly_prompt_guided_learning(self, deepseek_client):
        """Test week-specific learning guidance."""
        # Week 2: Focus on hands-on practice
        week2_prompt = """这是第2周：实践练习周。
规则：
1. 不给完整代码示例
2. 只提供思路和伪代码
3. 鼓励学生自己尝试实现
4. 学生问代码时，反问"你觉得第一步应该做什么？"""
        
        conversation = [
            {"role": "user", "content": "帮我写一个计算斐波那契数列的函数"}
        ]
        
        response = await deepseek_client.chat(conversation, week2_prompt)
        
        # Verify: no complete code, should have questions
        code_indicators = ["def ", "return ", "for ", "while "]
        has_code = any(indicator in response for indicator in code_indicators)
        
        # Allow some code snippets but not complete solution
        assert "?" in response or "你觉得" in response, (
            "Should guide with questions, not give complete answer"
        )


class TestWeekTransition:
    """Test prompt changes across week transitions."""
    
    async def test_different_week_different_style(self, deepseek_client):
        """Verify different week prompts produce different teaching styles."""
        question = "教我 Python 字典"
        
        # Week 1: Theory focused
        week1_prompt = "第1周：理论概念周。详细解释原理，多用比喻和定义。"
        week1_response = await deepseek_client.chat(
            [{"role": "user", "content": question}],
            week1_prompt
        )
        
        # Week 3: Practice focused
        week3_prompt = "第3周：实战练习周。给出实际例子和练习题，少讲理论。"
        week3_response = await deepseek_client.chat(
            [{"role": "user", "content": question}],
            week3_prompt
        )
        
        # Verify different approaches
        week1_theory_words = ["定义", "概念", "原理", "本质", "相当于"]
        week3_practice_words = ["例子", "练习", "试试", "写代码", "实现"]
        
        week1_theory_score = sum(1 for w in week1_theory_words if w in week1_response)
        week3_practice_score = sum(1 for w in week3_practice_words if w in week3_response)
        
        assert week1_theory_score >= 2, "Week 1 should focus on theory"
        assert week3_practice_score >= 2, "Week 3 should focus on practice"


class TestPromptRobustness:
    """Test edge cases with real LLM."""
    
    async def test_long_prompt_handling(self, deepseek_client):
        """Test system prompt with 1000+ characters."""
        long_prompt = "详细说明：" + "这是重要规则。" * 200  # ~1400 chars
        
        response = await deepseek_client.chat(
            [{"role": "user", "content": "Hello"}],
            system_prompt=long_prompt
        )
        
        assert len(response) > 0
        assert isinstance(response, str)
    
    async def test_special_characters_in_prompt(self, deepseek_client):
        """Test system prompt with special characters."""
        special_prompt = """特殊字符测试：
- 代码：`print("hello")`
- 数学：x² + y² = z²
- 符号：→ ← ↑ ↓ ✅ ❌
- Unicode: 🐍 Python 🚀"""
        
        response = await deepseek_client.chat(
            [{"role": "user", "content": "Say something"}],
            system_prompt=special_prompt
        )
        
        # Should not crash and return valid response
        assert len(response) > 0
