# Trading Assistant Architecture

## 1) System Overview

Trading Assistant is a full-stack application for portfolio management and trading workflow support. The codebase is organized as a monorepo with:

- `frontend/`: Next.js App Router UI (React + TypeScript)
- `backend/`: FastAPI API service (Python + SQLAlchemy)
- `database/`: SQL bootstrap scripts
- `docs/` and `policy/`: architecture and rule definitions

At runtime, the project is intended to run as multi-service Docker Compose stack: `ui`, `api`, `worker`, `db`, and `redis`.

## 2) Repository Structure Map

Top-level map of the repository (`trading-assistant/`):

```text
trading-assistant/
├── backend/
│   ├── app/
│   │   ├── api/
│   │   │   ├── deps.py
│   │   │   └── v1/endpoints/
│   │   │       ├── auth.py
│   │   │       ├── portfolios.py
│   │   │       └── registry.py
│   │   ├── core/
│   │   │   ├── config.py
│   │   │   ├── database.py
│   │   │   └── security.py
│   │   ├── db/
│   │   │   └── session.py
│   │   ├── domain/
│   │   │   └── models.py
│   │   ├── schemas/
│   │   │   ├── auth.py
│   │   │   ├── common.py
│   │   │   └── registry.py
│   │   └── main.py
│   ├── alembic/
│   │   ├── env.py
│   │   └── versions/
│   ├── scripts/
│   ├── Dockerfile
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── app/
│   │   │   ├── layout.tsx
│   │   │   ├── page.tsx
│   │   │   ├── login/page.tsx
│   │   │   ├── registry/page.tsx
│   │   │   └── portfolios/[id]/page.tsx
│   │   ├── context/
│   │   │   └── AuthContext.tsx
│   │   ├── hooks/
│   │   │   └── use-portfolios.ts
│   │   └── lib/
│   │       └── api-client.ts
│   ├── next.config.ts
│   ├── package.json
│   └── Dockerfile
├── database/
│   └── init.sql
├── docs/
│   ├── manifesto.md
│   └── design/
├── implementation/
│   └── delivery_plan.md
├── policy/
│   ├── manifesto_policy.json
│   └── manifesto_policy.schema.json
├── docker-compose.yml
├── init_project.sh
├── README.md
└── use_case.md
```

## 3) Main Entry Points

### Runtime / service entry points

1. Backend API app
   - File: `backend/app/main.py`
   - Process command: `uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload` (from `docker-compose.yml`)
   - FastAPI bootstrap includes CORS and v1 routers.

2. Frontend app
   - File: `frontend/package.json`
   - Scripts: `dev`, `build`, `start`, `lint`
   - Next.js App Router root layout: `frontend/src/app/layout.tsx`

3. Container orchestration
   - File: `docker-compose.yml`
   - Services: `db` (Postgres), `redis`, `api`, `worker`, `ui`

### Supporting startup surfaces

- Backend container defaults: `backend/Dockerfile` (uvicorn command)
- Frontend container defaults: `frontend/Dockerfile` (`npm start`)
- Utility/bootstrap scripts: `backend/scripts/*.py`, `init_project.sh`

## 4) Backend Architecture

### Layering

Backend follows a conventional layered FastAPI structure:

- API layer: `backend/app/api/v1/endpoints/*`
- Dependency/auth context: `backend/app/api/deps.py`
- Domain model layer: `backend/app/domain/models.py`
- Schema/validation layer: `backend/app/schemas/*`
- Core infrastructure: `backend/app/core/*`
- DB session management: `backend/app/db/session.py`

### API wiring

`backend/app/main.py` initializes the app and mounts routers:

- `/api/v1/auth`
- `/api/v1/registry`
- `/api/v1/portfolios`

Endpoint count currently detected:

- `auth.py`: 4 routes
- `registry.py`: 2 routes
- `portfolios.py`: 4 routes

### Authentication and security flow

