#!/bin/bash
# ============================================
# TeachProxy 手动部署脚本
# 用于首次部署或手动更新
# ============================================

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 配置
DEPLOY_DIR="${DEPLOY_DIR:-$HOME/teachproxy}"
DOMAIN="${DOMAIN:-}"

# 打印带颜色的信息
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

# 检查依赖
check_dependencies() {
    log_info "Checking dependencies..."
    
    command -v docker >/dev/null 2>&1 || { log_error "Docker is required but not installed."; exit 1; }
    command -v docker-compose >/dev/null 2>&1 || { log_error "Docker Compose is required but not installed."; exit 1; }
    
    log_success "Dependencies check passed"
}

# 创建部署目录
setup_directory() {
    log_info "Setting up deployment directory..."
    
    mkdir -p "$DEPLOY_DIR"
    mkdir -p "$DEPLOY_DIR/nginx/conf.d"
    
    log_success "Directory created at $DEPLOY_DIR"
}

# 复制文件
copy_files() {
    log_info "Copying deployment files..."
    
    # 检查是否在项目根目录
    if [ ! -f "docker-compose.yml" ]; then
        log_error "Please run this script from project root directory"
        exit 1
    fi
    
    cp docker-compose.yml "$DEPLOY_DIR/"
    cp Dockerfile "$DEPLOY_DIR/"
    cp -r nginx "$DEPLOY_DIR/"
    
    log_success "Files copied"
}

# 设置环境变量
setup_env() {
    log_info "Setting up environment variables..."
    
    ENV_FILE="$DEPLOY_DIR/.env"
    
    if [ ! -f "$ENV_FILE" ]; then
        log_warn ".env file not found, creating from .env.production..."
        
        if [ -f ".env.production" ]; then
            cp .env.production "$ENV_FILE"
            log_warn "Please edit $ENV_FILE with your actual values before continuing!"
            exit 1
        else
            log_error ".env.production not found. Please create $ENV_FILE manually."
            exit 1
        fi
    fi
    
    # 加载环境变量
    export $(grep -v '^#' "$ENV_FILE" | xargs)
    
    log_success "Environment loaded"
}

# 生成 Nginx 配置
generate_nginx_config() {
    log_info "Generating Nginx configuration..."
    
    if [ -z "$DOMAIN" ]; then
        log_warn "DOMAIN not set, using template without SSL"
        cp "$DEPLOY_DIR/nginx/conf.d/default.conf" "$DEPLOY_DIR/nginx/conf.d/app.conf"
    else
        log_info "Generating config for domain: $DOMAIN"
        export DOMAIN
        envsubst '\${DOMAIN}' < "$DEPLOY_DIR/nginx/conf.d/app.conf.template" > "$DEPLOY_DIR/nginx/conf.d/app.conf"
        log_success "Nginx config generated"
    fi
}

# 初始化 SSL 证书
init_ssl() {
    if [ -z "$DOMAIN" ]; then
        log_warn "DOMAIN not set, skipping SSL initialization"
        return
    fi
    
    log_info "Initializing SSL certificate for $DOMAIN..."
    
    # 启动 nginx 以便 certbot 可以验证
    cd "$DEPLOY_DIR"
    docker-compose up -d nginx
    
    # 等待 nginx 启动
    sleep 5
    
    # 申请证书
    docker-compose run --rm certbot certonly \
        --webroot \
        --webroot-path=/var/www/certbot \
        --email admin@$DOMAIN \
        --agree-tos \
        --no-eff-email \
        -d $DOMAIN
    
    log_success "SSL certificate initialized"
}

# 构建和启动服务
deploy() {
    log_info "Building and starting services..."
    
    cd "$DEPLOY_DIR"
    
    # 构建镜像
    log_info "Building Docker images..."
    docker-compose build --no-cache
    
    # 启动服务
    log_info "Starting services..."
    docker-compose up -d
    
    # 等待服务启动
    log_info "Waiting for services to start..."
    sleep 10
    
    log_success "Services started"
}

# 健康检查
health_check() {
    log_info "Running health check..."
    
    MAX_RETRIES=10
    RETRY_COUNT=0
    
    while [ $RETRY_COUNT -lt $MAX_RETRIES ]; do
        if curl -sf http://localhost:8000/health > /dev/null 2>&1; then
            log_success "API is healthy!"
            return 0
        fi
        
        RETRY_COUNT=$((RETRY_COUNT + 1))
        log_warn "Health check attempt $RETRY_COUNT/$MAX_RETRIES failed, retrying..."
        sleep 5
    done
    
    log_error "Health check failed after $MAX_RETRIES attempts"
    docker-compose logs api --tail 50
    return 1
}

# 显示状态
show_status() {
    echo ""
    echo "========================================"
    log_success "Deployment completed!"
    echo "========================================"
    echo ""
    echo "Services:"
    docker-compose -f "$DEPLOY_DIR/docker-compose.yml" ps
    echo ""
    
    if [ -n "$DOMAIN" ]; then
        echo "🌐 Application URL: https://$DOMAIN"
    else
        echo "🌐 Application URL: http://$(curl -s ifconfig.me)"
    fi
    echo "📚 API Documentation: https://$DOMAIN/docs"
    echo ""
    echo "Useful commands:"
    echo "  View logs: docker-compose -f $DEPLOY_DIR/docker-compose.yml logs -f"
    echo "  Stop:      docker-compose -f $DEPLOY_DIR/docker-compose.yml down"
    echo "  Restart:   docker-compose -f $DEPLOY_DIR/docker-compose.yml restart"
    echo ""
}

# 主流程
main() {
    echo "🚀 TeachProxy Deployment Script"
    echo "================================"
    echo ""
    
    check_dependencies
    setup_directory
    copy_files
    setup_env
    generate_nginx_config
    
    # 询问是否初始化 SSL
    if [ -n "$DOMAIN" ]; then
        read -p "Initialize SSL certificate for $DOMAIN? (y/N) " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            init_ssl
        fi
    fi
    
    deploy
    health_check
    show_status
}

# 处理命令行参数
case "${1:-}" in
    status)
        cd "$DEPLOY_DIR" && docker-compose ps
        ;;
    logs)
        cd "$DEPLOY_DIR" && docker-compose logs -f "${2:-}"
        ;;
    restart)
        cd "$DEPLOY_DIR" && docker-compose restart
        ;;
    stop)
        cd "$DEPLOY_DIR" && docker-compose down
        ;;
    update)
        copy_files
        cd "$DEPLOY_DIR" && docker-compose up -d --build
        health_check
        ;;
    *)
        main
        ;;
esac
