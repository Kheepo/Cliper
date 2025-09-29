#!/bin/bash

# Cliper Production Backup Script
# Automated backup and recovery procedures for production environment

set -euo pipefail

# Configuration
BACKUP_DIR="/backup/output"
DATE=$(date +"%Y%m%d_%H%M%S")
RETENTION_DAYS=30
COMPRESSION_LEVEL=6

# Logging
LOG_FILE="$BACKUP_DIR/backup_$DATE.log"
exec 1> >(tee -a "$LOG_FILE")
exec 2>&1

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1"
}

log "Starting backup process..."

# Create backup directory structure
mkdir -p "$BACKUP_DIR/{database,redis,media,config,logs}"

# Function to check service health
check_service_health() {
    local service=$1
    local max_attempts=5
    local attempt=1
    
    while [ $attempt -le $max_attempts ]; do
        if docker-compose -f /opt/cliper/deploy/config/docker-compose.prod.yml exec -T $service echo "healthy" > /dev/null 2>&1; then
            log "Service $service is healthy"
            return 0
        fi
        log "Service $service health check failed (attempt $attempt/$max_attempts)"
        sleep 10
        ((attempt++))
    done
    
    log "ERROR: Service $service is not healthy after $max_attempts attempts"
    return 1
}

# Function to send notification
send_notification() {
    local status=$1
    local message=$2
    
    # Slack notification
    if [ -n "${SLACK_WEBHOOK_URL:-}" ]; then
        curl -X POST -H 'Content-type: application/json' \
            --data "{\"text\":\"Backup $status: $message\"}" \
            "$SLACK_WEBHOOK_URL" || true
    fi
    
    # Email notification
    if [ -n "${SMTP_SERVER:-}" ] && [ -n "${BACKUP_EMAIL:-}" ]; then
        echo "Subject: Cliper Backup $status\n\n$message" | \
            sendmail "$BACKUP_EMAIL" || true
    fi
}

# Function to cleanup old backups
cleanup_old_backups() {
    log "Cleaning up backups older than $RETENTION_DAYS days..."
    find "$BACKUP_DIR" -name "backup_*.tar.gz" -mtime +$RETENTION_DAYS -delete || true
    find "$BACKUP_DIR" -name "*.log" -mtime +$RETENTION_DAYS -delete || true
    log "Cleanup completed"
}

# Function to backup PostgreSQL
backup_postgres() {
    log "Starting PostgreSQL backup..."
    
    local backup_file="$BACKUP_DIR/database/postgres_$DATE.sql"
    
    # Check if PostgreSQL is healthy
    if ! check_service_health postgres; then
        log "ERROR: PostgreSQL is not healthy, skipping database backup"
        return 1
    fi
    
    # Create database backup
    docker-compose -f /opt/cliper/deploy/config/docker-compose.prod.yml exec -T postgres \
        pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" --verbose --clean --if-exists \
        --no-owner --no-privileges > "$backup_file"
    
    if [ $? -eq 0 ]; then
        log "PostgreSQL backup completed: $backup_file"
        
        # Compress backup
        gzip -$COMPRESSION_LEVEL "$backup_file"
        log "PostgreSQL backup compressed: ${backup_file}.gz"
        
        # Verify backup integrity
        if gunzip -t "${backup_file}.gz"; then
            log "PostgreSQL backup integrity verified"
        else
            log "ERROR: PostgreSQL backup integrity check failed"
            return 1
        fi
    else
        log "ERROR: PostgreSQL backup failed"
        return 1
    fi
}

