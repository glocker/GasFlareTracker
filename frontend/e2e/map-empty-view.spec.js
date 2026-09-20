const { test, expect } = require("#e2e/fixtures");

test("shows map empty view and refetches with date and region filters", async ({ page }) => {
  const facilityRequests = [];
  page.on("request", (request) => {
    const url = new URL(request.url());
    if (url.pathname === "/api/facilities") {
      facilityRequests.push(url);
    }
  });

  await page.goto("/", { waitUntil: "domcontentloaded" });

  const emptyView = page.locator("facility-map .map-empty-view");
  await expect(emptyView).toBeVisible();
  await expect(emptyView.locator(".map-empty-view__message")).toHaveText(
    "Oops, no data in chosen period or region. Pick another one."
  );

  const dateInput = emptyView.locator('input[type="date"]');
  await dateInput.fill("2020-06-15");
  await dateInput.dispatchEvent("change");

  await expect
    .poll(() => facilityRequests.some((url) => url.searchParams.get("current_date") === "2020-06-15"))
    .toBe(true);

  const regionSelect = emptyView.locator("select");
  await regionSelect.dispatchEvent("change");

  await expect
    .poll(() =>
      facilityRequests.some(
        (url) =>
          url.searchParams.get("current_date") === "2020-06-15" &&
          url.searchParams.get("country") === "US"
      )
    )
    .toBe(true);
});
