#!/bin/bash
#
# Database Backup Script for Trading Assistant
# Creates a timestamped PostgreSQL backup using pg_dump
#
# Usage:
#   ./scripts/backup_db.sh              # Backup with default settings
#   ./scripts/backup_db.sh --compress   # Backup with gzip compression
#   ./scripts/backup_db.sh --help       # Show help
#
# Backups are stored in: backups/trading_assistant_YYYYMMDD_HHMMSS.sql[.gz]
#

set -euo pipefail

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
BACKUP_DIR="${PROJECT_ROOT}/backups"
CONTAINER_NAME="trading-assistant-db-1"
DB_NAME="trading_assistant"
DB_USER="ta_app"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_FILENAME="trading_assistant_${TIMESTAMP}.sql"
COMPRESS=false

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Helper functions
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

# Show usage
show_help() {
    cat << EOF
Trading Assistant Database Backup Script

Usage: $0 [OPTIONS]

Options:
  --compress, -c    Compress backup with gzip
  --help, -h        Show this help message

Environment Variables:
  BACKUP_DIR        Directory to store backups (default: ./backups)
  DB_NAME           Database name (default: trading_assistant)
  DB_USER           Database user (default: ta_app)

Examples:
  $0                # Create uncompressed backup
  $0 --compress     # Create compressed backup
  BACKUP_DIR=/mnt/backups $0 --compress

Backup Location:
  Backups are stored in: ${BACKUP_DIR}/
  Filename format: trading_assistant_YYYYMMDD_HHMMSS.sql[.gz]
EOF
}

# Parse arguments
parse_args() {
    while [[ $# -gt 0 ]]; do
        case $1 in
            --compress|-c)
                COMPRESS=true
                shift
                ;;
            --help|-h)
                show_help
                exit 0
                ;;
            *)
                log_error "Unknown option: $1"
                show_help
                exit 1
                ;;
        esac
    done
}

# Check prerequisites
check_prerequisites() {
    log_info "Checking prerequisites..."
    
    # Check if Docker is running
    if ! docker ps &> /dev/null; then
        log_error "Docker is not running or not accessible"
        exit 1
    fi
    
    # Check if database container is running
    if ! docker ps | grep -q "${CONTAINER_NAME}"; then
        log_error "Database container '${CONTAINER_NAME}' is not running"
        log_info "Start the stack with: docker compose up -d"
        exit 1
    fi
    
    # Create backup directory if it doesn't exist
    if [[ ! -d "$BACKUP_DIR" ]]; then
        log_info "Creating backup directory: $BACKUP_DIR"
        mkdir -p "$BACKUP_DIR"
    fi
    
    log_success "Prerequisites check passed"
}

# Perform backup
perform_backup() {
    local backup_path="${BACKUP_DIR}/${BACKUP_FILENAME}"
    local final_path="$backup_path"
    
    if [[ "$COMPRESS" == true ]]; then
        final_path="${backup_path}.gz"
        BACKUP_FILENAME="${BACKUP_FILENAME}.gz"
        log_info "Creating compressed backup: ${BACKUP_FILENAME}"
    else
        log_info "Creating backup: ${BACKUP_FILENAME}"
    fi
    
    log_info "This may take a moment depending on database size..."
    
    # Execute pg_dump inside the container
    if [[ "$COMPRESS" == true ]]; then
        docker exec "${CONTAINER_NAME}" pg_dump \
            -U "${DB_USER}" \
            -d "${DB_NAME}" \
            --format=plain \
            --verbose 2>/dev/null | gzip > "${final_path}"
    else
        docker exec "${CONTAINER_NAME}" pg_dump \
            -U "${DB_USER}" \
            -d "${DB_NAME}" \
            --format=plain \
            --verbose > "${final_path}" 2>/dev/null
    fi
    
    # Check if backup was successful
    if [[ $? -eq 0 && -f "$final_path" ]]; then
        local file_size
        file_size=$(du -h "$final_path" | cut -f1)
        log_success "Backup created successfully"
        log_info "File: ${final_path}"
        log_info "Size: ${file_size}"
        return 0
    else
        log_error "Backup failed"
        rm -f "$final_path"
        return 1
    fi
}

# Cleanup old backups (keep last 10)
cleanup_old_backups() {
    log_info "Cleaning up old backups (keeping last 10)..."
    
    local count
    count=$(ls -1t "${BACKUP_DIR}"/trading_assistant_*.sql* 2>/dev/null | wc -l)
    
    if [[ $count -gt 10 ]]; then
        ls -1t "${BACKUP_DIR}"/trading_assistant_*.sql* | tail -n +11 | xargs rm -f
        log_success "Removed old backups, kept 10 most recent"
    else
        log_info "No cleanup needed (${count} backups exist)"
    fi
}

# Main function
main() {
    parse_args "$@"
    
    echo ""
    echo "╔════════════════════════════════════════════════════════════════╗"
    echo "║     Trading Assistant - Database Backup                        ║"
    echo "╚════════════════════════════════════════════════════════════════╝"
    echo ""
    
    check_prerequisites
    perform_backup || exit 1
    cleanup_old_backups
    
    echo ""
    log_success "Backup complete!"
    echo ""
    log_info "To restore this backup, run:"
    echo "  ./scripts/restore_db.sh ${BACKUP_FILENAME}"
    echo ""
    
    return 0
}

# Run main function
main "$@"
