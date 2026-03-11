# Phase 4 Build Playbook — Deterministic Engine + Recommendations (Manifesto-Aligned)

_Last updated: 2026-03-11 (UTC)_

This playbook turns Phase 4 scope into an implementable build guide using the delivery plan as the governing contract, while aligning the engine behavior to the current investment manifesto.

Phase 4 Outcome:

- You can build a **deterministic RunInputSnapshot** from current portfolio state, trusted prices, and policy.
    
- You can run a **pure recommendation pipeline** that produces the same result for the same input snapshot + policy hash.
    
- You can persist **recommendation batches** with proposed order lines, rationale, triggered rules, and constraint-compliance evidence.
    
- The UI can show a **reviewable recommendation pack** without mutating portfolio state.
    
- Freeze / DQ guardrails remain **hard blockers** for advice generation.
    
- Engine behavior matches the current manifesto, including **monthly default buys**, **quarterly rebalance priorities**, **weekly review-only behavior**, **staged cash parked in CSH2**, **wave triggers**, **sunset deployment**, **min trade**, and **max order-count** rules.
    

---

## 0) Baseline carried forward from Phases 1–3

Backend:

- FastAPI + Pydantic v2
    
- SQLAlchemy 2.x + Alembic
    
- Postgres
    
- Existing auth/session and portfolio tenancy enforcement
    
- Existing market-data ingest, DQ gate, alerts, freeze states, notifications, and task-runs patterns from Phase 2
    
- Existing append-only ledger and incremental `cash_snapshots` / `holding_snapshots` from Phase 3
    

Frontend:

- Next.js (App Router) + TypeScript
    
- TanStack Query
    
- Decimal-string API serialization conventions
    
- Existing portfolio-level UI patterns, frozen-state banner, notifications surface, and authenticated API wrapper
    

Operational baseline carried forward:

- Recommendation generation must reuse the existing **TaskRun + RunInputSnapshot** audit pattern.
    
- Recommendation calculations must read **current snapshots**, not ad hoc ledger replay.
    
- Recommendation generation is advisory only in Phase 4; no ledger mutation happens here.
    
- Manual/API-triggered runs may enqueue jobs; calculation should not block request threads if worker execution already exists in your runtime model.
    

---

## 1) Manifesto-aligned strategy contract (locked for this playbook)

The deterministic engine must implement the following policy behavior.

### 1.1 Strategic invested-asset targets

These are the strategic weights for **long-term invested assets**, excluding the staged cash park.

|Sleeve|Ticker|Strategic target|
|---|---|---|
|core|VWRP|35%|
|semis|SEMI|35%|
|energy|XWES|10%|
|healthcare|XWHS|10%|
|small_cap|WLDS|5%|
|short_gilts|IGL5|5%|

### 1.2 Staged cash park

- Parking instrument: `CSH2`
    
- Initial staged amount reference: `£16000`
    
- CSH2 is **not** part of the strategic invested-asset target weights.
    
- CSH2 is treated as a **separate staged-capital reservoir** that can be deployed only via explicit wave/sunset rules.
    

### 1.3 Review/action cadence

- **Weekly** = review only (`review_only=true`) unless an explicit trigger fires.
    
- **Monthly** = action window for the regular `£500` contribution flow.
    
- **Quarterly** = action window for drift correction / sector-satellite adjustment.
    

### 1.4 Monthly default contribution behavior

Monthly contribution flow defaults to:

- `VWRP` = `£425`
    
- `WLDS` = `£75`
    

Fallback behavior:

- If drift is large enough, the monthly contribution may be redirected using `most_underweight`, while still respecting max-order and min-trade rules.
    

### 1.5 Quarterly rebalance priorities

On quarterly rebalance runs, redirect that month’s contribution to correct drift, prioritising:

1. energy
    
2. healthcare
    
3. semis
    
4. short_gilts
    

If nothing is meaningfully underweight:

- revert to monthly default lines
    

### 1.6 Drift thresholds

- Major sleeves act when absolute drift exceeds **2.0 percentage points**
    
- Minor sleeves act when absolute drift exceeds **1.0 percentage points**
    
- Minor sleeves list:
    
    - `small_cap`
        
    - `short_gilts`
        

### 1.7 Friction / execution constraints

- Monthly default investing uses **≤2 orders**
    
- Quarterly rebalance uses **≤3 orders**
    
- Minimum trade size = **£25** unless part of a wave deployment
    

### 1.8 Wave trigger policy

Wave triggers are enabled.

|Wave|Drawdown trigger|Deployment amount|Allocation rule|
|---|---|---|---|
|A|10%|£8000|most_underweight|
|B|20%|£8000|most_underweight|

### 1.9 Sunset clause

If staged cash remains undeployed, deploy it by date rules:

|Date|Deploy fraction of remaining staged cash|Allocation rule|
|---|---|---|
|2027-02-01|50%|fixed_allocation → core|
|2028-02-01|100%|fixed_allocation → core|

### 1.10 Safety and policy constraints

- Individual stocks are not allowed.
    
- Accumulating-fund policy is on.
    
- Critical DQ alerts block recommendations.
    
- Manual Freeze / Kill Switch halts scheduler activity and advice generation until reset.
    
- Deterministic local rules engine is authoritative; cloud LLM output is advisory only.
    

---

## 2) Definition of Done (Phase 4)

### Backend DoD

- A **RunInputSnapshot builder** exists and captures all inputs required to generate recommendations reproducibly.
    
- A deterministic calculation pipeline exists with modules for:
    
    - valuation in base currency
        
    - invested-asset sleeve weights
        
    - drift detection by policy thresholds
        
    - cadence classification (weekly / monthly / quarterly)
        
    - staged-cash state analysis (`CSH2` and available GBP cash)
        
    - wave trigger evaluation
        
    - sunset clause evaluation
        
    - friction filter (`min_trade`, `max_orders`)
        
    - recommendation assembly + rationale + constraints report
        
- Recommendation persistence exists:
    
    - recommendation batch/header
        
    - recommendation lines
        
- A run can end in a clear status such as:
    
    - `SUCCESS`
        
    - `BLOCKED_FROZEN`
        
    - `BLOCKED_DQ`
        
    - `NO_ACTION`
        
    - `FAILED`
        
- Same `run_input_hash` + same `policy_hash` => same recommendation payload.
    
- Freeze / DQ blockers prevent recommendation creation.
    

### Frontend DoD

- A portfolio-level recommendations screen exists.
    
- The UI can:
    
    - trigger a recommendation run
        
    - list prior recommendation batches
        
    - inspect recommendation lines
        
    - show triggered rules / rationale / constraint compliance
        
    - show action source (`MONTHLY_DEFAULT`, `MONTHLY_REDIRECT`, `QUARTERLY_REBALANCE`, `WAVE_A`, `WAVE_B`, `SUNSET_2027`, `SUNSET_2028`)
        
    - clearly show when a run was blocked by freeze or DQ state
        
- UI does **not** mark anything as executed in Phase 4.
    

### Exit criteria

- Given the same RunInputSnapshot + policy hash, recommendation output is reproducible.
    
- Recommendations show triggered rules and constraint compliance.
    
- Portfolio state is unchanged by recommendation generation alone.
    
- Recommendation output is sufficient input for Phase 5 “mark executed”.
    

---

## 3) Locked assumptions for this playbook

|ID|Assumption|
|---|---|
|P4-A01|Base currency remains **GBP** for V1.|
|P4-A02|Phase 4 reads **cash/holding snapshots** as the current-state book, not replay.|
|P4-A03|Market data used for advice must already have passed the Phase 2 DQ gate; frozen portfolios do not receive advice.|
|P4-A04|Recommendations are **advisory only** in Phase 4; they do not write ledger entries.|
|P4-A05|Determinism is the primary invariant: same input state + same policy hash => same output.|
|P4-A06|Recommendation generation reuses the existing run/audit pattern (`task_runs` + `run_input_snapshots`).|
|P4-A07|The runtime policy source should be the executable policy payload (for example `manifesto_policy.json`), not Markdown parsing at runtime.|
|P4-A08|`manifesto.md` is the human-readable rendering of policy, useful for docs and review but not the execution source.|
|P4-A09|`CSH2` is treated as staged cash / cash-park capital, not as part of strategic invested-asset sleeve weights.|
|P4-A10|Regular monthly contribution flow and staged-cash deployment are separate capital channels and must not be merged implicitly.|

---

## 4) Build order for Phase 4

Build in this order.

### P4A — Deterministic input capture

Goal:

- Build one canonical input object from snapshots, trusted prices, constituent mappings, and normalized policy.
    

### P4B — Pure policy-aware calc modules

Goal:

- Make each calc step testable and deterministic in isolation.
    

### P4C — Recommendation persistence + APIs + UI

Goal:

- Persist and surface explainable recommendation batches and lines.
    

Do not start Phase 5 execution-capture work until P4C is stable.

---

## 5) Canonical concepts
## 5A) Policy allocation mapping (required)

The engine must have a deterministic mapping from tradeable listing to policy role, sleeve, and target weight before any valuation or drift logic runs.

This mapping must distinguish:

- **listing metadata** — global facts such as ticker, ISIN, venue, currency, quote scale
    
- **portfolio/policy allocation metadata** — sleeve code, policy role, target weight, priority order, and whether the listing is part of invested assets or staged cash
    

Do **not** store `target_weight_pct` on the global `listing` table.

Reason:

