#!/usr/bin/env python3
"""
TeachProxy 多用户压力测试

模拟多个并发用户同时访问网关 API，测试系统在高负载下的性能表现。

本测试自动启用 Mock Provider 模式，无需配置真实 AI API Key。

Usage:
    python test_multi_user_stress.py --users 50 --duration 60
    python test_multi_user_stress.py -u 100 -d 300 --base-url http://localhost:8000
"""

from __future__ import annotations

# 设置 Mock Provider 环境变量（必须在导入 gateway 模块之前）
import os
os.environ["TEACHPROXY_MOCK_PROVIDER"] = "true"
# 清空真实 API key，强制使用 Mock Provider
os.environ.pop("DEEPSEEK_API_KEY", None)
os.environ.pop("OPENAI_API_KEY", None)
# 提高速率限制以支持高并发测试
os.environ["RATE_LIMIT_REQUESTS_PER_MINUTE"] = "10000"
os.environ["RATE_LIMIT_BURST_SIZE"] = "1000"

import argparse
import asyncio
import hashlib
import json
import random
import statistics
import sys
import time
import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from gateway.app.core.config import settings
from gateway.app.core.security import hash_api_key
from gateway.app.db.models import Student, Conversation


# =============================================================================
# 配置
# =============================================================================

@dataclass
class StressTestConfig:
    """压力测试配置"""
    # 并发设置
    concurrent_users: int = 50
    duration_seconds: int = 60
    ramp_up_seconds: float = 0.5  # 用户启动间隔
    
    # 请求行为
    min_think_time: float = 1.0  # 最小思考时间（秒）
    max_think_time: float = 5.0  # 最大思考时间（秒）
    request_timeout: float = 30.0
    
    # 网络
    base_url: str = "http://localhost:8000"
    
    # 测试数据
    student_count: int = 50
    
    # 请求类型权重
    normal_chat_weight: float = 0.70
    streaming_weight: float = 0.20
    rule_triggered_weight: float = 0.10
    
    # 报告
    report_dir: Path = field(default_factory=lambda: Path(__file__).parent / "reports")
    
    def __post_init__(self):
        if self.report_dir is None:
            self.report_dir = Path(__file__).parent / "reports"
        self.report_dir = Path(self.report_dir)
        self.report_dir.mkdir(parents=True, exist_ok=True)


# =============================================================================
# 数据加载
# =============================================================================

def load_prompts() -> Dict[str, List[str]]:
    """加载测试提示词"""
    data_dir = Path(__file__).parent / "data"
    prompts_file = data_dir / "prompts.json"
    
    if prompts_file.exists():
        with open(prompts_file, encoding="utf-8") as f:
            return json.load(f)
    
    # 默认提示词
    return {
        "normal": ["Hello, how are you?", "What is Python?", "Explain recursion"],
        "rule_triggered": ["Write a sorting algorithm", "Code a calculator"],
        "long_context": ["Explain Python decorators in detail"]
    }


PROMPTS = load_prompts()


# =============================================================================
# 性能指标
# =============================================================================

@dataclass
class RequestRecord:
    """单个请求记录"""
    timestamp: float
    user_id: str
    request_type: str
    latency_ms: float
    success: bool
    status_code: int
    error_type: Optional[str] = None
    prompt: str = ""
    response: str = ""


@dataclass 
class MetricsSnapshot:
    """指标快照"""
    timestamp: float
    total_requests: int = 0
    success_count: int = 0
    error_count: int = 0
    active_users: int = 0
    rps: float = 0.0
    avg_latency_ms: float = 0.0


class MetricsCollector:
    """性能指标收集器"""
    
    def __init__(self):
        self.records: List[RequestRecord] = []
        self.snapshots: List[MetricsSnapshot] = []
        self._lock = asyncio.Lock()
        self._start_time = time.time()
        self._last_snapshot_time = self._start_time
        self._last_request_count = 0
    
    async def record(self, record: RequestRecord) -> None:
        """记录请求"""
        async with self._lock:
            self.records.append(record)
    
    async def take_snapshot(self, active_users: int) -> MetricsSnapshot:
        """获取当前指标快照"""
        async with self._lock:
            now = time.time()
            total = len(self.records)
            success = sum(1 for r in self.records if r.success)
            
            # 计算 RPS（最近 10 秒）
            time_delta = now - self._last_snapshot_time
            request_delta = total - self._last_request_count
            rps = request_delta / time_delta if time_delta > 0 else 0
            
            # 计算平均延迟（最近 100 个成功请求）
            recent_latencies = [
                r.latency_ms for r in self.records[-100:] 
                if r.success
            ]
            avg_latency = statistics.mean(recent_latencies) if recent_latencies else 0
            
            snapshot = MetricsSnapshot(
                timestamp=now,
                total_requests=total,
                success_count=success,
                error_count=total - success,
                active_users=active_users,
                rps=round(rps, 2),
                avg_latency_ms=round(avg_latency, 2)
            )
            
            self.snapshots.append(snapshot)
            self._last_snapshot_time = now
            self._last_request_count = total
            
            return snapshot
    
    def get_latency_percentiles(self) -> Dict[str, float]:
        """计算延迟百分位数"""
        latencies = [r.latency_ms for r in self.records if r.success]
        if not latencies:
            return {"p50": 0, "p95": 0, "p99": 0}
        
        latencies.sort()
        n = len(latencies)
        
        def percentile(p: float) -> float:
            idx = int(n * p / 100)
            return latencies[min(idx, n - 1)]
        
        return {
            "p50": percentile(50),
            "p95": percentile(95),
            "p99": percentile(99)
        }
    
    def get_error_breakdown(self) -> Dict[str, int]:
        """错误类型分布"""
        errors = defaultdict(int)
        for r in self.records:
            if not r.success and r.error_type:
                errors[r.error_type] += 1
        return dict(errors)
    
    def get_request_type_stats(self) -> Dict[str, Dict[str, Any]]:
        """按请求类型统计"""
        stats = defaultdict(lambda: {"requests": 0, "success": 0, "latencies": []})
        
        for r in self.records:
            stats[r.request_type]["requests"] += 1
            if r.success:
                stats[r.request_type]["success"] += 1
                stats[r.request_type]["latencies"].append(r.latency_ms)
        
        result = {}
        for req_type, data in stats.items():
            result[req_type] = {
                "requests": data["requests"],
                "success_rate": round(data["success"] / data["requests"], 4) if data["requests"] > 0 else 0,
                "avg_latency_ms": round(statistics.mean(data["latencies"]), 2) if data["latencies"] else 0
            }
        
        return result


# =============================================================================
# 用户模拟器
# =============================================================================

