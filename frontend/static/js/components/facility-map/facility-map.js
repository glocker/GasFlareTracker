import { fetchFacilities } from "#app/api.js";
import { PeriodFilterControl } from "#app/components/facility-map/period-filter-control.js";

/** @typedef {import("maplibre-gl").Map} MapLibreMap */
/** @typedef {import("#app/types.js").FacilityProperties} FacilityProperties */
/** @typedef {import("#app/types.js").FlareEvent} FlareEvent */

const STATUS_COLORS = {
  no_data: "#9ca3af",
  silent: "#f59e0b",
  elevated: "#dc2626",
  reduced: "#2563eb",
  normal: "#16a34a",
};

const STATUS_LABELS = {
  no_data: "No data",
  silent: "Silent",
  elevated: "Elevated",
  reduced: "Reduced",
  normal: "Normal",
};

const MAP_STYLE_URL = "https://tiles.openfreemap.org/styles/liberty";

// A relative href written inside facility-map.html would resolve against the
// document's URL once parsed via innerHTML (the template has no base URL of
// its own) - so our own same-origin stylesheet is built here instead, resolved
// against this module's URL, same as the template fetch below.
const STYLESHEET_URL = new URL("./facility-map.css", import.meta.url);

const templateHtml = await fetch(new URL("./facility-map.html", import.meta.url)).then((res) =>
  res.text()
);
const template = document.createElement("template");
template.innerHTML = templateHtml;

export class FacilityMap extends HTMLElement {
  /** @type {MapLibreMap} */
  map;

  /** @type {PeriodFilterControl} */
  periodFilterControl;

  /** @type {GeoJSON.FeatureCollection<GeoJSON.Point, FacilityProperties>} */
  geojson;

  connectedCallback() {
    // Listener on external target needs connect/disconnect pairing
    document.addEventListener("event-selected", this._onEventSelected);

    const shadow = this.attachShadow({ mode: "open" });
    const stylesheet = document.createElement("link");
    stylesheet.rel = "stylesheet";
    stylesheet.href = STYLESHEET_URL.href;

    // MapLibre measures the container size synchronously in constructor,
    // before async stylesheet above applied and never remeasures
    // later, so constructing early permanently freezes the canvas at the
    // wrong size
    const stylesheetReady = new Promise((resolve) => {
      stylesheet.addEventListener("load", resolve, { once: true });
    });
    shadow.append(stylesheet, template.content.cloneNode(true));

    // Legend toggle doesn't depend on MapLibre or the stylesheet load, so it's
    // wired up right away instead of waiting on stylesheetReady below
    const legendList = /** @type {HTMLDListElement} */ (shadow.querySelector(".legend-list"));
    for (const [status, color] of Object.entries(STATUS_COLORS)) {
      const swatch = document.createElement("dt");
      swatch.className = "legend-swatch";
      swatch.style.background = color;

      const label = document.createElement("dd");
      label.textContent = STATUS_LABELS[/** @type {keyof typeof STATUS_LABELS} */ (status)];

      legendList.append(swatch, label);
    }

    const legendDialog = /** @type {HTMLDialogElement} */ (shadow.querySelector(".legend-dialog"));
    // Closes on ESC and on any click outside dialog, same as facility-card
    legendDialog.setAttribute("closedby", "any");
    const legendToggle = shadow.querySelector(".legend-toggle");
    legendToggle?.addEventListener("click", () => {
      if (legendDialog.open) {
        legendDialog.close();
      } else {
        legendDialog.show();
      }
    });

    stylesheetReady.then(() => {
      const container = /** @type {HTMLElement} */ (shadow.querySelector(".map-container"));

      this.map = new maplibregl.Map({
        container,
        style: MAP_STYLE_URL,
        center: [-95, 35], // Сentered on the continental US
        zoom: 3.5,
      });

      this.map.addControl(new maplibregl.NavigationControl(), "top-right");
      this.periodFilterControl = new PeriodFilterControl((currentDate) =>
        this.loadFacilities(currentDate)
      );
      this.map.addControl(this.periodFilterControl, "top-left");
      this.map.on("load", () => this.loadFacilities());
    });
  }

  disconnectedCallback() {
    document.removeEventListener("event-selected", this._onEventSelected);
  }

  /**
   * Fly to facility behind clicked event feed and opens its
   * card with this event's details attached
   * @param {Event} e - event selected event
   */
  _onEventSelected = (e) => {
    const flareEvent = /** @type {CustomEvent<FlareEvent>} */ (e).detail;
    const feature = this.geojson?.features.find((f) => f.id === flareEvent.facility_id);
    if (!feature || !this.map) return;

    this.map.flyTo({
      center: /** @type {[number, number]} */ (feature.geometry.coordinates),
      zoom: Math.max(this.map.getZoom(), 9),
    });
    this.dispatchEvent(
      new CustomEvent("facility-selected", {
        detail: { ...feature.properties, event: flareEvent },
        bubbles: true,
      })
    );
  };

  /**
   * Fetches facilities for given date
   * Also sets map source for first time or updates existing one in place
   * @param {string | undefined} [currentDate] - selected date filter value
   */
  async loadFacilities(currentDate) {
    let geojson;
    try {
      geojson = await fetchFacilities(currentDate);
    } catch (err) {
      console.error("failed to load facilities", err);
      return;
    }

    this.geojson = geojson;
    this.periodFilterControl.setValue(geojson.as_of);

    const source = /** @type {import("maplibre-gl").GeoJSONSource | undefined} */ (
      this.map.getSource("facilities")
    );
    if (source) {
      source.setData(geojson);
      return;
    }

    // Add source only once
    // MapLibre don't allow to add source with existed id twice
    this.map.addSource("facilities", { type: "geojson", data: geojson });

    this.map.addLayer({
      id: "facilities-points",
      type: "circle",
      source: "facilities",
      paint: {
        "circle-radius": 6,
        "circle-color": [
          "match",
          ["get", "status"],
          "no_data", STATUS_COLORS.no_data,
          "silent", STATUS_COLORS.silent,
          "elevated", STATUS_COLORS.elevated,
          "reduced", STATUS_COLORS.reduced,
          "normal", STATUS_COLORS.normal,
          /* other */ STATUS_COLORS.no_data,
        ],
        "circle-stroke-width": 1,
        "circle-stroke-color": "#ffffff",
      },
    });

    this.map.on("click", "facilities-points", (e) => {
      const feature = e.features?.[0];
      if (!feature) return;
      this.dispatchEvent(
        new CustomEvent("facility-selected", { detail: feature.properties, bubbles: true })
      );
    });

    this.map.on("mouseenter", "facilities-points", () => {
      this.map.getCanvas().style.cursor = "pointer";
    });
    this.map.on("mouseleave", "facilities-points", () => {
      this.map.getCanvas().style.cursor = "";
    });
  }
}

customElements.define("facility-map", FacilityMap);
