# GasFlareTracker

GasFlareTracker detects refinery flare-regime changes from VIIRS/FIRMS thermal detections and shows facility-level map markers plus an event feed.

## v0.1 data scope

- Event period shown in the product: 2020.
- Internal baseline period used by the detector: 2019.
- Facility registry source: EIA Refinery Capacity Report from `data/refcap26.xlsx`.

### Known v0.1 registry limitation

`data/refcap26.xlsx` has EIA `PERIOD = 26`, so it is treated as the 2026 Refinery Capacity Report. v0.1 still evaluates and displays flare events for 2020. That means the facility registry and event period can be temporarily out of sync: facilities that opened, closed, changed operator, or changed corporate ownership between 2020 and 2026 may be represented by their 2026 registry state.

This is accepted for v0.1 as a release limitation because no 2020/2021 EIA Refinery Capacity Report file is currently checked into the repository. Before making stronger historical claims, replace `data/refcap26.xlsx` with a period-matched 2020/2021 registry or document the mismatch in the public release notes.

## License

Apache License 2.0 — see [LICENSE](LICENSE).