class UserSimulator:
    """用户行为模拟器"""
    
    def __init__(
        self,
        user_id: str,
        api_key: str,
        config: StressTestConfig,
        metrics: MetricsCollector,
        client: httpx.AsyncClient,
    ):
        self.user_id = user_id
        self.api_key = api_key
        self.config = config
        self.metrics = metrics
        self.client = client
        self.request_count = 0
        self.running = True
    
    async def run(self) -> None:
        """运行用户会话"""
        # 随机启动延迟，避免同时启动
        await asyncio.sleep(random.uniform(0, self.config.ramp_up_seconds * 2))
        
        start_time = time.time()
        
        while self.running and (time.time() - start_time) < self.config.duration_seconds:
            await self._send_request()
            self.request_count += 1
            
            # 思考时间
            think_time = random.uniform(
                self.config.min_think_time,
                self.config.max_think_time
            )
            await asyncio.sleep(think_time)
    
    def stop(self) -> None:
        """停止用户会话"""
        self.running = False
    
    async def _send_request(self) -> None:
        """发送请求"""
        # 根据权重选择请求类型
        rand = random.random()
        if rand < self.config.normal_chat_weight:
            await self._send_normal_request()
        elif rand < self.config.normal_chat_weight + self.config.streaming_weight:
            await self._send_streaming_request()
        else:
            await self._send_rule_triggered_request()
    
    async def _send_normal_request(self) -> None:
        """发送普通聊天请求"""
        await self._do_request("normal", stream=False)
    
    async def _send_streaming_request(self) -> None:
        """发送流式聊天请求"""
        await self._do_request("streaming", stream=True)
    
    async def _send_rule_triggered_request(self) -> None:
        """发送规则触发请求"""
        await self._do_request("rule_triggered", stream=False)
    
    async def _do_request(self, request_type: str, stream: bool) -> None:
        """执行请求"""
        start_time = time.time()
        
        # 选择提示词
        if request_type == "rule_triggered":
            prompt = random.choice(PROMPTS.get("rule_triggered", PROMPTS["normal"]))
        else:
            prompt = random.choice(PROMPTS["normal"])
        
        record = RequestRecord(
            timestamp=start_time,
            user_id=self.user_id,
            request_type=request_type,
            latency_ms=0,
            success=False,
            status_code=0,
            prompt=prompt[:100]  # 截断存储
        )
        
        try:
            request_body = {
                "model": "deepseek-chat",
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": random.randint(100, 500),
                "temperature": random.uniform(0.5, 1.0),
                "stream": stream
            }
            
            response = await self.client.post(
                f"{self.config.base_url}/v1/chat/completions",
                headers={"Authorization": f"Bearer {self.api_key}"},
                json=request_body,
                timeout=self.config.request_timeout
            )
            
            latency_ms = (time.time() - start_time) * 1000
            record.latency_ms = latency_ms
            record.status_code = response.status_code
            
            if stream and response.status_code == 200:
                # 读取流式响应
                content_chunks = []
                async for line in response.aiter_lines():
                    if line.strip() == "data: [DONE]":
                        break
                    if line.startswith("data: "):
                        try:
                            data = json.loads(line[6:])
                            delta = data.get("choices", [{}])[0].get("delta", {})
                            content = delta.get("content", "")
                            if content:
                                content_chunks.append(content)
                        except:
                            pass
                record.response = "".join(content_chunks)[:200]
                record.success = True
            else:
                if response.status_code == 200:
                    record.success = True
                    try:
                        data = response.json()
                        if "choices" in data:
                            record.response = data["choices"][0].get("message", {}).get("content", "")[:200]
                    except:
                        pass
                elif response.status_code == 429:
                    # 配额耗尽是预期的行为
                    record.success = True
                    record.error_type = "quota_exceeded"
                else:
                    record.error_type = f"http_{response.status_code}"
            
        except httpx.TimeoutException:
            record.latency_ms = (time.time() - start_time) * 1000
            record.error_type = "timeout"
        except httpx.ConnectError:
            record.latency_ms = (time.time() - start_time) * 1000
            record.error_type = "connection_error"
        except Exception as e:
            record.latency_ms = (time.time() - start_time) * 1000
            record.error_type = type(e).__name__
        
        await self.metrics.record(record)


# =============================================================================
# 测试报告生成器
# =============================================================================

