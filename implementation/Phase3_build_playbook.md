# Phase 3 Build Playbook — Book of Record (Revised MVP)

_Last updated: 2026-03-10 (UTC)_

This playbook turns Phase 3 scope into an implementable build guide using the delivery plan as the governing contract and carrying forward the execution patterns already established in Phases 1 and 2.

Phase 3 Outcome:

- The **ledger** is the append-only source of truth for cash and position changes.
    
- `holding_snapshots` and `cash_snapshots` are updated **incrementally in the same DB transaction** that writes `ledger_entries`.
    
- “Current state” reads come from **snapshots**, not replay.
    
- Submissions are **idempotent** and safe against duplicate apply.
    
- Phase 3 also supports **CSV position import with delta planning**, so imported positions can be converted into proposed **adjustment / buy / sell / top-up** postings and then applied through the same atomic ledger service.
    

---

## 0) Baseline carried forward from Phases 1 and 2

Backend:

- FastAPI + Pydantic v2
    
- SQLAlchemy 2.x + Alembic
    
- Postgres
    
- Existing auth/session and portfolio tenancy enforcement
    
- Decimal-string API serialization conventions
    
- Existing portfolio / instrument / listing registry from Phase 1
    
- Existing alerts / freeze / notifications / task-runs patterns from Phase 2
    

Frontend:

- Next.js (App Router) + TypeScript
    
- TanStack Query
    
- Existing authenticated API wrapper and portfolio selector patterns
    
- Existing frozen-state banner / notifications surface where relevant
    

Implementation baseline carried forward:

- Portfolio-scoped endpoints already enforce owner tenancy.
    
- Phase 2 freeze semantics already exist and must remain visible in UI/API.
    
- Phase 3 write operations should remain **synchronous and transactional** by default; do not introduce a worker path unless import volume later proves it necessary.
    

---

## 1) Locked product/accounting decisions for this playbook

The following decisions are now treated as **fixed** for Phase 3 build:

|ID|Decision|
|---|---|
|P3-D01|Phase 3 stores **GBP cash impact only** for ledger economics. Do **not** add trade-currency / FX-at-execution modeling in V1.|
|P3-D02|**Negative cash balances are allowed** in V1.|
|P3-D03|**Negative holdings are not allowed** in V1. No short positions.|
|P3-D04|**Trade fees are embedded on BUY / SELL lines**, not modeled as separate trade-fee postings.|
|P3-D05|Corrections are **reversal-only**. No edit-in-place, no delete, no cancel mutation of posted facts.|
|P3-D06|Phase 3 must support **CSV position import** and calculate proposed **adjustment / buy / sell / top-up** postings.|
|P3-D07|Manual ledger posting is still **allowed while the portfolio is frozen**. Freeze blocks advice / recommendation workflows, not book-of-record updates.|
|P3-D08|A single `effective_at` timestamp is sufficient for V1. No separate trade-date / settlement-date pair yet.|
|P3-D09|`holding_snapshots` must carry **quantity**, **book_cost_gbp**, and **avg_cost_gbp**.|

CSV import profile now locked for the first supported export format:

- Phase 3 V1 must support the exact column-based positions export sample provided by the user, including one **cash row** and multiple **holding rows**.
    
- `Date` + `Time` must be normalized into a single `effective_at`.
    
- Non-GBP valuations, FX conversion, and multi-currency import are **out of scope** for this first profile.
    

---

## 2) Definition of Done (Phase 3)

### Backend DoD

- Core persistence implemented + migrated:
    
    - `ledger_batches`
        
    - `ledger_entries`
        
    - `cash_snapshots`
        
    - `holding_snapshots`
        
- Append-only ledger posting service exists and enforces idempotency.
    
- Snapshot updater applies deltas **atomically** in the same DB transaction as ledger-entry creation.
    
- Reversal service exists and posts compensating entries only.
    
- CSV import path exists with **preview → review → apply** semantics.
    
- API supports:
    
    - create ledger batch / entries
        
    - create reversal batch referencing prior entries
        
    - preview CSV import delta plan
        
    - apply approved CSV import plan through the same posting service
        
    - list ledger history
        
    - read current cash snapshot
        
    - read current holding snapshots
        
- Validation blocks negative holdings and invalid reversal/import states.
    
- Duplicate submit does **not** double-apply.
    

### Frontend DoD

- A minimal portfolio ledger UI exists:
    
    - post manual contribution / buy / sell lines
        
    - reverse a prior entry or batch
        
    - inspect ledger history
        
    - inspect current cash and holdings snapshots
        
- A minimal CSV import UI exists:
    
    - upload file
        
    - show proposed delta actions
        
    - allow explicit apply of approved plan
        
- Frozen portfolio state remains visible, but ledger posting/import is still permitted.
    

### Exit criteria

- Writing ledger entries updates snapshots **atomically and consistently**.
    
- Reads use snapshots for current state.
    
- Duplicate submit does not double-apply.
    
- CSV import produces deterministic proposed postings and applies them only after explicit confirmation.
    
- Phase 3 output is sufficient for Phase 4 to build deterministic run inputs from holdings + cash + prices.
    

---

## 3) Scope split for build order

Build in this order.

### P3A — Ledger contract + current-state reads

Goal:

- Define append-only posting contract.
    
- Expose current cash / holding snapshots and ledger history.
    

### P3B — Atomic snapshot mutation

Goal:

- Ensure every accepted ledger post mutates snapshots in the same commit boundary.
    

### P3C — CSV delta-import path

Goal:

- Parse imported position state.
    
- Compare imported state with current snapshots.
    
- Produce proposed adjustment / buy / sell / top-up actions.
    
- Apply only via the same ledger posting service.
    

Do not start Phase 4 calculation logic until P3B is proven solid.

---

## 4) Canonical concepts

### 4.1 Ledger facts vs snapshot projections

- **Ledger** = immutable facts.
    
- **Snapshots** = current-state projections derived incrementally.
    
- Reads for portfolio state must use snapshots, not ledger replay.
    

### 4.2 Manual top-up naming

- User-facing UI can use **Top-up**.
    
- Canonical ledger kind should remain **`CONTRIBUTION`**.
    

### 4.3 Reversal model

- A correction is always a **new posted fact**.
    
- Reversal must reference the original `entry_id` (or all entries in a prior batch).
    
- Reversal produces opposite deltas and a clean audit trail without mutating prior rows.
    

### 4.4 Import delta planning

The CSV import flow is not a shortcut that edits snapshots directly.

Required behavior:

1. Parse imported target state.
    
2. Compare it with current snapshots.
    
3. Generate a proposed posting plan.
    
4. Present that plan to the user.
    
5. Apply it through the same atomic ledger service used by manual posting.
    

---

## 5) Persistence / data model

### 5.1 `ledger_batches`

Intent:

- One user/API submission unit that groups one or more ledger entries into a single atomic posting operation.
    

Minimum columns:

- `batch_id (uuid pk)`
    
- `portfolio_id (uuid fk -> portfolio, not null)`
    
- `submitted_by_user_id (uuid fk -> user, not null)`
    
- `source (text, not null)` — e.g. `UI`, `CSV_IMPORT`, `REVERSAL`
    
- `created_at (timestamptz, default now())`
    
- `note (text, nullable)`
    
- `meta (jsonb, nullable)`
    
- `idempotency_key (text, nullable)`
    

Recommended indexes:

- `(portfolio_id, created_at desc)`
    
- unique partial index on `(portfolio_id, idempotency_key)` where `idempotency_key is not null`
    

---

### 5.2 `ledger_entries`

Intent:

- Append-only economic events that change cash and/or holdings.
    

Recommended canonical `entry_kind` values for Phase 3:

- `CONTRIBUTION`
    
- `BUY`
    
- `SELL`
    
- `ADJUSTMENT`
    
- `REVERSAL`
    

Minimum columns:

- `entry_id (uuid pk)`
    
- `batch_id (uuid fk -> ledger_batches, not null)`
    
- `portfolio_id (uuid fk -> portfolio, not null)`
    
- `entry_kind (text, not null)`
    
- `effective_at (timestamptz, not null)`
    
- `listing_id (uuid fk -> listing, nullable)`
    
- `quantity_delta (numeric(28,10), nullable)` — signed quantity delta; positive buy/add, negative sell/remove
    
- `net_cash_delta_gbp (numeric(28,10), not null)` — signed final GBP cash impact
    
- `fee_gbp (numeric(28,10), nullable)` — allowed only for `BUY` / `SELL`; embedded fee detail
    
- `book_cost_delta_gbp (numeric(28,10), nullable)` — explicit only where needed for `ADJUSTMENT` / `REVERSAL`
    
- `reversal_of_entry_id (uuid fk -> ledger_entries, nullable)`
    
- `created_at (timestamptz, default now())`
    
- `note (text, nullable)`
    
- `meta (jsonb, nullable)`
    

Design notes:

- Do **not** store trade-currency / FX-at-execution detail in Phase 3.
    
- For standard manual `BUY` / `SELL`, `quantity_delta` + `net_cash_delta_gbp` are the core economics.
    
- `fee_gbp` is part of the line item, not a separate ledger posting.
    
- `book_cost_delta_gbp` exists mainly so import reconciliation and reversal can stay explicit when needed.
    

Suggested constraints:

- `CHECK (entry_kind in ('CONTRIBUTION','BUY','SELL','ADJUSTMENT','REVERSAL'))`
    
- `BUY` / `SELL` require `listing_id` and `quantity_delta`
    
- `CONTRIBUTION` must not require `listing_id`
    
- `fee_gbp is null or fee_gbp >= 0`
    
- `reversal_of_entry_id` required only for `REVERSAL`
    

Recommended indexes:

- `(portfolio_id, effective_at desc, created_at desc)`
    
- `(batch_id)`
    
- `(portfolio_id, listing_id, effective_at desc)`
    
- `(reversal_of_entry_id)`
    

Important:

- Ledger entries are **append-only**.
    
- Do not implement update/delete semantics on posted rows.
    

---

### 5.3 `cash_snapshots`

Intent:

- Fast current-state cash read per portfolio.
    

Columns:

- `portfolio_id (uuid pk, fk -> portfolio)`
    
- `balance_gbp (numeric(28,10), not null, default 0)`
    
- `updated_at (timestamptz, not null)`
    
- `last_entry_id (uuid fk -> ledger_entries, nullable)`
    
- `version_no (bigint, not null, default 0)`
    

Notes:

- One row per portfolio.
    
- Negative balances are allowed.
    

---

### 5.4 `holding_snapshots`

Intent:

- Fast current-state holdings read per portfolio/listing.
    

Columns:

- `portfolio_id (uuid fk -> portfolio, not null)`
    
- `listing_id (uuid fk -> listing, not null)`
    
- `quantity (numeric(28,10), not null, default 0)`
    
- `book_cost_gbp (numeric(28,10), not null, default 0)`
    
- `avg_cost_gbp (numeric(28,10), not null, default 0)`
    
- `updated_at (timestamptz, not null)`
    
- `last_entry_id (uuid fk -> ledger_entries, nullable)`
    
- `version_no (bigint, not null, default 0)`
    

Primary key:

- `(portfolio_id, listing_id)`
    

Required invariant:

- `quantity >= 0`
    

Behavior:

- When `quantity = 0`, `book_cost_gbp` and `avg_cost_gbp` must also be `0`.
    

---

## 6) Posting rules and accounting behavior

### 6.1 Transaction contract

Every successful ledger post must behave like this:

1. Validate auth and tenancy.
    
2. Validate request shape and entry-kind rules.
    
3. Open one DB transaction.
    
4. Insert `ledger_batches`.
    
5. Insert all `ledger_entries`.
    
6. Lock/upsert `cash_snapshots` row.
    
7. Lock/upsert relevant `holding_snapshots` rows in deterministic listing order.
    
8. Apply deltas entry by entry in deterministic order.
    
9. Validate resulting state.
    
10. Commit once.
    

If anything fails:

- Roll back the entire transaction.
    
- No partial ledger rows.
    
- No partial snapshot mutations.
    

### 6.2 Lock order

Always mutate state in the same order:

1. `cash_snapshots` row for the portfolio
    
2. `holding_snapshots` rows sorted by `listing_id`
    

### 6.3 Manual posting rules

Use signed deltas consistently.

#### `CONTRIBUTION`

- `net_cash_delta_gbp > 0`
    
- No holding delta
    

#### `BUY`

- `quantity_delta > 0`
    
- `net_cash_delta_gbp < 0`
    
- `fee_gbp >= 0` if present
    
- `book_cost_gbp` increases by **absolute acquisition cost in GBP**
    
- `avg_cost_gbp = new_book_cost_gbp / new_quantity`
    

#### `SELL`

- `quantity_delta < 0`
    
- `net_cash_delta_gbp > 0`
    
- `fee_gbp >= 0` if present
    
- Reject if resulting quantity would go below zero
    
- Remaining `book_cost_gbp` is reduced by **pre-sell average cost × sold quantity**
    
- Remaining `avg_cost_gbp` is recalculated from remaining quantity/book cost
    

#### `ADJUSTMENT`

- Reserved for **import reconciliation** and exceptional administrative correction that cannot be expressed cleanly as simple contribution / buy / sell.
    
- Must remain explicit in UI/history and should not be the default manual action.
    
- Can carry direct `quantity_delta`, `net_cash_delta_gbp`, and `book_cost_delta_gbp` as needed.
    

#### `REVERSAL`

- Must reference a prior posted entry.
    
- Produces equal-and-opposite deltas.
    
- Must not mutate the original row.
    
- Reversal should normally be generated by service code, not hand-crafted by the UI.
    

---

## 7) Validation rules

### 7.1 Structural validation

- `portfolio_id` in path must match ownership context.
    
- `entry_kind` must be supported.
    
- `listing_id` required for `BUY`, `SELL`, and most `ADJUSTMENT` cases.
    
- Decimal precision must be preserved end to end.
    
- `effective_at` required for all posted lines.
    

### 7.2 State-transition validation

- Negative cash is allowed, so do **not** reject a post solely because `balance_gbp < 0` after apply.
    
- Negative holdings are **not** allowed.
    
- `SELL` and relevant `REVERSAL` / `ADJUSTMENT` lines must not drive quantity below zero.
    
- `book_cost_gbp` and `avg_cost_gbp` must stay internally consistent.
    
- If quantity becomes zero, both book cost and average cost must reset to zero.
    

### 7.3 Idempotency validation

- Duplicate `entry_id` must not double-apply.
    
- Duplicate `batch_id` / `idempotency_key` retry with the same payload should return the already-applied result or a clean idempotent success response.
    
- Same IDs with a different payload must return conflict.
    

### 7.4 Reversal validation

- An entry can only be reversed once unless you explicitly support reverse-of-reversal logic.
    
- Reversal must target an existing entry in the same portfolio.
    
- Reversal should fail cleanly if applying the compensating line would violate the no-negative-holdings rule.
    

---

## 8) CSV import pathway

### 8.1 First supported CSV profile (locked)

Phase 3 V1 must support the exact sample structure provided by the user.

Expected headers for the first import profile:

- `Investment`
    
- `Quantity`
    
- `Price`
    
- `Value (£)`
    
- `Cost (£)`
    
- `Change (£)`
    
- `Change (%)`
    
- `Price +/- today (%)`
    
- `Valuation currency`
    
- `Market currency`
    
- `Exchange rate`
    
- `Date`
    
- `Time`
    
- `Portfolio`
    
- `Ticker`
    

Parser rules:

- Header match should be **exact** for this first profile.
    
- Column order may be accepted as-is from the export, but parsing should key by header name, not column position.
    
- Extra unknown columns may be ignored.
    
- Missing required columns must fail preview.
    
- Quoted values must be accepted.
    
- Numeric text may contain thousands separators and must be normalized safely.
    
- Percent columns are informational only and do not drive postings.
    

### 8.2 Row classes

The parser must classify rows into exactly two types.

#### Cash row

Recognize as cash when:

- `Investment = 'Cash GBP'`
    
- `Ticker` is blank or missing
    

For cash row:

- `Value (£)` is the canonical imported **target cash balance**.
    
- `Quantity` may be validated but should be treated as informational.
    
- `Price` should normally be `1`.
    
- `Valuation currency` must be `GBP`.
    
- `Market currency` must be `GBP`.
    
- `Exchange rate` must be `1`.
    

#### Holding row

Recognize as a holding when:

- `Ticker` is populated
    
- `Investment != 'Cash GBP'`
    

For holding rows:

- `Ticker` is the primary external identifier for listing resolution.
    
- `Investment` is descriptive only and should be retained in preview metadata.
    
- `Quantity` is the imported target holding quantity.
    
- `Cost (£)` is the imported target book cost in GBP.
    
- `Value (£)` is informational market valuation only; do not use it as ledger cost.
    
- `Price` is informational market price only; do not treat it as execution price.
    
- `Valuation currency` must be `GBP` for this profile.
    
- `Market currency` must be `GBP` for this profile.
    
- `Exchange rate` must be `1` for this profile.
    

### 8.3 Required columns by row type

Globally required columns for this profile:

- `Investment`
    
- `Quantity`
    
- `Value (£)`
    
- `Cost (£)`
    
- `Date`
    
- `Time`
    
- `Portfolio`
    
- `Valuation currency`
    
- `Market currency`
    
- `Exchange rate`
    

Conditionally required:

- `Ticker` required for holding rows
    

Informational-only columns:

- `Price`
    
- `Change (£)`
    
- `Change (%)`
    
- `Price +/- today (%)`
    

### 8.4 Datetime normalization

Import file contains separate `Date` and `Time` columns.

Required behavior:

- Combine them into one import timestamp.
    
- Parse the sample format `10-Mar-26` + `17:07`.
    
- Normalize to one canonical `effective_at` value for every generated posting in the import batch.
    
- Interpret this timestamp in the application timezone for this environment (`Europe/London`) before storing canonical UTC in the database.
    

If parsing fails:

- Preview must fail with row/file level validation details.
    

### 8.5 Portfolio matching

Import is always executed for a selected `portfolio_id` from the route / screen context.

Required behavior:

- The target portfolio is determined by where the user initiates the upload, not by resolving CSV `Portfolio` text to an internal portfolio record.
    
- `Portfolio` values in the CSV must be uniform when present.
    
- CSV `Portfolio` is informational and may be used only as an optional consistency check against the currently opened portfolio screen.
    
- Mixed portfolio values in one file must fail preview.
    
- The server must never use CSV `Portfolio` as the primary lookup key for `portfolio_id`.
    

Implementation note:

- Preferred V1 pattern is `POST /portfolios/{portfolio_id}/ledger/imports/preview` so the route already carries the target portfolio context.
    
- UI should display the selected portfolio prominently before upload and in the preview summary.
    
- A mismatch between CSV `Portfolio` and the selected portfolio label should produce a clear preview warning or blocking validation, controlled by configuration; it must not remap the upload to another portfolio.
    

### 8.6 Listing resolution

Required resolution order for holding rows:

1. Match by `Ticker`
    
2. If needed, optionally fall back to parsing `(LSE:XXXX)` from `Investment` for diagnostics only
    

Required behavior:

- Unresolved ticker => row-level preview error
    
- Duplicate ticker mapping within the platform registry => preview error
    
- Holdings must resolve to existing `listing_id`; Phase 3 import must not create new listings automatically
    

### 8.7 Currency and FX guardrails

Because Phase 3 is GBP-cash-only:

- `Valuation currency` must be `GBP`
    
- `Market currency` must be `GBP`
    
- `Exchange rate` must normalize to `1`
    

If any row violates this:

- preview must fail for this profile
    
- no implicit FX conversion is allowed in V1
    

### 8.8 Import normalization model

After parsing, the import service should normalize the file into an internal target-state structure:

{  
  "portfolio_label": "SIPP",  
  "effective_at": "2026-03-10T17:07:00Z",  
  "cash_target_gbp": "637.68",  
  "holdings": [  
    {  
      "ticker": "VWRP",  
      "listing_id": "...",  
      "target_quantity": "140",  
      "target_book_cost_gbp": "17942.36",  
      "investment_name": "Vanguard FTSE All-World ETF USD Acc GBP (LSE:VWRP)"  
    }  
  ]  
}

Notes:

- `Value (£)` and `Price` should be retained in preview metadata for operator visibility, but they do not determine ledger economics.
    
- The planner works from **target quantity**, **target book cost**, and **target cash balance**.
    

### 8.9 Delta-planning rules

The import flow is not allowed to mutate snapshots directly.

Required flow:

1. Upload CSV.
    
2. Parse and normalize rows.
    
3. Validate portfolio match and listing resolution.
    
4. Read current snapshots.
    
5. Compare imported target state with current snapshots.
    
6. Generate a deterministic preview plan.
    
7. Apply only after explicit confirmation.
    
8. Materialize approved lines through the standard ledger posting service.
    

Planner outputs may include:

- `TOP_UP` (materialized as `CONTRIBUTION`)
    
- `BUY`
    
- `SELL`
    
- `ADJUSTMENT`
    

### 8.10 How synthetic import postings should behave

Import-generated trade lines are **reconciliation postings**, not historical execution records.

This is important because the CSV gives current position state, not the full execution history.

Required modeling:

- Synthetic `BUY` lines use:
    
    - `quantity_delta > 0`
        
    - `net_cash_delta_gbp = -book_cost_delta_gbp`
        
    - `fee_gbp = 0`
        
- Synthetic `SELL` lines use:
    
    - `quantity_delta < 0`
        
    - cash credit based on relieved book cost, not market value
        
    - `fee_gbp = 0`
        
- `ADJUSTMENT` is used where quantity/cost reconciliation cannot be represented cleanly by pure buy/sell logic.
    

This ensures:

- holdings snapshot lands on the imported quantity and book cost
    
- import does not invent gains/losses from market valuation fields
    
- cash is reconciled separately and explicitly
    

### 8.11 Concrete planning algorithm for V1

For each holding row, compare current snapshot vs imported target.

Definitions:

- `current_qty`
    
- `current_book_cost`
    
- `target_qty`
    
- `target_book_cost`
    
- `delta_qty = target_qty - current_qty`
    
- `delta_cost = target_book_cost - current_book_cost`
    

Planning rules:

#### Case A — New or increased holding

If `delta_qty > 0`:

- propose a synthetic `BUY`
    
- set `quantity_delta = delta_qty`
    
- set `book_cost_delta_gbp = delta_cost` when `delta_cost >= 0`
    
- set `net_cash_delta_gbp = -delta_cost`
    
- if `delta_cost < 0`, fall back to `ADJUSTMENT` and flag operator warning
    

#### Case B — Reduced holding

If `delta_qty < 0`:

- first compute the expected relieved book cost using current average cost method
    
- if target residual book cost matches the average-cost reduction within tolerance, propose `SELL`
    
- otherwise propose `SELL` for quantity reduction plus `ADJUSTMENT` for remaining cost-basis mismatch, or a single `ADJUSTMENT` if cleaner
    

#### Case C — Quantity unchanged, cost changed

If `delta_qty = 0` and `delta_cost != 0`:

- propose `ADJUSTMENT`
    

#### Case D — Quantity and cost unchanged

If both unchanged:

- propose no holding action
    

### 8.12 Cash reconciliation rule

After all holding actions are planned:

1. Simulate resulting cash from current cash snapshot plus planned holding actions.
    
2. Compare to imported `cash_target_gbp` from the cash row.
    
3. Reconcile the remaining cash delta as follows:
    
    - if remaining delta is positive => propose `TOP_UP` (materialized as `CONTRIBUTION`)
        
    - if remaining delta is negative => propose cash-only `ADJUSTMENT`
        
    - if zero => no cash action
        

This preserves a transparent audit trail and avoids inventing a separate withdrawal type in Phase 3.

### 8.13 Import preview contract

Suggested endpoint:

- `POST /api/v1/portfolios/{portfolio_id}/ledger/imports/preview`
    

Suggested request shape:

- multipart file upload, or JSON wrapper with base64/file reference
    
- include:
    
    - `csv_profile = "positions_gbp_v1"`
        
    - optional `idempotency_key`
        

Suggested response contract:

{  
  "csv_profile": "positions_gbp_v1",  
  "source_file_sha256": "...",  
  "portfolio_id": "...",  
  "portfolio_label": "SIPP",  
  "effective_at": "2026-03-10T17:07:00Z",  
  "basis": {  
    "cash_snapshot_version": 12,  
    "holding_versions": {  
      "listing_id_1": 4,  
      "listing_id_2": 7  
    }  
  },  
  "summary": {  
    "holding_rows": 7,  
    "cash_rows": 1,  
    "errors": 0,  
    "warnings": 0  
  },  
  "normalized_targets": {  
    "cash_target_gbp": "637.68",  
    "holdings": []  
  },  
  "proposed_entries": [  
    {  
      "entry_kind": "BUY",  
      "listing_id": "...",  
      "quantity_delta": "140",  
      "net_cash_delta_gbp": "-17942.36",  
      "fee_gbp": "0",  
      "book_cost_delta_gbp": "17942.36"  
    },  
    {  
      "entry_kind": "CONTRIBUTION",  
      "net_cash_delta_gbp": "18600.04"  
    }  
  ],  
  "warnings": [],  
  "errors": [],  
  "plan_hash": "..."  
}

Required behavior:

- Preview must return row-level and file-level validation issues.
    
- Preview must include the snapshot basis versions used to compute the plan.
    
- Preview must be deterministic for the same file + same snapshot state.
    

### 8.14 Import apply contract

Suggested endpoint:

- `POST /api/v1/portfolios/{portfolio_id}/ledger/imports/apply`
    

Suggested request shape:

{  
  "csv_profile": "positions_gbp_v1",  
  "plan_hash": "...",  
  "source_file_sha256": "...",  
  "effective_at": "2026-03-10T17:07:00Z",  
  "basis": {  
    "cash_snapshot_version": 12,  
    "holding_versions": {  
      "listing_id_1": 4,  
      "listing_id_2": 7  
    }  
  },  
  "proposed_entries": [...],  
  "idempotency_key": "..."  
}

Required behavior:

- Server must validate that current snapshots still match the preview basis.
    
- If state drift occurred since preview, return `409 Conflict` and require a fresh preview.
    
- Apply path must transform approved plan into a normal `ledger_batches` post with `source = 'CSV_IMPORT'`.
    
- Apply must use the same transaction, idempotency, and reversal rules as manual posting.
    

### 8.15 Import-specific validation and error cases

Preview must fail cleanly for at least these cases:

- required header missing
    
- more than one cash row
    
- no cash row present
    
- mixed portfolio labels in one file
    
- unresolved ticker
    
- duplicate ticker rows in the same file unless explicitly aggregated first
    
- non-GBP valuation/market currency
    
- `Exchange rate != 1`
    
- malformed number field
    
- malformed date/time field
    
- negative imported quantity
    
- negative imported cost on a holding row
    
- imported target state that would require negative holdings after apply
    

Warnings may be used for:

- cost-basis reconciliation requiring `ADJUSTMENT`
    
- imported price/value fields inconsistent with quantity × price due to rounding
    
- informational name/ticker mismatch where ticker still resolves uniquely
    

### 8.16 Guardrails

- Import must not create listings.
    
- Import must not mutate snapshots directly.
    
- Import must not bypass idempotency.
    
- Import must not bypass reversal-only accounting.
    
- Import preview/apply must remain synchronous in V1.
    

## 9) Backend build steps (in order)

### Step 1 — PDM + Alembic migrations

Deliverables:

- SQLAlchemy models for:
    
    - `ledger_batches`
        
    - `ledger_entries`
        
    - `cash_snapshots`
        
    - `holding_snapshots`
        
- Alembic migration(s) creating tables, indexes, and constraints
    

Acceptance:

- `alembic upgrade head` succeeds cleanly
    
- Snapshot invariants are enforced by code and, where practical, DB constraints
    
- Basic local transaction test passes
    

Suggested files:

- `app/domain/models.py`
    
- `alembic/versions/<revision>_phase3_ledger_snapshots_v2.py`
    

---

### Step 2 — Pydantic schemas / API contracts

Deliverables:

- `app/schemas/ledger.py`
    
- Request/response models for:
    
    - batch create
        
    - reversal create
        
    - ledger-entry read
        
    - cash snapshot read
        
    - holding snapshot read
        
    - CSV import preview
        
    - CSV import apply
        

Acceptance:

- OpenAPI exposes clean batch and import contracts
    
- Decimal values serialize as strings
    
- Invalid shapes fail with clean 4xx responses
    

---

### Step 3 — Ledger posting service

Deliverables:

- `app/services/ledger_posting.py`
    
- One orchestration function responsible for:
    
    - validation
        
    - transaction handling
        
    - ledger insert
        
    - snapshot mutation
        
    - idempotency handling
        
    - reversal generation
        

Suggested signatures:

def post_ledger_batch(  
    *,  
    db,  
    portfolio_id: str,  
    submitted_by_user_id: str,  
    batch_request: LedgerBatchCreateRequest,  
) -> LedgerBatchPostResult:  
    ...  
  
  
def reverse_ledger_entries(  
    *,  
    db,  
    portfolio_id: str,  
    submitted_by_user_id: str,  
    reversal_request: LedgerReversalRequest,  
) -> LedgerBatchPostResult:  
    ...

Acceptance:

- One valid batch produces one atomic commit
    
- Invalid second line in a batch causes full rollback
    
- Duplicate retry does not double-apply
    
- Reversal creates compensating rows only
    

---

### Step 4 — Snapshot mutation helpers

Deliverables:

- `app/services/snapshots.py`
    
- Deterministic helpers such as:
    
    - `apply_cash_delta(...)`
        
    - `apply_holding_delta(...)`
        
    - `recalculate_avg_cost(...)`
        
    - `apply_reversal(...)`
        

Acceptance:

- Snapshot mutation is testable outside HTTP
    
- Quantity / book cost / average cost remain consistent after buy/sell/reversal
    

---

### Step 5 — CSV import planner

Deliverables:

- `app/services/ledger_import.py`
    
- First concrete import profile: `positions_gbp_v1`
    
- Header-based parser and normalization logic for the real sample CSV format
    
- Cash-row / holding-row classification
    
- Preview planner that compares imported state to current snapshots
    
- Apply path that converts approved plan into standard ledger batch request(s)
    
- Basis-version drift checks between preview and apply
    

Acceptance:

- Same file + same snapshot state => same preview plan
    
- Parser accepts quoted numeric fields with commas
    
- Cash row is recognized correctly and mapped to `cash_target_gbp`
    
- Holding rows resolve by ticker to existing listings
    
- Non-GBP or FX-bearing rows fail cleanly in V1
    
- Apply path uses standard posting service, not a shortcut
    
- Import errors are row-specific and readable
    

---

### Step 6 — API endpoints

Suggested endpoint surface:

- `POST /api/v1/portfolios/{portfolio_id}/ledger/batches`
    
- `POST /api/v1/portfolios/{portfolio_id}/ledger/reversals`
    
- `GET /api/v1/portfolios/{portfolio_id}/ledger/batches?limit=&offset=`
    
- `GET /api/v1/portfolios/{portfolio_id}/ledger/entries?limit=&offset=&entry_kind=`
    
- `GET /api/v1/portfolios/{portfolio_id}/snapshots/cash`
    
- `GET /api/v1/portfolios/{portfolio_id}/snapshots/holdings`
    
- `POST /api/v1/portfolios/{portfolio_id}/ledger/imports/preview`
    
- `POST /api/v1/portfolios/{portfolio_id}/ledger/imports/apply`
    

Acceptance:

- All endpoints enforce owner tenancy
    
- Preview returns normalized targets, proposed entries, row/file validation results, basis versions, and `plan_hash`
    
- Apply rejects stale preview basis with `409 Conflict`
    
- Current-state reads come from snapshots, not replay
    
- Frozen portfolios still allow ledger posting/import endpoints
    

Suggested files:

- `app/api/v1/endpoints/ledger.py`
    
- `app/api/v1/endpoints/snapshots.py`
    
- `app/api/v1/endpoints/ledger_import.py`
    

---

## 10) Frontend notes

Required pages/components:

- Portfolio ledger page
    
- Current-state cards for cash + holdings
    
- Ledger history table
    
- Reversal action from history row or batch detail
    
- CSV import preview/apply page or modal
    

Recommended hooks:

- `useLedgerBatches(portfolioId, ...)`
    
- `useLedgerEntries(portfolioId, ...)`
    
- `useCashSnapshot(portfolioId)`
    
- `useHoldingSnapshots(portfolioId)`
    
- `useCreateLedgerBatch(portfolioId)`
    
- `useReverseLedgerEntries(portfolioId)`
    
- `usePreviewLedgerImport(portfolioId)`
    
- `useApplyLedgerImport(portfolioId)`
    

UX rules:

- Continue using decimal strings; no JS float arithmetic for money.
    
- Avoid optimistic mutation for posting/import apply.
    
- Show freeze banner but do not block ledger forms.
    
- Make reversal-only correction model explicit in UI copy.
    
- Clearly label `ADJUSTMENT` lines so they do not look like normal trade capture.
    

---

## 11) Testing strategy (minimum)

### Automated tests

Create at least:

- `test_contribution_updates_cash_snapshot_atomically()`
    
- `test_buy_updates_cash_qty_book_cost_avg_cost()`
    
- `test_sell_updates_cash_qty_book_cost_avg_cost()`
    
- `test_negative_cash_is_allowed()`
    
- `test_sell_rejected_when_quantity_would_go_negative()`
    
- `test_duplicate_entry_id_does_not_double_apply()`
    
- `test_batch_rolls_back_if_second_entry_invalid()`
    
- `test_reversal_creates_compensating_entries_only()`
    
- `test_reversal_does_not_mutate_original_entry()`
    
- `test_snapshot_reads_do_not_replay_ledger()`
    
- `test_portfolio_tenancy_forbidden_for_ledger_endpoints()`
    
- `test_import_preview_is_deterministic()`
    
- `test_import_apply_uses_standard_posting_service()`
    
- `test_frozen_portfolio_still_allows_manual_ledger_posting()`
    

### Manual smoke script

Create `scripts/phase3_smoke.sh` covering at minimum:

1. login
    
2. create/get portfolio
    
3. post contribution batch
    
4. verify cash snapshot increased
    
5. post buy batch
    
6. verify holding quantity / book cost / avg cost updated
    
7. post sell batch
    
8. verify quantity reduced and remaining avg cost recalculated
    
9. post duplicate batch with same `entry_id`
    
10. verify no double-apply
    
11. reverse prior entry
    
12. verify compensating effect applied
    
13. upload CSV preview
    
14. review proposed actions
    
15. apply import plan
    
16. verify snapshots match expected state
    
17. post invalid sell that would go negative
    
18. verify rollback and unchanged snapshots
    

---

## 12) Don’t-miss edge cases

- **Append-only means append-only**: no silent update/delete of posted facts.
    
- **Atomicity is the feature**: ledger rows and snapshots must never diverge.
    
- **Negative cash is allowed, negative holdings are not**: code this explicitly.
    
- **Book cost discipline matters**: snapshot cost basis must remain internally consistent after sell/reversal/import.
    
- **Reversal is not delete**: preserve the original row and add a compensating row.
    
- **Import is not a backdoor**: it must pass through the same posting service.
    
- **Freeze interaction must stay explicit**: frozen blocks advice, not book-of-record maintenance.
    
- **Do not accidentally add trade-currency/FX complexity** into Phase 3.
    
- **Do not reintroduce replay** into current-state read paths.
    

---

## 13) Recommended file map

Backend:

- `app/schemas/ledger.py`
    
- `app/services/ledger_posting.py`
    
- `app/services/snapshots.py`
    
- `app/services/ledger_import.py`
    
- `app/api/v1/endpoints/ledger.py`
    
- `app/api/v1/endpoints/snapshots.py`
    
- `app/api/v1/endpoints/ledger_import.py`
    
- `app/domain/models.py`
    
- `alembic/versions/<revision>_phase3_ledger_snapshots_v2.py`
    

Frontend:

- `src/app/portfolios/[id]/ledger/page.tsx`
    
- `src/components/ledger/ledger-history-table.tsx`
    
- `src/components/ledger/ledger-entry-form.tsx`
    
- `src/components/ledger/ledger-import-preview.tsx`
    
- `src/hooks/use-ledger.ts`
    
- `src/hooks/use-snapshots.ts`
    
- `src/hooks/use-ledger-import.ts`
    

Scripts / docs:

- `scripts/phase3_smoke.sh`
    
- `implementation/Phase3_build_playbook.md`
    

---

## 14) Explicit Phase 3 deferrals

Keep these out of Phase 3 unless you later re-scope them:

- general replay / rebuild-snapshots tool
    
- multi-currency cash ledger
    
- trade-currency / FX-at-execution storage
    
- lot matching / tax lots
    
- rich realized / unrealized P&L engine
    
- external notification channels for ledger operations
    
- historical as-of portfolio reconstruction
    
- high-volume async import orchestration