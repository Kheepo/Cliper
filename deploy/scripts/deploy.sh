#!/bin/bash

# Cliper Production Deployment Script
# Automated deployment procedures for production environment

set -euo pipefail

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
DEPLOY_DIR="$PROJECT_ROOT/deploy"
DATE=$(date +"%Y%m%d_%H%M%S")
DEPLOYMENT_LOG="/var/log/cliper_deploy_$DATE.log"

# Logging
exec 1> >(tee -a "$DEPLOYMENT_LOG")
exec 2>&1

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1"
}

# Function to display usage
usage() {
    cat << EOF
Usage: $0 [OPTIONS] ENVIRONMENT

Environments:
    staging     Deploy to staging environment
    production  Deploy to production environment

Options:
    -h, --help              Show this help message
    -f, --force             Force deployment without confirmation
    -b, --backup            Create backup before deployment
    -r, --rollback VERSION  Rollback to specific version
    -s, --skip-tests        Skip running tests
    -q, --quick             Quick deployment (skip non-essential steps)
    --dry-run               Show what would be deployed without executing
    --health-check          Perform health check only
    --list-versions         List available versions

Examples:
    $0 staging
    $0 production --backup
    $0 --rollback v1.2.3 production
    $0 --dry-run production
    $0 --health-check

EOF
}

# Function to check prerequisites
check_prerequisites() {
    log "Checking deployment prerequisites..."
    
    # Check required commands
    local required_commands=("docker" "docker-compose" "git" "curl" "jq")
    for cmd in "${required_commands[@]}"; do
        if ! command -v "$cmd" >/dev/null 2>&1; then
            log "ERROR: Required command not found: $cmd"
            return 1
        fi
    done
    
    # Check Docker daemon
    if ! docker info >/dev/null 2>&1; then
        log "ERROR: Docker daemon is not running"
        return 1
    fi
    
    # Check disk space
    local available_space=$(df /opt/cliper | awk 'NR==2 {print $4}')
    local required_space=5242880  # 5GB in KB
    if [ "$available_space" -lt "$required_space" ]; then
        log "ERROR: Insufficient disk space. Required: 5GB, Available: $((available_space/1024/1024))GB"
        return 1
    fi
    
    # Check memory
    local available_memory=$(free -m | awk 'NR==2{print $7}')
    local required_memory=4096  # 4GB in MB
    if [ "$available_memory" -lt "$required_memory" ]; then
        log "ERROR: Insufficient memory. Required: 4GB, Available: ${available_memory}MB"
        return 1
    fi
    
    log "Prerequisites check passed"
    return 0
}

# Function to validate environment
validate_environment() {
    local env=$1
    
    log "Validating $env environment..."
    
    # Check environment configuration
    local env_file="$DEPLOY_DIR/config/${env}.env"
    if [ ! -f "$env_file" ]; then
        log "ERROR: Environment file not found: $env_file"
        return 1
    fi
    
    # Check Docker Compose file
    local compose_file="$DEPLOY_DIR/config/docker-compose.${env}.yml"
    if [ ! -f "$compose_file" ]; then
        log "ERROR: Docker Compose file not found: $compose_file"
        return 1
    fi
    
    # Validate Docker Compose configuration
    if ! docker-compose -f "$compose_file" config >/dev/null 2>&1; then
        log "ERROR: Invalid Docker Compose configuration"
        return 1
    fi
    
    log "Environment validation passed"
    return 0
}

# Function to run tests
run_tests() {
    log "Running test suite..."
    
    cd "$PROJECT_ROOT"
    
    # Run unit tests
    log "Running unit tests..."
    if ! python -m pytest tests/unit/ -v --tb=short; then
        log "ERROR: Unit tests failed"
        return 1
    fi
    
    # Run integration tests
    log "Running integration tests..."
    if ! python -m pytest tests/integration/ -v --tb=short; then
        log "ERROR: Integration tests failed"
        return 1
    fi
    
    # Run security tests
    log "Running security tests..."
    if command -v bandit >/dev/null 2>&1; then
        if ! bandit -r api/ -f json -o security_report.json; then
            log "WARNING: Security issues found, check security_report.json"
        fi
    fi
    
    log "All tests passed"
    return 0
}

