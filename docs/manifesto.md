# Investment Manifesto — SIPP ETF Portfolio

_Generated: 2026-02-14 (UTC) from `policy/manifesto_policy.json` version 1.0.0_


This document is the **human-readable strategy** for the Trading Assistant Agent. The executable rules live in `policy/manifesto_policy.json` (validated by `policy/manifesto_policy.schema.json`).


---

## Principles

- Own broad, accumulating funds inside the SIPP; avoid dividend admin and reinvestment friction.
- Keep trading frequency low (minimise dealing + FX + spread).
- Use rules, not feelings: rebalance only when drift exceeds thresholds, and deploy cash via pre-set triggers.
- Cash is not idle: staged cash must earn a cash-like return while waiting.

Additional operating principles:

- **Low friction by design:** default monthly investing uses **≤2 orders**; quarterly rebalance uses **≤3 orders**.

- **Deterministic first:** recommendations are produced by the local rules engine; cloud LLM output is **advisory only**.

- **Data safety:** recommendations are blocked and the system can **freeze** if price/FX data looks wrong.


---

## Strategy overview

### Target portfolio (100% of long-term invested assets)

Weights below are the **strategic targets**. The staged cash park (CSH2) is managed separately.


| Target | Sleeve | Instrument(s) | ISIN(s) |
|---:|---|---|---|

| 35% | Core — Global All‑World equity | VWRP | IE00BK5BQT80 |
| 35% | Growth satellite — Global Semiconductors | SEMI | IE000I8KRLL9 |
| 10% | Diversifier — Global Energy sector | XWES | IE00BM67HM91 |
| 10% | Diversifier — Global Healthcare sector | XWHS | IE00BM67HK77 |
| 5% | Diversifier — Global Small‑Cap equity | WLDS | IE00BF4RFH31 |
| 5% | Defensive — Short‑dated UK Gilts (0–5y) | IGL5 | IE000RCMNFR9 |

### Staged cash policy (separate from target weights)

- **Parking instrument:** `CSH2` (money market / cash-like return)

- **Initial staged amount:** £16000

- **Purpose:** earn cash-like return while waiting; deploy into risk assets only via explicit triggers.


**Wave triggers**


| Wave | Portfolio drawdown trigger | Amount to deploy | Allocation rule |
|---|---:|---:|---|

| A | 10% | £8000 | most_underweight |
| B | 20% | £8000 | most_underweight |

**Sunset clause**


| Date | Deploy fraction of remaining staged cash | Allocation rule |
|---|---:|---|

| 2027-02-01 | 50% | fixed_allocation → core |
| 2028-02-01 | 100% | fixed_allocation → core |

---

## Operating plan

### Review cadence (decision vs action)

- **Weekly (review-only):** check weights and triggers; **no trading** unless a Wave trigger or other explicit trigger is hit. (`review_only=true`)

- **Monthly (action):** deploy **£500** with **≤2 orders**.

- **Quarterly (action):** sector/satellite correction with **≤3 orders**.


### Monthly default buy list

- Minimum trade size (friction filter): **£25** (unless part of a Wave deployment)


| Ticker | Amount |
|---|---:|

| VWRP | £425 |
| WLDS | £75 |

If drift is large, the monthly contribution may be redirected using the fallback strategy: **most_underweight** (while respecting max order count and min trade size).


### Quarterly rebalance priorities

- On rebalance months, redirect that month’s contribution to correct drift, prioritising:

  - energy → healthcare → semis → short_gilts

- If nothing is meaningfully underweight, revert to the monthly default lines: `fallback_to_monthly_defaults_when_no_meaningful_drift=true`


---

## Triggers and constraints

### Drift thresholds (when to act)

- **Major sleeves:** act when absolute drift exceeds **2.0 percentage points**.

- **Minor sleeves:** act when absolute drift exceeds **1.0 percentage points**.

- **Minor sleeves list:** small_cap, short_gilts

- **Wave triggers enabled:** true


### Portfolio constraints

- **Allow individual stocks:** false (expected: false)

- **Acc-only policy:** true (expected: true)

- **Max acceptable drawdown (behavioural tolerance):** 20%


---

## Data quality and safety

The system must block advice and may **freeze** to prevent acting on bad market data.


Key rules:

- **Freeze on value jump:** if `(price × units)` moves by more than **50%** in one day without a logged trade/corporate action → **Freeze**.

- **Quote-scale checks (GBX vs GBP):** enabled = true

- **Currency mismatch checks:** enabled = true

- **Block recommendations on any critical alert:** true


### Emergency Freeze / Kill Switch

- A manual **Freeze** control exists to halt scheduler activity and pause notifications until manually reset.


---

## Stress tests (rationale)

- **Staged cash opportunity cost:** staged cash is held in a money-market ETF + governed by a sunset clause.

- **Dealing friction:** default 2 monthly lines + quarterly batching + minimum trade filter.

- **Behavioural tinkering risk:** weekly is review-only; action windows are monthly/quarterly.

- **FX / quote-scale errors:** controlled via UCITS ETFs + explicit data-quality checks (GBX/GBP and currency mismatch).

- **Energy cyclicality:** capped by fixed 10% target + periodic rebalance.

- **Rate shock:** short gilts capped at 5%; staged cash remains cash-like.


---

## Policy snapshot (for audit)

This section is a **rendered snapshot** of the current policy configuration.


### Instruments


| Ticker | ISIN | Exchange | Currency | Quote scale | Sleeve |
|---|---|---|---|---|---|

| VWRP | IE00BK5BQT80 | LSE | GBP | GBX | core |
| WLDS | IE00BF4RFH31 | LSE | GBP | GBX | small_cap |
| XWES | IE00BM67HM91 | LSE | GBP | GBX | energy |
| XWHS | IE00BM67HK77 | LSE | GBP | GBX | healthcare |
| IGL5 | IE000RCMNFR9 | LSE | GBP | GBX | short_gilts |
| SEMI | IE000I8KRLL9 | LSE | GBP | GBX | semis |
| CSH2 | LU1230136894 | LSE | GBP | GBX | cash_park |

### Quote scale normalization

- LSE feeds commonly quote in **GBX (pence)**. The policy uses `quote_scale=GBX` and a factor of **0.01** to normalize into GBP.

- Provider/ingestion must respect `price_normalization.quote_scale_factors`.


---

## Change management

- Changes to rules must be made in `policy/manifesto_policy.json` and validated against `policy/manifesto_policy.schema.json`.

- Human narrative updates can be made in this Markdown, but should remain consistent with the policy.

- Recommendations should always record: policy version, prices timestamp, holdings snapshot, and the rules that fired.
