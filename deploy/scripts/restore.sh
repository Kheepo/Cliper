#!/bin/bash

# Cliper Production Recovery Script
# Automated recovery procedures for production environment

set -euo pipefail

# Configuration
BACKUP_DIR="/backup/output"
RESTORE_DIR="/tmp/restore_$(date +%s)"
DATE_PATTERN="[0-9]{8}_[0-9]{6}"

# Logging
LOG_FILE="/var/log/cliper_restore_$(date +%Y%m%d_%H%M%S).log"
exec 1> >(tee -a "$LOG_FILE")
exec 2>&1

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1"
}

# Function to display usage
usage() {
    cat << EOF
Usage: $0 [OPTIONS] BACKUP_FILE

Options:
    -h, --help              Show this help message
    -f, --force             Force restore without confirmation
    -d, --database-only     Restore database only
    -r, --redis-only        Restore Redis only
    -m, --media-only        Restore media files only
    -c, --config-only       Restore configuration only
    -t, --test              Test restore without applying changes
    --from-cloud PROVIDER   Download backup from cloud storage (aws|gcs|azure)
    --backup-date DATE      Restore from specific backup date (YYYYMMDD_HHMMSS)
    --list-backups          List available backups

Examples:
    $0 backup_20231201_120000.tar.gz
    $0 --database-only backup_20231201_120000.tar.gz
    $0 --from-cloud aws --backup-date 20231201_120000
    $0 --list-backups
    $0 --test backup_20231201_120000.tar.gz

EOF
}

# Function to list available backups
list_backups() {
    log "Available local backups:"
    find "$BACKUP_DIR" -name "backup_*.tar.gz" -printf "%f\t%TY-%Tm-%Td %TH:%TM\t%s bytes\n" | sort -r
    
    # List cloud backups if configured
    if [ -n "${AWS_S3_BUCKET:-}" ] && command -v aws >/dev/null 2>&1; then
        log "\nAvailable AWS S3 backups:"
        aws s3 ls "s3://$AWS_S3_BUCKET/backups/" --human-readable | grep backup_ || true
    fi
    
    if [ -n "${GCS_BUCKET:-}" ] && command -v gsutil >/dev/null 2>&1; then
        log "\nAvailable Google Cloud Storage backups:"
        gsutil ls -l "gs://$GCS_BUCKET/backups/backup_*.tar.gz" || true
    fi
    
    if [ -n "${AZURE_CONTAINER:-}" ] && command -v az >/dev/null 2>&1; then
        log "\nAvailable Azure Blob Storage backups:"
        az storage blob list --container-name "$AZURE_CONTAINER" --prefix "backups/backup_" --output table || true
    fi
}

# Function to download backup from cloud
download_from_cloud() {
    local provider=$1
    local backup_date=$2
    local backup_file="backup_${backup_date}.tar.gz"
    local checksum_file="backup_${backup_date}.sha256"
    local local_backup="$BACKUP_DIR/$backup_file"
    local local_checksum="$BACKUP_DIR/$checksum_file"
    
    log "Downloading backup from $provider..."
    
    case $provider in
        aws)
            if [ -z "${AWS_S3_BUCKET:-}" ]; then
                log "ERROR: AWS_S3_BUCKET not configured"
                return 1
            fi
            aws s3 cp "s3://$AWS_S3_BUCKET/backups/$backup_file" "$local_backup"
            aws s3 cp "s3://$AWS_S3_BUCKET/backups/$checksum_file" "$local_checksum"
            ;;
        gcs)
            if [ -z "${GCS_BUCKET:-}" ]; then
                log "ERROR: GCS_BUCKET not configured"
                return 1
            fi
            gsutil cp "gs://$GCS_BUCKET/backups/$backup_file" "$local_backup"
            gsutil cp "gs://$GCS_BUCKET/backups/$checksum_file" "$local_checksum"
            ;;
        azure)
            if [ -z "${AZURE_CONTAINER:-}" ]; then
                log "ERROR: AZURE_CONTAINER not configured"
                return 1
            fi
            az storage blob download --container-name "$AZURE_CONTAINER" --name "backups/$backup_file" --file "$local_backup"
            az storage blob download --container-name "$AZURE_CONTAINER" --name "backups/$checksum_file" --file "$local_checksum"
            ;;
        *)
            log "ERROR: Unsupported cloud provider: $provider"
            return 1
            ;;
    esac
    
    log "Backup downloaded successfully: $local_backup"
    echo "$local_backup"
}

