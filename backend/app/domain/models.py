"""
Trading Assistant Domain Models
Phase 1 + Phase 2 (Market Data + Data Quality Gate)
"""
import uuid
from sqlalchemy import Column, String, Boolean, ForeignKey, func, UniqueConstraint, Numeric, Text
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID, TIMESTAMP, JSONB
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

# --- 4. Market Data (Phase 2) ---

class PricePoint(Base):
    """Append-only time-series prices for each listing."""
    __tablename__ = "price_points"
    
    price_point_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    listing_id = Column(UUID(as_uuid=True), ForeignKey("listing.listing_id"), nullable=False)
    as_of = Column(TIMESTAMP(timezone=True), nullable=False)
    price = Column(Numeric(precision=28, scale=10), nullable=False)
    currency = Column(String(3), nullable=True)  # Provider-reported if available
    is_close = Column(Boolean, nullable=False, default=False)
    source_id = Column(String, nullable=False)
    raw = Column(JSONB, nullable=True)  # Optional: raw provider payload
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())
    
    # Idempotency: unique constraint prevents duplicates
    __table_args__ = (
        UniqueConstraint('listing_id', 'as_of', 'source_id', 'is_close', name='uq_price_point'),
    )

class FxRate(Base):
    """Append-only FX rates for validation and valuation."""
    __tablename__ = "fx_rates"
    
    fx_rate_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    base_ccy = Column(String(3), nullable=False)
    quote_ccy = Column(String(3), nullable=False)
    as_of = Column(TIMESTAMP(timezone=True), nullable=False)
    rate = Column(Numeric(precision=28, scale=10), nullable=False)
    source_id = Column(String, nullable=False)
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())
    
    # Idempotency: unique constraint prevents duplicates
    __table_args__ = (
        UniqueConstraint('base_ccy', 'quote_ccy', 'as_of', 'source_id', name='uq_fx_rate'),
    )

# --- 5. Data Quality & Safety (Phase 2) ---

class Alert(Base):
    """Durable record of DQ events or system safety events."""
    __tablename__ = "alerts"
    
    alert_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    portfolio_id = Column(UUID(as_uuid=True), ForeignKey("portfolio.portfolio_id"), nullable=False)
    listing_id = Column(UUID(as_uuid=True), ForeignKey("listing.listing_id"), nullable=True)
    severity = Column(String, nullable=False)  # INFO/WARN/CRITICAL
    rule_code = Column(String, nullable=False)  # e.g., DQ_GBX_SCALE, DQ_STALE_CLOSE
    title = Column(Text, nullable=False)
    message = Column(Text, nullable=True)
    details = Column(JSONB, nullable=True)  # thresholds, observed values, etc.
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())
    resolved_at = Column(TIMESTAMP(timezone=True), nullable=True)

class FreezeState(Base):
    """Circuit breaker state for a portfolio."""
    __tablename__ = "freeze_states"
    
    freeze_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    portfolio_id = Column(UUID(as_uuid=True), ForeignKey("portfolio.portfolio_id"), nullable=False)
    is_frozen = Column(Boolean, nullable=False, default=False)
    reason_alert_id = Column(UUID(as_uuid=True), ForeignKey("alerts.alert_id"), nullable=True)
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())
    cleared_at = Column(TIMESTAMP(timezone=True), nullable=True)
    cleared_by_user_id = Column(UUID(as_uuid=True), ForeignKey("user.user_id"), nullable=True)

# --- 6. Operations & Audit (Phase 2) ---

class TaskRun(Base):
    """Auditability and reproducibility for task executions."""
    __tablename__ = "task_runs"
    
    run_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    job_id = Column(UUID(as_uuid=True), nullable=False)  # From queue message
    task_kind = Column(String, nullable=False)  # e.g., PRICE_REFRESH
    portfolio_id = Column(UUID(as_uuid=True), ForeignKey("portfolio.portfolio_id"), nullable=True)
    status = Column(String, nullable=False)  # SUCCESS / FROZEN / FAILED
    started_at = Column(TIMESTAMP(timezone=True), server_default=func.now())
    ended_at = Column(TIMESTAMP(timezone=True), nullable=True)
    summary = Column(JSONB, nullable=True)  # counts, warnings, rule hits

class RunInputSnapshot(Base):
    """Reproducibility blob for task runs (kept 12 months)."""
    __tablename__ = "run_input_snapshots"
    
    run_id = Column(UUID(as_uuid=True), ForeignKey("task_runs.run_id"), primary_key=True)
    input_json = Column(JSONB, nullable=False)  # listing_ids, provider, thresholds, etc.
    input_hash = Column(String, nullable=True)  # Stable hash for dedupe/debug
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())

class Notification(Base):
    """Polling feed for critical events."""
    __tablename__ = "notifications"
    
    notification_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_user_id = Column(UUID(as_uuid=True), ForeignKey("user.user_id"), nullable=False)
    severity = Column(String, nullable=False)  # INFO/WARN/CRITICAL
    title = Column(Text, nullable=False)
    body = Column(Text, nullable=True)
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())
    read_at = Column(TIMESTAMP(timezone=True), nullable=True)
    meta = Column(JSONB, nullable=True)  # references: portfolio_id, alert_id, run_id