# Function to build Docker images
build_images() {
    local env=$1
    
    log "Building Docker images for $env..."
    
    cd "$PROJECT_ROOT"
    
    # Build backend image
    log "Building backend image..."
    if ! docker build -f Dockerfile.backend -t "cliper/backend:$DATE" -t "cliper/backend:latest" .; then
        log "ERROR: Failed to build backend image"
        return 1
    fi
    
    # Build frontend image
    log "Building frontend image..."
    if ! docker build -f Dockerfile.frontend -t "cliper/frontend:$DATE" -t "cliper/frontend:latest" .; then
        log "ERROR: Failed to build frontend image"
        return 1
    fi
    
    # Build worker image
    log "Building worker image..."
    if ! docker build -f Dockerfile.worker -t "cliper/worker:$DATE" -t "cliper/worker:latest" .; then
        log "ERROR: Failed to build worker image"
        return 1
    fi
    
    # Build scheduler image
    log "Building scheduler image..."
    if ! docker build -f Dockerfile.scheduler -t "cliper/scheduler:$DATE" -t "cliper/scheduler:latest" .; then
        log "ERROR: Failed to build scheduler image"
        return 1
    fi
    
    # Build backup image
    log "Building backup image..."
    if ! docker build -f Dockerfile.backup -t "cliper/backup:$DATE" -t "cliper/backup:latest" .; then
        log "ERROR: Failed to build backup image"
        return 1
    fi
    
    log "Docker images built successfully"
    return 0
}

# Function to create backup
create_backup() {
    log "Creating pre-deployment backup..."
    
    if [ -f "$SCRIPT_DIR/backup.sh" ]; then
        if bash "$SCRIPT_DIR/backup.sh"; then
            log "Backup created successfully"
            return 0
        else
            log "ERROR: Backup creation failed"
            return 1
        fi
    else
        log "WARNING: Backup script not found, skipping backup"
        return 0
    fi
}

# Function to deploy services
deploy_services() {
    local env=$1
    local compose_file="$DEPLOY_DIR/config/docker-compose.${env}.yml"
    
    log "Deploying services for $env environment..."
    
    cd "$DEPLOY_DIR/config"
    
    # Pull latest images
    log "Pulling latest images..."
    docker-compose -f "docker-compose.${env}.yml" pull || true
    
    # Stop existing services
    log "Stopping existing services..."
    docker-compose -f "docker-compose.${env}.yml" down --remove-orphans
    
    # Start infrastructure services first
    log "Starting infrastructure services..."
    docker-compose -f "docker-compose.${env}.yml" up -d postgres redis
    
    # Wait for infrastructure to be ready
    log "Waiting for infrastructure services..."
    sleep 30
    
    # Start application services
    log "Starting application services..."
    docker-compose -f "docker-compose.${env}.yml" up -d backend worker scheduler
    
    # Wait for application services
    log "Waiting for application services..."
    sleep 30
    
    # Start frontend and proxy
    log "Starting frontend and proxy services..."
    docker-compose -f "docker-compose.${env}.yml" up -d frontend nginx
    
    # Start monitoring services
    log "Starting monitoring services..."
    docker-compose -f "docker-compose.${env}.yml" up -d prometheus grafana alertmanager
    
    # Start logging services
    log "Starting logging services..."
    docker-compose -f "docker-compose.${env}.yml" up -d elasticsearch logstash kibana filebeat
    
    # Start system monitoring
    log "Starting system monitoring..."
    docker-compose -f "docker-compose.${env}.yml" up -d node-exporter cadvisor
    
    # Start backup service
    log "Starting backup service..."
    docker-compose -f "docker-compose.${env}.yml" up -d backup
    
    log "Services deployed successfully"
    return 0
}

# Function to run database migrations
run_migrations() {
    log "Running database migrations..."
    
    # Wait for database to be ready
    local max_attempts=30
    local attempt=1
    
    while [ $attempt -le $max_attempts ]; do
        if docker-compose -f "$DEPLOY_DIR/config/docker-compose.${ENVIRONMENT}.yml" exec -T postgres \
            pg_isready -U "$POSTGRES_USER" -d "$POSTGRES_DB" >/dev/null 2>&1; then
            break
        fi
        log "Waiting for database (attempt $attempt/$max_attempts)..."
        sleep 10
        ((attempt++))
    done
    
    if [ $attempt -gt $max_attempts ]; then
        log "ERROR: Database not ready after $max_attempts attempts"
        return 1
    fi
    
    # Run migrations
    if docker-compose -f "$DEPLOY_DIR/config/docker-compose.${ENVIRONMENT}.yml" exec -T backend \
        python -m alembic upgrade head; then
        log "Database migrations completed successfully"
        return 0
    else
        log "ERROR: Database migrations failed"
        return 1
    fi
}

