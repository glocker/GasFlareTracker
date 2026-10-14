# v0.1 release smoke checklist

Run this checklist against the production Render URL after migrations and the 2019–2020 backfill complete, and before sharing the demo externally.

Record the tested URL, deployment identifier, date, and tester with the release notes. A failed required check blocks the release until it is fixed and rerun.

## Test context

- Production URL:
- Deployment/commit:
- Date:
- Tester:
- Browser: latest stable Chrome or Chromium

## HTTP and static-serving checks

Set `BASE_URL` to the production origin, without a trailing slash.

```sh
export BASE_URL="https://example.onrender.com"
```

- [ ] `GET /health` returns HTTP 200 and `{"status":"ok"}`.

  ```sh
  curl --fail --show-error --silent "$BASE_URL/health"
  ```

- [ ] `GET /api/facilities?current_date=2020-12-31&country=US` returns HTTP 200, `data_ready: true`, and a non-empty GeoJSON `features` array.

  ```sh
  curl --fail --show-error --silent "$BASE_URL/api/facilities?current_date=2020-12-31&country=US"
  ```

- [ ] `GET /api/events?date_from=2020-01-01&date_to=2020-12-31` returns HTTP 200, `data_ready: true`, and an `events` array.

  ```sh
  curl --fail --show-error --silent "$BASE_URL/api/events?date_from=2020-01-01&date_to=2020-12-31"
  ```

- [ ] `GET /` returns HTTP 200 and the GasFlareTracker application page.

  ```sh
  curl --fail --show-error --silent --output /dev/null "$BASE_URL/"
  ```

- [ ] Tooling and dependency paths are not publicly served. Every request below returns HTTP 404, not 200.

  ```sh
  curl --silent --output /dev/null --write-out '%{http_code}\n' "$BASE_URL/package.json"
  curl --silent --output /dev/null --write-out '%{http_code}\n' "$BASE_URL/jsconfig.json"
  curl --silent --output /dev/null --write-out '%{http_code}\n' "$BASE_URL/node_modules/maplibre-gl/package.json"
  ```

## Browser checks

Use the latest stable Chrome or Chromium with DevTools open. Treat uncaught console errors or failed same-origin application requests as failures. OpenFreeMap remains an accepted external runtime dependency for v0.1, so its style and tile requests must also succeed during the normal-path checks.

- [ ] Open `/`; the map renders and displays one marker per facility rather than raw detection points.
- [ ] Open the event feed; 2020 events render without an API or empty-state error.
- [ ] Click an event; the map flies to that event's facility and the facility card opens with the clicked event's kind, period, score, and blind-night information.
- [ ] Select a date outside the loaded 2019–2020 coverage; the map shows the no-data state instead of stale markers or the API-error state.
- [ ] Restore a date in 2020; facility markers return and the no-data state disappears.
- [ ] Confirm the facility card is positioned at the right edge and closes with Escape and a click outside it.

## API failure-state check

This check verifies the frontend message without disrupting the production backend:

1. In Chrome DevTools, enable request blocking for `*/api/facilities*`.
2. Reload `/`.
3. Confirm the map shows the API/network error state, not the no-data or not-yet-processed state.
4. Disable request blocking and reload; confirm normal facility markers return.
5. Repeat with `*/api/events*`; confirm the event feed shows its API error state rather than an empty feed.

- [ ] Map API failure is reported as an error state.
- [ ] Event-feed API failure is reported as an error state.
- [ ] Normal behavior returns after request blocking is disabled.

## Result

- [ ] All required checks passed.
- Notes/failures:
