# Trading Assistant - Implementation Report

## Executive Summary

The Trading Assistant is a fully local, privacy-first portfolio management system designed to implement the Boglehead passive investment philosophy. It provides institutional-grade portfolio analytics and deterministic trade recommendations while maintaining complete user control over data and execution.

**Core Principles:**
- **Privacy-First:** All data stored locally in PostgreSQL, no cloud dependencies
- **Recommendation-Only:** Generates trade plans but never executes trades automatically
- **Deterministic:** Same inputs always produce identical outputs (auditable, testable)
- **Event-Sourced:** Complete audit trail via append-only ledger

**Manifesto Implementation:**
The system codifies the Boglehead investment philosophy through policy allocations (target weights per sleeve), drift thresholds (5%), and systematic rebalancing rules. The deterministic engine ensures trades are calculated purely on math, removing emotional decision-making.

---

## System Architecture

### 2.1 Tech Stack

| Layer | Technology | Version | Purpose |
|-------|-----------|---------|---------|
| Frontend | Next.js | 14.x | React framework with App Router |
| Frontend | React | 18.x | UI component library |
| Frontend | TypeScript | 5.x | Type-safe JavaScript |
| Frontend | Tailwind CSS | 3.x | Utility-first styling |
| Frontend | TanStack Query | 5.x | Server state management |
| Backend | FastAPI | 0.115.x | High-performance Python API |
| Backend | SQLAlchemy | 2.x | ORM for database access |
| Backend | Alembic | 1.x | Database migrations |
| Backend | Pydantic | 2.x | Data validation |
| Database | PostgreSQL | 16 | Persistent storage |
| Cache | Redis | 7 | Job queue, caching |
| Market Data | yfinance | 0.2.54 | Yahoo Finance EOD price data |
| Infrastructure | Docker Compose | - | Local deployment |

**Language:** Python 3.11 with strict type hints throughout

### 2.2 Separation of Concerns

```
┌─────────────────────────────────────────────────────────────┐
│                         UI Layer                            │
│  (React Components, Hooks, Pages - Presentation Only)       │
└───────────────────────┬─────────────────────────────────────┘
                        │ HTTP/REST
┌───────────────────────▼─────────────────────────────────────┐
│                        API Layer                            │
│  (FastAPI Endpoints, Pydantic Schemas, Dependency Injection)│
└───────────────────────┬─────────────────────────────────────┘
                        │
┌───────────────────────▼─────────────────────────────────────┐
│                     Service Layer                           │
│  (Business Logic, Calculations, Data Transformations)       │
└───────────────────────┬─────────────────────────────────────┘
                        │
┌───────────────────────▼─────────────────────────────────────┐
│                      Domain Layer                           │
│  (Pure Data Models - SQLAlchemy, Pure Math Functions)       │
└───────────────────────┬─────────────────────────────────────┘
                        │ SQL
┌───────────────────────▼─────────────────────────────────────┐
│                       Data Layer                            │
│              (PostgreSQL via SQLAlchemy ORM)                │
└─────────────────────────────────────────────────────────────┘
```

### 2.3 Key Architectural Decisions

1. **100% Decimal Math:** All monetary calculations use Python's `decimal.Decimal` to prevent floating-point errors. Database columns use `Numeric(precision=18, scale=8)`.

2. **Deterministic Calculation Engine:** The Phase 4 engine produces identical outputs for identical inputs. No randomness, no external API calls during calculation, pure mathematical functions.

3. **Event-Sourced Ledger:** All portfolio changes recorded as immutable events (LedgerEntry). Historical state can be reconstructed at any point in time.

4. **API-First Design:** RESTful JSON API between frontend and backend. No server-side rendering of UI components.

5. **No Trading API Integration:** System generates recommendations but user executes trades manually through their broker. Protects capital from software bugs.

---

## Phase Completion Summary

### Phase 1: Registry (Entity Master)

**Purpose:** Define the universe of tradable instruments and organizational structure.

**Deliverables:**

| Component | File | Description |
|-----------|------|-------------|
| Instrument Model | `backend/app/domain/models.py` (lines 38-50) | ISIN-level instrument master (ISIN, name, type: ETF/STOCK/ETC/FUND) |
| Listing Model | `backend/app/domain/models.py` (lines 53-65) | Exchange-specific tickers (ticker, exchange, currency, price scale: MAJOR/MINOR) |
| Sleeve Taxonomy | `backend/app/domain/models.py` (lines 68-79) | Investment strategy buckets (CORE, SATELLITE, CASH, GROWTH_SEMIS, ENERGY, HEALTHCARE) |
| Portfolio Model | `backend/app/domain/models.py` (lines 82-95) | Portfolio definitions with tax wrappers (SIPP, ISA, GIA) |
| Registry API | `backend/app/api/v1/endpoints/registry.py` | CRUD endpoints for instruments and listings |
| Frontend Registry | `frontend/src/app/registry/` | UI pages for managing instruments and listings |

