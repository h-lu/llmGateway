"""E2E测试共享配置和fixtures."""
import pytest
import pytest_asyncio
from typing import AsyncGenerator
from httpx import AsyncClient

e2e = pytest.mark.e2e
api_test = pytest.mark.api_test
browser_test = pytest.mark.browser_test
llm_test = pytest.mark.llm_test


@pytest_asyncio.fixture
async def http_client() -> AsyncGenerator[AsyncClient, None]:
    """提供HTTP异步客户端."""
    async with AsyncClient(base_url="http://localhost:8000", timeout=30.0) as client:
        yield client


@pytest.fixture
def test_student_credentials():
    """测试学生API凭证."""
    return {
        "api_key": "tp-test-student-key-for-e2e",
        "student_id": "test_student_001",
    }


@pytest.fixture
def seed_prompts():
    """返回测试用的每周提示词配置."""
    return {
        1: {
            "week_start": 1,
            "week_end": 1,
            "description": "第1周：理论基础周",
            "system_prompt": """你是Python编程导师，这是第1周学习。
规则：
1. 重点解释编程概念和原理
2. 使用生活化的比喻帮助理解
3. 详细解释"为什么"要这样做
4. 给出完整的概念定义

示例风格："变量就像一个盒子，你可以把数据放进去...""",
            "is_active": True,
        },
        2: {
            "week_start": 2,
            "week_end": 2,
            "description": "第2周：苏格拉底式提问周",
            "system_prompt": """你是Python编程导师，这是第2周学习。
规则：
1. 不直接给出答案
2. 必须用提问引导学生思考
3. 每个回答至少包含2-3个问题
4. 鼓励学生自己发现答案

示例风格："这是个好问题。在你写代码之前，你觉得第一步应该做什么？如果变量不存在会发生什么？""",
            "is_active": True,
        },
        3: {
            "week_start": 3,
            "week_end": 3,
            "description": "第3周：实践练习周",
            "system_prompt": """你是Python编程导师，这是第3周学习。
规则：
1. 提供可运行的代码示例
2. 给出具体的练习题
3. 鼓励学生动手尝试
4. 代码注释要详细

示例风格："这是一个例子：```python\nx = 5\nprint(x)\n``` 现在你自己试试...""",
            "is_active": True,
        },
        4: {
            "week_start": 4,
            "week_end": 4,
            "description": "第4周：项目实战周",
            "system_prompt": """你是Python编程导师，这是第4周学习。
规则：
1. 围绕一个完整项目展开
2. 将大问题分解成小步骤
3. 每个步骤都有明确目标
4. 引导学生完成整个项目

示例风格："我们来做一个计算器。第一步，先实现加法功能...""",
            "is_active": True,
        },
    }
