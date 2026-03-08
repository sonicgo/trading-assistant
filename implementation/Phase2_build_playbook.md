# Phase 2 Build Playbook — Market Data + Data Quality Gate (Execution Guide)

_Last updated: 2026-02-27 (UTC)_

This playbook turns Phase 2 scope into an implementable build checklist with concrete file responsibilities, interface contracts, data model guardrails, and “don’t-miss” safety edge cases.

Phase 2 Outcome:
- You can **ingest market prices** (intraday + EOD close) for monitored constituents.
- You can **ingest FX rates** (only as needed for validation at this stage).
- Every ingest produces a **TaskRun** with a reproducible **RunInputSnapshot**.
- A **Data Quality (DQ) Gate** validates data before it is trusted.
- DQ failures create **Alerts**, emit **Notification feed** rows (critical events), and can apply a **Freeze** to the portfolio.
- UI surfaces: Market Data, Alerts, Notifications (minimal polling), and “Frozen” banner on the portfolio.

---

## 0) Assumptions (locked for this playbook)

Backend:
- FastAPI + Pydantic v2
- SQLAlchemy 2.x + Alembic
- Postgres (schema per your Phase 1 setup; examples use `ta.*` tables)
- Single market data provider in V1, but a strict **Adapter Abstraction** is mandatory.
- Ingestion is **idempotent** (append-only writes; conflicts are non-fatal).
- Manual API triggers exist for V1, but **must enqueue jobs** (not do long-running fetch inline).
- “Scheduled refresh” in Phase 2 is acceptable as a **minimal scheduler stub** (simple loop/cron) — Phase 3 may replace this with a richer tasks model.

Frontend:
- Next.js (App Router) + TypeScript
- TanStack Query
- Decimal strings in API responses; UI uses decimal.js/big.js for arithmetic

---

## 1) Definition of Done (Phase 2)

Backend DoD:
- Market Data Adapter interface defined and one concrete adapter implemented (Mock or real provider).
- Core tables implemented + migrated:
  - `price_points`, `fx_rates`
  - `alerts`, `freeze_states`
  - `task_runs`, `run_input_snapshots`
  - `notifications`
- **Idempotency guardrails** exist via unique constraints + `ON CONFLICT` handling.
- Manual triggers **enqueue** jobs into Redis; worker consumes and performs:
  1) Load monitored constituents + listing metadata
  2) Fetch prices/FX via adapter
  3) Write `price_points` / `fx_rates` idempotently
  4) Run DQ gate (below)
  5) Write `task_run` + `run_input_snapshot`
  6) If DQ fails: write `alert` + (optionally) `freeze_state` + `notification`
- DQ Gate rules implemented (UC-22/23):
  1. **Staleness**: price older than expected
  2. **Missing**: expected close missing once market is closed (market-closed aware)
  3. **Jump**: move > configured threshold vs last close
  4. **Scale mismatch**: GBP/GBX mismatch and other scale errors
  5. **FX mismatch**: currency mismatch or FX unavailable/stale when required
  6. **Market closed awareness**: only enforce “missing close” after venue close time (timezone aware)
- Freeze semantics:
  - CRITICAL alerts can set `freeze_states.is_frozen=true`
  - While frozen, “advice”/future runs can be blocked; Phase 2 minimum: UI shows frozen and APIs expose status
- Notifications:
  - CRITICAL alert/freeze emits a row for polling feed (`GET /notifications?since=...`)

Frontend DoD:
- `/market-data` shows latest prices/FX (portfolio-scoped view is preferred).
- `/alerts` shows active alerts by portfolio (and their rule codes/severity).
- `/notifications` page (optional) or header badge; polling feed implemented.
- Portfolio detail shows a visible “FROZEN” banner + drill-down to the alert(s).

Exit criteria (Phase 2):
- Price refresh writes `price_points` idempotently (`ON CONFLICT DO NOTHING`).
- DQ failures produce Alert and (optionally) Freeze; runs are recorded as `FROZEN/FAILED`.
- TaskRuns recorded with status and summary.

