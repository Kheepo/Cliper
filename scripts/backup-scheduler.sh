#!/bin/bash

# Cliper Backup Scheduler
# Automated backup scheduling with different frequencies and retention policies

set -euo pipefail

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_ROOT="$(dirname "$SCRIPT_DIR")"
BACKUP_SCRIPT="$SCRIPT_DIR/backup-system.py"
LOG_FILE="/var/log/cliper-backup-scheduler.log"
LOCK_FILE="/var/run/cliper-backup.lock"
CONFIG_FILE="$SCRIPT_DIR/backup-config.json"

# Logging function
log() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') - $1" | tee -a "$LOG_FILE"
}

# Error handling
error_exit() {
    log "ERROR: $1"
    cleanup
    exit 1
}

# Cleanup function
cleanup() {
    if [[ -f "$LOCK_FILE" ]]; then
        rm -f "$LOCK_FILE"
    fi
}

# Trap for cleanup
trap cleanup EXIT

# Check if backup is already running
check_lock() {
    if [[ -f "$LOCK_FILE" ]]; then
        local pid
        pid=$(cat "$LOCK_FILE")
        if kill -0 "$pid" 2>/dev/null; then
            log "Backup already running with PID $pid"
            exit 0
        else
            log "Removing stale lock file"
            rm -f "$LOCK_FILE"
        fi
    fi
    
    # Create lock file
    echo $$ > "$LOCK_FILE"
}

# Check prerequisites
check_prerequisites() {
    log "Checking prerequisites..."
    
    # Check if backup script exists
    if [[ ! -f "$BACKUP_SCRIPT" ]]; then
        error_exit "Backup script not found: $BACKUP_SCRIPT"
    fi
    
    # Check if Python is available
    if ! command -v python3 &> /dev/null; then
        error_exit "Python3 is required but not installed"
    fi
    
    # Check if required Python packages are installed
    python3 -c "import cryptography, boto3" 2>/dev/null || {
        log "Installing required Python packages..."
        pip3 install cryptography boto3 requests
    }
    
    # Check if PostgreSQL client is available
    if ! command -v pg_dump &> /dev/null; then
        error_exit "PostgreSQL client (pg_dump) is required but not installed"
    fi
    
    # Check if Redis client is available
    if ! command -v redis-cli &> /dev/null; then
        log "WARNING: Redis client not found, Redis backups will be skipped"
    fi
    
    log "Prerequisites check completed"
}

# Load environment variables
load_environment() {
    log "Loading environment variables..."
    
    # Load from .env file if it exists
    if [[ -f "$APP_ROOT/.env" ]]; then
        set -a
        source "$APP_ROOT/.env"
        set +a
        log "Loaded environment from .env file"
    fi
    
    # Load from production env if it exists
    if [[ -f "$APP_ROOT/.env.production" ]]; then
        set -a
        source "$APP_ROOT/.env.production"
        set +a
        log "Loaded environment from .env.production file"
    fi
    
    # Set default values if not provided
    export BACKUP_ROOT="${BACKUP_ROOT:-/backups}"
    export APP_ROOT="${APP_ROOT:-$APP_ROOT}"
    export BACKUP_DAILY_RETENTION="${BACKUP_DAILY_RETENTION:-7}"
    export BACKUP_WEEKLY_RETENTION="${BACKUP_WEEKLY_RETENTION:-4}"
    export BACKUP_MONTHLY_RETENTION="${BACKUP_MONTHLY_RETENTION:-12}"
}

# Create backup configuration
create_backup_config() {
    log "Creating backup configuration..."
    
    cat > "$CONFIG_FILE" << EOF
{
    "db_host": "${DB_HOST:-localhost}",
    "db_port": ${DB_PORT:-5432},
    "db_name": "${DB_NAME:-cliper}",
    "db_user": "${DB_USER:-postgres}",
    "db_password": "${DB_PASSWORD:-}",
    "backup_root": "${BACKUP_ROOT}",
    "app_root": "${APP_ROOT}",
    "s3_bucket": "${BACKUP_S3_BUCKET:-}",
    "s3_region": "${AWS_REGION:-us-east-1}",
    "aws_access_key": "${AWS_ACCESS_KEY_ID:-}",
    "aws_secret_key": "${AWS_SECRET_ACCESS_KEY:-}",
    "encryption_key": "${BACKUP_ENCRYPTION_KEY:-}",
    "daily_retention": ${BACKUP_DAILY_RETENTION},
    "weekly_retention": ${BACKUP_WEEKLY_RETENTION},
    "monthly_retention": ${BACKUP_MONTHLY_RETENTION},
    "compression_level": ${BACKUP_COMPRESSION_LEVEL:-6},
    "notification_webhook": "${BACKUP_NOTIFICATION_WEBHOOK:-}",
    "notification_email": "${BACKUP_NOTIFICATION_EMAIL:-}"
}
EOF
    
    log "Backup configuration created: $CONFIG_FILE"
}

# Run backup
run_backup() {
    local backup_type="${1:-daily}"
    
    log "Starting $backup_type backup..."
    
    # Create backup directory if it doesn't exist
    mkdir -p "$BACKUP_ROOT"
    
    # Run the backup script
    if python3 "$BACKUP_SCRIPT" --config "$CONFIG_FILE"; then
        log "$backup_type backup completed successfully"
        
        # Send success notification
        send_notification "success" "$backup_type backup completed successfully"
        
        return 0
    else
        log "$backup_type backup failed"
        
        # Send failure notification
        send_notification "failure" "$backup_type backup failed"
        
        return 1
    fi
}

