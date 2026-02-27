# Phase 1 Build Playbook — Identity + Registry (Execution Guide)

_Last updated: 2026-02-15 (UTC)_

This playbook turns the Phase 1 LLD pack (**LLD-0..4**) into an implementable build checklist with concrete file responsibilities, function signatures, acceptance tests, and “don’t-miss” edge cases.

Phase 1 Outcome:
- You can **sign in** (JWT access + refresh cookie + CSRF)
- You can configure the portfolio universe:
  - **Portfolio CRUD**
  - **Instrument CRUD**
  - **Listing CRUD** (venue + trading currency + MAJOR/MINOR scale)
  - **Portfolio constituents** (listing → sleeve mapping + monitored flag)
- API enforces **portfolio tenancy** checks.

---

## 0) Assumptions (locked for this playbook)

Backend:
- FastAPI + Pydantic v2
- SQLAlchemy 2.x + Alembic
- Postgres (schema per `schema_v2.sql`)
- Password hashing: Argon2 (preferred) or bcrypt
- Auth: Access JWT (15 min) + Refresh cookie (7 days) + CSRF double-submit

Frontend:
- Next.js (App Router) + TypeScript
- TanStack Query
- Decimal strings in API responses; UI uses decimal.js/big.js for arithmetic
- Refresh mutex in UI (single refresh in-flight)

---

## 1) Definition of Done (Phase 1)

Backend DoD:
- Auth endpoints implemented (login/refresh/logout/me)
- Registry endpoints implemented (instruments/listings)
- Portfolio endpoints implemented (CRUD + constituents bulk upsert)
- Tenancy checks enforced on all portfolio-scoped endpoints
- Sleeves lookup seeded (`ta.sleeves`) matching API enum values
- Listing currency/scale mapped to DB `quote_scale` with GBP+MINOR→GBX
- All decimals serialize as strings (Pydantic v2 serializer)
- Manual smoke tests pass (curl), and minimum automated tests exist (pytest)

Frontend DoD:
- Login page works; access token in memory
- Refresh mutex works (no phantom logout under concurrent 401)
- Portfolio list + detail + constituents mapping works end-to-end

---

## 2) Environment & Configuration

### 2.1 Required environment variables (backend)
Minimum env keys (names are examples; align to your repo):
- `DATABASE_URL=postgresql+psycopg://user:pass@db:5432/trading_assistant`
- `JWT_SECRET_KEY=...` (32+ bytes)
- `JWT_ALGORITHM=HS256`
- `ACCESS_TOKEN_EXPIRE_MINUTES=15`
- `REFRESH_TOKEN_EXPIRE_DAYS=7`

Cookies / security:
- `COOKIE_SECURE=true` (prod) / `false` (local http)
- `COOKIE_SAMESITE=Strict` (preferred)
- `REFRESH_COOKIE_NAME=ta_refresh`
- `CSRF_COOKIE_NAME=ta_csrf`

Bootstrap admin seed:
- `BOOTSTRAP_ADMIN_EMAIL=...`
- `BOOTSTRAP_ADMIN_PASSWORD=...` (or generate + print once)
- `BOOTSTRAP_ADMIN_ENABLED=true`

CORS (only if different origins):
- `CORS_ORIGINS=["https://ta.home","http://localhost:3000"]`

### 2.2 Running services
- Postgres reachable to API
- Next.js reachable to user
- Reverse proxy terminates TLS in non-local setups

---

## 3) Backend Build Steps (in-order)

### Step 1 — Foundation (Backend)

#### 1.1 `app/core/config.py`
**Goal:** typed settings class with sane defaults.

Deliverables:
- `Settings` object loaded from env (Pydantic settings)
- `.get_settings()` cached dependency

Acceptance:
- App boots, logs settings summary (non-secrets only)

Suggested skeleton:
```python
# app/core/config.py
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str
    jwt_secret_key: str
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 15
    refresh_token_expire_days: int = 7

    cookie_secure: bool = True
    cookie_samesite: str = "Strict"
    refresh_cookie_name: str = "ta_refresh"
    csrf_cookie_name: str = "ta_csrf"

    bootstrap_admin_email: str | None = None
    bootstrap_admin_password: str | None = None
    bootstrap_admin_enabled: bool = True

settings = Settings()
```

#### 1.2 `app/core/security.py`
**Goal:** password hashing + JWT + refresh token generation/hashing.

Deliverables (functions):
- `hash_password(plain: str) -> str`
- `verify_password(plain: str, password_hash: str) -> bool`
- `create_access_token(*, user_id: UUID, session_id: UUID) -> str`
- `decode_access_token(token: str) -> dict`
- `generate_refresh_token() -> str`
- `hash_refresh_token(token: str) -> str`

