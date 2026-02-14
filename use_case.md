# Trading Assistant Agent — Use Cases (V1 + V2)

Assumption: **One functional user type**, but the platform supports **multiple user accounts** with authentication (**no RBAC**). All authenticated users have the same capabilities. “Admin / operator” is a **bootstrap capability** (initial seeding + user lifecycle), not a full RBAC model.

---

## Actors

- **User (admin / operator)**: bootstrap system; create/disable users; password resets. (No RBAC in-app.)
- **User (primary)**: authenticated user; full functional capability (same as any other user).
- **System Scheduler**: triggers periodic tasks.
- **Market Data Provider**: price/FX API(s).
- **Cloud LLM Provider**: sanity checks + advisory commentary (non-authoritative).
- **Notification Channel**: email / Telegram / Web Push.

---

# V1 Use Cases (in-scope)

## Access and authentication

### UC-01 — User sign-in
- **Goal**: log in securely to use UI.
- **Preconditions**: user account exists in local DB.
- **Main flow**: enter credentials → validate → issue session/token.
- **Postconditions**: authenticated session established.
- **Exceptions**: invalid credentials; account locked.

### UC-02 — User sign-out
- **Goal**: end session.
- **Main flow**: revoke session/token.
- **Postconditions**: session revoked; user is no longer authenticated.

### UC-03 — User management (admin / operator)
- **Goal**: create/disable users without RBAC complexity.
- **Preconditions**: “Bootstrap Admin” via env/seeding, then manage users in DB.
- **Main flow**: create user → set password reset link or initial password → disable user when needed.
- **Postconditions**: user accounts reflect current allowed users.

---

## Instrument, monitoring, and holdings management

### UC-10 — Maintain instrument registry
- **Goal**: define what instruments exist in the system.
- **Data**: ticker, ISIN (primary key), exchange, currency, sleeve, price source preference.
- **Main flow**: add/edit instrument → validate (ticker/ISIN format) → save.

### UC-11 — Configure monitoring list
- **Goal**: select which instruments are actively watched and for which calculations.
- **Main flow**: toggle monitored status → assign to portfolios/sleeves → save.

### UC-12 — Maintain holdings (positions)
- **Goal**: record current units per instrument (per portfolio/account).
- **Main flow**: add holding → set units → save.
- **Postconditions**: portfolio valuations reflect holdings.

### UC-13 — Maintain trade ledger (buys/sells)
- **Goal**: record every trade with price, fees, timestamps; derive cost basis.
- **Main flow**: log **batch** of trades (BUY/SELL, units, price, fees, date/time) → recompute:
  - units
  - average cost (or FIFO if configured later)
  - realized/unrealized P/L (optional)
- **Postconditions**: holdings updated; audit trail preserved.

### UC-14 — Maintain cash balances
- **Goal**: track cash and “cash park” instrument (e.g., CSH2) separately.
- **Main flow**: set cash balance → record transfers/contributions → record staged-cash allocation.

### UC-15 — Corporate actions adjustment (non-trade events)
- **Goal**: adjust holdings for stock splits/mergers/ISIN changes without creating BUY/SELL events in the ledger.
- **Main flow**: select instrument → type (Split/Merge/ISIN change) → ratio/mapping (e.g., 10:1) → system updates units & price history consistently.

### UC-16 — Excess Reportable Income (Optional; not applicable to SIPP)
- **Note**: tracked as a placeholder only; **out of scope for V1 implementation** unless explicitly needed.

---

## Market data ingestion

### UC-20 — Price refresh (manual)
- **Goal**: pull latest prices/FX on demand.
- **Main flow**: user clicks refresh → fetch prices → store with timestamp/source → flag anomalies.
- **Exceptions**: API unavailable; rate-limited; partial results.

### UC-21 — Price refresh (scheduled)
- **Goal**: ingest prices automatically on a schedule.
- **Actor**: System Scheduler.
- **Main flow**: run job → fetch prices for monitored list → store → produce data-quality report.
- **Postconditions**: latest close/live data available for calculations.

### UC-22 — Data quality handling (blocks advice when unsafe)
- **Goal**: prevent bad prices from driving bad advice.
- **Rules**:
  - stale price detection
  - missing price detection
  - abnormal jump thresholds
  - market-closed awareness
  - **Unit Consistency Check**:
    - If `(Current Price × Units)` differs from `(Previous Value)` by **> 50%** in one day **without any logged trade/corporate action**, then **FREEZE (UC-80)**.
    - Purpose: catch **GBX vs GBP (100×)** or currency mis-reporting errors.
- **Outputs**: warnings; “advice blocked” if data quality fails; may trigger UC-80 freeze.

### UC-23 — FX awareness (sub-routine of UC-22)
- **Goal**: detect currency mismatch and quote-scale errors.
- **Why**: a common API bug is reporting a GBX-quoted LSE instrument in GBP (or vice versa), or mixing USD/GBP.
- **Rule of thumb**: validate `Price ≈ Previous Close × 100` (pence vs pounds) **or** alert immediately; escalate to UC-80 if severe.

---

## Manifesto (strategy) and policy management

### UC-30 — View Manifesto
- **Goal**: see current strategy principles + rules.
- **Content**: human-readable markdown + machine-readable policy.

### UC-31 — Edit Manifesto (versioned)
- **Goal**: update principles and rules safely.
- **Main flow**: edit draft → validate policy schema → save new version.
- **Postconditions**: new Manifesto version exists as Draft.

### UC-32 — Approve Manifesto
- **Goal**: make a version active for all tasks.
- **Main flow**: promote Draft → Approved; optionally retire old version.
- **Postconditions**: tasks default to latest Approved version.

### UC-33 — Policy schema validation
- **Goal**: ensure rules are machine-executable.
- **Examples**: target weights sum to 100%; thresholds valid; no forbidden instruments; max-trade limits present.

---

## Scheduled tasks and calculations

### UC-40 — Define scheduled tasks
- **Goal**: create multiple jobs with different rules and schedules.
- **Examples**:
  - hourly price updates
  - weekly review-only
  - monthly contribution allocation
  - quarterly rebalance
  - drift alerts
  - Wave A / Wave B triggers
  - sunset clause date actions
- **Main flow**: create task → choose schedule (cron/RRULE) → select calculation module(s) → select Manifesto version (or “latest approved”) → enable.

### UC-41 — Run calculation task (scheduled)
- **Actor**: System Scheduler.
- **Main flow**: load holdings + latest prices → compute weights/drift/drawdown → evaluate triggers → produce recommendation or “no action” → notify if configured.

### UC-42 — Run calculation task (manual)
- **Goal**: run a task on demand (e.g., before placing Monday orders).

---

## Judge and advise

### UC-50 — Generate recommendation (local rules engine)
- **Goal**: output exact actions, e.g., “Buy £125 of XWES”, while enforcing constraints.
- **Inputs**: holdings, prices, Manifesto rules, constraints (e.g., max orders).
- **Outputs**:
  - order list (ticker/ISIN, £ amount, estimated units, rationale)
  - expected post-trade weights
  - constraints compliance (max orders, no individual stocks, etc.)
  - **Friction Filter Logic**: If suggested trade value `< £X` (e.g., £25), suppress recommendation unless part of a larger Wave deployment.

### UC-51 — Review recommendation in UI
- **Goal**: see details and rationale before acting.
- **Main flow**: open recommendation → inspect triggered rules → inspect calculations → accept/ignore.

### UC-52 — Mark trades as executed
- **Goal**: after placing orders in AJ Bell, record execution details.
- **Main flow**: mark executed → enter fill price/fees/time → update ledger/holdings → close recommendation.
- **Postconditions**: portfolio state is accurate and auditable.

---

## Cloud LLM sanity-check (cloud AI advisory)

### UC-60 — Request cloud LLM review on trading plan
- **Goal**: second opinion on macro/context and rule compliance.
- **Main flow**: send decision packet (rules + computed state + proposed orders) → receive PASS/WARN/FAIL + notes.
- **Postconditions**: verdict stored with the recommendation.
- **Constraints**: LLM is reviewer only; cannot change rules automatically.

### UC-61 — Request cloud LLM review on Manifesto
- **Goal**: second opinion on Manifesto draft (principles + machine policy).
- **Main flow**: send Manifesto + diff/suggested changes → receive PASS/WARN/FAIL + notes.
- **Postconditions**: verdict stored with the recommendation.
- **Constraints**: LLM is advisor only; cannot change Manifesto automatically.

### UC-62 — Review recommended Manifesto changes in UI
- **Goal**: see details and rationale before acting.
- **Main flow**: open recommendation → accept/ignore.

### UC-63 — Apply accepted Manifesto changes
- **Goal**: commit updates with audit trail.
- **Main flow**: mark accepted → backup previous version → update Manifesto → close recommendation.
- **Postconditions**: Manifesto is accurate and auditable.

### UC-64 — LLM safety guardrails
- **Goal**: prevent the LLM from becoming an unbounded trading brain.
- **Rules**: deterministic engine remains source of truth; LLM output is advisory; require user confirmation for any change.

---

## Notifications and reporting

### UC-70 — Notifications
- **Goal**: alert when action is needed or triggers fire.
- **Events**: drift breach, wave trigger, sunset clause due, data quality failure, task completion, freeze.
- **Channels**: email / Telegram / Slack / Web Push.

### UC-71 — Reports / dashboard
- **Goal**: view portfolio value, sleeve weights, drift history, drawdown, and prior recommendations.
- **Outputs**: charts/tables; export CSV (optional).

---

## Safety controls

### UC-80 — Emergency “Kill Switch” / “Freeze”
- **Why**: if data provider misreports prices (e.g., 100× error), the agent might generate dangerous or spammy recommendations.
- **Goal**: stop scheduler/actions and pause notifications until reset.
- **Flow**: user clicks “Stop” → system sets Freeze flag → scheduler halted → outbound notifications paused → API usage disabled logically (do not call provider) until manually reset.

---

## Test & deployment control

### UC-90 — “Dry Run” Simulation (Sandbox)
- **Goal**: test a draft Manifesto against historical data.
- **Flow**: select Draft Manifesto → select time window (e.g., last year) → system calculates hypothetical P&L and max drawdown → AI comments on volatility (optional).

---

# V2 Use Cases (placeholder; not in V1 implementation)

Purpose: allow the trading assistant to operate under a wider **personal agent hub** and interact with other agents. Keep V2 minimal until V1 stabilizes.

### UC-100 — Agent hub integration settings
- **Goal**: configure endpoints, tokens, and enable/disable inter-agent features.

### UC-101 — Register trading assistant with agent hub
- **Goal**: hub can discover this agent’s capabilities (name, version, endpoints).

### UC-110 — Receive task request from agent hub
- **Goal**: hub can request calculations/advice (e.g., run a scheduled task now).

### UC-112 — Publish events to agent hub
- **Goal**: publish key events (recommendation created, freeze triggered, manifesto approved).

### UC-130 — Data sharing consent policy (inter-agent)
- **Goal**: control what fields can be shared externally (never share secrets).

### UC-131 — Inter-agent authentication (minimal)
- **Goal**: prevent spoofed inbound requests/events (token/signature validation).

---

# Cross-cutting non-functional requirements (apply to all use cases)

## Authentication
- Support multiple users.
- No RBAC; all users have same permissions, but accounts are distinct.

## Database security
- Access limited: DB not exposed publicly; only internal Docker network; allowlist app container(s) only.
- Encryption in transit: TLS between app and DB (recommended even on LAN).
- Encryption at rest: encrypted storage for DB volume (host-level is most robust: e.g., LUKS on Proxmox datastore; then mount into LXC/Docker).
- Secrets management: no secrets in git; use Docker secrets / env injected from encrypted store; rotate keys.

## Auditability
Immutable log of:
- price snapshots used
- Manifesto version used
- recommendations generated
- user approvals
- executed trade ledger entries

## Portability
- Entire system runs as Docker containers; LXC is the host wrapper.
- Persistent data via mounted volumes; backup/restore documented.

## Reliability / ops
- Scheduled tasks must be idempotent (safe to rerun).
- Backups: daily DB dump + weekly full snapshot.
- Observability: basic logs + health checks.
