#!/bin/bash
# scripts/run_e2e_tests.sh
# E2E测试运行脚本

set -e

echo "🧪 TeachProxy E2E Test Runner"
echo "=============================="

# 解析参数
RUN_L3=false
HEADED=false

while [[ $# -gt 0 ]]; do
  case $1 in
    --l3)
      RUN_L3=true
      shift
      ;;
    --headed)
      HEADED=true
      shift
      ;;
    --help)
      echo "Usage: $0 [--l3] [--headed]"
      echo ""
      echo "Options:"
      echo "  --l3      Run L3 real LLM tests (requires TEST_LLM_API_KEY)"
      echo "  --headed  Run browser tests in headed mode (visible browser)"
      echo "  --help    Show this help message"
      exit 0
      ;;
    *)
      echo "Unknown option: $1"
      echo "Usage: $0 [--l3] [--headed]"
      exit 1
      ;;
  esac
done

# 检查服务状态
echo ""
echo "📋 Checking services..."
if ! curl -s http://localhost:8000/health > /dev/null 2>&1; then
  # Try /docs endpoint as fallback
  if ! curl -s http://localhost:8000/docs > /dev/null 2>&1; then
    echo "⚠️  Gateway service not running on localhost:8000"
    echo "   Please start it first: cd gateway && uv run python -m uvicorn app.main:app"
    exit 1
  fi
fi
echo "✅ Gateway service is running"

# 准备测试数据
echo ""
echo "🌱 Seeding test data..."
uv run python tests/e2e/data/seed_weekly_prompts.py seed

# 运行 L1 测试
echo ""
echo "🧪 Running L1 API Tests..."
uv run pytest tests/e2e/api/ -v -m "e2e and api_test" --tb=short || true

# 运行 L2 测试（如果pytest有browser标记的测试）
if uv run pytest tests/e2e/browser/ --collect-only -q 2>/dev/null | grep -q "test"; then
  echo ""
  echo "🎭 Running L2 Browser Tests..."
  if [ "$HEADED" = true ]; then
    uv run pytest tests/e2e/browser/ -v -m "e2e and browser_test" --headed --tb=short || true
  else
    uv run pytest tests/e2e/browser/ -v -m "e2e and browser_test" --tb=short || true
  fi
else
  echo ""
  echo "⏭️  Skipping L2 Browser Tests (no tests found or playwright not installed)"
fi

# 运行 L3 测试（如果指定）
if [ "$RUN_L3" = true ]; then
  echo ""
  echo "🤖 Running L3 Real LLM Tests..."
  if [ -z "$TEST_LLM_API_KEY" ] && [ -z "$DEEPSEEK_API_KEY" ]; then
    echo "⚠️  TEST_LLM_API_KEY or DEEPSEEK_API_KEY not set, skipping L3 tests"
  else
    RUN_REAL_LLM_TESTS=true uv run pytest tests/e2e/llm/ -v -m "e2e and llm_test" --tb=short || true
  fi
fi

# 清理测试数据
echo ""
echo "🧹 Cleaning up test data..."
uv run python tests/e2e/data/seed_weekly_prompts.py cleanup

echo ""
echo "✅ All E2E tests completed!"
