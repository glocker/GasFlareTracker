const { test, expect } = require("#e2e/fixtures");

test("creates MapLibre after the map container has viewport-sized layout", async ({ page }) => {
  await page.goto("/", { waitUntil: "domcontentloaded" });

  const sizeHandle = await page.waitForFunction(() => {
    const map = window.__maplibreMaps?.[0];
    if (!map) return null;

    const container = map.options.container;
    const containerRect = container.getBoundingClientRect();
    return {
      canvasWidth: map.canvas.width,
      canvasHeight: map.canvas.height,
      containerWidth: Math.round(containerRect.width),
      containerHeight: Math.round(containerRect.height),
      viewportWidth: window.innerWidth,
      viewportHeight: window.innerHeight,
    };
  });
  const size = await sizeHandle.jsonValue();

  expect(size.canvasWidth).toBeGreaterThanOrEqual(size.viewportWidth * 0.9);
  expect(size.canvasHeight).toBeGreaterThanOrEqual(size.viewportHeight * 0.9);
  expect(Math.abs(size.canvasWidth - size.containerWidth)).toBeLessThanOrEqual(1);
  expect(Math.abs(size.canvasHeight - size.containerHeight)).toBeLessThanOrEqual(1);
});
