# Phase 5–6 Final Build Playbook — Execution Capture, Audit, and Ops Polish

_Last updated: 2026-03-11 (UTC)_

This playbook consolidates the remaining V1 work after the implemented Phase 1–4 baseline. It is written against the system that already exists today:

- local Docker Compose deployment
    
- FastAPI + SQLAlchemy + Alembic backend
    
- Next.js + TanStack Query frontend
    
- provider-backed market data with DQ/freeze guardrails
    
- append-only ledger with incremental cash/holding snapshots
    
- deterministic recommendation engine with policy allocations, projected cash pool logic, and stale-price/freeze blockers
    

This document covers:

- **Phase 5** — Execution Capture + Audit Trail
    
- **Phase 6** — Ops Polish
    

It assumes Phases 1–4 are already implemented and should not be redesigned.

---

## 0) Source of truth and scope alignment

There is a phase-label mismatch between the implementation report and the original delivery plan.

For this playbook, treat the **delivery plan** as the contractual source of truth for phase numbering:

- **Phase 5** = execution capture + audit trail
    
- **Phase 6** = ops polish
    

Useful ideas from the implementation report’s “Future Roadmap” are folded in only where they fit these two phases. Anything that changes system scope materially remains deferred.

---

## 1) Implemented baseline carried forward

### 1.1 Backend baseline already in place

- Registry domain: instruments, listings, sleeves, portfolios, constituents
    
- Policy allocation mapping: `portfolio_policy_allocations`
    
- Market data: `price_points`, `fx_rates`, provider abstraction, yfinance adapter, mock provider
    
- Safety controls: `alerts`, `freeze_states`, `notifications`
    
- Book of record: `ledger_batches`, `ledger_entries`, `cash_snapshots`, `holding_snapshots`
    
- Deterministic engine inputs and calculator modules
    
- Local deployment via Docker Compose with Postgres, Redis, API, worker, UI
    

### 1.2 Frontend baseline already in place

- Portfolio detail page
    
- Assistant/trade-plan page
    
- Market-data hooks and sync mutation
    
- API-first UI using TanStack Query
    

### 1.3 Architectural constraints that remain fixed

- Base currency remains **GBP** for V1
    
- Event-sourced / append-only ledger remains authoritative
    
- Recommendations remain **manual-review only** until explicitly marked executed
    
- No broker API integration in V1
    
- Decimal math end to end
    
- Freeze and stale-price blockers remain hard safety gates for advice generation
    

---

## 2) Phase 5 outcome

### Outcome

Close the loop from recommendation to recorded execution, while preserving full auditability and keeping the ledger model append-only.

### User story

1. User generates a deterministic recommendation batch.
    
2. User executes one or more trades manually with broker.
    
3. User records what actually happened.
    
4. System writes the resulting portfolio facts into the ledger.
    
5. Snapshots update atomically.
    
6. Audit events preserve who did what and when.
    
7. Recommendation status reflects whether it was executed, partially executed, ignored, reversed, or superseded.
    

### Phase 5 is **not**

- automated broker order placement
    
- smart order routing
    
- FIX or API integration with a broker
    
- tax-lot optimisation engine
    
- wash-sale compliance engine
    
- order-execution automation
    

---

## 3) Phase 6 outcome

### Outcome

Make the system operable unattended in homelab/production-like conditions, with dashboards, data-retention controls, backup/restore procedures, and basic observability.

### User story

1. User can see current value, sleeve mix, drift, and recent run history.
    
2. Old operational data does not grow without bound.
    
3. Backups can be taken and restored using a documented runbook.
    
4. API/worker/scheduler health is visible.
    
5. Operational incidents can be diagnosed from structured logs and metrics.
    

---

## 4) Final V1 definition of done

V1 is complete when all of the following are true:

1. Recommendation batches can be marked as executed or ignored.
    
2. Marking executed writes ledger facts and updates snapshots atomically.
    
3. Audit events exist for key user/system actions.
    
4. Recommendation lifecycle is visible in UI.
    
5. Portfolio dashboards show current value, sleeve weights, drift, and run history.
    
6. Retention and housekeeping jobs run unattended.
    
7. Backup and restore have a written, tested playbook.
    
8. Health checks and structured logs support day-2 operations.
    

---

## 5) Key locked decisions for Phase 5–6

