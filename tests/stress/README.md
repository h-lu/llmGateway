# TeachProxy 多用户压力测试

## 简介

多用户压力测试模块用于模拟多个并发用户同时访问 TeachProxy 网关 API，测试系统在高负载下的性能表现。

## 特性

- **高并发模拟**: 支持模拟 10-1000+ 并发用户
- **真实行为模拟**: 随机思考时间、渐进式用户启动
- **多种请求类型**: 普通聊天、流式响应、规则触发
- **实时指标**: RPS、延迟分布、成功率、错误类型
- **可视化报告**: HTML 报告（Chart.js 图表）+ JSON 报告

## 快速开始

### 1. 命令行运行

```bash
# 快速测试（10 用户，30 秒）
python tests/stress/test_multi_user_stress.py --users 10 --duration 30

# 完整测试（50 用户，5 分钟）
python tests/stress/test_multi_user_stress.py --users 50 --duration 300

# 高负载测试（100 用户，10 分钟）
python tests/stress/test_multi_user_stress.py --users 100 --duration 600
```

### 2. Pytest 运行

```bash
# 默认参数
pytest tests/stress/test_stress_pytest.py -v

# 自定义参数
pytest tests/stress/test_stress_pytest.py -v \
    --stress-users=50 \
    --stress-duration=60 \
    --stress-base-url=http://localhost:8000

# 只运行压力测试
pytest tests/stress/ -v -m stress
```

### 3. Python API

```python
import asyncio
from tests.stress import MultiUserStressTest, StressTestConfig

async def main():
    config = StressTestConfig(
        concurrent_users=50,
        duration_seconds=60,
        base_url="http://localhost:8000"
    )
    
    test = MultiUserStressTest(config)
    reports = await test.run()
    
    print(f"JSON 报告: {reports['json']}")
    print(f"HTML 报告: {reports['html']}")

asyncio.run(main())
```

## 命令行参数

| 参数 | 简写 | 默认值 | 说明 |
|------|------|--------|------|
| `--users` | `-u` | 50 | 并发用户数 |
| `--duration` | `-d` | 60 | 测试时长（秒） |
| `--base-url` | `-b` | http://localhost:8000 | 网关基础 URL |
| `--output` | `-o` | tests/stress/reports | 报告输出目录 |
| `--ramp-up` | - | 0.5 | 用户启动间隔（秒） |
| `--min-think-time` | - | 1.0 | 最小思考时间（秒） |
| `--max-think-time` | - | 5.0 | 最大思考时间（秒） |
| `--timeout` | - | 30.0 | 请求超时时间（秒） |

## 测试场景

压力测试模拟以下请求类型：

1. **普通聊天** (70%): 正常对话请求
2. **流式聊天** (20%): 流式响应请求
3. **规则触发** (10%): 触发规则引擎的请求

## 报告内容

测试完成后会生成两份报告：

### HTML 报告

- 测试摘要（总请求数、成功率、RPS）
- 延迟分布（P50、P95、P99）
- 性能趋势图（RPS、延迟、活跃用户）
- 请求类型统计
- 错误分布

### JSON 报告

包含详细的机器可读数据，方便后续分析和集成。

## 性能指标

测试收集以下指标：

- **总请求数**: 测试期间发送的所有请求
- **成功率**: 成功请求占总请求的百分比
- **RPS**: 每秒请求数
- **延迟分布**: P50、P95、P99 延迟
- **错误类型**: 超时、连接错误、HTTP 错误等

## 测试数据

测试数据位于 `tests/stress/data/` 目录：

- `prompts.json`: 测试提示词（正常对话、规则触发、长文本）

## 注意事项

1. **确保网关服务已启动**: 测试前需要确保网关服务在指定 URL 上运行
2. **数据库**: 测试会创建临时学生账号，测试结束后自动清理
3. **资源**: 高并发测试可能消耗较多系统资源
4. **网络**: 确保网络连接稳定，避免网络波动影响测试结果

## 故障排除

### 连接错误

```
error_type: connection_error
```

- 检查网关服务是否运行
- 检查 `--base-url` 参数是否正确

### 超时错误

```
error_type: timeout
```

- 增加 `--timeout` 参数值
- 检查网关服务响应时间

### 成功率过低

- 检查网关服务日志
- 减少 `--users` 数量
- 增加 `--duration` 时间
