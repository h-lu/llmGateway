#!/bin/sh
set -e

# 创建静态文件目录并复制前端文件（以 root 身份）
mkdir -p /app/static
cp -r /app/web/dist/* /app/static/
chown -R appuser:appuser /app/static

# 切换到非 root 用户并启动应用
exec gosu appuser uvicorn gateway.app.main:app --host 0.0.0.0 --port 8000