# Send notification
send_notification() {
    local status="$1"
    local message="$2"
    
    # Send webhook notification if configured
    if [[ -n "${BACKUP_NOTIFICATION_WEBHOOK:-}" ]]; then
        curl -X POST "$BACKUP_NOTIFICATION_WEBHOOK" \
            -H "Content-Type: application/json" \
            -d "{
                \"status\": \"$status\",
                \"message\": \"$message\",
                \"timestamp\": \"$(date -Iseconds)\",
                \"hostname\": \"$(hostname)\"
            }" \
            --max-time 30 \
            --silent || log "Failed to send webhook notification"
    fi
    
    # Send email notification if configured
    if [[ -n "${BACKUP_NOTIFICATION_EMAIL:-}" ]] && command -v mail &> /dev/null; then
        echo "$message" | mail -s "Cliper Backup $status" "$BACKUP_NOTIFICATION_EMAIL" || \
            log "Failed to send email notification"
    fi
}

# Health check
health_check() {
    log "Performing backup system health check..."
    
    local issues=0
    
    # Check backup directory
    if [[ ! -d "$BACKUP_ROOT" ]]; then
        log "WARNING: Backup directory does not exist: $BACKUP_ROOT"
        ((issues++))
    fi
    
    # Check disk space
    local available_space
    available_space=$(df "$BACKUP_ROOT" | awk 'NR==2 {print $4}')
    local required_space=1048576  # 1GB in KB
    
    if [[ $available_space -lt $required_space ]]; then
        log "WARNING: Low disk space in backup directory: ${available_space}KB available"
        ((issues++))
    fi
    
    # Check database connectivity
    if ! PGPASSWORD="${DB_PASSWORD:-}" psql -h "${DB_HOST:-localhost}" -p "${DB_PORT:-5432}" -U "${DB_USER:-postgres}" -d "${DB_NAME:-cliper}" -c "SELECT 1;" &>/dev/null; then
        log "WARNING: Cannot connect to database"
        ((issues++))
    fi
    
    # Check Redis connectivity
    if command -v redis-cli &> /dev/null; then
        if ! redis-cli ping &>/dev/null; then
            log "WARNING: Cannot connect to Redis"
            ((issues++))
        fi
    fi
    
    # Check S3 connectivity if configured
    if [[ -n "${BACKUP_S3_BUCKET:-}" ]] && [[ -n "${AWS_ACCESS_KEY_ID:-}" ]]; then
        if ! aws s3 ls "s3://$BACKUP_S3_BUCKET" &>/dev/null; then
            log "WARNING: Cannot access S3 bucket: $BACKUP_S3_BUCKET"
            ((issues++))
        fi
    fi
    
    if [[ $issues -eq 0 ]]; then
        log "Health check passed: No issues found"
        return 0
    else
        log "Health check completed with $issues issues"
        return 1
    fi
}

# Install cron jobs
install_cron() {
    log "Installing cron jobs..."
    
    # Create cron entries
    local cron_file="/tmp/cliper-backup-cron"
    
    cat > "$cron_file" << EOF
# Cliper Backup Schedule
# Daily backup at 2:00 AM
0 2 * * * $SCRIPT_DIR/backup-scheduler.sh daily

# Weekly backup on Sunday at 3:00 AM
0 3 * * 0 $SCRIPT_DIR/backup-scheduler.sh weekly

# Monthly backup on the 1st at 4:00 AM
0 4 1 * * $SCRIPT_DIR/backup-scheduler.sh monthly

# Health check every 6 hours
0 */6 * * * $SCRIPT_DIR/backup-scheduler.sh health-check

# Cleanup old backups daily at 5:00 AM
0 5 * * * $SCRIPT_DIR/backup-scheduler.sh cleanup
EOF
    
    # Install cron jobs
    crontab "$cron_file"
    rm -f "$cron_file"
    
    log "Cron jobs installed successfully"
}

# Remove cron jobs
remove_cron() {
    log "Removing cron jobs..."
    
    # Remove all cron jobs for this script
    crontab -l | grep -v "$SCRIPT_DIR/backup-scheduler.sh" | crontab -
    
    log "Cron jobs removed successfully"
}

# Cleanup old backups
cleanup_backups() {
    log "Starting backup cleanup..."
    
    if python3 "$BACKUP_SCRIPT" --cleanup-only --config "$CONFIG_FILE"; then
        log "Backup cleanup completed successfully"
    else
        log "Backup cleanup failed"
    fi
}

# Main function
main() {
    local command="${1:-daily}"
    
    case "$command" in
        "daily"|"weekly"|"monthly")
            check_lock
            check_prerequisites
            load_environment
            create_backup_config
            run_backup "$command"
            ;;
        "health-check")
            load_environment
            health_check
            ;;
        "cleanup")
            check_lock
            load_environment
            create_backup_config
            cleanup_backups
            ;;
        "install-cron")
            install_cron
            ;;
        "remove-cron")
            remove_cron
            ;;
        "test")
            check_prerequisites
            load_environment
            create_backup_config
            health_check
            log "Test completed"
            ;;
        *)
            echo "Usage: $0 {daily|weekly|monthly|health-check|cleanup|install-cron|remove-cron|test}"
            echo ""
            echo "Commands:"
            echo "  daily        - Run daily backup"
            echo "  weekly       - Run weekly backup"
            echo "  monthly      - Run monthly backup"
            echo "  health-check - Check backup system health"
            echo "  cleanup      - Clean up old backups"
            echo "  install-cron - Install cron jobs for automated backups"
            echo "  remove-cron  - Remove cron jobs"
            echo "  test         - Test backup system configuration"
            exit 1
            ;;
    esac
}

# Run main function
main "$@"