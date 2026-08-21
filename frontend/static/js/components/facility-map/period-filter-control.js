import { debounce } from "#app/debounce.js";

/** @typedef {import("maplibre-gl").Map} MapLibreMap */
/** @typedef {import("maplibre-gl").IControl} MapLibreIControl */

/**
 * MapLibre IControl that renders date input on map corner
 * @implements {MapLibreIControl}
 */
export class PeriodFilterControl {
  /** @type {HTMLInputElement} */
  input;

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
   * Called by MapLibre when the control is added to the map.
   * Builds the input and wraps handlerCallback in a single debounced instance.
   * @param {MapLibreMap} map - the map this control is being added to
   * @returns {HTMLElement} the control's container element
   */
  onAdd(map) {
    this.input = document.createElement("input");
    this.input.setAttribute("type", "date");

    // needs the maplibregl-ctrl class or clicks fall through to canvas
    this.container = document.createElement("div");
    this.container.className = "maplibregl-ctrl";
    this.container.appendChild(this.input);

    // Wrap once here, not per-event - debounce needs one shared timer across calls
    this.handlerCallback = debounce(this.handlerCallback, 1000);

    this.input.addEventListener("change", () => {
      this.handlerCallback(this.input.value || undefined);
    });

    return this.container;
  }

  /**
   * Sets displayed date without triggering change handler
   * @param {string} currentDate - ISO date to display
   */
  setValue(currentDate) {
    this.input.value = currentDate;
  }

  /**
   * Called by MapLibre when control is removed from map
   * @param {MapLibreMap} map - this control is being removed from
   */
  onRemove(map) {
    this.container.remove();
  }
}
