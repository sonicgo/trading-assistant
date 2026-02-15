# Alembic baseline migration (Trading Assistant)

This folder is a ready-to-use Alembic scaffold containing a **baseline migration** that applies:
- the full `ta` schema DDL (tables/constraints/indexes)
- retention helper functions

## How to run (Docker / local)

1) Install deps:
- alembic
- sqlalchemy
- psycopg (v3) or psycopg2

2) Set DATABASE_URL (recommended):
export DATABASE_URL="postgresql+psycopg://user:pass@localhost:5432/trading_assistant"

3) Run migrations:
alembic -c alembic.ini upgrade head

## Notes
- IDs are UUID; the application should generate UUIDv7.
- All timestamps are TIMESTAMPTZ stored in UTC.
- The baseline migration is SQL-first (no SQLAlchemy models required).