# Function to verify backup integrity
verify_backup() {
    local backup_file=$1
    local checksum_file="${backup_file%.tar.gz}.sha256"
    
    log "Verifying backup integrity..."
    
    # Check if backup file exists
    if [ ! -f "$backup_file" ]; then
        log "ERROR: Backup file not found: $backup_file"
        return 1
    fi
    
    # Verify checksum if available
    if [ -f "$checksum_file" ]; then
        if (cd "$(dirname "$backup_file")" && sha256sum -c "$(basename "$checksum_file")"); then
            log "Backup checksum verification passed"
        else
            log "ERROR: Backup checksum verification failed"
            return 1
        fi
    else
        log "WARNING: Checksum file not found, skipping verification"
    fi
    
    # Test archive integrity
    if tar -tzf "$backup_file" > /dev/null 2>&1; then
        log "Backup archive integrity test passed"
    else
        log "ERROR: Backup archive is corrupted"
        return 1
    fi
    
    return 0
}

# Function to extract backup
extract_backup() {
    local backup_file=$1
    
    log "Extracting backup to $RESTORE_DIR..."
    mkdir -p "$RESTORE_DIR"
    
    if tar -xzf "$backup_file" -C "$RESTORE_DIR"; then
        log "Backup extracted successfully"
        return 0
    else
        log "ERROR: Failed to extract backup"
        return 1
    fi
}

# Function to stop services
stop_services() {
    log "Stopping Cliper services..."
    
    docker-compose -f /opt/cliper/deploy/config/docker-compose.prod.yml stop backend worker scheduler || true
    
    # Wait for services to stop
    sleep 10
    
    log "Services stopped"
}

# Function to start services
start_services() {
    log "Starting Cliper services..."
    
    docker-compose -f /opt/cliper/deploy/config/docker-compose.prod.yml up -d
    
    # Wait for services to start
    sleep 30
    
    log "Services started"
}

# Function to restore PostgreSQL
restore_postgres() {
    local postgres_backup="$RESTORE_DIR/database/postgres_*.sql.gz"
    
    log "Restoring PostgreSQL database..."
    
    # Find the PostgreSQL backup file
    local backup_file=$(ls $postgres_backup 2>/dev/null | head -1)
    if [ -z "$backup_file" ]; then
        log "ERROR: PostgreSQL backup file not found"
        return 1
    fi
    
    log "Using PostgreSQL backup: $backup_file"
    
    # Stop application services
    docker-compose -f /opt/cliper/deploy/config/docker-compose.prod.yml stop backend worker scheduler
    
    # Restore database
    gunzip -c "$backup_file" | docker-compose -f /opt/cliper/deploy/config/docker-compose.prod.yml exec -T postgres \
        psql -U "$POSTGRES_USER" -d "$POSTGRES_DB"
    
    if [ $? -eq 0 ]; then
        log "PostgreSQL database restored successfully"
        return 0
    else
        log "ERROR: PostgreSQL database restore failed"
        return 1
    fi
}

# Function to restore Redis
restore_redis() {
    local redis_backup="$RESTORE_DIR/redis/redis_*.rdb.gz"
    
    log "Restoring Redis data..."
    
    # Find the Redis backup file
    local backup_file=$(ls $redis_backup 2>/dev/null | head -1)
    if [ -z "$backup_file" ]; then
        log "ERROR: Redis backup file not found"
        return 1
    fi
    
    log "Using Redis backup: $backup_file"
    
    # Stop Redis service
    docker-compose -f /opt/cliper/deploy/config/docker-compose.prod.yml stop redis
    
    # Extract and copy Redis dump file
    local temp_rdb="/tmp/dump_restore.rdb"
    gunzip -c "$backup_file" > "$temp_rdb"
    
    # Copy to Redis data directory
    docker cp "$temp_rdb" cliper_redis:/data/dump.rdb
    
    # Start Redis service
    docker-compose -f /opt/cliper/deploy/config/docker-compose.prod.yml start redis
    
    # Wait for Redis to start
    sleep 10
    
    # Verify Redis is working
    if docker-compose -f /opt/cliper/deploy/config/docker-compose.prod.yml exec -T redis redis-cli ping | grep -q PONG; then
        log "Redis data restored successfully"
        rm -f "$temp_rdb"
        return 0
    else
        log "ERROR: Redis restore failed"
        rm -f "$temp_rdb"
        return 1
    fi
}

