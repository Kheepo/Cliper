#!/bin/bash

# Production Deployment Script for Cliper API
# This script handles the complete production deployment process

set -e  # Exit on any error

# Configuration
APP_NAME="cliper"
DOCKER_REGISTRY="your-registry.com"  # Replace with your registry
IMAGE_TAG="${1:-latest}"
ENV_FILE=".env.production"
BACKUP_DIR="/opt/backups/cliper"
LOG_FILE="/var/log/cliper-deploy.log"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging function
log() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') - $1" | tee -a "$LOG_FILE"
}

log_info() {
    echo -e "${BLUE}[INFO]${NC} $1" | tee -a "$LOG_FILE"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1" | tee -a "$LOG_FILE"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1" | tee -a "$LOG_FILE"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1" | tee -a "$LOG_FILE"
}

# Check prerequisites
check_prerequisites() {
    log_info "Checking prerequisites..."
    
    # Check if running as root or with sudo
    if [[ $EUID -ne 0 ]]; then
        log_error "This script must be run as root or with sudo"
        exit 1
    fi
    
    # Check if Docker is installed and running
    if ! command -v docker &> /dev/null; then
        log_error "Docker is not installed"
        exit 1
    fi
    
    if ! docker info &> /dev/null; then
        log_error "Docker daemon is not running"
        exit 1
    fi
    
    # Check if Docker Compose is installed
    if ! command -v docker-compose &> /dev/null; then
        log_error "Docker Compose is not installed"
        exit 1
    fi
    
    # Check if environment file exists
    if [[ ! -f "$ENV_FILE" ]]; then
        log_error "Environment file $ENV_FILE not found"
        exit 1
    fi
    
    log_success "Prerequisites check passed"
}

# Create backup
create_backup() {
    log_info "Creating backup..."
    
    BACKUP_TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
    BACKUP_PATH="$BACKUP_DIR/backup_$BACKUP_TIMESTAMP"
    
    mkdir -p "$BACKUP_PATH"
    
    # Backup current deployment
    if docker-compose ps | grep -q "Up"; then
        log_info "Backing up current deployment..."
        
        # Export current containers
        docker-compose config > "$BACKUP_PATH/docker-compose.yml"
        
        # Backup volumes
        docker run --rm -v cliper_redis_data:/data -v "$BACKUP_PATH":/backup alpine tar czf /backup/redis_data.tar.gz -C /data .
        
        # Backup logs
        cp -r logs "$BACKUP_PATH/" 2>/dev/null || true
        
        # Backup uploads
        cp -r uploads "$BACKUP_PATH/" 2>/dev/null || true
        
        log_success "Backup created at $BACKUP_PATH"
    else
        log_warning "No running containers found, skipping backup"
    fi
}

# Pull latest images
pull_images() {
    log_info "Pulling latest images..."
    
    # Pull base images
    docker pull redis:7-alpine
    docker pull nginx:alpine
    docker pull python:3.11-slim
    docker pull node:18-alpine
    
    log_success "Images pulled successfully"
}

# Build application image
build_image() {
    log_info "Building application image..."
    
    # Build the main application image
    docker build -t "$APP_NAME:$IMAGE_TAG" .
    
    # Tag for registry if specified
    if [[ "$DOCKER_REGISTRY" != "your-registry.com" ]]; then
        docker tag "$APP_NAME:$IMAGE_TAG" "$DOCKER_REGISTRY/$APP_NAME:$IMAGE_TAG"
        log_info "Image tagged for registry: $DOCKER_REGISTRY/$APP_NAME:$IMAGE_TAG"
    fi
    
    log_success "Application image built successfully"
}

# Deploy application
deploy_application() {
    log_info "Deploying application..."
    
    # Stop existing containers gracefully
    if docker-compose ps | grep -q "Up"; then
        log_info "Stopping existing containers..."
        docker-compose down --timeout 30
    fi
    
    # Start new deployment
    log_info "Starting new deployment..."
    docker-compose --env-file "$ENV_FILE" up -d
    
    # Wait for services to be healthy
    log_info "Waiting for services to be healthy..."
    sleep 30
    
    # Check service health
    check_service_health
    
    log_success "Application deployed successfully"
}

# Check service health
check_service_health() {
    log_info "Checking service health..."
    
    local max_attempts=30
    local attempt=1
    
    while [[ $attempt -le $max_attempts ]]; do
        if curl -f http://localhost/health &> /dev/null; then
            log_success "Health check passed"
            return 0
        fi
        
        log_info "Health check attempt $attempt/$max_attempts failed, retrying in 10 seconds..."
        sleep 10
        ((attempt++))
    done
    
    log_error "Health check failed after $max_attempts attempts"
    return 1
}

# Run database migrations
run_migrations() {
    log_info "Running database migrations..."
    
    # Run any pending migrations
    docker-compose exec -T api python -c "
    import asyncio
    from api.database.migrations import run_migrations
    asyncio.run(run_migrations())
    " || log_warning "Migration script not found or failed"
    
    log_success "Migrations completed"
}

# Clean up old images and containers
cleanup() {
    log_info "Cleaning up old images and containers..."
    
    # Remove old containers
    docker container prune -f
    
    # Remove old images (keep last 3 versions)
    docker images "$APP_NAME" --format "table {{.Repository}}:{{.Tag}}\t{{.CreatedAt}}" | \
        tail -n +2 | sort -k2 -r | tail -n +4 | awk '{print $1}' | \
        xargs -r docker rmi
    
    # Remove unused volumes (be careful with this)
    # docker volume prune -f
    
    log_success "Cleanup completed"
}

# Setup monitoring
setup_monitoring() {
    log_info "Setting up monitoring..."
    
    # Create monitoring directories
    mkdir -p /var/log/cliper
    mkdir -p /opt/cliper/monitoring
    
    # Setup log rotation
    cat > /etc/logrotate.d/cliper << EOF
/var/log/cliper/*.log {
    daily
    missingok
    rotate 30
    compress
    delaycompress
    notifempty
    create 644 root root
    postrotate
        docker-compose restart api celery-worker celery-beat
    endscript
}
EOF
    
    log_success "Monitoring setup completed"
}

# Main deployment function
main() {
    log_info "Starting production deployment for $APP_NAME:$IMAGE_TAG"
    
    check_prerequisites
    create_backup
    pull_images
    build_image
    deploy_application
    run_migrations
    setup_monitoring
    cleanup
    
    log_success "Production deployment completed successfully!"
    log_info "Application is available at: https://your-domain.com"
    log_info "Monitoring dashboard: https://your-domain.com/monitoring"
    log_info "Flower (Celery monitoring): http://your-domain.com:5555"
}

# Handle script interruption
trap 'log_error "Deployment interrupted"; exit 1' INT TERM

# Run main function
main "$@"