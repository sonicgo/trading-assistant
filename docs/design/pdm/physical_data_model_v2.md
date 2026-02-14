# Trading Assistant — Physical Data Model (PDM) v2 Addendum

_Last updated: 2026-02-14 (UTC)_

This is an **addendum** to the existing PDM package. It explicitly covers the “missing step” items:
- Partitions decision for time-series tables
- JSONB field definitions + GIN indexing strategy
- Migration strategy (migrations over ad-hoc DDL)

It does **not** change your core decisions: UUIDv7, UTC `timestamptz`, intraday + EOD prices.

---

## 1) Partitions (time-series tables) — decision + trigger point

### V1 decision
**Do not partition in initial V1** because you expect **thousands** (not millions) of rows, and partitions add:
- migration complexity (table recreation / swap)
- operational overhead (partition management)
- more complex constraints across partitions

### Revisit trigger (explicit)
Introduce partitions when **any** condition is met:
- `price_points` exceeds **5 million** rows, or
- ingest cadence becomes **≤ 1-minute** bars across many listings, or
- “latest price” queries exceed **100ms P95** under normal load

### V1.1 optional partition plan
Partition by month on `as_of` for:
- `ta.price_points`
- optionally `ta.fx_rates`

Approach:
- `PARTITION BY RANGE (as_of)`
- monthly partitions (e.g., `price_points_2026_02`)
- keep uniqueness with partition key included:
  - `UNIQUE(listing_id, as_of, source_id, is_close)`

A ready-to-run **template script** is included as `schema_optional_partitions.sql`.

---

## 2) JSONB fields — canonical shape (V1) and indexing policy

### Design rule
JSONB is used for:
- **payload capture** (audit/reproducibility)
- **extensibility** (avoid schema migrations for minor new fields)

In V1, JSONB is mostly **read** by ID for display/audit, not filtered heavily.  
Therefore: **no default GIN indexes** unless you have stable query patterns.

### JSONB catalog (V1 canonical shapes)

#### `ta.policy_archives.policy_json`
Purpose: machine policy (validated by `manifesto_policy.schema.json`).

Example shape:
```json
{
  "portfolioTargets": [
    {"sleeve":"CORE","weight":0.35,"listingIsin":"IE00...","listingTicker":"VWRP"}
  ],
  "driftThresholds": {"default":0.02,"smallSleeves":0.01},
  "cadence": {"monthlyMaxOrders":2,"quarterlyMaxOrders":3},
  "minTrade": {"amountBase":25},
  "stagedCash": {"enabled":true,"instrumentIsin":"LU123...","sunsetDate":"2027-02-01"}
}
```
Indexing: none in V1.

#### `ta.price_points.quality_flags`
Purpose: DQ diagnostics + freeze provenance.
```json
{
  "stale": false,
  "missing": false,
  "abnormal_jump": false,
  "scale_suspect": false,
  "fx_mismatch": false,
  "notes": ["..."]
}
```
Indexing: optional GIN if you need “find all suspect points”.

#### `ta.task_definitions.module_config`
Purpose: per-task parameters.
```json
{
  "provider": {"priority":["X","Y"]},
  "calc": {"mode":"review_only","include_intraday":true},
  "retention": {"snapshots_months":12}
}
```
Indexing: none in V1.

#### `ta.task_runs.output_summary`
Purpose: small dashboard summary.
```json
{"prices_fetched":42,"alerts_raised":1,"drift_max":0.031}
```
Indexing: none in V1.

#### `ta.run_input_snapshots.snapshot_json`
Purpose: reproducibility blob (kept 12 months).
Top-level keys suggestion:
```json
{
  "as_of":"...",
  "policy_sha256":"...",
  "manifesto_sha256":"...",
  "holdings":[...],
  "cash":{...},
  "prices":[...],
  "fx":[...],
  "constituents":[...]
}
```
Indexing: never (read-by-run_id, then purged).

#### `ta.recommendations.rationale` / `ta.recommendations.constraints_report`
Purpose: explainability + compliance evidence.
Indexing: optional (rare).

#### `ta.notifications.payload`
Purpose: UI polling feed.
Indexing: none (poll by `(user_id, created_at)`).

#### `ta.audit_events.details`
Purpose: immutable audit metadata.
Indexing: none in V1.

---

## 3) GIN indexing strategy (when to add)

Only add a GIN index if:
- you have a stable query that filters on JSON keys, **and**
- it becomes a measurable bottleneck.

Recommended optional indexes (commented into `schema_v2.sql`):
- `price_points_quality_gin` on `ta.price_points USING gin (quality_flags)`
- `recommendations_rationale_gin` on `ta.recommendations USING gin (rationale)`

---

## 4) Migration strategy (V1)

### Recommendation
Use **Alembic** (aligned to FastAPI + SQLAlchemy):
- treat `schema.sql` as a baseline snapshot
- generate an initial Alembic migration matching the baseline
- thereafter: **migrations only** (no manual editing in prod)

Workflow:
1. Create models to match baseline schema
2. `alembic revision --autogenerate -m "baseline"`
3. Review migration for safety
4. `alembic upgrade head`

---

## 5) Output files added
- `schema_v2.sql` (baseline DDL + optional GIN index comments)
- `schema_optional_partitions.sql` (template for future partitioning)
