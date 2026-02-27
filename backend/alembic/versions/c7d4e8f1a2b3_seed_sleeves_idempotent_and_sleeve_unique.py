"""seed_sleeves_idempotent_and_sleeve_unique

Step 3.4 of Phase 1 Build Playbook:
  - Re-seed sleeves idempotently (INSERT ... ON CONFLICT DO NOTHING).
    Safe to run on a fresh DB or one already seeded by the baseline migration.
  - Add unique constraint on portfolio_constituent(portfolio_id, sleeve_code)
    to enforce the "one listing per sleeve per portfolio" invariant at the DB
    level, consistent with the application-level enforcement in the bulk-upsert
    endpoint.

Revision ID: c7d4e8f1a2b3
Revises: 82ea9af9c24d
Create Date: 2026-02-27
"""

from alembic import op

# ---------------------------------------------------------------------------
revision = "c7d4e8f1a2b3"
down_revision = "82ea9af9c24d"
branch_labels = None
depends_on = None
# ---------------------------------------------------------------------------


def upgrade() -> None:
    # 1. Idempotent sleeve seed ─────────────────────────────────────────────
    #    Safe on a fresh DB and on one already populated by migration 82ea9af9c24d.
    op.execute(
        """
        INSERT INTO sleeves (sleeve_code, name) VALUES
            ('CORE',         'Core Passive'),
            ('SATELLITE',    'Satellite Alpha'),
            ('CASH',         'Cash Buffer'),
            ('GROWTH_SEMIS', 'Growth - Semiconductors'),
            ('ENERGY',       'Thematic - Energy Transition'),
            ('HEALTHCARE',   'Thematic - Healthcare Innovation')
        ON CONFLICT (sleeve_code) DO NOTHING
        """
    )

    # 2. One-listing-per-sleeve-per-portfolio constraint ─────────────────────
    #    Pair with the application-level eviction logic in the bulk-upsert
    #    endpoint to give belt-and-suspenders protection.
    op.create_unique_constraint(
        "uq_portfolio_constituent_portfolio_sleeve",
        "portfolio_constituent",
        ["portfolio_id", "sleeve_code"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_portfolio_constituent_portfolio_sleeve",
        "portfolio_constituent",
        type_="unique",
    )
    # NOTE: we do NOT roll back the sleeve seed — removing reference data in
    # a downgrade would violate FK constraints if constituents exist.