# Function to restore media files
restore_media() {
    local media_backup="$RESTORE_DIR/media/media_*.tar.gz"
    
    log "Restoring media files..."
    
    # Find the media backup file
    local backup_file=$(ls $media_backup 2>/dev/null | head -1)
    if [ -z "$backup_file" ]; then
        log "WARNING: Media backup file not found, skipping media restore"
        return 0
    fi
    
    log "Using media backup: $backup_file"
    
    # Create backup of current media
    if [ -d "/opt/cliper/media" ]; then
        mv "/opt/cliper/media" "/opt/cliper/media.backup.$(date +%s)"
    fi
    
    # Extract media files
    mkdir -p "/opt/cliper/media"
    if tar -xzf "$backup_file" -C "/opt/cliper/media"; then
        log "Media files restored successfully"
        return 0
    else
        log "ERROR: Media files restore failed"
        return 1
    fi
}

# Function to restore configuration
restore_config() {
    local config_backup="$RESTORE_DIR/config/config_*.tar.gz"
    
    log "Restoring configuration files..."
    
    # Find the configuration backup file
    local backup_file=$(ls $config_backup 2>/dev/null | head -1)
    if [ -z "$backup_file" ]; then
        log "ERROR: Configuration backup file not found"
        return 1
    fi
    
    log "Using configuration backup: $backup_file"
    
    # Create backup of current configuration
    if [ -d "/opt/cliper/deploy" ]; then
        mv "/opt/cliper/deploy" "/opt/cliper/deploy.backup.$(date +%s)"
    fi
    
    # Extract configuration files
    mkdir -p "/opt/cliper/deploy"
    if tar -xzf "$backup_file" -C "/opt/cliper/deploy"; then
        log "Configuration files restored successfully"
        return 0
    else
        log "ERROR: Configuration files restore failed"
        return 1
    fi
}

# Function to send notification
send_notification() {
    local status=$1
    local message=$2
    
    # Slack notification
    if [ -n "${SLACK_WEBHOOK_URL:-}" ]; then
        curl -X POST -H 'Content-type: application/json' \
            --data "{\"text\":\"Restore $status: $message\"}" \
            "$SLACK_WEBHOOK_URL" || true
    fi
    
    # Email notification
    if [ -n "${SMTP_SERVER:-}" ] && [ -n "${BACKUP_EMAIL:-}" ]; then
        echo "Subject: Cliper Restore $status\n\n$message" | \
            sendmail "$BACKUP_EMAIL" || true
    fi
}

# Function to perform health checks
health_check() {
    log "Performing post-restore health checks..."
    
    local max_attempts=10
    local attempt=1
    
    while [ $attempt -le $max_attempts ]; do
        log "Health check attempt $attempt/$max_attempts"
        
        # Check PostgreSQL
        if docker-compose -f /opt/cliper/deploy/config/docker-compose.prod.yml exec -T postgres \
            pg_isready -U "$POSTGRES_USER" -d "$POSTGRES_DB" > /dev/null 2>&1; then
            log "PostgreSQL health check passed"
        else
            log "PostgreSQL health check failed"
            ((attempt++))
            sleep 30
            continue
        fi
        
        # Check Redis
        if docker-compose -f /opt/cliper/deploy/config/docker-compose.prod.yml exec -T redis \
            redis-cli ping | grep -q PONG; then
            log "Redis health check passed"
        else
            log "Redis health check failed"
            ((attempt++))
            sleep 30
            continue
        fi
        
        # Check backend API
        if curl -f http://localhost:8000/health/ready > /dev/null 2>&1; then
            log "Backend API health check passed"
            log "All health checks passed"
            return 0
        else
            log "Backend API health check failed"
            ((attempt++))
            sleep 30
            continue
        fi
    done
    
    log "ERROR: Health checks failed after $max_attempts attempts"
    return 1
}

