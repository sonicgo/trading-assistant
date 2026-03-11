import os
import uuid
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

load_dotenv()
engine = create_engine(os.getenv("DATABASE_URL"))

TEST_TICKERS = [
    ("CSH2", "IE00BCRY6557", "iShares Core MSCI Pacific ex-Japan UCITS ETF"),
    ("SEMI", "IE00B4MCH366", "iShares MSCI World Information Technology UCITS ETF"),
    ("WLDS", "IE00BYX5K108", "iShares Core MSCI World UCITS ETF USD (Acc)"),
    ("IGL5", "IE00B3VWN518", "iShares UK Gilts 0-5yr UCITS ETF"),
    ("VWRP", "IE00BK5BQT80", "Vanguard FTSE All-World UCITS ETF"),
    ("XWES", "IE00BGPK9703", "Xtrackers MSCI World ESG UCITS ETF"),
    ("XWHS", "IE00BJYHR264", "Xtrackers MSCI World Health Care UCITS ETF"),
]

def seed_test_tickers():
    try:
        with engine.connect() as conn:
            for ticker, isin, name in TEST_TICKERS:
                instrument_id = str(uuid.uuid4())
                listing_id = str(uuid.uuid4())
                
                instrument_sql = """
                    INSERT INTO instrument (instrument_id, isin, instrument_type, name)
                    VALUES (:inst_id, :isin, 'ETF', :name)
                    ON CONFLICT (isin) DO UPDATE SET name = EXCLUDED.name
                    RETURNING instrument_id;
                """
                result = conn.execute(
                    text(instrument_sql),
                    {"inst_id": instrument_id, "isin": isin, "name": name}
                )
                row = result.fetchone()
                if row:
                    actual_inst_id = row[0]
                else:
                    existing = conn.execute(
                        text("SELECT instrument_id FROM instrument WHERE isin = :isin"),
                        {"isin": isin}
                    )
                    actual_inst_id = existing.fetchone()[0]
                
                check_sql = """
                    SELECT listing_id FROM listing 
                    WHERE ticker = :ticker AND exchange = 'LSE'
                """
                existing_listing = conn.execute(text(check_sql), {"ticker": ticker}).fetchone()
                
                if not existing_listing:
                    listing_sql = """
                        INSERT INTO listing (
                            listing_id, instrument_id, ticker, exchange, 
                            trading_currency, quote_scale, is_primary
                        )
                        VALUES (
                            :list_id, :inst_id, :ticker, 'LSE', 
                            'GBP', 'GBX', true
                        );
                    """
                    conn.execute(
                        text(listing_sql),
                        {
                            "list_id": listing_id,
                            "inst_id": actual_inst_id,
                            "ticker": ticker
                        }
                    )
                print(f"Seeded: {ticker}")
            
            conn.commit()
        
        print(f"\nSUCCESS: All {len(TEST_TICKERS)} test tickers seeded successfully.")
        
    except Exception as e:
        print(f"SEED FAILED: {e}")
        raise

if __name__ == "__main__":
    seed_test_tickers()