**Key Design Decisions:**
- Instruments identified by ISIN (unique, permanent)
- Listings link instruments to exchanges (one instrument can have multiple listings)
- Price scale distinguishes between MAJOR (GBP, USD) and MINOR (GBX = GBP/100)
- Sleeves provide policy-level allocation buckets

---

### Phase 2: Market Data

**Purpose:** Fetch, store, and validate market prices for portfolio valuation.

**Deliverables:**

| Component | File | Description |
|-----------|------|-------------|
| PricePoint Model | `backend/app/domain/models.py` (lines 115-132) | Append-only time series of close prices |
| FxRate Model | `backend/app/domain/models.py` (lines 135-148) | Cross-currency exchange rates |
| Alert Model | `backend/app/domain/models.py` (lines 151-163) | Data quality and policy violation alerts |
| FreezeState Model | `backend/app/domain/models.py` (lines 166-178) | Portfolio-level circuit breaker |
| Market Data API | `backend/app/api/v1/endpoints/market_data.py` | Price refresh endpoints |
| Market Data Ingest | `backend/app/services/market_data_ingest.py` | Price fetching logic |
| Data Quality | `backend/app/services/data_quality.py` | Validation and staleness checks |
| Market Data Adapter | `backend/app/services/market_data_adapter.py` | Protocol for provider independence |
| YFinance Provider | `backend/app/services/providers/yfinance_adapter.py` | Yahoo Finance EOD price provider |
| Mock Provider | `backend/app/services/providers/mock_provider.py` | Deterministic test provider |
| Market Data Service | `backend/app/services/market_data_service.py` | On-demand sync with rate limiting |
| Sync API Endpoint | `backend/app/api/v1/endpoints/market_data.py` | POST /market-data/sync endpoint |

**Key Guardrails:**

1. **3-Day Staleness Check:**
   - Implementation: `backend/app/services/engine_inputs.py` (lines 91-131)
   - Behavior: Blocks trade plan generation if any required price is older than 3 days
   - Error Message: "Stale market data for {ticker}; latest trusted price is older than 3 days"

2. **Trusted Close Prices:**
   - PricePoint.is_close flag distinguishes end-of-day closes from intraday
   - Only is_close=true prices used for valuation
   - Prevents trading on unreliable intraday data

3. **Alert System:**
   - Automatic alerts for missing prices, FX rate gaps
   - Severity levels: INFO, WARN, CRITICAL
   - Alerts linked to portfolio freeze mechanism

4. **Freeze Mechanism:**
    - Portfolio-level circuit breaker
    - Prevents trade plan generation during data quality issues
    - Manual unfreeze via API/UI

**Market Data Provider Architecture:**

The system uses a provider-agnostic adapter pattern to support multiple market data sources:

```
┌─────────────────────────────────────────────────────────────┐
│                    Market Data Ingest                       │
│              (market_data_ingest.py)                        │
│                                                             │
│  ┌─────────────────┐         ┌─────────────────┐           │
│  │  YFinance       │         │  MockProvider   │           │
│  │  Adapter        │◄───────►│  (Testing)      │           │
│  │                 │         │                 │           │
│  │  • EOD Prices   │         │  • Deterministic│           │
│  │  • FX Rates     │         │  • Anomalies    │           │
│  │  • LSE Rule     │         │  • No network   │           │
│  └─────────────────┘         └─────────────────┘           │
│           │                                                 │
│           ▼                                                 │
│  ┌──────────────────────────────────────────────┐          │
│  │         MarketDataAdapter Protocol           │          │
│  │  - fetch_prices(listing_ids)                 │          │
│  │  - fetch_fx_rates(pairs)                     │          │
│  │  - source_id                                 │          │
│  └──────────────────────────────────────────────┘          │
└─────────────────────────────────────────────────────────────┘
```

**YFinance Provider Features:**

1. **LSE Rule for UK ETFs:**
   - Bare tickers (e.g., `VWRP`, `IGL5`, `CSH2`) automatically get `.L` suffix
   - Tickers with existing suffix (e.g., `VWRP.L`, `AAPL`) remain unchanged
   - Fallback to bare ticker if `.L` returns no data (handles US stocks)
   - Implementation: `_lse_ticker(ticker) -> ticker if "." in ticker else f"{ticker}.L"`

2. **Async I/O:**
   - Uses `asyncio.to_thread()` to run yfinance calls without blocking event loop
   - Thread-safe for concurrent price fetches

3. **Error Handling:**
   - `ProviderUnavailableError`: Network or Yahoo Finance service issues
   - `InvalidResponseError`: Malformed or empty data returned
   - `RateLimitError`: Yahoo Finance rate limiting (handled via retry)

4. **Decimal Precision:**
   - Prices returned as 4-decimal strings (e.g., `"127.6800"`)
   - FX rates returned as 6-decimal strings (e.g., `"1.274500"`)
   - Compatible with `decimal.Decimal` conversion

**Example Live Price Fetch:**
```python
adapter = YFinanceAdapter()
quotes = await adapter.fetch_prices(["VWRP"], want_close=True, want_intraday=False)
# Returns: PriceQuote(listing_id="VWRP", price="127.6800", currency="GBP", ...)
```