---

## 2) Environment & Configuration

### 2.1 Required environment variables (backend)

Minimum keys (names indicative; align to your existing config style):

- `DATABASE_URL`
- `REDIS_URL` (e.g. `redis://redis:6379/0`)
- `MARKETDATA_PROVIDER` (e.g. `mock`, `yahoo`, `alphavantage`)
- `MARKETDATA_API_KEY` (if required by provider)

DQ / market rules:
- `DQ_STALE_MAX_MINUTES_INTRADAY` (e.g. `30`)
- `DQ_STALE_MAX_DAYS_CLOSE` (e.g. `3`)
- `DQ_JUMP_THRESHOLD_PCT` (e.g. `10`)
- `DQ_REQUIRE_CLOSE` (`true|false`) — if true, missing close becomes a DQ event once market is closed
- `DQ_FX_STALE_MAX_DAYS` (e.g. `3`)

Venue hours (minimal V1):
- `VENUE_LSE_TZ=Europe/London`
- `VENUE_LSE_CLOSE_TIME=16:30`
- `VENUE_NYSE_TZ=America/New_York`
- `VENUE_NYSE_CLOSE_TIME=16:00`
  - You can start with only the venues you actually use.

### 2.2 Optional configuration file

If you already use a file-based config folder, add:
- `config/venues.yml` (timezone + close time per venue)
- `config/dq.yml` (thresholds; allow overrides per venue)

---

## 3) Persistence/Data Model (PDM) — Phase 2 tables + constraints

### 3.1 `price_points` (append-only)
**Intent:** time-series prices for each listing.

**Must-have uniqueness (idempotency):**
- `UNIQUE(listing_id, as_of, source_id, is_close)`

Recommended columns (V1):
- `price_point_id (uuid pk)`
- `listing_id (uuid fk)`
- `as_of (timestamptz)` — provider timestamp (or normalized bucket)
- `price (numeric)` — stored as Decimal
- `currency (text)` — e.g. GBP, USD (provider-reported if available)
- `is_close (bool)`
- `source_id (text)` — provider identifier
- `raw (jsonb)` — optional: raw provider payload
- `created_at (timestamptz)`

Recommended index:
- `(listing_id, as_of DESC)` (optionally partial index for close points)

### 3.2 `fx_rates` (append-only)
**Intent:** FX needed for validation (Phase 2) and later valuation (Phase 4).

Uniqueness:
- `UNIQUE(base_ccy, quote_ccy, as_of, source_id)`

Minimal columns:
- `fx_rate_id (uuid pk)`
- `base_ccy (text)` / `quote_ccy (text)` — e.g. GBP/USD
- `as_of (timestamptz)`
- `rate (numeric)`
- `source_id (text)`
- `created_at (timestamptz)`

### 3.3 `alerts`
**Intent:** durable record of DQ events or system safety events.

Minimal columns:
- `alert_id (uuid pk)`
- `portfolio_id (uuid fk)`
- `listing_id (uuid fk, nullable)` — some alerts are portfolio-wide
- `severity (text)` — INFO/WARN/CRITICAL
- `rule_code (text)` — e.g. `DQ_GBX_SCALE`, `DQ_STALE_CLOSE`
- `title (text)` / `message (text)`
- `details (jsonb)` — thresholds, observed values, etc.
- `created_at (timestamptz)`
- `resolved_at (timestamptz nullable)`

### 3.4 `freeze_states`
**Intent:** circuit breaker state for a portfolio.

Minimal columns:
- `freeze_id (uuid pk)`
- `portfolio_id (uuid fk)`
- `is_frozen (bool)`
- `reason_alert_id (uuid fk nullable)`
- `created_at (timestamptz)`
- `cleared_at (timestamptz nullable)`
- `cleared_by_user_id (uuid fk nullable)`

### 3.5 `task_runs` + `run_input_snapshots`
**Intent:** auditability and reproducibility.

