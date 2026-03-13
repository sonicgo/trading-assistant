# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Architecture Mandate

Before making any architectural or data model decisions, read these documents:
- `docs/design/HLD.md` — Master narrative, all architectural decisions
- `docs/design/conceptual_data_model.md` — Domain objects, Stream vs Snapshot lifecycle
- `docs/design/logical_data_model.md` — Tables, keys, invariants
- `docs/design/pdm/physical_data_model_v2.md` — JSONB rules, indexing, migration approach
- `docs/manifesto.md` — Investment strategy, wave triggers, constraints (source of truth for business rules)
- `implementation/IMPLEMENTATION_REPORT.md` — What has been implemented so far

Never guess schema, functional requirements, or architectural boundaries. If a requirement is ambiguous, ask before writing code.

## Environment (Split-Brain)

Two hosts share the working tree via NFS:

| Host | Role |
|---|---|
| `u24-dev` | **Editing** — all file reads and writes happen here |
| `docker-dev` | **Execution** — Docker daemon; all build/test/run commands execute here |

`DOCKER_HOST` is set on `u24-dev` to route `docker` and `docker compose` commands transparently to `docker-dev`. Never run Docker commands directly on `docker-dev` via SSH unless `DOCKER_HOST` routing is unavailable.

Preferred execution (from u24-dev, via DOCKER_HOST):
```bash
docker compose run --rm <service> <command>
```

Fallback (direct SSH to docker-dev):
```bash
ssh docker-dev "cd ~/projects/trading-assistant && <command>"
```

## Commands

### Start/stop services
```bash
docker compose up -d           # Start all services (api, worker, db, redis, ui)
docker compose down
docker compose logs -f api     # Tail API logs
docker compose logs -f worker  # Tail worker logs
```

### Backend tests (from /backend)
```bash
docker compose run --rm api pytest tests/ -v
docker compose run --rm api pytest tests/test_engine_calculator.py -v          # single file
docker compose run --rm api pytest tests/test_engine_calculator.py::test_name  # single test
```

### Frontend
```bash
cd frontend && npm run dev     # Dev server (port 3000)
cd frontend && npm run build
cd frontend && npm run lint
```

### Database migrations
```bash
docker compose run --rm api alembic upgrade head
```

## High-Level Architecture

```
Next.js UI (port 3000)
     ↓ REST
FastAPI API (port 8000)  ←→  Redis Queue  ←→  Worker Process
     ↓
PostgreSQL 16
     ↓
External: yfinance (market data), Apprise (notifications)
```

### Backend layers (`/backend/app/`)

| Layer | Path | Purpose |
|---|---|---|
| API endpoints | `api/v1/endpoints/` | auth, registry, portfolios, ledger, engine, recommendations, dashboard, alerts, freeze, notifications |
| Services | `services/` | Business logic — each service owns a domain (market data ingest, data quality, ledger posting, engine calculator, execution, alerts, freeze, scheduler, notifications, snapshots) |
| Market data providers | `services/providers/` | `yfinance_adapter.py`, `mock_provider.py` |
| Worker | `worker/runner.py` | Async event loop; dequeues Redis jobs and dispatches handlers |
| Queue | `queue/redis_queue.py` | Redis-backed job queue |
| Domain models | `domain/models.py` | All SQLAlchemy ORM models |
| Entry point | `main.py` | FastAPI app, CORS, router registration, scheduler lifespan |

### Data model patterns

Two distinct table classes (never conflate them):
- **Stream tables** (append-only): `ledger_batches`, `ledger_entries`, `price_points`, `fx_rates`, `audit_events`
- **Snapshot tables** (mutable point-in-time): `cash_snapshots`, `holding_snapshots`, `recommendation_batches`, `recommendation_lines`

### Key data flows

**Price ingest → DQ gate → freeze:**
APScheduler enqueues `PRICE_REFRESH` → worker fetches via provider → `data_quality.py` validates (stale, missing, jumps, GBX/FX scale) → if valid: insert price_points; if invalid: insert alerts + freeze state.

**Ledger posting:**
User POSTs ledger batch → atomic write of `ledger_entries` + update `cash_snapshot` / `holding_snapshot` in same transaction → `audit_events` row.

**Engine → recommendations:**
`engine_inputs.py` assembles snapshot from DB → `engine_calculator.py` runs deterministic drift/rebalance calculation → writes `recommendation_batch` + `recommendation_lines`.

**Execution capture:**
User marks recommendation executed → `execution_service.py` creates `ledger_entry` → snapshots updated → audit logged.

### Frontend (`/frontend/src/`)

- `app/` — Next.js App Router pages
- `components/` — React components
- `hooks/` — TanStack Query hooks wrapping API calls
- `lib/` — axios API client, helpers
- `context/` — AuthContext (JWT)
- `types/` — TypeScript interfaces

## Key Config

`/.env` (gitignored) — database URL, JWT secret, Redis URL, `MARKETDATA_PROVIDER` (mock|yfinance), DQ thresholds, venue timezone/hours, Apprise notification config, bootstrap admin credentials.

`/backend/pytest.ini` — `asyncio_mode = auto`, `pythonpath = .`

`/policy/` — JSON policy configuration for portfolio allocation rules.
