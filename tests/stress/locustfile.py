"""
TeachProxy 压力测试 - Locust 脚本

运行方式:
    uv run locust -f tests/stress/locustfile.py --host http://localhost:8000 \
        --headless -u 50 -r 10 --run-time 5m
"""

import json
import random
from pathlib import Path
from locust import HttpUser, task, between, events

# Load prompts
PROMPTS_FILE = Path(__file__).parent / "data" / "prompts.json"
try:
    with open(PROMPTS_FILE) as f:
        PROMPTS = json.load(f)
except:
    PROMPTS = {
        "normal": ["Hello", "解释Python", "什么是HTTP"],
        "rule_triggered": ["帮我写代码", "帮我写爬虫"],
    }

class TeachProxyUser(HttpUser):
    """TeachProxy 压力测试用户"""
    wait_time = between(0.1, 0.5)
    
    def on_start(self):
        self.client.headers["Authorization"] = "Bearer sk-stress-test-user"
        self.client.headers["Content-Type"] = "application/json"
    
    @task(70)
    def chat_normal(self):
        """普通聊天请求"""
        self.client.post(
            "/v1/chat/completions",
            json={
                "model": "deepseek-chat",
                "messages": [{"role": "user", "content": random.choice(PROMPTS["normal"])}],
                "stream": False,
                "max_tokens": 100,
            },
            name="chat_normal",
        )
    
    @task(20)
    def chat_streaming(self):
        """流式聊天请求"""
        with self.client.post(
            "/v1/chat/completions",
            json={
                "model": "deepseek-chat",
                "messages": [{"role": "user", "content": random.choice(PROMPTS["normal"])}],
                "stream": True,
                "max_tokens": 100,
            },
            name="chat_streaming",
            stream=True,
        ) as resp:
            for _ in resp.iter_content(chunk_size=1024):
                pass
    
    @task(10)
    def chat_rule(self):
        """规则触发请求"""
        self.client.post(
            "/v1/chat/completions",
            json={
                "model": "deepseek-chat",
                "messages": [{"role": "user", "content": random.choice(PROMPTS["rule_triggered"])}],
                "stream": False,
                "max_tokens": 100,
            },
            name="chat_rule",
        )

@events.test_stop.add_listener
def on_test_stop(env, **kwargs):
    stats = env.runner.stats.total
    print("\n" + "=" * 50)
    print(f"总请求: {stats.num_requests}, 失败: {stats.num_failures}")
    if stats.num_requests > 0:
        print(f"成功率: {100-stats.fail_ratio*100:.1f}%, 平均延迟: {stats.avg_response_time:.0f}ms")
        print(f"P95: {stats.get_response_time_percentile(0.95):.0f}ms, RPS: {stats.total_rps:.1f}")
    print("=" * 50)
