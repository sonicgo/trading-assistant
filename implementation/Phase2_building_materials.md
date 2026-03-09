# Phase 2 Building Materials — As-Built Documentation

**Trading Assistant V1 — Market Data + Data Quality Gate**

_Last Updated: March 9, 2026_

---

## Executive Summary

Phase 2 of the Trading Assistant implements the **Market Data Ingestion & Data Quality Gate** system. This phase adds 7 new database tables, 8 DQ validation rules, 11 API endpoints, and a complete frontend UI for monitoring market data and alerts.

The core innovation of Phase 2 is the **Data Quality (DQ) Gate** — a circuit-breaker pattern that prevents bad market data from flowing downstream to the calculation engine. When critical DQ violations are detected (e.g., stale prices, 100× scale errors, currency mismatches), the system can freeze the portfolio and alert operators.

---

## 1. The Phase 2 Schema

### 1.1 Overview

Phase 2 introduces **7 new tables** that extend the Phase 1 schema. All tables use UUID primary keys and TIMESTAMPTZ (UTC) timestamps for consistency.

### 1.2 Table Reference

#### **price_points** — Append-Only Time-Series Prices

**Purpose**: Store historical price data for each instrument listing with idempotency guarantees.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `price_point_id` | UUID | PK | Unique identifier |
| `listing_id` | UUID | FK → `listing`, NOT NULL | Reference to instrument listing |
| `as_of` | TIMESTAMPTZ | NOT NULL | Price timestamp |
| `price` | NUMERIC(28,10) | NOT NULL | Price value (stored as Decimal) |
| `currency` | VARCHAR(3) | NULLABLE | Provider-reported currency |
| `is_close` | BOOLEAN | NOT NULL, DEFAULT false | True if this is a closing price |
| `source_id` | VARCHAR | NOT NULL | Data provider/source identifier |
| `raw` | JSONB | NULLABLE | Raw provider payload |
| `created_at` | TIMESTAMPTZ | DEFAULT now() | Record creation time |

**Unique Constraint**: `uq_price_point` ON `(listing_id, as_of, source_id, is_close)`
- **Purpose**: Idempotency key preventing duplicate ingestion
- **Pattern**: `INSERT ... ON CONFLICT DO NOTHING`

**Index**: `ix_price_points_listing_as_of` ON `(listing_id, as_of DESC)`

**Relationships**: → `listing` (many-to-one)

---

#### **fx_rates** — Append-Only FX Rates

**Purpose**: Store historical foreign exchange rates for currency conversion and validation.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `fx_rate_id` | UUID | PK | Unique identifier |
| `base_ccy` | VARCHAR(3) | NOT NULL | Base currency (e.g., "GBP") |
| `quote_ccy` | VARCHAR(3) | NOT NULL | Quote currency (e.g., "USD") |
| `as_of` | TIMESTAMPTZ | NOT NULL | Rate timestamp |
| `rate` | NUMERIC(28,10) | NOT NULL | Exchange rate |
| `source_id` | VARCHAR | NOT NULL | Data provider/source |
| `created_at` | TIMESTAMPTZ | DEFAULT now() | Record creation time |

**Unique Constraint**: `uq_fx_rate` ON `(base_ccy, quote_ccy, as_of, source_id)`
- **Purpose**: Idempotency key for FX rates

**Relationships**: None (standalone reference table)

---

#### **alerts** — Data Quality & Safety Events

**Purpose**: Durable record of DQ violations and system safety events.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `alert_id` | UUID | PK | Unique identifier |
| `portfolio_id` | UUID | FK → `portfolio`, NOT NULL | Associated portfolio |
| `listing_id` | UUID | FK → `listing`, NULLABLE | Associated instrument |
| `severity` | VARCHAR | NOT NULL | INFO / WARN / CRITICAL |
| `rule_code` | VARCHAR | NOT NULL | DQ rule code (e.g., DQ_GBX_SCALE) |
| `title` | TEXT | NOT NULL | Alert title |
| `message` | TEXT | NULLABLE | Human-readable message |
| `details` | JSONB | NULLABLE | Thresholds, observed values, etc. |
| `created_at` | TIMESTAMPTZ | DEFAULT now() | Alert creation time |
| `resolved_at` | TIMESTAMPTZ | NULLABLE | Resolution timestamp |

**Index**: `ix_alerts_portfolio_created` ON `(portfolio_id, created_at DESC)`

**Relationships**: 
- → `portfolio` (many-to-one)
- → `listing` (many-to-one, optional)

---

#### **freeze_states** — Circuit Breaker State

**Purpose**: Track freeze/circuit-breaker state for each portfolio.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `freeze_id` | UUID | PK | Unique identifier |
| `portfolio_id` | UUID | FK → `portfolio`, NOT NULL | Portfolio being frozen |
| `is_frozen` | BOOLEAN | NOT NULL, DEFAULT false | Freeze state |
| `reason_alert_id` | UUID | FK → `alerts`, NULLABLE | Alert that triggered freeze |
| `created_at` | TIMESTAMPTZ | DEFAULT now() | Freeze initiated time |
| `cleared_at` | TIMESTAMPTZ | NULLABLE | Freeze cleared time |
| `cleared_by_user_id` | UUID | FK → `user`, NULLABLE | User who cleared freeze |