# Function to backup Redis
backup_redis() {
    log "Starting Redis backup..."
    
    local backup_file="$BACKUP_DIR/redis/redis_$DATE.rdb"
    
    # Check if Redis is healthy
    if ! check_service_health redis; then
        log "ERROR: Redis is not healthy, skipping Redis backup"
        return 1
    fi
    
    # Force Redis to save current state
    docker-compose -f /opt/cliper/deploy/config/docker-compose.prod.yml exec -T redis \
        redis-cli BGSAVE
    
    # Wait for background save to complete
    while [ "$(docker-compose -f /opt/cliper/deploy/config/docker-compose.prod.yml exec -T redis redis-cli LASTSAVE)" = "$(docker-compose -f /opt/cliper/deploy/config/docker-compose.prod.yml exec -T redis redis-cli LASTSAVE)" ]; do
        sleep 1
    done
    
    # Copy Redis dump file
    docker cp cliper_redis:/data/dump.rdb "$backup_file"
    
    if [ $? -eq 0 ]; then
        log "Redis backup completed: $backup_file"
        
        # Compress backup
        gzip -$COMPRESSION_LEVEL "$backup_file"
        log "Redis backup compressed: ${backup_file}.gz"
    else
        log "ERROR: Redis backup failed"
        return 1
    fi
}

# Function to backup media files
backup_media() {
    log "Starting media files backup..."
    
    local backup_file="$BACKUP_DIR/media/media_$DATE.tar"
    
    # Create media backup
    tar -cf "$backup_file" -C /backup/media . 2>/dev/null || true
    
    if [ -f "$backup_file" ]; then
        log "Media files backup completed: $backup_file"
        
        # Compress backup
        gzip -$COMPRESSION_LEVEL "$backup_file"
        log "Media files backup compressed: ${backup_file}.gz"
    else
        log "WARNING: Media files backup failed or no media files found"
    fi
}

# Function to backup configuration
backup_config() {
    log "Starting configuration backup..."
    
    local backup_file="$BACKUP_DIR/config/config_$DATE.tar"
    
    # Create configuration backup
    tar -cf "$backup_file" -C /opt/cliper/deploy . 2>/dev/null || true
    
    if [ -f "$backup_file" ]; then
        log "Configuration backup completed: $backup_file"
        
        # Compress backup
        gzip -$COMPRESSION_LEVEL "$backup_file"
        log "Configuration backup compressed: ${backup_file}.gz"
    else
        log "ERROR: Configuration backup failed"
        return 1
    fi
}

# Function to backup application logs
backup_logs() {
    log "Starting logs backup..."
    
    local backup_file="$BACKUP_DIR/logs/logs_$DATE.tar"
    
    # Create logs backup (last 7 days)
    find /backup/logs -name "*.log" -mtime -7 -exec tar -rf "$backup_file" {} + 2>/dev/null || true
    
    if [ -f "$backup_file" ]; then
        log "Logs backup completed: $backup_file"
        
        # Compress backup
        gzip -$COMPRESSION_LEVEL "$backup_file"
        log "Logs backup compressed: ${backup_file}.gz"
    else
        log "WARNING: Logs backup failed or no recent logs found"
    fi
}

# Function to create full backup archive
create_full_backup() {
    log "Creating full backup archive..."
    
    local full_backup="$BACKUP_DIR/backup_$DATE.tar.gz"
    
    # Create full backup archive
    tar -czf "$full_backup" -C "$BACKUP_DIR" \
        database/postgres_$DATE.sql.gz \
        redis/redis_$DATE.rdb.gz \
        media/media_$DATE.tar.gz \
        config/config_$DATE.tar.gz \
        logs/logs_$DATE.tar.gz 2>/dev/null || true
    
    if [ -f "$full_backup" ]; then
        local size=$(du -h "$full_backup" | cut -f1)
        log "Full backup archive created: $full_backup (Size: $size)"
        
        # Calculate checksum
        local checksum=$(sha256sum "$full_backup" | cut -d' ' -f1)
        echo "$checksum  backup_$DATE.tar.gz" > "$BACKUP_DIR/backup_$DATE.sha256"
        log "Backup checksum: $checksum"
        
        return 0
    else
        log "ERROR: Failed to create full backup archive"
        return 1
    fi
}

