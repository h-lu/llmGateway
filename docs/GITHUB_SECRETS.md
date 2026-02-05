# 🔐 GitHub Secrets 配置指南

本文档详细介绍如何配置 GitHub Secrets 以实现自动部署。

---

## 📋 Secrets 清单

### 🔑 必需 Secrets

| Secret Name | 说明 | 获取方式 |
|------------|------|---------|
| `SSH_HOST` | 服务器 IP 地址 | VPS 控制台查看 |
| `SSH_USER` | SSH 用户名 | 通常为 `ubuntu` |
| `SSH_PORT` | SSH 端口 | 通常为 `22` |
| `SSH_PRIVATE_KEY` | SSH 私钥 | 在服务器上生成 |
| `DOMAIN` | 应用域名 | 你的域名，如 `api.example.com` |

### 🗄️ 数据库 Secrets

| Secret Name | 说明 | 建议值 |
|------------|------|--------|
| `DB_USER` | 数据库用户名 | `teachproxy` |
| `DB_PASSWORD` | 数据库密码 | 强密码，20+ 字符 |
| `DB_NAME` | 数据库名称 | `teachproxy` |

### 🤖 AI 提供商 Secrets

| Secret Name | 说明 | 获取方式 |
|------------|------|---------|
| `DEEPSEEK_API_KEY` | DeepSeek API Key | [DeepSeek 控制台](https://platform.deepseek.com/) |
| `DEEPSEEK_BASE_URL` | DeepSeek API 地址 | `https://api.deepseek.com/v1` |
| `OPENAI_API_KEY` | OpenAI API Key (可选) | [OpenAI 控制台](https://platform.openai.com/) |
| `TEACHER_DEEPSEEK_API_KEY` | 教师 Key (可选) | DeepSeek 控制台 |
| `TEACHER_OPENROUTER_API_KEY` | OpenRouter Key (可选) | [OpenRouter](https://openrouter.ai/) |

### 🔒 安全 Secrets

| Secret Name | 说明 | 生成方式 |
|------------|------|---------|
| `ADMIN_TOKEN` | 管理员认证令牌 | 强密码，32+ 字符 |
| `API_KEY_ENCRYPTION_KEY` | API Key 加密密钥 | `python -c "import secrets; print(secrets.token_urlsafe(32))"` |

### ⚙️ 可选 Secrets

| Secret Name | 说明 | 默认值 |
|------------|------|--------|
| `RATE_LIMIT_REQUESTS_PER_MINUTE` | 每分钟请求限制 | `60` |
| `RATE_LIMIT_BURST_SIZE` | 突发请求限制 | `10` |
| `LOG_LEVEL` | 日志级别 | `INFO` |
| `LOG_FORMAT` | 日志格式 | `json` |
| `SEMESTER_START_DATE` | 学期开始日期 | - |
| `SEMESTER_WEEKS` | 学期周数 | `16` |

---

## 🚀 配置步骤

### 步骤 1: 生成 SSH 密钥对

在**本地电脑**上执行：

```bash
# 生成新的 SSH 密钥对（专用于 GitHub Actions）
ssh-keygen -t ed25519 -C "github-actions-deploy" -f ~/.ssh/teachproxy_deploy

# 查看公钥
cat ~/.ssh/teachproxy_deploy.pub
# 输出类似：ssh-ed25519 AAAAC3NzaC... github-actions-deploy

# 查看私钥（稍后添加到 GitHub Secrets）
cat ~/.ssh/teachproxy_deploy
# -----BEGIN OPENSSH PRIVATE KEY-----
# ...
# -----END OPENSSH PRIVATE KEY-----
```

### 步骤 2: 在服务器上添加公钥

连接到你的 VPS：

```bash
ssh ubuntu@your-server-ip

# 创建 .ssh 目录（如果不存在）
mkdir -p ~/.ssh
chmod 700 ~/.ssh

# 添加公钥到 authorized_keys
echo "ssh-ed25519 AAAAC3NzaC... github-actions-deploy" >> ~/.ssh/authorized_keys
chmod 600 ~/.ssh/authorized_keys

# 测试连接（在本地执行）
ssh -i ~/.ssh/teachproxy_deploy ubuntu@your-server-ip
```

### 步骤 3: 生成加密密钥

```bash
# 生成 32 字节加密密钥
python3 -c "import secrets; print(secrets.token_urlsafe(32))"
# 输出类似：N0j4NGivD1BJuonSE9BWvgdYjpba1Bmj6lfhLsZ0i1E
```

### 步骤 4: 生成管理员令牌

```bash
# 生成强密码
python3 -c "import secrets; print(secrets.token_urlsafe(32))"
# 或
openssl rand -base64 32
```

### 步骤 5: 在 GitHub 上配置 Secrets

#### 方式 A: 使用 GitHub Web 界面

1. 打开仓库页面：https://github.com/h-lu/llmGateway
2. 点击 **Settings** → **Secrets and variables** → **Actions**
3. 点击 **New repository secret**
4. 逐个添加以下 Secrets：

```
Name: SSH_HOST
Secret: 1.2.3.4  (你的服务器IP)

Name: SSH_USER
Secret: ubuntu

Name: SSH_PORT
Secret: 22

Name: SSH_PRIVATE_KEY
Secret: -----BEGIN OPENSSH PRIVATE KEY-----
        ...
        -----END OPENSSH PRIVATE KEY-----

Name: DOMAIN
Secret: api.yourdomain.com

Name: DB_USER
Secret: teachproxy

Name: DB_PASSWORD
Secret: Your-Secure-Database-Password-123!

Name: DB_NAME
Secret: teachproxy

Name: DEEPSEEK_API_KEY
Secret: sk-your-deepseek-api-key

Name: DEEPSEEK_BASE_URL
Secret: https://api.deepseek.com/v1

Name: ADMIN_TOKEN
Secret: your-secure-admin-token

Name: API_KEY_ENCRYPTION_KEY
Secret: your-32-byte-encryption-key
```

#### 方式 B: 使用 GitHub CLI（推荐）

```bash
# 安装 gh CLI
# macOS: brew install gh
# Ubuntu: sudo apt install gh

# 登录 GitHub
gh auth login

# 设置仓库
gh repo set-default h-lu/llmGateway

# 批量添加 Secrets
gh secret set SSH_HOST --body "1.2.3.4"
gh secret set SSH_USER --body "ubuntu"
gh secret set SSH_PORT --body "22"
gh secret set SSH_PRIVATE_KEY --bodyFile ~/.ssh/teachproxy_deploy
gh secret set DOMAIN --body "api.yourdomain.com"
gh secret set DB_USER --body "teachproxy"
gh secret set DB_PASSWORD --body "Your-Secure-Password"
gh secret set DB_NAME --body "teachproxy"
gh secret set DEEPSEEK_API_KEY --body "sk-your-key"
gh secret set DEEPSEEK_BASE_URL --body "https://api.deepseek.com/v1"
gh secret set ADMIN_TOKEN --body "your-admin-token"
gh secret set API_KEY_ENCRYPTION_KEY --body "your-encryption-key"
```

---

## 🔧 使用脚本快速配置

### 1. 生成本地环境文件

```bash
# 运行配置脚本
./scripts/generate-secrets.sh
```

这个脚本会：
1. 生成加密密钥
2. 生成管理员令牌
3. 生成本地 .env 文件
4. 显示 GitHub Secrets 设置命令

### 2. 验证 Secrets

```bash
# 使用 GitHub CLI 查看已配置的 Secrets
gh secret list

# 测试 SSH 连接
ssh -i ~/.ssh/teachproxy_deploy ubuntu@your-server-ip

# 测试部署（手动触发）
gh workflow run cd.yml
```

---

## ✅ 配置验证清单

在触发自动部署前，请确认：

- [ ] SSH 密钥对已生成
- [ ] 公钥已添加到服务器的 `~/.ssh/authorized_keys`
- [ ] 私钥已添加到 GitHub Secrets（`SSH_PRIVATE_KEY`）
- [ ] 服务器 IP 已添加到 GitHub Secrets（`SSH_HOST`）
- [ ] 域名已解析到服务器 IP
- [ ] DeepSeek API Key 已获取并添加到 Secrets
- [ ] 数据库密码已设置（强密码）
- [ ] 管理员令牌已生成
- [ ] 加密密钥已生成
- [ ] 本地测试可以通过 SSH 连接到服务器

---

## 🐛 常见问题

### SSH 连接失败

```bash
# 检查 SSH 服务状态
sudo systemctl status ssh

# 检查防火墙
sudo ufw status
sudo ufw allow 22/tcp

# 检查 authorized_keys 权限
chmod 700 ~/.ssh
chmod 600 ~/.ssh/authorized_keys

# 查看 SSH 日志
sudo tail -f /var/log/auth.log
```

### Secrets 未生效

```bash
# 检查 Secrets 是否正确设置
gh secret list

# 重新设置 Secret
gh secret set SSH_PRIVATE_KEY --bodyFile ~/.ssh/teachproxy_deploy -R h-lu/llmGateway
```

### 部署失败查看日志

在 GitHub Actions 页面查看详细的部署日志，或手动在服务器上查看：

```bash
# 连接到服务器
ssh ubuntu@your-server-ip

# 查看容器日志
cd ~/teachproxy
docker-compose logs api
```

---

## 📚 参考

- [GitHub Secrets 文档](https://docs.github.com/en/actions/security-guides/encrypted-secrets)
- [GitHub CLI 文档](https://cli.github.com/manual/)
- [SSH 密钥管理](https://www.ssh.com/academy/ssh/keygen)
