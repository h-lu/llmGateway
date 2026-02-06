#!/bin/sh
set -e

# 创建静态文件目录（如果不存在）
mkdir -p /app/static

# 复制前端构建产物到静态目录
cp -r /app/web/dist/* /app/static/

# 启动应用
exec uvicorn gateway.app.main:app --host 0.0.0.0 --port 8000