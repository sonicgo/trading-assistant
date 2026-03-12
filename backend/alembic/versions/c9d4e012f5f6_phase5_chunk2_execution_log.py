"""Phase 5/6 Chunk 2: ExecutionLog for automated job tracking

Revision ID: c9d4e012f5f6
Revises: b8c3d901f4e5
Create Date: 2026-03-11 16:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'c9d4e012f5f6'
down_revision = 'b8c3d901f4e5'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'execution_logs',
        sa.Column('execution_log_id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('job_name', sa.String(), nullable=False),
        sa.Column('status', sa.String(), nullable=False),
        sa.Column('started_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('completed_at', postgresql.TIMESTAMP(timezone=True), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('meta', postgresql.JSONB(), nullable=True),
    )
    
    op.create_index('ix_execution_logs_job_name', 'execution_logs', ['job_name'])
    op.create_index('ix_execution_logs_status', 'execution_logs', ['status'])
    op.create_index('ix_execution_logs_job_started', 'execution_logs', ['job_name', sa.text('started_at desc')])
    op.create_index('ix_execution_logs_status_started', 'execution_logs', ['status', sa.text('started_at desc')])


def downgrade():
    op.drop_index('ix_execution_logs_status_started', table_name='execution_logs')
    op.drop_index('ix_execution_logs_job_started', table_name='execution_logs')
    op.drop_index('ix_execution_logs_status', table_name='execution_logs')
    op.drop_index('ix_execution_logs_job_name', table_name='execution_logs')
    op.drop_table('execution_logs')
