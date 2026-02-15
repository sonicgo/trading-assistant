import os
import sys
from dotenv import load_dotenv
from sqlalchemy import create_engine

# Add current directory to path
sys.path.append(os.getcwd())

from app.core.database import Base
# Import models so SQLAlchemy knows they exist
from app.models.user import User
from app.models.portfolio import Portfolio, PortfolioConstituent
from app.models.instrument import Instrument, Listing

load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL")

def create_schema():
    print(f"Connecting to: {DATABASE_URL}")
    engine = create_engine(DATABASE_URL)
    
    print("Creating all tables defined in models...")
    Base.metadata.create_all(bind=engine)
    print("Schema created successfully!")

if __name__ == "__main__":
    create_schema()
