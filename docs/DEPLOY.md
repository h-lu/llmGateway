# 🚀 TeachProxy 部署指南

本文档介绍如何使用 Docker 部署 TeachProxy 到 VPS 服务器。

## 📋 目录

- [环境要求](#环境要求)
- [快速部署](#快速部署)
- [手动部署](#手动部署)
- [GitHub Actions 自动部署](#github-actions-自动部署)
- [SSL 证书配置](#ssl-证书配置)
- [运维管理](#运维管理)
- [故障排查](#故障排查)

---

## 🖥️ 环境要求

### 服务器配置

| 配置项 | 最低要求 | 推荐配置 |
|--------|---------|---------|
| CPU | 2 核 | 4 核+ |
| 内存 | 4 GB | 8 GB+ |
| 磁盘 | 20 GB SSD | 50 GB SSD |
| 带宽 | 5 Mbps | 10 Mbps+ |
| 系统 | Ubuntu 22.04 LTS | Ubuntu 24.04 LTS |

### 软件依赖

- Docker >= 24.0
- Docker Compose >= 2.0
- Git
- curl

### 域名

- 一个已解析到服务器的域名（用于 SSL 证书）
- 可选：通配符域名支持

---

## ⚡ 快速部署

### 1. 服务器初始化

```bash
# 连接到你的 VPS
ssh ubuntu@your-server-ip

# 更新系统
sudo apt update && sudo apt upgrade -y

# 安装 Docker
 curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER
newgrp docker

# 安装 Docker Compose
sudo apt install -y docker-compose-plugin

# 验证安装
docker --version
docker compose version
```

### 2. 克隆项目

```bash
cd ~
git clone https://github.com/h-lu/llmGateway.git teachproxy
cd teachproxy
```

### 3. 配置环境变量

```bash
# 复制生产环境配置
cp .env.production .env

# 编辑配置
nano .env
```

**必需修改的配置项：**

```env
# 数据库密码（生产环境必须修改）
DB_PASSWORD=your-secure-password

# DeepSeek API Key
DEEPSEEK_API_KEY=sk-your-deepseek-key

# 管理员令牌（设置强密码）
ADMIN_TOKEN=your-secure-admin-token

# API Key 加密密钥（生成命令：python -c "import secrets; print(secrets.token_urlsafe(32))"）
API_KEY_ENCRYPTION_KEY=your-32-byte-encryption-key

# 学期开始日期
SEMESTER_START_DATE=2026-02-17
```

### 4. 设置域名（可选，用于 HTTPS）

```bash
export DOMAIN=your-domain.com
```

### 5. 执行部署

```bash
# 使用部署脚本
./scripts/deploy.sh
```

部署完成后，访问：
- 应用：https://your-domain.com （如果设置了 DOMAIN）
- API 文档：https://your-domain.com/docs
- 直接访问：http://your-server-ip

---

## 🔧 手动部署

如果你不想使用脚本，可以手动执行以下步骤：

### 1. 创建部署目录

```bash
mkdir -p ~/teachproxy
cd ~/teachproxy
```

### 2. 复制文件

```bash
# 从项目目录复制
cp /path/to/project/docker-compose.yml ./
cp /path/to/project/Dockerfile ./
cp -r /path/to/project/nginx ./
cp /path/to/project/.env.production ./.env

# 编辑 .env 文件
nano .env
```

### 3. 生成 Nginx 配置

```bash
# 如果有域名
export DOMAIN=your-domain.com
envsubst '\${DOMAIN}' < nginx/conf.d/app.conf.template > nginx/conf.d/app.conf

# 如果没有域名，使用默认配置
cp nginx/conf.d/default.conf nginx/conf.d/app.conf
```

### 4. 启动服务

```bash
# 构建镜像
docker-compose build

# 启动服务
docker-compose up -d

# 查看状态
docker-compose ps
```

### 5. 初始化 SSL（需要域名）

```bash
# 确保 nginx 已启动
docker-compose up -d nginx

# 申请证书
docker-compose run --rm certbot certonly \
    --webroot \
    --webroot-path=/var/www/certbot \
    --email admin@your-domain.com \
    --agree-tos \
    --no-eff-email \
    -d your-domain.com

# 重启 nginx
docker-compose restart nginx
```

---

## 🔄 GitHub Actions 自动部署

配置 GitHub Actions 实现代码推送后自动部署。

### 1. 配置 GitHub Secrets

在 GitHub 仓库的 Settings → Secrets and variables → Actions 中添加以下 secrets：

| Secret Name | 说明 | 示例 |
|------------|------|------|
| `SSH_HOST` | 服务器 IP | `1.2.3.4` |
| `SSH_USER` | SSH 用户名 | `ubuntu` |
| `SSH_PORT` | SSH 端口 | `22` |
| `SSH_PRIVATE_KEY` | SSH 私钥 | `-----BEGIN OPENSSH PRIVATE KEY-----...` |
| `DOMAIN` | 域名 | `api.teachproxy.com` |
| `DB_USER` | 数据库用户 | `teachproxy` |
| `DB_PASSWORD` | 数据库密码 | `secure-password` |
| `DB_NAME` | 数据库名 | `teachproxy` |
| `DEEPSEEK_API_KEY` | DeepSeek API Key | `sk-...` |
| `ADMIN_TOKEN` | 管理员令牌 | `secure-token` |
| `API_KEY_ENCRYPTION_KEY` | 加密密钥 | `...` |

### 2. 配置 SSH 密钥

在服务器上生成部署专用密钥：

```bash
# 在服务器上生成密钥对
ssh-keygen -t ed25519 -C "deploy@github" -f ~/.ssh/deploy_key

# 添加公钥到 authorized_keys
cat ~/.ssh/deploy_key.pub >> ~/.ssh/authorized_keys

# 查看私钥（复制到 GitHub Secrets）
cat ~/.ssh/deploy_key
```

### 3. 触发部署

配置完成后，每次推送代码到 `main` 分支会自动触发部署：

```bash
git add .
git commit -m "feat: some feature"
git push origin main
```

在 GitHub Actions 页面可以查看部署进度。

---

## 🔒 SSL 证书配置

### 自动续期

部署配置已包含 Certbot 自动续期，无需手动操作。

### 手动申请证书

```bash
cd ~/teachproxy

# 申请证书
docker-compose run --rm certbot certonly \
    --webroot \
    --webroot-path=/var/www/certbot \
    --email your-email@example.com \
    --agree-tos \
    --no-eff-email \
    -d your-domain.com

# 重启 nginx
docker-compose restart nginx
```

### 查看证书状态

```bash
# 查看证书信息
docker-compose run --rm certbot certificates

# 测试续期
docker-compose run --rm certbot renew --dry-run
```

---

## 🛠️ 运维管理

### 常用命令

```bash
cd ~/teachproxy

# 查看服务状态
docker-compose ps

# 查看日志
docker-compose logs -f          # 所有服务
docker-compose logs -f api      # 仅 API
docker-compose logs -f nginx    # 仅 Nginx

# 重启服务
docker-compose restart          # 重启所有
docker-compose restart api      # 仅重启 API

# 停止服务
docker-compose down             # 停止并删除容器
docker-compose down -v          # 同时删除数据卷（谨慎使用）

# 更新部署
./scripts/deploy.sh update

# 进入容器调试
docker-compose exec api /bin/sh
```

### 备份数据

```bash
# 备份数据库
docker-compose exec postgres pg_dump -U teachproxy teachproxy > backup_$(date +%Y%m%d).sql

# 备份 Redis
docker-compose exec redis redis-cli SAVE
docker cp teachproxy-redis:/data/dump.rdb ./redis_backup_$(date +%Y%m%d).rdb
```

### 恢复数据

```bash
# 恢复数据库
docker-compose exec -T postgres psql -U teachproxy teachproxy < backup_20240101.sql

# 恢复 Redis
docker cp redis_backup_20240101.rdb teachproxy-redis:/data/dump.rdb
docker-compose restart redis
```

### 扩容（垂直）

编辑 `docker-compose.yml` 调整资源限制：

```yaml
services:
  api:
    deploy:
      resources:
        limits:
          cpus: '2.0'
          memory: 2G
        reservations:
          cpus: '1.0'
          memory: 1G
```

然后重启：

```bash
docker-compose up -d
```

---

## 🐛 故障排查

### 服务无法启动

```bash
# 查看详细日志
docker-compose logs api

# 检查配置
docker-compose config

# 检查端口占用
sudo lsof -i :80
sudo lsof -i :443
sudo lsof -i :8000
```

### 数据库连接失败

```bash
# 检查 postgres 状态
docker-compose ps postgres
docker-compose logs postgres

# 手动连接测试
docker-compose exec postgres psql -U teachproxy -d teachproxy -c "SELECT 1"
```

### SSL 证书问题

```bash
# 查看证书状态
docker-compose run --rm certbot certificates

# 重新申请证书
docker-compose run --rm certbot certonly --webroot -w /var/www/certbot -d your-domain.com

# 强制续期
docker-compose run --rm certbot renew --force-renewal
```

### API 健康检查失败

```bash
# 检查 API 日志
docker-compose logs api --tail 100

# 手动测试健康检查
curl http://localhost:8000/health

# 检查环境变量
docker-compose exec api env | grep -E "(DATABASE_URL|REDIS)"
```

### 性能问题

```bash
# 查看资源使用
docker stats

# 查看慢查询（进入 postgres）
docker-compose exec postgres psql -U teachproxy -c "SELECT * FROM pg_stat_statements ORDER BY total_time DESC LIMIT 10;"
```

---

## 📚 参考

- [Docker 官方文档](https://docs.docker.com/)
- [Docker Compose 文档](https://docs.docker.com/compose/)
- [Certbot 文档](https://certbot.eff.org/)
- [Nginx 文档](https://nginx.org/en/docs/)

---

## 🤝 支持

遇到问题？请通过以下方式获取帮助：

1. 查看 [故障排查](#故障排查) 章节
2. 提交 [GitHub Issue](https://github.com/h-lu/llmGateway/issues)