**Index**: `ix_freeze_states_portfolio` ON `(portfolio_id)`

**Relationships**:
- → `portfolio` (many-to-one)
- → `alerts` (many-to-one, optional)
- → `user` (many-to-one, optional)

---

#### **task_runs** — Task Execution Audit

**Purpose**: Audit trail and reproducibility for background task executions.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `run_id` | UUID | PK | Unique identifier |
| `job_id` | UUID | NOT NULL | From queue message |
| `task_kind` | VARCHAR | NOT NULL | Task type (e.g., PRICE_REFRESH) |
| `portfolio_id` | UUID | FK → `portfolio`, NULLABLE | Associated portfolio |
| `status` | VARCHAR | NOT NULL | SUCCESS / FROZEN / FAILED |
| `started_at` | TIMESTAMPTZ | DEFAULT now() | Task start time |
| `ended_at` | TIMESTAMPTZ | NULLABLE | Task completion time |
| `summary` | JSONB | NULLABLE | Counts, warnings, rule hits |

**Index**: `ix_task_runs_portfolio_started` ON `(portfolio_id, started_at DESC)`

**Relationships**: → `portfolio` (many-to-one, optional)

---

#### **run_input_snapshots** — Task Input Reproducibility

**Purpose**: Store task inputs for reproducibility and audit trails.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `run_id` | UUID | FK → `task_runs`, PK | Links to parent task run |
| `input_json` | JSONB | NOT NULL | Listing IDs, provider, thresholds, etc. |
| `input_hash` | VARCHAR | NULLABLE | Stable hash for deduplication/debug |
| `created_at` | TIMESTAMPTZ | DEFAULT now() | Snapshot creation time |

**Relationships**: → `task_runs` (one-to-one via FK)

---

#### **notifications** — User Notification Feed

**Purpose**: Polling feed for critical events to notify users.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `notification_id` | UUID | PK | Unique identifier |
| `owner_user_id` | UUID | FK → `user`, NOT NULL | User who owns this notification |
| `severity` | VARCHAR | NOT NULL | INFO / WARN / CRITICAL |
| `title` | TEXT | NOT NULL | Notification title |
| `body` | TEXT | NULLABLE | Notification body |
| `created_at` | TIMESTAMPTZ | DEFAULT now() | Creation time |
| `read_at` | TIMESTAMPTZ | NULLABLE | Read timestamp |
| `meta` | JSONB | NULLABLE | References (portfolio_id, alert_id, run_id) |

**Index**: `ix_notifications_user_created` ON `(owner_user_id, created_at DESC)`

**Relationships**: → `user` (many-to-one)

---

### 1.3 Schema Relationships

```
user
├── portfolio (1:m)
│   ├── alerts (1:m)
│   ├── freeze_states (1:m) ──→ alerts (optional)
│   └── task_runs (1:m)
├── notifications (1:m)
└── freeze_states (cleared_by_user_id) (1:m)

listing
├── price_points (1:m)
├── alerts (1:m)
└── instrument (m:1)

task_runs
└── run_input_snapshots (1:1)
```

---

## 2. The Data Quality Engine

### 2.1 Overview

The DQ engine is a **pure evaluator** that returns violations without side effects. The caller (worker/ingest pipeline) is responsible for persisting violations as Alert rows. This separation allows for flexible DQ strategies (e.g., warn-only mode, different severity thresholds per portfolio).

**Implementation**: `/home/lei-dev/projects/trading-assistant/backend/app/services/data_quality.py`

### 2.2 Configuration Thresholds

All thresholds are configurable via environment variables (defined in `app/core/config.py`):

| Setting | Default | Description |
|---------|---------|-------------|
| `dq_stale_max_minutes_intraday` | 30 | Max age for intraday prices (minutes) |
| `dq_stale_max_days_close` | 3 | Max age for close prices (days) |
| `dq_jump_threshold_pct` | 10.0 | Price jump threshold (%) |
| `dq_require_close` | True | Require close prices |
| `dq_fx_stale_max_days` | 3 | Max age for FX rates (days) |

**Venue Close Times** (for DQ_MISSING_CLOSE):
- **LSE/XLON/LON**: 16:30 Europe/London
- **NYSE/XNYS**: 16:00 America/New_York
- **NASDAQ/XNAS**: 16:00 America/New_York
- **Unknown**: Conservative "market closed" = True

### 2.3 The 8 DQ Rules

#### **DQ_STALE_INTRADAY** (Severity: WARN)

**Purpose**: Detect when intraday price is too old.

**Logic**:
- Skip when no intraday price exists (normal outside market hours)
- Compare `latest_intraday.as_of` vs current `as_of` timestamp
- Threshold: **30 minutes**
- Returns WARN violation if age > threshold