**On-Demand Market Data Sync:**

A user-triggered sync capability that fetches latest prices for portfolio holdings:

| Component | File | Description |
|-----------|------|-------------|
| Market Data Service | `backend/app/services/market_data_service.py` | On-demand sync logic with rate limiting |
| Sync API Endpoint | `backend/app/api/v1/endpoints/market_data.py` | POST /{portfolio_id}/market-data/sync |
| Sync Hook | `frontend/src/hooks/use-market-data.ts` | useSyncMarketData mutation |
| Sync Button | `frontend/src/app/portfolios/[id]/page.tsx` | "Refresh Prices" button in portfolio header |

**Sync Process Flow:**

```
User clicks "Refresh Prices"
         │
         ▼
┌──────────────────────┐
│   Frontend Hook      │ useSyncMarketData()
│   (TanStack Query)   │
└──────────┬───────────┘
           │ POST /market-data/sync
           ▼
┌──────────────────────┐
│   API Endpoint       │ market_data.py
│   (FastAPI)          │ async def sync_market_data()
└──────────┬───────────┘
           │
           ▼
┌──────────────────────┐
│   Service Layer      │ market_data_service.py
│   • Query holdings   │ sync_portfolio_prices()
│   • Fetch prices     │ await adapter.fetch_prices()
│   • Rate limiting    │ await asyncio.sleep(1.5)
│   • Save to DB       │ INSERT INTO price_points
└──────────┬───────────┘
           │
           ▼
┌──────────────────────┐
│   UI Update          │ onSuccess: invalidateQueries
│   (Auto-refresh)     │ prices table refreshes
└──────────────────────┘
```

**Key Features:**

1. **Rate Limiting:** 1.5-second delay between Yahoo Finance API calls to respect TOS
2. **Idempotent Writes:** Uses ON CONFLICT DO NOTHING to prevent duplicate prices
3. **Real-time UI:** TanStack Query invalidation auto-refreshes price table
4. **Loading State:** Button shows "Syncing..." during operation
5. **Error Handling:** Graceful handling of rate limits, network errors, missing tickers

**API Response Example:**
```json
{
  "portfolio_id": "0dbb642d-ce67-4752-b6e3-6242d8c69d72",
  "total_listings": 7,
  "prices_fetched": 7,
  "prices_inserted": 0,
  "errors": [],
  "status": "completed"
}
```

---

### Phase 3: The Ledger (Book of Record)

**Purpose:** Event-sourced accounting system for all portfolio activity with immutable audit trail.

**Deliverables:**

| Component | File | Description |
|-----------|------|-------------|
| LedgerBatch Model | `backend/app/domain/models.py` (lines 230-250) | Transaction groups with idempotency |
| LedgerEntry Model | `backend/app/domain/models.py` (lines 253-278) | Individual transactions (5 kinds) |
| CashSnapshot Model | `backend/app/domain/models.py` (lines 281-293) | Current cash balance per portfolio |
| HoldingSnapshot Model | `backend/app/domain/models.py` (lines 296-310) | Current positions per portfolio |
| Ledger API | `backend/app/api/v1/endpoints/ledger.py` | Post entries, get history |
| Snapshots API | `backend/app/api/v1/endpoints/snapshots.py` | Query current state |
| Ledger Service | `backend/app/services/ledger_service.py` | Core accounting logic |
| CSV Parser | `backend/app/services/csv_parser.py` | Positions CSV import |

**Entry Kinds:**

```python
EntryKind = 'CONTRIBUTION' | 'BUY' | 'SELL' | 'ADJUSTMENT' | 'REVERSAL'
```

- **CONTRIBUTION:** Cash deposit/withdrawal
- **BUY:** Purchase of security (negative cash, positive quantity)
- **SELL:** Sale of security (positive cash, negative quantity)
- **ADJUSTMENT:** Manual correction by admin
- **REVERSAL:** Compensating entry that reverses a previous entry

**CSV Import Features:**

1. **BOM Stripping:**
   - Handles Excel-exported UTF-8 files with byte-order marks
   - Implementation: `csv_parser.py` detects and strips UTF-8 BOM

2. **Strict Ticker Mapping:**
   - Requires exact ticker match in database
   - Validates all tickers exist before processing
   - Rejects CSV with unknown tickers

3. **Smart Math Engine:**
   - Calculates adjustment entries (buy/sell to reach target positions)
   - Compares current holdings vs CSV targets
   - Generates proposed ledger entries

4. **Idempotency:**
   - SHA256 hash of file content prevents duplicate imports
   - Same file cannot be imported twice

5. **Reconciliation:**
   - CSV book cost vs calculated book cost
   - Warnings for mismatches

**Event Sourcing Principles:**

- **Append-Only:** Entries never deleted or modified
- **Immutability:** Historical state preserved forever
- **Reversals:** Create compensating entries instead of updates
- **Snapshots:** Derived views (can be rebuilt from entries)
- **Versioning:** Optimistic concurrency control via version_no

---

