import { PeriodFilter } from "#app/components/period-filter/period-filter.js";
import { RegionFilter } from "#app/components/region-filter/region-filter.js";

/**
 * Empty view for facility map
 */
export class MapEmptyState {
  /** @type {HTMLElement} */
  element;

  /** @type {PeriodFilter} */
  periodFilter;

  /** @type {RegionFilter} */
  regionFilter;

  /**
   * @param {(currentDate: string | undefined) => void} onPeriodChange - period filter change handler
   * @param {(country: string | undefined) => void} onRegionChange - region filter change handler
   */
  constructor(onPeriodChange, onRegionChange) {
    this.periodFilter = new PeriodFilter(onPeriodChange);
    this.regionFilter = new RegionFilter(onRegionChange);

    const message = document.createElement("p");
    message.className = "map-empty-state__message";
    message.textContent = "Oops, no data in chosen period or region. Pick another one.";

    const filters = document.createElement("div");
    filters.className = "map-empty-state__filters";
    filters.append(this.periodFilter.input, this.regionFilter.select);

    const panel = document.createElement("div");
    panel.className = "map-empty-state__panel";
    panel.append(message, filters);

    this.element = document.createElement("div");
    this.element.className = "map-empty-state";
    // Hidden until facility-map decides otherwise - not shown/hidden by any
    // logic in here
    this.element.hidden = true;
    this.element.append(panel);
  }
}
