const { test, expect, sampleEvents, sampleFacilities } = require("#e2e/fixtures");

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
  test.use({ eventsResponse: sampleEvents, facilitiesResponse: sampleFacilities });

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

  test("clicking event card flies to facility and opens card with clicked event", async ({ page }) => {
    await page.goto("/", { waitUntil: "domcontentloaded" });

    await page.waitForFunction(() => {
      const map = window.__maplibreMaps?.[0];
      return Boolean(map?.getSource("facilities")?.data?.features?.length);
    });

    const eventCard = page.locator("event-feed .event-feed__card");
    await expect(eventCard).toHaveCount(1);
    await page.getByRole("button", { name: "Show events" }).click();
    await eventCard.click();

    const flyToHandle = await page.waitForFunction(() => window.__maplibreMaps?.[0]?.lastFlyTo ?? null);
    const flyTo = await flyToHandle.jsonValue();
    expect(flyTo).toMatchObject({
      center: [-95.36, 29.75],
      zoom: 9,
    });

    const dialog = page.locator("facility-card dialog");
    await expect(dialog).toHaveJSProperty("open", true);
    await expect(dialog.locator("h2")).toHaveText("Smoke Test Refinery");
    await expect(dialog).toContainText("Kindrefinery");
    await expect(dialog.locator("h3")).toHaveText("Flare event");
    await expect(dialog).toContainText("KindRegime up");
    await expect(dialog).toContainText("Period2020-06-01 – Ongoing");
    await expect(dialog).toContainText("Score4.00");
    await expect(dialog).toContainText("Blind nights2");
  });
});
