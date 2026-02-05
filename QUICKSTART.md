# 🚀 TeachProxy 快速部署指南

PR#9 已合并！按照以下步骤完成部署。

---

## 📋 部署流程概览

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│  1. 准备服务器   │ -> │ 2. 配置 Secrets │ -> │  3. 触发部署    │
│  (安装 Docker)  │    │  (GitHub/本地)  │    │  (自动/手动)   │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

---

## 步骤 1: 准备服务器

### 1.1 连接到你的 VPS

```bash
ssh ubuntu@your-server-ip
```

### 1.2 运行初始化脚本

```bash
# 下载并运行初始化脚本
curl -fsSL https://raw.githubusercontent.com/h-lu/llmGateway/main/scripts/setup-server.sh | sudo bash

# 或手动执行步骤
sudo apt update && sudo apt upgrade -y
sudo apt install -y curl git

# 安装 Docker
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER

# 安装 Docker Compose
sudo apt install -y docker-compose-plugin

# 配置防火墙
sudo ufw allow 22/tcp
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw --force enable

# 退出并重新登录使 Docker 权限生效
exit
```

### 1.3 验证安装

重新连接服务器：

```bash
ssh ubuntu@your-server-ip

# 验证 Docker
docker --version
docker compose version

# 验证防火墙
sudo ufw status
```

---

## 步骤 2: 配置 GitHub Secrets

### 2.1 在本地电脑上生成配置

```bash
# 1. 克隆仓库（如果还没有）
git clone https://github.com/h-lu/llmGateway.git
cd llmGateway

# 2. 生成 SSH 密钥
./scripts/setup-ssh.sh

# 3. 生成 Secrets
./scripts/generate-secrets.sh
```

### 2.2 设置 GitHub Secrets

**方式 A: 使用脚本（推荐）**

```bash
./scripts/setup-github-secrets.sh
```

**方式 B: 手动设置**

访问：https://github.com/h-lu/llmGateway/settings/secrets/actions

添加以下 Secrets：

| Secret | 值 | 获取方式 |
|--------|-----|---------|
| `SSH_HOST` | 你的服务器 IP | VPS 控制台 |
| `SSH_USER` | `ubuntu` | - |
| `SSH_PORT` | `22` | - |
| `SSH_PRIVATE_KEY` | SSH 私钥内容 | `cat ~/.ssh/teachproxy_deploy` |
| `DOMAIN` | 你的域名 | 如 `api.example.com` |
| `DB_PASSWORD` | 数据库密码 | `generate-secrets.sh` 生成 |
| `DEEPSEEK_API_KEY` | DeepSeek API Key | [DeepSeek 控制台](https://platform.deepseek.com/) |
| `ADMIN_TOKEN` | 管理员令牌 | `generate-secrets.sh` 生成 |
| `API_KEY_ENCRYPTION_KEY` | 加密密钥 | `generate-secrets.sh` 生成 |

---

## 步骤 3: 触发部署

### 3.1 自动部署（推荐）

推送任意代码到 main 分支：

```bash
git checkout main
git pull origin main

# 做一个空提交触发部署
git commit --allow-empty -m "trigger: deploy"
git push origin main
```

在 GitHub Actions 页面查看部署进度：
https://github.com/h-lu/llmGateway/actions

### 3.2 手动部署（备用）

```bash
# 在服务器上执行
git clone https://github.com/h-lu/llmGateway.git ~/teachproxy
cd ~/teachproxy
cp .env.production .env
# 编辑 .env 配置

./scripts/deploy.sh
```

---

## 步骤 4: 验证部署

### 4.1 检查服务状态

```bash
# 连接服务器
ssh ubuntu@your-server-ip

cd ~/teachproxy
docker-compose ps

# 预期输出：所有服务显示 Up (healthy)
```

### 4.2 测试访问

```bash
# 测试健康检查
curl http://your-server-ip:8000/health

# 测试 API 文档
curl http://your-server-ip:8000/docs
```

### 4.3 配置域名和 SSL

如果你有域名：

```bash
# 1. 确保域名已解析到服务器 IP

# 2. 在本地生成 Nginx 配置并上传
export DOMAIN=your-domain.com
envsubst '\${DOMAIN}' < nginx/conf.d/app.conf.template > nginx.conf
scp nginx.conf ubuntu@your-server-ip:~/teachproxy/nginx/conf.d/app.conf

# 3. 申请 SSL 证书（在服务器上执行）
ssh ubuntu@your-server-ip
cd ~/teachproxy
docker-compose run --rm certbot certonly \
  --webroot \
  --webroot-path=/var/www/certbot \
  --email admin@your-domain.com \
  --agree-tos \
  --no-eff-email \
  -d your-domain.com

# 4. 重启 nginx
docker-compose restart nginx
```

---

## 🎯 部署完成检查清单

- [ ] 服务器初始化完成（Docker 已安装）
- [ ] GitHub Secrets 全部配置
- [ ] GitHub Actions 部署成功（显示绿色 ✅）
- [ ] 容器运行正常（`docker-compose ps` 显示 Up）
- [ ] API 健康检查通过（`curl /health` 返回 ok）
- [ ] 域名可访问（如果有域名）
- [ ] SSL 证书有效（浏览器显示 🔒）

---

## 🐛 故障排查

### SSH 连接失败

```bash
# 检查 SSH 服务
ssh ubuntu@your-server-ip "sudo systemctl status ssh"

# 检查防火墙
ssh ubuntu@your-server-ip "sudo ufw status"
```

### 部署失败

```bash
# 查看 GitHub Actions 日志
gh run list
gh run view <run-id>

# 在服务器上查看日志
ssh ubuntu@your-server-ip "cd ~/teachproxy && docker-compose logs api"
```

### 服务启动失败

```bash
ssh ubuntu@your-server-ip
cd ~/teachproxy

# 查看详细日志
docker-compose logs api --tail 100

# 重启服务
docker-compose restart
```

---

## 📚 相关文档

- [详细部署文档](./docs/DEPLOY.md)
- [GitHub Secrets 配置](./docs/GITHUB_SECRETS.md)
- [部署检查清单](./docs/DEPLOY_CHECKLIST.md)

---

## 💬 需要帮助？

- 提交 [GitHub Issue](https://github.com/h-lu/llmGateway/issues)
- 查看 [故障排查指南](./docs/DEPLOY.md#故障排查)
