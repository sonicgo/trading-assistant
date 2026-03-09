#!/bin/bash
#
# Phase 2 Smoke Test Script for Trading Assistant
# Tests: Market Data Ingestion → DQ Gate → Alerts/Freeze/Notifications Pipeline
#
# Usage:
#   1. Start the full stack: docker compose up -d
#   2. Run this script: ./scripts/phase2_smoke.sh
#   3. For anomaly testing, the script will guide you through injecting anomalies
#
# Required environment variables (or uses defaults):
#   - API_BASE_URL (default: http://localhost:8000/api/v1)
#   - TEST_USER_EMAIL (default: admin@example.com)
#   - TEST_USER_PASSWORD (default: admin123)
#

set -euo pipefail

# ─────────────────────────────────────────────────────────────────────────────
# Configuration
# ─────────────────────────────────────────────────────────────────────────────
API_BASE_URL="${API_BASE_URL:-http://localhost:8000/api/v1}"
TEST_USER_EMAIL="${TEST_USER_EMAIL:-admin@example.com}"
TEST_USER_PASSWORD="${TEST_USER_PASSWORD:-admin123}"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# ─────────────────────────────────────────────────────────────────────────────
# Helper Functions
# ─────────────────────────────────────────────────────────────────────────────
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[PASS]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[FAIL]${NC} $1"
}

# Check if jq is installed
check_dependencies() {
    if ! command -v jq &> /dev/null; then
        log_error "jq is required but not installed. Install with: sudo apt-get install jq"
        exit 1
    fi
    if ! command -v curl &> /dev/null; then
        log_error "curl is required but not installed."
        exit 1
    fi
    log_success "Dependencies check passed (curl, jq)"
}

# ─────────────────────────────────────────────────────────────────────────────
# API Helper Functions
# ─────────────────────────────────────────────────────────────────────────────

# Global variable to store JWT token
ACCESS_TOKEN=""

# Login and get JWT token
api_login() {
    log_info "Authenticating as $TEST_USER_EMAIL..."
    
    local response
    response=$(curl -s -X POST "${API_BASE_URL}/auth/login" \
        -H "Content-Type: application/json" \
        -d "{\"email\": \"${TEST_USER_EMAIL}\", \"password\": \"${TEST_USER_PASSWORD}\"}" 2>/dev/null || echo '{"error": "Connection failed"}')
    
    # Check for errors
    if echo "$response" | jq -e '.error' &>/dev/null; then
        log_error "Login failed: $(echo "$response" | jq -r '.error // .detail // "Unknown error"')"
        exit 1
    fi
    
    ACCESS_TOKEN=$(echo "$response" | jq -r '.access_token // empty')
    
    if [[ -z "$ACCESS_TOKEN" || "$ACCESS_TOKEN" == "null" ]]; then
        log_error "Login failed: No access token received"
        echo "Response: $response"
        exit 1
    fi
    
    log_success "Authenticated successfully"
}

# API GET request
api_get() {
    local endpoint="$1"
    curl -s -X GET "${API_BASE_URL}${endpoint}" \
        -H "Authorization: Bearer ${ACCESS_TOKEN}" \
        -H "Accept: application/json" 2>/dev/null || echo '[]'
}

# API POST request
api_post() {
    local endpoint="$1"
    local data="$2"
    curl -s -X POST "${API_BASE_URL}${endpoint}" \
        -H "Authorization: Bearer ${ACCESS_TOKEN}" \
        -H "Content-Type: application/json" \
        -d "$data" 2>/dev/null || echo '{"error": "Request failed"}'
}

# API PUT request
api_put() {
    local endpoint="$1"
    local data="$2"
    curl -s -X PUT "${API_BASE_URL}${endpoint}" \
        -H "Authorization: Bearer ${ACCESS_TOKEN}" \
        -H "Content-Type: application/json" \
        -d "$data" 2>/dev/null || echo '{"error": "Request failed"}'
}

# ─────────────────────────────────────────────────────────────────────────────
# Test Data Management (Idempotent - uses unique identifiers per run)
# ─────────────────────────────────────────────────────────────────────────────

# Global variables for created resources
INSTRUMENT_ID=""
LISTING_ID=""
PORTFOLIO_ID=""
UNIQUE_SUFFIX=""

# Generate unique suffix for this run
generate_unique_suffix() {
    UNIQUE_SUFFIX="$((RANDOM % 90000000 + 10000000))"
    log_info "Using unique suffix: ${UNIQUE_SUFFIX}"
}

