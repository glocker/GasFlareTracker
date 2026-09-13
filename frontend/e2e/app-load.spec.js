const { test, expect } = require("#e2e/fixtures");

test("loads app shell without browser errors", async ({ page }) => {
  const pageErrors = [];
  const consoleErrors = [];

  page.on("pageerror", (error) => {
    pageErrors.push(error.message);
  });
  page.on("console", (message) => {
    if (message.type() === "error") {
      consoleErrors.push(message.text());
    }
  });

  await page.goto("/", { waitUntil: "domcontentloaded" });
  await page.waitForFunction(() =>
    Boolean(
      customElements.get("facility-map") &&
        customElements.get("facility-card") &&
        customElements.get("event-feed")
    )
  );

  await expect(page.locator("facility-map")).toHaveCount(1);
  await expect(page.locator("facility-card")).toHaveCount(1);
  await expect(page.locator("event-feed")).toHaveCount(1);

  expect(pageErrors).toEqual([]);
  expect(consoleErrors).toEqual([]);
});
