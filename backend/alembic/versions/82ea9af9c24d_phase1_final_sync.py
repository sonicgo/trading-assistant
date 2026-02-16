"""phase1_final_sync
Revision ID: 82ea9af9c24d
Revises: None
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '82ea9af9c24d'
down_revision = None # Confirms this is the "Initial Revision"
branch_labels = None
depends_on = None

def upgrade():
    # 1. Identity & Tenancy
    op.create_table('user',
        sa.Column('user_id', sa.UUID(), nullable=False),
        sa.Column('email', sa.String(), nullable=False),
        sa.Column('password_hash', sa.String(), nullable=False),
        sa.Column('is_enabled', sa.Boolean(), server_default='true'),
        sa.Column('is_bootstrap_admin', sa.Boolean(), server_default='false'),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), server_default=sa.func.now()),
        sa.Column('last_login_at', sa.TIMESTAMP(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('user_id'),
        sa.UniqueConstraint('email')
    )

    op.create_table('portfolio',
        sa.Column('portfolio_id', sa.UUID(), nullable=False),
        sa.Column('owner_user_id', sa.UUID(), nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('broker', sa.String(), nullable=False),
        sa.Column('base_currency', sa.String(length=3), nullable=False),
        sa.Column('tax_treatment', sa.String(), nullable=False),
        sa.Column('is_enabled', sa.Boolean(), server_default='true'),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['owner_user_id'], ['user.user_id'], name='fk_portfolio_owner'),
        sa.PrimaryKeyConstraint('portfolio_id')
    )

    # 2. Registry
    op.create_table('instrument',
        sa.Column('instrument_id', sa.UUID(), nullable=False),
        sa.Column('isin', sa.String(length=12), nullable=False),
        sa.Column('instrument_type', sa.String(), nullable=False),
        sa.Column('name', sa.String(), nullable=True),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), server_default=sa.func.now()),
        sa.PrimaryKeyConstraint('instrument_id'),
        sa.UniqueConstraint('isin')
    )

    op.create_table('listing',
        sa.Column('listing_id', sa.UUID(), nullable=False),
        sa.Column('instrument_id', sa.UUID(), nullable=False),
        sa.Column('ticker', sa.String(), nullable=False),
        sa.Column('exchange', sa.String(), nullable=False),
        sa.Column('trading_currency', sa.String(length=3), nullable=False),
        sa.Column('quote_scale', sa.String(), nullable=False),
        sa.Column('is_primary', sa.Boolean(), server_default='false'),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['instrument_id'], ['instrument.instrument_id']),
        sa.PrimaryKeyConstraint('listing_id'),
        # NEW: Integrity protection against duplicate listings
        sa.UniqueConstraint('instrument_id', 'ticker', 'exchange', name='uq_listing_ticker_exchange')
    )

    # 3. Strategy / Portfolio Mapping
    op.create_table('sleeves',
        sa.Column('sleeve_code', sa.String(), nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.PrimaryKeyConstraint('sleeve_code')
    )

    # SEED SLEEVES (Preferred: 2.3 Option 1)
    op.bulk_insert(
        sa.table('sleeves', sa.column('sleeve_code'), sa.column('name')),
        [
            {'sleeve_code': 'CORE', 'name': 'Core Passive'},
            {'sleeve_code': 'SATELLITE', 'name': 'Satellite Alpha'},
            {'sleeve_code': 'CASH', 'name': 'Cash Buffer'},
            {'sleeve_code': 'GROWTH_SEMIS', 'name': 'Growth - Semiconductors'},
            {'sleeve_code': 'ENERGY', 'name': 'Thematic - Energy Transition'},
            {'sleeve_code': 'HEALTHCARE', 'name': 'Thematic - Healthcare Innovation'}
        ]
    )

    op.create_table('portfolio_constituent',
        sa.Column('portfolio_id', sa.UUID(), nullable=False),
        sa.Column('listing_id', sa.UUID(), nullable=False),
        sa.Column('sleeve_code', sa.String(), nullable=False),
        sa.Column('is_monitored', sa.Boolean(), server_default='true'),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['listing_id'], ['listing.listing_id']),
        sa.ForeignKeyConstraint(['portfolio_id'], ['portfolio.portfolio_id']),
        sa.ForeignKeyConstraint(['sleeve_code'], ['sleeves.sleeve_code']),
        sa.PrimaryKeyConstraint('portfolio_id', 'listing_id')
    )

def downgrade():
    op.drop_table('portfolio_constituent')
    op.drop_table('sleeves')
    op.drop_table('listing')
    op.drop_table('instrument')
    op.drop_table('portfolio')
    op.drop_table('user')