#!/usr/bin/env python3
"""
多轮连续对话测试脚本

测试目标：验证 AI 在多轮对话中是否能保持导师角色，并基于上下文提供连贯的指导

测试设计：
- 5 个学生，每人 1 个对话线程
- 每个线程 10 轮连续问答（保持上下文）
- 模拟真实学习场景：从问题 → 引导 → 追问 → 深化理解
"""

import asyncio
import os
import sys
import uuid
from datetime import datetime
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import httpx
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from gateway.app.core.config import settings
from gateway.app.core.security import hash_api_key
from gateway.app.db.models import Student, Conversation, WeeklySystemPrompt

load_dotenv(project_root / ".env")

DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")
DEEPSEEK_API_URL = "https://api.deepseek.com/chat/completions"
MODEL = "deepseek-chat"

# ============ 严格的导师模式系统提示词 ============
STRICT_MENTOR_PROMPT = """你是 Python 编程导师，不是代码生成器。

【回答长度限制】
每次回复控制在 300 字以内。简洁有力，直击要点。

【核心原则】
1. **绝不直接给答案**：必须引导思考过程
2. **绝不代写完整代码**：只提供思路、伪代码或代码片段
3. **基于上下文指导**：回顾之前的对话，保持连贯性
4. **苏格拉底式引导**：用提问代替直接回答

【多轮对话策略】
- 第1轮：了解学生问题，给出初步引导
- 第2轮：根据学生反馈，深化引导
- 第3轮+：逐步推进，帮助学生自主发现答案
- 如果学生还是不懂：换一种方式解释，但不要直接给答案

【绝对禁止】
- 生成完整可运行的作业代码
- 直接给出选择题/填空题答案
- 回复超过 300 字"""

# ============ 5 个学生的多轮对话场景 ============
# 每个场景是一个连续的对话线程
MULTI_TURN_SCENARIOS = [
    {
        "name": "小明",
        "email": "xiaoming@test.edu",
        "profile": "想直接要答案但被引导思考",
        "thread": [
            # 第1轮：学生直接要答案
            "这道编程题的答案是什么？直接给我代码",
            # 第2轮：AI 引导后，学生还是想要答案
            "我还是不太懂，你就不能直接告诉我怎么写吗？",
            # 第3轮：学生尝试理解
            "那你能说说思路吗？我应该从哪里开始想？",
            # 第4轮：学生描述理解
            "我理解是要先读取输入，然后处理数据，最后输出结果？",
            # 第5轮：学生尝试写代码但遇到问题
            "我写了代码但是报错了，你能帮我看看吗？（附上错误信息）",
            # 第6轮：学生根据提示修改后
            "我按照你说的改了，现在能运行了，但是结果不对",
            # 第7轮：学生继续追问
            "那我应该怎么调试呢？用 print 打印中间结果吗？",
            # 第8轮：学生确认理解
            "哦我发现了，是边界条件没处理好，这样改对吗？",
            # 第9轮：学生要求优化
            "这个解法时间复杂度是多少？能优化吗？",
            # 第10轮：总结
            "谢谢老师，这次我明白了，以后我会先自己思考问题",
        ],
    },
    {
        "name": "小红",
        "email": "xiaohong@test.edu",
        "profile": "基础薄弱，需要循序渐进",
        "thread": [
            "我完全不懂 for 循环，你能教教我吗？",
            "我看了语法但还是不明白，循环是怎么执行的？",
            "那 range(5) 会生成什么数字？",
            "如果我想从 1 数到 5 呢？",
            "循环里面可以嵌套另一个循环吗？",
            "双重循环是怎么执行的？先执行内层还是外层？",
            "能给我一个简单的例子让我理解吗？",
            "我自己写了一个，你能帮我看看对不对吗？",
            "为什么我的结果是错的？我哪里想错了？",
            "现在我明白了，谢谢老师的耐心指导！",
        ],
    },
    {
        "name": "小刚",
        "email": "xiaogang@test.edu",
        "profile": "偏题但被引导回正途",
        "thread": [
            "我想用 Python 写个自动抢课的脚本",
            "为什么不能帮我写？这只是个技术问题",
            "那你能教我怎么用 Python 发送网络请求吗？",
            "requests 库怎么安装？基本用法是什么？",
            "GET 和 POST 请求有什么区别？",
            "怎么解析网页上的数据？",
            " BeautifulSoup 是什么？怎么用？",
            "我能用这些技术做什么合法的项目？",
            "我想做个天气查询工具，从哪开始？",
            "好的，我明白了，会用在正当的地方学习",
        ],
    },
    {
        "name": "小丽",
        "email": "xiaoli@test.edu",
        "profile": "主动思考，寻求确认和深化",
        "thread": [
            "变量就像是给数据贴标签，这样理解对吗？",
            "那如果我把 a = 5 改成 a = 10，原来的 5 去哪了？",
            "Python 里的变量是引用还是拷贝？",
            "列表和元组的区别是什么？什么时候用哪个？",
            "我理解的列表是可变的，元组是不可变的，对吗？",
            "那字典是什么原理？为什么查找这么快？",
            "哈希表是什么意思？能简单解释一下吗？",
            "集合和列表的主要区别是什么？",
            "这些数据结构在内存中是怎么存储的？",
            "谢谢老师，这些概念我现在理解得更清楚了",
        ],
    },
    {
        "name": "小华",
        "email": "xiaohua@test.edu",
        "profile": "进阶问题，深度探讨",
        "thread": [
            "递归的时间复杂度怎么分析？",
            "递归树的高度和什么有关？",
            "为什么递归会有栈溢出的风险？",
            "尾递归优化是什么原理？Python 支持吗？",
            "那怎么把递归改成迭代？",
            "动态规划和递归有什么关系？",
            "能用记忆化搜索优化递归吗？",
            "备忘录和迭代的 DP 有什么区别？",
            "空间复杂度还能优化吗？",
            "明白了，递归改迭代的关键是手动维护栈状态",
        ],
    },
]


