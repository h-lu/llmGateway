"""E2E测试数据准备: 注入测试用的每周提示词."""
import asyncio
import sys
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from datetime import datetime

# 测试用的每周提示词
TEST_PROMPTS = [
    {
        "week_start": 1,
        "week_end": 1,
        "description": "第1周：理论基础周 (E2E测试)",
        "system_prompt": """你是Python编程导师，这是第1周学习。
规则：
1. 重点解释编程概念和原理
2. 使用生活化的比喻帮助理解
3. 详细解释"为什么"要这样做
4. 给出完整的概念定义

示例风格："变量就像一个盒子，你可以把数据放进去..."
""",
        "is_active": True,
    },
    {
        "week_start": 2,
        "week_end": 2,
        "description": "第2周：苏格拉底式提问周 (E2E测试)",
        "system_prompt": """你是Python编程导师，这是第2周学习。
规则：
1. 不直接给出答案
2. 必须用提问引导学生思考
3. 每个回答至少包含2-3个问题
4. 鼓励学生自己发现答案

示例风格："这是个好问题。在你写代码之前，你觉得第一步应该做什么？"
""",
        "is_active": True,
    },
    {
        "week_start": 3,
        "week_end": 3,
        "description": "第3周：实践练习周 (E2E测试)",
        "system_prompt": """你是Python编程导师，这是第3周学习。
规则：
1. 提供可运行的代码示例
2. 给出具体的练习题
3. 鼓励学生动手尝试
4. 代码注释要详细

示例风格："这是一个例子：```python\nx = 5\nprint(x)\n``` 现在你自己试试..."
""",
        "is_active": True,
    },
    {
        "week_start": 4,
        "week_end": 4,
        "description": "第4周：项目实战周 (E2E测试)",
        "system_prompt": """你是Python编程导师，这是第4周学习。
规则：
1. 围绕一个完整项目展开
2. 将大问题分解成小步骤
3. 每个步骤都有明确目标
4. 引导学生完成整个项目

示例风格："我们来做一个计算器。第一步，先实现加法功能..."
""",
        "is_active": True,
    },
]


async def seed_prompts():
    """注入测试提示词."""
    try:
        from gateway.app.db.async_session import get_async_session
        from gateway.app.db.models import WeeklySystemPrompt
        from sqlalchemy import select
        
        async with get_async_session() as session:
            for prompt_data in TEST_PROMPTS:
                # 检查是否已存在（通过description识别测试数据）
                result = await session.execute(
                    select(WeeklySystemPrompt).where(
                        WeeklySystemPrompt.description == prompt_data["description"]
                    )
                )
                existing = result.scalar_one_or_none()
                
                if existing:
                    print(f"✓ Prompt for week {prompt_data['week_start']} already exists")
                    continue
                
                # 创建新提示词
                prompt = WeeklySystemPrompt(
                    week_start=prompt_data["week_start"],
                    week_end=prompt_data["week_end"],
                    description=prompt_data["description"],
                    system_prompt=prompt_data["system_prompt"],
                    is_active=prompt_data["is_active"],
                    created_at=datetime.utcnow(),
                    updated_at=datetime.utcnow(),
                )
                session.add(prompt)
                print(f"✓ Created prompt for week {prompt_data['week_start']}: {prompt_data['description']}")
            
            await session.commit()
            print("\n✅ Seeding completed!")
            
    except Exception as e:
        print(f"❌ Error during seeding: {e}")
        raise


async def cleanup_prompts():
    """清理测试提示词."""
    try:
        from gateway.app.db.async_session import get_async_session
        from gateway.app.db.models import WeeklySystemPrompt
        from sqlalchemy import delete
        
        async with get_async_session() as session:
            for prompt_data in TEST_PROMPTS:
                result = await session.execute(
                    delete(WeeklySystemPrompt).where(
                        WeeklySystemPrompt.description == prompt_data["description"]
                    )
                )
                if result.rowcount > 0:
                    print(f"✓ Cleaned up prompt: {prompt_data['description']}")
            
            await session.commit()
            print("\n✅ Cleanup completed!")
            
    except Exception as e:
        print(f"❌ Error during cleanup: {e}")
        raise


async def list_prompts():
    """列出当前的每周提示词."""
    try:
        from gateway.app.db.async_session import get_async_session
        from gateway.app.db.models import WeeklySystemPrompt
        from sqlalchemy import select
        
        async with get_async_session() as session:
            result = await session.execute(select(WeeklySystemPrompt))
            prompts = result.scalars().all()
            
            print(f"\n📋 Found {len(prompts)} weekly prompts:\n")
            for p in prompts:
                status = "🟢 Active" if p.is_active else "🔴 Inactive"
                print(f"  Week {p.week_start}-{p.week_end}: {p.description}")
                print(f"    Status: {status}")
                print(f"    Preview: {p.system_prompt[:50]}...")
                print()
                
    except Exception as e:
        print(f"❌ Error listing prompts: {e}")
        raise


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Manage E2E test data for weekly prompts")
    parser.add_argument(
        "action",
        choices=["seed", "cleanup", "list"],
        help="Action to perform: seed (create), cleanup (remove), list (show all)"
    )
    args = parser.parse_args()
    
    if args.action == "seed":
        print("🌱 Seeding test prompts...")
        asyncio.run(seed_prompts())
    elif args.action == "cleanup":
        print("🧹 Cleaning up test prompts...")
        asyncio.run(cleanup_prompts())
    elif args.action == "list":
        print("📋 Listing all prompts...")
        asyncio.run(list_prompts())
