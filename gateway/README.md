# TeachProxy Gateway

AI 教学代理网关，提供统一 API 访问多个 AI 提供商，具备限流、配额管理、规则引擎和内容过滤功能。

## 功能特性

- 🤖 **多提供商支持**: DeepSeek、OpenAI，可扩展
- ⚖️ **智能负载均衡**: 轮询、加权、健康优先策略
- 🛡️ **限流保护**: 滑动窗口/Token Bucket，支持内存或 Redis
- 📊 **配额管理**: 按学生、按周的 Token 配额控制
- 📜 **规则引擎**: 基于正则的内容过滤和引导（支持按教学周配置）
- 🔍 **可观测性**: Prometheus 指标、分布式追踪、结构化日志
- 🔄 **故障转移**: 自动检测并切换故障 Provider

## 快速开始

### 安装

```bash
# 基础安装
pip install -e .

# 带 Redis 支持
pip install -e ".[redis]"
```

### 配置

创建 `.env` 文件：

```bash
# 必需配置
DEEPSEEK_API_KEY=your_deepseek_api_key

# 可选配置
OPENAI_API_KEY=your_openai_api_key
DATABASE_URL=sqlite+aiosqlite:///./teachproxy.db
REDIS_ENABLED=false
SEMESTER_START_DATE=2026-02-17
LOG_LEVEL=INFO
```

### 启动

```bash
uvicorn gateway.app.main:app --host 0.0.0.0 --port 8000
```

## API 使用

### 聊天补全

```bash
curl -X POST http://localhost:8000/v1/chat/completions \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "deepseek-chat",
    "messages": [{"role": "user", "content": "Hello!"}],
    "stream": false
  }'
```

### 流式响应

```bash
curl -X POST http://localhost:8000/v1/chat/completions \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "deepseek-chat",
    "messages": [{"role": "user", "content": "Hello!"}],
    "stream": true
  }'
```

### 健康检查

```bash
curl http://localhost:8000/health
```

### Prometheus 指标

```bash
curl http://localhost:8000/metrics
```

## 架构设计

### 请求流程

```
Request → RateLimit → Auth → RuleEngine → QuotaCheck → Provider → Response
                ↓           ↓          ↓          ↓
           限流检查    API Key    内容过滤    配额扣除
```

### 模块说明

| 模块 | 说明 |
|------|------|
| `api/chat.py` | 聊天接口，处理 OpenAI 兼容格式请求 |
| `middleware/rate_limit.py` | 限流中间件，内存/Redis 双后端 |
| `middleware/auth.py` | API Key 认证，SHA256 哈希存储 |
| `services/rule_service.py` | 规则引擎，数据库+缓存+硬编码兜底 |
| `services/quota_cache.py` | 配额缓存，乐观锁更新 |
| `providers/` | AI 提供商抽象和实现 |
| `providers/loadbalancer.py` | 负载均衡，多策略支持 |
| `api/metrics.py` | Prometheus 指标和监控 |

## 规则配置

规则存储在数据库 `rules` 表：

| 字段 | 说明 |
|------|------|
| pattern | 正则表达式 |
| rule_type | block(拦截) / guide(引导) |
| message | 返回给用户的提示 |
| active_weeks | 生效周数，如 "1-2", "3-6" |
| enabled | 是否启用 |

示例规则：
- 第 1-2 周拦截直接要代码的请求
- 第 3-6 周引导简短问题补充背景

## 配额系统

- 每周分配固定 Token 额度
- 使用时先检查缓存，不足再查数据库
- 支持 Redis 分布式配额同步

## 开发

### 运行测试

```bash
pytest tests/ -v
```

### 添加新 Provider

1. 继承 `BaseProvider`:
```python
class NewProvider(BaseProvider):
    async def chat_completion(self, payload, traceparent=None):
        # 实现非流式请求
        pass
    
    async def stream_chat(self, payload, traceparent=None):
        # 实现 SSE 流式请求
        pass
    
    async def health_check(self, timeout=2.0):
        # 实现健康检查
        pass
```

2. 在 `factory.py` 注册:
```python
_PROVIDER_REGISTRY[ProviderType.NEW] = NewProvider
```

## 部署建议

### 单实例部署
- 使用内存限流和缓存
- SQLite 数据库

### 多实例部署
- 启用 Redis (限流 + 配额同步)
- 使用 PostgreSQL 替代 SQLite
- 配置共享的 Redis 缓存

## 环境变量参考

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `DEEPSEEK_API_KEY` | - | DeepSeek API 密钥 |
| `OPENAI_API_KEY` | - | OpenAI API 密钥 |
| `DATABASE_URL` | sqlite+aiosqlite:///./teachproxy.db | 数据库连接 |
| `REDIS_ENABLED` | false | 启用 Redis |
| `REDIS_URL` | redis://localhost:6379/0 | Redis 地址 |
| `RATE_LIMIT_REQUESTS_PER_MINUTE` | 60 | 每分钟请求限制 |
| `SEMESTER_START_DATE` | - | 学期开始日期 |
| `SEMESTER_WEEKS` | 16 | 学期总周数 |
| `LOG_LEVEL` | INFO | 日志级别 |
| `LOG_FORMAT` | text | 日志格式 (text/json) |

## License

MIT
