import { PeriodFilter } from "#app/components/period-filter/period-filter.js";
import { RegionFilter } from "#app/components/region-filter/region-filter.js";

/**
 * Empty view for facility map
 */
export class MapEmptyView {
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
    message.className = "map-empty-view__message";
    message.textContent = "Oops, no data in chosen period or region. Pick another one.";

    const filters = document.createElement("div");
    filters.className = "map-empty-view__filters";
    filters.append(this.periodFilter.input, this.regionFilter.select);

    const panel = document.createElement("div");
    panel.className = "map-empty-view__panel";
    panel.append(message, filters);

    this.element = document.createElement("div");
    this.element.className = "map-empty-view";
    // Hidden until facility-map decides otherwise - not shown/hidden by any
    // logic in here
    this.element.hidden = true;
    this.element.append(panel);
  }
}