|ID|Decision|
|---|---|
|P56-D01|Keep **recommendations** and **executions** separate. Recommendation data never mutates holdings directly.|
|P56-D02|Execution capture writes **ledger batches/entries** only; snapshots update from ledger in the same transaction.|
|P56-D03|Execution capture is **manual confirmation** of broker activity, not broker integration.|
|P56-D04|Recommendation lifecycle must support full, partial, ignored, and reversed outcomes.|
|P56-D05|Audit events are append-only and must exist for all key transitions.|
|P56-D06|Dashboards read from snapshots and persisted recommendation/run history, not ad hoc recalculation in the browser.|
|P56-D07|Operational data retention applies to alerts, notifications, task runs, and old run-input snapshots; not to ledger facts.|
|P56-D08|Backup/restore must be documented and testable with Docker Compose deployment.|
|P56-D09|Observability should stay lightweight: structured logs, health checks, optional basic metrics, no heavy external observability stack required for V1.|

---

## 6) Phase 5 functional contract

### 6.1 Core capabilities

Phase 5 must add:

- recommendation execution capture
    
- recommendation ignore/dismiss workflow
    
- recommendation status model
    
- execution-to-ledger translation
    
- audit event write path
    
- UI history/status surfaces
    

### 6.2 Minimum lifecycle states

Recommended recommendation batch lifecycle:

- `PROPOSED`
    
- `APPROVED` (optional if you want explicit review step)
    
- `EXECUTED_PARTIAL`
    
- `EXECUTED_FULL`
    
- `IGNORED`
    
- `REVERSED`
    
- `SUPERSEDED`
    

If you want a leaner V1, `APPROVED` can be omitted and UI can move directly from `PROPOSED` to `EXECUTED_*` or `IGNORED`.

### 6.3 Execution capture modes

Support these modes in V1:

#### Mode A — Execute exact recommendation lines

User confirms that one or more proposed lines were executed and records:

- actual quantity
    
- actual gross/notional or execution value
    
- actual fee
    
- effective/execution timestamp
    
- optional broker reference / note
    

#### Mode B — Partial execution

User records a smaller quantity or subset of lines.

#### Mode C — Ignore recommendation

User explicitly closes a recommendation without execution.

#### Mode D — Reverse mistaken execution capture

If the user captured the wrong execution, they create a compensating reversal through the ledger, and the recommendation lifecycle is updated accordingly.

---

## 7) Phase 5 data model

### 7.1 New table: `audit_events`

Intent:  
Durable append-only audit trail for user/system actions.

Minimum columns:

- `audit_event_id (uuid pk)`
    
- `portfolio_id (uuid fk -> portfolio, nullable)`
    
- `actor_user_id (uuid fk -> user, nullable)`
    
- `event_type (text, not null)`
    
- `entity_type (text, not null)`
    
- `entity_id (uuid or text, not null)`
    
- `occurred_at (timestamptz, not null default now())`
    
- `summary (text, not null)`
    
- `details (jsonb, nullable)`
    
- `correlation_id (text, nullable)`
    

Recommended indexes:

- `(portfolio_id, occurred_at desc)`
    
- `(entity_type, entity_id, occurred_at desc)`
    
- `(actor_user_id, occurred_at desc)`
    

### 7.2 Recommended extension: `recommendation_batches`

Add execution lifecycle fields if not already present.

Recommended columns:

- `status`
    
- `executed_at (timestamptz, nullable)`
    
- `ignored_at (timestamptz, nullable)`
    
- `closed_by_user_id (uuid fk -> user, nullable)`
    
- `execution_summary (jsonb, nullable)`
    
- `last_audit_event_id (uuid fk -> audit_events, nullable)`
    

### 7.3 Recommended extension: `recommendation_lines`

Add execution-tracking fields if not already present.

Recommended columns:

- `status (text, nullable)` — `PROPOSED`, `EXECUTED`, `PARTIAL`, `IGNORED`, `REVERSED`
    
- `executed_quantity (numeric(28,10), nullable)`
    
- `executed_value_gbp (numeric(28,10), nullable)`
    
- `executed_fee_gbp (numeric(28,10), nullable)`
    
- `execution_note (text, nullable)`
    
- `ledger_entry_id (uuid fk -> ledger_entries, nullable)`
    

Note:  
A single recommendation line may map to one or more ledger entries in real life, but V1 can keep a 1:1 or 1:few relationship by storing the primary ledger entry reference on the line and full mapping in execution details JSON.

### 7.4 Optional table: `recommendation_executions`

If you want cleaner normalization, add a dedicated execution table.

Minimum columns:

- `recommendation_execution_id (uuid pk)`
    
- `recommendation_batch_id (uuid fk)`
    
- `recommendation_line_id (uuid fk, nullable)`
    
- `portfolio_id (uuid fk)`
    
- `listing_id (uuid fk, nullable)`
    
- `action (text)`
    
- `executed_quantity (numeric(28,10), nullable)`
    
- `executed_value_gbp (numeric(28,10), nullable)`
    
- `fee_gbp (numeric(28,10), nullable)`
    
- `executed_at (timestamptz, not null)`
    
- `broker_reference (text, nullable)`
    
- `note (text, nullable)`
    
- `ledger_batch_id (uuid fk -> ledger_batches, nullable)`
    
- `created_by_user_id (uuid fk -> user, not null)`
    
- `created_at (timestamptz, default now())`
    

Recommendation:  
Use this table if you want Phase 5 to stay clean and extensible. If you want minimum churn, extend `recommendation_lines` plus `audit_events` only.

---

## 8) Phase 5 execution-to-ledger translation rules

### 8.1 General principle

Captured executions do not mutate recommendations directly into state. They must be translated into normal ledger batches and entries using the existing Phase 3 posting service.

### 8.2 Buy execution

For an executed buy:

- create `BUY` ledger entry
    
- `quantity_delta > 0`
    
- `net_cash_delta_gbp < 0`
    
- `fee_gbp >= 0`
    
- update holding and cash snapshots atomically
    

### 8.3 Sell execution

For an executed sell:

- create `SELL` ledger entry
    
- `quantity_delta < 0`
    
- `net_cash_delta_gbp > 0`
    
- `fee_gbp >= 0`
    
- reject if this would create negative holdings
    

### 8.4 Ignore recommendation

Ignoring a recommendation:

- does **not** create ledger entries
    
- must create audit event
    
- must update recommendation lifecycle status
    

### 8.5 Reverse captured execution

Reversal of mistaken capture:

- must create `REVERSAL` ledger entries via existing reversal service
    
- must create audit event
    
- must update recommendation/recommendation-line execution status accordingly
    

### 8.6 Partial execution

If only part of a line is executed:

- ledger reflects actual quantity/value only
    
- line status becomes `PARTIAL` or `EXECUTED_PARTIAL`
    
- remaining unexecuted quantity stays advisory history only; do not auto-generate another recommendation batch silently
    

---

## 9) Audit event catalog

Minimum event types to implement:

- `RECOMMENDATION_GENERATED`
    
- `RECOMMENDATION_VIEWED` (optional)
    
- `RECOMMENDATION_EXECUTED`
    
- `RECOMMENDATION_PARTIALLY_EXECUTED`
    
- `RECOMMENDATION_IGNORED`
    
- `RECOMMENDATION_REVERSED`
    
- `PORTFOLIO_FROZEN`
    
- `PORTFOLIO_UNFROZEN`
    
- `LEDGER_BATCH_POSTED`
    
- `LEDGER_BATCH_REVERSED`
    
- `CSV_IMPORT_PREVIEWED`
    
- `CSV_IMPORT_APPLIED`
    
- `POLICY_CHANGED` (if policy editing exists in V1)
    

Required audit detail payload examples:

- actor
    
- portfolio_id
    
- recommendation_batch_id
    
- recommendation_line_ids
    
- ledger_batch_id / ledger_entry_ids where relevant
    
- reason / note
    
- old_status / new_status where relevant
    

---

## 10) Phase 5 API surface

Recommended endpoints:

- `GET /api/v1/portfolios/{portfolio_id}/recommendations`
    
- `GET /api/v1/portfolios/{portfolio_id}/recommendations/{batch_id}`
    
- `POST /api/v1/portfolios/{portfolio_id}/recommendations/{batch_id}/execute`
    
- `POST /api/v1/portfolios/{portfolio_id}/recommendations/{batch_id}/ignore`
    
- `GET /api/v1/portfolios/{portfolio_id}/audit-events?limit=&offset=`
    
- `GET /api/v1/portfolios/{portfolio_id}/executions?limit=&offset=` (optional)
    

### 10.1 Execute request contract

Suggested shape:

{  
  "executed_at": "2026-03-11T14:35:00Z",  
  "note": "Executed in AJ Bell",  
  "lines": [  
    {  
      "recommendation_line_id": "...",  
      "executed_quantity": "12.0000000000",  
      "executed_value_gbp": "1524.36",  
      "fee_gbp": "0.00",  
      "broker_reference": "optional-ref"  
    }  
  ]  
}