### Phase 4: The Brain (Deterministic Calculation Engine)

**Purpose:** Generate trade recommendations based on policy drift using pure mathematical calculations.

**Deliverables:**

| Component | File | Description |
|-----------|------|-------------|
| Domain Models | `backend/app/domain/engine.py` | ProposedTrade, TradePlan, AssetPosition, RunInputSnapshot |
| World State Gatherer | `backend/app/services/engine_inputs.py` | Fetch and validate portfolio state |
| Calculator | `backend/app/services/engine_calculator.py` | Pure math pipeline |
| Engine API | `backend/app/api/v1/endpoints/engine.py` | REST endpoint |
| Frontend Hook | `frontend/src/hooks/use-engine.ts` | TanStack Query hook |
| Trade Plan UI | `frontend/src/components/engine/trade-plan.tsx` | Component with drift visualization |
| Assistant Page | `frontend/src/app/portfolios/[id]/assistant/page.tsx` | Page wrapper |

---

### Phase 5: Automation Foundation

**Purpose:** Establish the infrastructure for unattended operations with execution tracking and data retention.

**Deliverables:**

| Component | File | Description |
|-----------|------|-------------|
| Scheduler Service | `backend/app/services/scheduler.py` | APScheduler with Europe/London timezone |
| Scheduler Integration | `backend/app/main.py` | FastAPI lifespan context manager |
| Execution Log Model | `backend/app/domain/models.py` | Job execution audit trail |
| Retention Job | `backend/app/services/jobs/retention.py` | Weekly cleanup of old execution logs |
| Notification Config Model | `backend/app/domain/models.py` | Per-portfolio notification settings |
| Retention Tests | `backend/tests/test_retention.py` | 7 comprehensive test cases |

**Scheduler Configuration:**
- **Timezone:** Europe/London (using `zoneinfo`)
- **Retention Schedule:** Every Sunday at 02:00 London time
- **Retention Period:** 30 days for execution logs
- **Single-Worker Guard:** Prevents duplicate APScheduler executions

**Execution Logger Pattern:**
```python
async with execution_logger("cleanup_old_logs") as meta:
    result = await cleanup_function()
    meta["rows_deleted"] = result
# Automatically logs RUNNING -> SUCCESS/FAILED with full traceback
```

---

### Phase 5: Recommendation Execution Capture

**Purpose:** Bridge the gap between recommendations and the ledger with full audit trail.

**Deliverables:**

| Component | File | Description |
|-----------|------|-------------|
| Recommendation Batch Model | `backend/app/domain/models.py` | Status tracking (PENDING/EXECUTED/IGNORED) |
| Recommendation Line Model | `backend/app/domain/models.py` | Individual trade lines with execution tracking |
| Audit Event Model | `backend/app/domain/models.py` | Durable append-only audit trail |
| Execution Service | `backend/app/services/execution_service.py` | Translation logic from recommendations to ledger |
| Execution API | `backend/app/api/v1/endpoints/recommendations.py` | Execute and ignore endpoints |
| Execute Modal | `frontend/src/components/recommendations/execute-modal.tsx` | Form for executed prices/fees |
| Ignore Modal | `frontend/src/components/recommendations/ignore-modal.tsx` | Dismissal with optional reason |
| Recommendation Detail Page | `frontend/src/app/portfolios/[id]/recommendations/[batch_id]/page.tsx` | Full execution workflow |
| Execution Tests | `backend/tests/test_execution_service.py` | 11 test cases |

**Math Rules:**
- **BUY:** `quantity_delta > 0`, `net_cash_delta_gbp < 0` (cash outflow)
- **SELL:** `quantity_delta < 0`, `net_cash_delta_gbp > 0` (cash inflow)
- **Fees:** Deducted from cash impact for both BUY and SELL

**Idempotency Guard:**
```python
if batch.status != "PENDING":
    raise DoubleExecutionError("Recommendation batch already executed")
```

**API Endpoints:**
- `POST /api/v1/portfolios/{id}/recommendations/{batch_id}/execute` - Execute batch
- `POST /api/v1/portfolios/{id}/recommendations/{batch_id}/ignore` - Ignore batch

---

### Phase 6: Dashboard Reads

**Purpose:** Provide a command center view of portfolio health with valuations, drift, and activity.

**Deliverables:**

| Component | File | Description |
|-----------|------|-------------|
| Dashboard API | `backend/app/api/v1/endpoints/dashboard.py` | Aggregated summary endpoint |
| Dashboard Hook | `frontend/src/hooks/use-dashboard.ts` | TanStack Query with 30s refresh |
| Value Summary Card | `frontend/src/components/dashboard/value-summary-card.tsx` | Portfolio valuation overview |
| Sleeve Allocations Table | `frontend/src/components/dashboard/sleeve-allocations-table.tsx` | Target vs current weights |
| Activity Feed | `frontend/src/components/dashboard/activity-feed.tsx` | Recent actions list |
| Portfolio Detail Page | `frontend/src/app/portfolios/[id]/page.tsx` | Redesigned dashboard layout |

