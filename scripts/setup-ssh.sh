#!/bin/bash
# ============================================
# TeachProxy SSH 密钥设置脚本
# 用于生成和配置 GitHub Actions 部署密钥
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

# 检查 ssh-keygen
check_dependencies() {
    if ! command -v ssh-keygen &> /dev/null; then
        log_error "未找到 ssh-keygen，请先安装 OpenSSH"
        exit 1
    fi
    
    if ! command -v ssh &> /dev/null; then
        log_error "未找到 ssh 命令，请先安装 OpenSSH"
        exit 1
    fi
}

# 生成 SSH 密钥对
generate_key() {
    local key_file="$HOME/.ssh/teachproxy_deploy"
    
    if [ -f "$key_file" ]; then
        log_warn "密钥文件已存在: $key_file"
        read -p "是否覆盖？ [y/N]: " overwrite
        if [[ ! $overwrite =~ ^[Yy]$ ]]; then
            log_info "使用现有密钥"
            return
        fi
        rm -f "$key_file" "$key_file.pub"
    fi
    
    log_info "生成新的 SSH 密钥对..."
    ssh-keygen -t ed25519 -C "github-actions-deploy" -f "$key_file" -N ""
    
    chmod 600 "$key_file"
    chmod 644 "$key_file.pub"
    
    log_success "密钥对已生成:"
    log_info "私钥: $key_file"
    log_info "公钥: $key_file.pub"
}

# 显示密钥
show_keys() {
    local key_file="$HOME/.ssh/teachproxy_deploy"
    
    echo ""
    echo "=========================================="
    log_info "公钥内容 (添加到服务器):"
    echo "=========================================="
    echo ""
    cat "$key_file.pub"
    echo ""
    
    echo "=========================================="
    log_info "私钥内容 (添加到 GitHub Secrets):"
    echo "=========================================="
    echo ""
    cat "$key_file"
    echo ""
}

# 配置服务器
setup_server() {
    log_prompt "请输入服务器信息以配置 SSH 访问:"
    read -p "服务器 IP: " server_ip
    read -p "用户名 [ubuntu]: " username
    username=${username:-ubuntu}
    read -p "端口 [22]: " port
    port=${port:-22}
    
    log_info "将尝试连接到服务器并添加公钥..."
    
    # 检查是否已经有 SSH 访问权限
    if ssh -o PasswordAuthentication=no -o ConnectTimeout=5 -p "$port" "$username@$server_ip" "echo 'SSH OK'" 2>/dev/null | grep -q "SSH OK"; then
        log_success "已有 SSH 访问权限，跳过配置"
        return
    fi
    
    log_warn "需要通过密码验证连接服务器"
    log_info "正在添加公钥到服务器..."
    
    # 使用 ssh-copy-id 添加公钥
    if command -v ssh-copy-id &> /dev/null; then
        ssh-copy-id -p "$port" "$username@$server_ip"
    else
        # 手动添加
        log_info "请手动将以下公钥添加到服务器的 ~/.ssh/authorized_keys:"
        cat "$HOME/.ssh/teachproxy_deploy.pub"
        echo ""
        read -p "添加完成后按 Enter 继续..."
    fi
    
    # 测试连接
    log_info "测试 SSH 连接..."
    if ssh -o PasswordAuthentication=no -p "$port" "$username@$server_ip" "echo 'SSH Connection Successful'"; then
        log_success "SSH 配置成功！"
    else
        log_error "SSH 连接测试失败"
        exit 1
    fi
}

# 配置 GitHub Secrets
setup_github_secrets() {
    local key_file="$HOME/.ssh/teachproxy_deploy"
    
    echo ""
    log_info "GitHub Secrets 配置"
    echo "------------------------------------------"
    
    # 检查 gh CLI
    if ! command -v gh &> /dev/null; then
        log_warn "未找到 GitHub CLI (gh)"
        echo ""
        echo "请手动在 GitHub 上添加 SSH_PRIVATE_KEY Secret:"
        echo "1. 访问: https://github.com/h-lu/llmGateway/settings/secrets/actions"
        echo "2. 点击 'New repository secret'"
        echo "3. Name: SSH_PRIVATE_KEY"
        echo "4. Value: 复制以下内容:"
        echo ""
        cat "$key_file"
        echo ""
        return
    fi
    
    # 检查登录状态
    if ! gh auth status &> /dev/null; then
        log_warn "请先登录 GitHub CLI"
        gh auth login
    fi
    
    # 设置默认仓库
    gh repo set-default h-lu/llmGateway 2>/dev/null || true
    
    # 添加 Secret
    log_info "添加 SSH_PRIVATE_KEY 到 GitHub Secrets..."
    if gh secret set SSH_PRIVATE_KEY --bodyFile "$key_file"; then
        log_success "SSH_PRIVATE_KEY 已添加到 GitHub Secrets"
    else
        log_error "添加失败，请手动配置"
    fi
}

# 测试完整部署链
test_deployment() {
    local key_file="$HOME/.ssh/teachproxy_deploy"
    
    log_prompt "是否测试部署连接？ [Y/n]: "
    read -r test_deploy
    if [[ $test_deploy =~ ^[Nn]$ ]]; then
        return
    fi
    
    read -p "服务器 IP: " server_ip
    read -p "用户名 [ubuntu]: " username
    username=${username:-ubuntu}
    
    log_info "测试 SSH 连接..."
    if ssh -i "$key_file" "$username@$server_ip" "whoami"; then
        log_success "SSH 连接测试通过！"
    else
        log_error "SSH 连接测试失败"
        exit 1
    fi
}

# 主流程
main() {
    echo "=========================================="
    echo "🔑 TeachProxy SSH 密钥设置"
    echo "=========================================="
    echo ""
    
    check_dependencies
    generate_key
    show_keys
    
    echo ""
    log_prompt "是否自动配置服务器 SSH 访问？ [Y/n]: "
    read -r setup_srv
    if [[ ! $setup_srv =~ ^[Nn]$ ]]; then
        setup_server
    fi
    
    echo ""
    log_prompt "是否配置 GitHub Secrets？ [Y/n]: "
    read -r setup_gh
    if [[ ! $setup_gh =~ ^[Nn]$ ]]; then
        setup_github_secrets
    fi
    
    echo ""
    echo "=========================================="
    log_success "SSH 设置完成！"
    echo "=========================================="
    echo ""
    echo "密钥文件位置:"
    echo "  私钥: ~/.ssh/teachproxy_deploy"
    echo "  公钥: ~/.ssh/teachproxy_deploy.pub"
    echo ""
    echo "下一步："
    echo "1. 确保公钥已添加到服务器的 ~/.ssh/authorized_keys"
    echo "2. 确保私钥已添加到 GitHub Secrets (SSH_PRIVATE_KEY)"
    echo "3. 运行 ./scripts/generate-secrets.sh 生成其他 Secrets"
    echo ""
}

# 运行
main
