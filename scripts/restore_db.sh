#!/bin/bash
#
# Database Restore Script for Trading Assistant
# Restores a PostgreSQL database from a backup file
#
# Usage:
#   ./scripts/restore_db.sh backup_file.sql         # Restore uncompressed backup
#   ./scripts/restore_db.sh backup_file.sql.gz      # Restore compressed backup
#   ./scripts/restore_db.sh --help                  # Show help
#
# IMPORTANT: This script will DROP and recreate the database.
# Make sure you have a current backup before proceeding.
#

set -euo pipefail

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
BACKUP_DIR="${PROJECT_ROOT}/backups"
CONTAINER_NAME="trading-assistant-db-1"
DB_NAME="trading_assistant"
DB_USER="ta_app"
FORCE=false

# Colors for output
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

show_help() {
    cat << EOF
Trading Assistant Database Restore Script

Usage: $0 [OPTIONS] <backup_file>

Arguments:
  backup_file       Path to backup file (relative to backups/ or absolute path)

Options:
  --force, -f       Skip confirmation prompt (use with caution)
  --help, -h        Show this help message

Environment Variables:
  BACKUP_DIR        Directory containing backups (default: ./backups)
  DB_NAME           Database name (default: trading_assistant)
  DB_USER           Database user (default: ta_app)

Examples:
  $0 trading_assistant_20240311_120000.sql
  $0 --force trading_assistant_20240311_120000.sql.gz
  BACKUP_DIR=/mnt/backups $0 /mnt/backups/backup.sql

WARNING:
  This script will DROP the existing database and recreate it.
  All current data will be lost. Ensure you have a backup.
EOF
}

parse_args() {
    while [[ $# -gt 0 ]]; do
        case $1 in
            --force|-f)
                FORCE=true
                shift
                ;;
            --help|-h)
                show_help
                exit 0
                ;;
            -*)
                log_error "Unknown option: $1"
                show_help
                exit 1
                ;;
            *)
                BACKUP_FILE="$1"
                shift
                ;;
        esac
    done
    
    if [[ -z "${BACKUP_FILE:-}" ]]; then
        log_error "No backup file specified"
        show_help
        exit 1
    fi
}

check_prerequisites() {
    log_info "Checking prerequisites..."
    
    if ! docker ps &> /dev/null; then
        log_error "Docker is not running or not accessible"
        exit 1
    fi
    
    if ! docker ps | grep -q "${CONTAINER_NAME}"; then
        log_error "Database container '${CONTAINER_NAME}' is not running"
        exit 1
    fi
    
    local backup_path="$BACKUP_FILE"
    if [[ ! "$backup_path" = /* ]]; then
        backup_path="${BACKUP_DIR}/${BACKUP_FILE}"
    fi
    
    if [[ ! -f "$backup_path" ]]; then
        log_error "Backup file not found: $backup_path"
        exit 1
    fi
    
    log_success "Prerequisites check passed"
}

confirm_restore() {
    if [[ "$FORCE" == true ]]; then
        return 0
    fi
    
    echo ""
    log_warn "WARNING: This will DELETE all current data in the database!"
    log_warn "Database '${DB_NAME}' will be dropped and recreated."
    echo ""
    read -p "Are you sure you want to continue? (yes/no): " confirm
    
    if [[ "$confirm" != "yes" ]]; then
        log_info "Restore cancelled by user"
        exit 0
    fi
}

stop_services() {
    log_info "Stopping API and worker services..."
    cd "$PROJECT_ROOT"
    docker compose stop api worker 2>/dev/null || true
    log_success "Services stopped"
}

start_services() {
    log_info "Starting API and worker services..."
    cd "$PROJECT_ROOT"
    docker compose start api worker 2>/dev/null || true
    log_success "Services started"
}

perform_restore() {
    local backup_path="$BACKUP_FILE"
    if [[ ! "$backup_path" = /* ]]; then
        backup_path="${BACKUP_DIR}/${BACKUP_FILE}"
    fi
    
    local is_compressed=false
    if [[ "$backup_path" == *.gz ]]; then
        is_compressed=true
        log_info "Detected compressed backup"
    fi
    
    log_info "Preparing database for restore..."
    
    docker exec "${CONTAINER_NAME}" psql -U "${DB_USER}" -d postgres -c "
        SELECT pg_terminate_backend(pg_stat_activity.pid)
        FROM pg_stat_activity
        WHERE pg_stat_activity.datname = '${DB_NAME}'
        AND pid <> pg_backend_pid();
    " 2>/dev/null || true
    
    log_info "Dropping database '${DB_NAME}'..."
    docker exec "${CONTAINER_NAME}" dropdb -U "${DB_USER}" --if-exists "${DB_NAME}" 2>/dev/null || true
    
    log_info "Creating fresh database '${DB_NAME}'..."
    docker exec "${CONTAINER_NAME}" createdb -U "${DB_USER}" "${DB_NAME}"
    
    log_info "Restoring from backup (this may take several minutes)..."
    
    if [[ "$is_compressed" == true ]]; then
        gunzip -c "$backup_path" | docker exec -i "${CONTAINER_NAME}" psql -U "${DB_USER}" -d "${DB_NAME}" 2>/dev/null
    else
        docker exec -i "${CONTAINER_NAME}" psql -U "${DB_USER}" -d "${DB_NAME}" < "$backup_path" 2>/dev/null
    fi
    
    if [[ $? -eq 0 ]]; then
        log_success "Database restored successfully"
        return 0
    else
        log_error "Database restore failed"
        return 1
    fi
}

verify_restore() {
    log_info "Verifying restore..."
    
    local table_count
    table_count=$(docker exec "${CONTAINER_NAME}" psql -U "${DB_USER}" -d "${DB_NAME}" -t -c "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = 'public';" 2>/dev/null | xargs)
    
    log_info "Found ${table_count} tables in restored database"
    
    if [[ "$table_count" -gt 0 ]]; then
        log_success "Restore verification passed"
        return 0
    else
        log_error "Restore verification failed - no tables found"
        return 1
    fi
}

main() {
    parse_args "$@"
    
    echo ""
    echo "╔════════════════════════════════════════════════════════════════╗"
    echo "║     Trading Assistant - Database Restore                       ║"
    echo "╚════════════════════════════════════════════════════════════════╝"
    echo ""
    
    check_prerequisites
    confirm_restore
    stop_services
    perform_restore || {
        start_services
        exit 1
    }
    verify_restore
    start_services
    
    echo ""
    log_success "Database restore complete!"
    log_info "Services are starting up. Wait 10-15 seconds before accessing the application."
    echo ""
    
    return 0
}

main "$@"