Behavior:

- validate ownership and recommendation status
    
- validate no duplicate execution for same line unless partial model explicitly allows it
    
- create ledger batch/entries
    
- create audit event(s)
    
- update recommendation status atomically or within one controlled unit of work
    

### 10.2 Ignore request contract

Suggested shape:

{  
  "reason": "Chose to defer until next month"  
}

Behavior:

- no ledger mutation
    
- audit event required
    
- status changes to `IGNORED`
    

---

## 11) Phase 5 frontend deliverables

### 11.1 Recommendation detail page enhancements

Add:

- status badge
    
- execute button
    
- ignore button
    
- execution history panel
    
- linked ledger history / audit trail references
    

### 11.2 Execution capture form

Fields:

- executed timestamp
    
- per-line quantity
    
- per-line value / fee
    
- broker reference
    
- free-text note
    

Rules:

- no optimistic state mutation
    
- server response becomes source of truth
    
- after successful execute, invalidate:
    
    - recommendation detail
        
    - ledger history
        
    - cash snapshot
        
    - holding snapshots
        
    - audit-event list
        

### 11.3 Audit history view

Minimum surface:

- timeline/table grouped by date
    
- event type
    
- actor
    
- summary
    
- related entity links
    

---

## 12) Phase 5 build order

### Step 1 — PDM + Alembic

Deliverables:

- `audit_events`
    
- recommendation execution lifecycle extensions
    
- optional `recommendation_executions`
    

Acceptance:

- migration cleanly upgrades existing Phase 1–4 schema
    
- foreign keys preserve portfolio integrity
    

### Step 2 — Schemas and domain contracts

Deliverables:

- `app/schemas/audit.py`
    
- `app/schemas/executions.py`
    
- recommendation status enums
    

Acceptance:

- request/response contracts serialize decimals as strings
    
- invalid state transitions return clean 4xx errors
    

### Step 3 — Execution capture service

Deliverables:

- `app/services/execution_capture.py`
    

Responsibilities:

- validate recommendation state
    
- translate execution payload into ledger batch request(s)
    
- call existing Phase 3 ledger posting service
    
- create audit events
    
- update recommendation status/summary
    

Acceptance:

- successful execute produces correct ledger rows and snapshot changes
    
- ignore produces no ledger rows but creates audit event
    
- reversal path uses existing reversal mechanics
    

### Step 4 — API endpoints

Deliverables:

- `app/api/v1/endpoints/executions.py`
    
- `app/api/v1/endpoints/audit.py`
    
- recommendation endpoint extensions
    

Acceptance:

- all portfolio-scoped endpoints enforce tenancy
    
- duplicate or invalid status transitions rejected cleanly
    

### Step 5 — Frontend integration

Deliverables:

- `src/app/portfolios/[id]/recommendations/[batchId]/page.tsx` or equivalent
    
- `src/components/recommendations/execution-capture-form.tsx`
    
- `src/components/audit/audit-timeline.tsx`
    
- hooks in `src/hooks/use-recommendations.ts` and `src/hooks/use-audit.ts`
    

Acceptance:

- user can mark recommendation executed or ignored end-to-end
    
- snapshot views update correctly after execute
    

---

## 13) Phase 5 tests

Minimum automated tests:

- `test_execute_recommendation_creates_ledger_batch_and_audit_event()`
    
- `test_ignore_recommendation_creates_audit_event_only()`
    
- `test_partial_execution_updates_status_correctly()`
    
- `test_execute_recommendation_rejects_cross_tenant_access()`
    
- `test_execute_recommendation_rejects_duplicate_full_execution()`
    
- `test_execution_capture_uses_existing_ledger_service()`
    
- `test_reverse_captured_execution_creates_compensating_entries()`
    
- `test_audit_event_written_for_freeze_and_unfreeze()`
    

Manual smoke script: `scripts/phase5_smoke.sh`

1. create/generate recommendation batch
    
2. execute one line fully
    
3. verify ledger history updated
    
4. verify snapshots updated
    
5. verify audit event exists
    
6. generate another batch and ignore it
    
7. verify no ledger changes and audit event exists
    
8. capture partial execution
    
9. verify lifecycle status and amounts
    
10. reverse mistaken capture
    
11. verify compensating entries and audit trail
    

---

## 14) Phase 6 dashboards

### 14.1 Dashboard set

