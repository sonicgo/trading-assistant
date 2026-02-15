"""phase1_final_sync

Revision ID: 82ea9af9c24d
Revises: 
Create Date: 2026-02-15

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '82ea9af9c24d'
down_revision = None
branch_labels = None
depends_on = None

def upgrade():
    # We leave this empty because the tables already exist in 'public'
    pass

def downgrade():
    pass
