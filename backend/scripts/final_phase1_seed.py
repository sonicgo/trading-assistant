import os
import uuid
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

load_dotenv()
engine = create_engine(os.getenv("DATABASE_URL"))

# We use fixed UUIDs so the seed is consistent across fresh installs
ADMIN_ID = 'b0f91464-98f2-47f1-8856-0c89733330e8'
PORTFOLIO_ID = '23d98803-5ce7-456b-a44e-552f4857d5f6'
INSTRUMENT_ID = '550e8400-e29b-41d4-a716-446655440000'
LISTING_ID = '660e8400-e29b-41d4-a716-446655440001'

seed_sql = [
    # 1. Create Admin User (Password is 'admin')
    """INSERT INTO "user" (user_id, email, password_hash, is_bootstrap_admin) 
       VALUES (:admin_id, 'admin@example.com', 
       '$2b$12$AM7CfI2ZNYph7oV3s3pjU.KBY82ADL.v6r2bkWbb/P/qtjHf.W/8a', true)
       ON CONFLICT (email) DO NOTHING;""",
    
    # 2. Create Portfolio
    """INSERT INTO portfolio (portfolio_id, owner_user_id, name, base_currency, tax_treatment, broker)
       VALUES (:portfolio_id, :admin_id, 'SIPP', 'GBP', 'ISA', 'Manual')
       ON CONFLICT (portfolio_id) DO NOTHING;""",

    # 3. Create Instrument (Vanguard FTSE All-World UCITS ETF)
    """INSERT INTO instrument (instrument_id, isin, instrument_type, name)
       VALUES (:inst_id, 'IE00BK5BQT80', 'ETF', 'Vanguard FTSE All-World')
       ON CONFLICT (isin) DO UPDATE SET name = EXCLUDED.name RETURNING instrument_id;""",

    # 4. Create Listing (VWRP on London Stock Exchange)
    # The uq_listing_ticker_exchange constraint will protect this
    """INSERT INTO listing (listing_id, instrument_id, ticker, exchange, trading_currency, quote_scale)
       VALUES (:list_id, :inst_id, 'VWRP', 'LSE', 'GBP', 'GBP')
       ON CONFLICT ON CONSTRAINT uq_listing_ticker_exchange DO NOTHING;""",

    # 5. Map Listing to Portfolio via Sleeve (CORE)
    """INSERT INTO portfolio_constituent (portfolio_id, listing_id, sleeve_code, is_monitored)
       VALUES (:portfolio_id, :list_id, 'CORE', true)
       ON CONFLICT (portfolio_id, listing_id) DO NOTHING;"""
]

params = {
    "admin_id": ADMIN_ID,
    "portfolio_id": PORTFOLIO_ID,
    "inst_id": INSTRUMENT_ID,
    "list_id": LISTING_ID
}

try:
    with engine.connect() as conn:
        for sql in seed_sql:
            conn.execute(text(sql), params)
        conn.commit()
    print("SUCCESS: Phase 1 Data Seeded (Admin, Portfolio, VWRP, and Sleeve Mapping).")
except Exception as e:
    print(f"SEED FAILED: {e}")