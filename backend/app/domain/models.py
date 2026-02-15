import uuid
from sqlalchemy import Column, String, Boolean, ForeignKey, func
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID, TIMESTAMP
from app.core.database import Base

# --- 1. Identity & Tenancy ---
class User(Base):
    __tablename__ = "user"  # Matches physical table 'user'

    user_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String, unique=True, nullable=False, index=True)
    password_hash = Column(String, nullable=False)
    is_enabled = Column(Boolean, default=True)
    is_bootstrap_admin = Column(Boolean, default=False)
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())
    last_login_at = Column(TIMESTAMP(timezone=True), nullable=True)

    # Use back_populates to link to the Portfolio class
    portfolios = relationship("Portfolio", back_populates="owner")

class Portfolio(Base):
    __tablename__ = "portfolio"  # Matches physical table 'portfolio'

    portfolio_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    # FIX: Use 'user.user_id' (singular, no 'ta.' prefix)
    owner_user_id = Column(UUID(as_uuid=True), ForeignKey("user.user_id"), nullable=False)
    name = Column(String, nullable=False)
    broker = Column(String, nullable=False)
    base_currency = Column(String(3), default="GBP", nullable=False)
    
    # Mapping 'tax_profile' to the physical column 'tax_treatment'
    tax_profile = Column("tax_treatment", String, nullable=False) 
    
    is_enabled = Column(Boolean, default=True)
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())

    owner = relationship("User", back_populates="portfolios")
    constituents = relationship("PortfolioConstituent", back_populates="portfolio")

# --- 2. Registry ---
class Instrument(Base):
    __tablename__ = "instrument"

    instrument_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    isin = Column(String(12), unique=True, nullable=False, index=True)
    instrument_type = Column(String, nullable=False)
    name = Column(String, nullable=True)
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())

    listings = relationship("InstrumentListing", back_populates="instrument")

class InstrumentListing(Base):
    __tablename__ = "listing"

    listing_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    # FIX: Use 'instrument.instrument_id'
    instrument_id = Column(UUID(as_uuid=True), ForeignKey("instrument.instrument_id"), nullable=False)
    ticker = Column(String, nullable=False)
    exchange = Column(String, nullable=False)
    trading_currency = Column(String(3), nullable=False)
    quote_scale = Column(String, nullable=False) 
    is_primary = Column(Boolean, default=False)
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())

    instrument = relationship("Instrument", back_populates="listings")

# --- 3. Strategy / Portfolio Mapping ---
class Sleeve(Base):
    __tablename__ = "sleeves" # Table created by Alembic/Force Schema
    
    sleeve_code = Column(String, primary_key=True)
    name = Column(String, nullable=False)

class PortfolioConstituent(Base):
    __tablename__ = "portfolio_constituent"

    # FIX: Use singular names and no 'ta.' prefixes
    portfolio_id = Column(UUID(as_uuid=True), ForeignKey("portfolio.portfolio_id"), primary_key=True)
    listing_id = Column(UUID(as_uuid=True), ForeignKey("listing.listing_id"), primary_key=True)
    sleeve_code = Column(String, ForeignKey("sleeves.sleeve_code"), nullable=False)
    is_monitored = Column(Boolean, default=True)
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())

    portfolio = relationship("Portfolio", back_populates="constituents")