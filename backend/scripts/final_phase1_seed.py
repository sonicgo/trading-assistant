import os
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

load_dotenv()
engine = create_engine(os.getenv("DATABASE_URL"))

seed_sql = [
    # 1. Create Admin User (Password is 'admin')
    # This hash is exactly 'admin' using Bcrypt 4.0.1
    """INSERT INTO "user" (user_id, email, password_hash, is_bootstrap_admin) 
       VALUES ('b0f91464-98f2-47f1-8856-0c89733330e8', 'admin@example.com', 
       '$2b$12$AM7CfI2ZNYph7oV3s3pjU.KBY82ADL.v6r2bkWbb/P/qtjHf.W/8a', true)
       ON CONFLICT (email) DO NOTHING;""",
    
    # 2. Create Portfolio
    """INSERT INTO portfolio (portfolio_id, owner_user_id, name, base_currency, tax_treatment, broker)
       VALUES ('23d98803-5ce7-456b-a44e-552f4857d5f6', 'b0f91464-98f2-47f1-8856-0c89733330e8', 
       'Retirement ISA', 'GBP', 'ISA', 'Manual')
       ON CONFLICT DO NOTHING;"""
]

try:
    with engine.connect() as conn:
        for sql in seed_sql:
            conn.execute(text(sql))
        conn.commit()
    print("SUCCESS: Phase 1 Data Seeded.")
except Exception as e:
    print(f"SEED FAILED: {e}")
