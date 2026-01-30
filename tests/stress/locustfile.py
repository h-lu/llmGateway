#!/usr/bin/env python3
"""
TeachProxy 压力测试 - Locust 版本

支持三种测试类型：
1. Load Test - 负载测试（验证正常负载下性能）
2. Soak Test - 浸泡测试（长时间稳定性，发现内存泄漏）
3. Spike Test - 尖峰测试（突发流量应对能力）
4. Stress Test - 压力测试（逐步加压至系统极限）

Usage:
    # Web UI 模式（推荐）
    locust -f tests/stress/locustfile.py --host=http://localhost:8000

    # 无头模式 - Load Test
    locust -f tests/stress/locustfile.py --headless --users 50 --spawn-rate 5 --run-time 5m

    # Soak Test (1小时)
    locust -f tests/stress/locustfile.py --headless --soak

    # Spike Test
    locust -f tests/stress/locustfile.py --headless --spike

    # Stress Test
    locust -f tests/stress/locustfile.py --headless --stress

    # 自定义配置
    locust -f tests/stress/locustfile.py --users 100 --spawn-rate 10 --run-time 10m --html=report.html
"""

import asyncio
import json
import os
import random
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

import httpx
from locust import HttpUser, task, between, events, LoadTestShape
from locust.runners import MasterRunner

# =============================================================================
# 环境配置
# =============================================================================

# 设置 Mock Provider 模式
os.environ["TEACHPROXY_MOCK_PROVIDER"] = "true"
os.environ.pop("DEEPSEEK_API_KEY", None)
os.environ.pop("OPENAI_API_KEY", None)
# 提高速率限制
os.environ["RATE_LIMIT_REQUESTS_PER_MINUTE"] = "10000"
os.environ["RATE_LIMIT_BURST_SIZE"] = "1000"


# =============================================================================
# 测试数据
# =============================================================================

NORMAL_PROMPTS = [
    "Hello, how are you?",
    "What is Python?",
    "Explain recursion",
    "What is a function?",
    "How do I install packages?",
    "What's the difference between list and tuple?",
    "Explain decorators",
    "What is a class?",
]

RULE_TRIGGERED_PROMPTS = [
    "Write a sorting algorithm",
    "Code a calculator",
    "Generate a program",
    "Help me implement",
    "Give me the code for",
]

LONG_CONTEXT_PROMPTS = [
    "Explain Python decorators in detail with examples",
    "What are the best practices for error handling in Python?",
    "How does async/await work in Python?",
]


# =============================================================================
# Locust 用户类
# =============================================================================

class GatewayUser(HttpUser):
    """
    模拟 TeachProxy 网关用户

    用户行为分布：
    - 70% Normal Chat (普通对话)
    - 20% Streaming Chat (流式响应)
    - 10% Rule Triggered (触发规则)
    """

    # 更真实的思考时间：0.2-1秒之间（之前1-5秒太长）
    wait_time = between(0.2, 1)

    # 测试 API key 列表（在启动时加载）
    _test_api_keys = []

    @classmethod
    def load_test_api_keys(cls):
        """从数据库加载测试 API keys"""
        if cls._test_api_keys:
            return

        import sys
        from pathlib import Path
        sys.path.insert(0, str(Path(__file__).parent.parent.parent))

        from gateway.app.core.config import settings
        from gateway.app.db.models import Student
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker

        engine = create_engine(settings.database_url.replace("+aiosqlite", "").replace("+pysqlite", ""))
        Session = sessionmaker(bind=engine)
        session = Session()

        try:
            students = session.query(Student).filter(
                Student.id.like("locust_test_%")
            ).order_by(Student.id.desc()).limit(200).all()

            # 生成对应的 API keys
            for student in students:
                # API key 格式：sk-stress-test-{index}
                # 从 student_id 中提取索引，如 "locust_test_1769753006_001" -> 001
                parts = student.id.split("_")
                if len(parts) >= 3:
                    index = parts[-1]
                    cls._test_api_keys.append(f"sk-stress-test-{index}")
        finally:
            session.close()

        print(f"[GatewayUser] Loaded {len(cls._test_api_keys)} test API keys")

    def on_start(self):
        """用户启动时执行（登录、初始化）"""
        # 确保加载了 API keys
        if not self._test_api_keys:
            self.load_test_api_keys()

        # 使用循环分配 API key 给用户
        user_index = id(self) % len(self._test_api_keys)
        api_key = self._test_api_keys[user_index]

        self.client.headers.update({
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        })
        self.client.timeout = 30

    @task(7)
    def normal_chat(self):
        """普通聊天请求（70%权重）"""
        prompt = random.choice(NORMAL_PROMPTS)
        self._do_chat_request(prompt, stream=False, request_type="normal")

    @task(2)
    def streaming_chat(self):
        """流式聊天请求（20%权重）"""
        prompt = random.choice(LONG_CONTEXT_PROMPTS)
        self._do_chat_request(prompt, stream=True, request_type="streaming")

    @task(1)
    def rule_triggered_chat(self):
        """触发规则的请求（10%权重）"""
        prompt = random.choice(RULE_TRIGGERED_PROMPTS)
        self._do_chat_request(prompt, stream=False, request_type="rule_triggered")

    def _do_chat_request(self, prompt: str, stream: bool, request_type: str):
        """执行聊天请求"""
        payload = {
            "model": "deepseek-chat",
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": random.randint(100, 500),
            "temperature": random.uniform(0.5, 1.0),
            "stream": stream
        }

        with self.client.post(
            "/v1/chat/completions",
            json=payload,
            catch_response=True,
            name=f"/v1/chat/completions ({request_type})"
        ) as response:
            if response.status_code == 200:
                if stream:
                    # 消费流式响应（处理 bytes）
                    for line in response.iter_lines():
                        if not line:
                            continue
                        line_str = line.decode('utf-8') if isinstance(line, bytes) else line
                        line_str = line_str.strip()
                        if line_str == "data: [DONE]":
                            break
                        if line_str.startswith("data: "):
                            try:
                                data = json.loads(line_str[6:])
                                if data.get("choices"):
                                    content = data["choices"][0].get("delta", {}).get("content", "")
                            except:
                                pass
                else:
                    # 非流式响应
                    try:
                        data = response.json()
                        if "choices" not in data:
                            response.failure(f"Invalid response: {data}")
                    except:
                        response.failure("Invalid JSON response")
            elif response.status_code == 429:
                # 配额耗尽是预期行为
                response.success()
            else:
                response.failure(f"HTTP {response.status_code}")