# Function to upload backup to cloud storage
upload_to_cloud() {
    local backup_file="$BACKUP_DIR/backup_$DATE.tar.gz"
    local checksum_file="$BACKUP_DIR/backup_$DATE.sha256"
    
    # AWS S3 upload
    if [ -n "${AWS_S3_BUCKET:-}" ] && command -v aws >/dev/null 2>&1; then
        log "Uploading backup to AWS S3..."
        aws s3 cp "$backup_file" "s3://$AWS_S3_BUCKET/backups/" || log "WARNING: S3 upload failed"
        aws s3 cp "$checksum_file" "s3://$AWS_S3_BUCKET/backups/" || log "WARNING: S3 checksum upload failed"
    fi
    
    # Google Cloud Storage upload
    if [ -n "${GCS_BUCKET:-}" ] && command -v gsutil >/dev/null 2>&1; then
        log "Uploading backup to Google Cloud Storage..."
        gsutil cp "$backup_file" "gs://$GCS_BUCKET/backups/" || log "WARNING: GCS upload failed"
        gsutil cp "$checksum_file" "gs://$GCS_BUCKET/backups/" || log "WARNING: GCS checksum upload failed"
    fi
    
    # Azure Blob Storage upload
    if [ -n "${AZURE_CONTAINER:-}" ] && command -v az >/dev/null 2>&1; then
        log "Uploading backup to Azure Blob Storage..."
        az storage blob upload --file "$backup_file" --container-name "$AZURE_CONTAINER" --name "backups/backup_$DATE.tar.gz" || log "WARNING: Azure upload failed"
        az storage blob upload --file "$checksum_file" --container-name "$AZURE_CONTAINER" --name "backups/backup_$DATE.sha256" || log "WARNING: Azure checksum upload failed"
    fi
}

# Function to test backup integrity
test_backup_integrity() {
    log "Testing backup integrity..."
    
    local backup_file="$BACKUP_DIR/backup_$DATE.tar.gz"
    local checksum_file="$BACKUP_DIR/backup_$DATE.sha256"
    
    # Verify checksum
    if sha256sum -c "$checksum_file"; then
        log "Backup checksum verification passed"
    else
        log "ERROR: Backup checksum verification failed"
        return 1
    fi
    
    # Test archive extraction
    local test_dir="/tmp/backup_test_$DATE"
    mkdir -p "$test_dir"
    
    if tar -tzf "$backup_file" > /dev/null 2>&1; then
        log "Backup archive integrity test passed"
        rm -rf "$test_dir"
        return 0
    else
        log "ERROR: Backup archive integrity test failed"
        rm -rf "$test_dir"
        return 1
    fi
}

# Main backup execution
main() {
    local start_time=$(date +%s)
    local success=true
    
    log "=== Cliper Production Backup Started ==="
    log "Backup date: $DATE"
    log "Backup directory: $BACKUP_DIR"
    
    # Execute backup components
    backup_postgres || success=false
    backup_redis || success=false
    backup_media || success=false
    backup_config || success=false
    backup_logs || success=false
    
    if [ "$success" = true ]; then
        # Create full backup archive
        if create_full_backup; then
            # Test backup integrity
            if test_backup_integrity; then
                # Upload to cloud storage
                upload_to_cloud
                
                # Cleanup old backups
                cleanup_old_backups
                
                local end_time=$(date +%s)
                local duration=$((end_time - start_time))
                local message="Backup completed successfully in ${duration}s"
                log "$message"
                send_notification "SUCCESS" "$message"
            else
                local message="Backup integrity test failed"
                log "ERROR: $message"
                send_notification "FAILED" "$message"
                exit 1
            fi
        else
            local message="Failed to create full backup archive"
            log "ERROR: $message"
            send_notification "FAILED" "$message"
            exit 1
        fi
    else
        local message="One or more backup components failed"
        log "ERROR: $message"
        send_notification "FAILED" "$message"
        exit 1
    fi
    
    log "=== Cliper Production Backup Completed ==="
}

# Execute main function
main "$@"