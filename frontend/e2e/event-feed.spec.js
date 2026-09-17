const { test, expect } = require("#e2e/fixtures");

test("shows empty state when there are no flare events", async ({ page }) => {
  await page.goto("/", { waitUntil: "domcontentloaded" });

  await expect
    .poll(() => page.locator("event-feed .event-feed__empty").evaluate((el) => el.hidden))
    .toBe(false);

  await page.getByRole("button", { name: "Show events" }).click();

  const panel = page.locator("event-feed .event-feed__panel");
  const list = page.locator("event-feed .event-feed__list");
  const emptyState = page.locator("event-feed .event-feed__empty");

  await expect(panel).toHaveJSProperty("open", true);
  await expect(emptyState).toBeVisible();
  await expect(emptyState).toHaveText("No events found in selected period");
  await expect(list).toBeHidden();
  await expect(page.locator("event-feed .event-feed__card")).toHaveCount(0);
});
