-- Trading Assistant (ta) — schema_optional_partitions.sql
-- Optional future enhancement: monthly range partitions for price_points (and optionally fx_rates).
-- Apply only if/when data volume grows materially (millions+ rows).

BEGIN;

-- This file is intentionally a TEMPLATE, not an automatic online migration.
-- Recommended approach for adding partitions later:
-- 1) Create a new partitioned table (e.g., ta.price_points_p) PARTITION BY RANGE (as_of)
-- 2) Create monthly partitions ahead (N months)
-- 3) Dual-write (optional) or migrate data
-- 4) Swap tables (rename) with a short maintenance window
--
-- Example (fresh install only):
-- DROP TABLE IF EXISTS ta.price_points CASCADE;
-- CREATE TABLE ta.price_points (
--   ... same columns as current ...
-- ) PARTITION BY RANGE (as_of);
--
-- CREATE TABLE ta.price_points_2026_02 PARTITION OF ta.price_points
--   FOR VALUES FROM ('2026-02-01') TO ('2026-03-01');
--
-- Repeat monthly.

COMMIT;
