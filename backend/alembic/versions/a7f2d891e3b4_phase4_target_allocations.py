"""Phase 4: Portfolio Policy Allocations table

Revision ID: a7f2d891e3b4
Revises: 313f551cee8c
Create Date: 2026-03-11 14:30:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'a7f2d891e3b4'
down_revision = '313f551cee8c'
branch_labels = None
depends_on = None


def upgrade():
    # Create portfolio_policy_allocations table
    op.create_table(
        'portfolio_policy_allocations',
        sa.Column('portfolio_policy_allocation_id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('portfolio_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('portfolio.portfolio_id'), nullable=False),
        sa.Column('listing_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('listing.listing_id'), nullable=False),
        sa.Column('ticker', sa.String(), nullable=False),
        sa.Column('sleeve_code', sa.String(), nullable=False),
        sa.Column('policy_role', sa.String(), nullable=False),
        sa.Column('target_weight_pct', sa.Numeric(precision=18, scale=8), nullable=True),
        sa.Column('priority_rank', sa.Integer(), nullable=True),
        sa.Column('policy_hash', sa.String(), nullable=False),
        sa.Column('created_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=False),
    )
    
    # Create unique constraint on portfolio_id, policy_hash, listing_id
    op.create_index(
        'uq_policy_allocation',
        'portfolio_policy_allocations',
        ['portfolio_id', 'policy_hash', 'listing_id'],
        unique=True
    )
    
    # Create index on portfolio_id + policy_hash for efficient lookups
    op.create_index(
        'ix_policy_allocations_portfolio_hash',
        'portfolio_policy_allocations',
        ['portfolio_id', 'policy_hash']
    )


def downgrade():
    op.drop_index('ix_policy_allocations_portfolio_hash', table_name='portfolio_policy_allocations')
    op.drop_index('uq_policy_allocation', table_name='portfolio_policy_allocations')
    op.drop_table('portfolio_policy_allocations')