class RealisticGatewayUser(GatewayUser):
    """
    更真实的用户模拟，包含模拟 AI API 延迟

    注意：这需要使用自定义的 Mock Provider，或者在外部添加延迟
    """

    wait_time = between(1, 3)  # 更长的思考时间，模拟真实用户

    @task
    def realistic_conversation(self):
        """模拟真实对话流程"""
        # 第一条消息
        self._do_chat_request("Hello", stream=False, request_type="greeting")

        # 短暂思考
        time.sleep(random.uniform(2, 5))

        # 后续消息
        follow_up = random.choice([
            "Can you explain more?",
            "That's helpful, thanks",
            "What about X?",
            "Ok got it"
        ])
        self._do_chat_request(follow_up, stream=False, request_type="followup")


# =============================================================================
# Load Test Shapes - 测试场景定义
# =============================================================================

class LoadTestShape(LoadTestShape):
    """
    标准负载测试 - 阶梯式增长

    模拟从零开始逐步增加用户，观察系统在不同负载下的表现。
    """

    stages = [
        # duration, users, spawn_rate
        (60, 10, 5),    # 1分钟：10用户（基准）
        (120, 25, 10),   # 2分钟：25用户
        (180, 50, 15),   # 3分钟：50用户
        (240, 100, 20),  # 4分钟：100用户
        (300, 50, 10),   # 5分钟：降到50用户
        (360, 10, 5),    # 6分钟：回到10用户
    ]

    def tick(self):
        run_time = self.get_run_time()

        for stage_time, users, spawn_rate in self.stages:
            if run_time < stage_time:
                return (users, spawn_rate)

        return None


class SoakTestShape(LoadTestShape):
    """
    浸泡测试 (Soak Test) / 耐久测试

    长时间稳定负载，用于发现：
    - 内存泄漏
    - 连接池耗尽
    - 缓存失效问题
    - 资源未释放

    典型时长：1-24小时
    """

    # 配置
    STABLE_USERS = 20
    DURATION_SECONDS = 3600  # 1小时，可扩展到更长
    SPAWN_RATE = 5

    def tick(self):
        run_time = self.get_run_time()

        if run_time < self.DURATION_SECONDS:
            # 前期 ramp-up
            if run_time < 60:
                users = min(self.STABLE_USERS, int(run_time / 3))
                return (users, min(self.SPAWN_RATE, users))
            # 稳定负载期
            return (self.STABLE_USERS, self.SPAWN_RATE)

        return None