Minimum dashboards/pages:

- **Portfolio Overview**
    
    - total portfolio value
        
    - cash balance
        
    - sleeve weights vs targets
        
    - drift summary
        
    - freeze status
        
- **Drift History**
    
    - history of top sleeve drifts over time
        
    - recommendation batch outcomes over time
        
- **Run History**
    
    - market-data runs
        
    - recommendation runs
        
    - blocked/failed runs
        
- **Execution History**
    
    - executed recommendations
        
    - ignored recommendations
        
    - reversals
        

### 14.2 Data sources

Read from persisted tables, not client-side recomputation where avoidable:

- `cash_snapshots`
    
- `holding_snapshots`
    
- `recommendation_batches`
    
- `recommendation_lines`
    
- `task_runs`
    
- `audit_events`
    
- latest trusted `price_points`
    

### 14.3 Optional materialized views

If query pressure appears, consider read-optimized views for:

- current portfolio valuation
    
- sleeve valuation summary
    
- run-status rollups
    

Do not add them preemptively unless needed.

---

## 15) Phase 6 retention and housekeeping

### 15.1 Retain forever / long horizon

Do not purge in V1:

- `ledger_batches`
    
- `ledger_entries`
    
- `cash_snapshots` current rows
    
- `holding_snapshots` current rows
    
- `audit_events` (unless you later define archival)
    
- recommendation batches/lines for V1 history
    

### 15.2 Retention candidates

Add scheduled jobs for:

- old `notifications` — e.g. keep unread forever, archive/read older than N days
    
- resolved `alerts` older than N days
    
- `run_input_snapshots` older than N days if high-volume and reproducibility policy allows pruning
    
- `task_runs` older than N days after summarization
    

Recommended V1 defaults:

- notifications: 180 days for read rows
    
- alerts: 365 days for resolved rows
    
- task runs: 365 days
    
- run input snapshots: 90–365 days depending on volume and need
    

### 15.3 Housekeeping jobs

Suggested jobs:

- `RETENTION_NOTIFICATIONS`
    
- `RETENTION_ALERTS`
    
- `RETENTION_TASK_RUNS`
    
- `RETENTION_RUN_INPUT_SNAPSHOTS`
    

Each job should:

- write a task run record
    
- report rows deleted/archived
    
- never touch ledger facts
    

---

## 16) Phase 6 backup and restore playbook

### 16.1 Backup scope

At minimum back up:

- PostgreSQL database
    
- `.env` / secret material (securely, outside git)
    
- policy payloads / manifesto execution files if stored outside DB
    
- Docker Compose manifests / deployment config
    

### 16.2 Minimum backup procedure

Document and test:

- full logical database backup via `pg_dump`
    - Update `backend/Dockerfile` to install `postgresql-client` so the `pg_dump` command is available inside the container.
    
- restore into clean environment
    
- apply migrations if needed
    
- start services
    
- run smoke test
    

### 16.3 Restore verification checklist

After restore verify:

- user can log in
    
- portfolios exist
    
- market data history accessible
    
- ledger snapshots consistent
    
- recommendations visible
    
- audit history visible
    
- health endpoint returns OK
    

### 16.4 Deliverable

Create `docs/runbooks/backup_restore.md` including:

- commands
    
- storage locations
    
- retention rotation
    
- restore drill procedure
    
- rollback guidance
    

---

## 17) Phase 6 observability and operational controls

### 17.1 Structured logging

Standardize log fields across API/worker/scheduler:

- timestamp
    
- service name
    
- environment
    
- log level
    
- correlation_id
    
- portfolio_id (when relevant)
    
- run_id / batch_id / recommendation_batch_id (when relevant)
    
- event_type / task_kind
    
- outcome / error code
    

### 17.2 Health checks

Required endpoints/signals:

- `/health` basic liveness
    
- `/ready` or equivalent readiness check
    
- DB connectivity check
    
- Redis connectivity check where worker/scheduler depends on it
    

### 17.3 Basic metrics

If you implement metrics, keep them lightweight:

- recommendation run count by status
    
- task run duration
    
- ledger post count
    
- alerts by severity
    
- active freeze count
    
- retention job deleted row counts
    

### 17.4 Operational controls

Add/administer:

- manual freeze/unfreeze remains available
    
- optional global “scheduler pause” flag if not already present
    
- clear runbook for stale-price recovery and yfinance outage handling
    

---

## 18) Phase 6 build order

### Step 1 — Dashboard APIs

