"""
Trading Assistant Domain Models
Phase 1 + Phase 2 (Market Data + Data Quality Gate)
"""
import uuid
from sqlalchemy import Column, String, Boolean, ForeignKey, func, UniqueConstraint, Numeric, Text, Index, CheckConstraint, Integer
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
    policy_allocations = relationship("PortfolioPolicyAllocation", back_populates="portfolio")

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

# --- 3B. Policy Allocation (Phase 4) ---
class PortfolioPolicyAllocation(Base):
    __tablename__ = "portfolio_policy_allocations"
    
    portfolio_policy_allocation_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    portfolio_id = Column(UUID(as_uuid=True), ForeignKey("portfolio.portfolio_id"), nullable=False)
    listing_id = Column(UUID(as_uuid=True), ForeignKey("listing.listing_id"), nullable=False)
    ticker = Column(String, nullable=False)
    sleeve_code = Column(String, nullable=False)
    policy_role = Column(String, nullable=False)
    target_weight_pct = Column(Numeric(precision=18, scale=8), nullable=True)
    priority_rank = Column(Integer, nullable=True)
    policy_hash = Column(String, nullable=False)
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())
    
    portfolio = relationship("Portfolio", back_populates="policy_allocations")
    
    __table_args__ = (
        UniqueConstraint('portfolio_id', 'policy_hash', 'listing_id', name='uq_policy_allocation'),
    )

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


class ExecutionLog(Base):
    """Audit log for automated scheduled job executions (Phase 5/6)."""
    __tablename__ = "execution_logs"
    
    execution_log_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    job_name = Column(String, nullable=False, index=True)
    status = Column(String, nullable=False, index=True)
    started_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now())
    completed_at = Column(TIMESTAMP(timezone=True), nullable=True)
    error_message = Column(Text, nullable=True)
    meta = Column(JSONB, nullable=True)
    
    __table_args__ = (
        Index('ix_execution_logs_job_started', 'job_name', started_at.desc()),
        Index('ix_execution_logs_status_started', 'status', started_at.desc()),
    )


class NotificationConfig(Base):
    """Per-portfolio notification configuration for external alerts (Phase 5/6)."""
    __tablename__ = "notification_configs"
    
    notification_config_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    portfolio_id = Column(UUID(as_uuid=True), ForeignKey("portfolio.portfolio_id"), nullable=False, unique=True)
    apprise_url = Column(Text, nullable=True)  # Apprise-compatible URL (e.g., discord://, mailto://)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())
    updated_at = Column(TIMESTAMP(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # Relationships
    portfolio = relationship("Portfolio")


# --- 7. Book of Record / Ledger (Phase 3) ---

class LedgerBatch(Base):
    """Atomic posting unit that groups one or more ledger entries."""
    __tablename__ = "ledger_batches"
    
    batch_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    portfolio_id = Column(UUID(as_uuid=True), ForeignKey("portfolio.portfolio_id"), nullable=False)
    submitted_by_user_id = Column(UUID(as_uuid=True), ForeignKey("user.user_id"), nullable=False)
    source = Column(String, nullable=False)  # UI, CSV_IMPORT, REVERSAL
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())
    note = Column(Text, nullable=True)
    meta = Column(JSONB, nullable=True)
    idempotency_key = Column(String, nullable=True)
    
    # Relationships
    portfolio = relationship("Portfolio")
    submitted_by = relationship("User")
    entries = relationship("LedgerEntry", back_populates="batch", cascade="all, delete-orphan")
    
    __table_args__ = (
        Index('ix_ledger_batches_portfolio_created', 'portfolio_id', 'created_at'),
    )


class LedgerEntry(Base):
    """Append-only economic events that change cash and/or holdings."""
    __tablename__ = "ledger_entries"
    
    entry_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    batch_id = Column(UUID(as_uuid=True), ForeignKey("ledger_batches.batch_id"), nullable=False)
    portfolio_id = Column(UUID(as_uuid=True), ForeignKey("portfolio.portfolio_id"), nullable=False)
    entry_kind = Column(String, nullable=False)  # CONTRIBUTION, BUY, SELL, ADJUSTMENT, REVERSAL
    effective_at = Column(TIMESTAMP(timezone=True), nullable=False)
    listing_id = Column(UUID(as_uuid=True), ForeignKey("listing.listing_id"), nullable=True)
    quantity_delta = Column(Numeric(precision=28, scale=10), nullable=True)  # Signed: positive=buy/add, negative=sell/remove
    net_cash_delta_gbp = Column(Numeric(precision=28, scale=10), nullable=False)  # Signed final GBP cash impact
    fee_gbp = Column(Numeric(precision=28, scale=10), nullable=True)  # Only for BUY/SELL
    book_cost_delta_gbp = Column(Numeric(precision=28, scale=10), nullable=True)  # For ADJUSTMENT/REVERSAL
    reversal_of_entry_id = Column(UUID(as_uuid=True), ForeignKey("ledger_entries.entry_id"), nullable=True)
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())
    note = Column(Text, nullable=True)
    meta = Column(JSONB, nullable=True)

    __table_args__ = (
        Index('ix_ledger_entries_portfolio_effective', 'portfolio_id', 'effective_at'),
        Index('ix_ledger_entries_batch', 'batch_id'),
        Index('ix_ledger_entries_portfolio_listing', 'portfolio_id', 'listing_id', 'effective_at'),
        Index('ix_ledger_entries_reversal', 'reversal_of_entry_id'),
    )

    # Relationships
    batch = relationship("LedgerBatch", back_populates="entries")
    portfolio = relationship("Portfolio")
    listing = relationship("InstrumentListing")
    reversal_of = relationship("LedgerEntry", remote_side=[entry_id])
    
    # Constraints
    __table_args__ = (
        CheckConstraint(
            "entry_kind IN ('CONTRIBUTION', 'BUY', 'SELL', 'ADJUSTMENT', 'REVERSAL')",
            name='ck_ledger_entry_kind'
        ),
        CheckConstraint(
            "fee_gbp IS NULL OR fee_gbp >= 0",
            name='ck_ledger_entry_fee_non_negative'
        ),
    )


