const { test, expect, sampleFacilities } = require("#e2e/fixtures");

test.use({ facilitiesResponse: sampleFacilities });

test("opens facility card on point click and positions it on the right", async ({ page }) => {
  await page.goto("/", { waitUntil: "domcontentloaded" });

  await page.waitForFunction(() => {
    const map = window.__maplibreMaps?.[0];
    return Boolean(
      map?.getSource("facilities")?.data?.features?.length &&
        map.handlers.some(
          (handler) => handler.eventName === "click" && handler.layer === "facilities-points"
        )
    );
  });

  await page.evaluate(() => {
    const map = window.__maplibreMaps[0];
    const clickHandler = map.handlers.find(
      (handler) => handler.eventName === "click" && handler.layer === "facilities-points"
    ).handler;
    const feature = map.getSource("facilities").data.features[0];
    clickHandler({ features: [feature] });
  });

  const dialog = page.locator("facility-card dialog");
  await expect(dialog).toHaveJSProperty("open", true);
  await expect(dialog).toContainText("Smoke Test Refinery");
  await expect(dialog).toContainText("refinery");
  await expect(dialog).toContainText("Test Operator");
  await expect(dialog).toContainText("normal");

  const box = await dialog.boundingBox();
  const viewport = page.viewportSize();
  expect(box).not.toBeNull();
  expect(viewport).not.toBeNull();

  const rightGap = viewport.width - (box.x + box.width);
  expect(rightGap).toBeGreaterThanOrEqual(14);
  expect(rightGap).toBeLessThanOrEqual(18);
  expect(box.x).toBeGreaterThan(100);
});
