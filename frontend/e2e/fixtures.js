const { test: base, expect } = require("@playwright/test");

const emptyFacilities = {
  type: "FeatureCollection",
  as_of: "2020-12-31",
  features: [],
};

const emptyEvents = { events: [] };

const maplibreStub = String.raw`
(() => {
  class StubNavigationControl {}

  class StubMap {
    constructor(options) {
      this.options = options;
      this.sources = new globalThis.Map();
      this.handlers = [];
      this.zoom = options.zoom ?? 0;
      this.canvas = document.createElement("canvas");
      this.canvas.width = Math.max(1, Math.round(options.container.getBoundingClientRect().width));
      this.canvas.height = Math.max(1, Math.round(options.container.getBoundingClientRect().height));
      options.container.append(this.canvas);
      window.__maplibreMaps.push(this);
    }

    addControl() {}

    addSource(id, source) {
      this.sources.set(id, {
        data: source.data,
        setData(data) {
          this.data = data;
        },
      });
    }

    getSource(id) {
      return this.sources.get(id);
    }

    addLayer(layer) {
      this.layer = layer;
    }

    on(eventName, layerOrHandler, maybeHandler) {
      const handler = typeof layerOrHandler === "function" ? layerOrHandler : maybeHandler;
      this.handlers.push({ eventName, layer: typeof layerOrHandler === "string" ? layerOrHandler : undefined, handler });
      if (eventName === "load" && typeof handler === "function") {
        queueMicrotask(handler);
      }
    }

    flyTo(options) {
      this.lastFlyTo = options;
    }

    getZoom() {
      return this.zoom;
    }

    getCanvas() {
      return this.canvas;
    }
  }

  window.__maplibreMaps = [];
  window.maplibregl = { Map: StubMap, NavigationControl: StubNavigationControl };
})();
`;

/**
 * Installs default browser-side stubs shared by frontend e2e tests.
 * @param {import("@playwright/test").Page} page - Playwright page to configure
 */
async function installDefaultRoutes(page) {
  await page.route("**/*", async (route) => {
    const requestUrl = new URL(route.request().url());

    if (requestUrl.href === "https://unpkg.com/maplibre-gl@4.7.1/dist/maplibre-gl.js") {
      await route.fulfill({
        status: 200,
        contentType: "application/javascript",
        body: maplibreStub,
      });
      return;
    }

    if (requestUrl.origin === "http://127.0.0.1:4173") {
      if (requestUrl.pathname === "/api/facilities") {
        await route.fulfill({ status: 200, contentType: "application/json", json: emptyFacilities });
        return;
      }
      if (requestUrl.pathname === "/api/events") {
        await route.fulfill({ status: 200, contentType: "application/json", json: emptyEvents });
        return;
      }
      await route.continue();
      return;
    }

    await route.abort("blockedbyclient");
  });
}

const test = base.extend({
  page: async ({ page }, use) => {
    await installDefaultRoutes(page);
    await use(page);
  },
});

module.exports = {
  test,
  expect,
  installDefaultRoutes,
  emptyFacilities,
  emptyEvents,
};