**Code Location**: `data_quality.py` lines 107-145

---

#### **DQ_STALE_CLOSE** (Severity: WARN → CRITICAL)

**Purpose**: Detect when close price is outdated.

**Logic**:
- Skip if no close price (handled by DQ_MISSING_CLOSE)
- Compare `latest_close.as_of` vs current `as_of`
- Threshold: **3 days**
- **Severity Escalation**:
  - Age > 3 days but ≤ 6 days → WARN
  - Age > 6 days → CRITICAL

**Code Location**: `data_quality.py` lines 148-187

---

#### **DQ_MISSING_CLOSE** (Severity: CRITICAL)

**Purpose**: Detect missing close price after market close.

**Logic** (all conditions must be true):
1. `settings.dq_require_close = True` (default: True)
2. `latest_close is None` (no close price in DB)
3. Market is closed at `as_of` time (timezone-aware check)

**Market Close Detection**:
- LSE: 16:30 Europe/London
- NYSE/NASDAQ: 16:00 America/New_York
- Unknown venues → conservative "market closed" = True

**Code Location**: `data_quality.py` lines 190-224

---

#### **DQ_JUMP_CLOSE** (Severity: CRITICAL)

**Purpose**: Detect abnormal price movements vs previous close.

**Logic**:
- Requires BOTH `latest_close` and `prev_close` to exist
- Calculates: `pct_change = |current - previous| / previous × 100`
- Threshold: **10%**
- Returns CRITICAL if `pct_change > threshold_pct`

**Example**: If previous close was $100 and current is $115, that's a 15% jump → CRITICAL

**Code Location**: `data_quality.py` lines 227-273

---

#### **DQ_GBX_SCALE** (Severity: CRITICAL) — The 100× Hazard

**Purpose**: Detect 100× scale errors between GBX (pence) and GBP (pounds).

**Background**: UK stocks are often quoted in GBX (pence) rather than GBP (pounds). A price of 5000 GBX = £50.00 GBP. If a provider mixes these up, you get a 100× error.

**Logic** (detects both directions):

**Case 1 — Price ~100× too small**:
- Provider returned GBP, but listing expects GBX
- Ratio = `current_price / previous_close`
- If `0.005 < ratio < 0.02` → CRITICAL
- **Example**: Previous close 5000 GBX (£50), provider sends 50 GBP → ratio = 0.01 (expected: ~100)

**Case 2 — Price ~100× too large**:
- Provider returned GBX, but listing expects GBP
- If `50 < ratio < 150` → CRITICAL
- **Example**: Previous close 50 GBP, provider sends 5000 GBX → ratio = 100 (expected: ~0.01)

**Normalization Note**: GBX → GBP for FX lookup (handled as same currency family)

**Code Location**: `data_quality.py` lines 276-358

---

#### **DQ_CCY_MISMATCH** (Severity: CRITICAL)

**Purpose**: Detect currency mismatch between provider and listing.

**Logic**:
1. If provider didn't report currency → skip (cannot check)
2. Normalize both to uppercase
3. **Special case**: GBX and GBP are treated as same family (scale handled by DQ_GBX_SCALE)
4. If `provider_ccy != listing_ccy` → CRITICAL

**Code Location**: `data_quality.py` lines 361-401

---

#### **DQ_FX_MISSING** (Severity: WARN → CRITICAL)

**Purpose**: Detect missing FX rate needed for currency conversion.

**Logic**:
1. Normalize listing currency (GBX → GBP for FX lookup)
2. If listing currency == base currency → skip (no conversion needed)
3. Look for FX pair in available quotes (either `listing_ccy/base_ccy` or `base_ccy/listing_ccy`)
4. If no matching pair found:
   - `dq_require_close = True` → CRITICAL
   - Otherwise → WARN

**Code Location**: `data_quality.py` lines 404-451

---

#### **DQ_FX_STALE** (Severity: WARN)

**Purpose**: Detect stale FX rates.

**Logic**:
1. Skip if listing currency == base currency
2. Find matching FX pair (handled by DQ_FX_MISSING if absent)
3. Get most recent FX quote
4. Threshold: **3 days**
5. If age > threshold → WARN

**Code Location**: `data_quality.py` lines 454-510

### 2.4 Severity Summary Table

| Rule | INFO | WARN | CRITICAL |
|------|------|------|----------|
| DQ_STALE_INTRADAY | — | Age > 30 min | — |
| DQ_STALE_CLOSE | — | Age > 3 days, ≤ 6 days | Age > 6 days |
| DQ_MISSING_CLOSE | — | — | Always (when triggered) |
| DQ_JUMP_CLOSE | — | — | Always (when triggered) |
| DQ_GBX_SCALE | — | — | Always (both 100× cases) |
| DQ_CCY_MISMATCH | — | — | Always (when triggered) |
| DQ_FX_MISSING | — | dq_require_close=False | dq_require_close=True |
| DQ_FX_STALE | — | Age > 3 days | — |

---

## 3. The API Surface

