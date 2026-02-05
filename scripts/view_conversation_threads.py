#!/usr/bin/env python3
"""
查看多轮连续对话效果

按学生分组，展示完整的对话线程
"""

import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from admin.db_utils_v2 import get_all_students, get_conversations_by_student


def view_student_thread(student_name: str):
    """查看某个学生的完整对话线程"""
    # 找到学生
    students = get_all_students()
    student = None
    for s in students:
        if s["name"] == student_name:
            student = s
            break

    if not student:
        print(f"❌ 找不到学生: {student_name}")
        print(f"可用学生: {', '.join(s['name'] for s in students)}")
        return

    # 获取对话
    convs = get_conversations_by_student(student["id"], limit=100)
    # 按时间正序排列（从早到晚）
    convs.reverse()

    print("=" * 80)
    print(f"🎓 {student['name']} 的多轮对话线程")
    print(f"   邮箱: {student['email']}")
    print(f"   总对话数: {len(convs)} 轮")
    print("=" * 80)

    for i, conv in enumerate(convs, 1):
        print(f"\n{'─' * 80}")
        print(f"第 {i} 轮 | {conv['timestamp']}")
        print(f"{'─' * 80}")
        print(f"👤 学生: {conv['prompt_text']}")
        print(f"\n🤖 AI导师: {conv['response_text']}")
        print(f"\n📊 Tokens: {conv['tokens_used']} | Week: {conv['week_number']}")

    print(f"\n{'=' * 80}")
    print(f"✅ {student['name']} 的对话线程结束")
    print(f"{'=' * 80}")


def view_all_summary():
    """查看所有学生的对话摘要"""
    print("=" * 80)
    print("📊 所有学生对话摘要")
    print("=" * 80)

    students = get_all_students()
    for s in students:
        convs = get_conversations_by_student(s["id"], limit=100)
        if len(convs) > 0:
            print(f"\n👤 {s['name']} ({s['email']})")
            print(f"   总对话数: {len(convs)} 轮")
            print("   最新对话:")
            for c in convs[:3]:
                print(f"     - {str(c['timestamp'])[:16]}: {c['prompt_text'][:40]}...")


def compare_teaching_effect():
    """对比不同学生类型的教学效果"""
    print("=" * 80)
    print("📈 教学效果对比分析")
    print("=" * 80)

    test_students = {
        "小明": "直接索取答案型",
        "小红": "基础薄弱依赖型",
        "小刚": "偏题探索型",
        "小丽": "思考但寻求确认型",
        "小华": "进阶挑战型",
    }

    students = get_all_students()

    for s in students:
        if s["name"] in test_students:
            convs = get_conversations_by_student(s["id"], limit=100)
            convs.reverse()  # 正序

            print(f"\n{'─' * 80}")
            print(f"👤 {s['name']} - {test_students[s['name']]}")
            print(f"{'─' * 80}")

            # 显示第一轮和最后一轮
            if len(convs) >= 2:
                print("\n📝 第 1 轮（初始状态）:")
                print(f"   学生: {convs[0]['prompt_text'][:60]}...")
                print(f"   AI: {convs[0]['response_text'][:80]}...")

                print("\n📝 最后 1 轮（结束状态）:")
                print(f"   学生: {convs[-1]['prompt_text'][:60]}...")
                print(f"   AI: {convs[-1]['response_text'][:80]}...")

                # 检查学生态度变化
                first = convs[0]["prompt_text"]
                last = convs[-1]["prompt_text"]

                if "谢谢" in last or "明白" in last:
                    print("\n✅ 效果: 学生态度积极转变（从索取到感谢）")
                elif "直接" in first and "明白" in last:
                    print("\n✅ 效果: 学生从要答案到理解思考")
                else:
                    print("\n⚠️ 效果: 需要进一步观察")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="查看多轮对话效果")
    parser.add_argument("student", nargs="?", help="查看特定学生的对话线程（如：小明）")
    parser.add_argument("--summary", action="store_true", help="显示所有学生摘要")
    parser.add_argument("--analysis", action="store_true", help="教学效果对比分析")

    args = parser.parse_args()

    if args.student:
        view_student_thread(args.student)
    elif args.summary:
        view_all_summary()
    elif args.analysis:
        compare_teaching_effect()
    else:
        # 默认显示分析
        compare_teaching_effect()
        print("\n" + "=" * 80)
        print("💡 使用提示:")
        print(
            "   python scripts/view_conversation_threads.py 小明    # 查看小明的完整对话"
        )
        print(
            "   python scripts/view_conversation_threads.py --summary  # 查看所有摘要"
        )
        print("=" * 80)