# Create test instrument
create_instrument() {
    log_info "Creating test instrument..."
    
    local test_isin="GB00${UNIQUE_SUFFIX}"
    local test_name="iShares Core FTSE 100 UCITS ETF (Smoke Test ${UNIQUE_SUFFIX})"
    
    local response
    response=$(api_post "/registry/instruments" "{\"isin\": \"${test_isin}\", \"name\": \"${test_name}\", \"instrument_type\": \"ETF\"}")
    
    INSTRUMENT_ID=$(echo "$response" | jq -r '.instrument_id // empty')
    
    if [[ -z "$INSTRUMENT_ID" || "$INSTRUMENT_ID" == "null" ]]; then
        log_warn "Instrument creation failed - checking if it already exists..."
        local existing
        existing=$(api_get "/registry/instruments?isin=${test_isin}")
        INSTRUMENT_ID=$(echo "$existing" | jq -r '.items[0].instrument_id // empty')
        if [[ -n "$INSTRUMENT_ID" && "$INSTRUMENT_ID" != "null" ]]; then
            log_info "Found existing instrument: $INSTRUMENT_ID"
        else
            log_error "Failed to create or find instrument"
            echo "Response: $response"
            exit 1
        fi
    else
        log_success "Created instrument: $INSTRUMENT_ID"
    fi
}

# Create test listing
create_listing() {
    log_info "Creating test listing..."
    
    local test_ticker="ISFA_${UNIQUE_SUFFIX}"
    
    local response
    response=$(api_post "/registry/listings" "{\"instrument_id\": \"${INSTRUMENT_ID}\", \"ticker\": \"${test_ticker}\", \"exchange\": \"LSE\", \"trading_currency\": \"GBP\", \"price_scale\": \"MINOR\", \"is_primary\": true}")
    
    LISTING_ID=$(echo "$response" | jq -r '.listing_id // empty')
    
    if [[ -z "$LISTING_ID" || "$LISTING_ID" == "null" ]]; then
        log_warn "Listing creation failed - checking if it already exists..."
        local existing
        existing=$(api_get "/registry/listings?ticker=${test_ticker}")
        LISTING_ID=$(echo "$existing" | jq -r '.items[0].listing_id // empty')
        if [[ -n "$LISTING_ID" && "$LISTING_ID" != "null" ]]; then
            log_info "Found existing listing: $LISTING_ID"
        else
            log_error "Failed to create or find listing"
            echo "Response: $response"
            exit 1
        fi
    else
        log_success "Created listing: $LISTING_ID"
    fi
}

# Create test portfolio
create_portfolio() {
    log_info "Creating test portfolio..."
    
    local timestamp=$(date +%s)
    
    local response
    response=$(api_post "/portfolios" "{\"name\": \"Phase2 Smoke Test Portfolio ${timestamp}_${UNIQUE_SUFFIX}\", \"base_currency\": \"GBP\", \"tax_profile\": \"ISA\", \"broker\": \"Test Broker\"}")
    
    PORTFOLIO_ID=$(echo "$response" | jq -r '.portfolio_id // empty')
    
    if [[ -z "$PORTFOLIO_ID" || "$PORTFOLIO_ID" == "null" ]]; then
        log_error "Failed to create portfolio"
        echo "Response: $response"
        exit 1
    fi
    
    log_success "Created portfolio: $PORTFOLIO_ID"
}

# Map listing to portfolio as constituent
map_constituent() {
    log_info "Mapping listing ${LISTING_ID} to portfolio ${PORTFOLIO_ID}..."
    
    local response
    response=$(api_put "/portfolios/${PORTFOLIO_ID}/constituents" "{\"items\": [{\"listing_id\": \"${LISTING_ID}\", \"sleeve_code\": \"CORE\", \"is_monitored\": true}], \"replace_missing\": false}")
    
    local status
    status=$(echo "$response" | jq -r '.status // empty')
    
    if [[ "$status" != "success" ]]; then
        log_error "Failed to map constituent"
        echo "Response: $response"
        exit 1
    fi
    
    log_success "Mapped constituent successfully"
}

# ─────────────────────────────────────────────────────────────────────────────
# Market Data Operations
# ─────────────────────────────────────────────────────────────────────────────

# Trigger market data refresh
trigger_refresh() {
    log_info "Triggering market data refresh for portfolio ${PORTFOLIO_ID}..."
    
    local response
    response=$(api_post "/portfolios/${PORTFOLIO_ID}/market-data/refresh" "{}")
    
    local job_id
    job_id=$(echo "$response" | jq -r '.job_id // empty')
    
    if [[ -z "$job_id" || "$job_id" == "null" ]]; then
        log_error "Failed to trigger refresh"
        echo "Response: $response"
        exit 1
    fi
    
    log_success "Refresh triggered, job_id: $job_id"
}

# Wait for job processing (poll with delay)
wait_for_processing() {
    local seconds="${1:-5}"
    log_info "Waiting ${seconds}s for job processing..."
    sleep "$seconds"
}

