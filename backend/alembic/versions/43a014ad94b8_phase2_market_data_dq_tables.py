"""phase2_market_data_dq_tables

Phase 2 Build Playbook - Market Data + Data Quality Gate:
  - price_points: append-only time-series prices with idempotency constraint
  - fx_rates: append-only FX rates with idempotency constraint  
  - alerts: DQ events and system safety events
  - freeze_states: circuit breaker state per portfolio
  - task_runs: auditability for task executions
  - run_input_snapshots: reproducibility blobs
  - notifications: polling feed for critical events

Revision ID: 43a014ad94b8
Revises: c7d4e8f1a2b3
Create Date: 2026-02-28
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# ---------------------------------------------------------------------------
revision = "43a014ad94b8"
down_revision = "c7d4e8f1a2b3"
branch_labels = None
depends_on = None
# ---------------------------------------------------------------------------


def upgrade() -> None:
    # 1. Market Data Tables -------------------------------------------------
    
    # price_points: append-only time-series prices
    op.create_table(
        'price_points',
        sa.Column('price_point_id', sa.UUID(), nullable=False),
        sa.Column('listing_id', sa.UUID(), nullable=False),
        sa.Column('as_of', sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column('price', sa.Numeric(precision=28, scale=10), nullable=False),
        sa.Column('currency', sa.String(length=3), nullable=True),
        sa.Column('is_close', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('source_id', sa.String(), nullable=False),
        sa.Column('raw', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['listing_id'], ['listing.listing_id']),
        sa.PrimaryKeyConstraint('price_point_id'),
        sa.UniqueConstraint('listing_id', 'as_of', 'source_id', 'is_close', name='uq_price_point')
    )
    
    # Index for efficient querying by listing and time
    op.create_index(
        'ix_price_points_listing_as_of',
        'price_points',
        ['listing_id', sa.text('as_of DESC')]
    )
    
    # fx_rates: append-only FX rates
    op.create_table(
        'fx_rates',
        sa.Column('fx_rate_id', sa.UUID(), nullable=False),
        sa.Column('base_ccy', sa.String(length=3), nullable=False),
        sa.Column('quote_ccy', sa.String(length=3), nullable=False),
        sa.Column('as_of', sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column('rate', sa.Numeric(precision=28, scale=10), nullable=False),
        sa.Column('source_id', sa.String(), nullable=False),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), server_default=sa.func.now()),
        sa.PrimaryKeyConstraint('fx_rate_id'),
        sa.UniqueConstraint('base_ccy', 'quote_ccy', 'as_of', 'source_id', name='uq_fx_rate')
    )
    
    # 2. Data Quality & Safety Tables ----------------------------------------
    
    # alerts: DQ events and system safety events
    op.create_table(
        'alerts',
        sa.Column('alert_id', sa.UUID(), nullable=False),
        sa.Column('portfolio_id', sa.UUID(), nullable=False),
        sa.Column('listing_id', sa.UUID(), nullable=True),
        sa.Column('severity', sa.String(), nullable=False),
        sa.Column('rule_code', sa.String(), nullable=False),
        sa.Column('title', sa.Text(), nullable=False),
        sa.Column('message', sa.Text(), nullable=True),
        sa.Column('details', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), server_default=sa.func.now()),
        sa.Column('resolved_at', sa.TIMESTAMP(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['portfolio_id'], ['portfolio.portfolio_id']),
        sa.ForeignKeyConstraint(['listing_id'], ['listing.listing_id']),
        sa.PrimaryKeyConstraint('alert_id')
    )
    
    # Index for querying active alerts by portfolio
    op.create_index(
        'ix_alerts_portfolio_created',
        'alerts',
        ['portfolio_id', sa.text('created_at DESC')]
    )
    
    # freeze_states: circuit breaker state per portfolio
    op.create_table(
        'freeze_states',
        sa.Column('freeze_id', sa.UUID(), nullable=False),
        sa.Column('portfolio_id', sa.UUID(), nullable=False),
        sa.Column('is_frozen', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('reason_alert_id', sa.UUID(), nullable=True),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), server_default=sa.func.now()),
        sa.Column('cleared_at', sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column('cleared_by_user_id', sa.UUID(), nullable=True),
        sa.ForeignKeyConstraint(['portfolio_id'], ['portfolio.portfolio_id']),
        sa.ForeignKeyConstraint(['reason_alert_id'], ['alerts.alert_id']),
        sa.ForeignKeyConstraint(['cleared_by_user_id'], ['user.user_id']),
        sa.PrimaryKeyConstraint('freeze_id')
    )
    
    # Index for fast freeze lookup by portfolio
    op.create_index(
        'ix_freeze_states_portfolio',
        'freeze_states',
        ['portfolio_id']
    )
    
    # 3. Operations & Audit Tables -------------------------------------------
    
    # task_runs: auditability for task executions
    op.create_table(
        'task_runs',
        sa.Column('run_id', sa.UUID(), nullable=False),
        sa.Column('job_id', sa.UUID(), nullable=False),
        sa.Column('task_kind', sa.String(), nullable=False),
        sa.Column('portfolio_id', sa.UUID(), nullable=True),
        sa.Column('status', sa.String(), nullable=False),
        sa.Column('started_at', sa.TIMESTAMP(timezone=True), server_default=sa.func.now()),
        sa.Column('ended_at', sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column('summary', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.ForeignKeyConstraint(['portfolio_id'], ['portfolio.portfolio_id']),
        sa.PrimaryKeyConstraint('run_id')
    )
    
    # Index for querying runs by portfolio and time
    op.create_index(
        'ix_task_runs_portfolio_started',
        'task_runs',
        ['portfolio_id', sa.text('started_at DESC')]
    )
    
    # run_input_snapshots: reproducibility blobs
    op.create_table(
        'run_input_snapshots',
        sa.Column('run_id', sa.UUID(), nullable=False),
        sa.Column('input_json', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('input_hash', sa.String(), nullable=True),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['run_id'], ['task_runs.run_id']),
        sa.PrimaryKeyConstraint('run_id')
    )
    
    # notifications: polling feed for critical events
    op.create_table(
        'notifications',
        sa.Column('notification_id', sa.UUID(), nullable=False),
        sa.Column('owner_user_id', sa.UUID(), nullable=False),
        sa.Column('severity', sa.String(), nullable=False),
        sa.Column('title', sa.Text(), nullable=False),
        sa.Column('body', sa.Text(), nullable=True),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), server_default=sa.func.now()),
        sa.Column('read_at', sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column('meta', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.ForeignKeyConstraint(['owner_user_id'], ['user.user_id']),
        sa.PrimaryKeyConstraint('notification_id')
    )
    
    # Index for efficient notification polling
    op.create_index(
        'ix_notifications_user_created',
        'notifications',
        ['owner_user_id', sa.text('created_at DESC')]
    )


def downgrade() -> None:
    # Drop in reverse order to respect FK constraints
    op.drop_index('ix_notifications_user_created', table_name='notifications')
    op.drop_table('notifications')
    
    op.drop_table('run_input_snapshots')
    
    op.drop_index('ix_task_runs_portfolio_started', table_name='task_runs')
    op.drop_table('task_runs')
    
    op.drop_index('ix_freeze_states_portfolio', table_name='freeze_states')
    op.drop_table('freeze_states')
    
    op.drop_index('ix_alerts_portfolio_created', table_name='alerts')
    op.drop_table('alerts')
    
    op.drop_table('fx_rates')
    
    op.drop_index('ix_price_points_listing_as_of', table_name='price_points')
    op.drop_table('price_points')