def get_db_session():
    """获取数据库会话"""
    url = settings.database_url.replace("+aiosqlite", "+pysqlite").replace(
        "+asyncpg", ""
    )
    engine = create_engine(url, pool_pre_ping=True)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    return SessionLocal()


def setup_student(session, config):
    """创建或重置学生"""
    existing = session.query(Student).filter(Student.email == config["email"]).first()

    if existing:
        existing.current_week_quota = 50000
        existing.used_quota = 0
        print(f"  🔄 重置: {config['name']}")
        return existing

    api_key = "tp_" + uuid.uuid4().hex[:32]
    student = Student(
        id=str(uuid.uuid4()),
        name=config["name"],
        email=config["email"],
        api_key_hash=hash_api_key(api_key),
        created_at=datetime.now(),
        current_week_quota=50000,
        used_quota=0,
    )
    session.add(student)
    print(f"  ✅ 创建: {config['name']}")
    return student


def setup_system_prompt(session):
    """设置系统提示词"""
    prompt = (
        session.query(WeeklySystemPrompt)
        .filter(
            WeeklySystemPrompt.week_start <= 1,
            WeeklySystemPrompt.week_end >= 1,
        )
        .first()
    )

    if prompt:
        prompt.system_prompt = STRICT_MENTOR_PROMPT
        prompt.is_active = True
    else:
        prompt = WeeklySystemPrompt(
            week_start=1,
            week_end=1,
            system_prompt=STRICT_MENTOR_PROMPT,
            description="第1周：多轮连续对话导师模式测试",
            is_active=True,
        )
        session.add(prompt)

    session.commit()
    print("  ✅ 系统提示词已配置")


async def call_deepseek(messages: list, student_name: str, turn: int) -> dict:
    """调用 DeepSeek API"""
    headers = {
        "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
        "Content-Type": "application/json",
    }

    payload = {
        "model": MODEL,
        "messages": messages,
        "temperature": 0.7,
        "max_tokens": 400,
    }

    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(DEEPSEEK_API_URL, headers=headers, json=payload)
        response.raise_for_status()
        data = response.json()

        return {
            "content": data["choices"][0]["message"]["content"],
            "tokens": data.get("usage", {}).get("total_tokens", 0),
        }