- target weights are strategy-specific, not exchange-security metadata
    
- the manifesto already defines the target portfolio and the instrument-to-sleeve mapping in policy
    
- Phase 1 already separated listings from sleeve mapping via constituents rather than collapsing them into one entity model.
    
    delivery_plan
    

### Recommended implementation options

Preferred V1 option:

- extend the existing portfolio constituent mapping layer so each active constituent can carry:
    
    - `sleeve_code`
        
    - `policy_role` — `INVESTED_ASSET` or `CASH_PARK`
        
    - `target_weight_pct`
        
    - `priority_rank`
        
    - `is_active`
        

Alternative V1 option:

- add a dedicated table such as `portfolio_policy_allocations`
    

Recommended columns:

- `portfolio_policy_allocation_id (uuid pk)`
    
- `portfolio_id (uuid fk -> portfolio, not null)`
    
- `listing_id (uuid fk -> listing, not null)`
    
- `ticker (text, not null)`
    
- `sleeve_code (text, not null)` — e.g. `core`, `semis`, `energy`, `healthcare`, `small_cap`, `short_gilts`, `cash_park`
    
- `policy_role (text, not null)` — `INVESTED_ASSET`, `CASH_PARK`
    
- `target_weight_pct (numeric(18,8), nullable)` — null for `cash_park` if you keep staged cash outside target sleeves
    
- `priority_rank (int, nullable)`
    
- `policy_hash (text, not null)`
    
- `created_at (timestamptz, default now())`
    

Uniqueness:

- `UNIQUE(portfolio_id, policy_hash, listing_id)`
    

### Required manifesto-aligned mapping for current policy

At minimum the active policy allocation set must represent:

- `VWRP` → `core` → `INVESTED_ASSET` → `35%`
    
- `SEMI` → `semis` → `INVESTED_ASSET` → `35%`
    
- `XWES` → `energy` → `INVESTED_ASSET` → `10%`
    
- `XWHS` → `healthcare` → `INVESTED_ASSET` → `10%`
    
- `WLDS` → `small_cap` → `INVESTED_ASSET` → `5%`
    
- `IGL5` → `short_gilts` → `INVESTED_ASSET` → `5%`
    
- `CSH2` → `cash_park` → `CASH_PARK` → no normal invested-target weight.
    

### RunInputSnapshot requirement

The RunInputSnapshot must persist the fully-resolved allocation map used by the engine, for example:

{  
  "allocation_map": [  
    {  
      "listing_id": "...",  
      "ticker": "VWRP",  
      "sleeve_code": "core",  
      "policy_role": "INVESTED_ASSET",  
      "target_weight_pct": "35.0",  
      "quote_scale": "GBX"  
    },  
    {  
      "listing_id": "...",  
      "ticker": "CSH2",  
      "sleeve_code": "cash_park",  
      "policy_role": "CASH_PARK",  
      "target_weight_pct": null,  
      "quote_scale": "GBX"  
    }  
  ]  
}

This prevents the engine from being “blind” to strategy and makes each run reproducible.

### 5.1 RunInputSnapshot

A RunInputSnapshot is the full reproducible advice input for one recommendation run.

It must capture at minimum:

- portfolio identity
    
- as-of timestamp
    
- cash snapshot state
    
- holding snapshot state
    
- trusted prices used
    
- constituent mapping / sleeve mapping used
    
- normalized executable policy payload
    
- policy hash
    
- freeze state / DQ gate result used in gating
    
- engine version identifier
    
- cadence classification context
    

### 5.2 Policy hash

The policy hash is the stable identifier for the exact strategy/rules configuration applied to the run.

Minimum expectation:

- Canonicalize the policy payload before hashing.
    
- Do not hash pretty-printed text directly if field ordering can vary.
    

### 5.3 Invested assets vs staged cash

Phase 4 must explicitly distinguish between:

- **Invested assets**: VWRP, SEMI, XWES, XWHS, WLDS, IGL5
    
- **Staged cash park**: CSH2
    
- **Uninvested GBP cash**: from `cash_snapshots`
    

Rules:

- Strategic target weights apply only to invested assets.
    
- CSH2 is not a target sleeve for normal drift balancing.
    
- Wave and sunset deployments draw from staged cash capital, not from the normal monthly contribution stream.
    

### 5.4 Recommendation batch vs recommendation line

- **Recommendation batch** = one run result for one portfolio at one as-of point.
    
- **Recommendation line** = one proposed action, normally corresponding to one listing/order candidate.
    

### 5.5 Blocked run vs no-action run

- **Blocked run**: no advice because guardrails prevented it.
    
- **No-action run**: advice engine ran successfully but found no qualifying action above thresholds/constraints.
    

Do not collapse these outcomes into one generic “empty” result.

---

## 6) Data model / persistence