### 3.1 Base Path

All API endpoints are prefixed with `/api/v1`.

### 3.2 Market Data Endpoints

#### **GET /portfolios/{portfolio_id}/market-data/prices**

**Description**: Retrieve latest price points for monitored constituents in a portfolio.

**Parameters**:
| Name | Type | In | Required | Default | Description |
|------|------|----|----------|---------|-------------|
| `portfolio_id` | UUID | path | Yes | — | Portfolio UUID |
| `limit` | int | query | No | 50 | Max results (≤500) |

**Response Schema**: `list[PricePointResponse]`

```json
{
  "price_point_id": "550e8400-e29b-41d4-a716-446655440000",
  "listing_id": "660e8400-e29b-41d4-a716-446655440001",
  "as_of": "2026-03-09T10:30:00Z",
  "price": "150.2500000000",
  "currency": "USD",
  "is_close": false,
  "source_id": "mock",
  "created_at": "2026-03-09T10:30:05Z"
}
```

**Access Control**: Requires portfolio access (via `deps.require_portfolio_access`)

---

#### **GET /portfolios/{portfolio_id}/market-data/fx**

**Description**: Retrieve FX rates for currencies used by portfolio constituents.

**Parameters**:
| Name | Type | In | Required | Default | Description |
|------|------|----|----------|---------|-------------|
| `portfolio_id` | UUID | path | Yes | — | Portfolio UUID |
| `limit` | int | query | No | 50 | Max results per currency pair (≤500) |

**Response Schema**: `list[FxRateResponse]`

```json
{
  "fx_rate_id": "770e8400-e29b-41d4-a716-446655440003",
  "base_ccy": "GBP",
  "quote_ccy": "USD",
  "as_of": "2026-03-09T10:30:00Z",
  "rate": "1.2500000000",
  "source_id": "mock",
  "created_at": "2026-03-09T10:30:05Z"
}
```

**Access Control**: Requires portfolio access

---

#### **POST /portfolios/{portfolio_id}/market-data/refresh**

**Description**: Trigger an asynchronous market data refresh for a portfolio.

**Parameters**:
| Name | Type | In | Required | Description |
|------|------|----|----------|-------------|
| `portfolio_id` | UUID | path | Yes | Portfolio UUID |

**Request Body**: None

**Response Schema**: `RefreshResponse`

```json
{
  "job_id": "880e8400-e29b-41d4-a716-446655440004",
  "status": "enqueued"
}
```

**Behavior**:
- Enqueues a `PRICE_REFRESH` job to the Redis queue
- Job will be processed by the worker asynchronously
- Returns immediately with `job_id` for tracking

**Access Control**: Requires portfolio access + authenticated user

---

### 3.3 Alerts Endpoints

#### **GET /portfolios/{portfolio_id}/alerts**

**Description**: Retrieve alerts for a portfolio.

**Parameters**:
| Name | Type | In | Required | Default | Description |
|------|------|----|----------|---------|-------------|
| `portfolio_id` | UUID | path | Yes | — | Portfolio UUID |
| `active_only` | boolean | query | No | true | Filter to unresolved alerts only |

**Response Schema**: `list[AlertResponse]`

```json
{
  "alert_id": "990e8400-e29b-41d4-a716-446655440005",
  "portfolio_id": "660e8400-e29b-41d4-a716-446655440001",
  "listing_id": "aa0e8400-e29b-41d4-a716-446655440006",
  "severity": "CRITICAL",
  "rule_code": "DQ_GBX_SCALE",
  "title": "GBX/GBP scale mismatch detected",
  "message": "Price appears to be 100× off expected scale",
  "details": {
    "observed_ratio": 0.01,
    "expected_range": "0.8-1.2"
  },
  "created_at": "2026-03-09T10:30:00Z",
  "resolved_at": null
}
```

**Access Control**: Requires portfolio access

---

### 3.4 Freeze Endpoints

#### **GET /portfolios/{portfolio_id}/freeze**

**Description**: Get freeze status for a portfolio.

**Parameters**:
| Name | Type | In | Required | Description |
|------|------|----|----------|-------------|
| `portfolio_id` | UUID | path | Yes | Portfolio UUID |

**Response Schema**: `FreezeStatusResponse`

```json
{
  "is_frozen": true,
  "freeze": {
    "freeze_id": "bb0e8400-e29b-41d4-a716-446655440007",
    "portfolio_id": "660e8400-e29b-41d4-a716-446655440001",
    "is_frozen": true,
    "reason_alert_id": "990e8400-e29b-41d4-a716-446655440005",
    "created_at": "2026-03-09T10:30:00Z",
    "cleared_at": null,
    "cleared_by_user_id": null
  }
}
```

**Access Control**: Requires portfolio access

---

#### **POST /portfolios/{portfolio_id}/freeze**

**Description**: Manually freeze a portfolio.

**Parameters**:
| Name | Type | In | Required | Description |
|------|------|----|----------|-------------|
| `portfolio_id` | UUID | path | Yes | Portfolio UUID |