async def run_conversation_thread(session, student, config):
    """运行一个学生的多轮对话线程"""
    print(f"\n{'=' * 70}")
    print(f"👤 [{config['name']}] - {config['profile']}")
    print(f"{'=' * 70}")

    # 维护对话历史
    messages = [{"role": "system", "content": STRICT_MENTOR_PROMPT}]
    thread_results = []

    for turn, user_message in enumerate(config["thread"], 1):
        print(f"\n  第 {turn}/10 轮:")
        print(f"  学生: {user_message[:60]}...")

        # 添加用户消息到历史
        messages.append({"role": "user", "content": user_message})

        try:
            # 调用 API（包含完整历史）
            result = await call_deepseek(messages, config["name"], turn)
            ai_response = result["content"]
            tokens = result["tokens"]

            # 添加 AI 回复到历史（用于下一轮上下文）
            messages.append({"role": "assistant", "content": ai_response})

            # 保存到数据库
            conv = Conversation(
                student_id=student.id,
                timestamp=datetime.now(),
                prompt_text=user_message,
                response_text=ai_response,
                tokens_used=tokens,
                action_taken="passed",
                week_number=1,
            )
            session.add(conv)

            # 更新配额
            student.used_quota += tokens

            word_count = len(ai_response)
            print(f"  AI: {ai_response[:80]}...")
            print(f"  📊 字数: {word_count} | Tokens: {tokens}")

            thread_results.append(
                {
                    "turn": turn,
                    "user": user_message,
                    "assistant": ai_response,
                    "word_count": word_count,
                    "tokens": tokens,
                }
            )

            await asyncio.sleep(0.3)

        except Exception as e:
            print(f"  ❌ 错误: {e}")

    return thread_results


async def run_test():
    """运行多轮对话测试"""
    print("=" * 70)
    print("🎓 多轮连续对话测试")
    print("=" * 70)
    print(f"模型: {MODEL}")
    print("测试学生: 5人")
    print("每生轮数: 10轮（保持上下文）")
    print("总计: 50轮对话\n")

    if not DEEPSEEK_API_KEY:
        print("❌ 错误: 未找到 DEEPSEEK_API_KEY")
        return

    session = get_db_session()

    # 1. 设置学生
    print("📋 设置测试学生...")
    students = []
    for config in MULTI_TURN_SCENARIOS:
        student = setup_student(session, config)
        students.append((student, config))
    session.commit()

    # 2. 设置系统提示词
    print("\n📝 配置系统提示词...")
    setup_system_prompt(session)

    # 3. 运行多轮对话（按顺序，不是并发）
    print("\n🚀 开始多轮连续对话测试...")
    print("注意：每个学生内部保持上下文，学生之间独立")

    all_results = []
    total_tokens = 0

    for student, config in students:
        thread_results = await run_conversation_thread(session, student, config)
        all_results.append(
            {
                "student": config["name"],
                "profile": config["profile"],
                "thread": thread_results,
            }
        )
        total_tokens += sum(r["tokens"] for r in thread_results)
        session.commit()  # 每个学生完成后提交

    session.close()

    # 4. 打印报告
    print("\n" + "=" * 70)
    print("📊 测试报告")
    print("=" * 70)
    print(f"\n总计: 50 轮对话, {total_tokens} tokens")

    # 打印一个完整的对话线程作为示例
    print("\n" + "=" * 70)
    print("📝 完整对话示例：[小明] 的 10 轮对话")
    print("=" * 70)

    for result in all_results:
        if result["student"] == "小明":
            for turn in result["thread"]:
                print(f"\n{'─' * 70}")
                print(f"第 {turn['turn']} 轮:")
                print(f"学生: {turn['user']}")
                print(f"AI: {turn['assistant']}")
            break

    print("\n" + "=" * 70)
    print("✅ 多轮对话测试完成！数据已保存到数据库")
    print("=" * 70)
    print("""
🔍 查看结果:
  访问: http://localhost:5173/conversations
  筛选: week_number = 1

📌 验证要点:
  • 每个学生的 10 轮对话是否保持上下文连贯？
  • AI 是否记得之前的对话内容？
  • 导师角色是否在多轮中保持一致？
  • 学生从"要答案"到"理解"的转变过程是否自然？
""")


if __name__ == "__main__":
    asyncio.run(run_test())
