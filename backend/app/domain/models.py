import uuid
from sqlalchemy import Column, String, Boolean, ForeignKey, Numeric, Date, Integer, Text, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from sqlalchemy.dialects.postgresql import UUID, JSONB, TIMESTAMP
from app.core.database import Base

# --- 1. Identity & Tenancy ---
class User(Base):
    __tablename__ = "users"
    __table_args__ = {"schema": "ta"}

    user_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String, unique=True, nullable=False)
    password_hash = Column(String, nullable=False)
    is_enabled = Column(Boolean, default=True)
    is_bootstrap_admin = Column(Boolean, default=False)
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())
    last_login_at = Column(TIMESTAMP(timezone=True), nullable=True)

    portfolios = relationship("Portfolio", back_populates="owner")

class Portfolio(Base):
    __tablename__ = "portfolios"
    __table_args__ = {"schema": "ta"}

    portfolio_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_user_id = Column(UUID(as_uuid=True), ForeignKey("ta.users.user_id"), nullable=False)
    name = Column(String, nullable=False)
    broker = Column(String, nullable=False)
    base_currency = Column(String(3), default="GBP", nullable=False)
    tax_treatment = Column(String, nullable=False) # SIPP/ISA/GIA
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())

    owner = relationship("User", back_populates="portfolios")

# --- 2. Registry ---
class Instrument(Base):
    __tablename__ = "instruments"
    __table_args__ = {"schema": "ta"}

    instrument_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    isin = Column(String(12), unique=True, nullable=False)
    instrument_type = Column(String, nullable=False)
    name = Column(String, nullable=True)
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())

    listings = relationship("InstrumentListing", back_populates="instrument")

class InstrumentListing(Base):
    __tablename__ = "instrument_listings"
    __table_args__ = {"schema": "ta"}

    listing_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    instrument_id = Column(UUID(as_uuid=True), ForeignKey("ta.instruments.instrument_id"), nullable=False)
    ticker = Column(String, nullable=False)
    exchange = Column(String, nullable=False)
    trading_currency = Column(String(3), nullable=False)
    quote_scale = Column(String, nullable=False) # GBX/GBP
    is_primary = Column(Boolean, default=False)
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())

    instrument = relationship("Instrument", back_populates="listings")

# --- 3. Strategy ---
class Sleeve(Base):
    __tablename__ = "sleeves"
    __table_args__ = {"schema": "ta"}
    
    sleeve_code = Column(String, primary_key=True)
    name = Column(String, nullable=False)

class PortfolioConstituent(Base):
    __tablename__ = "portfolio_constituents"
    __table_args__ = {"schema": "ta"}

    portfolio_id = Column(UUID(as_uuid=True), ForeignKey("ta.portfolios.portfolio_id"), primary_key=True)
    listing_id = Column(UUID(as_uuid=True), ForeignKey("ta.instrument_listings.listing_id"), primary_key=True)
    sleeve_code = Column(String, ForeignKey("ta.sleeves.sleeve_code"), nullable=False)
    is_monitored = Column(Boolean, default=True)
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())