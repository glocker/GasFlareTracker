"""Add 2019 detection partition for baseline backfill

Revision ID: 0004
Revises: 0003
Create Date: 2026-09-30
"""

from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        DO $$
        BEGIN
            IF to_regclass('public.detection_2019') IS NULL THEN
                IF EXISTS (
                    SELECT 1
                      FROM detection_default
                     WHERE night_date >= DATE '2019-01-01'
                       AND night_date <  DATE '2020-01-01'
                     LIMIT 1
                ) THEN
                    RAISE EXCEPTION '%',
                        'detection_default already contains 2019 rows; '
                        || 'move them before creating detection_2019 partition';
                END IF;

                CREATE TABLE detection_2019 PARTITION OF detection
                    FOR VALUES FROM ('2019-01-01') TO ('2020-01-01');
            END IF;
        END $$;
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS detection_2019;")
