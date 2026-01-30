#!/usr/bin/env python3
"""
TeachProxy 长时间压力测试

简化版本，专门用于长时间固定负载测试。
不使用 LoadTestShape，直接通过 --users 和 --run-time 控制。

Usage:
    # 20分钟测试，100用户
    locust -f tests/stress/locustfile_long.py --headless \\
        --users 100 --spawn-rate 10 --run-time 20m \\
        --host=http://localhost:8000

    # 1小时测试
    locust -f tests/stress/locustfile_long.py --headless \\
        --users 50 --spawn-rate 5 --run-time 1h \\
        --host=http://localhost:8000
"""

import json
import os
import random
import time
from datetime import datetime
from typing import Any, Dict, List

from locust import HttpUser, task, between, events


# =============================================================================
# 环境配置
# =============================================================================

# 设置 Mock Provider 模式
os.environ["TEACHPROXY_MOCK_PROVIDER"] = "true"
os.environ.pop("DEEPSEEK_API_KEY", None)
os.environ.pop("OPENAI_API_KEY", None)
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

    wait_time = between(0.2, 1)
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

            for student in students:
                parts = student.id.split("_")
                if len(parts) >= 3:
                    index = parts[-1]
                    cls._test_api_keys.append(f"sk-stress-test-{index}")
        finally:
            session.close()

        print(f"[GatewayUser] Loaded {len(cls._test_api_keys)} test API keys")

    def on_start(self):
        """用户启动时执行"""
        if not self._test_api_keys:
            self.load_test_api_keys()

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
                    try:
                        data = response.json()
                        if "choices" not in data:
                            response.failure(f"Invalid response: {data}")
                    except:
                        response.failure("Invalid JSON response")
            elif response.status_code == 429:
                response.success()
            else:
                response.failure(f"HTTP {response.status_code}")


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