# Main restore function
main() {
    local backup_file=""
    local force=false
    local test_mode=false
    local database_only=false
    local redis_only=false
    local media_only=false
    local config_only=false
    local from_cloud=""
    local backup_date=""
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
            -t|--test)
                test_mode=true
                shift
                ;;
            -d|--database-only)
                database_only=true
                shift
                ;;
            -r|--redis-only)
                redis_only=true
                shift
                ;;
            -m|--media-only)
                media_only=true
                shift
                ;;
            -c|--config-only)
                config_only=true
                shift
                ;;
            --from-cloud)
                from_cloud="$2"
                shift 2
                ;;
            --backup-date)
                backup_date="$2"
                shift 2
                ;;
            --list-backups)
                list_backups
                exit 0
                ;;
            -*)
                log "ERROR: Unknown option $1"
                usage
                exit 1
                ;;
            *)
                backup_file="$1"
                shift
                ;;
        esac
    done
    
    log "=== Cliper Production Restore Started ==="
    
    # Handle cloud download
    if [ -n "$from_cloud" ]; then
        if [ -z "$backup_date" ]; then
            log "ERROR: --backup-date required when using --from-cloud"
            exit 1
        fi
        backup_file=$(download_from_cloud "$from_cloud" "$backup_date")
    fi
    
    # Validate backup file
    if [ -z "$backup_file" ]; then
        log "ERROR: No backup file specified"
        usage
        exit 1
    fi
    
    # Convert to absolute path if relative
    if [[ "$backup_file" != /* ]]; then
        backup_file="$BACKUP_DIR/$backup_file"
    fi
    
    # Verify backup
    if ! verify_backup "$backup_file"; then
        log "ERROR: Backup verification failed"
        exit 1
    fi
    
    # Extract backup
    if ! extract_backup "$backup_file"; then
        log "ERROR: Backup extraction failed"
        exit 1
    fi
    
    # Confirmation prompt
    if [ "$force" = false ] && [ "$test_mode" = false ]; then
        echo "WARNING: This will restore data from backup and may overwrite current data."
        echo "Backup file: $backup_file"
        echo "Continue? (yes/no): "
        read -r confirmation
        if [ "$confirmation" != "yes" ]; then
            log "Restore cancelled by user"
            exit 0
        fi
    fi
    
    if [ "$test_mode" = true ]; then
        log "TEST MODE: Restore operations will be simulated"
        log "Backup file: $backup_file"
        log "Extracted to: $RESTORE_DIR"
        log "Available components:"
        ls -la "$RESTORE_DIR"/*/
        log "Test completed successfully"
        rm -rf "$RESTORE_DIR"
        exit 0
    fi
    
    # Perform restore operations
    local success=true
    
    if [ "$database_only" = true ]; then
        restore_postgres || success=false
    elif [ "$redis_only" = true ]; then
        restore_redis || success=false
    elif [ "$media_only" = true ]; then
        restore_media || success=false
    elif [ "$config_only" = true ]; then
        restore_config || success=false
    else
        # Full restore
        stop_services
        restore_postgres || success=false
        restore_redis || success=false
        restore_media || success=false
        restore_config || success=false
        start_services
    fi
    
    # Cleanup
    rm -rf "$RESTORE_DIR"
    
    if [ "$success" = true ]; then
        # Perform health checks
        if health_check; then
            local end_time=$(date +%s)
            local duration=$((end_time - start_time))
            local message="Restore completed successfully in ${duration}s"
            log "$message"
            send_notification "SUCCESS" "$message"
        else
            local message="Restore completed but health checks failed"
            log "WARNING: $message"
            send_notification "WARNING" "$message"
        fi
    else
        local message="Restore failed"
        log "ERROR: $message"
        send_notification "FAILED" "$message"
        exit 1
    fi
    
    log "=== Cliper Production Restore Completed ==="
}

# Execute main function
main "$@"