**Request Body**: None

**Response Schema**: `FreezeStateResponse`

```json
{
  "freeze_id": "bb0e8400-e29b-41d4-a716-446655440007",
  "portfolio_id": "660e8400-e29b-41d4-a716-446655440001",
  "is_frozen": true,
  "reason_alert_id": null,
  "created_at": "2026-03-09T10:30:00Z",
  "cleared_at": null,
  "cleared_by_user_id": null
}
```

**Access Control**: Requires portfolio access

---

#### **POST /portfolios/{portfolio_id}/unfreeze**

**Description**: Manually unfreeze a portfolio.

**Parameters**:
| Name | Type | In | Required | Description |
|------|------|----|----------|-------------|
| `portfolio_id` | UUID | path | Yes | Portfolio UUID |

**Request Body**: None

**Response Schema**: `FreezeStateResponse` (or 404 if not frozen)

```json
{
  "freeze_id": "bb0e8400-e29b-41d4-a716-446655440007",
  "portfolio_id": "660e8400-e29b-41d4-a716-446655440001",
  "is_frozen": false,
  "reason_alert_id": null,
  "created_at": "2026-03-09T10:30:00Z",
  "cleared_at": "2026-03-09T10:35:00Z",
  "cleared_by_user_id": "770e8400-e29b-41d4-a716-446655440002"
}
```

**Access Control**: Requires portfolio access + authenticated user

---

### 3.5 Notifications Endpoint

#### **GET /notifications**

**Description**: List notifications for the current user (polling feed).

**Parameters**:
| Name | Type | In | Required | Default | Description |
|------|------|----|----------|---------|-------------|
| `since` | datetime | query | No | null | Filter to notifications after this timestamp |

**Response Schema**: `list[NotificationResponse]`

```json
{
  "notification_id": "cc0e8400-e29b-41d4-a716-446655440008",
  "owner_user_id": "770e8400-e29b-41d4-a716-446655440002",
  "severity": "CRITICAL",
  "title": "Portfolio Frozen",
  "body": "Portfolio 'Test Portfolio' has been frozen due to DQ_GBX_SCALE violation",
  "created_at": "2026-03-09T10:30:00Z",
  "read_at": null,
  "meta": {
    "portfolio_id": "660e8400-e29b-41d4-a716-446655440001",
    "alert_id": "990e8400-e29b-41d4-a716-446655440005"
  }
}
```

**Access Control**: Current user only (filters by `owner_user_id`)

---

## 4. The Frontend Architecture

### 4.1 Next.js Routes

| Route | File | Description |
|-------|------|-------------|
| `/market-data` | `src/app/market-data/page.tsx` | Displays latest prices table, FX rates table, portfolio selector, refresh button |
| `/alerts` | `src/app/alerts/page.tsx` | Displays alert cards with severity badges, active/all toggle |
| `/portfolios/[id]` | `src/app/portfolios/[id]/page.tsx` | Portfolio detail with FROZEN banner (lines 160-189) |
| `/` (Dashboard) | `src/app/page.tsx` | Updated with Market Data and Alerts navigation buttons |

### 4.2 TanStack Query Hooks

All hooks are located in `/home/lei-dev/projects/trading-assistant/frontend/src/hooks/`:

#### **use-market-data.ts**

```typescript
// Query hooks
export function useMarketPrices(portfolioId: string | undefined, limit?: number)
export function useMarketFx(portfolioId: string | undefined, limit?: number)

// Mutation hook
export function useRefreshMarketData(portfolioId: string | undefined)
```

**Query Keys**:
- Prices: `[MARKET_DATA_KEY, 'prices', portfolioId, { limit }]`
- FX: `[MARKET_DATA_KEY, 'fx', portfolioId, { limit }]`

**Endpoints**:
- `GET /portfolios/${portfolioId}/market-data/prices`
- `GET /portfolios/${portfolioId}/market-data/fx`
- `POST /portfolios/${portfolioId}/market-data/refresh`

---

#### **use-alerts.ts**

```typescript
export function useAlerts(portfolioId: string | undefined, activeOnly?: boolean)
```

**Query Key**: `[ALERTS_KEY, portfolioId, { active_only: activeOnly }]`

**Endpoint**: `GET /portfolios/${portfolioId}/alerts`

---

#### **use-freeze.ts**

```typescript
// Query hook
export function useFreeze(portfolioId: string | undefined)

// Mutation hooks
export function useFreezePortfolio(portfolioId: string | undefined)
export function useUnfreezePortfolio(portfolioId: string | undefined)
```

**Query Key**: `[FREEZE_KEY, portfolioId]`

**Endpoints**:
- `GET /portfolios/${portfolioId}/freeze`
- `POST /portfolios/${portfolioId}/freeze`
- `POST /portfolios/${portfolioId}/unfreeze`

---

#### **use-notifications.ts**

```typescript
export function useNotifications(since?: string)
```

**Query Key**: `[NOTIFICATIONS_KEY, { since }]`

