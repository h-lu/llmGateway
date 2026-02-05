#!/bin/bash
# ============================================
# TeachProxy Secrets 生成和配置脚本
# 用于生成加密密钥和配置 GitHub Secrets
# ============================================

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# 打印函数
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

log_prompt() {
    echo -e "${CYAN}[PROMPT]${NC} $1"
}

# 生成随机密钥
generate_key() {
    python3 -c "import secrets; print(secrets.token_urlsafe(32))" 2>/dev/null || openssl rand -base64 32
}

# 生成密码
generate_password() {
    openssl rand -base64 24 | tr -d "=+/" | cut -c1-32
}

# 检查依赖
check_dependencies() {
    log_info "检查依赖..."
    
    if ! command -v python3 &> /dev/null && ! command -v openssl &> /dev/null; then
        log_error "需要安装 python3 或 openssl"
        exit 1
    fi
    
    log_success "依赖检查通过"
}

# 生成 Secrets
generate_secrets() {
    log_info "正在生成 Secrets..."
    echo ""
    
    # 加密密钥
    ENCRYPTION_KEY=$(generate_key)
    log_success "API_KEY_ENCRYPTION_KEY: ${ENCRYPTION_KEY:0:20}..."
    
    # 管理员令牌
    ADMIN_TOKEN=$(generate_password)
    log_success "ADMIN_TOKEN: ${ADMIN_TOKEN:0:20}..."
    
    # 数据库密码
    DB_PASSWORD=$(generate_password)
    log_success "DB_PASSWORD: ${DB_PASSWORD:0:20}..."
    
    echo ""
}