class CashSnapshot(Base):
    """Fast current-state cash read per portfolio."""
    __tablename__ = "cash_snapshots"
    
    portfolio_id = Column(UUID(as_uuid=True), ForeignKey("portfolio.portfolio_id"), primary_key=True)
    balance_gbp = Column(Numeric(precision=28, scale=10), nullable=False, default=0)
    updated_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now())
    last_entry_id = Column(UUID(as_uuid=True), ForeignKey("ledger_entries.entry_id"), nullable=True)
    version_no = Column(Numeric(precision=20, scale=0), nullable=False, default=0)  # Optimistic locking
    
    # Relationships
    portfolio = relationship("Portfolio")
    last_entry = relationship("LedgerEntry")


class HoldingSnapshot(Base):
    """Fast current-state holdings read per portfolio/listing."""
    __tablename__ = "holding_snapshots"
    
    portfolio_id = Column(UUID(as_uuid=True), ForeignKey("portfolio.portfolio_id"), primary_key=True)
    listing_id = Column(UUID(as_uuid=True), ForeignKey("listing.listing_id"), primary_key=True)
    quantity = Column(Numeric(precision=28, scale=10), nullable=False, default=0)
    book_cost_gbp = Column(Numeric(precision=28, scale=10), nullable=False, default=0)
    avg_cost_gbp = Column(Numeric(precision=28, scale=10), nullable=False, default=0)
    updated_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now())
    last_entry_id = Column(UUID(as_uuid=True), ForeignKey("ledger_entries.entry_id"), nullable=True)
    version_no = Column(Numeric(precision=20, scale=0), nullable=False, default=0)  # Optimistic locking
    
    # Relationships
    portfolio = relationship("Portfolio")
    listing = relationship("InstrumentListing")
    last_entry = relationship("LedgerEntry")
    
    # Constraints
    __table_args__ = (
        CheckConstraint(
            "quantity >= 0",
            name='ck_holding_snapshot_quantity_non_negative'
        ),
        CheckConstraint(
            "(quantity = 0 AND book_cost_gbp = 0 AND avg_cost_gbp = 0) OR quantity > 0",
            name='ck_holding_snapshot_cost_consistency'
        ),
    )


# --- 8. Recommendations & Audit (Phase 5) ---

