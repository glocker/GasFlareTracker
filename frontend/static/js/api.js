/** @typedef {import("./types.js").FacilityProperties} FacilityProperties */
/** @typedef {GeoJSON.FeatureCollection<GeoJSON.Point, FacilityProperties>} FacilityCollection */

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
 * include at least: id, name, kind, operator, status.
 * @returns {Promise<FacilityCollection>}
 */
export function fetchFacilities() {
  return /** @type {Promise<FacilityCollection>} */ (getData("/api/facilities"));
}