class ReportGenerator:
    """测试报告生成器"""
    
    def __init__(self, config: StressTestConfig, metrics: MetricsCollector):
        self.config = config
        self.metrics = metrics
    
    def generate(self) -> Dict[str, Path]:
        """生成测试报告"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        json_path = self._generate_json_report(timestamp)
        html_path = self._generate_html_report(timestamp)
        
        return {
            "json": json_path,
            "html": html_path
        }
    
    def _generate_json_report(self, timestamp: str) -> Path:
        """生成 JSON 报告"""
        filepath = self.config.report_dir / f"stress_test_report_{timestamp}.json"
        
        total = len(self.metrics.records)
        success = sum(1 for r in self.metrics.records if r.success)
        
        report = {
            "metadata": {
                "timestamp": datetime.now().isoformat(),
                "config": {
                    "concurrent_users": self.config.concurrent_users,
                    "duration_seconds": self.config.duration_seconds,
                    "base_url": self.config.base_url
                }
            },
            "summary": {
                "total_requests": total,
                "successful_requests": success,
                "failed_requests": total - success,
                "success_rate": round(success / total, 4) if total > 0 else 0,
                "avg_rps": round(total / self.config.duration_seconds, 2) if self.config.duration_seconds > 0 else 0
            },
            "latency": self.metrics.get_latency_percentiles(),
            "errors": self.metrics.get_error_breakdown(),
            "request_types": self.metrics.get_request_type_stats(),
            "snapshots": [
                {
                    "timestamp": s.timestamp,
                    "total_requests": s.total_requests,
                    "success_count": s.success_count,
                    "error_count": s.error_count,
                    "active_users": s.active_users,
                    "rps": s.rps,
                    "avg_latency_ms": s.avg_latency_ms
                }
                for s in self.metrics.snapshots
            ]
        }
        
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        
        return filepath
    
    def _generate_html_report(self, timestamp: str) -> Path:
        """生成 HTML 报告"""
        filepath = self.config.report_dir / f"stress_test_report_{timestamp}.html"
        
        total = len(self.metrics.records)
        success = sum(1 for r in self.metrics.records if r.success)
        success_rate = round(success / total * 100, 2) if total > 0 else 0
        
        latency = self.metrics.get_latency_percentiles()
        errors = self.metrics.get_error_breakdown()
        request_types = self.metrics.get_request_type_stats()
        
        # 生成快照数据图表
        snapshots_data = json.dumps([
            {
                "time": i * 5,
                "rps": s.rps,
                "latency": s.avg_latency_ms,
                "active_users": s.active_users
            }
            for i, s in enumerate(self.metrics.snapshots)
        ])
        
        html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>TeachProxy 压力测试报告</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            max-width: 1200px;
            margin: 0 auto;
            padding: 20px;
            background: #f5f5f5;
        }}
        h1, h2 {{
            color: #333;
        }}
        .summary {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 15px;
            margin: 20px 0;
        }}
        .metric-card {{
            background: white;
            padding: 20px;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        .metric-value {{
            font-size: 32px;
            font-weight: bold;
            color: #2563eb;
        }}
        .metric-label {{
            color: #666;
            margin-top: 5px;
        }}
        .success {{ color: #22c55e; }}
        .warning {{ color: #f59e0b; }}
        .error {{ color: #ef4444; }}
        .chart-container {{
            background: white;
            padding: 20px;
            border-radius: 8px;
            margin: 20px 0;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            background: white;
            border-radius: 8px;
            overflow: hidden;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        th, td {{
            padding: 12px;
            text-align: left;
            border-bottom: 1px solid #eee;
        }}
        th {{
            background: #f8f9fa;
            font-weight: 600;
        }}
        .config {{
            background: #f8f9fa;
            padding: 15px;
            border-radius: 8px;
            margin: 20px 0;
        }}
        .config-item {{
            margin: 5px 0;
        }}
    </style>
</head>
<body>
    <h1>🚀 TeachProxy 压力测试报告</h1>
    <p>生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
    
    <div class="config">
        <h3>测试配置</h3>
        <div class="config-item">并发用户数: <strong>{self.config.concurrent_users}</strong></div>
        <div class="config-item">测试时长: <strong>{self.config.duration_seconds} 秒</strong></div>
        <div class="config-item">基础 URL: <strong>{self.config.base_url}</strong></div>
        <div class="config-item">思考时间: <strong>{self.config.min_think_time}-{self.config.max_think_time} 秒</strong></div>
    </div>
    
    <h2>📊 测试摘要</h2>
    <div class="summary">
        <div class="metric-card">
            <div class="metric-value">{total}</div>
            <div class="metric-label">总请求数</div>
        </div>
        <div class="metric-card">
            <div class="metric-value {'success' if success_rate >= 95 else 'warning' if success_rate >= 80 else 'error'}">{success_rate}%</div>
            <div class="metric-label">成功率</div>
        </div>
        <div class="metric-card">
            <div class="metric-value">{round(total / self.config.duration_seconds, 1) if self.config.duration_seconds > 0 else 0}</div>
            <div class="metric-label">平均 RPS</div>
        </div>
        <div class="metric-card">
            <div class="metric-value">{latency.get('p50', 0):.0f}ms</div>
            <div class="metric-label">P50 延迟</div>
        </div>
        <div class="metric-card">
            <div class="metric-value">{latency.get('p95', 0):.0f}ms</div>
            <div class="metric-label">P95 延迟</div>
        </div>
        <div class="metric-card">
            <div class="metric-value">{latency.get('p99', 0):.0f}ms</div>
            <div class="metric-label">P99 延迟</div>
        </div>
    </div>
    
    <h2>📈 性能趋势</h2>
    <div class="chart-container">
        <canvas id="trendChart" height="100"></canvas>
    </div>
    
    <h2>📋 请求类型统计</h2>
    <table>
        <thead>
            <tr>
                <th>请求类型</th>
                <th>请求数</th>
                <th>成功率</th>
                <th>平均延迟</th>
            </tr>
        </thead>
        <tbody>
            {''.join(f"<tr><td>{k}</td><td>{v['requests']}</td><td>{v['success_rate']*100:.1f}%</td><td>{v['avg_latency_ms']:.1f}ms</td></tr>" for k, v in request_types.items())}
        </tbody>
    </table>
    
    <h2>⚠️ 错误分布</h2>
    <table>
        <thead>
            <tr>
                <th>错误类型</th>
                <th>次数</th>
            </tr>
        </thead>
        <tbody>
            {''.join(f"<tr><td>{k}</td><td>{v}</td></tr>" for k, v in errors.items()) if errors else '<tr><td colspan="2">无错误</td></tr>'}
        </tbody>
    </table>
    
    <script>
        const snapshots = {snapshots_data};
        
        new Chart(document.getElementById('trendChart'), {{
            type: 'line',
            data: {{
                labels: snapshots.map(s => s.time + 's'),
                datasets: [{{
                    label: 'RPS',
                    data: snapshots.map(s => s.rps),
                    borderColor: '#2563eb',
                    backgroundColor: 'rgba(37, 99, 235, 0.1)',
                    yAxisID: 'y'
                }}, {{
                    label: '延迟 (ms)',
                    data: snapshots.map(s => s.latency),
                    borderColor: '#f59e0b',
                    backgroundColor: 'rgba(245, 158, 11, 0.1)',
                    yAxisID: 'y1'
                }}, {{
                    label: '活跃用户',
                    data: snapshots.map(s => s.active_users),
                    borderColor: '#22c55e',
                    backgroundColor: 'rgba(34, 197, 94, 0.1)',
                    yAxisID: 'y'
                }}]
            }},
            options: {{
                responsive: true,
                interaction: {{
                    mode: 'index',
                    intersect: false,
                }},
                scales: {{
                    y: {{
                        type: 'linear',
                        display: true,
                        position: 'left',
                        title: {{
                            display: true,
                            text: 'RPS / 用户数'
                        }}
                    }},
                    y1: {{
                        type: 'linear',
                        display: true,
                        position: 'right',
                        title: {{
                            display: true,
                            text: '延迟 (ms)'
                        }},
                        grid: {{
                            drawOnChartArea: false,
                        }},
                    }}
                }}
            }}
        }});
    </script>
</body>
</html>"""
        
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(html)
        
        return filepath