**Dashboard Features:**
- **Total Portfolio Value:** Cash + Holdings (real-time)
- **Drift Warning:** Visual indicator when any sleeve exceeds 5% drift
- **Freeze Status:** Prominent banner when portfolio is frozen
- **Sleeve Allocations:** Table with target vs current weights and drift
- **Activity Feed:** Last 5 actions (executions, ignores, imports, syncs)
- **Auto-refresh:** Dashboard updates every 30 seconds

**Data Sources:**
- Cash Snapshots → Current cash balance
- Holding Snapshots + Price Points → Holdings value
- Policy Allocations → Target weights
- Audit Events → Activity feed

---

### Phase 6: Housekeeping

**Purpose:** Ensure data safety and system maintainability with backup/restore procedures.

**Deliverables:**

| Component | File | Description |
|-----------|------|-------------|
| Backup Script | `scripts/backup_db.sh` | pg_dump wrapper with compression |
| Restore Script | `scripts/restore_db.sh` | Database restoration with verification |
| Operations Runbook | `docs/RUNBOOK.md` | Complete operational procedures |
| Dockerfile Update | `backend/Dockerfile` | postgresql-client tools added |

**Backup Features:**
- **Timestamped:** `trading_assistant_YYYYMMDD_HHMMSS.sql.gz`
- **Compressed:** `--compress` flag for gzip compression
- **Automatic Cleanup:** Keeps last 10 backups
- **Location:** `./backups/` directory

**Restore Features:**
- **Interactive Confirmation:** Requires user confirmation (bypass with `--force`)
- **Service Management:** Stops API/worker during restore
- **Verification:** Checks table count after restore
- **Supports:** Both `.sql` and `.sql.gz` files

**RUNBOOK.md Sections:**
1. Starting and Stopping the Application
2. Database Backup and Restore
3. Monitoring and Logs (including scheduler logs)
4. Troubleshooting (common issues and solutions)
5. Health Checks

**Testing:**
- Backup created successfully: 44KB compressed
- All scripts tested via SSH bridge
- Help documentation verified for both scripts

**Pipeline Architecture:**

```
┌──────────────┐    ┌──────────────┐    ┌──────────────┐
│    GATHER    │───▶│   VALIDATE   │───▶│    VALUE     │
└──────────────┘    └──────────────┘    └──────────────┘
      │                   │                   │
      ▼                   ▼                   ▼
Fetch Cash          Check 3-day        Calculate Total
Fetch Holdings      Staleness          Portfolio Value
Fetch Prices        Check Freeze
Fetch Allocations   Check Missing

┌──────────────┐    ┌──────────────┐    ┌──────────────┐
│  DRIFT MATH  │───▶│   HARVEST    │───▶│    DEPLOY    │
└──────────────┘    └──────────────┘    └──────────────┘
      │                   │                   │
      ▼                   ▼                   ▼
Current vs          Generate Sells     Generate Buys
Target Weights      (Max 2 orders)     (Max 3 orders)
Identify >5%        Add to Cash Pool   Prioritize Under
Drift                                  weight

┌──────────────┐    ┌──────────────┐
│    FILTER    │───▶│    OUTPUT    │
└──────────────┘    └──────────────┘
      │                   │
      ▼                   ▼
Drop Trades <     TradePlan with
£500              Positions, Trades,
                  Cash Flow, Warnings
```

**Pipeline Stages:**

1. **Gather (lines 44-86 in engine_inputs.py):**
   - Fetches CashSnapshot, HoldingSnapshots, PricePoints, PolicyAllocations
   - Returns EngineInputResult with snapshot_data or block reason

2. **Validate (lines 52-68, 107-115 in engine_inputs.py):**
   - 3-day staleness check: `price.as_of < now - 3 days`
   - Freeze state check: Active freeze blocks all calculations
   - Missing price check: All holdings must have close prices

3. **Value (lines 27-32 in engine_calculator.py):**
   ```python
   total_value = cash_balance + sum(position.current_value_gbp)
   ```

4. **Drift Math (lines 46-53, 196-203 in engine_calculator.py):**
   ```python
   current_weight_pct = (position_value / total_value) * 100
   drift_pct = current_weight_pct - target_weight_pct
   is_drifted = abs(drift_pct) > 5.0
   ```

5. **Harvest - Sells (lines 77-105 in engine_calculator.py):**
   - Sort overweight positions by drift (highest first)
   - Max 2 sell orders
   - Calculate exact quantity: `excess_value / current_price`
   - Add proceeds to Projected Cash Pool

6. **Deploy - Buys (lines 112-148 in engine_calculator.py):**
   - Sort underweight positions by drift (lowest first)
   - Max 3 buy orders
   - Calculate exact quantity: `deficit_value / current_price`
   - Limited by available Projected Cash Pool

7. **Filter (lines 150-161 in engine_calculator.py):**
   - Drop any trade with `estimated_value_gbp < 500`
   - Warnings logged for filtered trades

**API Response Schema:**

