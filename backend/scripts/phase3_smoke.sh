#!/bin/bash
set -e

API_URL="http://localhost:8000/api/v1"
EMAIL="admin@example.com"
PASSWORD="admin123"

echo "Phase 3 Smoke Test"
echo "=================="

# Step 1: Login
echo "Step 1: Login"
LOGIN_RESPONSE=$(curl -s -X POST "$API_URL/auth/login" \
    -H "Content-Type: application/json" \
    -d "{\"email\":\"$EMAIL\",\"password\":\"$PASSWORD\"}")

if echo "$LOGIN_RESPONSE" | grep -q "access_token"; then
    ACCESS_TOKEN=$(echo "$LOGIN_RESPONSE" | grep -o '"access_token":"[^"]*' | cut -d'"' -f4)
    echo "  ✓ Login successful"
else
    echo "  ✗ Login failed"
    exit 1
fi

# Step 2: Get portfolio
echo "Step 2: Get portfolio"
PORTFOLIOS=$(curl -s -X GET "$API_URL/portfolios" -H "Authorization: Bearer $ACCESS_TOKEN")
PORTFOLIO_ID=$(echo "$PORTFOLIOS" | grep -o '"portfolio_id":"[^"]*' | head -1 | cut -d'"' -f4)
echo "  ✓ Using portfolio: $PORTFOLIO_ID"

# Step 3: Post contribution
echo "Step 3: Post contribution"
CONTRIB=$(curl -s -X POST "$API_URL/portfolios/$PORTFOLIO_ID/ledger/batches" \
    -H "Content-Type: application/json" \
    -H "Authorization: Bearer $ACCESS_TOKEN" \
    -d '{"entries":[{"entry_kind":"CONTRIBUTION","effective_at":"2024-01-01T00:00:00Z","net_cash_delta_gbp":"1000.00"}]}')

if echo "$CONTRIB" | grep -q "batch_id"; then
    echo "  ✓ Contribution posted"
else
    echo "  ✗ Contribution failed: $CONTRIB"
    exit 1
fi

# Step 4: Check cash snapshot
echo "Step 4: Check cash snapshot"
CASH=$(curl -s -X GET "$API_URL/portfolios/$PORTFOLIO_ID/snapshots/cash" -H "Authorization: Bearer $ACCESS_TOKEN")
if echo "$CASH" | grep -q "balance_gbp"; then
    echo "  ✓ Cash snapshot retrieved"
else
    echo "  ✗ Cash snapshot failed: $CASH"
    exit 1
fi

# Step 5: List ledger batches
echo "Step 5: List ledger batches"
BATCHES=$(curl -s -X GET "$API_URL/portfolios/$PORTFOLIO_ID/ledger/batches" -H "Authorization: Bearer $ACCESS_TOKEN")
if echo "$BATCHES" | grep -q "items"; then
    echo "  ✓ Batches listed"
else
    echo "  ✗ Batches list failed: $BATCHES"
    exit 1
fi

# Step 6: List ledger entries
echo "Step 6: List ledger entries"
ENTRIES=$(curl -s -X GET "$API_URL/portfolios/$PORTFOLIO_ID/ledger/entries" -H "Authorization: Bearer $ACCESS_TOKEN")
if echo "$ENTRIES" | grep -q "items"; then
    echo "  ✓ Entries listed"
else
    echo "  ✗ Entries list failed: $ENTRIES"
    exit 1
fi

# Step 7: Preview CSV import
echo "Step 7: Preview CSV import"
CSV_B64=$(echo "Investment,Quantity,Price,Value (£),Cost (£),Change (£),Change (%),Price +/- today (%),Valuation currency,Market currency,Exchange rate,Date,Time,Portfolio,Ticker
Cash GBP,1,1,5000.00,5000.00,0,0,0,GBP,GBP,1,10-Mar-26,17:07,Test," | base64 -w 0)

PREVIEW=$(curl -s -X POST "$API_URL/portfolios/$PORTFOLIO_ID/ledger/imports/preview" \
    -H "Content-Type: application/json" \
    -H "Authorization: Bearer $ACCESS_TOKEN" \
    -d "{\"csv_profile\":\"positions_gbp_v1\",\"file_content_base64\":\"$CSV_B64\"}")

if echo "$PREVIEW" | grep -q "plan_hash\|errors"; then
    echo "  ✓ CSV preview completed"
else
    echo "  ✗ CSV preview failed: $PREVIEW"
    exit 1
fi

echo ""
echo "=================="
echo "All tests passed!"
