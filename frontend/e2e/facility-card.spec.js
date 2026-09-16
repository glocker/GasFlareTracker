const { test, expect, sampleFacilities } = require("#e2e/fixtures");

test.use({ facilitiesResponse: sampleFacilities });

/**
 * Opens first mocked facility through same map click path users hit
 * @param {import("@playwright/test").Page} page - Playwright page to drive
 */
async function openFirstFacilityCard(page) {
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
  return dialog;
}

test("opens facility card on point click and positions it on right", async ({ page }) => {
  const dialog = await openFirstFacilityCard(page);
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

test("closes facility card on Escape", async ({ page }) => {
  const dialog = await openFirstFacilityCard(page);

  await page.keyboard.press("Escape");

  await expect(dialog).toHaveJSProperty("open", false);
});

test("closes facility card on outside click", async ({ page }) => {
  const dialog = await openFirstFacilityCard(page);

  await page.mouse.click(10, 10);

  await expect(dialog).toHaveJSProperty("open", false);
});
