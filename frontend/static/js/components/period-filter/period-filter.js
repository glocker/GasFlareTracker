import { debounce } from "#app/debounce.js";

/**
 * Reusable date filter
 * No MapLibre/IControl dependency, so it can be mounted
 * anywhere - a map corner control or a plain overlay
 */
export class PeriodFilter {
  /** @type {HTMLInputElement} */
  input;

  /**
   * @param {(currentDate: string | undefined) => void} handlerCallback - called
   * with selected date (or undefined if cleared), debounced
   */
  constructor(handlerCallback) {
    this.input = document.createElement("input");
    this.input.setAttribute("type", "date");

    // Wrap once here, not per-event - debounce needs one shared timer across calls
    const debouncedHandler = debounce(handlerCallback, 1000);
    this.input.addEventListener("change", () => {
      debouncedHandler(this.input.value || undefined);
    });
  }

  /**
   * Sets displayed date without triggering change handler
   * @param {string} currentDate - ISO date to display
   */
  setValue(currentDate) {
    this.input.value = currentDate;
  }
}
