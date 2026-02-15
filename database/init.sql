-- Trading Assistant Initial Schema (PDM v2)
-- All timestamps UTC, UUIDv7 keys, JSONB for payloads.

CREATE SCHEMA IF NOT EXISTS ta;

-- Users
CREATE TABLE IF NOT EXISTS ta.users (
  user_id uuid PRIMARY KEY,
  email text NOT NULL UNIQUE,
  is_enabled boolean DEFAULT true,
  created_at timestamptz DEFAULT now()
);

-- Portfolios
CREATE TABLE IF NOT EXISTS ta.portfolios (
  portfolio_id uuid PRIMARY KEY,
  owner_user_id uuid REFERENCES ta.users(user_id),
  name text NOT NULL,
  base_currency char(3) DEFAULT 'GBP',
  created_at timestamptz DEFAULT now()
);

-- (Placeholder: Full schema_v2.sql should be pasted here in production)
-- For Phase 0, we just ensure the DB starts.
