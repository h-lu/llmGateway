#!/bin/bash
# ============================================
# TeachProxy 服务器初始化脚本
# 在 VPS 上运行此脚本准备部署环境
# ============================================

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

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

# 检查 root 权限
check_root() {
    if [ "$EUID" -ne 0 ]; then
        log_error "请使用 sudo 运行此脚本"
        exit 1
    fi
}

# 更新系统
update_system() {
    log_info "更新系统包..."
    apt-get update
    apt-get upgrade -y
    log_success "系统已更新"
}

# 安装基础工具
install_base_tools() {
    log_info "安装基础工具..."
    apt-get install -y \
        curl \
        wget \
        git \
        vim \
        htop \
        unzip \
        jq \
        ncdu \
        fail2ban \
        ufw
    log_success "基础工具已安装"
}

# 安装 Docker
install_docker() {
    log_info "安装 Docker..."
    
    if command -v docker &> /dev/null; then
        log_warn "Docker 已安装，跳过"
        docker --version
        return
    fi
    
    # 使用官方脚本安装
    curl -fsSL https://get.docker.com | sh
    
    # 启动 Docker
    systemctl enable docker
    systemctl start docker
    
    log_success "Docker 已安装"
    docker --version
}

# 配置 Docker 权限
setup_docker_user() {
    local username="${1:-ubuntu}"
    
    log_info "配置 Docker 权限 (用户: $username)..."
    
    usermod -aG docker "$username"
    
    log_success "用户 $username 已添加到 docker 组"
    log_warn "请重新登录以使权限生效"
}

# 安装 Docker Compose
install_docker_compose() {
    log_info "安装 Docker Compose..."
    
    if docker compose version &> /dev/null; then
        log_warn "Docker Compose 已安装，跳过"
        docker compose version
        return
    fi
    
    # 安装插件
    apt-get install -y docker-compose-plugin
    
    log_success "Docker Compose 已安装"
}

# 配置防火墙
setup_firewall() {
    log_info "配置防火墙..."
    
    # 重置防火墙
    ufw --force reset
    
    # 默认策略
    ufw default deny incoming
    ufw default allow outgoing
    
    # 允许 SSH
    ufw allow 22/tcp
    
    # 允许 HTTP/HTTPS
    ufw allow 80/tcp
    ufw allow 443/tcp
    
    # 启用防火墙
    ufw --force enable
    
    log_success "防火墙已配置"
    ufw status
}

# 配置 fail2ban
setup_fail2ban() {
    log_info "配置 fail2ban..."
    
    systemctl enable fail2ban
    systemctl start fail2ban
    
    log_success "fail2ban 已启动"
}

# 配置时区
setup_timezone() {
    log_info "配置时区..."
    
    timedatectl set-timezone Asia/Shanghai
    
    log_success "时区已设置为 Asia/Shanghai"
    timedatectl
}

# 优化系统参数
optimize_system() {
    log_info "优化系统参数..."
    
    # 增加文件描述符限制
    cat >> /etc/security/limits.conf << 'EOF'
* soft nofile 65536
* hard nofile 65536
EOF
    
    # 优化内核参数
    cat >> /etc/sysctl.conf << 'EOF'
# 增加连接数
net.core.somaxconn = 65535
net.ipv4.tcp_max_syn_backlog = 65535

# 优化 TCP 性能
net.ipv4.tcp_tw_reuse = 1
net.ipv4.tcp_fin_timeout = 30
net.ipv4.tcp_keepalive_time = 1200
net.ipv4.tcp_max_tw_buckets = 5000

# 内存优化
vm.swappiness = 10
vm.dirty_ratio = 40
vm.dirty_background_ratio = 10
EOF
    
    sysctl -p
    
    log_success "系统参数已优化"
}

# 创建部署目录
create_deploy_dir() {
    local username="${1:-ubuntu}"
    
    log_info "创建部署目录..."
    
    mkdir -p /home/$username/teachproxy
    chown $username:$username /home/$username/teachproxy
    
    log_success "部署目录已创建: /home/$username/teachproxy"
}

# 清理系统
cleanup() {
    log_info "清理系统..."
    apt-get autoremove -y
    apt-get autoclean
    log_success "系统已清理"
}

# 显示完成信息
show_summary() {
    local username="${1:-ubuntu}"
    
    echo ""
    echo "========================================"
    log_success "服务器初始化完成！"
    echo "========================================"
    echo ""
    echo "已安装："
    echo "  ✓ Docker"
    echo "  ✓ Docker Compose"
    echo "  ✓ 基础工具 (git, vim, htop 等)"
    echo "  ✓ 防火墙 (UFW)"
    echo "  ✓ 入侵防护 (fail2ban)"
    echo ""
    echo "已配置："
    echo "  ✓ 时区 (Asia/Shanghai)"
    echo "  ✓ 防火墙规则"
    echo "  ✓ 系统优化参数"
    echo ""
    echo "下一步："
    echo "1. 重新登录服务器使 Docker 权限生效"
    echo "2. 在本地运行 ./scripts/setup-ssh.sh 配置 SSH 密钥"
    echo "3. 在本地运行 ./scripts/generate-secrets.sh 生成配置"
    echo "4. 在本地运行 ./scripts/setup-github-secrets.sh 设置 Secrets"
    echo "5. 推送代码触发自动部署"
    echo ""
    echo "防火墙状态:"
    ufw status
}

# 主流程
main() {
    echo "========================================"
    echo "🖥️  TeachProxy 服务器初始化"
    echo "========================================"
    echo ""
    
    check_root
    
    read -p "请输入部署用户名 [ubuntu]: " username
    username=${username:-ubuntu}
    
    log_info "开始初始化 (用户: $username)..."
    
    update_system
    install_base_tools
    install_docker
    setup_docker_user "$username"
    install_docker_compose
    setup_firewall
    setup_fail2ban
    setup_timezone
    optimize_system
    create_deploy_dir "$username"
    cleanup
    
    show_summary "$username"
}

# 运行
main
