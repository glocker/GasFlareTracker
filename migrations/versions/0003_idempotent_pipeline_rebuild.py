"""Make pipeline rebuild steps idempotent

Revision ID: 0003
Revises: 0002
Create Date: 2026-09-28
"""

from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("DROP FUNCTION IF EXISTS match_detections(date, date);")
    op.execute(
        """
        CREATE OR REPLACE FUNCTION match_detections(
            p_from date,
            p_to date,
            p_force boolean DEFAULT false
        )
        RETURNS integer AS $$
        DECLARE
            n integer;
        BEGIN
            IF p_force THEN
                UPDATE detection
                   SET facility_id = NULL,
                       dist_m      = NULL
                 WHERE night_date >= p_from
                   AND night_date <  p_to;
            END IF;

            WITH nearest AS (
                SELECT d.id,
                       d.night_date,
                       f.id   AS facility_id,
                       ST_Distance(d.geom::geography, f.geom::geography) AS dist_m
                FROM detection d
                CROSS JOIN LATERAL (
                    SELECT f.id, f.geom, f.match_radius_m
                    FROM facility f
                    WHERE ST_DWithin(d.geom::geography, f.geom::geography, f.match_radius_m)
                    ORDER BY d.geom <-> f.geom
                    LIMIT 1
                ) f
                WHERE d.night_date >= p_from
                  AND d.night_date <  p_to
                  AND d.facility_id IS NULL
            )
            UPDATE detection d
               SET facility_id = n.facility_id,
                   dist_m      = n.dist_m
              FROM nearest n
             WHERE d.id = n.id AND d.night_date = n.night_date;

            GET DIAGNOSTICS n = ROW_COUNT;
            RETURN n;
        END;
        $$ LANGUAGE plpgsql;
        """
    )
    op.execute(
        """
        CREATE OR REPLACE FUNCTION rebuild_facility_nights(p_from date, p_to date)
        RETURNS void AS $$
        BEGIN
            DELETE FROM facility_night
             WHERE night_date >= p_from
               AND night_date <  p_to;

            INSERT INTO facility_night (facility_id, night_date, n_det, frp_sum, frp_max)
            SELECT facility_id,
                   night_date,
                   count(*),
                   coalesce(sum(frp), 0),
                   coalesce(max(frp), 0)
              FROM detection
             WHERE facility_id IS NOT NULL
               AND daynight = 'N'
               AND night_date >= p_from AND night_date < p_to
             GROUP BY facility_id, night_date;

            INSERT INTO facility_night (facility_id, night_date, n_det, frp_sum, frp_max)
            SELECT f.id, d.night_date::date, 0, 0, 0
              FROM facility f
             CROSS JOIN generate_series(p_from, p_to - 1, interval '1 day') AS d(night_date)
            ON CONFLICT (facility_id, night_date) DO NOTHING;
        END;
        $$ LANGUAGE plpgsql;
        """
    )


def downgrade() -> None:
    op.execute("DROP FUNCTION IF EXISTS match_detections(date, date, boolean);")
    op.execute(
        """
        CREATE OR REPLACE FUNCTION match_detections(p_from date, p_to date)
        RETURNS integer AS $$
        DECLARE
            n integer;
        BEGIN
            WITH nearest AS (
                SELECT d.id,
                       d.night_date,
                       f.id   AS facility_id,
                       ST_Distance(d.geom::geography, f.geom::geography) AS dist_m
                FROM detection d
                CROSS JOIN LATERAL (
                    SELECT f.id, f.geom, f.match_radius_m
                    FROM facility f
                    WHERE ST_DWithin(d.geom::geography, f.geom::geography, f.match_radius_m)
                    ORDER BY d.geom <-> f.geom
                    LIMIT 1
                ) f
                WHERE d.night_date >= p_from
                  AND d.night_date <  p_to
                  AND d.facility_id IS NULL
            )
            UPDATE detection d
               SET facility_id = n.facility_id,
                   dist_m      = n.dist_m
              FROM nearest n
             WHERE d.id = n.id AND d.night_date = n.night_date;

            GET DIAGNOSTICS n = ROW_COUNT;
            RETURN n;
        END;
        $$ LANGUAGE plpgsql;
        """
    )
    op.execute(
        """
        CREATE OR REPLACE FUNCTION rebuild_facility_nights(p_from date, p_to date)
        RETURNS void AS $$
        BEGIN
            INSERT INTO facility_night (facility_id, night_date, n_det, frp_sum, frp_max)
            SELECT facility_id,
                   night_date,
                   count(*),
                   coalesce(sum(frp), 0),
                   coalesce(max(frp), 0)
              FROM detection
             WHERE facility_id IS NOT NULL
               AND daynight = 'N'
               AND night_date >= p_from AND night_date < p_to
             GROUP BY facility_id, night_date
            ON CONFLICT (facility_id, night_date) DO UPDATE
               SET n_det   = EXCLUDED.n_det,
                   frp_sum = EXCLUDED.frp_sum,
                   frp_max = EXCLUDED.frp_max;

            INSERT INTO facility_night (facility_id, night_date, n_det, frp_sum, frp_max)
            SELECT f.id, d.night_date, 0, 0, 0
              FROM facility f
             CROSS JOIN generate_series(p_from, p_to - 1, interval '1 day') AS d(night_date)
            ON CONFLICT (facility_id, night_date) DO NOTHING;
        END;
        $$ LANGUAGE plpgsql;
        """
    )