```typescript
GET /api/v1/portfolios/{portfolio_id}/engine/plan

{
  "portfolio_id": "uuid",
  "as_of": "2026-03-11T12:00:00Z",
  
  // Current State
  "total_value_gbp": "125000.00",
  "cash_balance_gbp": "25000.00",
  "positions": [
    {
      "listing_id": "uuid",
      "ticker": "VWRP",
      "current_quantity": "100.0000000000",
      "current_price_gbp": "105.50",
      "current_value_gbp": "10550.00",
      "target_weight_pct": "35.00",
      "current_weight_pct": "8.44",
      "drift_pct": "-26.56",
      "is_drifted": true
    }
  ],
  
  // Proposed Trades
  "trades": [
    {
      "action": "BUY",
      "ticker": "VWRP",
      "listing_id": "uuid",
      "quantity": "315.1658767701",
      "estimated_value_gbp": "33250.00",
      "reason": "DRIFT_BELOW_THRESHOLD"
    }
  ],
  
  // Cash Flow
  "projected_post_trade_cash": "18750.00",
  "cash_pool_used": "6250.00",
  "cash_pool_remaining": "18750.00",
  
  // Metadata
  "warnings": [
    "Max sell orders reached (2)",
    "2 trades filtered below 500 GBP"
  ],
  "is_blocked": false,
  "block_reason": null,
  "block_message": null
}
```

**UI Features:**

- **Allocations Table:** Current vs Target with drift highlighting (>5% = amber background)
- **Proposed Trades:** Separate cards for Buys (emerald) and Sells (rose)
- **Cash Flow Summary:** Post-trade projections
- **Warnings Panel:** Lists constraints and filters applied
- **Blocked State:** Red alert when trading blocked (stale prices, frozen, etc.)

---

## Core Guardrails & Data Quality

### 4.1 100% Decimal Math

**Requirement:** All monetary calculations use `decimal.Decimal`, never `float`.

**Rationale:** Floating-point arithmetic introduces rounding errors that compound in financial calculations. Decimal provides exact precision.

**Implementation:**
- Database: `Numeric(precision=18, scale=8)` columns
- Python: `Decimal` type throughout service layer
- Frontend: String representation of Decimals in JSON

**Enforcement:**
- Type hints require Decimal
- Unit tests validate exact decimal precision
- No float-to-decimal conversions in calculation paths

### 4.2 Strict CSV Parser

**Features:**
1. **BOM Stripping:** Removes UTF-8 byte-order mark from Excel exports
2. **Strict Ticker Mapping:** Requires exact ticker match in database
3. **Schema Validation:** Column headers and types validated
4. **Idempotency:** SHA256 hash prevents duplicate imports

**Implementation:** `backend/app/services/csv_parser.py`

### 4.3 3-Day Market Data Staleness Guardrail

**Purpose:** Prevent trading decisions on outdated prices.

**Implementation:** `backend/app/services/engine_inputs.py` (lines 91-131)

**Logic:**
```python
stale_cutoff = now - timedelta(days=3)
if price.as_of < stale_cutoff:
    return EngineInputResult(
        is_blocked=True,
        block_reason="STALE_PRICE",
        block_message=f"Stale market data for {ticker}; latest trusted price is older than 3 days"
    )
```

**User Impact:** Trade plan generation blocked until fresh prices available.

### 4.4 Recommendation-Only Engine

**Principle:** Engine generates Trade Plan but NEVER executes trades.

**User Control:**
- All trades executed manually through user's broker
- Engine provides recommendations only
- User reviews and approves every trade

**Capital Protection:**
- No API keys stored in system
- No automated trading capability
- No market order submission
- Software bugs cannot drain capital

### 4.5 Event Sourcing & Immutability

**Principles:**
- **Append-Only:** Ledger entries never deleted or modified
- **Reversals:** Create compensating entries instead of updates
- **Snapshots:** Derived from ledger (rebuildable)
- **Audit Trail:** Complete history preserved forever

**Benefits:**
- Complete audit trail for compliance
- Historical state reconstruction
- Bug investigation via point-in-time queries
- Regulatory reporting support

---

## Database Schema Summary

### Core Tables

| Table | Purpose | Key Columns |
|-------|---------|-------------|
| `users` | Authentication | user_id, email, is_enabled, is_bootstrap_admin |
| `portfolios` | Portfolio definitions | portfolio_id, owner_user_id, name, tax_profile (SIPP/ISA/GIA), broker |
| `instruments` | ISIN master | instrument_id, isin, name, instrument_type |
| `listings` | Exchange tickers | listing_id, instrument_id, ticker, exchange, trading_currency, price_scale |
| `sleeves` | Strategy taxonomy | sleeve_code, name |
| `portfolio_constituents` | Portfolio holdings | portfolio_id, listing_id, sleeve_code, is_monitored |
| `portfolio_policy_allocations` | Target weights | portfolio_id, listing_id, ticker, sleeve_code, target_weight_pct, policy_hash |

### Market Data

