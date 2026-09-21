const { test, expect } = require("#e2e/fixtures");

test("syncs corner and empty-view period filters to API as_of date", async ({ page }) => {
  const requestedDates = [];
  page.on("request", (request) => {
    const url = new URL(request.url());
    if (url.pathname === "/api/facilities") {
      requestedDates.push(url.searchParams.get("current_date"));
    }
  });

  await page.goto("/", { waitUntil: "domcontentloaded" });

  const cornerDateInput = page.locator('facility-map .map-container input[type="date"]');
  const emptyViewDateInput = page.locator('facility-map .map-empty-view input[type="date"]');

  await expect(cornerDateInput).toHaveValue("2020-12-31");
  await expect(emptyViewDateInput).toHaveValue("2020-12-31");

  await cornerDateInput.fill("2021-01-15");
  await cornerDateInput.dispatchEvent("change");

  await expect
    .poll(() => requestedDates.includes("2021-01-15"))
    .toBe(true);

  await expect(cornerDateInput).toHaveValue("2020-12-31");
  await expect(emptyViewDateInput).toHaveValue("2020-12-31");
});
