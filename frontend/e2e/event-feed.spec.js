const { test, expect, sampleEvents } = require("#e2e/fixtures");

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

test.describe("with flare events", () => {
  test.use({ eventsResponse: sampleEvents });

  test("renders ongoing event card with blind nights badge", async ({ page }) => {
    await page.goto("/", { waitUntil: "domcontentloaded" });

    const panel = page.locator("event-feed .event-feed__panel");
    const card = page.locator("event-feed .event-feed__card");

    await expect(card).toHaveCount(1);
    await page.getByRole("button", { name: "Show events" }).click();

    await expect(panel).toHaveJSProperty("open", true);
    await expect(card).toBeVisible();
    await expect(card.locator("strong")).toHaveText("Smoke Test Refinery");
    await expect(card.locator(".event-feed__kind")).toHaveText("Regime up");
    await expect(card.locator(".event-feed__period")).toHaveText("2020-06-01 – Ongoing");
    await expect(card.locator(".event-feed__blind-badge")).toHaveText("2 blind nights");
    await expect(page.locator("event-feed .event-feed__empty")).toBeHidden();
  });
});