### 6.1 Reuse existing Phase 2 tables

Phase 4 should reuse:

- `task_runs`
    
- `run_input_snapshots`
    
- `notifications` (optional for critical run failures/blockers)
    

Recommended refinement:

- Extend `task_runs.task_kind` to include `RECOMMENDATION_RUN`.
    
- Continue storing a run summary in `task_runs.summary`.
    

### 6.2 Recommended new table: `recommendation_batches`

Intent:

- durable persisted result of one successful or blocked recommendation run
    

Minimum columns:

- `recommendation_batch_id (uuid pk)`
    
- `run_id (uuid fk -> task_runs.run_id, not null)`
    
- `portfolio_id (uuid fk -> portfolio, not null)`
    
- `status (text, not null)` — `SUCCESS`, `BLOCKED_FROZEN`, `BLOCKED_DQ`, `NO_ACTION`, `FAILED`
    
- `as_of (timestamptz, not null)`
    
- `policy_hash (text, not null)`
    
- `policy_version (text, nullable)`
    
- `run_input_hash (text, not null)`
    
- `engine_version (text, not null)`
    
- `run_mode (text, not null)` — `WEEKLY_REVIEW`, `MONTHLY_ACTION`, `QUARTERLY_ACTION`, `MANUAL`
    
- `summary (jsonb, not null)`
    
- `constraints_report (jsonb, nullable)`
    
- `triggered_rules (jsonb, nullable)`
    
- `rationale (jsonb, nullable)`
    
- `created_at (timestamptz, default now())`
    

Recommended indexes:

- `(portfolio_id, created_at desc)`
    
- `(portfolio_id, status, created_at desc)`
    
- `(run_input_hash, policy_hash)`
    

### 6.3 Recommended new table: `recommendation_lines`

Intent:

- one persisted proposed action per order candidate
    

Minimum columns:

- `recommendation_line_id (uuid pk)`
    
- `recommendation_batch_id (uuid fk -> recommendation_batches, not null)`
    
- `portfolio_id (uuid fk -> portfolio, not null)`
    
- `listing_id (uuid fk -> listing, not null)`
    
- `action (text, not null)` — e.g. `BUY`, `SELL`, `HOLD`, `SKIP`
    
- `action_source (text, not null)` — `MONTHLY_DEFAULT`, `MONTHLY_REDIRECT`, `QUARTERLY_REBALANCE`, `WAVE_A`, `WAVE_B`, `SUNSET_2027`, `SUNSET_2028`
    
- `funding_source (text, not null)` — `MONTHLY_CONTRIBUTION`, `STAGED_CASH`, `UNALLOCATED_CASH`, `NONE`
    
- `sleeve_code (text, nullable)`
    
- `current_weight_pct (numeric(18,8), nullable)`
    
- `target_weight_pct (numeric(18,8), nullable)`
    
- `drift_pct (numeric(18,8), nullable)`
    
- `notional_gbp (numeric(28,10), nullable)`
    
- `priority_rank (int, nullable)`
    
- `triggered_rules (jsonb, nullable)`
    
- `constraint_flags (jsonb, nullable)`
    
- `rationale (jsonb, nullable)`
    
- `created_at (timestamptz, default now())`
    

Recommended indexes:

- `(recommendation_batch_id, priority_rank)`
    
- `(portfolio_id, listing_id, created_at desc)`
    

Design notes:

- Persist tradeable lines relationally.
    
- `HOLD` / `SKIP` lines may remain in batch JSON if you want to keep the table concise.
    
- Phase 4 should not generate `SELL` lines unless you explicitly choose to support them for future rebalance logic; current manifesto primarily describes buy-side contribution and staged-cash deployment behavior.
    

### 6.4 Reuse / extend `run_input_snapshots`

For `RECOMMENDATION_RUN`, `input_json` should include:

- `portfolio_id`
    
- `as_of`
    
- `cash_snapshot`
    
- `holding_snapshots`
    
- `price_points_used`
    
- `constituents`
    
- `policy`
    
- `policy_hash`
    
- `engine_version`
    
- `gates`
    
- `run_mode`
    
- `market_drawdown_context`
    
- `staged_cash_state`
    

Example shape:

{  
  "portfolio_id": "...",  
  "as_of": "2026-03-11T16:00:00Z",  
  "cash_snapshot": {...},  
  "holding_snapshots": [...],  
  "price_points_used": [...],  
  "constituents": [...],  
  "policy": {...},  
  "policy_hash": "...",  
  "engine_version": "phase4-v1",  
  "run_mode": "MONTHLY_ACTION",  
  "gates": {  
    "is_frozen": false,  
    "dq_ok": true,  
    "critical_alert_count": 0  
  },  
  "market_drawdown_context": {  
    "reference_method": "configured_index_or_portfolio_peak",  
    "drawdown_pct": "10.23",  
    "wave_a_fired_before": false,  
    "wave_b_fired_before": false  
  },  
  "staged_cash_state": {  
    "cash_park_ticker": "CSH2",  
    "cash_park_value_gbp": "16012.35",  
    "available_cash_gbp": "500.00"  
  }  
}

---

## 7) Deterministic calculation pipeline

Implement the engine as a sequence of small, deterministic modules. Avoid a monolithic `generate_recommendations()` block.

### 7.1 Step 1 — Input assembly / gate evaluation

Responsibilities:

- Load current `cash_snapshots` and `holding_snapshots`
    
- Load latest trusted prices needed for valuation
    
- Load portfolio constituents / sleeve mapping
    
- Load normalized executable policy payload
    
- Determine freeze / DQ gating state
    
- Determine run mode (`WEEKLY_REVIEW`, `MONTHLY_ACTION`, `QUARTERLY_ACTION`, `MANUAL`)
    

Hard-block cases:

- portfolio frozen
    
- any critical alert blocks recommendations
    
- missing trusted prices for required holdings
    
- required policy payload missing / invalid
    

Output:

- fully-populated `RunInputSnapshot`
    
- either proceed or record blocked-run result
    
Additional hard-block case:

- any required listing price is older than **3 days** at run time
    

Required error behavior:

- abort the run before valuation/drift calculation
    
- set recommendation batch status to `BLOCKED_DQ`
    
- include a clear message such as:
    
    - `Stale market data for VWRP; latest trusted price is older than 3 days`
        
- persist this in `task_runs.summary`, `recommendation_batches.summary`, and `constraints_report`
    

Reason:

- recommendation sizing should not be generated from stale valuations
    
- this is consistent with the Phase 2 stale-price safety model, but should also be enforced again at the Phase 4 advice boundary.

### 7.2 Step 2 — Valuation layer

Responsibilities:

- Value each holding in GBP using trusted prices
    
- Normalize quote scale correctly (GBX → GBP where applicable)
    
- Separate values into buckets:
    
    - invested assets
        
    - staged cash park (`CSH2`)
        
    - available GBP cash
        

Important:

- Invested-asset sleeve weights must exclude `CSH2`.
    
- Do not accidentally dilute weights by including staged cash park in invested-target denominator.
    

Output example:

- `invested_value_gbp`
    
- `cash_park_value_gbp`
    
- `available_cash_gbp`
    
- per-sleeve current values and weights
    

### 7.3 Step 3 — Drift engine

Responsibilities:

- Compute sleeve weights against invested assets only
    
- Compare current weights to strategic targets
    
- Apply per-sleeve thresholds:
    
    - major sleeves: 2.0pp
        
    - minor sleeves: 1.0pp
        
- Mark sleeves as:
    
    - underweight actionable
        
    - overweight informational
        
    - within band
        

Output:

- sleeve drift table
    
- ordered underweight list
    
- ordered most-underweight list
    

### 7.4 Step 4 — Cadence classifier

Responsibilities:

- Determine whether this run is:
    
    - weekly review-only
        
    - monthly action
        
    - quarterly action
        
    - manual action
        

Rules:

- Weekly runs are review-only unless an explicit trigger fires.
    
- Monthly runs may allocate the standard monthly contribution flow.
    
- Quarterly runs may redirect that month’s contribution using rebalance priorities.
    

Output:

- `run_mode`
    
- `action_window_open: bool`
    
- `default_action_path`
    

## 7.5A) Projected cash pool (required sizing primitive)

All buy-side recommendation sizing must be done against a deterministic projected cash pool.

For the current manifesto-aligned V1, the projected cash pool is:

`projected_cash_pool = current_available_cash_gbp + monthly_budget_gbp + staged_cash_deployment_gbp`

Where:

- `current_available_cash_gbp` comes from `cash_snapshots`
    
- `monthly_budget_gbp` is normally `500` during monthly/quarterly action windows
    
- `staged_cash_deployment_gbp` is `0` unless a Wave or Sunset rule is firing
    
- `projected_sell_proceeds_gbp = 0` in Phase 4 V1 unless sell-side rebalance is explicitly enabled by future policy
    

Important:

- The current manifesto does **not** define a general sell-down rebalance engine.
    
- Therefore Phase 4 V1 should remain **buy-side only** for ordinary monthly and quarterly logic.
    
- Overweight sleeves may be reported in drift output and rationale, but they do not automatically produce sell lines in V1.
    

### New rule in recommendation writer

If proposed buy notional exceeds the projected cash pool:

- reduce or drop lower-priority buy lines deterministically
    
- record the constraint in `constraints_report`
    
- never imply capital that does not exist
    

### Future-ready extension note

If a future policy enables sell-side rebalance:

1. size sell candidates first
    
