import { fetchFacilities } from "#app/api.js";

/** @typedef {import("maplibre-gl").Map} MapLibreMap */

const STATUS_COLORS = {
  no_data: "#9ca3af",
  silent: "#f59e0b",
  elevated: "#dc2626",
  reduced: "#2563eb",
  normal: "#16a34a",
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

  connectedCallback() {
    const shadow = this.attachShadow({ mode: "open" });
    const stylesheet = document.createElement("link");
    stylesheet.rel = "stylesheet";
    stylesheet.href = STYLESHEET_URL.href;
    shadow.append(stylesheet, template.content.cloneNode(true));
    const container = /** @type {HTMLElement} */ (shadow.querySelector(".map-container"));

    this.map = new maplibregl.Map({
      container,
      style: MAP_STYLE_URL,
      center: [-95, 35], // Сentered on the continental US
      zoom: 3.5,
    });

    this.map.addControl(new maplibregl.NavigationControl(), "top-right");
    this.map.on("load", () => this.loadFacilities());
  }

  async loadFacilities() {
    /** @type {GeoJSON.FeatureCollection} */
    let geojson;
    try {
      geojson = await fetchFacilities();
    } catch (err) {
      console.error("failed to load facilities", err);
      return;
    }

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
