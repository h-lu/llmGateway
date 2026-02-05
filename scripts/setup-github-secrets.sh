#!/bin/bash
# ============================================
# TeachProxy GitHub Secrets 批量配置脚本
# 使用 GitHub CLI 批量设置 Secrets
# ============================================

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

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

# 检查 gh CLI
check_gh() {
    if ! command -v gh &> /dev/null; then
        log_error "未找到 GitHub CLI (gh)"
        echo ""
        echo "安装方式:"
        echo "  macOS:    brew install gh"
        echo "  Ubuntu:   sudo apt install gh"
        echo "  其他:     https://github.com/cli/cli#installation"
        echo ""
        exit 1
    fi
    
    # 检查登录状态
    if ! gh auth status &> /dev/null; then
        log_warn "请先登录 GitHub"
        gh auth login
    fi
    
    # 设置默认仓库
    gh repo set-default h-lu/llmGateway 2>/dev/null || true
    
    log_success "GitHub CLI 已就绪"
}

# 从 .env 文件读取配置
load_from_env() {
    if [ ! -f ".env" ]; then
        log_error "未找到 .env 文件"
        log_info "请先运行: ./scripts/generate-secrets.sh"
        exit 1
    fi
    
    log_info "从 .env 文件加载配置..."
    
    # 读取变量
    export $(grep -v '^#' .env | grep -v '^$' | xargs)
    
    log_success "配置已加载"
}

# 设置单个 Secret
set_secret() {
    local name=$1
    local value=$2
    
    if [ -z "$value" ]; then
        log_warn "$name 为空，跳过"
        return
    fi
    
    log_info "设置 $name..."
    if echo "$value" | gh secret set "$name" &> /dev/null; then
        log_success "$name 已设置"
    else
        log_error "$name 设置失败"
    fi
}

# 设置文件类型的 Secret
set_secret_file() {
    local name=$1
    local file=$2
    
    if [ ! -f "$file" ]; then
        log_warn "文件不存在: $file"
        return
    fi
    
    log_info "设置 $name (来自文件)..."
    if gh secret set "$name" --bodyFile "$file" &> /dev/null; then
        log_success "$name 已设置"
    else
        log_error "$name 设置失败"
    fi
}

# 批量设置 Secrets
setup_all_secrets() {
    echo ""
    echo "=========================================="
    log_info "开始批量设置 GitHub Secrets"
    echo "=========================================="
    echo ""
    
    # 收集必要信息
    log_prompt "请输入服务器信息:"
    read -p "服务器 IP 地址 (SSH_HOST): " SSH_HOST
    read -p "SSH 用户名 [ubuntu]: " SSH_USER
    SSH_USER=${SSH_USER:-ubuntu}
    read -p "SSH 端口 [22]: " SSH_PORT
    SSH_PORT=${SSH_PORT:-22}
    read -p "应用域名 (如 api.example.com): " DOMAIN
    
    echo ""
    log_info "正在设置 Secrets..."
    echo ""
    
    # SSH 配置
    set_secret "SSH_HOST" "$SSH_HOST"
    set_secret "SSH_USER" "$SSH_USER"
    set_secret "SSH_PORT" "$SSH_PORT"
    
    # SSH 私钥
    if [ -f "$HOME/.ssh/teachproxy_deploy" ]; then
        set_secret_file "SSH_PRIVATE_KEY" "$HOME/.ssh/teachproxy_deploy"
    else
        log_warn "SSH 私钥不存在，跳过 SSH_PRIVATE_KEY"
        log_info "请运行: ./scripts/setup-ssh.sh 生成密钥"
    fi
    
    # 域名
    set_secret "DOMAIN" "$DOMAIN"
    
    # 数据库配置
    set_secret "DB_USER" "${DB_USER:-teachproxy}"
    set_secret "DB_PASSWORD" "$DB_PASSWORD"
    set_secret "DB_NAME" "${DB_NAME:-teachproxy}"
    
    # AI 提供商
    set_secret "DEEPSEEK_API_KEY" "$DEEPSEEK_API_KEY"
    set_secret "DEEPSEEK_BASE_URL" "${DEEPSEEK_BASE_URL:-https://api.deepseek.com/v1}"
    
    if [ -n "$OPENAI_API_KEY" ]; then
        set_secret "OPENAI_API_KEY" "$OPENAI_API_KEY"
    fi
    
    # 安全
    set_secret "ADMIN_TOKEN" "$ADMIN_TOKEN"
    set_secret "API_KEY_ENCRYPTION_KEY" "$API_KEY_ENCRYPTION_KEY"
    
    # 可选配置
    set_secret "RATE_LIMIT_REQUESTS_PER_MINUTE" "${RATE_LIMIT_REQUESTS_PER_MINUTE:-60}"
    set_secret "RATE_LIMIT_BURST_SIZE" "${RATE_LIMIT_BURST_SIZE:-10}"
    set_secret "LOG_LEVEL" "${LOG_LEVEL:-INFO}"
    set_secret "LOG_FORMAT" "${LOG_FORMAT:-json}"
    
    if [ -n "$SEMESTER_START_DATE" ]; then
        set_secret "SEMESTER_START_DATE" "$SEMESTER_START_DATE"
    fi
    set_secret "SEMESTER_WEEKS" "${SEMESTER_WEEKS:-16}"
    
    echo ""
    echo "=========================================="
    log_success "GitHub Secrets 设置完成！"
    echo "=========================================="
}