**Endpoint**: `GET /notifications`

**Polling**: `refetchInterval: 30000` (30 seconds)

### 4.3 Shared Components

#### **PortfolioSelector** (`src/components/portfolio-selector.tsx`)

**Props**:
```typescript
interface PortfolioSelectorProps {
  selectedId?: string;
  onSelect: (id: string) => void;
}
```

**Features**:
- Dropdown select with all user portfolios
- Displays: `{name} ({tax_profile}) — {base_currency}`
- Loading state: "Loading..."
- Empty state: "No portfolios available"

---

#### **NotificationsDropdown** (`src/components/notifications-dropdown.tsx`)

**Features**:
- Bell icon (🔔) with unread count badge
- Dropdown showing notification list
- Severity indicator dots (CRITICAL=red, WARN=amber, INFO=blue)
- Title, body preview (truncated), relative timestamp
- Click outside to close
- 30-second polling via `useNotifications` hook

**Unread Count**: `notifications.filter(n => !n.read_at).length`

### 4.4 TypeScript Types

**Location**: `/home/lei-dev/projects/trading-assistant/frontend/src/types/index.ts`

**Market Data Types**:
```typescript
export interface PricePoint {
  price_point_id: string;
  listing_id: string;
  as_of: string;
  price: string;           // DecimalStr
  currency: string | null;
  is_close: boolean;
  source_id: string;
  created_at: string;
}

export interface FxRate {
  fx_rate_id: string;
  base_ccy: string;
  quote_ccy: string;
  as_of: string;
  rate: string;            // DecimalStr
  source_id: string;
  created_at: string;
}
```

**Alert Types**:
```typescript
export type AlertSeverity = 'INFO' | 'WARN' | 'CRITICAL';

export interface Alert {
  alert_id: string;
  portfolio_id: string;
  listing_id: string | null;
  severity: AlertSeverity;
  rule_code: string;
  title: string;
  message: string | null;
  details: Record<string, unknown> | null;
  created_at: string;
  resolved_at: string | null;
}
```

**Freeze Types**:
```typescript
export interface FreezeState {
  freeze_id: string;
  portfolio_id: string;
  is_frozen: boolean;
  reason_alert_id: string | null;
  created_at: string;
  cleared_at: string | null;
  cleared_by_user_id: string | null;
}

export interface FreezeStatus {
  is_frozen: boolean;
  freeze: FreezeState | null;
}
```

**Notification Type**:
```typescript
export interface Notification {
  notification_id: string;
  owner_user_id: string;
  severity: string;
  title: string;
  body: string | null;
  created_at: string;
  read_at: string | null;
  meta: Record<string, unknown> | null;
}
```

---

## 5. Worker Topology

### 5.1 Overview

The Phase 2 worker system uses **Redis as a message queue** with a **single-worker polling pattern**. Jobs are enqueued by the API (or external scheduler) and processed by a dedicated worker process.

### 5.2 Job Flow Pipeline

```
┌─────────────────────────────────────────────────────────────────────┐
│                         EXTERNAL SCHEDULER                         │
│  phase2_scheduler.py: polls every N minutes                        │
│  1. Login to API                                                   │
│  2. GET /api/v1/portfolios → list of portfolios                    │
│  3. POST /api/v1/portfolios/{id}/market-data/refresh (each)        │
└─────────────────────────────────────┬───────────────────────────────┘
                                      │ HTTP POST
                                      ↓
┌─────────────────────────────────────────────────────────────────────┐
│                         FASTAPI APP                                 │
│  market_data.py endpoint                                          │
│  - Validates portfolio access                                      │
│  - Calls enqueue_job(task_kind, portfolio_id, user_id)           │
└─────────────────────────────────────┬───────────────────────────────┘
                                      │ enqueue_job()
                                      ↓
┌─────────────────────────────────────────────────────────────────────┐
│                         REDIS QUEUE                                 │
│  redis_queue.py                                                   │
│  - LPUSH to "ta:jobs" queue                                        │
│  - JobPayload serialized as JSON                                  │
└─────────────────────────────────────┬───────────────────────────────┘
                                      │ BRPOP (blocking)
                                      ↓
┌─────────────────────────────────────────────────────────────────────┐
│                         WORKER PROCESS                              │
│  runner.py + price_refresh_worker.py                               │
│  - Polls queue with 5s timeout                                     │
│  - Dispatches to handle_price_refresh()                           │
│  - Orchestrates: ingest → DQ → alerts → freeze → persist         │
└─────────────────────────────────────┬───────────────────────────────┘
                                      │ DB operations
                                      ↓
┌─────────────────────────────────────────────────────────────────────┐
│                         POSTGRES DATABASE                          │
│  - TaskRun (job result)                                            │
│  - RunInputSnapshot (input state)                                  │
│  - Alerts, Portfolios, Prices, FX Rates                           │
└─────────────────────────────────────────────────────────────────────┘
```

### 5.3 Redis Queue Implementation

**Location**: `/home/lei-dev/projects/trading-assistant/backend/app/queue/redis_queue.py`

