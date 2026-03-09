# Phase 2 Smoke Test

This smoke test script validates the Trading Assistant Phase 2 implementation:
**Market Data Ingestion → DQ Gate → Alerts/Freeze/Notifications Pipeline**

## Files Created/Modified

1. **`scripts/phase2_smoke.sh`** - The main smoke test script
2. **`backend/app/core/config.py`** - Added mock anomaly configuration options
3. **`backend/app/worker/price_refresh_worker.py`** - Modified to support environment-based anomaly injection

## Quick Start

```bash
# 1. Start the full stack
docker compose up -d

# 2. Run the smoke test
./scripts/phase2_smoke.sh
```

## What the Test Does

### Phase 1: Normal Flow (Automated)
1. Authenticates and obtains JWT token
2. Creates test instrument (iShares FTSE 100 ETF)
3. Creates test listing (ISFA on LSE)
4. Creates test portfolio
5. Maps listing as monitored constituent
6. Triggers market data refresh
7. Verifies prices exist in database
8. Verifies no alerts (healthy run)

### Phase 2: Anomaly Flow (Requires Manual Setup)
1. Enables anomaly injection mode
2. Triggers refresh with anomalous data
3. Verifies DQ Gate detects violations
4. Verifies alert created
5. Verifies portfolio frozen (if CRITICAL)
6. Verifies notification emitted

## Anomaly Injection

To test the DQ Gate's ability to detect and respond to bad data, the MockProvider supports three anomaly types:

| Anomaly Type | Environment Variable | Effect | Expected DQ Rule |
|--------------|----------------------|--------|------------------|
| Stale Prices | `MOCK_STALE_PRICES=true` | Returns prices from 7 days ago | `STALE_PRICE_CLOSE` |
| Jump Prices | `MOCK_JUMP_PRICES=true` | Returns prices 10x higher | `PRICE_JUMP` |
| Scale Mismatch | `MOCK_SCALE_MISMATCH=true` | Returns GBX as GBP (100x) | `PRICE_SCALE_MISMATCH` |

### Running Anomaly Tests

**Option 1: Environment Variables (Recommended)**

1. Add to your `.env` file:
   ```
   MOCK_STALE_PRICES=true
   ```

2. Restart the worker:
   ```bash
   docker compose restart worker
   ```

3. Run the smoke test and follow Phase 2 prompts

**Option 2: Manual Code Edit**

1. Edit `backend/app/worker/price_refresh_worker.py` line 81
2. Change `adapter = MockProvider()` to:
   - `adapter = MockProvider(stale_prices=True)` for stale prices
   - `adapter = MockProvider(jump_prices=True)` for price jump
   - `adapter = MockProvider(scale_mismatch=True)` for scale error

3. Restart worker: `docker compose restart worker`

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `API_BASE_URL` | `http://localhost:8000/api/v1` | API base URL |
| `TEST_USER_EMAIL` | `admin@example.com` | Test user email |
| `TEST_USER_PASSWORD` | `admin123` | Test user password |
| `MOCK_STALE_PRICES` | `false` | Inject stale prices |
| `MOCK_JUMP_PRICES` | `false` | Inject price jumps |
| `MOCK_SCALE_MISMATCH` | `false` | Inject scale mismatch |

## API Endpoints Tested

- `POST /auth/login` - Authentication
- `POST /registry/instruments` - Create instrument
- `POST /registry/listings` - Create listing
- `POST /portfolios` - Create portfolio
- `PUT /portfolios/{pid}/constituents` - Map constituents
- `POST /portfolios/{pid}/market-data/refresh` - Trigger refresh
- `GET /portfolios/{pid}/market-data/prices` - Get prices
- `GET /portfolios/{pid}/alerts` - Get alerts
- `GET /notifications` - Get notifications

## Expected Outputs

### Phase 1 Success Indicators
```
[PASS] Authenticated successfully
[PASS] Created instrument: <uuid>
[PASS] Created listing: <uuid>
[PASS] Created portfolio: <uuid>
[PASS] Mapped constituent successfully
[PASS] Refresh triggered, job_id: <uuid>
[PASS] Found N price points
[PASS] Alert count matches expected: 0
```

### Phase 2 Success Indicators (with anomaly)
```
[PASS] Refresh triggered, job_id: <uuid>
[PASS] Alert created: 1 alert(s) found
  - CRITICAL: STALE_PRICE_CLOSE - Stale price detected
[PASS] CRITICAL alert found: 1
[PASS] Freeze status correct: true
[PASS] Found 1 notifications (minimum: 1)
```

## Troubleshooting

**Issue**: "No prices found after refresh"
- **Solution**: Increase the wait time in `wait_for_processing()` function
- Worker may need more time to process the job

**Issue**: "Alert count mismatch"
- **Solution**: Ensure worker has anomaly mode enabled before Phase 2
- Check worker logs: `docker compose logs worker -f`

**Issue**: "Cannot determine freeze status"
- **Solution**: Freeze endpoint may not be implemented yet - check Phase 2 build progress
- Portfolio freeze status is optional for smoke test Phase 1

## Verification Commands

Manual verification of test results:

```bash
# Get JWT token
TOKEN=$(curl -s -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "admin@example.com", "password": "admin123"}' | jq -r '.access_token')

# View created portfolio
curl -H "Authorization: Bearer $TOKEN" \
  http://localhost:8000/api/v1/portfolios/{portfolio_id}

# View prices
curl -H "Authorization: Bearer $TOKEN" \
  http://localhost:8000/api/v1/portfolios/{portfolio_id}/market-data/prices

# View alerts
curl -H "Authorization: Bearer $TOKEN" \
  http://localhost:8000/api/v1/portfolios/{portfolio_id}/alerts?active_only=true

# View notifications
curl -H "Authorization: Bearer $TOKEN" \
  http://localhost:8000/api/v1/notifications
```
