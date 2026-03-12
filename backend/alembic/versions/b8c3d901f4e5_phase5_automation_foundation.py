"""Phase 5/6: Notification Config and Automation Foundation

Revision ID: b8c3d901f4e5
Revises: a7f2d891e3b4
Create Date: 2026-03-11 15:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'b8c3d901f4e5'
down_revision = 'a7f2d891e3b4'
branch_labels = None
depends_on = None


def upgrade():
    # Create notification_configs table
    op.create_table(
        'notification_configs',
        sa.Column('notification_config_id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('portfolio_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('portfolio.portfolio_id'), nullable=False, unique=True),
        sa.Column('apprise_url', sa.Text(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.text('true')),
        sa.Column('created_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=False),
    )
    
    # Create index on portfolio_id for efficient lookups
    op.create_index(
        'ix_notification_configs_portfolio_id',
        'notification_configs',
        ['portfolio_id'],
        unique=True
    )
    
    # Create index on is_active for filtering active configs
    op.create_index(
        'ix_notification_configs_is_active',
        'notification_configs',
        ['is_active']
    )


def downgrade():
    op.drop_index('ix_notification_configs_is_active', table_name='notification_configs')
    op.drop_index('ix_notification_configs_portfolio_id', table_name='notification_configs')
    op.drop_table('notification_configs')
