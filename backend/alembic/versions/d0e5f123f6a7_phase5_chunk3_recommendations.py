"""Phase 5 Chunk 3: Recommendations and Audit Events

Revision ID: d0e5f123f6a7
Revises: c9d4e012f5f6
Create Date: 2026-03-11 17:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'd0e5f123f6a7'
down_revision = 'c9d4e012f5f6'
branch_labels = None
depends_on = None


def upgrade():
    # Create recommendation_batches table
    op.create_table(
        'recommendation_batches',
        sa.Column('recommendation_batch_id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('portfolio_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('portfolio.portfolio_id'), nullable=False),
        sa.Column('status', sa.String(), nullable=False, server_default='PENDING'),
        sa.Column('generated_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('executed_at', postgresql.TIMESTAMP(timezone=True), nullable=True),
        sa.Column('ignored_at', postgresql.TIMESTAMP(timezone=True), nullable=True),
        sa.Column('closed_by_user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('user.user_id'), nullable=True),
        sa.Column('execution_summary', postgresql.JSONB(), nullable=True),
        sa.Column('run_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('task_runs.run_id'), nullable=True),
        sa.Column('created_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=False),
    )
    
    op.create_index('ix_recommendation_batches_portfolio_status', 'recommendation_batches', ['portfolio_id', 'status'])
    op.create_index('ix_recommendation_batches_generated', 'recommendation_batches', [sa.text('generated_at desc')])
    
    # Create recommendation_lines table
    op.create_table(
        'recommendation_lines',
        sa.Column('recommendation_line_id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('recommendation_batch_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('recommendation_batches.recommendation_batch_id'), nullable=False),
        sa.Column('listing_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('listing.listing_id'), nullable=False),
        sa.Column('action', sa.String(), nullable=False),
        sa.Column('proposed_quantity', sa.Numeric(precision=28, scale=10), nullable=False),
        sa.Column('proposed_price_gbp', sa.Numeric(precision=28, scale=10), nullable=False),
        sa.Column('proposed_value_gbp', sa.Numeric(precision=28, scale=10), nullable=False),
        sa.Column('proposed_fee_gbp', sa.Numeric(precision=28, scale=10), nullable=False, server_default='0'),
        sa.Column('status', sa.String(), nullable=False, server_default='PROPOSED'),
        sa.Column('executed_quantity', sa.Numeric(precision=28, scale=10), nullable=True),
        sa.Column('executed_price_gbp', sa.Numeric(precision=28, scale=10), nullable=True),
        sa.Column('executed_value_gbp', sa.Numeric(precision=28, scale=10), nullable=True),
        sa.Column('executed_fee_gbp', sa.Numeric(precision=28, scale=10), nullable=True),
        sa.Column('ledger_entry_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('ledger_entries.entry_id'), nullable=True),
        sa.Column('execution_note', sa.Text(), nullable=True),
        sa.Column('created_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=False),
    )
    
    # Create audit_events table
    op.create_table(
        'audit_events',
        sa.Column('audit_event_id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('portfolio_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('portfolio.portfolio_id'), nullable=True),
        sa.Column('actor_user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('user.user_id'), nullable=True),
        sa.Column('event_type', sa.String(), nullable=False),
        sa.Column('entity_type', sa.String(), nullable=False),
        sa.Column('entity_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('occurred_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('summary', sa.Text(), nullable=False),
        sa.Column('details', postgresql.JSONB(), nullable=True),
        sa.Column('correlation_id', sa.String(), nullable=True),
    )
    
    op.create_index('ix_audit_events_event_type', 'audit_events', ['event_type'])
    op.create_index('ix_audit_events_portfolio_occurred', 'audit_events', ['portfolio_id', sa.text('occurred_at desc')])
    op.create_index('ix_audit_events_entity', 'audit_events', ['entity_type', 'entity_id', sa.text('occurred_at desc')])
    op.create_index('ix_audit_events_actor', 'audit_events', ['actor_user_id', sa.text('occurred_at desc')])


def downgrade():
    op.drop_index('ix_audit_events_actor', table_name='audit_events')
    op.drop_index('ix_audit_events_entity', table_name='audit_events')
    op.drop_index('ix_audit_events_portfolio_occurred', table_name='audit_events')
    op.drop_index('ix_audit_events_event_type', table_name='audit_events')
    op.drop_table('audit_events')
    op.drop_table('recommendation_lines')
    op.drop_index('ix_recommendation_batches_generated', table_name='recommendation_batches')
    op.drop_index('ix_recommendation_batches_portfolio_status', table_name='recommendation_batches')
    op.drop_table('recommendation_batches')
