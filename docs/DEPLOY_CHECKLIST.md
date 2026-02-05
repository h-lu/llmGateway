# ✅ TeachProxy 部署验证清单

本文档提供首次部署前的完整检查清单，确保部署顺利进行。

---

## 📋 前置条件检查

### 1. 服务器准备

- [ ] **已购买 VPS 服务器**
  - 推荐配置：4核 8GB 内存 50GB SSD
  - 操作系统：Ubuntu 22.04 LTS 或 24.04 LTS
  
- [ ] **已配置安全组/防火墙**
  - 开放端口：22 (SSH), 80 (HTTP), 443 (HTTPS)
  - 可选端口：8000 (直接访问 API，用于调试)

- [ ] **已配置域名解析**
  - A 记录指向服务器 IP
  - 等待 DNS 生效（通常 5-60 分钟）

### 2. 本地环境准备

- [ ] **已安装 Git**
  ```bash
  git --version
  ```

- [ ] **已安装 GitHub CLI (可选但推荐)**
  ```bash
  gh --version
  gh auth login
  ```

- [ ] **已有 SSH 客户端**
  ```bash
  ssh -V
  ```

---

## 🔑 SSH 密钥配置检查

### 生成部署密钥

- [ ] **已运行 SSH 设置脚本**
  ```bash
  ./scripts/setup-ssh.sh
  ```

- [ ] **密钥对已生成**
  ```bash
  ls -la ~/.ssh/teachproxy_deploy*
  # 应看到:
  # -rw------- 1 user user  411 Feb  5 10:00 teachproxy_deploy
  # -rw-r--r-- 1 user user  102 Feb  5 10:00 teachproxy_deploy.pub
  ```

- [ ] **公钥已添加到服务器**
  ```bash
  # 在服务器上执行
  cat ~/.ssh/authorized_keys | grep github-actions-deploy
  ```

- [ ] **本地测试 SSH 连接成功**
  ```bash
  ssh -i ~/.ssh/teachproxy_deploy ubuntu@your-server-ip "echo 'OK'"
  # 输出: OK
  ```

---

## 🔐 GitHub Secrets 配置检查

### 必需 Secrets

- [ ] **SSH_HOST** - 服务器 IP 地址
  ```bash
  gh secret get SSH_HOST
  ```

- [ ] **SSH_USER** - SSH 用户名（通常是 `ubuntu`）

- [ ] **SSH_PORT** - SSH 端口（通常是 `22`）

- [ ] **SSH_PRIVATE_KEY** - SSH 私钥完整内容
  ```bash
  # 检查是否设置
  gh secret list | grep SSH_PRIVATE_KEY
  ```

- [ ] **DOMAIN** - 应用域名（如 `api.example.com`）

### 数据库 Secrets

- [ ] **DB_USER** - 数据库用户名（建议 `teachproxy`）

- [ ] **DB_PASSWORD** - 强密码（20+ 字符，包含大小写、数字、符号）

- [ ] **DB_NAME** - 数据库名称（建议 `teachproxy`）

### AI 提供商 Secrets

- [ ] **DEEPSEEK_API_KEY** - 有效的 DeepSeek API Key
  ```bash
  # 验证 API Key 有效性
  curl https://api.deepseek.com/v1/models \
    -H "Authorization: Bearer sk-your-key"
  ```

- [ ] **DEEPSEEK_BASE_URL** - 默认为 `https://api.deepseek.com/v1`

### 安全 Secrets

- [ ] **ADMIN_TOKEN** - 管理员认证令牌（强密码）
  ```bash
  # 生成方式
  python3 -c "import secrets; print(secrets.token_urlsafe(32))"
  ```

- [ ] **API_KEY_ENCRYPTION_KEY** - 32 字节加密密钥
  ```bash
  # 生成方式
  python3 -c "import secrets; print(secrets.token_urlsafe(32))"
  ```

### 验证所有 Secrets

```bash
# 查看已配置的所有 Secrets
gh secret list

# 预期输出包含以下条目:
# ADMIN_TOKEN
# API_KEY_ENCRYPTION_KEY
# DB_NAME
# DB_PASSWORD
# DB_USER
# DEEPSEEK_API_KEY
# DEEPSEEK_BASE_URL
# DOMAIN
# SSH_HOST
# SSH_PORT
# SSH_PRIVATE_KEY
# SSH_USER
```

---

## 🐳 服务器环境检查

### Docker 安装

- [ ] **Docker 已安装**
  ```bash
  # 在服务器上执行
  docker --version
  # 预期输出: Docker version 24.x.x or higher
  ```

- [ ] **Docker Compose 已安装**
  ```bash
  docker compose version
  # 预期输出: Docker Compose version v2.x.x
  ```

- [ ] **当前用户已添加到 docker 组**
  ```bash
  groups
  # 应包含 'docker'
  ```

### 系统配置

- [ ] **系统已更新**
  ```bash
  sudo apt update && sudo apt upgrade -y
  ```

- [ ] **时区设置正确**
  ```bash
  timedatectl
  # 确保时区正确，如 Asia/Shanghai
  ```

---

## 🧪 部署前测试

