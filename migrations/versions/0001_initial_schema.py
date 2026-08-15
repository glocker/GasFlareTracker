"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-08-15
"""

from pathlib import Path

from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None

SCHEMA_SQL = Path(__file__).resolve().parents[2] / "db" / "schema.sql"


def upgrade() -> None:
    # db/schema.sql stays the readable source of truth; this migration just
    # applies it verbatim so it's tracked by Alembic like any other change.
    op.execute(SCHEMA_SQL.read_text())


def downgrade() -> None:
    # Explicit drops, not "DROP SCHEMA public CASCADE": alembic_version lives
    # in public too, and dropping the whole schema takes it out from under
    # Alembic's own bookkeeping mid-migration (verified - it does, and the
    # DELETE FROM alembic_version step right after fails outright).
    # detection's yearly/default partitions come down with it via CASCADE.
    op.execute(
        """
        DROP MATERIALIZED VIEW IF EXISTS facility_status CASCADE;
        DROP FUNCTION IF EXISTS rebuild_facility_nights(date, date);
        DROP FUNCTION IF EXISTS match_detections(date, date);
        DROP TABLE IF EXISTS flare_event_confirmation CASCADE;
        DROP TABLE IF EXISTS flare_event CASCADE;
        DROP TABLE IF EXISTS detector_version CASCADE;
        DROP TABLE IF EXISTS region_night CASCADE;
        DROP TABLE IF EXISTS facility_night CASCADE;
        DROP TABLE IF EXISTS detection CASCADE;
        DROP TABLE IF EXISTS fetch_log CASCADE;
        DROP TABLE IF EXISTS fetch_region CASCADE;
        DROP TABLE IF EXISTS facility_external_ref CASCADE;
        DROP TABLE IF EXISTS facility CASCADE;
        """
    )
