# E2E Tests for TeachProxy

## 测试架构 (三层)

```
┌─────────────────────────────────────────────────────────────────┐
│ L3: Real LLM Tests (tests/e2e/llm/)                             │
│    - 验证提示词确实改变AI行为                                      │
│    - 需要设置 RUN_REAL_LLM_TESTS=true                            │
│    - 会产生真实的API调用费用                                       │
├─────────────────────────────────────────────────────────────────┤
│ L2: Browser Tests (tests/e2e/browser/)                          │
│    - Playwright驱动的浏览器自动化测试                              │
│    - 验证管理员和学生完整操作流程                                  │
├─────────────────────────────────────────────────────────────────┤
│ L1: API Tests (tests/e2e/api/)                                  │
│    - 直接调用后端API                                              │
│    - Mock LLM提供商                                               │
│    - 快速、稳定、适合CI                                           │
└─────────────────────────────────────────────────────────────────┘
```

## 快速开始

### 1. 安装依赖

```bash
# 安装E2E测试依赖
uv pip install -e ".[e2e]"

# 安装Playwright浏览器（用于L2测试）
playwright install chromium
```

### 2. 启动服务

```bash
# 启动Gateway服务
cd gateway && uv run python -m uvicorn app.main:app --reload

# 启动前端（可选，用于L2测试）
cd web && npm run dev
```

### 3. 运行测试

```bash
# 运行所有E2E测试（推荐）
./scripts/run_e2e_tests.sh

# 运行包含真实LLM的测试（需要API Key）
export TEST_LLM_API_KEY="your-deepseek-key"
./scripts/run_e2e_tests.sh --l3

# 浏览器测试可见模式
./scripts/run_e2e_tests.sh --headed
```

## 测试场景覆盖

| 场景 | 层级 | 文件 | 验证内容 |
|------|------|------|---------|
| **场景1: 基础注入** | L1 | `test_weekly_prompt_injection.py` | 请求中包含正确的system prompt |
| **场景2: 多轮对话** | L1 | `test_multi_turn_conversation.py` | 上下文保持一致 |
| **场景3: 周切换** | L1/L2 | `test_week_transition.py` + UI | 不同周使用不同提示词 |
| **场景4: 边界周** | L1 | `test_boundary_weeks.py` | 第1周、最后一周、无配置周 |
| **场景5: 并发学生** | L1 | `test_concurrent_students.py` | 缓存隔离、无串扰 |
| **L3: 真实LLM** | L3 | `test_real_llm_behavior.py` | 提示词改变AI回复风格 |

## 单独运行测试

```bash
# L1 API测试
uv run pytest tests/e2e/api/ -v -m "e2e and api_test"

# L2 Browser测试
uv run pytest tests/e2e/browser/ -v -m "e2e and browser_test"

# L3 Real LLM测试
export RUN_REAL_LLM_TESTS=true
export TEST_LLM_API_KEY="your-key"
uv run pytest tests/e2e/llm/ -v -m "e2e and llm_test"
```

## 数据准备

```bash
# 注入测试数据（4周的提示词）
uv run python tests/e2e/data/seed_weekly_prompts.py seed

# 查看当前提示词
uv run python tests/e2e/data/seed_weekly_prompts.py list

# 清理测试数据
uv run python tests/e2e/data/seed_weekly_prompts.py cleanup
```

## 测试数据说明

测试数据包含4周的提示词：

| 周次 | 风格 | 描述 |
|------|------|------|
| 第1周 | 理论导向 | 解释概念、使用比喻 |
| 第2周 | 苏格拉底式 | 用提问引导，不直接给答案 |
| 第3周 | 实践导向 | 提供代码示例和练习 |
| 第4周 | 项目导向 | 引导完成小项目 |

## 环境变量

| 变量 | 说明 | 必需 |
|------|------|------|
| `TEST_LLM_API_KEY` | DeepSeek API Key（用于L3测试） | L3测试时 |
| `DEEPSEEK_API_KEY` | 替代TEST_LLM_API_KEY | L3测试时 |
| `RUN_REAL_LLM_TESTS` | 设置为`true`启用L3测试 | L3测试时 |
| `TEST_LLM_MODEL` | 模型名称（默认deepseek-chat） | 否 |

## 故障排除

### 服务未运行
```
⚠️  Gateway service not running on localhost:8000
```
解决：启动服务 `cd gateway && uv run python -m uvicorn app.main:app`

### Playwright未安装
```
browser_type.launch: Executable doesn't exist
```
解决：运行 `playwright install chromium`

### API Key未设置
```
⚠️  TEST_LLM_API_KEY not set, skipping L3 tests
```
解决：设置环境变量 `export TEST_LLM_API_KEY="your-key"`

## 编写新测试

参考现有测试文件，遵循以下约定：

1. **标记**: 使用 `@e2e` 和层级标记 (`@api_test`, `@browser_test`, `@llm_test`)
2. **命名**: 测试函数以 `test_` 开头，描述性强
3. **Fixtures**: 使用 `http_client`, `test_student_credentials` 等共享fixtures
4. **清理**: 测试结束后清理创建的数据

示例：

```python
import pytest

e2e = pytest.mark.e2e
api_test = pytest.mark.api_test

@e2e
@api_test
async def test_my_new_feature(http_client, test_student_credentials):
    headers = {"Authorization": f"Bearer {test_student_credentials['api_key']}"}
    response = await http_client.post("/v1/chat/completions", ...)
    assert response.status_code == 200
```

## CI/CD 集成

在GitHub Actions中运行E2E测试：

```yaml
- name: Run E2E Tests
  run: |
    ./scripts/run_e2e_tests.sh
  env:
    TEST_LLM_API_KEY: ${{ secrets.TEST_LLM_API_KEY }}
```

注意：L3真实LLM测试建议在定时任务（如每周）而非每次PR时运行，以控制成本。
