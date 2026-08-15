-- =========================================================================
--  DB schema for the flare/shutdown monitor based on thermal signature
--  PostgreSQL 15+ with PostGIS
-- =========================================================================

CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS pg_trgm;   -- fuzzy search over names

-- =========================================================================
--  1. FACILITY REGISTRY
-- =========================================================================

-- The facility itself: refinery, upstream field, LNG terminal.
-- This is own entity. External sources are linked separately.
-- List of human-readable names of oil and gas facilities.
CREATE TABLE facility (
    id            bigserial PRIMARY KEY,
    name          text        NOT NULL,
    kind          text        NOT NULL,        -- refinery | upstream | lng | other
    country_iso2  char(2),
    operator      text,                         -- who operates it
    parent_owner  text,                         -- parent company
    -- point only, by design: line assets (pipelines) don't fit this model
    -- and are out of scope - a facility is a single flare-point source
    geom          geometry(Point, 4326) NOT NULL,
    -- radius within which a detection is considered to belong to the facility.
    -- a large refinery has flares spread over kilometers, a small field doesn't
    match_radius_m integer    NOT NULL DEFAULT 3000,
    notes         text,
    created_at    timestamptz NOT NULL DEFAULT now(),
    updated_at    timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX facility_geom_gix ON facility USING gist (geom);
CREATE INDEX facility_name_trgm ON facility USING gin (name gin_trgm_ops);
CREATE INDEX facility_kind_idx ON facility (kind, country_iso2);

-- Links to external registries. A single facility can appear in several
-- sources under different ids and different names - we store all of them,
-- noting where each came from. This is the "data provenance" interviewers
-- like to ask about.
CREATE TABLE facility_external_ref (
    id          bigserial PRIMARY KEY,
    facility_id bigint NOT NULL REFERENCES facility(id) ON DELETE CASCADE,
    source      text   NOT NULL,   -- gem_goit | gem_goget | osm | eprtr | wikipedia
    external_id text   NOT NULL,
    name_in_src text,
    fetched_at  timestamptz NOT NULL DEFAULT now(),
    raw         jsonb,             -- the original source row as-is, in case someone asks "where did this come from?"
    UNIQUE (source, external_id)
);

CREATE INDEX facility_ext_facility_idx ON facility_external_ref (facility_id);

-- =========================================================================
--  2. FETCH REGIONS
-- =========================================================================

-- FIRMS serves data per bounding box. Downloading one request per facility
-- would be 500 facilities x 14 years / 5-day windows = half a million requests.
-- So facilities are grouped into regions, and one request covers dozens of them.
CREATE TABLE fetch_region (
    id         bigserial PRIMARY KEY,
    name       text NOT NULL,
    bbox       geometry(Polygon, 4326) NOT NULL,
    active     boolean NOT NULL DEFAULT true
);

CREATE INDEX fetch_region_gix ON fetch_region USING gist (bbox);

-- Fetch log: what was downloaded, for which dates, when, how many rows.
-- Needed for incremental fetching and to know where the gaps are.
CREATE TABLE fetch_log (
    id          bigserial PRIMARY KEY,
    region_id   bigint NOT NULL REFERENCES fetch_region(id),
    source      text   NOT NULL,       -- VIIRS_SNPP_SP | VIIRS_NOAA20_SP | ...
    day_from    date   NOT NULL,
    day_to      date   NOT NULL,
    fetched_at  timestamptz NOT NULL DEFAULT now(),
    n_rows      integer,
    status      text   NOT NULL,       -- ok | error
    error       text,
    UNIQUE (region_id, source, day_from, day_to, fetched_at)
);

CREATE INDEX fetch_log_lookup ON fetch_log (region_id, source, day_from);

-- =========================================================================
--  3. RAW DETECTIONS  (the biggest table)
-- =========================================================================

-- Partitioned by date. Without this, a query like "show me 2021" would
-- scan all 14 years. With it, only the needed partitions are touched.
CREATE TABLE detection (
    id            bigserial,
    acq_ts        timestamptz NOT NULL,     -- observation timestamp, UTC
    night_date    date        NOT NULL,     -- "night" in the facility's local time,
                                            -- NOT the same as the UTC date: an
                                            -- observation at 02:00 UTC over
                                            -- Texas is actually the previous
                                            -- evening
    geom          geometry(Point, 4326) NOT NULL,
    frp           real,                     -- fire radiative power, MW
    bright_ti4    real,
    bright_ti5    real,
    daynight      char(1),                  -- D | N
    confidence    text,                     -- l | n | h  (VIIRS uses letters)
    satellite     text        NOT NULL,     -- N | 1 | 2
    source        text        NOT NULL,     -- FIRMS product
    scan          real,
    track         real,
    facility_id   bigint,                   -- filled in during the matching step
    dist_m        real,                     -- distance to the matched facility
    fetch_id      bigint,                   -- which fetch run this row came from
    PRIMARY KEY (id, night_date)
) PARTITION BY RANGE (night_date);

-- Partitions by year. Create ahead of time or via a script.
CREATE TABLE detection_2020 PARTITION OF detection
    FOR VALUES FROM ('2020-01-01') TO ('2021-01-01');
CREATE TABLE detection_2021 PARTITION OF detection
    FOR VALUES FROM ('2021-01-01') TO ('2022-01-01');
CREATE TABLE detection_2022 PARTITION OF detection
    FOR VALUES FROM ('2022-01-01') TO ('2023-01-01');
-- ... remaining years follow the same pattern

CREATE INDEX detection_geom_gix  ON detection USING gist (geom);
CREATE INDEX detection_facility_idx ON detection (facility_id, night_date);
-- BRIN instead of btree: rows are inserted in increasing date order,
-- so the index ends up hundreds of times smaller
CREATE INDEX detection_date_brin ON detection USING brin (night_date);

-- Guards against duplicate inserts when the loader restarts.
-- Same detection = same satellite, same time, same point.
CREATE UNIQUE INDEX detection_dedup
    ON detection (satellite, acq_ts, geom, night_date);

-- =========================================================================
--  4. NIGHTLY FACILITY SNAPSHOT  (working table for the detector and the map)
-- =========================================================================

-- Rollup of "one facility - one night". This is what feeds the chart and
-- the event calculations. The map NEVER queries detection directly.
CREATE TABLE facility_night (
    facility_id bigint NOT NULL REFERENCES facility(id) ON DELETE CASCADE,
    night_date  date   NOT NULL,
    n_det       integer NOT NULL DEFAULT 0,
    frp_sum     real    NOT NULL DEFAULT 0,
    frp_max     real    NOT NULL DEFAULT 0,
    -- key field: was it even visible. Distinguishes "not flaring" from "not observed".
    -- Computed from neighbors: if no other facility within N km was visible that
    -- night either, it's cloud cover, not a shutdown.
    observable  boolean,
    n_neighbors_seen smallint,   -- how many neighboring facilities were visible that night
    PRIMARY KEY (facility_id, night_date)
);

CREATE INDEX facility_night_date_idx ON facility_night (night_date);

-- =========================================================================
--  5. REGIONAL OBSERVABILITY
-- =========================================================================

-- Same idea, but aggregated by region - used to show "the region was
-- blind that night" and to filter events accordingly.
CREATE TABLE region_night (
    region_id        bigint NOT NULL REFERENCES fetch_region(id),
    night_date        date   NOT NULL,
    n_facilities      smallint NOT NULL,   -- how many facilities are in the region
    n_facilities_seen smallint NOT NULL,   -- how many of them produced a detection
    blind             boolean  NOT NULL,   -- n_facilities_seen <= threshold
    PRIMARY KEY (region_id, night_date)
);

-- =========================================================================
--  6. FLARE EVENTS  (what this is all for)
-- =========================================================================

-- Detector version. We can answer "why was there a flare event
-- yesterday but not today" - the algorithm may have changed.
CREATE TABLE detector_version (
    id          bigserial PRIMARY KEY,
    name        text NOT NULL,
    params      jsonb NOT NULL,     -- thresholds, windows, everything that's configurable
    code_sha    text,               -- commit the computation was run with
    created_at  timestamptz NOT NULL DEFAULT now()
);

-- Computed internally by comparing facility_night to its own rolling baseline
-- (see peak_frp/baseline_frp/score below) - not sourced from any external
-- registry or incident feed. GEM/OSM/etc. only populate facility and
-- facility_external_ref, so detections can be matched to a named object;
-- they carry no operational events themselves.
CREATE TABLE flare_event (
    id            bigserial PRIMARY KEY,
    facility_id   bigint NOT NULL REFERENCES facility(id) ON DELETE CASCADE,
    detector_id   bigint NOT NULL REFERENCES detector_version(id),
    kind          text   NOT NULL,   -- spike | regime_up | regime_down
    start_date    date   NOT NULL,
    end_date      date,              -- NULL = still ongoing
    peak_frp      real,
    baseline_frp  real,              -- level before the event
    score         real,              -- how many times above its baseline
    -- how many nights within the event window were blind. If many,
    -- the event is unreliable, and that should be surfaced to the user
    blind_nights  smallint NOT NULL DEFAULT 0,
    detected_at   timestamptz NOT NULL DEFAULT now(),
    UNIQUE (facility_id, detector_id, kind, start_date)
);

CREATE INDEX flare_event_facility_idx ON flare_event (facility_id, start_date DESC);
CREATE INDEX flare_event_recent_idx ON flare_event (start_date DESC);

-- External confirmation: a news article, an EIA report, a maintenance
-- announcement.
CREATE TABLE flare_event_confirmation (
    id            bigserial PRIMARY KEY,
    flare_event_id bigint NOT NULL REFERENCES flare_event(id) ON DELETE CASCADE,
    source_kind   text NOT NULL,      -- news | eia_padd | operator_notice | alsi
    url           text,
    published     date,
    note          text,
    -- confirms or contradicts
    verdict       text NOT NULL       -- confirms | contradicts | unclear
);

-- =========================================================================
--  7. MATCHING DETECTIONS TO FACILITIES
-- =========================================================================

-- Solves the Port Arthur problem: two refineries 1.5 km apart, a 9 km
-- bounding box, a detection lands in both. The correct answer is to
-- assign it to the NEAREST one, not to both.
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
            ORDER BY d.geom <-> f.geom     -- <-> uses the GiST index
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

-- =========================================================================
--  8. REBUILDING NIGHTLY SNAPSHOTS
-- =========================================================================

CREATE OR REPLACE FUNCTION rebuild_facility_nights(p_from date, p_to date)
RETURNS void AS $$
BEGIN
    -- first the rollup itself (night observations only)
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

    -- then fill in the zeros: the night existed, no detection occurred
    INSERT INTO facility_night (facility_id, night_date, n_det, frp_sum, frp_max)
    SELECT f.id, d.night_date, 0, 0, 0
      FROM facility f
     CROSS JOIN generate_series(p_from, p_to - 1, interval '1 day') AS d(night_date)
    ON CONFLICT (facility_id, night_date) DO NOTHING;
END;
$$ LANGUAGE plpgsql;

-- =========================================================================
--  9. MAP VIEW
-- =========================================================================

-- Current state of each facility - what gets drawn on the map.
-- Materialized, refreshed once a day after ingest.
CREATE MATERIALIZED VIEW facility_status AS
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
           WHEN fn.last_seen < current_date - 30         THEN 'silent'
           WHEN fn.frp_30d_median > 2 * fn.frp_365d_median THEN 'elevated'
           WHEN fn.frp_30d_median < 0.5 * fn.frp_365d_median THEN 'reduced'
           ELSE 'normal'
       END AS status
  FROM facility f
  LEFT JOIN LATERAL (
      SELECT max(night_date) FILTER (WHERE n_det > 0) AS last_seen,
             percentile_cont(0.5) WITHIN GROUP (ORDER BY frp_sum)
                 FILTER (WHERE night_date > current_date - 30)  AS frp_30d_median,
             percentile_cont(0.5) WITHIN GROUP (ORDER BY frp_sum)
                 FILTER (WHERE night_date > current_date - 365) AS frp_365d_median
        FROM facility_night
       WHERE facility_id = f.id
  ) fn ON true;

CREATE UNIQUE INDEX facility_status_id ON facility_status (id);
CREATE INDEX facility_status_gix ON facility_status USING gist (geom);

-- REFRESH MATERIALIZED VIEW CONCURRENTLY facility_status;