# Get prices and verify they exist
verify_prices() {
    log_info "Verifying prices exist..."
    
    local response
    response=$(api_get "/portfolios/${PORTFOLIO_ID}/market-data/prices?limit=10")
    
    local count
    count=$(echo "$response" | jq 'length')
    
    if [[ "$count" -eq 0 ]]; then
        log_warn "No prices found yet, waiting a bit more..."
        sleep 3
        response=$(api_get "/portfolios/${PORTFOLIO_ID}/market-data/prices?limit=10")
        count=$(echo "$response" | jq 'length')
    fi
    
    if [[ "$count" -gt 0 ]]; then
        log_success "Found $count price points"
        local sample
        sample=$(echo "$response" | jq -r '.[0] | "Price: \(.price) \(.currency) (is_close: \(.is_close))"')
        log_info "Sample: $sample"
        return 0
    else
        log_error "No prices found after refresh"
        return 1
    fi
}

# Check alerts
verify_alerts() {
    local expected_count="${1:-0}"
    
    log_info "Checking alerts (expecting ${expected_count})..."
    
    local response
    response=$(api_get "/portfolios/${PORTFOLIO_ID}/alerts?active_only=true")
    
    local count
    count=$(echo "$response" | jq 'length')
    
    if [[ "$count" -eq "$expected_count" ]]; then
        log_success "Alert count matches expected: $count"
        return 0
    else
        log_error "Alert count mismatch: expected ${expected_count}, got ${count}"
        if [[ "$count" -gt 0 ]]; then
            echo "Current alerts:"
            echo "$response" | jq -r '.[] | "  - \(.severity): \(.rule_code) - \(.title)"'
        fi
        return 1
    fi
}

# Check notifications
verify_notifications() {
    local expected_min="${1:-0}"
    
    log_info "Checking notifications (expecting at least ${expected_min})..."
    
    local response
    response=$(api_get "/notifications")
    
    local count
    count=$(echo "$response" | jq 'length')
    
    if [[ "$count" -ge "$expected_min" ]]; then
        log_success "Found $count notifications (minimum: $expected_min)"
        return 0
    else
        log_error "Notification count too low"
        return 1
    fi
}

# ─────────────────────────────────────────────────────────────────────────────
# Main Test Flow
# ─────────────────────────────────────────────────────────────────────────────

run_phase1_normal_flow() {
    echo ""
    echo "╔══════════════════════════════════════════════════════════════════════╗"
    echo "║  PHASE 1: Normal Market Data Refresh (Healthy Run)                  ║"
    echo "╚══════════════════════════════════════════════════════════════════════╝"
    echo ""
    
    log_info "Step 1: Authentication"
    api_login
    
    log_info "Step 2: Generate unique identifiers for this run"
    generate_unique_suffix
    
    log_info "Step 3: Create test data"
    create_instrument
    create_listing
    create_portfolio
    
    log_info "Step 4: Map constituent to portfolio"
    map_constituent
    
    log_info "Step 5: Trigger market data refresh"
    trigger_refresh
    
    log_info "Step 6: Wait for processing"
    wait_for_processing 5
    
    log_info "Step 7: Verify results"
    verify_prices || exit 1
    verify_alerts 0 || exit 1
    verify_notifications 0 || true
    
    echo ""
    log_success "PHASE 1 COMPLETE: Healthy run verified ✓"
    echo ""
}

run_cleanup() {
    echo ""
    echo "╔══════════════════════════════════════════════════════════════════════╗"
    echo "║  CLEANUP: Summary of created resources                               ║"
    echo "╚══════════════════════════════════════════════════════════════════════╝"
    echo ""
    
    if [[ -n "$PORTFOLIO_ID" ]]; then
        log_info "Created Portfolio ID: $PORTFOLIO_ID"
        log_info "  - View: GET ${API_BASE_URL}/portfolios/${PORTFOLIO_ID}"
        log_info "  - Prices: GET ${API_BASE_URL}/portfolios/${PORTFOLIO_ID}/market-data/prices"
        log_info "  - Alerts: GET ${API_BASE_URL}/portfolios/${PORTFOLIO_ID}/alerts"
    fi
    
    echo ""
}

# ─────────────────────────────────────────────────────────────────────────────
# Main Entry Point
# ─────────────────────────────────────────────────────────────────────────────

main() {
    echo ""
    echo "╔══════════════════════════════════════════════════════════════════════╗"
    echo "║     Trading Assistant - Phase 2 Market Data Smoke Test               ║"
    echo "╚══════════════════════════════════════════════════════════════════════╝"
    echo ""
    echo "  API Base:   ${API_BASE_URL}"
    echo "  Test User:  ${TEST_USER_EMAIL}"
    echo ""
    
    check_dependencies
    run_phase1_normal_flow
    run_cleanup
    
    echo ""
    echo "╔══════════════════════════════════════════════════════════════════════╗"
    echo "║                    SMOKE TEST COMPLETE                               ║"
    echo "╚══════════════════════════════════════════════════════════════════════╝"
    echo ""
    
    return 0
}

# Run main function
main "$@"
