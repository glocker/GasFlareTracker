/** @typedef {import("./types.js").FacilityProperties} FacilityProperties */
/** @typedef {import("./types.js").FlareEvent} FlareEvent */
/**
 * @typedef {GeoJSON.FeatureCollection<GeoJSON.Point, FacilityProperties> & { as_of: string }} FacilityCollection
 */

/**
 * Fetches data from URL in params and returns JSON
 * @param {string} url
 * @returns {Promise<unknown>}
 */
async function getData(url) {
  const result = await fetch(url);
  if (!result.ok) throw new Error(`${result.status} ${result.statusText}`);
  return result.json();
}

/**
 * GET /api/facilities -> GeoJSON FeatureCollection of Point features, one per
 * facility, sourced from `facility_status`. Each feature's `properties` must
 * include at least: id, name, kind, operator, status. `as_of` is the date the
 * statuses were actually computed for - current_date echoed back, or the
 * backend's own default when omitted.
 * @param {string | undefined} currentDate selected date in date input
 * @returns {Promise<FacilityCollection>}
 */
export function fetchFacilities(currentDate) {
  const url = new URLSearchParams();

  if (currentDate) {
    url.set('current_date', currentDate);
  }

  return /** @type {Promise<FacilityCollection>} */ (getData(`/api/facilities?${url}`));
}

/**
 * GET /api/events -> flare_event rows joined with facility name, newest first.
 * @param {string | undefined} [dateFrom] - inclusive lower bound on start_date
 * @param {string | undefined} [dateTo] - inclusive upper bound on start_date
 * @returns {Promise<{ events: FlareEvent[] }>}
 */
export function fetchEvents(dateFrom, dateTo) {
  const url = new URLSearchParams();

  if (dateFrom) {
    url.set('date_from', dateFrom);
  }
  if (dateTo) {
    url.set('date_to', dateTo);
  }

  return /** @type {Promise<{ events: FlareEvent[] }>} */ (getData(`/api/events?${url}`));
}