# =============================================================================
# 主测试类
# =============================================================================

class MultiUserStressTest:
    """多用户压力测试"""
    
    def __init__(self, config: Optional[StressTestConfig] = None):
        self.config = config or StressTestConfig()
        self.metrics = MetricsCollector()
        self.users: List[UserSimulator] = []
        self._test_students: List[Student] = []
        self._student_api_keys: List[str] = []
        self._stop_event = asyncio.Event()
    
    async def setup(self) -> None:
        """准备测试数据"""
        print("[准备] 创建测试学生账号...")
        
        # 使用同步数据库操作
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker
        
        engine = create_engine(settings.database_url.replace("+aiosqlite", "").replace("+pysqlite", ""))
        Session = sessionmaker(bind=engine)
        session = Session()
        
        try:
            # 清理旧测试数据
            session.query(Student).filter(Student.id.like("stress_test_%")).delete(synchronize_session=False)
            session.commit()
            
            # 创建测试学生
            students = []
            timestamp = int(time.time())
            
            for i in range(1, self.config.student_count + 1):
                student_id = f"stress_test_{timestamp}_{i:03d}"
                api_key = f"sk-stress-{timestamp}-{i:03d}"
                api_key_hash = hash_api_key(api_key)
                
                student = Student(
                    id=student_id,
                    name=f"Stress Test Student {i}",
                    email=f"stress{i}_{timestamp}@test.com",
                    api_key_hash=api_key_hash,
                    created_at=datetime.now(),
                    current_week_quota=random.randint(10000, 50000),
                    used_quota=0
                )
                students.append((student, api_key))
                session.add(student)
            
            session.commit()
            
            self._test_students = [s[0] for s in students]
            self._student_api_keys = [s[1] for s in students]
            
            print(f"[准备] 创建了 {len(students)} 个测试学生")
            
        finally:
            session.close()
    
    async def teardown(self) -> None:
        """清理测试数据"""
        print("[清理] 删除测试数据...")
        
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker
        
        engine = create_engine(settings.database_url.replace("+aiosqlite", "").replace("+pysqlite", ""))
        Session = sessionmaker(bind=engine)
        session = Session()
        
        try:
            # 删除测试学生的对话记录
            session.query(Conversation).filter(
                Conversation.student_id.like("stress_test_%")
            ).delete(synchronize_session=False)
            
            # 删除测试学生
            session.query(Student).filter(
                Student.id.like("stress_test_%")
            ).delete(synchronize_session=False)
            
            session.commit()
            print("[清理] 测试数据已删除")
            
        finally:
            session.close()
    
    async def _metrics_reporter(self) -> None:
        """定期输出指标报告"""
        while not self._stop_event.is_set():
            await asyncio.sleep(5)
            snapshot = await self.metrics.take_snapshot(len(self.users))
            print(f"[指标] 请求: {snapshot.total_requests} | "
                  f"成功: {snapshot.success_count} | "
                  f"失败: {snapshot.error_count} | "
                  f"RPS: {snapshot.rps:.1f} | "
                  f"延迟: {snapshot.avg_latency_ms:.0f}ms | "
                  f"用户: {snapshot.active_users}")
    
    async def run(self) -> Dict[str, Path]:
        """运行压力测试"""
        print("=" * 60)
        print("🚀 多用户压力测试开始")
        print("=" * 60)
        print(f"并发用户数: {self.config.concurrent_users}")
        print(f"测试时长: {self.config.duration_seconds} 秒")
        print(f"基础 URL: {self.config.base_url}")
        print("=" * 60)
        
        # 准备测试数据
        await self.setup()
        
        # 创建 HTTP 客户端
        limits = httpx.Limits(
            max_connections=200,
            max_keepalive_connections=50
        )
        
        async with httpx.AsyncClient(limits=limits, timeout=30.0) as client:
            # 创建用户模拟器
            for i in range(self.config.concurrent_users):
                user_id = f"user_{i+1:03d}"
                api_key = self._student_api_keys[i % len(self._student_api_keys)]
                user = UserSimulator(
                    user_id=user_id,
                    api_key=api_key,
                    config=self.config,
                    metrics=self.metrics,
                    client=client
                )
                self.users.append(user)
                
                # 渐进式启动
                await asyncio.sleep(self.config.ramp_up_seconds / self.config.concurrent_users)
            
            print(f"[启动] 已创建 {len(self.users)} 个用户模拟器")
            
            # 启动指标报告器
            reporter_task = asyncio.create_task(self._metrics_reporter())
            
            # 启动所有用户
            user_tasks = [asyncio.create_task(user.run()) for user in self.users]
            
            # 等待测试完成
            start_time = time.time()
            try:
                await asyncio.wait_for(
                    asyncio.gather(*user_tasks, return_exceptions=True),
                    timeout=self.config.duration_seconds + 10  # 额外缓冲时间
                )
            except asyncio.TimeoutError:
                print("[超时] 测试时间到达上限")
            
            # 停止指标报告
            self._stop_event.set()
            reporter_task.cancel()
            try:
                await reporter_task
            except asyncio.CancelledError:
                pass
            
            elapsed = time.time() - start_time
            print(f"\n[完成] 测试运行了 {elapsed:.1f} 秒")
        
        # 清理
        await self.teardown()
        
        # 生成报告
        print("\n[报告] 生成测试报告...")
        generator = ReportGenerator(self.config, self.metrics)
        reports = generator.generate()
        
        print(f"[报告] JSON 报告: {reports['json']}")
        print(f"[报告] HTML 报告: {reports['html']}")
        
        # 打印摘要
        self._print_summary()
        
        return reports
    
    def _print_summary(self) -> None:
        """打印测试摘要"""
        total = len(self.metrics.records)
        success = sum(1 for r in self.metrics.records if r.success)
        
        print("\n" + "=" * 60)
        print("📊 测试摘要")
        print("=" * 60)
        print(f"总请求数: {total}")
        print(f"成功请求: {success}")
        print(f"失败请求: {total - success}")
        print(f"成功率: {success/total*100:.2f}%" if total > 0 else "成功率: N/A")
        
        latency = self.metrics.get_latency_percentiles()
        print(f"\n延迟分布:")
        print(f"  P50: {latency['p50']:.1f}ms")
        print(f"  P95: {latency['p95']:.1f}ms")
        print(f"  P99: {latency['p99']:.1f}ms")
        
        errors = self.metrics.get_error_breakdown()
        if errors:
            print(f"\n错误分布:")
            for error_type, count in errors.items():
                print(f"  {error_type}: {count}")
        
        print("=" * 60)