# 显示当前 Secrets
list_secrets() {
    echo ""
    log_info "当前已配置的 Secrets:"
    echo "------------------------------------------"
    gh secret list || true
    echo ""
}

# 删除所有 Secrets (危险操作)
delete_all_secrets() {
    log_warn "⚠️  此操作将删除所有 Secrets！"
    read -p "输入 'DELETE' 确认删除所有 Secrets: " confirm
    
    if [ "$confirm" != "DELETE" ]; then
        log_info "已取消删除操作"
        return
    fi
    
    log_info "删除所有 Secrets..."
    gh secret list | tail -n +2 | awk '{print $1}' | while read -r name; do
        log_info "删除 $name..."
        gh secret delete "$name" -y || true
    done
    
    log_success "所有 Secrets 已删除"
}

# 主菜单
show_menu() {
    echo ""
    echo "=========================================="
    echo "🔐 GitHub Secrets 管理工具"
    echo "=========================================="
    echo ""
    echo "1) 批量设置所有 Secrets (推荐)"
    echo "2) 查看当前 Secrets"
    echo "3) 设置单个 Secret"
    echo "4) 删除所有 Secrets (⚠️ 危险)"
    echo "5) 退出"
    echo ""
}

# 设置单个 Secret 交互
set_single_secret() {
    read -p "Secret 名称: " name
    read -p "Secret 值: " value
    set_secret "$name" "$value"
}

# 主流程
main() {
    check_gh
    
    # 尝试加载 .env
    if [ -f ".env" ]; then
        load_from_env
    else
        log_warn "未找到 .env 文件"
    fi
    
    while true; do
        show_menu
        read -p "请选择操作 [1-5]: " choice
        
        case $choice in
            1)
                setup_all_secrets
                ;;
            2)
                list_secrets
                ;;
            3)
                set_single_secret
                ;;
            4)
                delete_all_secrets
                ;;
            5)
                log_info "退出"
                exit 0
                ;;
            *)
                log_error "无效选择"
                ;;
        esac
    done
}

# 命令行参数处理
case "${1:-}" in
    --list|-l)
        check_gh
        list_secrets
        ;;
    --setup|-s)
        check_gh
        load_from_env
        setup_all_secrets
        ;;
    --delete|-d)
        check_gh
        delete_all_secrets
        ;;
    *)
        main
        ;;
esac