class SpikeTestShape(LoadTestShape):
    """
    尖峰测试 (Spike Test)

    模拟突发流量，验证系统：
    - 能否处理突然的流量激增
    - 流量下降后能否快速恢复
    - 自动扩缩容是否生效

    典型场景：促销活动、社交媒体传播
    """

    # 配置
    BASELINE_USERS = 10
    SPIKE_USERS = 200
    SPAWN_RATE_NORMAL = 5
    SPAWN_RATE_SPIKE = 50  # 快速 ramp-up

    stages = [
        # 阶梯式：duration, users, spawn_rate
        (60, BASELINE_USERS, SPAWN_RATE_NORMAL),      # 0-1min: 基线
        (70, SPIKE_USERS, SPAWN_RATE_SPIKE),          # 1-1.7min: 突增到200
        (130, SPIKE_USERS, SPAWN_RATE_NORMAL),        # 1.7-2.7min: 维持高负载
        (140, BASELINE_USERS, SPAWN_RATE_NORMAL),     # 2.7-3min: 快速下降
        (200, BASELINE_USERS, SPAWN_RATE_NORMAL),     # 3-4min: 恢复期观察
    ]

    def tick(self):
        run_time = self.get_run_time()

        for stage_time, users, spawn_rate in self.stages:
            if run_time < stage_time:
                return (users, spawn_rate)

        return None


class StressTestShape(LoadTestShape):
    """
    压力测试 (Stress Test)

    逐步增加用户数直到系统崩溃，用于：
    - 发现系统极限容量
    - 识别瓶颈点
    - 验证降级策略

    注意：此测试会让系统达到极限，生产环境慎用
    """

    # 配置
    MAX_USERS = 500
    RAMP_DURATION = 300  # 5分钟内达到最大用户
    SPAWN_RATE = 20

    def tick(self):
        run_time = self.get_run_time()

        if run_time < self.RAMP_DURATION:
            # 线性增长
            users = int((run_time / self.RAMP_DURATION) * self.MAX_USERS)
            users = max(10, users)  # 至少10用户
            return (users, self.SPAWN_RATE)

        return None


class LongRunShape(LoadTestShape):
    """
    长时间稳定负载测试

    用于长时间（如20分钟、1小时）的稳定性测试，
    保持固定用户数，不自动停止。

    注意：测试时长由 --run-time 参数控制，此 Shape 始终返回固定用户数
    """

    # 固定用户数和启动速率
    FIXED_USERS = 100
    SPAWN_RATE = 10

    def tick(self):
        # 始终返回相同的用户数，让 --run-time 控制测试时长
        # 这样测试会持续运行直到达到 --run-time 指定的时间
        return (self.FIXED_USERS, self.SPAWN_RATE)


class CustomLoadShape(LoadTestShape):
    """
    自定义负载形状 - 支持通过环境变量配置

    环境变量：
    - LOCUST_STAGES: JSON 格式的阶段配置
      例如: [{"duration":60,"users":10,"spawn_rate":5},{"duration":120,"users":50,"spawn_rate":10}]
    """

    def __init__(self):
        super().__init__()
        self.stages = self._load_stages_from_env()

    def _load_stages_from_env(self) -> List[Dict[str, Any]]:
        """从环境变量加载阶段配置"""
        stages_str = os.getenv("LOCUST_STAGES")
        if stages_str:
            try:
                return json.loads(stages_str)
            except:
                pass

        # 默认阶梯测试
        return [
            {"duration": 60, "users": 10, "spawn_rate": 5},
            {"duration": 120, "users": 25, "spawn_rate": 10},
            {"duration": 180, "users": 50, "spawn_rate": 10},
            {"duration": 240, "users": 100, "spawn_rate": 20},
        ]

    def tick(self):
        run_time = self.get_run_time()

        # 累计时间计算
        cumulative_time = 0
        for stage in self.stages:
            duration = stage["duration"]
            users = stage["users"]
            spawn_rate = stage["spawn_rate"]

            if cumulative_time <= run_time < cumulative_time + duration:
                return (users, spawn_rate)

            cumulative_time += duration

        return None


# =============================================================================
# 命令行参数处理
# =============================================================================

def setup_test_shape_from_args():
    """
    根据命令行参数设置默认的 LoadTestShape

    支持：
    - --soak: 使用 SoakTestShape
    - --spike: 使用 SpikeTestShape
    - --stress: 使用 StressTestShape
    - --long: 使用 LongRunShape（长时间稳定负载）
    - --shape: 自定义 JSON 配置
    """
    import sys

    args = sys.argv[1:]

    if "--soak" in args:
        os.environ["LOCUST_SHAPE_CLASS"] = "soak"
    elif "--spike" in args:
        os.environ["LOCUST_SHAPE_CLASS"] = "spike"
    elif "--stress" in args:
        os.environ["LOCUST_SHAPE_CLASS"] = "stress"
    elif "--long" in args:
        os.environ["LOCUST_SHAPE_CLASS"] = "long"
    elif "--shape" in args:
        idx = args.index("--shape")
        if idx + 1 < len(args):
            os.environ["LOCUST_STAGES"] = args[idx + 1]


