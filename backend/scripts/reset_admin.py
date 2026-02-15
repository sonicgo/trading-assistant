import os
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv
import sys

sys.path.append(os.getcwd())
from app.core.security import get_password_hash

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

def force_reset():
    engine = create_engine(DATABASE_URL)
    Session = sessionmaker(bind=engine)
    session = Session()

    try:
        email = "admin@example.com"
        new_password = "admin"
        hashed_password = get_password_hash(new_password)

        # Check if table is 'user' or 'users'
        # Most SQLAlchemy models default to the class name 'User' -> table 'user'
        query = text("UPDATE \"user\" SET password_hash = :hash WHERE email = :email")
        
        print(f"Attempting to update 'user' table...")
        result = session.execute(query, {"hash": hashed_password, "email": email})
        session.commit()

        if result.rowcount == 0:
            print(f"Table found, but user {email} not found. Creating user...")
            # If update fails to find a row, insert it
            insert_query = text("INSERT INTO \"user\" (user_id, email, password_hash, is_bootstrap_admin) "
                               "VALUES (gen_random_uuid(), :email, :hash, true)")
            session.execute(insert_query, {"email": email, "hash": hashed_password})
            session.commit()
            print("User created successfully.")
        else:
            print(f"SUCCESS: Password for {email} updated.")

    except Exception as e:
        print(f"FAILED: {e}")
        session.rollback()
    finally:
        session.close()

if __name__ == "__main__":
    force_reset()