Acceptance:
- Unit test verifies:
  - hash/verify works
  - JWT decode works, expires correctly
  - refresh token hashes match on same token

Notes:
- Access JWT claims: `sub` (user_id), `sid` (session_id), `exp`, `iat`
- Never store raw refresh tokens; store hash only.

#### 1.3 `app/db/session.py`
**Goal:** SQLAlchemy engine/session and `get_db()` dependency.

Deliverables:
- `engine = create_engine(settings.database_url, pool_pre_ping=True)`
- `SessionLocal = sessionmaker(...)`
- `get_db()` yields session and closes on exit

Acceptance:
- `/health` endpoint can execute `SELECT 1`

#### 1.4 `app/api/deps.py`
**Goal:** request dependencies for current user, admin guard, and portfolio tenancy.

Deliverables:
- `get_current_user(request, db) -> User`
- `require_bootstrap_admin(current_user) -> User`
- `require_portfolio_access(portfolio_id, current_user, db) -> Portfolio`

Acceptance:
- Any portfolio endpoint returns 403 if user doesn’t own/access portfolio.

---

### Step 2 — Auth Domain (Backend)

#### 2.1 `app/schemas/auth.py`
**Goal:** implement Pydantic models per LLD-1.

Deliverables:
- `AuthLoginRequest`
- `AuthTokenResponse`
- `AuthLogoutResponse`
- `MeResponse`
- Error envelope is shared (`ErrorEnvelope`)

Acceptance:
- OpenAPI shows models and request/response examples.

#### 2.2 `app/api/v1/endpoints/auth.py`
Endpoints:
- `POST /api/v1/auth/login`
- `POST /api/v1/auth/refresh`
- `POST /api/v1/auth/logout`
- `GET /api/v1/auth/me`

Core responsibilities by endpoint:

**Login**
1) verify user exists + enabled
2) verify password
3) create `auth_session` row with `refresh_token_hash`
4) set cookies:
   - `ta_refresh` (HttpOnly, Secure, SameSite, Path=/api/v1/auth/refresh)
   - `ta_csrf` (JS-readable, Secure, SameSite, Path=/api/v1/auth/refresh)
5) return `AuthTokenResponse`

**Refresh**
1) validate CSRF: header `X-CSRF-Token` equals cookie `ta_csrf`
2) get `ta_refresh` cookie, hash, match active session (not revoked/expired)
3) rotate refresh token (update hash + last_seen)
4) issue new access token + set new cookies

**Logout**
1) revoke session
2) clear cookies

**Me**
- return identity payload from access token user

Acceptance tests (manual):
```bash
# 1) Login
curl -i -X POST https://ta.home/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@x","password":"..."}'

# Expect: Set-Cookie ta_refresh=...; HttpOnly
#         Set-Cookie ta_csrf=...
#         JSON access_token

# 2) Refresh requires CSRF header
curl -i -X POST https://ta.home/api/v1/auth/refresh \
  -H "X-CSRF-Token: <value from ta_csrf cookie>" \
  --cookie "ta_refresh=<...>; ta_csrf=<...>"
```

**Don’t miss**
- Refresh mutex is primarily a frontend control, but backend must not crash if refresh called twice.
- Return standard error envelope + `X-Correlation-Id`.

---

### Step 3 — Registry + Portfolio Domain (Backend)

#### 3.1 Schemas
Files:
- `app/schemas/registry.py`
- `app/schemas/portfolio.py`
- (shared) `app/schemas/common.py` for `DecimalStr`, errors, pagination

Acceptance:
- OpenAPI shows offset pagination for instruments/listings.

#### 3.2 Registry endpoints
File:
- `app/api/v1/endpoints/registry.py`

Endpoints:
- Instruments:
  - `GET /instruments?limit&offset&q&isin`
  - `POST /instruments`
  - `PATCH /instruments/{instrument_id}`
- Listings:
  - `GET /listings?limit&offset&instrument_id&exchange&ticker`
  - `POST /listings`
  - `PATCH /listings/{listing_id}`

**Critical implementation mapping (accepted)**
API exposes:
- `trading_currency` (GBP/USD/EUR)
- `price_scale` (MAJOR/MINOR)

DB stores:
- `quote_scale` (GBP/GBX/USD/...)

Backend mapping:
- if GBP + MINOR → quote_scale=GBX
- else quote_scale=trading_currency

Acceptance (manual):
- Create listing with GBP+MINOR and verify DB quote_scale=GBX.

