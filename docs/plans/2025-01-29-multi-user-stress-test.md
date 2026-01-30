# 多用户压力测试实现计划

> **For Kimi CLI:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 为 @gateway/ 创建一个多用户压力测试脚本，模拟多个并发用户同时访问 API，测试系统在高负载下的性能表现。

**Architecture:** 使用 asyncio 实现高并发用户模拟，每个用户模拟真实行为（思考时间、随机请求间隔），通过 MetricsCollector 收集性能指标，最后生成 HTML 和 JSON 格式的详细测试报告。

**Tech Stack:** Python 3.12+, asyncio, httpx, pytest-asyncio, FastAPI TestClient

---

## 任务概览

1. 创建测试数据目录和提示词数据文件
2. 创建多用户压力测试主脚本
3. 创建用户行为模拟器
4. 创建性能指标收集器
5. 创建测试报告生成器
6. 添加命令行参数支持
7. 运行测试并验证

---

## Task 1: 创建测试数据目录和提示词数据文件

**Files:**
- Create: `tests/stress/data/prompts.json`

**Step 1: 创建数据目录**

```bash
mkdir -p tests/stress/data tests/stress/reports
```

**Step 2: 编写提示词数据文件**

内容包含 20+ 条不同类型的测试提示词，覆盖正常对话、规则触发、长文本等场景。

---

## Task 2: 创建多用户压力测试主脚本

**Files:**
- Create: `tests/stress/test_multi_user_stress.py`

**Step 1: 创建基础框架**

主脚本结构：
1. 导入依赖
2. 定义配置类 `StressTestConfig`
3. 定义主测试类 `MultiUserStressTest`
4. 实现测试生命周期方法（setup/run/teardown）
5. 实现命令行参数解析
6. 添加主入口

**Step 2: 添加配置类**

配置项包括：
- 并发用户数
- 测试时长
- 请求间隔范围
- 基础 URL
- 学生数量
- 超时设置

---

## Task 3: 创建用户行为模拟器

**Files:**
- Modify: `tests/stress/test_multi_user_stress.py`

**Step 1: 创建 UserSimulator 类**

用户行为模拟器需要模拟：
- 随机思考时间（1-5秒）
- 随机选择提示词
- 支持流式和非流式请求
- 维护用户对话历史（可选）
- 记录每次请求的结果

**Step 2: 实现请求发送逻辑**

请求类型：
1. 普通聊天请求（70%）
2. 流式聊天请求（20%）
3. 规则触发请求（10%）

**Step 3: 实现错误处理**

记录各种错误类型：
- 网络错误
- 超时错误
- 认证错误
- 配额耗尽错误

---

## Task 4: 创建性能指标收集器

**Files:**
- Modify: `tests/stress/test_multi_user_stress.py`

**Step 1: 创建 MetricsCollector 类**

收集指标：
- 总请求数
- 成功/失败数
- 延迟分布（P50, P95, P99）
- 每秒请求数（RPS）
- 活跃用户数
- 错误类型分布

**Step 2: 实现实时指标快照**

每 5 秒输出一次当前指标快照。

---

## Task 5: 创建测试报告生成器

**Files:**
- Modify: `tests/stress/test_multi_user_stress.py`

**Step 1: 创建 ReportGenerator 类**

生成报告包括：
- 测试摘要（总请求数、成功率、平均延迟）
- 延迟分布直方图数据
- 每秒请求数趋势
- 错误类型分布
- 各用户统计

**Step 2: 实现 HTML 报告生成**

使用内联 CSS 和 Chart.js 生成可视化报告。

**Step 3: 实现 JSON 报告生成**

生成机器可读的 JSON 报告，方便后续分析。

---

## Task 6: 添加命令行参数支持

**Files:**
- Modify: `tests/stress/test_multi_user_stress.py`

**Step 1: 添加 argparse 支持**

参数：
- `--users` / `-u`: 并发用户数（默认: 50）
- `--duration` / `-d`: 测试时长秒数（默认: 60）
- `--base-url` / `-b`: 网关基础 URL（默认: http://localhost:8000）
- `--output` / `-o`: 报告输出目录（默认: tests/stress/reports）
- `--ramp-up`: 用户启动间隔秒数（默认: 0.5）

---

## Task 7: 运行测试并验证

**Step 1: 确保网关服务可运行**

```bash
# 检查是否可以导入
python -c "from gateway.app.main import app; print('OK')"
```

**Step 2: 运行压力测试**

```bash
# 快速测试
python tests/stress/test_multi_user_stress.py --users 10 --duration 30

# 完整测试
python tests/stress/test_multi_user_stress.py --users 100 --duration 300
```

**Step 3: 验证报告生成**

检查报告目录是否包含：
- HTML 报告
- JSON 报告

---

## 执行选项

**Plan complete and saved to `docs/plans/2025-01-29-multi-user-stress-test.md`. Two execution options:**

**1. Subagent-Driven (this session)** - I dispatch fresh subagent per task, review between tasks, fast iteration

**2. Parallel Session (separate)** - Open new session with executing-plans, batch execution with checkpoints

**Which approach?**