2. add theoretical sell proceeds into `projected_cash_pool`
    
3. size buys only from that resulting pool
    
4. preserve deterministic sell-before-buy sequencing in the batch rationale
    

That extension is valid, but it should not be silently assumed in the current Phase 4 scope.
    

### 7.7 Step 7 — Wave trigger evaluator

Responsibilities:

- Evaluate whether Wave A / Wave B should fire based on configured drawdown thresholds.
    
- Determine whether each wave has already been consumed.
    
- If a wave fires, allocate the configured staged-cash amount using `most_underweight`.
    

Rules:

- Wave A trigger: 10% drawdown => deploy £8000
    
- Wave B trigger: 20% drawdown => deploy £8000
    
- Wave deployment is exempt from the ordinary monthly min-trade exception only where the policy allows it.
    
- Engine must not fire the same wave twice.
    

Required design decision for persistence/state:

- Persist wave-consumption state explicitly so repeated runs do not reissue the same wave recommendation forever.
    

Recommended storage options:

- either persist in `recommendation_batches.summary`
    
- or add a dedicated policy-state table for durable trigger consumption
    

Preferred V1 approach:

- add a small durable table such as `policy_trigger_states` keyed by portfolio + trigger code
    

### 7.8 Step 8 — Sunset clause evaluator

Responsibilities:

- Check date-based deployment milestones for remaining staged cash.
    
- If milestone date is reached and staged cash remains, deploy by rule:
    
    - 2027-02-01 => 50% of remaining staged cash to core
        
    - 2028-02-01 => 100% of remaining staged cash to core
        

Rules:

- Sunset deployment funding source = staged cash
    
- Target instrument = core (`VWRP`)
    
- Must not repeatedly refire the same sunset milestone after it has been consumed
    

### 7.9 Step 9 — Friction / order-count filter

Responsibilities:

- Apply:
    
    - minimum trade threshold
        
    - maximum order count
        
    - optional whole-share / broker-lot constraints if already known
        

Behavior:

- Drop or merge small lines below threshold unless policy says otherwise.
    
- Preserve deterministic ranking so the same candidate set always collapses the same way.
    
- When constraints suppress a candidate, record that fact in the constraints report.
    

### 7.10 Step 10 — Recommendation writer

Responsibilities:

- Convert selected candidates into persisted recommendation batch + lines
    
- Record:
    
    - action source
        
    - funding source
        
    - triggered rules
        
    - constraint compliance
        
    - rationale
        

Output categories:

- successful actionable recommendation batch
    
- successful no-action batch
    
- blocked batch
    

---

## 8) Policy-state persistence for one-time triggers

The manifesto introduces trigger types that must not refire indefinitely:

- Wave A
    
- Wave B
    
- Sunset 2027
    
- Sunset 2028
    

Phase 4 therefore needs durable trigger-state persistence.

### 8.1 Recommended table: `policy_trigger_states`

Minimum columns:

- `policy_trigger_state_id (uuid pk)`
    
- `portfolio_id (uuid fk -> portfolio, not null)`
    
- `policy_hash (text, not null)`
    
- `trigger_code (text, not null)` — e.g. `WAVE_A`, `WAVE_B`, `SUNSET_2027`, `SUNSET_2028`
    
- `status (text, not null)` — `AVAILABLE`, `RECOMMENDED`, `CONSUMED`, `CANCELLED`
    
- `first_triggered_at (timestamptz, nullable)`
    
- `last_recommendation_batch_id (uuid fk -> recommendation_batches, nullable)`
    
- `consumed_at (timestamptz, nullable)`
    
- `meta (jsonb, nullable)`
    

Uniqueness:

- `UNIQUE(portfolio_id, policy_hash, trigger_code)`
    

V1 behavior recommendation:

- set to `RECOMMENDED` when a recommendation batch proposes the trigger-based deployment
    
- set to `CONSUMED` in Phase 5 once execution is marked completed
    

This preserves a clean boundary between advice and execution.

---

## 9) Backend build steps (in order)

### Step 1 — Policy loader + canonicalizer

Deliverables:

- `app/services/policy_loader.py`
    
- `app/services/policy_hash.py`
    
- normalized policy DTOs for engine consumption
    

Responsibilities:

- load executable policy payload
    
- validate schema/version
    
- canonicalize policy object
    
- compute stable hash
    
- expose a typed object to calc modules
    

Acceptance:

- same policy payload with different field ordering => same hash
    
- invalid policy payload fails before calculation begins
    

### Step 2 — PDM + Alembic migrations

Deliverables:

- SQLAlchemy models for:
    
    - `recommendation_batches`
        
    - `recommendation_lines`
        
    - `policy_trigger_states` (recommended)
        
- Alembic migrations creating tables, indexes, and constraints
    

Acceptance:

- `alembic upgrade head` succeeds cleanly
    
- uniqueness and foreign-key constraints support idempotent persistence
    

### Step 3 — RunInputSnapshot builder

Deliverables:

- `app/services/recommendation_input.py`
    

Responsibilities:

- load portfolio state from snapshots
    
- load latest trusted prices
    
- load constituent mappings and normalized policy
    
- compute run mode context
    
- evaluate freeze/DQ blockers
    
- persist `task_runs` + `run_input_snapshots`
    

Acceptance:

- same underlying inputs produce the same `run_input_hash`
    
- blocked run still records a useful audit snapshot
    

### Step 4 — Valuation / drift modules

Deliverables:

- `app/services/reco_calc/valuation.py`
    
- `app/services/reco_calc/drift.py`
    

Acceptance:

- CSH2 is excluded from invested-asset sleeve weights
    
- per-sleeve weights and drift numbers are deterministic and testable
    
- GBX/GBP normalization is correct
    

### Step 5 — Cadence / policy modules

Deliverables:

- `app/services/reco_calc/cadence.py`
    
- `app/services/reco_calc/monthly.py`
    
- `app/services/reco_calc/quarterly.py`
    
- `app/services/reco_calc/waves.py`
    
- `app/services/reco_calc/sunset.py`
    
- `app/services/reco_calc/friction.py`
    

Acceptance:

- weekly runs do not emit actionable lines unless an explicit trigger fires
    
- monthly default emits VWRP/WLDS when no redirect applies
    
- quarterly priorities are applied in the configured order
    
- wave/sunset logic is one-time and deterministic
    
- max order count and min trade rules are enforced consistently
    

### Step 6 — Recommendation orchestration service

Deliverables:

- `app/services/recommendation_engine.py`
    

Suggested responsibilities:

- orchestrate all calc modules
    
- assemble selected candidates
    
- create recommendation batch + lines
    
- record summary / rationale / constraints report
    
- update trigger-state persistence when needed
    

Acceptance:

- same `run_input_hash` + same `policy_hash` => same persisted result
    
- blocked/no-action runs are represented clearly
    

### Step 7 — API endpoints

Suggested endpoint surface:

- `POST /api/v1/portfolios/{portfolio_id}/recommendations/runs`
    
- `GET /api/v1/portfolios/{portfolio_id}/recommendations`
    
- `GET /api/v1/portfolios/{portfolio_id}/recommendations/{recommendation_batch_id}`
    
- `GET /api/v1/portfolios/{portfolio_id}/recommendations/{recommendation_batch_id}/lines`
    

Acceptance:

- all endpoints enforce owner tenancy
    
- blocked reasons are returned explicitly
    
- batch detail includes rationale, triggered rules, and constraints report
    

### Step 8 — Frontend viewer

Required pages/components:

- recommendation run trigger control
    
- recommendation history list
    
- recommendation batch detail page
    
- order-line table with action source / funding source / rationale
    
- blocked-run state panel
    

UX rules:

- clearly separate monthly contribution recommendations from staged-cash deployment recommendations
    
- clearly label wave / sunset recommendations
    
- clearly label review-only runs that produced no action
    
- do not imply broker execution has happened
    

---

## 10) Minimum calculation rules to encode explicitly

These rules should be encoded as named rules so they can appear in rationale / audit output.

Suggested rule codes:

- `RUN_BLOCKED_FROZEN`
    
- `RUN_BLOCKED_CRITICAL_ALERT`
    
- `RUN_MODE_WEEKLY_REVIEW`
    
- `RUN_MODE_MONTHLY_ACTION`
    
- `RUN_MODE_QUARTERLY_ACTION`
    
- `MONTHLY_DEFAULT_BUY_VWRP`
    
- `MONTHLY_DEFAULT_BUY_WLDS`
    
- `MONTHLY_REDIRECT_MOST_UNDERWEIGHT`
    
- `QUARTERLY_PRIORITY_ENERGY`
    
- `QUARTERLY_PRIORITY_HEALTHCARE`
    
- `QUARTERLY_PRIORITY_SEMIS`
    
- `QUARTERLY_PRIORITY_SHORT_GILTS`
    
- `QUARTERLY_FALLBACK_MONTHLY_DEFAULTS`
    
- `DRIFT_MAJOR_THRESHOLD_EXCEEDED`
    
- `DRIFT_MINOR_THRESHOLD_EXCEEDED`
    
- `WAVE_A_TRIGGERED`
    
- `WAVE_B_TRIGGERED`
    
- `SUNSET_2027_TRIGGERED`
    
- `SUNSET_2028_TRIGGERED`
    
- `MIN_TRADE_FILTERED`
    
- `MAX_ORDER_LIMIT_APPLIED`

- `RUN_BLOCKED_STALE_PRICE`
    