# =============================================================================
# 命令行入口
# =============================================================================

def parse_args() -> argparse.Namespace:
    """解析命令行参数"""
    parser = argparse.ArgumentParser(
        description="TeachProxy 多用户压力测试",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python test_multi_user_stress.py --users 50 --duration 60
  python test_multi_user_stress.py -u 100 -d 300 -b http://localhost:8000
  python test_multi_user_stress.py --users 10 --duration 30 --ramp-up 1.0
        """
    )
    
    parser.add_argument(
        "-u", "--users",
        type=int,
        default=50,
        help="并发用户数 (默认: 50)"
    )
    
    parser.add_argument(
        "-d", "--duration",
        type=int,
        default=60,
        help="测试时长（秒）(默认: 60)"
    )
    
    parser.add_argument(
        "-b", "--base-url",
        type=str,
        default="http://localhost:8000",
        help="网关基础 URL (默认: http://localhost:8000)"
    )
    
    parser.add_argument(
        "-o", "--output",
        type=str,
        default=None,
        help="报告输出目录 (默认: tests/stress/reports)"
    )
    
    parser.add_argument(
        "--ramp-up",
        type=float,
        default=0.5,
        help="用户启动间隔（秒）(默认: 0.5)"
    )
    
    parser.add_argument(
        "--min-think-time",
        type=float,
        default=1.0,
        help="最小思考时间（秒）(默认: 1.0)"
    )
    
    parser.add_argument(
        "--max-think-time",
        type=float,
        default=5.0,
        help="最大思考时间（秒）(默认: 5.0)"
    )
    
    parser.add_argument(
        "--timeout",
        type=float,
        default=30.0,
        help="请求超时时间（秒）(默认: 30.0)"
    )
    
    return parser.parse_args()


async def main() -> int:
    """主函数"""
    args = parse_args()
    
    config = StressTestConfig(
        concurrent_users=args.users,
        duration_seconds=args.duration,
        base_url=args.base_url,
        ramp_up_seconds=args.ramp_up,
        min_think_time=args.min_think_time,
        max_think_time=args.max_think_time,
        request_timeout=args.timeout,
        report_dir=Path(args.output) if args.output else None
    )
    
    test = MultiUserStressTest(config)
    
    try:
        await test.run()
        return 0
    except KeyboardInterrupt:
        print("\n[中断] 测试被用户中断")
        return 130
    except Exception as e:
        print(f"\n[错误] 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