`task_runs` minimal columns:
- `run_id (uuid pk)`
- `job_id (uuid)` — from queue message
- `task_kind (text)` — e.g. `PRICE_REFRESH`
- `portfolio_id (uuid fk)`
- `status (text)` — SUCCESS / FROZEN / FAILED
- `started_at`, `ended_at`
- `summary (jsonb)` — counts, warnings, rule hits

`run_input_snapshots` minimal columns:
- `run_id (uuid pk, fk task_runs.run_id)`
- `input_json (jsonb)` — listing_ids, provider, time window, dq thresholds, venue config hashes
- `input_hash (text)` — stable hash for dedupe/debug (optional but recommended)
- `created_at (timestamptz)`

### 3.6 `notifications`
**Intent:** polling feed for critical events (Phase 2 minimum).

Minimal columns:
- `notification_id (uuid pk)`
- `owner_user_id (uuid fk)` — who should see it
- `severity (text)` — INFO/WARN/CRITICAL
- `title (text)`
- `body (text)`
- `created_at (timestamptz)`
- `read_at (timestamptz nullable)`
- `meta (jsonb)` — references (portfolio_id, alert_id, run_id)

---

## 4) Backend Build Steps (in-order)

### Step 1 — PDM + Alembic migrations (Backend)

Deliverables:
- SQLAlchemy models for the tables in Section 3
- Alembic migration(s) creating tables + constraints + indexes

Acceptance:
- `alembic upgrade head` creates tables cleanly
- Uniqueness constraints prevent duplicates without failing the pipeline

Suggested migration notes:
- Use `ON CONFLICT DO NOTHING` for append-only inserts
- Prefer `jsonb` for raw payload and run summaries

---

### Step 2 — Market Data Adapter contract (Backend)

**Goal:** provider independence.

Deliverables:
- `app/services/market_data_adapter.py` (ABC + result DTOs)
- One implementation:
  - `app/services/providers/mock_provider.py` (recommended first)
  - or `.../yahoo_provider.py` / `.../alphavantage_provider.py`

Suggested interface skeleton:
```python
# app/services/market_data_adapter.py
from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol, Sequence

@dataclass(frozen=True)
class PriceQuote:
    listing_id: str
    as_of: datetime
    price: str           # decimal string
    currency: str | None # provider-reported if available
    is_close: bool
    raw: dict | None

@dataclass(frozen=True)
class FxQuote:
    base_ccy: str
    quote_ccy: str
    as_of: datetime
    rate: str            # decimal string
    raw: dict | None

class MarketDataAdapter(Protocol):
    source_id: str

    async def fetch_prices(
        self,
        listing_ids: Sequence[str],
        *,
        want_close: bool,
        want_intraday: bool,
    ) -> list[PriceQuote]:
        ...

    async def fetch_fx_rates(
        self,
        pairs: Sequence[tuple[str, str]],
    ) -> list[FxQuote]:
        ...
```

Acceptance:
- Mock provider returns deterministic values for repeatable tests.

---

### Step 3 — Job queue + worker (Backend)

**Goal:** long-running fetch/ingest happens in worker; API only enqueues.

Deliverables:
- `app/queue/redis_queue.py` (enqueue + dequeue)
- `app/worker/price_refresh_worker.py` (main loop)
- Job payload (minimum):
  - `job_id`, `task_kind`, `portfolio_id`, `requested_by_user_id`, `enqueued_at`

Suggested job payload:
```json
{
  "job_id": "uuid",
  "task_kind": "PRICE_REFRESH",
  "portfolio_id": "uuid",
  "requested_by_user_id": "uuid",
  "enqueued_at": "2026-02-27T10:00:00Z"
}
```

Acceptance:
- Enqueue from API returns quickly (<200ms)
- Worker logs correlation IDs (`job_id`, `run_id`, `portfolio_id`)

---

### Step 4 — Ingestion pipeline (Backend)