| Table | Purpose | Key Columns |
|-----------|---------|-------------|
| `price_points` | Time series | price_point_id, listing_id, as_of, price, is_close, **source_id** (e.g., 'yfinance', 'mock') |
| `fx_rates` | Currency rates | fx_rate_id, base_ccy, quote_ccy, as_of, rate, **source_id** (e.g., 'yfinance', 'mock') |

### Book of Record

| Table | Purpose | Key Columns |
|-------|---------|-------------|
| `ledger_batches` | Transaction groups | batch_id, portfolio_id, source (UI/CSV_IMPORT/REVERSAL), note |
| `ledger_entries` | Individual transactions | entry_id, batch_id, entry_kind, effective_at, quantity_delta, net_cash_delta_gbp |
| `cash_snapshots` | Cash state | portfolio_id, balance_gbp, updated_at, version_no |
| `holding_snapshots` | Position state | portfolio_id, listing_id, quantity, book_cost_gbp, avg_cost_gbp, version_no |

### Operational

| Table | Purpose | Key Columns |
|-------|---------|-------------|
| `alerts` | Data quality | alert_id, portfolio_id, severity, rule_code, title, message |
| `freeze_states` | Circuit breaker | freeze_id, portfolio_id, is_frozen, reason_alert_id, cleared_at |
| `notifications` | User messages | notification_id, owner_user_id, severity, title, body, read_at |
| `task_runs` | Background jobs | task_id, task_type, status, started_at, completed_at |

### Phase 5: Automation

| Table | Purpose | Key Columns |
|-------|---------|-------------|
| `execution_logs` | Job audit trail | execution_log_id, job_name, status, started_at, completed_at, error_message |
| `notification_configs` | External alerts | notification_config_id, portfolio_id, apprise_url, is_active |

### Phase 5: Recommendation Execution

| Table | Purpose | Key Columns |
|-------|---------|-------------|
| `recommendation_batches` | Trade recommendations | recommendation_batch_id, portfolio_id, status, generated_at, executed_at |
| `recommendation_lines` | Individual trades | recommendation_line_id, action, proposed_quantity, executed_quantity, status |
| `audit_events` | Durable audit trail | audit_event_id, event_type, entity_type, entity_id, occurred_at, summary |

---

## Testing Strategy

### Backend Tests

| Test File | Count | Coverage |
|-----------|-------|----------|
| `tests/test_engine_inputs.py` | 6 | World State Gatherer, staleness checks, freeze states |
| `tests/test_engine_calculator.py` | 13 | Deterministic math, drift thresholds, order limits |
| `tests/test_yfinance_adapter.py` | 9 | LSE ticker rule, live price fetch, FX rates |
| `tests/test_retention.py` | 7 | Execution log cleanup, scheduled jobs |
| `tests/test_execution_service.py` | 11 | Recommendation execution, ignore, audit trail |

**Key Test Scenarios:**
- 3-day staleness blocking
- Fresh price success paths
- Portfolio freeze blocking
- Missing price handling
- No trades under 5% drift
- £500 friction filter
- Max 2 sells / 3 buys limits
- Cash pool exhaustion
- Exact quantity calculations
- LSE ticker suffix rule (bare tickers get `.L`)
- Live VWRP price fetch from Yahoo Finance
- Decimal precision in price quotes
- FX rate fetching (GBP/USD)
- Execution log creation and cleanup
- Double-execution prevention
- Ignore workflow and audit trail
- Ledger entry creation from recommendations

### Frontend

- TypeScript strict mode enabled
- Zero type errors: `npx tsc --noEmit` passes
- TanStack Query for server state management
- Real-time UI updates on data changes
- Dashboard auto-refresh (30-second intervals)

---

## Deployment Architecture

### Docker Compose Services

```yaml
services:
  db:
    image: postgres:16-alpine
    ports: ["5432:5432"]
    
  redis:
    image: redis:7-alpine
    ports: ["6379:6379"]
    
  api:
    build: ./backend
    ports: ["8000:8000"]
    command: uvicorn app.main:app --host 0.0.0.0 --port 8000
    
  worker:
    build: ./backend
    command: python -m app.worker
    
  ui:
    build: ./frontend
    ports: ["3000:3000"]
```

### Local Development

```bash
# Start all services
docker compose up -d

# Backend development shell
docker compose exec api bash

# Frontend development (hot reload)
cd frontend && npm run dev

# Run backend tests
docker compose run --rm -e PYTHONPATH=/app api pytest

# TypeScript checks
docker compose run --rm ui npx tsc --noEmit
```

### Production Considerations

1. **Secrets Management:** All sensitive config via environment variables (.env)
2. **Database Migrations:** Managed via Alembic (`alembic upgrade head`)
3. **No External Dependencies:** Core functionality works air-gapped
4. **Backup Strategy:** PostgreSQL volume backups for data protection
5. **Monitoring:** Health checks at `/health` endpoint

---

## Phase Completion Status