# Function to perform health checks
health_check() {
    local env=$1
    
    log "Performing health checks for $env environment..."
    
    local max_attempts=20
    local attempt=1
    local all_healthy=false
    
    while [ $attempt -le $max_attempts ] && [ "$all_healthy" = false ]; do
        log "Health check attempt $attempt/$max_attempts"
        all_healthy=true
        
        # Check PostgreSQL
        if ! docker-compose -f "$DEPLOY_DIR/config/docker-compose.${env}.yml" exec -T postgres \
            pg_isready -U "$POSTGRES_USER" -d "$POSTGRES_DB" >/dev/null 2>&1; then
            log "PostgreSQL health check failed"
            all_healthy=false
        fi
        
        # Check Redis
        if ! docker-compose -f "$DEPLOY_DIR/config/docker-compose.${env}.yml" exec -T redis \
            redis-cli ping | grep -q PONG; then
            log "Redis health check failed"
            all_healthy=false
        fi
        
        # Check backend API
        if ! curl -f http://localhost:8000/health/ready >/dev/null 2>&1; then
            log "Backend API health check failed"
            all_healthy=false
        fi
        
        # Check frontend
        if ! curl -f http://localhost >/dev/null 2>&1; then
            log "Frontend health check failed"
            all_healthy=false
        fi
        
        if [ "$all_healthy" = true ]; then
            log "All health checks passed"
            return 0
        fi
        
        sleep 30
        ((attempt++))
    done
    
    log "ERROR: Health checks failed after $max_attempts attempts"
    return 1
}

# Function to rollback deployment
rollback_deployment() {
    local version=$1
    local env=$2
    
    log "Rolling back to version $version in $env environment..."
    
    # Stop current services
    docker-compose -f "$DEPLOY_DIR/config/docker-compose.${env}.yml" down
    
    # Tag rollback images
    docker tag "cliper/backend:$version" "cliper/backend:latest"
    docker tag "cliper/frontend:$version" "cliper/frontend:latest"
    docker tag "cliper/worker:$version" "cliper/worker:latest"
    docker tag "cliper/scheduler:$version" "cliper/scheduler:latest"
    
    # Deploy with rollback images
    deploy_services "$env"
    
    # Run health checks
    if health_check "$env"; then
        log "Rollback completed successfully"
        return 0
    else
        log "ERROR: Rollback health checks failed"
        return 1
    fi
}

# Function to list available versions
list_versions() {
    log "Available versions:"
    docker images cliper/backend --format "table {{.Tag}}\t{{.CreatedAt}}\t{{.Size}}" | head -20
}

# Function to send notification
send_notification() {
    local status=$1
    local message=$2
    local env=$3
    
    # Slack notification
    if [ -n "${SLACK_WEBHOOK_URL:-}" ]; then
        curl -X POST -H 'Content-type: application/json' \
            --data "{\"text\":\"Deployment $status ($env): $message\"}" \
            "$SLACK_WEBHOOK_URL" || true
    fi
    
    # Email notification
    if [ -n "${SMTP_SERVER:-}" ] && [ -n "${DEPLOY_EMAIL:-}" ]; then
        echo "Subject: Cliper Deployment $status ($env)\n\n$message" | \
            sendmail "$DEPLOY_EMAIL" || true
    fi
}

# Function to cleanup old images
cleanup_old_images() {
    log "Cleaning up old Docker images..."
    
    # Remove dangling images
    docker image prune -f || true
    
    # Keep only last 5 versions of each image
    for image in backend frontend worker scheduler backup; do
        docker images "cliper/$image" --format "{{.Tag}}" | \
            grep -E '^[0-9]{8}_[0-9]{6}$' | \
            sort -r | \
            tail -n +6 | \
            xargs -r -I {} docker rmi "cliper/$image:{}" || true
    done
    
    log "Image cleanup completed"
}

