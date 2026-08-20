"""Update facility_status_asof for last date in table

Revision ID: 0002
Revises: 0001
Create Date: 2026-08-20
"""

from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.execute("""
    CREATE OR REPLACE FUNCTION facility_status_asof(p_asof date)
    RETURNS TABLE (
        id               bigint,
        name             text,
        kind             text,
        country_iso2     char(2),
        operator         text,
        geom             geometry(Point, 4326),
        last_seen        date,
        frp_30d_median   real,
        frp_365d_median  real,
        status           text
    ) AS $$
    SELECT f.id,
           f.name,
           f.kind,
           f.country_iso2,
           f.operator,
           f.geom,
           fn.last_seen,
           fn.frp_30d_median,
           fn.frp_365d_median,
           CASE
               WHEN fn.last_seen IS NULL                     THEN 'no_data'
               WHEN fn.last_seen < p_asof - 30         THEN 'silent'
               WHEN fn.frp_30d_median > 2 * fn.frp_365d_median THEN 'elevated'
               WHEN fn.frp_30d_median < 0.5 * fn.frp_365d_median THEN 'reduced'
               ELSE 'normal'
           END AS status
      FROM facility f
      LEFT JOIN LATERAL (
          SELECT max(night_date) FILTER (WHERE n_det > 0) AS last_seen,
                 percentile_cont(0.5) WITHIN GROUP (ORDER BY frp_sum)
                     FILTER (WHERE night_date > p_asof - 30)  AS frp_30d_median,
                 percentile_cont(0.5) WITHIN GROUP (ORDER BY frp_sum)
                     FILTER (WHERE night_date > p_asof - 365) AS frp_365d_median
            FROM facility_night
           WHERE facility_id = f.id
      ) fn ON true;
      $$ LANGUAGE sql STABLE;
      """)

def downgrade() -> None:
    op.execute("DROP FUNCTION IF EXISTS facility_status_asof(date);")
