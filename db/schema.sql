-- =========================================================================
--  DB schema for the flare/shutdown monitor based on thermal signature
--  PostgreSQL 15+ with PostGIS
-- =========================================================================

CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS pg_trgm;   -- fuzzy search over names

-- =========================================================================
--  1. SITE REGISTRY
-- =========================================================================

-- The site itself: refinery, upstream field, LNG terminal.
-- This is own entity. External sources are linked separately.
CREATE TABLE site (
    id            bigserial PRIMARY KEY,
    name          text        NOT NULL,
    kind          text        NOT NULL,        -- refinery | upstream | lng | steel | other
    country_iso2  char(2),
    operator      text,                         -- who operates it
    parent_owner  text,                         -- parent company
    geom          geometry(Point, 4326) NOT NULL,
    -- radius within which a detection is considered to belong to the site.
    -- a large refinery has flares spread over kilometers, a small field doesn't
    match_radius_m integer    NOT NULL DEFAULT 3000,
    notes         text,
    created_at    timestamptz NOT NULL DEFAULT now(),
    updated_at    timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX site_geom_gix ON site USING gist (geom);
CREATE INDEX site_name_trgm ON site USING gin (name gin_trgm_ops);
CREATE INDEX site_kind_idx ON site (kind, country_iso2);

-- Links to external registries. A single site can appear in several
-- sources under different ids and different names - we store all of them,
-- noting where each came from. This is the "data provenance" interviewers
-- like to ask about.
CREATE TABLE site_external_ref (
    id          bigserial PRIMARY KEY,
    site_id     bigint NOT NULL REFERENCES site(id) ON DELETE CASCADE,
    source      text   NOT NULL,   -- gem_goit | gem_goget | osm | eprtr | wikipedia
    external_id text   NOT NULL,
    name_in_src text,
    fetched_at  timestamptz NOT NULL DEFAULT now(),
    raw         jsonb,             -- the original source row as-is, in case someone asks "where did this come from?"
    UNIQUE (source, external_id)
);

CREATE INDEX site_ext_site_idx ON site_external_ref (site_id);

-- =========================================================================
--  2. FETCH REGIONS
-- =========================================================================

-- FIRMS serves data per bounding box. Downloading one request per site
-- would be 500 sites x 14 years / 5-day windows = half a million requests.
-- So sites are grouped into regions, and one request covers dozens of them.
CREATE TABLE fetch_region (
    id         bigserial PRIMARY KEY,
    name       text NOT NULL,
    bbox       geometry(Polygon, 4326) NOT NULL,
    active     boolean NOT NULL DEFAULT true
);

CREATE INDEX fetch_region_gix ON fetch_region USING gist (bbox);

-- Ingest log: what was downloaded, for which dates, when, how many rows.
-- Needed for incremental fetching and to know where the gaps are.
CREATE TABLE ingest_log (
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

CREATE INDEX ingest_log_lookup ON ingest_log (region_id, source, day_from);

-- =========================================================================
--  3. RAW DETECTIONS  (the biggest table)
-- =========================================================================

-- Partitioned by date. Without this, a query like "show me 2021" would
-- scan all 14 years. With it, only the needed partitions are touched.
CREATE TABLE detection (
    id            bigserial,
    acq_ts        timestamptz NOT NULL,     -- observation timestamp, UTC
    night_date    date        NOT NULL,     -- "night" in the site's local time,
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
    site_id       bigint,                   -- filled in during the matching step
    dist_m        real,                     -- distance to the matched site
    ingest_id     bigint,                   -- which ingest run this row came from
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
CREATE INDEX detection_site_idx  ON detection (site_id, night_date);
-- BRIN instead of btree: rows are inserted in increasing date order,
-- so the index ends up hundreds of times smaller
CREATE INDEX detection_date_brin ON detection USING brin (night_date);

-- Guards against duplicate inserts when the loader restarts.
-- Same detection = same satellite, same time, same point.
CREATE UNIQUE INDEX detection_dedup
    ON detection (satellite, acq_ts, geom, night_date);

-- =========================================================================
--  4. NIGHTLY SITE SNAPSHOT  (working table for the detector and the map)
-- =========================================================================

-- Rollup of "one site - one night". This is what feeds the chart and
-- the event calculations. The map NEVER queries detection directly.
CREATE TABLE site_night (
    site_id     bigint NOT NULL REFERENCES site(id) ON DELETE CASCADE,
    night_date  date   NOT NULL,
    n_det       integer NOT NULL DEFAULT 0,
    frp_sum     real    NOT NULL DEFAULT 0,
    frp_max     real    NOT NULL DEFAULT 0,
    -- key field: was it even visible. Distinguishes "not flaring" from "not observed".
    -- Computed from neighbors: if no other site within N km was visible that
    -- night either, it's cloud cover, not a shutdown.
    observable  boolean,
    n_neighbors_seen smallint,   -- how many neighboring sites were visible that night
    PRIMARY KEY (site_id, night_date)
);

CREATE INDEX site_night_date_idx ON site_night (night_date);

-- =========================================================================
--  5. REGIONAL OBSERVABILITY
-- =========================================================================

-- Same idea, but aggregated by region - used to show "the region was
-- blind that night" and to filter events accordingly.
CREATE TABLE region_night (
    region_id     bigint NOT NULL REFERENCES fetch_region(id),
    night_date    date   NOT NULL,
    n_sites       smallint NOT NULL,   -- how many sites are in the region
    n_sites_seen  smallint NOT NULL,   -- how many of them produced a detection
    blind         boolean  NOT NULL,   -- n_sites_seen <= threshold
    PRIMARY KEY (region_id, night_date)
);

-- =========================================================================
--  6. EVENTS  (what this is all for)
-- =========================================================================

-- Detector version. We can answer "why was there an event
-- yesterday but not today" - the algorithm may have changed.
CREATE TABLE detector_version (
    id          bigserial PRIMARY KEY,
    name        text NOT NULL,
    params      jsonb NOT NULL,     -- thresholds, windows, everything that's configurable
    code_sha    text,               -- commit the computation was run with
    created_at  timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE event (
    id            bigserial PRIMARY KEY,
    site_id       bigint NOT NULL REFERENCES site(id) ON DELETE CASCADE,
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
    UNIQUE (site_id, detector_id, kind, start_date)
);

CREATE INDEX event_site_idx ON event (site_id, start_date DESC);
CREATE INDEX event_recent_idx ON event (start_date DESC);

-- External confirmation: a news article, an EIA report, a maintenance
-- announcement.
CREATE TABLE event_confirmation (
    id          bigserial PRIMARY KEY,
    event_id    bigint NOT NULL REFERENCES event(id) ON DELETE CASCADE,
    source_kind text NOT NULL,      -- news | eia_padd | operator_notice | alsi
    url         text,
    published   date,
    note        text,
    -- confirms or contradicts
    verdict     text NOT NULL       -- confirms | contradicts | unclear
);

-- =========================================================================
--  7. MATCHING DETECTIONS TO SITES
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
               s.id   AS site_id,
               ST_Distance(d.geom::geography, s.geom::geography) AS dist_m
        FROM detection d
        CROSS JOIN LATERAL (
            SELECT s.id, s.geom, s.match_radius_m
            FROM site s
            WHERE ST_DWithin(d.geom::geography, s.geom::geography, s.match_radius_m)
            ORDER BY d.geom <-> s.geom     -- <-> uses the GiST index
            LIMIT 1
        ) s
        WHERE d.night_date >= p_from
          AND d.night_date <  p_to
          AND d.site_id IS NULL
    )
    UPDATE detection d
       SET site_id = n.site_id,
           dist_m  = n.dist_m
      FROM nearest n
     WHERE d.id = n.id AND d.night_date = n.night_date;

    GET DIAGNOSTICS n = ROW_COUNT;
    RETURN n;
END;
$$ LANGUAGE plpgsql;

-- =========================================================================
--  8. REBUILDING NIGHTLY SNAPSHOTS
-- =========================================================================

CREATE OR REPLACE FUNCTION rebuild_site_nights(p_from date, p_to date)
RETURNS void AS $$
BEGIN
    -- first the rollup itself (night observations only)
    INSERT INTO site_night (site_id, night_date, n_det, frp_sum, frp_max)
    SELECT site_id,
           night_date,
           count(*),
           coalesce(sum(frp), 0),
           coalesce(max(frp), 0)
      FROM detection
     WHERE site_id IS NOT NULL
       AND daynight = 'N'
       AND night_date >= p_from AND night_date < p_to
     GROUP BY site_id, night_date
    ON CONFLICT (site_id, night_date) DO UPDATE
       SET n_det   = EXCLUDED.n_det,
           frp_sum = EXCLUDED.frp_sum,
           frp_max = EXCLUDED.frp_max;

    -- then fill in the zeros: the night existed, no detection occurred
    INSERT INTO site_night (site_id, night_date, n_det, frp_sum, frp_max)
    SELECT s.id, d.night_date, 0, 0, 0
      FROM site s
     CROSS JOIN generate_series(p_from, p_to - 1, interval '1 day') AS d(night_date)
    ON CONFLICT (site_id, night_date) DO NOTHING;
END;
$$ LANGUAGE plpgsql;

-- =========================================================================
--  9. MAP VIEW
-- =========================================================================

-- Current state of each site - what gets drawn on the map.
-- Materialized, refreshed once a day after ingest.
CREATE MATERIALIZED VIEW site_status AS
SELECT s.id,
       s.name,
       s.kind,
       s.country_iso2,
       s.operator,
       s.geom,
       sn.last_seen,
       sn.frp_30d_median,
       sn.frp_365d_median,
       CASE
           WHEN sn.last_seen IS NULL                     THEN 'no_data'
           WHEN sn.last_seen < current_date - 30         THEN 'silent'
           WHEN sn.frp_30d_median > 2 * sn.frp_365d_median THEN 'elevated'
           WHEN sn.frp_30d_median < 0.5 * sn.frp_365d_median THEN 'reduced'
           ELSE 'normal'
       END AS status
  FROM site s
  LEFT JOIN LATERAL (
      SELECT max(night_date) FILTER (WHERE n_det > 0) AS last_seen,
             percentile_cont(0.5) WITHIN GROUP (ORDER BY frp_sum)
                 FILTER (WHERE night_date > current_date - 30)  AS frp_30d_median,
             percentile_cont(0.5) WITHIN GROUP (ORDER BY frp_sum)
                 FILTER (WHERE night_date > current_date - 365) AS frp_365d_median
        FROM site_night
       WHERE site_id = s.id
  ) sn ON true;

CREATE UNIQUE INDEX site_status_id ON site_status (id);
CREATE INDEX site_status_gix ON site_status USING gist (geom);

-- REFRESH MATERIALIZED VIEW CONCURRENTLY site_status;