**Queue Structure**:
- **Queue Name**: `ta:jobs`
- **Redis URL**: `redis://redis:6379/0` (configurable)
- **Data Structure**: Redis List (LPUSH/BRPOP)

**JobPayload Model**:
```python
class JobPayload(BaseModel):
    job_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    task_kind: str                    # e.g., "PRICE_REFRESH"
    portfolio_id: str
    requested_by_user_id: str
    enqueued_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
```

**Example JSON**:
```json
{
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "task_kind": "PRICE_REFRESH",
  "portfolio_id": "660e8400-e29b-41d4-a716-446655440001",
  "requested_by_user_id": "770e8400-e29b-41d4-a716-446655440002",
  "enqueued_at": "2026-03-09T10:30:00+00:00"
}
```

**Enqueue Operation** (LPUSH to head):
```python
def enqueue_job(self, job: JobPayload) -> str:
    job_json = job.model_dump_json()
    self.client.lpush(self.queue_name, job_json)
    return job.job_id
```

**Dequeue Operation** (BRPOP blocking right-pop):
```python
def dequeue_job(self, timeout: int = 5) -> Optional[JobPayload]:
    result = self.client.brpop(self.queue_name, timeout=timeout)
    if result:
        job_json = result[1]
        return JobPayload.model_validate_json(job_json)
    return None
```

### 5.4 Price Refresh Worker

**Entry Point**: `/home/lei-dev/projects/trading-assistant/backend/app/worker/runner.py`

**Main Loop** (lines 20-71):
- Polls queue with 5-second timeout
- Dispatches jobs based on `task_kind`
- Handles graceful shutdown on SIGINT/SIGTERM
- Attaches correlation IDs for logging

**Job Processing Flow** (`price_refresh_worker.py` lines 39-308):

1. **Open DB Session** (line 77): Worker-managed lifecycle
2. **Select Provider** (line 81): Uses `MockProvider` for Phase 2
3. **Ingest Market Data** (lines 86-103):
   - Calls `ingest_prices_for_portfolio()`
   - Fetches intraday + close prices
   - Returns `IngestResult` with price_quotes, fx_quotes, errors
4. **Evaluate DQ Rules** (lines 106-113):
   - Calls `evaluate_dq()`
   - Returns list of `DQViolation` objects
5. **Process Violations** (lines 118-191):
   - For each violation: create alert with deduplication
   - For CRITICAL alerts: freeze portfolio + emit notification
6. **Determine Status** (lines 197-204):
   - `FROZEN`: CRITICAL violations + portfolio frozen
   - `FAILED`: violations exist but not frozen
   - `SUCCESS`: no violations
7. **Write TaskRun + RunInputSnapshot** (lines 207-267)
8. **Commit** (line 272)

### 5.5 External Scheduler

**Location**: `/home/lei-dev/projects/trading-assistant/backend/app/scheduler/phase2_scheduler.py`

**How It Works**:
1. **Login**: Authenticate to API and obtain Bearer token
2. **Get Portfolios**: Fetch all portfolios via `GET /api/v1/portfolios`
3. **Trigger Refresh**: For each portfolio, call `POST /api/v1/portfolios/{id}/market-data/refresh`
4. **Loop**: Waits `SCHEDULER_INTERVAL_MINUTES` (default 5) between cycles

**Configuration**:
- `SCHEDULER_API_BASE_URL`: `http://localhost:8000`
- `SCHEDULER_INTERVAL_MINUTES`: 5
- `SCHEDULER_AUTH_EMAIL` / `SCHEDULER_AUTH_PASSWORD`: API credentials

---

## 6. File Reference

### 6.1 Backend (Python/FastAPI)

| File | Purpose |
|------|---------|
| `app/services/data_quality.py` | DQ rules engine (8 rules) |
| `app/services/alerts.py` | Alert creation with deduplication |
| `app/services/freeze.py` | Portfolio freeze/unfreeze logic |
| `app/services/notifications.py` | Notification creation |
| `app/worker/price_refresh_worker.py` | Main job processor |
| `app/worker/runner.py` | Worker entry point |
| `app/queue/redis_queue.py` | Redis queue operations |
| `app/scheduler/phase2_scheduler.py` | External scheduler |
| `app/api/v1/endpoints/market_data.py` | Market data API endpoints |
| `app/api/v1/endpoints/alerts.py` | Alerts API endpoints |
| `app/api/v1/endpoints/freeze.py` | Freeze API endpoints |
| `app/api/v1/endpoints/notifications.py` | Notifications API endpoints |
| `app/domain/models.py` | SQLAlchemy ORM models |
| `app/schemas/market_data.py` | Market data Pydantic schemas |
| `app/schemas/alert.py` | Alert Pydantic schemas |
| `app/schemas/freeze.py` | Freeze Pydantic schemas |
| `app/schemas/notification.py` | Notification Pydantic schemas |
| `app/core/config.py` | Configuration including DQ thresholds |
| `alembic/versions/43a014ad94b8_phase2_market_data_dq_tables.py` | Phase 2 migration |