| Phase | Status | Key Deliverables |
|-------|--------|------------------|
| Phase 1: Registry | ✅ Complete | Instruments, Listings, Sleeves, Portfolios |
| Phase 2: Market Data | ✅ Complete | Price ingestion, DQ Gate, Alerts, Freeze mechanism |
| Phase 3: Ledger | ✅ Complete | Event-sourced accounting, Cash/Holding snapshots |
| Phase 4: Engine | ✅ Complete | Deterministic trade recommendations, drift math |
| Phase 5: Automation | ✅ Complete | APScheduler, execution logs, retention, execution capture |
| Phase 6: Dashboard | ✅ Complete | Portfolio command center, backup/restore procedures |

---

## Future Roadmap (Beyond Phase 6)

### Phase 7: Advanced Order Management
- Convert Trade Plan to broker-specific order formats
- Tax-loss harvesting optimization
- Lot-level cost basis selection (FIFO, LIFO, specific lot)
- Manual order submission tracking

### Phase 8: Performance Analytics
- Performance attribution (Brinson model)
- Risk metrics (VaR, maximum drawdown)
- Monte Carlo retirement projections
- Benchmark comparison (index tracking error)
- Historical performance visualization

---

## File Inventory

### Backend Core Files

| File | Lines | Purpose |
|------|-------|---------|
| `app/main.py` | 47 | FastAPI app initialization, router registration |
| `app/core/config.py` | 25 | Settings and environment variables |
| `app/core/database.py` | 20 | SQLAlchemy engine and session |
| `app/domain/models.py` | 331 | SQLAlchemy ORM models |
| `app/domain/engine.py` | 93 | Pure domain models for calculation engine |
| `app/api/deps.py` | 101 | Dependency injection (auth, database) |
| `app/api/v1/endpoints/*.py` | ~150 each | API route handlers |
| `app/services/*.py` | 100-250 each | Business logic services |
| `app/services/market_data_adapter.py` | 123 | Provider protocol and exceptions |
| `app/services/market_data_service.py` | 95 | On-demand price sync service |
| `app/services/providers/yfinance_adapter.py` | 186 | Yahoo Finance provider implementation |
| `app/services/providers/mock_provider.py` | 213 | Mock provider for testing |
| `app/services/scheduler.py` | 183 | APScheduler with London timezone |
| `app/services/jobs/retention.py` | 65 | Weekly retention cleanup job |
| `app/services/execution_service.py` | 320 | Recommendation to ledger translation |
| `app/api/v1/endpoints/recommendations.py` | 220 | Execute/ignore endpoints |
| `app/api/v1/endpoints/dashboard.py` | 245 | Portfolio dashboard summary |
| `scripts/sync_market_data.py` | 180 | Standalone sync script |
| `scripts/backup_db.sh` | 195 | Database backup script |
| `scripts/restore_db.sh` | 200 | Database restore script |

### Frontend Core Files

| File | Lines | Purpose |
|------|-------|---------|
| `src/app/layout.tsx` | 21 | Root layout with QueryClient |
| `src/app/page.tsx` | ~50 | Dashboard |
| `src/app/portfolios/[id]/page.tsx` | 484 | Portfolio detail |
| `src/app/portfolios/[id]/assistant/page.tsx` | 23 | Trade Assistant |
| `src/components/engine/trade-plan.tsx` | 326 | Trade plan display |
| `src/hooks/use-engine.ts` | 17 | TanStack Query hook |
| `src/hooks/use-market-data.ts` | 65 | Market data queries and sync mutation |
| `src/hooks/use-dashboard.ts` | 20 | Dashboard summary hook |
| `src/hooks/use-recommendations.ts` | 95 | Recommendation execution hooks |
| `src/components/dashboard/value-summary-card.tsx` | 85 | Portfolio valuation display |
| `src/components/dashboard/sleeve-allocations-table.tsx` | 95 | Allocation vs target table |
| `src/components/dashboard/activity-feed.tsx` | 75 | Recent activity list |
| `src/components/recommendations/execute-modal.tsx` | 165 | Trade execution form |
| `src/components/recommendations/ignore-modal.tsx` | 55 | Recommendation dismissal form |
| `src/app/portfolios/[id]/recommendations/[batch_id]/page.tsx` | 311 | Recommendation detail page |
| `src/types/index.ts` | 560 | TypeScript interfaces |
| `src/lib/api-client.ts` | ~30 | Axios configuration |

---

## Conclusion

The Trading Assistant represents a production-ready, enterprise-grade portfolio management system built on solid engineering principles:

- **Deterministic calculations** ensure reproducibility and auditability
- **Event sourcing** provides complete audit trail
- **Decimal math** eliminates floating-point errors
- **Privacy-first architecture** keeps user data local
- **Recommendation-only design** protects user capital
- **Automated operations** with scheduler, retention, and execution tracking
- **Command center dashboard** for at-a-glance portfolio health
- **Robust backup/restore** procedures for data safety

The system successfully implements the Boglehead passive investment philosophy through systematic rebalancing, policy-based allocations, emotional-decision-free trade recommendations, and comprehensive operational controls.

---

*Report generated: March 11, 2026*
*Implementation: Phases 1-6 Complete (Full V1 Implementation)*
*Total Lines of Code: ~10,000+ (backend) + ~6,500+ (frontend)*
