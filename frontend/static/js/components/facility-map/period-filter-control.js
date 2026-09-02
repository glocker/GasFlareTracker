import { PeriodFilter } from "#app/components/period-filter/period-filter.js";

/** @typedef {import("maplibre-gl").Map} MapLibreMap */
/** @typedef {import("maplibre-gl").IControl} MapLibreIControl */

/**
 * MapLibre IControl to render PeriodFilter on map corner
 * @implements {MapLibreIControl}
 */
export class PeriodFilterControl {
  /** @type {PeriodFilter} */
  filter;

  /** @type {HTMLElement} */
  container;

  /**
   * @param {(currentDate: string | undefined) => void} handlerCallback - called
   * with the selected date (or undefined if cleared), debounced
   */
  constructor(handlerCallback) {
    this.handlerCallback = handlerCallback;
  }

  /**
   * Called by MapLibre when control is added to map
   * @param {MapLibreMap} map - map this control is being added to
   * @returns {HTMLElement} control's container element
   */
  onAdd(map) {
    this.filter = new PeriodFilter(this.handlerCallback);

    // needs the maplibregl-ctrl class or clicks fall through to canvas
    this.container = document.createElement("div");
    this.container.className = "maplibregl-ctrl";
    this.container.appendChild(this.filter.input);

    return this.container;
  }

  /**
   * Sets displayed date without triggering change handler
   * @param {string} currentDate - ISO date to display
   */
  setValue(currentDate) {
    this.filter.setValue(currentDate);
  }

  /**
   * Called by MapLibre when control is removed from map
   * @param {MapLibreMap} map - this control is being removed from
   */
  onRemove(map) {
    this.container.remove();
  }
}