### 6.2 Frontend (TypeScript/Next.js)

| File | Purpose |
|------|---------|
| `src/app/market-data/page.tsx` | Market Data page |
| `src/app/alerts/page.tsx` | Alerts page |
| `src/app/portfolios/[id]/page.tsx` | Portfolio detail with FROZEN banner |
| `src/app/page.tsx` | Dashboard with navigation |
| `src/hooks/use-market-data.ts` | Market data TanStack Query hooks |
| `src/hooks/use-alerts.ts` | Alerts TanStack Query hook |
| `src/hooks/use-freeze.ts` | Freeze TanStack Query hooks |
| `src/hooks/use-notifications.ts` | Notifications TanStack Query hook |
| `src/components/portfolio-selector.tsx` | Portfolio dropdown component |
| `src/components/notifications-dropdown.tsx` | Notifications bell component |
| `src/types/index.ts` | TypeScript type definitions |

### 6.3 Documentation

| File | Purpose |
|------|---------|
| `implementation/Phase2_build_playbook.md` | Build playbook |
| `implementation/Phase2_building_materials.md` | This file — As-Built documentation |
| `docs/design/physical_data_model_v2.md` | PDM for Phase 2 tables |

---

## 7. Key Design Decisions

### 7.1 Idempotency via Unique Constraints

Both `price_points` and `fx_rates` use composite unique constraints to prevent duplicate ingestion:
- `price_points`: `(listing_id, as_of, source_id, is_close)`
- `fx_rates`: `(base_ccy, quote_ccy, as_of, source_id)`

This allows the worker to safely retry jobs without creating duplicate data.

### 7.2 Pure DQ Evaluator Pattern

The DQ engine (`data_quality.py`) returns violations but does NOT write to the database. The caller (worker) is responsible for:
1. Creating alerts
2. Freezing portfolios (if CRITICAL)
3. Emitting notifications

This separation allows for flexible DQ strategies (e.g., warn-only mode, different thresholds per portfolio).

### 7.3 Alert Deduplication

Alerts are deduplicated based on `(portfolio_id, listing_id, rule_code)` for **unresolved** alerts only. This prevents spam while allowing re-alerting once the previous alert is resolved.

### 7.4 GBX/GBP Scale Detection

The `DQ_GBX_SCALE` rule detects 100× errors by comparing the ratio of current price to previous close:
- Ratio ~0.01: Provider sent GBP, listing expects GBX (100× too small)
- Ratio ~100: Provider sent GBX, listing expects GBP (100× too large)

### 7.5 External Scheduler

The scheduler runs as a separate process and makes HTTP calls to the API rather than enqueuing directly to Redis. This:
- Ensures authentication/authorization
- Allows the API to validate the request
- Provides a clear audit trail via HTTP logs

### 7.6 Frontend Polling Strategy

- **Notifications**: 30-second polling via `refetchInterval: 30000`
- **Market Data/Alerts**: No polling (manual refresh via button)
- **Freeze Status**: No polling (checked on page load, updated via mutations)

---

## 8. Testing & Verification

### 8.1 Backend Tests

Located in `backend/tests/`:
- `test_dq_rules.py` — Unit tests for each DQ rule
- `test_data_quality.py` — Integration tests for DQ engine
- `test_alerts.py` — Alert creation and deduplication
- `test_freeze.py` — Freeze/unfreeze logic

### 8.2 Frontend Verification

- TypeScript compilation: `npx tsc --noEmit` ✓
- Build: `npm run build` ✓

### 8.3 Manual Smoke Test

See `scripts/phase2_smoke.sh` for end-to-end verification.

---

## 9. Operational Notes

### 9.1 Reset Admin Password

```bash
docker compose exec api python3 /app/scripts/reset_admin.py
```

Sets password to "admin" for `admin@example.com`.

### 9.2 Enable Admin User

```bash
docker compose exec db psql -U ta_app -d trading_assistant -c "UPDATE \"user\" SET is_enabled = true WHERE email = 'admin@example.com';"
```

### 9.3 Run Worker Locally

```bash
cd backend
python -m app.worker.runner
```

### 9.4 Run Scheduler

```bash
cd backend
python -m app.scheduler.phase2_scheduler
```

---

## 10. Glossary

| Term | Definition |
|------|------------|
| **DQ** | Data Quality |
| **GBX** | British pence (1/100 of GBP) |
| **GBP** | British pound sterling |
| **LSE** | London Stock Exchange |
| **NYSE** | New York Stock Exchange |
| **CRITICAL** | Highest alert severity — triggers portfolio freeze |
| **WARN** | Medium alert severity — logged but portfolio remains active |
| **INFO** | Lowest alert severity — informational only |
| **Freeze** | Circuit-breaker state preventing trades/advice |
| **TaskRun** | Audit record of background job execution |
| **RunInputSnapshot** | Reproducible input state for a task run |

---

*End of Phase 2 Building Materials Documentation*