Deliverables:

- `app/api/v1/endpoints/dashboard.py`
    
- aggregated read models / queries
    

Acceptance:

- overview and run-history data returned in one or few efficient calls
    

### Step 2 — Frontend dashboards

Deliverables:

- `src/app/dashboard/page.tsx` enhancement or dedicated dashboard pages
    
- charts/tables for value, sleeve weights, drift history, run history
    

Acceptance:

- user can inspect portfolio and operations state without drilling into raw tables
    

### Step 3 — Retention jobs

Deliverables:

- `app/services/retention.py`
    
- scheduler/worker job definitions
    

Acceptance:

- jobs run unattended
    
- task run/audit summary produced
    
- no ledger facts deleted
    

### Step 4 — Backup/restore runbook

Deliverables:

- `docs/runbooks/backup_restore.md`
    
- optional backup helper script(s)
    

Acceptance:

- restore drill completed successfully at least once
    

### Step 5 — Observability hardening

Deliverables:

- structured logging config
    
- health/readiness endpoints improvements
    
- optional lightweight metrics endpoint
    

Acceptance:

- common failure modes are diagnosable from logs and health status
    

---

## 19) Phase 6 tests and operational drills

Minimum tests:

- `test_dashboard_summary_matches_snapshot_state()`
    
- `test_retention_job_does_not_delete_ledger_facts()`
    
- `test_retention_job_writes_task_run_summary()`
    
- `test_backup_restore_smoke_recovery()`
    
- `test_health_endpoint_detects_db_failure()`
    
- `test_structured_logs_include_correlation_id()`
    

Operational drills:

1. stale-price block and recovery
    
2. freeze/unfreeze cycle
    
3. DB restore into fresh stack
    
4. retention job dry run and real run
    
5. yfinance outage simulation with graceful error surfaces
    

---

## 20) File map

Backend:

- `app/services/execution_capture.py`
    
- `app/services/audit.py`
    
- `app/services/retention.py`
    
- `app/api/v1/endpoints/executions.py`
    
- `app/api/v1/endpoints/audit.py`
    
- `app/api/v1/endpoints/dashboard.py`
    
- `app/schemas/executions.py`
    
- `app/schemas/audit.py`
    
- `app/domain/models.py`
    
- `alembic/versions/<revision>_phase5_6_execution_audit_ops.py`
    

Frontend:

- `src/app/portfolios/[id]/recommendations/[batchId]/page.tsx`
    
- `src/components/recommendations/execution-capture-form.tsx`
    
- `src/components/audit/audit-timeline.tsx`
    
- `src/components/dashboard/value-summary.tsx`
    
- `src/components/dashboard/sleeve-weights-chart.tsx`
    
- `src/components/dashboard/run-history-table.tsx`
    
- `src/hooks/use-audit.ts`
    
- `src/hooks/use-dashboard.ts`
    
- `src/hooks/use-executions.ts`
    

Docs / scripts:

- `scripts/phase5_smoke.sh`
    
- `scripts/phase6_smoke.sh`
    
- `docs/runbooks/backup_restore.md`
    
- `implementation/Phase5_6_final_build_playbook.md`
    

---

## 21) Explicit deferrals beyond this final V1 playbook

Keep these out of the final V1 unless you intentionally re-scope:

- broker API integration / automated order placement
    
- broker statement ingestion and full reconciliation parser
    
- tax-loss harvesting optimizer
    
- FIFO/LIFO/specific-lot selection engine
    
- wash-sale compliance engine
    
- backtesting / UC-90 dry run
    
- multi-provider market data failover
    
- multi-currency cash ledger
    
- heavy observability platform (Prometheus/Grafana/ELK) if lightweight controls are sufficient
    
- full historical snapshot rebuild admin tool
    

---

## 22) Recommended delivery sequence from current state

Given your reported baseline, the most efficient close-out order is:

1. **Phase 5 execution capture core**
    
    - audit table
        
    - execute/ignore endpoints
        
    - execution-to-ledger translation
        
2. **Phase 5 UI lifecycle surfaces**
    
    - recommendation detail execution form
        
    - audit timeline
        
3. **Phase 6 dashboard reads**
    
    - overview, drift, run history, execution history
        
4. **Phase 6 housekeeping**
    
    - retention jobs
        
    - backup/restore runbook
        
    - observability hardening
        
5. **Final V1 exit validation**
    
    - end-to-end smoke test from price sync to recommendation to execution capture to dashboard verification