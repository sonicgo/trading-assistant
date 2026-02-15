import os
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv
import sys

sys.path.append(os.getcwd())
from app.core.security import get_password_hash

load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL")

def discover_and_reset():
    engine = create_engine(DATABASE_URL)
    Session = sessionmaker(bind=engine)
    session = Session()

    try:
        # 1. List all tables to see what we are working with
        tables_query = text("SELECT tablename FROM pg_catalog.pg_tables WHERE schemaname = 'public'")
        tables = [row[0] for row in session.execute(tables_query)]
        print(f"Tables found in database: {tables}")

        # 2. Identify the likely user table
        # We look for a table that has an 'email' column
        user_table = None
        for table in tables:
            col_query = text(f"SELECT column_name FROM information_schema.columns WHERE table_name = '{table}' AND column_name = 'email'")
            if session.execute(col_query).fetchone():
                user_table = table
                break
        
        if not user_table:
            print("Could not find a table with an 'email' column. Are migrations complete?")
            return

        print(f"Targeting table: '{user_table}'")

        # 3. Perform the update
        email = "admin@example.com"
        new_password = "admin"
        hashed_password = get_password_hash(new_password)

        update_query = text(f"UPDATE \"{user_table}\" SET password_hash = :hash WHERE email = :email")
        result = session.execute(update_query, {"hash": hashed_password, "email": email})
        session.commit()

        if result.rowcount > 0:
            print(f"SUCCESS: Password for {email} updated in table '{user_table}'.")
        else:
            print(f"User {email} not found in '{user_table}'. Please check your seed data.")

    except Exception as e:
        print(f"FAILED: {e}")
        session.rollback()
    finally:
        session.close()

if __name__ == "__main__":
    discover_and_reset()