- Login endpoint validates credentials and returns access token.
- Refresh uses cookie + CSRF header double-submit style check.
- `deps.get_current_user` decodes JWT and loads user from DB.
- Password hashing and token generation live in `core/security.py`.

### Data access and models

- SQLAlchemy declarative base: `core/database.py`
- Engine/session factory: `db/session.py`
- Domain entities include users, portfolios, instruments, listings, sleeves, and constituents.

## 5) Frontend Architecture

### Framework and composition

- Next.js app directory (`src/app`) with client components.
- Root providers in `src/app/layout.tsx`:
  - React Query `QueryClientProvider`
  - Custom `AuthProvider`

### Routing surfaces

- `/` dashboard (`src/app/page.tsx`)
- `/login` login page
- `/registry` instrument/listing creation
- `/portfolios/[id]` portfolio constituent details

### Data and auth behavior

- Shared Axios client in `src/lib/api-client.ts`
  - Base URL: `/api/v1`
  - `withCredentials: true`
  - 401 interceptor with refresh attempt and retry queue
- Auth state and login/logout flow in `src/context/AuthContext.tsx`
- Dashboard uses React Query to load portfolios.

### Frontend-backend boundary

`frontend/next.config.ts` defines rewrites:

- `/api/v1/:path*` -> `http://localhost:8000/api/v1/:path*`

This keeps browser requests same-origin from the UI perspective while forwarding to FastAPI during local development.

## 6) Data and Infrastructure Architecture

### Docker Compose topology

From `docker-compose.yml`:

- `db`: Postgres 16 with persistent volume and init scripts from `./database`
- `redis`: Redis 7
- `api`: FastAPI container from `./backend`
- `worker`: Python module launch target `python -m app.worker.runner`
- `ui`: Next.js container from `./frontend`

All services are attached to network `ta_net`.

### Database lifecycle

- Bootstrap SQL: `database/init.sql`
- Migration framework: Alembic (`backend/alembic/*`, `alembic.ini`)

## 7) End-to-End Request Flow

Typical authenticated UI flow:

1. User logs in via frontend (`/login`).
2. Frontend posts credentials to `/api/v1/auth/login`.
3. API validates credentials, returns access token, sets refresh/CSRF cookies.
4. Frontend stores bearer token in Axios default headers.
5. Dashboard requests portfolio data from `/api/v1/portfolios`.
6. API checks JWT in dependency, loads DB user, applies owner scoping.
7. API queries SQLAlchemy models and returns typed response payloads.

## 8) Design Strengths and Risks

### Strengths

- Clean backend folder separation (API, schemas, domain, core, db).
- Clear frontend provider and route structure.
- Explicit API versioning (`/api/v1`).
- Docker Compose support for local full-stack execution.
- Rich architecture design docs in `docs/design/`.

### Notable risks / gaps observed

- `docker-compose.yml` references `app.worker.runner`, but `backend/app/worker/runner.py` is not present in the repository snapshot.
- `README.md` is minimal and does not describe runbook/architecture in depth.
- No dedicated tests directory or CI workflow (`.github/workflows`) found.
- Some auth refresh logic contains placeholder behavior in `backend/app/api/v1/endpoints/auth.py` (`subject="placeholder_user_id"`), indicating incomplete production-hardening.

## 9) Key Files to Read First

For onboarding, read in this order:

1. `docker-compose.yml`
2. `backend/app/main.py`
3. `backend/app/api/v1/endpoints/*.py`
4. `backend/app/domain/models.py`
5. `frontend/src/app/layout.tsx`
6. `frontend/src/lib/api-client.ts`
7. `frontend/src/context/AuthContext.tsx`
8. `docs/design/high_level_technical_design.md`

## 10) Architectural Summary

This repository is structured as a pragmatic full-stack monorepo with FastAPI + Next.js, backed by PostgreSQL and Redis, and orchestrated via Docker Compose. The code organization follows familiar layered patterns and is easy to navigate. The largest implementation concern is that worker runtime wiring appears partially defined (compose command present, module missing), while core API/UI interactions are implemented and traceable end to end.
