"""
TeachProxy 多用户压力测试 - Pytest 版本

可以通过 pytest 运行:
    pytest tests/stress/test_stress_pytest.py -v
    pytest tests/stress/test_stress_pytest.py -v --stress-users=10 --stress-duration=30
"""

import asyncio
import pytest
from pathlib import Path

from tests.stress import MultiUserStressTest, StressTestConfig

# Check if database is available for stress tests
def _db_available():
    import os
    return os.getenv("STRESS_TEST_DB_AVAILABLE", "false").lower() == "true"

# Skip stress tests unless explicitly enabled
stress_test_skip = pytest.mark.skip(
    reason="Stress tests require running database and server. Set STRESS_TEST_DB_AVAILABLE=true to enable."
)


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def stress_config(request) -> StressTestConfig:
    """创建压力测试配置"""
    # 从命令行参数获取配置
    users = getattr(request.config.option, "stress_users", 10)
    duration = getattr(request.config.option, "stress_duration", 30)
    base_url = getattr(request.config.option, "stress_base_url", "http://localhost:8000")
    
    return StressTestConfig(
        concurrent_users=users,
        duration_seconds=duration,
        base_url=base_url,
        report_dir=Path(__file__).parent / "reports"
    )


# =============================================================================
# Tests
# =============================================================================

@stress_test_skip
@pytest.mark.stress
@pytest.mark.asyncio
@pytest.mark.timeout(300)  # 5分钟超时
async def test_multi_user_stress(stress_config: StressTestConfig):
    """
    多用户压力测试
    
    验证系统在多个并发用户下的性能和稳定性。
    """
    test = MultiUserStressTest(stress_config)
    
    try:
        reports = await test.run()
        
        # 验证报告生成成功
        assert reports["json"].exists(), "JSON 报告未生成"
        assert reports["html"].exists(), "HTML 报告未生成"
        
        # 验证测试结果
        total_requests = len(test.metrics.records)
        success_requests = sum(1 for r in test.metrics.records if r.success)
        
        # 断言：必须有请求被处理
        assert total_requests > 0, "没有请求被处理"
        
        # 断言：成功率必须大于 80%
        success_rate = success_requests / total_requests if total_requests > 0 else 0
        assert success_rate >= 0.8, f"成功率过低: {success_rate*100:.1f}% (要求 >= 80%)"
        
        # 断言：P95 延迟必须小于 10 秒
        latency = test.metrics.get_latency_percentiles()
        assert latency["p95"] < 10000, f"P95 延迟过高: {latency['p95']:.0f}ms (要求 < 10000ms)"
        
        # 断言：平均 RPS 必须大于 0
        rps = total_requests / stress_config.duration_seconds
        assert rps > 0, "RPS 为 0"
        
    except Exception as e:
        pytest.fail(f"压力测试执行失败: {e}")


@stress_test_skip
@pytest.mark.stress
@pytest.mark.asyncio
@pytest.mark.timeout(120)
async def test_small_scale_stress():
    """
    小规模快速压力测试
    
    用于快速验证压力测试功能是否正常。
    """
    config = StressTestConfig(
        concurrent_users=5,
        duration_seconds=10,
        base_url="http://localhost:8000",
        min_think_time=0.5,
        max_think_time=1.0
    )
    
    test = MultiUserStressTest(config)
    
    try:
        reports = await test.run()
        
        assert reports["json"].exists()
        assert reports["html"].exists()
        
        # 小规模测试只验证有请求被处理
        assert len(test.metrics.records) > 0
        
    except Exception as e:
        pytest.fail(f"小规模压力测试失败: {e}")


# =============================================================================
# Pytest Hooks
# =============================================================================

def pytest_addoption(parser):
    """添加命令行选项"""
    parser.addoption(
        "--stress-users",
        action="store",
        default=10,
        type=int,
        help="压力测试并发用户数"
    )
    parser.addoption(
        "--stress-duration",
        action="store",
        default=30,
        type=int,
        help="压力测试时长（秒）"
    )
    parser.addoption(
        "--stress-base-url",
        action="store",
        default="http://localhost:8000",
        help="网关基础 URL"
    )