---

## 11) Testing strategy (minimum)

Create at least:

- `test_run_blocked_when_portfolio_frozen()`
    
- `test_run_blocked_when_critical_alert_exists()`
    
- `test_same_input_and_policy_produce_same_recommendation()`
    
- `test_csh2_excluded_from_invested_asset_weights()`
    
- `test_monthly_default_lines_vwrp_and_wlds()`
    
- `test_monthly_redirect_to_most_underweight_when_drift_large()`
    
- `test_quarterly_priority_order_applied_correctly()`
    
- `test_quarterly_falls_back_to_monthly_defaults_when_no_meaningful_drift()`
    
- `test_major_vs_minor_drift_thresholds()`
    
- `test_wave_a_fires_once_at_10pct_drawdown()`
    
- `test_wave_b_fires_once_at_20pct_drawdown()`
    
- `test_sunset_2027_allocates_50pct_remaining_to_core()`
    
- `test_sunset_2028_allocates_all_remaining_to_core()`
    
- `test_min_trade_filter_removes_small_line()`
    
- `test_max_order_limit_caps_output_deterministically()`
    
- `test_no_action_run_persists_cleanly()`
    
- `test_blocked_run_persists_cleanly()`
    
- `test_recommendation_lines_record_action_source_and_funding_source()`
- `test_run_blocked_when_required_price_is_older_than_3_days()`
    

### Manual smoke script

Create `scripts/phase4_smoke.sh` covering at minimum:

1. ensure portfolio is unfrozen and DQ-clean
    
2. seed holdings + CSH2 + cash
    
3. trigger weekly review run
    
4. verify review-only behavior and no action unless explicit trigger
    
5. trigger monthly run
    
6. verify default VWRP/WLDS lines when no redirect applies
    
7. create an underweight scenario
    
8. verify monthly redirect / quarterly priority behavior
    
9. create a drawdown scenario
    
10. verify Wave A then Wave B behavior
    
11. simulate sunset-date condition
    
12. verify fixed allocation to core
    
13. rerun same input
    
14. verify identical output
    
15. introduce freeze / critical alert
    
16. verify blocked run and no advice
    

---

## 12) Don’t-miss edge cases

- **Do not parse Markdown as runtime policy.** Use the executable policy payload.
    
- **Do not include CSH2 in invested-target sleeve weights.**
    
- **Do not merge staged cash deployment with monthly contribution logic.** They are distinct capital channels.
    
- **Do not let waves or sunset rules refire forever.** Persist trigger state.
    
- **Do not let weekly review-only runs place ordinary monthly buys unless an explicit trigger fires.**
    
- **Do not silently exceed max order counts.** Record the applied constraint.
    
- **Do not silently drop small lines without explaining why.**
    
- **Do not generate recommendations while frozen or under critical DQ block.**
    
- **Do not mutate ledger or snapshots in Phase 4.**
    
- **Do not make cloud LLM commentary authoritative over deterministic rules.**
- 
- **Do not assume Phase 2 DQ alone is enough; Phase 4 must re-check price freshness for the exact input set it is about to use.**
    

---

## 13) Recommended file map

Backend:

- `app/services/policy_loader.py`
    
- `app/services/policy_hash.py`
    
- `app/services/recommendation_input.py`
    
- `app/services/recommendation_engine.py`
    
- `app/services/reco_calc/valuation.py`
    
- `app/services/reco_calc/drift.py`
    
- `app/services/reco_calc/cadence.py`
    
- `app/services/reco_calc/monthly.py`
    
- `app/services/reco_calc/quarterly.py`
    
- `app/services/reco_calc/waves.py`
    
- `app/services/reco_calc/sunset.py`
    
- `app/services/reco_calc/friction.py`
    
- `app/api/v1/endpoints/recommendations.py`
    
- `app/domain/models.py`
    
- `alembic/versions/<revision>_phase4_recommendations.py`
    

Frontend:

- `src/app/portfolios/[id]/recommendations/page.tsx`
    
- `src/components/recommendations/recommendation-history-table.tsx`
    
- `src/components/recommendations/recommendation-detail.tsx`
    
- `src/components/recommendations/recommendation-lines-table.tsx`
    
- `src/hooks/use-recommendations.ts`
    

Scripts / docs:

- `scripts/phase4_smoke.sh`
    
- `implementation/Phase4_build_playbook.md`
    

---

## 14) Explicit Phase 4 deferrals

Keep these out of Phase 4 unless you later re-scope them:

- historical backtesting / UC-90 dry run
    
- general portfolio optimisation solver
    
- multi-currency valuation engine
    
- multi-provider price failover
    
- broker execution integration
    
- automatic execution / order placement
    
- LLM-authored policy changes
    
- rich tax-lot optimisation
    
- as-of historical portfolio reconstruction