# 在导入时设置
setup_test_shape_from_args()


def get_shape_class():
    """获取配置的 LoadTestShape 类"""
    shape_class = os.getenv("LOCUST_SHAPE_CLASS", "")

    if shape_class == "soak":
        return SoakTestShape
    elif shape_class == "spike":
        return SpikeTestShape
    elif shape_class == "stress":
        return StressTestShape
    elif shape_class == "long":
        return LongRunShape
    elif os.getenv("LOCUST_STAGES"):
        return CustomLoadShape
    else:
        return LoadTestShape  # 默认


# 设置 Locust 使用的 Shape 类（Locust 会查找这个模块级变量）
locust_shape_class = get_shape_class()


# =============================================================================
# 事件处理器 - 测试结果统计
# =============================================================================

@events.request.add_listener
def on_request(request_type, name, response_time, response_length, exception, **kwargs):
    """请求完成事件 - 记录详细指标"""
    if exception:
        print(f"[ERROR] {name}: {exception}")


@events.test_stop.add_listener
def on_test_stop(environment, **kwargs):
    """测试结束事件 - 生成摘要"""
    if isinstance(environment.runner, MasterRunner):
        return

    stats = environment.stats

    print("\n" + "=" * 60)
    print("📊 测试完成摘要")
    print("=" * 60)
    print(f"总请求数: {stats.total.num_requests}")
    print(f"失败请求: {stats.total.num_failures}")
    print(f"成功率: {(1 - stats.total.fail_ratio) * 100:.2f}%")
    print(f"平均响应时间: {stats.total.avg_response_time:.0f}ms")
    print(f"中位数响应时间: {stats.total.median_response_time:.0f}ms")
    print(f"P95 响应时间: {stats.total.get_response_time_percentile(0.95):.0f}ms")
    print(f"RPS: {stats.total.total_rps:.2f}")
    print("=" * 60)


# =============================================================================
# 数据库设置助手
# =============================================================================

def setup_test_students(count: int = 50):
    """
    创建测试学生账号

    Args:
        count: 创建的学生数量
    """
    import sys
    from pathlib import Path

    # 添加项目路径
    sys.path.insert(0, str(Path(__file__).parent.parent.parent))

    from gateway.app.core.config import settings
    from gateway.app.core.security import hash_api_key
    from gateway.app.db.models import Student
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    engine = create_engine(settings.database_url.replace("+aiosqlite", "").replace("+pysqlite", ""))
    Session = sessionmaker(bind=engine)
    session = Session()

    try:
        # 清理旧测试数据
        session.query(Student).filter(Student.id.like("locust_test_%")).delete(synchronize_session=False)
        session.commit()

        # 创建测试学生
        timestamp = int(time.time())

        for i in range(1, count + 1):
            student_id = f"locust_test_{timestamp}_{i:03d}"
            api_key = f"sk-stress-test-{i:03d}"
            api_key_hash = hash_api_key(api_key)

            student = Student(
                id=student_id,
                name=f"Locust Test Student {i}",
                email=f"locust{i}_{timestamp}@test.com",
                api_key_hash=api_key_hash,
                created_at=datetime.now(),
                current_week_quota=100000,
                used_quota=0
            )
            session.add(student)

        session.commit()
        print(f"[Setup] Created {count} test students with API keys: sk-stress-test-001 to sk-stress-test-{count:03d}")

    finally:
        session.close()


def cleanup_test_students():
    """清理测试学生账号"""
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).parent.parent.parent))

    from gateway.app.core.config import settings
    from gateway.app.db.models import Student, Conversation
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    engine = create_engine(settings.database_url.replace("+aiosqlite", "").replace("+pysqlite", ""))
    Session = sessionmaker(bind=engine)
    session = Session()

    try:
        session.query(Conversation).filter(
            Conversation.student_id.like("locust_test_%")
        ).delete(synchronize_session=False)

        session.query(Student).filter(
            Student.id.like("locust_test_%")
        ).delete(synchronize_session=False)

        session.commit()
        print("[Cleanup] Test data removed")

    finally:
        session.close()


# =============================================================================
# 命令行入口
# =============================================================================

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="TeachProxy Locust Stress Test")
    parser.add_argument("--setup", action="store_true", help="Setup test students")
    parser.add_argument("--cleanup", action="store_true", help="Cleanup test data")
    parser.add_argument("--count", type=int, default=50, help="Number of test students")

    args = parser.parse_args()

    if args.setup:
        setup_test_students(args.count)
    elif args.cleanup:
        cleanup_test_students()
    else:
        print("Use 'locust -f <this_file>' to run the test")
        print("\nQuick setup:")
        print("  python locustfile.py --setup")
        print("\nQuick cleanup:")
        print("  python locustfile.py --cleanup")
