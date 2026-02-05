# TeachProxy - AI 教学代理网关与管理面板

一个高性能的 AI API 网关，基于 FastAPI 构建，具备速率限制、配额管理、多提供商支持和基于规则的内容过滤功能。

## 功能特性

- **多提供商支持**: DeepSeek、OpenAI 和 Mock 提供商，支持自动故障转移
- **负载均衡**: 轮询、加权轮询和健康优先策略
- **速率限制**: 基于令牌桶算法，支持 Redis 分布式限制
- **配额管理**: 每周学生令牌配额，支持 Redis 缓存
- **内容过滤**: 基于正则的规则引擎，用于拦截和引导内容
- **健康检查**: 自动提供商健康监控与恢复
- **可观测性**: 结构化日志、指标和 OpenTelemetry 链路追踪
- **高性能**: 连接池、异步操作和预热启动
- **管理面板**: 基于 React 18 + TypeScript + Vite 的现代化管理界面

## 快速开始

### 安装

```bash
# 克隆仓库
git clone <repository-url>
cd teachproxy

# 安装依赖
uv pip install -e ".[dev]"
```

### 配置

创建 `.env` 文件：

```bash
# 复制示例配置
cp .env.example .env

# 编辑 .env 文件，配置数据库和 API 密钥
```

### 运行

**启动网关服务：**

```bash
# 开发模式
uvicorn gateway.app.main:app --reload --host 0.0.0.0 --port 8000

# 生产模式
uvicorn gateway.app.main:app --host 0.0.0.0 --port 8000 --workers 4
```

**启动管理面板（前端）：**

```bash
cd web
npm install
npm run dev
```
前端运行在 http://localhost:5173

## 项目结构

```
.
├── gateway/              # FastAPI 网关服务
│   ├── app/
│   │   ├── api/          # API 端点
│   │   ├── core/         # 配置、日志、安全
│   │   ├── db/           # 数据库模型和操作
│   │   ├── middleware/   # 认证、限流中间件
│   │   ├── providers/    # AI 提供商实现
│   │   └── services/     # 业务逻辑
│   └── ...
├── web/                  # React 管理面板
│   ├── src/              # 源代码
│   └── package.json      # 依赖配置
├── admin/                # 数据库工具模块
│   └── db_utils_v2.py    # 数据库操作工具
├── tests/                # 测试用例
└── docs/                 # 文档
```

## API 文档

启动服务后，可通过以下地址访问 API 文档：

- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

### 主要端点

| 端点 | 描述 |
|------|------|
| `POST /v1/chat/completions` | 聊天补全 |
| `GET /v1/models` | 列出可用模型 |
| `GET /health` | 健康检查 |
| `GET /metrics` | 指标数据 |

## 测试

```bash
# 运行所有测试
pytest

# 带覆盖率报告
pytest --cov=gateway --cov-report=html

# 运行特定测试文件
pytest tests/test_docs.py -v
```

## 开发

```bash
# 代码格式化
ruff format gateway/ admin/
npx prettier --write web/src/

# 代码检查
ruff check gateway/ admin/
npx eslint web/src/

# 类型检查
mypy gateway/ admin/
cd web && npx tsc --noEmit
```

## 许可证

MIT