# Main deployment function
main() {
    local environment=""
    local force=false
    local backup=false
    local rollback_version=""
    local skip_tests=false
    local quick=false
    local dry_run=false
    local health_check_only=false
    local start_time=$(date +%s)
    
    # Parse command line arguments
    while [[ $# -gt 0 ]]; do
        case $1 in
            -h|--help)
                usage
                exit 0
                ;;
            -f|--force)
                force=true
                shift
                ;;
            -b|--backup)
                backup=true
                shift
                ;;
            -r|--rollback)
                rollback_version="$2"
                shift 2
                ;;
            -s|--skip-tests)
                skip_tests=true
                shift
                ;;
            -q|--quick)
                quick=true
                shift
                ;;
            --dry-run)
                dry_run=true
                shift
                ;;
            --health-check)
                health_check_only=true
                shift
                ;;
            --list-versions)
                list_versions
                exit 0
                ;;
            staging|production)
                environment="$1"
                shift
                ;;
            -*)
                log "ERROR: Unknown option $1"
                usage
                exit 1
                ;;
            *)
                log "ERROR: Unknown argument $1"
                usage
                exit 1
                ;;
        esac
    done
    
    # Health check only mode
    if [ "$health_check_only" = true ]; then
        if [ -z "$environment" ]; then
            environment="production"
        fi
        health_check "$environment"
        exit $?
    fi
    
    # Validate environment
    if [ -z "$environment" ]; then
        log "ERROR: Environment not specified"
        usage
        exit 1
    fi
    
    log "=== Cliper Deployment Started ==="
    log "Environment: $environment"
    log "Date: $DATE"
    log "Log file: $DEPLOYMENT_LOG"
    
    # Load environment variables
    if [ -f "$DEPLOY_DIR/config/${environment}.env" ]; then
        set -a
        source "$DEPLOY_DIR/config/${environment}.env"
        set +a
        export ENVIRONMENT="$environment"
    fi
    
    # Dry run mode
    if [ "$dry_run" = true ]; then
        log "DRY RUN MODE: Showing what would be deployed"
        log "Environment: $environment"
        log "Images to be built: backend, frontend, worker, scheduler, backup"
        log "Services to be deployed:"
        docker-compose -f "$DEPLOY_DIR/config/docker-compose.${environment}.yml" config --services
        exit 0
    fi
    
    # Rollback mode
    if [ -n "$rollback_version" ]; then
        log "Rollback mode: $rollback_version"
        if rollback_deployment "$rollback_version" "$environment"; then
            send_notification "SUCCESS" "Rollback to $rollback_version completed" "$environment"
        else
            send_notification "FAILED" "Rollback to $rollback_version failed" "$environment"
            exit 1
        fi
        exit 0
    fi
    
    # Check prerequisites
    if ! check_prerequisites; then
        log "ERROR: Prerequisites check failed"
        exit 1
    fi
    
    # Validate environment
    if ! validate_environment "$environment"; then
        log "ERROR: Environment validation failed"
        exit 1
    fi
    
    # Confirmation prompt for production
    if [ "$environment" = "production" ] && [ "$force" = false ]; then
        echo "WARNING: You are about to deploy to PRODUCTION environment."
        echo "This will affect live users and services."
        echo "Continue? (yes/no): "
        read -r confirmation
        if [ "$confirmation" != "yes" ]; then
            log "Deployment cancelled by user"
            exit 0
        fi
    fi
    
    # Create backup if requested
    if [ "$backup" = true ]; then
        if ! create_backup; then
            log "ERROR: Backup creation failed"
            exit 1
        fi
    fi
    
    # Run tests unless skipped
    if [ "$skip_tests" = false ] && [ "$quick" = false ]; then
        if ! run_tests; then
            log "ERROR: Tests failed"
            exit 1
        fi
    fi
    
    # Build Docker images
    if ! build_images "$environment"; then
        log "ERROR: Image building failed"
        exit 1
    fi
    
    # Deploy services
    if ! deploy_services "$environment"; then
        log "ERROR: Service deployment failed"
        exit 1
    fi
    
    # Run database migrations
    if ! run_migrations; then
        log "ERROR: Database migrations failed"
        exit 1
    fi
    
    # Perform health checks
    if ! health_check "$environment"; then
        log "ERROR: Health checks failed"
        send_notification "FAILED" "Deployment health checks failed" "$environment"
        exit 1
    fi
    
    # Cleanup old images unless quick mode
    if [ "$quick" = false ]; then
        cleanup_old_images
    fi
    
    # Success notification
    local end_time=$(date +%s)
    local duration=$((end_time - start_time))
    local message="Deployment completed successfully in ${duration}s"
    log "$message"
    send_notification "SUCCESS" "$message" "$environment"
    
    log "=== Cliper Deployment Completed ==="
}

# Execute main function
main "$@"