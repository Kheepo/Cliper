#!/bin/bash

# Staging Deployment Script for Cliper API
# This script handles staging environment deployment with testing features

set -e  # Exit on any error

# Configuration
APP_NAME="cliper-staging"
IMAGE_TAG="${1:-staging}"
ENV_FILE=".env.staging"
LOG_FILE="/var/log/cliper-staging-deploy.log"
STAGING_URL="https://staging.your-domain.com"

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
    log_info "Checking prerequisites for staging deployment..."
    
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
        log_warning "Environment file $ENV_FILE not found, creating from template..."
        if [[ -f ".env.staging.template" ]]; then
            cp ".env.staging.template" "$ENV_FILE"
            log_warning "Please update $ENV_FILE with actual values before deploying"
        else
            log_error "No environment template found"
            exit 1
        fi
    fi
    
    log_success "Prerequisites check passed"
}

# Build staging image
build_staging_image() {
    log_info "Building staging image..."
    
    # Build with staging optimizations
    docker build \
        --target api-base \
        --build-arg ENVIRONMENT=staging \
        --build-arg ENABLE_DEBUG=true \
        -t "$APP_NAME:$IMAGE_TAG" .
    
    log_success "Staging image built successfully"
}

# Run tests before deployment
run_tests() {
    log_info "Running tests before deployment..."
    
    # Create test container
    docker run --rm \
        -v "$(pwd)":/app \
        -w /app \
        "$APP_NAME:$IMAGE_TAG" \
        python -m pytest api/tests/ -v --tb=short
    
    if [[ $? -eq 0 ]]; then
        log_success "All tests passed"
    else
        log_error "Tests failed, aborting deployment"
        exit 1
    fi
}

# Deploy to staging
deploy_staging() {
    log_info "Deploying to staging environment..."
    
    # Stop existing staging containers
    if docker-compose -f docker-compose.staging.yml ps | grep -q "Up"; then
        log_info "Stopping existing staging containers..."
        docker-compose -f docker-compose.staging.yml down
    fi
    
    # Start staging deployment
    log_info "Starting staging deployment..."
    docker-compose -f docker-compose.staging.yml --env-file "$ENV_FILE" up -d
    
    # Wait for services to be ready
    log_info "Waiting for services to be ready..."
    sleep 20
    
    # Check staging health
    check_staging_health
    
    log_success "Staging deployment completed"
}

# Check staging health
check_staging_health() {
    log_info "Checking staging environment health..."
    
    local max_attempts=20
    local attempt=1
    
    while [[ $attempt -le $max_attempts ]]; do
        if curl -f "$STAGING_URL/health" &> /dev/null; then
            log_success "Staging health check passed"
            return 0
        fi
        
        log_info "Health check attempt $attempt/$max_attempts failed, retrying in 5 seconds..."
        sleep 5
        ((attempt++))
    done
    
    log_error "Staging health check failed after $max_attempts attempts"
    return 1
}

# Run integration tests
run_integration_tests() {
    log_info "Running integration tests against staging..."
    
    # Wait a bit more for all services to be fully ready
    sleep 10
    
    # Run integration tests
    docker run --rm \
        --network cliper_cliper-network \
        -e STAGING_URL="$STAGING_URL" \
        -v "$(pwd)":/app \
        -w /app \
        "$APP_NAME:$IMAGE_TAG" \
        python -m pytest api/tests/integration/ -v --tb=short
    
    if [[ $? -eq 0 ]]; then
        log_success "Integration tests passed"
    else
        log_warning "Integration tests failed, but staging is still deployed"
    fi
}

# Setup staging monitoring
setup_staging_monitoring() {
    log_info "Setting up staging monitoring..."
    
    # Create staging-specific monitoring configuration
    mkdir -p /opt/cliper-staging/monitoring
    
    # Setup log aggregation for staging
    cat > /etc/logrotate.d/cliper-staging << EOF
/var/log/cliper-staging/*.log {
    daily
    missingok
    rotate 7
    compress
    delaycompress
    notifempty
    create 644 root root
    postrotate
        docker-compose -f docker-compose.staging.yml restart api celery-worker
    endscript
}
EOF
    
    log_success "Staging monitoring setup completed"
}

# Generate staging report
generate_staging_report() {
    log_info "Generating staging deployment report..."
    
    local report_file="/tmp/staging-deployment-report-$(date +%Y%m%d_%H%M%S).txt"
    
    cat > "$report_file" << EOF
Staging Deployment Report
========================
Deployment Time: $(date)
Image Tag: $IMAGE_TAG
Environment: staging
URL: $STAGING_URL

Services Status:
$(docker-compose -f docker-compose.staging.yml ps)

Health Check:
$(curl -s "$STAGING_URL/health" | jq . 2>/dev/null || echo "Health check failed")

System Info:
$(curl -s "$STAGING_URL/api/info" | jq . 2>/dev/null || echo "System info unavailable")

Container Logs (last 50 lines):
$(docker-compose -f docker-compose.staging.yml logs --tail=50)
EOF
    
    log_success "Staging report generated: $report_file"
    
    # Send report via email if configured
    if command -v mail &> /dev/null && [[ -n "${STAGING_REPORT_EMAIL:-}" ]]; then
        mail -s "Staging Deployment Report - $(date)" "$STAGING_REPORT_EMAIL" < "$report_file"
        log_info "Report sent to $STAGING_REPORT_EMAIL"
    fi
}

# Rollback function
rollback_staging() {
    log_warning "Rolling back staging deployment..."
    
    # Stop current deployment
    docker-compose -f docker-compose.staging.yml down
    
    # Start previous version (if available)
    if docker images | grep -q "$APP_NAME:previous"; then
        docker tag "$APP_NAME:previous" "$APP_NAME:$IMAGE_TAG"
        docker-compose -f docker-compose.staging.yml --env-file "$ENV_FILE" up -d
        log_success "Rollback completed"
    else
        log_error "No previous version available for rollback"
    fi
}

# Main staging deployment function
main() {
    log_info "Starting staging deployment for $APP_NAME:$IMAGE_TAG"
    
    # Tag current image as previous (for rollback)
    if docker images | grep -q "$APP_NAME:$IMAGE_TAG"; then
        docker tag "$APP_NAME:$IMAGE_TAG" "$APP_NAME:previous"
    fi
    
    check_prerequisites
    build_staging_image
    run_tests
    deploy_staging
    run_integration_tests
    setup_staging_monitoring
    generate_staging_report
    
    log_success "Staging deployment completed successfully!"
    log_info "Staging URL: $STAGING_URL"
    log_info "API Documentation: $STAGING_URL/docs"
    log_info "Monitoring Dashboard: $STAGING_URL/monitoring"
    log_info "Flower (Celery): $STAGING_URL:5555"
}

# Handle script interruption
trap 'log_error "Staging deployment interrupted"; rollback_staging; exit 1' INT TERM

# Parse command line arguments
case "${1:-deploy}" in
    "deploy")
        main
        ;;
    "rollback")
        rollback_staging
        ;;
    "health")
        check_staging_health
        ;;
    "report")
        generate_staging_report
        ;;
    *)
        echo "Usage: $0 [deploy|rollback|health|report] [image_tag]"
        exit 1
        ;;
esac