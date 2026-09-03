/**
 * Reusable region filter
 *
 * v0.1 data is US-only
 * Filter emits a real ISO 3166-1 alpha-2 value matching the `country` param
 * on /api/facilities, ready for more options once other countries land
 */
export class RegionFilter {
  /** @type {HTMLSelectElement} */
  select;

  /**
   * @param {(country: string | undefined) => void} handlerCallback -
   *  selected country in ISO 3166-1 alpha-2 format
   */
  constructor(handlerCallback) {
    this.select = document.createElement("select");

    const option = document.createElement("option");
    option.value = "US";
    option.textContent = "United States";
    this.select.appendChild(option);
    this.select.value = "US";

    this.select.addEventListener("change", () => {
      handlerCallback(this.select.value || undefined);
    });
  }

  /**
   * Sets selected country without triggering the change handler
   * @param {string} country
   */
  setValue(country) {
    this.select.value = country;
  }
}