#### 3.3 Portfolio endpoints
File:
- `app/api/v1/endpoints/portfolios.py`

Endpoints:
- `GET /portfolios`
- `POST /portfolios`
- `GET /portfolios/{portfolio_id}`
- `PATCH /portfolios/{portfolio_id}`
- `GET /portfolios/{portfolio_id}/constituents`
- `PUT /portfolios/{portfolio_id}/constituents` (bulk upsert)

**Bulk upsert semantics**
- Transactional:
  1) upsert each item
  2) if `replace_missing=true`, delete stale rows not in payload

Recommended constraints:
- V1: enforce **one listing per sleeve per portfolio** (simplifies downstream calculations)

Acceptance (manual):
1) Create portfolio
2) Create instrument
3) Create listing
4) PUT constituents mapping listing→sleeve

#### 3.4 Migration: seed sleeves (mandatory)
Add an Alembic migration that inserts sleeve codes, idempotently:
- `INSERT ... ON CONFLICT DO NOTHING`

Acceptance:
- Fresh DB deploy + running API allows constituents insert without FK failure.

---

## 4) Backend Testing Strategy (minimal, Phase 1)

### 4.1 Automated tests (pytest + httpx)
Minimum test suite:
- `test_auth_login_sets_cookies()`
- `test_refresh_requires_csrf()`
- `test_portfolio_tenancy_forbidden()`
- `test_listing_gbp_minor_maps_to_gbx()`
- `test_constituents_bulk_upsert_replace_missing()`

### 4.2 Manual smoke test script
Create `scripts/phase1_smoke.sh`:
- login
- call /me
- create portfolio
- create instrument/listing
- map constituents

This script is your “bring-up test” in homelab.

---

## 5) Frontend Build Steps (in-order)

### Step 4 — Frontend Wiring

#### 4.1 API client + AuthProvider (with refresh mutex)
Deliverables:
- `AuthProvider` with:
  - `accessToken` in memory
  - `login()`, `logout()`
- API client wrapper with:
  - attach bearer token
  - on 401: call refresh via mutex; retry request once
  - refresh includes `credentials: "include"` and `X-CSRF-Token` read from `ta_csrf` cookie

Acceptance:
- Open dashboard, open multiple pages quickly (concurrent API calls), no phantom logout.

#### 4.2 TanStack Query setup
Deliverables:
- `QueryClientProvider` at app root
- Query key conventions aligned to LLD-4

Acceptance:
- List pages show loading states + error states cleanly
- Mutations invalidate correct queries

#### 4.3 Pages (minimum)
- `/login`
- `/portfolios` (list + create)
- `/portfolios/[id]`:
  - view portfolio summary
  - constituents editor (bulk upsert)
- `/registry/instruments` (list/create/update)
- `/registry/listings` (list/create/update)

Acceptance:
- End-to-end: create portfolio → create instrument/listing → map constituent.

---

## 6) Common “Don’t-Miss” Edge Cases

- **Decimals**: never parse decimal strings as JS numbers for money math.
- **Cookies**:
  - `ta_refresh` must be HttpOnly
  - `ta_csrf` must be JS-readable
  - Path scoping to refresh endpoint reduces exposure
- **Refresh mutex**: required to avoid invalidating rotated tokens.
- **Sleeve seeding**: mandatory to satisfy FK constraints.
- **Tenancy**: portfolio endpoints must always verify access.
- **Correlation IDs**: return `X-Correlation-Id` for debugging.

---

## 7) Phase 1 Build Order (expanded)

1) Foundation (Backend)
- [ ] config.py + security.py
- [ ] db/session.py
- [ ] api/deps.py

2) Auth Domain (Backend)
- [ ] schemas/auth.py
- [ ] endpoints/auth.py
- [ ] Manual Test: login returns cookies + csrf token

3) Registry Domain (Backend)
- [ ] schemas/registry.py + schemas/portfolio.py
- [ ] endpoints/registry.py
- [ ] endpoints/portfolios.py
- [ ] Migration: seed sleeves
- [ ] Manual Test: create portfolio, create instrument/listing, map listing

4) Frontend Wiring
- [ ] QueryClient + AuthProvider + refresh mutex
- [ ] Login page
- [ ] Portfolio list + detail + constituents editor
- [ ] Registry pages (instruments/listings)

---

## 8) Exit Criteria (Phase 1)

- User logs in; refresh works; logout works
- User can create portfolio, instrument, listing
- User can map listing to sleeve via constituents page
- Portfolio endpoints enforce tenancy
- No refresh-race logouts in UI under concurrent requests
- Fresh DB deploy succeeds due to sleeves seed migration
