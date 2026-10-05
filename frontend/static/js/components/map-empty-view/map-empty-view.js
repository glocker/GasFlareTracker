import { PeriodFilter } from "#app/components/period-filter/period-filter.js";
import { RegionFilter } from "#app/components/region-filter/region-filter.js";

const STATE_MESSAGES = {
  empty: "Oops, no data in chosen period or region. Pick another one.",
  error: "Could not load facility data. Try again later.",
  "not-ready": "Facility data has not been processed yet.",
};

/** @typedef {keyof typeof STATE_MESSAGES} MapEmptyViewState */

/**
 * Status overlay for facility map
 */
export class MapEmptyView {
  /** @type {HTMLElement} */
  element;

  /** @type {HTMLParagraphElement} */
  message;

  /** @type {HTMLDivElement} */
  filters;

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

    this.message = document.createElement("p");
    this.message.className = "map-empty-view__message";
    this.message.textContent = STATE_MESSAGES.empty;

    this.filters = document.createElement("div");
    this.filters.className = "map-empty-view__filters";
    this.filters.append(this.periodFilter.input, this.regionFilter.select);

    const panel = document.createElement("div");
    panel.className = "map-empty-view__panel";
    panel.append(this.message, this.filters);

    this.element = document.createElement("div");
    this.element.className = "map-empty-view";
    // Hidden until facility-map decides otherwise - not shown/hidden by any
    // logic in here
    this.element.hidden = true;
    this.element.append(panel);
  }

  /**
   * Shows overlay in requested state
   * @param {MapEmptyViewState} state - UI state to display
   */
  show(state) {
    this.message.textContent = STATE_MESSAGES[state];
    this.filters.hidden = state !== "empty";
    this.element.hidden = false;
  }

  /**
   * Hides overlay
   */
  hide() {
    this.element.hidden = true;
  }
}