**Goal:** one orchestration function that the worker calls.

Deliverables:
- `app/services/market_data_ingest.py`
  - loads monitored constituents + listing metadata
  - calls adapter
  - writes price_points/fx_rates idempotently

Notes:
- **DB session lifecycle (worker context):** workers don’t get FastAPI’s `Depends(get_db)` lifecycle. Ensure the worker uses a dedicated SQLAlchemy session context manager (e.g., `with SessionLocal() as db:`) and commits/rolls back safely to avoid leaking connections.

Suggested structure:
```python
# app/services/market_data_ingest.py
async def ingest_prices_for_portfolio(
    *,
    db,
    adapter,
    portfolio_id: str,
    job_id: str,
    requested_by_user_id: str,
) -> str:  # returns run_id
    ...
```

Acceptance:
- Running ingest twice for same provider timestamp does not create duplicates.

---

### Step 5 — Data Quality Gate (Backend)

**Goal:** validate fetched/inserted data and decide run outcome.

Deliverables:
- `app/services/data_quality.py`
- Rule codes (examples):
  - `DQ_STALE_INTRADAY`
  - `DQ_STALE_CLOSE`
  - `DQ_MISSING_CLOSE`
  - `DQ_JUMP_CLOSE`
  - `DQ_GBX_SCALE`
  - `DQ_CCY_MISMATCH`
  - `DQ_FX_MISSING`
  - `DQ_FX_STALE`

Rule requirements (V1 pragmatic):
- **Staleness**
  - intraday: now - latest_intraday.as_of > `DQ_STALE_MAX_MINUTES_INTRADAY`
  - close: now - latest_close.as_of > `DQ_STALE_MAX_DAYS_CLOSE`
- **Missing close**
  - only enforce if market is closed for the venue (timezone + close time)
- **Jump**
  - compare latest close vs previous close; threshold `DQ_JUMP_THRESHOLD_PCT`
- **Scale mismatch (GBX/GBP)**
  - if listing expects `GBX` but provider returns `GBP` (or vice versa), detect 100x hazards
  - compare to last close and/or listing quote_scale rules from Phase 1
- **FX mismatch**
  - if provider currency != listing trading currency -> CRITICAL (or WARN if you intentionally allow provider to return a different but well-defined ccy)
  - if portfolio base ccy requires FX (later phases), Phase 2 minimum is validation only:
    - if FX required for a check and FX missing/stale -> WARN/CRITICAL per config

Acceptance:
- Inject a bad price (100x) and see a CRITICAL alert created.
- Inject a stale close and see a WARN/CRITICAL alert (per your policy).

---

### Step 6 — Alerts + Freeze + Notifications (Backend)

**Goal:** consistent side effects when DQ fails.

Deliverables:
- `app/services/alerts.py` (create/resolve)
- `app/services/freeze.py` (freeze/unfreeze)
- `app/services/notifications.py` (emit notification rows)

Required behavior:
- **Alert Deduplication:** before creating a new alert, check whether an **unresolved** alert already exists for the same `(portfolio_id, listing_id, rule_code)`. If yes, do **not** create a duplicate (and do not emit a duplicate notification); instead, optionally update `details` or leave as-is.
- On DQ failure:
  - write `alerts` row(s)
  - if CRITICAL: set `freeze_states.is_frozen=true`
  - write `task_runs` with status:
    - `FROZEN` if frozen
    - `FAILED` if not frozen but run invalid
  - write `run_input_snapshot`
  - emit `notifications` row for CRITICAL (Phase 2 minimum)

Acceptance:
- DQ failure produces:
  - Alert row
  - Freeze row (if CRITICAL)
  - Notification row
  - TaskRun status is correct

---

### Step 7 — API endpoints (Backend)

**Goal:** portfolio-scoped endpoints; no cross-tenant leaks.

Deliverables (indicative):
- `app/api/v1/endpoints/market_data.py`
  - `GET /portfolios/{pid}/market-data/prices?limit=...`
  - `GET /portfolios/{pid}/market-data/fx?limit=...`
  - `POST /portfolios/{pid}/market-data/refresh` (enqueues PRICE_REFRESH)
- `app/api/v1/endpoints/alerts.py`
  - `GET /portfolios/{pid}/alerts?active_only=true`
- `app/api/v1/endpoints/freeze.py`
  - `GET /portfolios/{pid}/freeze`
  - `POST /portfolios/{pid}/freeze` (manual freeze)
  - `POST /portfolios/{pid}/unfreeze` (manual unfreeze)
- `app/api/v1/endpoints/notifications.py`
  - `GET /notifications?since=timestamp`

Acceptance:
- All portfolio-scoped endpoints enforce `owner_user_id` tenancy (Phase 1 standard).

---

### Step 8 — Minimal “scheduled refresh” stub (Backend, Phase 2 acceptable)

Choose one:
- Option A: a tiny `scheduler` container that enqueues PRICE_REFRESH every N minutes for each portfolio
- Option B: cron outside containers calling `POST /portfolios/{pid}/market-data/refresh`

Acceptance:
- At least one automated trigger exists (not only manual clicks).

---

## 5) Frontend Build Steps (in-order)

### Step 9 — Frontend wiring

Deliverables:
- Query hooks:
  - `useMarketData(pid)`
  - `useAlerts(pid)`
  - `useFreeze(pid)`
  - `useNotifications(since)`
- Pages (Next.js **App Router**):
  - `/market-data` in `src/app/market-data/page.tsx` (prefer: portfolio selector; show latest close + intraday)
  - `/alerts` in `src/app/alerts/page.tsx` (portfolio selector; active alerts)
  - Optional `/notifications` in `src/app/notifications/page.tsx` (or header dropdown)

Acceptance:
- Portfolio detail shows a clear “FROZEN” banner when `is_frozen=true`.
- Alerts page shows the triggering rule codes and timestamps.

---

## 6) Testing Strategy (minimal, Phase 2)

### 6.1 Automated tests (pytest + httpx)
Minimum test suite:
- `test_price_ingest_idempotent_unique_constraint()`
- `test_dq_gbx_guard_detects_100x_mismatch()`
- `test_dq_stale_close_creates_alert()`
- `test_missing_close_only_after_market_close_time()`
- `test_alert_creates_notification_row_for_critical()`
- `test_task_run_written_with_status_success_vs_frozen()`

### 6.2 Manual smoke test script
Create `scripts/phase2_smoke.sh`:
- login
- create portfolio + listing (Phase 1 already supports)
- map monitored constituent(s)
- trigger `POST /portfolios/{pid}/market-data/refresh`
- verify:
  - `GET /portfolios/{pid}/market-data/prices` returns rows
  - `GET /portfolios/{pid}/alerts` empty (healthy run)
- inject anomaly via mock provider toggle:
  - trigger refresh again
  - verify alert + freeze + notification

Keep this as your homelab bring-up test, same as Phase 1.

---

## 7) Don’t-miss edge cases

- **GBX/GBP (100x) hazards:** never trust provider currency blindly; always compare to listing `quote_scale` rules.
- **Missing close:** don’t alert while market still open; enforce after venue close time (timezone aware).
- **Provider timestamps:** choose a stable `as_of` normalization strategy or you’ll defeat idempotency.
- **Partial portfolio anomalies:** decide whether to freeze on *any* CRITICAL constituent vs only if % impacted exceeds threshold (start simple: any CRITICAL freezes).
- **Tenancy:** keep endpoints portfolio-scoped to avoid future leaks.

---

## 8) Quick operational notes (Phase 2)

- Run worker locally:
  - `python -m app.worker.price_refresh_worker`
- Run minimal scheduler stub:
  - `python -m app.scheduler.phase2_scheduler` (if you implement Option A)
- Use correlation IDs in logs:
  - `job_id`, `run_id`, `portfolio_id`

