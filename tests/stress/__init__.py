"""TeachProxy 压力测试模块

提供多用户并发压力测试功能，用于测试网关在高负载下的性能表现。

Usage:
    # 命令行运行
    python tests/stress/test_multi_user_stress.py --users 50 --duration 60
    
    # Pytest 运行
    pytest tests/stress/test_stress_pytest.py -v --stress-users=10 --stress-duration=30
    
    # 作为模块导入
    from tests.stress import MultiUserStressTest, StressTestConfig
    
    config = StressTestConfig(concurrent_users=50, duration_seconds=60)
    test = MultiUserStressTest(config)
    reports = await test.run()
"""

from .test_multi_user_stress import (
    MultiUserStressTest,
    StressTestConfig,
    UserSimulator,
    MetricsCollector,
    ReportGenerator,
    RequestRecord,
    MetricsSnapshot,
)

__all__ = [
    "MultiUserStressTest",
    "StressTestConfig", 
    "UserSimulator",
    "MetricsCollector",
    "ReportGenerator",
    "RequestRecord",
    "MetricsSnapshot",
]