# 收集用户输入
collect_input() {
    log_prompt "请输入以下配置信息："
    echo ""
    
    # SSH 配置
    read -p "服务器 IP 地址 (SSH_HOST): " SSH_HOST
    read -p "SSH 用户名 [ubuntu]: " SSH_USER
    SSH_USER=${SSH_USER:-ubuntu}
    read -p "SSH 端口 [22]: " SSH_PORT
    SSH_PORT=${SSH_PORT:-22}
    
    echo ""
    
    # 域名
    read -p "应用域名 (如 api.example.com): " DOMAIN
    
    echo ""
    
    # AI 提供商
    read -p "DeepSeek API Key: " DEEPSEEK_API_KEY
    read -p "DeepSeek Base URL [https://api.deepseek.com/v1]: " DEEPSEEK_BASE_URL
    DEEPSEEK_BASE_URL=${DEEPSEEK_BASE_URL:-https://api.deepseek.com/v1}
    
    echo ""
    
    # 可选配置
    read -p "OpenAI API Key (可选): " OPENAI_API_KEY
    read -p "学期开始日期 (如 2026-02-17): " SEMESTER_START_DATE
    
    echo ""
}

# 创建本地 .env 文件
create_env_file() {
    log_info "创建本地 .env 文件..."
    
    cat > .env << EOF
# ============================================
# TeachProxy 生产环境配置
# 生成时间: $(date '+%Y-%m-%d %H:%M:%S')
# ============================================

# ============================================================
# 数据库配置
# ============================================================
DB_USER=teachproxy
DB_PASSWORD=${DB_PASSWORD}
DB_NAME=teachproxy

# ============================================================
# AI 提供商配置
# ============================================================
DEEPSEEK_API_KEY=${DEEPSEEK_API_KEY}
DEEPSEEK_BASE_URL=${DEEPSEEK_BASE_URL}
OPENAI_API_KEY=${OPENAI_API_KEY}

# ============================================================
# 安全配置
# ============================================================
ADMIN_TOKEN=${ADMIN_TOKEN}
API_KEY_ENCRYPTION_KEY=${ENCRYPTION_KEY}

# ============================================================
# 功能配置
# ============================================================
RATE_LIMIT_REQUESTS_PER_MINUTE=60
RATE_LIMIT_BURST_SIZE=10
LOG_LEVEL=INFO
LOG_FORMAT=json
SEMESTER_START_DATE=${SEMESTER_START_DATE}
SEMESTER_WEEKS=16
EOF
    
    log_success ".env 文件已创建"
}

# 显示 GitHub Secrets 设置命令
show_github_commands() {
    echo ""
    echo "=========================================="
    log_info "GitHub Secrets 设置命令"
    echo "=========================================="
    echo ""
    echo -e "${YELLOW}方式 1: 使用 GitHub CLI（推荐）${NC}"
    echo "------------------------------------------"
    echo ""
    echo "# 确保已登录 GitHub CLI"
    echo "gh auth login"
    echo ""
    echo "# 设置仓库"
    echo "gh repo set-default h-lu/llmGateway"
    echo ""
    echo "# 批量添加 Secrets"
    echo "gh secret set SSH_HOST --body \"${SSH_HOST}\""
    echo "gh secret set SSH_USER --body \"${SSH_USER}\""
    echo "gh secret set SSH_PORT --body \"${SSH_PORT}\""
    echo "gh secret set DOMAIN --body \"${DOMAIN}\""
    echo "gh secret set DB_USER --body \"teachproxy\""
    echo "gh secret set DB_PASSWORD --body \"${DB_PASSWORD}\""
    echo "gh secret set DB_NAME --body \"teachproxy\""
    echo "gh secret set DEEPSEEK_API_KEY --body \"${DEEPSEEK_API_KEY}\""
    echo "gh secret set DEEPSEEK_BASE_URL --body \"${DEEPSEEK_BASE_URL}\""
    echo "gh secret set ADMIN_TOKEN --body \"${ADMIN_TOKEN}\""
    echo "gh secret set API_KEY_ENCRYPTION_KEY --body \"${ENCRYPTION_KEY}\""
    
    if [ -n "$OPENAI_API_KEY" ]; then
        echo "gh secret set OPENAI_API_KEY --body \"${OPENAI_API_KEY}\""
    fi
    
    if [ -n "$SEMESTER_START_DATE" ]; then
        echo "gh secret set SEMESTER_START_DATE --body \"${SEMESTER_START_DATE}\""
    fi
    
    if [ -f "$HOME/.ssh/teachproxy_deploy" ]; then
        echo "gh secret set SSH_PRIVATE_KEY --bodyFile ~/.ssh/teachproxy_deploy"
    else
        echo ""
        echo -e "${YELLOW}注意: SSH 私钥文件 ~/.ssh/teachproxy_deploy 不存在${NC}"
        echo "请先运行: ./scripts/setup-ssh.sh"
    fi
    
    echo ""
    echo "------------------------------------------"
    echo -e "${YELLOW}方式 2: 使用 GitHub Web 界面${NC}"
    echo "------------------------------------------"
    echo ""
    echo "1. 打开: https://github.com/h-lu/llmGateway/settings/secrets/actions"
    echo "2. 点击 'New repository secret'"
    echo "3. 逐个添加以下 Secrets:"
    echo ""
    
    echo "Name: SSH_HOST"
    echo "Value: ${SSH_HOST}"
    echo ""
    echo "Name: SSH_USER"
    echo "Value: ${SSH_USER}"
    echo ""
    echo "Name: SSH_PORT"
    echo "Value: ${SSH_PORT}"
    echo ""
    echo "Name: DOMAIN"
    echo "Value: ${DOMAIN}"
    echo ""
    echo "Name: DB_PASSWORD"
    echo "Value: ${DB_PASSWORD:0:10}..."
    echo ""
    echo "Name: DEEPSEEK_API_KEY"
    echo "Value: ${DEEPSEEK_API_KEY:0:10}..."
    echo ""
    echo "Name: ADMIN_TOKEN"
    echo "Value: ${ADMIN_TOKEN:0:10}..."
    echo ""
    echo "Name: API_KEY_ENCRYPTION_KEY"
    echo "Value: ${ENCRYPTION_KEY:0:10}..."
    echo ""
}

# 保存 secrets 到文件
save_secrets_file() {
    SECRETS_FILE=".secrets_backup_$(date +%Y%m%d_%H%M%S).txt"
    
    cat > "$SECRETS_FILE" << EOF
TeachProxy Secrets 备份
生成时间: $(date '+%Y-%m-%d %H:%M:%S')
============================================

SSH_HOST=${SSH_HOST}
SSH_USER=${SSH_USER}
SSH_PORT=${SSH_PORT}
DOMAIN=${DOMAIN}

DB_USER=teachproxy
DB_PASSWORD=${DB_PASSWORD}
DB_NAME=teachproxy

DEEPSEEK_API_KEY=${DEEPSEEK_API_KEY}
DEEPSEEK_BASE_URL=${DEEPSEEK_BASE_URL}
OPENAI_API_KEY=${OPENAI_API_KEY}

ADMIN_TOKEN=${ADMIN_TOKEN}
API_KEY_ENCRYPTION_KEY=${ENCRYPTION_KEY}

SEMESTER_START_DATE=${SEMESTER_START_DATE}
============================================

⚠️  警告: 此文件包含敏感信息，请妥善保管！
EOF
    
    chmod 600 "$SECRETS_FILE"
    log_warn "Secrets 已备份到: $SECRETS_FILE"
    log_warn "请妥善保管此文件，并在配置完成后删除！"
}

# 主流程
main() {
    echo "=========================================="
    echo "🔐 TeachProxy Secrets 生成工具"
    echo "=========================================="
    echo ""
    
    check_dependencies
    generate_secrets
    collect_input
    
    echo ""
    echo "=========================================="
    log_info "配置摘要"
    echo "=========================================="
    echo "服务器: ${SSH_USER}@${SSH_HOST}:${SSH_PORT}"
    echo "域名: ${DOMAIN}"
    echo "数据库: teachproxy @ ${DB_PASSWORD:0:10}..."
    echo "DeepSeek: ${DEEPSEEK_API_KEY:0:10}..."
    echo ""
    
    read -p "确认以上信息正确？将生成配置文件 [Y/n]: " confirm
    if [[ $confirm =~ ^[Nn]$ ]]; then
        log_error "已取消"
        exit 1
    fi
    
    create_env_file
    save_secrets_file
    
    echo ""
    show_github_commands
    
    echo ""
    echo "=========================================="
    log_success "配置生成完成！"
    echo "=========================================="
    echo ""
    echo "下一步："
    echo "1. 在服务器上添加 SSH 公钥（如果还没有）"
    echo "2. 使用上面的命令配置 GitHub Secrets"
    echo "3. 删除备份文件: rm .secrets_backup_*.txt"
    echo "4. 触发部署: git push origin main"
    echo ""
}

# 运行
main
