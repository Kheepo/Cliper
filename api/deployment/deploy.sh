#!/bin/bash

# Video Processing System - Production Deployment Script
# Comprehensive deployment automation with health checks and rollback capabilities

set -euo pipefail

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
DEPLOYMENT_ENV="${DEPLOYMENT_ENV:-production}"
DOCKER_COMPOSE_FILE="docker-compose.prod.yml"
BACKUP_DIR="${BACKUP_DIR:-/var/backups/video-processing}"
LOG_FILE="${LOG_FILE:-/var/log/video-processing-deploy.log}"
HEALTH_CHECK_TIMEOUT="${HEALTH_CHECK_TIMEOUT:-300}"
ROLLBACK_ENABLED="${ROLLBACK_ENABLED:-true}"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging functions
log() {
    echo -e "[$(date +'%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

log_info() {
    log "${BLUE}[INFO]${NC} $1"
}

log_warn() {
    log "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    log "${RED}[ERROR]${NC} $1"
}

log_success() {
    log "${GREEN}[SUCCESS]${NC} $1"
}

# Error handling
error_exit() {
    log_error "$1"
    if [[ "$ROLLBACK_ENABLED" == "true" ]]; then
        log_warn "Initiating rollback..."
        rollback_deployment
    fi
    exit 1
}

# Cleanup function
cleanup() {
    log_info "Cleaning up temporary files..."
    # Remove any temporary files created during deployment
    rm -f /tmp/video-processing-*.tmp
}

# Set up signal handlers
trap cleanup EXIT
trap 'error_exit "Deployment interrupted by user"' INT TERM

# Validation functions
validate_environment() {
    log_info "Validating deployment environment..."
    
    # Check required commands
    local required_commands=("docker" "docker-compose" "curl" "jq")
    for cmd in "${required_commands[@]}"; do
        if ! command -v "$cmd" &> /dev/null; then
            error_exit "Required command '$cmd' not found"
        fi
    done
    
    # Check Docker daemon
    if ! docker info &> /dev/null; then
        error_exit "Docker daemon is not running"
    fi
    
    # Check available disk space (minimum 10GB)
    local available_space
    available_space=$(df "$PROJECT_ROOT" | awk 'NR==2 {print $4}')
    if [[ $available_space -lt 10485760 ]]; then  # 10GB in KB
        error_exit "Insufficient disk space. At least 10GB required."
    fi
    
    # Check environment file
    if [[ ! -f "$SCRIPT_DIR/.env.prod" ]]; then
        error_exit "Production environment file not found: $SCRIPT_DIR/.env.prod"
    fi
    
    # Validate environment variables
    source "$SCRIPT_DIR/.env.prod"
    local required_vars=("POSTGRES_PASSWORD" "REDIS_PASSWORD" "JWT_SECRET_KEY" "OPENAI_API_KEY")
    for var in "${required_vars[@]}"; do
        if [[ -z "${!var:-}" ]]; then
            error_exit "Required environment variable '$var' is not set"
        fi
    done
    
    log_success "Environment validation completed"
}

validate_configuration() {
    log_info "Validating configuration files..."
    
    # Check Docker Compose file
    if ! docker-compose -f "$SCRIPT_DIR/$DOCKER_COMPOSE_FILE" config &> /dev/null; then
        error_exit "Invalid Docker Compose configuration"
    fi
    
    # Validate Nginx configuration
    if [[ -f "$SCRIPT_DIR/nginx.prod.conf" ]]; then
        # Use nginx container to validate config
        docker run --rm -v "$SCRIPT_DIR/nginx.prod.conf:/etc/nginx/nginx.conf:ro" nginx:alpine nginx -t
        if [[ $? -ne 0 ]]; then
            error_exit "Invalid Nginx configuration"
        fi
    fi
    
    # Validate Prometheus configuration
    if [[ -f "$SCRIPT_DIR/prometheus.yml" ]]; then
        docker run --rm -v "$SCRIPT_DIR/prometheus.yml:/etc/prometheus/prometheus.yml:ro" prom/prometheus:latest promtool check config /etc/prometheus/prometheus.yml
        if [[ $? -ne 0 ]]; then
            error_exit "Invalid Prometheus configuration"
        fi
    fi
    
    log_success "Configuration validation completed"
}

# Backup functions
create_backup() {
    log_info "Creating backup before deployment..."
    
    local backup_timestamp
    backup_timestamp=$(date +"%Y%m%d_%H%M%S")
    local backup_path="$BACKUP_DIR/backup_$backup_timestamp"
    
    mkdir -p "$backup_path"
    
    # Backup database
    if docker-compose -f "$SCRIPT_DIR/$DOCKER_COMPOSE_FILE" ps postgres | grep -q "Up"; then
        log_info "Backing up PostgreSQL database..."
        docker-compose -f "$SCRIPT_DIR/$DOCKER_COMPOSE_FILE" exec -T postgres pg_dumpall -U "$POSTGRES_USER" > "$backup_path/database_backup.sql"
    fi
    
    # Backup Redis data
    if docker-compose -f "$SCRIPT_DIR/$DOCKER_COMPOSE_FILE" ps redis | grep -q "Up"; then
        log_info "Backing up Redis data..."
        docker-compose -f "$SCRIPT_DIR/$DOCKER_COMPOSE_FILE" exec -T redis redis-cli --rdb - > "$backup_path/redis_backup.rdb"
    fi
    
    # Backup application data
    if [[ -d "$PROJECT_ROOT/data" ]]; then
        log_info "Backing up application data..."
        cp -r "$PROJECT_ROOT/data" "$backup_path/"
    fi
    
    # Backup configuration
    log_info "Backing up configuration files..."
    cp -r "$SCRIPT_DIR" "$backup_path/deployment_config"
    
    # Create backup manifest
    cat > "$backup_path/manifest.json" << EOF
{
    "timestamp": "$backup_timestamp",
    "deployment_env": "$DEPLOYMENT_ENV",
    "git_commit": "$(git rev-parse HEAD 2>/dev/null || echo 'unknown')",
    "git_branch": "$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo 'unknown')",
    "backup_path": "$backup_path",
    "components": {
        "database": $([ -f "$backup_path/database_backup.sql" ] && echo "true" || echo "false"),
        "redis": $([ -f "$backup_path/redis_backup.rdb" ] && echo "true" || echo "false"),
        "application_data": $([ -d "$backup_path/data" ] && echo "true" || echo "false"),
        "configuration": $([ -d "$backup_path/deployment_config" ] && echo "true" || echo "false")
    }
}
EOF
    
    echo "$backup_path" > /tmp/video-processing-backup-path.tmp
    log_success "Backup created: $backup_path"
}

rollback_deployment() {
    log_warn "Starting deployment rollback..."
    
    local backup_path
    if [[ -f /tmp/video-processing-backup-path.tmp ]]; then
        backup_path=$(cat /tmp/video-processing-backup-path.tmp)
    else
        # Find the most recent backup
        backup_path=$(find "$BACKUP_DIR" -name "backup_*" -type d | sort -r | head -n 1)
    fi
    
    if [[ -z "$backup_path" || ! -d "$backup_path" ]]; then
        log_error "No backup found for rollback"
        return 1
    fi
    
    log_info "Rolling back to backup: $backup_path"
    
    # Stop current services
    docker-compose -f "$SCRIPT_DIR/$DOCKER_COMPOSE_FILE" down
    
    # Restore database
    if [[ -f "$backup_path/database_backup.sql" ]]; then
        log_info "Restoring database..."
        docker-compose -f "$SCRIPT_DIR/$DOCKER_COMPOSE_FILE" up -d postgres
        sleep 30  # Wait for database to be ready
        docker-compose -f "$SCRIPT_DIR/$DOCKER_COMPOSE_FILE" exec -T postgres psql -U "$POSTGRES_USER" < "$backup_path/database_backup.sql"
    fi
    
    # Restore Redis data
    if [[ -f "$backup_path/redis_backup.rdb" ]]; then
        log_info "Restoring Redis data..."
        docker-compose -f "$SCRIPT_DIR/$DOCKER_COMPOSE_FILE" down redis
        # Copy backup to Redis data volume
        docker run --rm -v "video-processing_redis_data:/data" -v "$backup_path:/backup" alpine cp /backup/redis_backup.rdb /data/dump.rdb
        docker-compose -f "$SCRIPT_DIR/$DOCKER_COMPOSE_FILE" up -d redis
    fi
    
    # Restore application data
    if [[ -d "$backup_path/data" ]]; then
        log_info "Restoring application data..."
        rm -rf "$PROJECT_ROOT/data"
        cp -r "$backup_path/data" "$PROJECT_ROOT/"
    fi
    
    # Start all services
    docker-compose -f "$SCRIPT_DIR/$DOCKER_COMPOSE_FILE" up -d
    
    log_success "Rollback completed"
}

# Build and deployment functions
build_images() {
    log_info "Building Docker images..."
    
    cd "$SCRIPT_DIR"
    
    # Build API image
    log_info "Building API image..."
    docker build -f Dockerfile.prod -t video-processing-api:latest "$PROJECT_ROOT"
    
    # Build worker image
    log_info "Building worker image..."
    docker build -f Dockerfile.worker -t video-processing-worker:latest "$PROJECT_ROOT"
    
    # Tag images with timestamp
    local timestamp
    timestamp=$(date +"%Y%m%d_%H%M%S")
    docker tag video-processing-api:latest "video-processing-api:$timestamp"
    docker tag video-processing-worker:latest "video-processing-worker:$timestamp"
    
    log_success "Docker images built successfully"
}

deploy_infrastructure() {
    log_info "Deploying infrastructure services..."
    
    cd "$SCRIPT_DIR"
    
    # Start infrastructure services first
    docker-compose -f "$DOCKER_COMPOSE_FILE" up -d postgres redis
    
    # Wait for database to be ready
    log_info "Waiting for PostgreSQL to be ready..."
    local retries=0
    while ! docker-compose -f "$DOCKER_COMPOSE_FILE" exec postgres pg_isready -U "$POSTGRES_USER" &> /dev/null; do
        if [[ $retries -ge 30 ]]; then
            error_exit "PostgreSQL failed to start within timeout"
        fi
        sleep 5
        ((retries++))
    done
    
    # Wait for Redis to be ready
    log_info "Waiting for Redis to be ready..."
    retries=0
    while ! docker-compose -f "$DOCKER_COMPOSE_FILE" exec redis redis-cli ping &> /dev/null; do
        if [[ $retries -ge 30 ]]; then
            error_exit "Redis failed to start within timeout"
        fi
        sleep 5
        ((retries++))
    done
    
    log_success "Infrastructure services deployed successfully"
}

run_migrations() {
    log_info "Running database migrations..."
    
    cd "$SCRIPT_DIR"
    
    # Run database migrations
    docker-compose -f "$DOCKER_COMPOSE_FILE" run --rm api python -m alembic upgrade head
    
    if [[ $? -ne 0 ]]; then
        error_exit "Database migrations failed"
    fi
    
    log_success "Database migrations completed"
}

deploy_application() {
    log_info "Deploying application services..."
    
    cd "$SCRIPT_DIR"
    
    # Deploy monitoring services
    docker-compose -f "$DOCKER_COMPOSE_FILE" up -d prometheus grafana
    
    # Deploy application services
    docker-compose -f "$DOCKER_COMPOSE_FILE" up -d api worker beat
    
    # Deploy reverse proxy
    docker-compose -f "$DOCKER_COMPOSE_FILE" up -d nginx
    
    # Deploy additional monitoring
    docker-compose -f "$DOCKER_COMPOSE_FILE" up -d flower
    
    log_success "Application services deployed successfully"
}

# Health check functions
check_service_health() {
    local service_name="$1"
    local health_url="$2"
    local timeout="${3:-60}"
    
    log_info "Checking health of $service_name..."
    
    local retries=0
    local max_retries=$((timeout / 5))
    
    while [[ $retries -lt $max_retries ]]; do
        if curl -f -s "$health_url" &> /dev/null; then
            log_success "$service_name is healthy"
            return 0
        fi
        
        sleep 5
        ((retries++))
        log_info "Waiting for $service_name to be healthy... ($retries/$max_retries)"
    done
    
    log_error "$service_name health check failed"
    return 1
}

run_health_checks() {
    log_info "Running comprehensive health checks..."
    
    local health_check_failed=false
    
    # Check API health
    if ! check_service_health "API" "http://localhost:8000/health" 120; then
        health_check_failed=true
    fi
    
    # Check database connectivity
    if ! docker-compose -f "$SCRIPT_DIR/$DOCKER_COMPOSE_FILE" exec postgres pg_isready -U "$POSTGRES_USER" &> /dev/null; then
        log_error "Database health check failed"
        health_check_failed=true
    fi
    
    # Check Redis connectivity
    if ! docker-compose -f "$SCRIPT_DIR/$DOCKER_COMPOSE_FILE" exec redis redis-cli ping &> /dev/null; then
        log_error "Redis health check failed"
        health_check_failed=true
    fi
    
    # Check Celery workers
    if ! check_service_health "Flower" "http://localhost:5555" 60; then
        log_warn "Flower health check failed (non-critical)"
    fi
    
    # Check Prometheus
    if ! check_service_health "Prometheus" "http://localhost:9090/-/healthy" 60; then
        log_warn "Prometheus health check failed (non-critical)"
    fi
    
    # Check Grafana
    if ! check_service_health "Grafana" "http://localhost:3000/api/health" 60; then
        log_warn "Grafana health check failed (non-critical)"
    fi
    
    if [[ "$health_check_failed" == "true" ]]; then
        error_exit "Critical health checks failed"
    fi
    
    log_success "All critical health checks passed"
}

# Performance validation
run_performance_tests() {
    log_info "Running performance validation tests..."
    
    # Test API response time
    local response_time
    response_time=$(curl -o /dev/null -s -w "%{time_total}" "http://localhost:8000/health")
    
    if (( $(echo "$response_time > 2.0" | bc -l) )); then
        log_warn "API response time is high: ${response_time}s"
    else
        log_success "API response time is acceptable: ${response_time}s"
    fi
    
    # Test database connection pool
    local db_connections
    db_connections=$(docker-compose -f "$SCRIPT_DIR/$DOCKER_COMPOSE_FILE" exec postgres psql -U "$POSTGRES_USER" -t -c "SELECT count(*) FROM pg_stat_activity;" | tr -d ' ')
    
    log_info "Active database connections: $db_connections"
    
    # Test Redis performance
    local redis_ping
    redis_ping=$(docker-compose -f "$SCRIPT_DIR/$DOCKER_COMPOSE_FILE" exec redis redis-cli --latency-history -i 1 | head -n 1 | awk '{print $4}')
    
    log_info "Redis latency: ${redis_ping}ms"
    
    log_success "Performance validation completed"
}

# Cleanup old resources
cleanup_old_resources() {
    log_info "Cleaning up old resources..."
    
    # Remove old Docker images (keep last 3 versions)
    docker images video-processing-api --format "table {{.Tag}}\t{{.ID}}" | tail -n +2 | sort -r | tail -n +4 | awk '{print $2}' | xargs -r docker rmi
    docker images video-processing-worker --format "table {{.Tag}}\t{{.ID}}" | tail -n +2 | sort -r | tail -n +4 | awk '{print $2}' | xargs -r docker rmi
    
    # Remove old backups (keep last 7 days)
    find "$BACKUP_DIR" -name "backup_*" -type d -mtime +7 -exec rm -rf {} +
    
    # Clean up Docker system
    docker system prune -f
    
    log_success "Resource cleanup completed"
}

# Main deployment function
main() {
    log_info "Starting Video Processing System deployment..."
    log_info "Deployment environment: $DEPLOYMENT_ENV"
    log_info "Project root: $PROJECT_ROOT"
    log_info "Script directory: $SCRIPT_DIR"
    
    # Pre-deployment validation
    validate_environment
    validate_configuration
    
    # Create backup
    create_backup
    
    # Build and deploy
    build_images
    deploy_infrastructure
    run_migrations
    deploy_application
    
    # Post-deployment validation
    run_health_checks
    run_performance_tests
    
    # Cleanup
    cleanup_old_resources
    
    log_success "Deployment completed successfully!"
    log_info "Services are available at:"
    log_info "  - API: http://localhost:8000"
    log_info "  - Grafana: http://localhost:3000 (admin/admin)"
    log_info "  - Prometheus: http://localhost:9090"
    log_info "  - Flower: http://localhost:5555"
    
    # Display deployment summary
    cat << EOF

${GREEN}=== DEPLOYMENT SUMMARY ===${NC}
Timestamp: $(date)
Environment: $DEPLOYMENT_ENV
Git Commit: $(git rev-parse HEAD 2>/dev/null || echo 'unknown')
Git Branch: $(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo 'unknown')
Backup Location: $(cat /tmp/video-processing-backup-path.tmp 2>/dev/null || echo 'none')
Log File: $LOG_FILE

${BLUE}Next Steps:${NC}
1. Monitor the application logs: docker-compose -f $DOCKER_COMPOSE_FILE logs -f
2. Check Grafana dashboards for system metrics
3. Verify video processing functionality
4. Set up external monitoring and alerting

EOF
}

# Script entry point
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi