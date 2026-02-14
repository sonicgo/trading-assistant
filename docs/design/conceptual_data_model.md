# Trading Assistant — Conceptual Data Model (CDM)

_Generated: 2026-02-14 (UTC)_

This Conceptual Data Model (CDM) defines the **domain objects**, their **responsibilities**, and the **relationships** between them. It is intentionally **technology-agnostic** (no columns / data types yet). It is the prerequisite for the Logical Data Model (LDM).

---

## 1) Two data lifecycles

### 1.1 Immutable Stream (facts)
A write-once stream of events and time-series facts. Once recorded, entries are never mutated (only superseded by new facts).

**Examples**
- Market data: `PricePoint`, `FXRate`, `CorporateAction`
- Book of record: `LedgerBatch`, `LedgerEntry`
- Decisioning: `StrategyVersion`, `TaskRun`, `Recommendation`, `LLMVerdict`
- Governance: `AuditEvent` (append-only)

### 1.2 Mutable Snapshots (current state)
Derived “current state” representations for UI and fast calculations. These are updated in place and are always derivable from the stream (with the policy/strategy context).

**Examples**
- `HoldingSnapshot`, `CashSnapshot`, `PortfolioSummary`
- `FreezeState`
- `DraftStrategyVersion` (optional representation of a strategy being edited)

---

## 2) Five core conceptual domains

### Domain A — Registry & Context (“Entities”)
**Purpose:** Defines the static universe the agent operates in.

**Key concepts**
- **Instrument** defines *what exists* (canonical ISIN identity).
- **Portfolio** defines *who is trading* and anchors most data.
- **User** is authentication/identity; portfolios are attached to users (ownership and/or membership).

**Entities**
- `User` — authentication credential; can access one or more portfolios.
- `Portfolio` — container for all activity (e.g., “AJ Bell SIPP”).
  - **Tax treatment attribute**: `tax_treatment` (e.g., SIPP / ISA / GIA).
- `PortfolioMembership` (optional) — enables multiple users to access the same portfolio without RBAC.
- `Instrument` — canonical definition of a tradeable asset (ISIN, type, trading venue, quote currency/scale).
- `InstrumentAlias` (optional) — alternate ticker/venue representations for the same ISIN.

> **Sleeves:** Sleeve is **not intrinsic** to an instrument. Sleeve membership is a **strategy/portfolio classification** (defined by `StrategyVersion` and/or portfolio instrument configuration).

---

### Domain B — Market Data (“Feed”)
**Purpose:** External, immutable truth about the world. Time-series facts.

**Entities**
- `PricePoint` — price (raw + normalized) per `Instrument` per timestamp, per source/provider.
- `FXRate` — currency pair rate per timestamp, per source/provider (used for validation and normalization).
- `CorporateAction` — split/merge/ISIN change events that affect internal state derivations.

> **FX:** Model as **provider-specific** (market data source), not broker-specific. Portfolios can select preferred sources.

---

### Domain C — Book of Record (“State”)
**Purpose:** Internal truth about *your money*, derived from immutable ledger events.

**Key concept:** **State is derived from Events**
- `HoldingSnapshot` and `CashSnapshot` are derived from ledger events and corporate actions.

**Entities**
- `LedgerBatch` — groups related ledger events (e.g., “Feb Monthly Contribution”, “Wave A Deployment”).
- `LedgerEntry` — immutable financial event. **Trade and cash movements are subtypes**:
  - BUY / SELL
  - CONTRIBUTION / WITHDRAWAL
  - FEE / INTEREST / TRANSFER
- `HoldingSnapshot` — current units and (optional) cost basis per instrument per portfolio (mutable).
- `CashSnapshot` — current cash balance per portfolio (mutable; base currency GBP in V1).

---

### Domain D — Strategy & Intelligence (“Brain”)
**Purpose:** Decision logic, versioning, and AI review outputs.

**Key concept:** Strategies are **versioned** objects. A TaskRun references an exact version for reproducibility.

**Entities**
- `StrategyVersion` — a paired bundle of:
  - `MachinePolicy` (JSON rules/thresholds, targets, cadence, constraints)
  - `HumanManifesto` (Markdown rationale, stress tests, operating guide)
- `Recommendation` — an actionable plan of trades produced by a TaskRun.
- `RecommendationLine` — an individual proposed action (e.g., “BUY £125 of XWES”).
- `LLMVerdict` — cloud AI “second opinion” attached to a recommendation or a draft strategy (PASS/WARN/FAIL).

> Implementation note: `PolicyArchive` and `ManifestoArchive` are persistence/traceability forms of `StrategyVersion` (hash + payload). In CDM we treat them as aspects of `StrategyVersion`.

---

### Domain E — Operations & Governance (“Guardrails”)
**Purpose:** Orchestration, safety, auditability, and notifications.

**Key concept:** Every action is traceable to a **TaskRun** (or a user action), and can be audited.

**Entities**
- `TaskDefinition` — a scheduled job definition (CRON/RRULE, modules, enabled) with scope:
  - GLOBAL (seeded templates)
  - PORTFOLIO (applies to one portfolio)
- `TaskRun` — an execution event (start/end/status), references StrategyVersion, captures input snapshot hashes for reproducibility.
- `Alert` — persistent warning (e.g., data quality violation) that can block future runs until resolved.
- `FreezeState` — portfolio-level kill switch status (mutable flag).
- `Notification` — message attempts/outcomes (email/telegram/slack/webpush).
- `AuditEvent` — append-only log of significant changes and decisions (freeze toggles, strategy approvals, trade execution confirmations, etc.).

---

## 3) Key invariants (CDM-level)
- **Reproducibility:** Every TaskRun must reference a specific StrategyVersion (hash/version) and the input snapshot (prices used, holdings used) must be recoverable.
- **Immutability:** Stream entities are append-only; corrections are expressed as new records, not updates.
- **Separation:** Instruments are canonical by ISIN; sleeve classification is strategy/portfolio context.
- **Safety:** Data-quality Alerts and FreezeState can block automated action generation.

---

## 4) Mermaid diagram
The Mermaid diagram is included below for convenient review.


```mermaid
graph TD

%% ===== Styles =====
classDef stream fill:#F5F5F5,stroke:#333,stroke-width:1px;
classDef snap fill:#E8F4FF,stroke:#1f77b4,stroke-width:1px;
classDef domain fill:#FFFFFF,stroke:#999,stroke-dasharray: 5 5;

%% ===== Domain A: Registry & Context =====
subgraph A["Domain A — Registry & Context"]
  U[User]:::stream
  P[Portfolio<br/>(tax_treatment)]:::stream
  PM[PortfolioMembership<br/>(optional)]:::stream
  I[Instrument<br/>(ISIN-canonical)]:::stream
  IA[InstrumentAlias<br/>(optional)]:::stream
end
class A domain;

U -->|owns| P
U -->|access (optional)| PM
PM --> P
I --> IA

%% ===== Domain B: Market Data (Immutable Stream) =====
subgraph B["Domain B — Market Data (Immutable Stream)"]
  PP[PricePoint]:::stream
  FX[FXRate]:::stream
  CA[CorporateAction]:::stream
end
class B domain;

I -->|1..N| PP
I -->|1..N| CA

%% ===== Domain C: Book of Record =====
subgraph C["Domain C — Book of Record"]
  LB[LedgerBatch]:::stream
  LE[LedgerEntry<br/>(BUY/SELL/CONTRIB/FEE...)]:::stream
  HS[HoldingSnapshot<br/>(current)]:::snap
  CS[CashSnapshot<br/>(current)]:::snap
end
class C domain;

P -->|1..N| LB
LB -->|1..N| LE
LE -. derives .-> HS
LE -. derives .-> CS
CA -. adjusts derivation .-> HS

P -->|has current| HS
P -->|has current| CS
I -->|held as| HS
I -->|traded as| LE

%% ===== Domain D: Strategy & Intelligence =====
subgraph D["Domain D — Strategy & Intelligence"]
  SV[StrategyVersion<br/>(policy+manifesto)]:::stream
  R[Recommendation]:::stream
  RL[RecommendationLine]:::stream
  LV[LLMVerdict]:::stream
end
class D domain;

SV -->|maps instrument→sleeve<br/>+ targets| I

%% ===== Domain E: Operations & Governance =====
subgraph E["Domain E — Operations & Governance"]
  TD[TaskDefinition<br/>(scope: GLOBAL/PORTFOLIO)]:::stream
  TR[TaskRun]:::stream
  AL[Alert]:::stream
  FR[FreezeState<br/>(current)]:::snap
  N[Notification]:::stream
  AE[AuditEvent]:::stream
end
class E domain;

TD -->|1..N| TR
TR -->|uses| SV
TR -->|0..1 produces| R
R -->|1..N| RL
R -->|0..N reviewed by| LV

P -->|0..1 current| FR
TR -->|may raise| AL
AL -->|may block| TD
TR -->|triggers| N
N -->|sent to| U

AE -->|references| P
AE -->|references| TR
AE -->|references| R
AE -->|references| SV
AE -->|references| LE

%% ===== Safety linkage =====
FR -->|halts automation| TD
```