### 1. 触发 GitHub Actions 工作流

- [ ] **手动触发部署**
  ```bash
  gh workflow run cd.yml
  ```

- [ ] **或推送代码触发**
  ```bash
  git checkout main
  git pull origin main
  # 做一些小修改
  git commit --allow-empty -m "trigger: deploy"
  git push origin main
  ```

### 2. 监控部署过程

- [ ] **在 GitHub Actions 页面查看部署日志**
  - 访问: `https://github.com/h-lu/llmGateway/actions`
  - 确保所有步骤都显示 ✅

### 3. 验证部署结果

- [ ] **容器状态正常**
  ```bash
  # 在服务器上执行
  cd ~/teachproxy
  docker-compose ps
  
  # 预期输出: 所有服务显示 'Up'
  # NAME                    STATUS
  # teachproxy-api          Up (healthy)
  # teachproxy-nginx        Up
  # teachproxy-postgres     Up (healthy)
  # teachproxy-redis        Up (healthy)
  # teachproxy-certbot      Up
  ```

- [ ] **API 健康检查通过**
  ```bash
  curl http://localhost:8000/health
  # 预期输出: {"status":"ok",...}
  ```

- [ ] **数据库连接正常**
  ```bash
  docker-compose exec postgres pg_isready
  # 预期输出: /var/run/postgresql:5432 - accepting connections
  ```

- [ ] **Redis 连接正常**
  ```bash
  docker-compose exec redis redis-cli ping
  # 预期输出: PONG
  ```

---

## 🌐 外部访问验证

### HTTP 访问

- [ ] **域名解析正确**
  ```bash
  nslookup your-domain.com
  # 应返回你的服务器 IP
  ```

- [ ] **HTTP 访问正常**
  ```bash
  curl http://your-domain.com/health
  # 或
  curl -I http://your-domain.com
  # 预期: HTTP/1.1 301 Moved Permanently (重定向到 HTTPS)
  ```

### HTTPS 访问

- [ ] **SSL 证书已申请**
  ```bash
  # 在服务器上执行
  docker-compose exec certbot certbot certificates
  # 应显示已颁发的证书
  ```

- [ ] **HTTPS 访问正常**
  ```bash
  curl https://your-domain.com/health
  # 预期: {"status":"ok",...}
  ```

- [ ] **浏览器访问正常**
  - 打开 `https://your-domain.com`
  - 检查证书是否有效（🔒 图标）
  - 应看到应用界面

### API 测试

- [ ] **API 文档可访问**
  - 打开 `https://your-domain.com/docs`
  - 应看到 Swagger UI

- [ ] **聊天接口测试（需要 API Key）**
  ```bash
  curl -X POST https://your-domain.com/v1/chat/completions \
    -H "Content-Type: application/json" \
    -H "Authorization: Bearer student-api-key" \
    -d '{"model":"deepseek-chat","messages":[{"role":"user","content":"hello"}]}'
  ```

---

## 📊 监控和日志检查

### 查看服务日志

- [ ] **API 日志无错误**
  ```bash
  docker-compose logs api --tail 100
  # 检查是否有 ERROR 级别的日志
  ```

- [ ] **Nginx 访问日志正常**
  ```bash
  docker-compose logs nginx --tail 50
  ```

- [ ] **数据库日志正常**
  ```bash
  docker-compose logs postgres --tail 50
  ```

### 资源使用

- [ ] **系统资源使用正常**
  ```bash
  docker stats --no-stream
  # 检查 CPU、内存使用是否在合理范围
  ```

---

## 🚨 常见问题快速修复

### SSL 证书问题

```bash
# 手动申请证书
docker-compose run --rm certbot certonly \
  --webroot \
  --webroot-path=/var/www/certbot \
  --email admin@your-domain.com \
  --agree-tos \
  --no-eff-email \
  -d your-domain.com

# 重启 Nginx
docker-compose restart nginx
```

### 数据库连接问题

```bash
# 重启数据库
docker-compose restart postgres

# 检查数据库日志
docker-compose logs postgres
```

### API 无法启动

```bash
# 查看详细日志
docker-compose logs api

# 检查环境变量
docker-compose exec api env | grep -E "(DATABASE|REDIS)"

# 重启 API
docker-compose restart api
```

---

## ✅ 部署完成确认

所有检查项通过后，确认以下事项：

- [ ] 🌐 应用可通过域名 HTTPS 访问
- [ ] 📚 API 文档正常显示
- [ ] 🔐 SSL 证书有效
- [ ] 🗄️ 数据库连接正常
- [ ] 💾 Redis 连接正常
- [ ] 🤖 AI 提供商调用正常
- [ ] 📊 监控和日志正常
- [ ] 🔄 自动部署流程已验证

---

## 📞 后续支持

如果部署遇到问题：

1. 查看详细日志：`docker-compose logs -f`
2. 检查 GitHub Actions 日志
3. 提交 [GitHub Issue](https://github.com/h-lu/llmGateway/issues)
4. 参考 [部署文档](./DEPLOY.md)

---

**部署日期**: ___________

**部署人员**: ___________

**验证结果**: ⬜ 成功 / ⬜ 失败
