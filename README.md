# 🤖 TeachProxy - AI 教学代理网关与管理面板

[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.128+-009688.svg)](https://fastapi.tiangolo.com)
[![React](https://img.shields.io/badge/React-19-61DAFB.svg)](https://react.dev)
[![TypeScript](https://img.shields.io/badge/TypeScript-5.9-3178C6.svg)](https://www.typescriptlang.org)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

一个高性能、生产级的 AI API 网关，专为教育场景设计。基于 FastAPI 构建，具备智能路由、速率限制、配额管理、多提供商故障转移和基于规则的内容过滤功能。

[功能特性](#功能特性) • [快速开始](#快速开始) • [API 文档](#api-文档) • [项目结构](#项目结构) • [开发指南](#开发指南)

---

## ✨ 功能特性

### 🔌 智能路由与提供商管理
- **多提供商支持**: DeepSeek、OpenAI、OpenRouter，支持自动故障转移
- **负载均衡策略**: 轮询、加权轮询、健康优先
- **智能路由**: 根据请求类型自动选择最优提供商
- **健康检查**: 自动监控提供商健康状态，故障自动切换

### 🛡️ 访问控制与配额
- **速率限制**: 基于令牌桶算法，支持 Redis 分布式限制
- **配额管理**: 每周学生令牌配额，支持 Redis 缓存和数据库持久化
- **分布式配额**: 多实例部署时的配额同步

### 🔍 内容安全
- **规则引擎**: 基于正则的内容过滤系统
- **内容分类**: 自动识别问题类型（概念题/编程题/一般问题）
- **智能引导**: 对敏感内容进行引导而非直接拦截

### 📊 可观测性
- **结构化日志**: JSON 格式日志，支持日志级别动态调整
- **链路追踪**: OpenTelemetry 集成
- **指标监控**: 请求量、延迟、错误率等关键指标
- **健康检查**: 数据库、缓存、提供商状态统一监控

### 🎨 管理面板
- **现代化 UI**: React 19 + TypeScript + TailwindCSS
- **实时数据**: 学生管理、对话查看、规则配置
- **仪表盘**: 实时指标和统计信息

### ⚡ 高性能
- **异步架构**: 全异步 I/O，高并发支持
- **连接池**: 数据库和 HTTP 客户端连接池
- **多级缓存**: 内存缓存 + Redis 缓存
- **GC 优化**: 请求期间禁用 GC，减少延迟抖动

---

## 🚀 快速开始

### 环境要求

- Python >= 3.12
- Node.js >= 18 (前端开发)
- PostgreSQL >= 14 (数据库)
- Redis >= 6 (可选，用于分布式缓存)

### 1. 克隆仓库

```bash
git clone <repository-url>
cd teachproxy
```

### 2. 安装依赖

**后端依赖:**
```bash
# 使用 uv (推荐)
uv pip install -e ".[dev]"

# 或使用 pip
pip install -e ".[dev]"
```

**前端依赖:**
```bash
cd web
npm install
cd ..
```

### 3. 配置环境变量

```bash
# 复制示例配置文件
cp .env.example .env

# 编辑 .env 文件，配置以下必需项:
# - DATABASE_URL: PostgreSQL 连接字符串
# - DEEPSEEK_API_KEY: DeepSeek API 密钥
# - ADMIN_TOKEN: 管理员认证令牌
```

**最小配置示例 (.env):**
```env
# 数据库
DATABASE_URL=postgresql+asyncpg://teachproxy:teachproxy123@localhost:5432/teachproxy

# AI 提供商
DEEPSEEK_API_KEY=sk-your-deepseek-api-key

# 管理员认证
ADMIN_TOKEN=your-secure-admin-token
```

### 4. 初始化数据库

```bash
# 创建数据库 (使用 psql 或任意 PostgreSQL 客户端)
createdb teachproxy

# 应用启动时会自动创建表结构
```

### 5. 启动服务

**终端 1 - 启动网关服务:**
```bash
# 开发模式 (热重载)
uvicorn gateway.app.main:app --reload --host 0.0.0.0 --port 8000

# 生产模式
# uvicorn gateway.app.main:app --host 0.0.0.0 --port 8000 --workers 4
```

**终端 2 - 启动管理面板:**
```bash
cd web
npm run dev
```

### 6. 验证安装

- **网关服务**: http://localhost:8000/health
- **API 文档**: http://localhost:8000/docs (Swagger UI)
- **管理面板**: http://localhost:5173

---

## 📚 API 文档

启动服务后，可通过以下端点访问 API 文档:

- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

### 核心端点

| 方法 | 端点 | 描述 | 认证 |
|------|------|------|------|
| `POST` | `/v1/chat/completions` | 聊天补全 (OpenAI 兼容) | API Key |
| `GET` | `/v1/models` | 列出可用模型 | API Key |
| `GET` | `/health` | 健康检查 | 公开 |
| `GET` | `/metrics` | Prometheus 指标 | 公开 |

### 管理端点 (Admin)

| 方法 | 端点 | 描述 |
|------|------|------|
| `GET` | `/admin/students` | 列出所有学生 |
| `POST` | `/admin/students` | 创建学生 |
| `GET` | `/admin/students/{id}` | 获取学生详情 |
| `PUT` | `/admin/students/{id}` | 更新学生 |
| `DELETE` | `/admin/students/{id}` | 删除学生 |
| `GET` | `/admin/rules` | 列出所有规则 |
| `POST` | `/admin/rules` | 创建规则 |
| `GET` | `/admin/conversations` | 列出对话历史 |
| `GET` | `/admin/dashboard` | 仪表盘数据 |
| `GET` | `/admin/weekly-prompts` | 每周提示词管理 |

### 聊天补全示例

```bash
curl -X POST http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer student-api-key" \
  -d '{
    "model": "deepseek-chat",
    "messages": [
      {"role": "user", "content": "你好，请介绍一下自己"}
    ],
    "stream": true
  }'
```

---

## 🏗️ 项目结构

```
teachproxy/
├── 📁 gateway/                 # FastAPI 网关服务
│   ├── 📁 app/
│   │   ├── 📁 api/            # API 路由
│   │   │   ├── chat.py        # 聊天补全端点
│   │   │   ├── admin/         # 管理后台 API
│   │   │   ├── metrics.py     # 指标收集
│   │   │   └── weekly_prompts.py
│   │   ├── 📁 core/           # 核心配置
│   │   │   ├── config.py      # 应用配置 (Pydantic Settings)
│   │   │   ├── logging.py     # 结构化日志
│   │   │   ├── cache.py       # 缓存抽象
│   │   │   └── security.py    # 安全工具
│   │   ├── 📁 db/             # 数据库层
│   │   │   ├── models.py      # SQLAlchemy 模型
│   │   │   ├── crud/          # CRUD 操作
│   │   │   └── async_session.py
│   │   ├── 📁 middleware/     # 中间件
│   │   │   ├── auth.py        # 认证中间件
│   │   │   ├── rate_limit/    # 限流中间件
│   │   │   └── request_id.py  # 请求追踪
│   │   ├── 📁 providers/      # AI 提供商
│   │   │   ├── base.py        # 提供商基类
│   │   │   ├── deepseek.py    # DeepSeek 实现
│   │   │   ├── openai.py      # OpenAI 实现
│   │   │   ├── factory.py     # 提供商工厂
│   │   │   └── loadbalancer.py
│   │   └── 📁 services/       # 业务服务
│   │       ├── rule_service/  # 规则引擎
│   │       ├── distributed_quota/  # 分布式配额
│   │       ├── smart_router.py
│   │       └── llm_cache.py
│   └── main.py                # 应用入口
│
├── 📁 web/                     # React 管理面板
│   ├── 📁 src/
│   │   ├── 📁 components/     # UI 组件
│   │   ├── 📁 pages/          # 页面组件
│   │   ├── 📁 hooks/          # 自定义 Hooks
│   │   ├── 📁 providers/      # Context Providers
│   │   ├── 📁 lib/            # 工具函数
│   │   └── 📁 types/          # TypeScript 类型
│   ├── package.json
│   └── vite.config.ts
│
├── 📁 admin/                   # 数据库工具
├── 📁 tests/                   # 测试用例
│   ├── 📁 e2e/                # E2E 测试
│   └── 📁 stress/             # 压力测试
├── 📁 scripts/                 # 脚本工具
├── 📁 docs/                    # 文档
├── pyproject.toml             # Python 项目配置
└── .env.example               # 环境变量示例
```

---

## 🛠️ 开发指南

### 代码规范

本项目使用以下工具保证代码质量:

**Python (后端):**
```bash
# 格式化代码
ruff format gateway/ admin/

# 代码检查
ruff check gateway/ admin/
ruff check gateway/ admin/ --fix  # 自动修复

# 类型检查
mypy gateway/ admin/
```

**TypeScript/React (前端):**
```bash
cd web

# 代码检查
npm run lint

# 类型检查
npx tsc --noEmit

# 格式化
npx prettier --write src/
```

### 提交规范

所有提交必须遵循 [Conventional Commits](https://www.conventionalcommits.org/) 规范:

```bash
# 格式: <type>(<scope>): <description>

git commit -m "feat(auth): 添加 JWT 认证支持"
git commit -m "fix(api): 修复配额计算错误"
git commit -m "refactor(db): 优化查询性能"
git commit -m "docs(readme): 更新部署说明"
git commit -m "test(quota): 添加配额缓存测试"
```

**类型说明:**
- `feat`: 新功能
- `fix`: Bug 修复
- `docs`: 文档更新
- `style`: 代码格式
- `refactor`: 代码重构
- `test`: 测试相关
- `chore`: 构建/依赖更新

### 测试

**单元测试:**
```bash
# 运行所有单元测试
pytest tests/ -m "not e2e" -v

# 带覆盖率报告
pytest tests/ -m "not e2e" --cov=gateway --cov-report=html

# 运行特定测试
pytest tests/test_chat_flow.py -v
```

**E2E 测试:**
```bash
# 安装 E2E 依赖
uv pip install -e ".[e2e]"
playwright install chromium

# 运行 E2E 测试
./scripts/run_e2e_tests.sh

# 运行真实 LLM 测试 (需要 API Key)
export TEST_LLM_API_KEY="your-deepseek-key"
./scripts/run_e2e_tests.sh --l3
```

**前端测试:**
```bash
cd web
npm run test
npm run test:watch
```

### 本地开发流程

```bash
# 1. 创建功能分支
git checkout -b feature/your-feature

# 2. 开发代码...

# 3. 运行代码检查
ruff format gateway/ && ruff check gateway/ && mypy gateway/

# 4. 运行测试
pytest tests/ -m "not e2e" -v

# 5. 提交代码
git add .
git commit -m "feat(scope): 描述"

# 6. 推送到远程并创建 PR
git push -u origin feature/your-feature
gh pr create --title "feat: xxx" --body "描述"
```

---

## ⚙️ 配置详解

### 数据库配置

```env
# PostgreSQL (推荐用于生产)
DATABASE_URL=postgresql+asyncpg://user:pass@host:5432/dbname

# 连接池配置
DB_POOL_SIZE=100
DB_MAX_OVERFLOW=50
DB_POOL_TIMEOUT=30
DB_POOL_RECYCLE=300
```

### AI 提供商配置

```env
# DeepSeek (主提供商)
DEEPSEEK_API_KEY=sk-your-key
DEEPSEEK_BASE_URL=https://api.deepseek.com/v1

# OpenAI (备用)
OPENAI_API_KEY=sk-your-key
OPENAI_BASE_URL=https://api.openai.com/v1

# OpenRouter (备用)
TEACHER_OPENROUTER_API_KEY=sk-your-key
TEACHER_OPENROUTER_BASE_URL=https://openrouter.ai/api/v1
```

### 缓存配置

```env
# Redis (推荐用于生产)
REDIS_ENABLED=true
REDIS_URL=redis://localhost:6379/0

# 内存缓存 (开发/测试)
CACHE_ENABLED=true
CACHE_DEFAULT_TTL=300
```

### 限流配置

```env
RATE_LIMIT_REQUESTS_PER_MINUTE=60
RATE_LIMIT_BURST_SIZE=10
RATE_LIMIT_WINDOW_SECONDS=60
RATE_LIMIT_FAIL_CLOSED=false  # Redis 故障时是否拒绝请求
```

### 学期配置

```env
# 学期开始日期 (用于计算当前是第几周)
SEMESTER_START_DATE=2026-02-17
SEMESTER_WEEKS=16
```

---

## 📄 许可证

本项目基于 [MIT](LICENSE) 许可证开源。

---

## 🤝 贡献

欢迎提交 Issue 和 Pull Request!

1. Fork 本仓库
2. 创建功能分支 (`git checkout -b feature/amazing-feature`)
3. 提交更改 (`git commit -m 'feat: add amazing feature'`)
4. 推送分支 (`git push origin feature/amazing-feature`)
5. 创建 Pull Request

---

## 📞 支持

如有问题，请通过以下方式联系:

- 提交 [GitHub Issue](../../issues)
- 查看 [API 文档](http://localhost:8000/docs) (本地启动后)

---

<p align="center">Made with ❤️ for AI Education</p>

