# ============================================
# TeachProxy 生产环境 Dockerfile
# 多阶段构建：构建前端 → 构建后端 → 合并运行
# ============================================

# -----------------------------------------
# 阶段 1: 构建前端
# -----------------------------------------
FROM node:20-alpine AS frontend-builder

WORKDIR /app/web

# 复制依赖文件
COPY web/package*.json ./

# 安装依赖
RUN npm ci

# 复制源代码并构建
COPY web/ ./
RUN npm run build

# -----------------------------------------
# 阶段 2: 构建后端
# -----------------------------------------
FROM python:3.12-slim AS backend-builder

WORKDIR /app

# 安装系统依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# 安装 uv
RUN pip install --no-cache-dir uv

# 复制项目文件
COPY pyproject.toml uv.lock ./
COPY gateway/ ./gateway/
COPY admin/ ./admin/

# 安装 Python 依赖
RUN uv pip install --system -e "."

# -----------------------------------------
# 阶段 3: 最终运行镜像
# -----------------------------------------
FROM python:3.12-slim AS production

WORKDIR /app

# 创建非 root 用户
RUN groupadd -r appuser && useradd -r -g appuser appuser

# 安装系统依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# 从 backend-builder 复制 Python 环境
COPY --from=backend-builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=backend-builder /usr/local/bin /usr/local/bin

# 复制应用代码
COPY --chown=appuser:appuser gateway/ ./gateway/
COPY --chown=appuser:appuser admin/ ./admin/

# 复制前端构建产物
COPY --from=frontend-builder --chown=appuser:appuser /app/web/dist ./web/dist

# 设置环境变量
ENV PYTHONPATH=/app
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# 健康检查
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# 切换到非 root 用户
USER appuser

# 暴露端口
EXPOSE 8000

# 启动命令
CMD ["uvicorn", "gateway.app.main:app", "--host", "0.0.0.0", "--port", "8000"]
