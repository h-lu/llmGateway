# TeachProxy 压力测试指南 (Locust 版本)

## 安装

```bash
pip install locust
```

## 初始化测试数据

```bash
# 创建 100 个测试学生账号
python tests/stress/locustfile.py --setup --count 100

# 清理测试数据
python tests/stress/locustfile.py --cleanup
```

## 运行测试

### 1. Web UI 模式（推荐）

```bash
locust -f tests/stress/locustfile.py --host=http://localhost:8000
```

浏览器访问 `http://localhost:8089`，可实时调整用户数。

### 2. 无头模式 - 基础负载测试

```bash
# 50用户，30秒
locust -f tests/stress/locustfile.py --headless --users 50 --spawn-rate 5 --run-time 30s

# 100用户，5分钟
locust -f tests/stress/locustfile.py --headless --users 100 --spawn-rate 10 --run-time 5m
```

### 3. Soak Test（浸泡测试）

发现内存泄漏、连接泄漏等渐进性问题：

```bash
locust -f tests/stress/locustfile.py --headless --soak --run-time 1h
```

### 4. Spike Test（尖峰测试）

验证突发流量应对能力：

```bash
locust -f tests/stress/locustfile.py --headless --spike --run-time 5m
```

### 5. Stress Test（压力测试）

逐步加压至系统极限：

```bash
locust -f tests/stress/locustfile.py --headless --stress --run-time 10m
```

### 6. Long Run Test（长时间稳定测试）

长时间固定负载测试，验证系统稳定性。**注意**：使用 `--long` 选项时，必须指定 `--run-time`：

```bash
# 20分钟高强度测试（100用户固定）
locust -f tests/stress/locustfile.py --headless --long --run-time 20m

# 1小时稳定性测试
locust -f tests/stress/locustfile.py --headless --long --run-time 1h
```

### 7. 自定义测试场景

通过 JSON 配置自定义阶段：

```bash
locust -f tests/stress/locustfile.py --headless \
  --shape '[{"duration":60,"users":10},{"duration":120,"users":50},{"duration":180,"users":100}]' \
  --run-time 5m
```

### 7. 生成 HTML 报告

```bash
locust -f tests/stress/locustfile.py --headless \
  --users 100 --spawn-rate 10 --run-time 5m \
  --html reports/locust_report.html
```

### 8. 导出 CSV 数据

```bash
locust -f tests/stress/locustfile.py --headless \
  --users 50 --spawn-rate 5 --run-time 2m \
  --csv reports/stress_test
```

## 测试场景对比

| 测试类型 | 目的 | 典型时长 | 预期发现 |
|---------|------|---------|---------|
| **Load Test** | 验证正常负载性能 | 5-15分钟 | 响应时间、吞吐量基线 |
| **Soak Test** | 长时间稳定性 | 1-24小时 | 内存泄漏、连接耗尽 |
| **Spike Test** | 突发流量应对 | 3-5分钟 | 扩缩容能力、恢复速度 |
| **Stress Test** | 寻找系统极限 | 直到崩溃 | 最大容量、瓶颈点 |
| **Long Run Test** | 固定负载长时间测试 | 20分钟-数小时 | 持续负载下系统表现 |

## 关键指标说明

| 指标 | 说明 | 健康标准 |
|-----|------|---------|
| RPS | 每秒请求数 | 越高越好 |
| Avg Response Time | 平均响应时间 | < 500ms |
| P95 Response Time | 95%请求响应时间 | < 1000ms |
| P99 Response Time | 99%请求响应时间 | < 2000ms |
| Fail Ratio | 失败率 | < 1% |
| Current Users | 当前并发用户 | - |

## 分布式测试

如果单机无法产生足够负载，可以使用多台机器：

```bash
# Master 节点
locust -f tests/stress/locustfile.py --master --host=http://gateway-server

# Worker 节点（在多台机器上运行）
locust -f tests/stress/locustfile.py --worker --master-host=<master-ip>
```

## Docker 运行

```bash
docker run -p 8089:8089 -v $(pwd):/mnt locustio/locust \
  -f /mnt/tests/stress/locustfile.py --host=http://host.docker.internal:8000
```

## CI/CD 集成

```yaml
# .github/workflows/stress-test.yml
name: Stress Test

on: [push, pull_request]

jobs:
  stress:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - name: Install dependencies
        run: pip install locust
      - name: Run stress test
        run: |
          locust -f tests/stress/locustfile.py --headless \
            --users 50 --spawn-rate 5 --run-time 2m \
            --html reports/locust_report.html
      - name: Upload report
        uses: actions/upload-artifact@v2
        with:
          name: locust-report
          path: reports/locust_report.html
```