class RecommendationBatch(Base):
    """A batch of trade recommendations generated by the engine."""
    __tablename__ = "recommendation_batches"

    recommendation_batch_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    portfolio_id = Column(UUID(as_uuid=True), ForeignKey("portfolio.portfolio_id"), nullable=False)
    status = Column(String, nullable=False, default="PENDING")  # PENDING, EXECUTED, EXECUTED_PARTIAL, IGNORED
    generated_at = Column(TIMESTAMP(timezone=True), server_default=func.now(), nullable=False)
    executed_at = Column(TIMESTAMP(timezone=True), nullable=True)
    ignored_at = Column(TIMESTAMP(timezone=True), nullable=True)
    closed_by_user_id = Column(UUID(as_uuid=True), ForeignKey("user.user_id"), nullable=True)
    execution_summary = Column(JSONB, nullable=True)
    run_id = Column(UUID(as_uuid=True), ForeignKey("task_runs.run_id"), nullable=True)
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now(), nullable=False)

    # Relationships
    portfolio = relationship("Portfolio")
    closed_by = relationship("User")
    lines = relationship("RecommendationLine", back_populates="batch", cascade="all, delete-orphan")
    run = relationship("TaskRun")

    __table_args__ = (
        Index('ix_recommendation_batches_portfolio_status', 'portfolio_id', 'status'),
        Index('ix_recommendation_batches_generated', generated_at.desc()),
    )


class RecommendationLine(Base):
    """Individual trade line within a recommendation batch."""
    __tablename__ = "recommendation_lines"

    recommendation_line_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    recommendation_batch_id = Column(UUID(as_uuid=True), ForeignKey("recommendation_batches.recommendation_batch_id"), nullable=False)
    listing_id = Column(UUID(as_uuid=True), ForeignKey("listing.listing_id"), nullable=False)
    action = Column(String, nullable=False)  # BUY, SELL
    proposed_quantity = Column(Numeric(precision=28, scale=10), nullable=False)
    proposed_price_gbp = Column(Numeric(precision=28, scale=10), nullable=False)
    proposed_value_gbp = Column(Numeric(precision=28, scale=10), nullable=False)
    proposed_fee_gbp = Column(Numeric(precision=28, scale=10), nullable=False, default=0)
    status = Column(String, nullable=False, default="PROPOSED")  # PROPOSED, EXECUTED, PARTIAL, IGNORED
    executed_quantity = Column(Numeric(precision=28, scale=10), nullable=True)
    executed_price_gbp = Column(Numeric(precision=28, scale=10), nullable=True)
    executed_value_gbp = Column(Numeric(precision=28, scale=10), nullable=True)
    executed_fee_gbp = Column(Numeric(precision=28, scale=10), nullable=True)
    ledger_entry_id = Column(UUID(as_uuid=True), ForeignKey("ledger_entries.entry_id"), nullable=True)
    execution_note = Column(Text, nullable=True)
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now(), nullable=False)

    # Relationships
    batch = relationship("RecommendationBatch", back_populates="lines")
    listing = relationship("InstrumentListing")
    ledger_entry = relationship("LedgerEntry")

    __table_args__ = (
        CheckConstraint(
            "action IN ('BUY', 'SELL')",
            name='ck_recommendation_line_action'
        ),
        CheckConstraint(
            "status IN ('PROPOSED', 'EXECUTED', 'PARTIAL', 'IGNORED')",
            name='ck_recommendation_line_status'
        ),
    )


class AuditEvent(Base):
    """Durable append-only audit trail for user/system actions (Phase 5)."""
    __tablename__ = "audit_events"

    audit_event_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    portfolio_id = Column(UUID(as_uuid=True), ForeignKey("portfolio.portfolio_id"), nullable=True)
    actor_user_id = Column(UUID(as_uuid=True), ForeignKey("user.user_id"), nullable=True)
    event_type = Column(String, nullable=False, index=True)  # RECOMMENDATION_EXECUTED, RECOMMENDATION_IGNORED, etc.
    entity_type = Column(String, nullable=False)  # RECOMMENDATION_BATCH, LEDGER_ENTRY, etc.
    entity_id = Column(UUID(as_uuid=True), nullable=False)
    occurred_at = Column(TIMESTAMP(timezone=True), server_default=func.now(), nullable=False)
    summary = Column(Text, nullable=False)
    details = Column(JSONB, nullable=True)
    correlation_id = Column(String, nullable=True)

    # Relationships
    portfolio = relationship("Portfolio")
    actor = relationship("User")

    __table_args__ = (
        Index('ix_audit_events_portfolio_occurred', 'portfolio_id', occurred_at.desc()),
        Index('ix_audit_events_entity', 'entity_type', 'entity_id', occurred_at.desc()),
        Index('ix_audit_events_actor', 'actor_user_id', occurred_at.desc()),
    )
