import os
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL")

# Raw SQL for Phase 1 Schema
tables_sql = [
    """CREATE TABLE IF NOT EXISTS "user" (
        user_id UUID PRIMARY KEY,
        email VARCHAR UNIQUE NOT NULL,
        password_hash VARCHAR NOT NULL,
        is_bootstrap_admin BOOLEAN DEFAULT FALSE,
        created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
    );""",
    """CREATE TABLE IF NOT EXISTS portfolio (
        portfolio_id UUID PRIMARY KEY,
        owner_user_id UUID REFERENCES "user"(user_id),
        name VARCHAR NOT NULL,
        base_currency VARCHAR(3) NOT NULL,
        tax_treatment VARCHAR NOT NULL,
        broker VARCHAR,
        is_enabled BOOLEAN DEFAULT TRUE
    );""",
    """CREATE TABLE IF NOT EXISTS instrument (
        instrument_id UUID PRIMARY KEY,
        isin VARCHAR(12) UNIQUE NOT NULL,
        name VARCHAR NOT NULL,
        instrument_type VARCHAR NOT NULL
    );""",
    """CREATE TABLE IF NOT EXISTS listing (
        listing_id UUID PRIMARY KEY,
        instrument_id UUID REFERENCES instrument(instrument_id),
        ticker VARCHAR NOT NULL,
        exchange VARCHAR NOT NULL,
        trading_currency VARCHAR(3) NOT NULL,
        quote_scale VARCHAR DEFAULT 'UNIT',
        is_primary BOOLEAN DEFAULT TRUE
    );""",
    """CREATE TABLE IF NOT EXISTS portfolio_constituent (
        portfolio_id UUID REFERENCES portfolio(portfolio_id),
        listing_id UUID REFERENCES listing(listing_id),
        sleeve_code VARCHAR NOT NULL,
        is_monitored BOOLEAN DEFAULT TRUE,
        PRIMARY KEY (portfolio_id, listing_id)
    );"""
]

def create_schema():
    engine = create_engine(DATABASE_URL)
    with engine.connect() as conn:
        for sql in tables_sql:
            conn.execute(text(sql))
        conn.commit()
    print("Schema Force-Created Successfully!")

if __name__ == "__main__":
    create_schema()
