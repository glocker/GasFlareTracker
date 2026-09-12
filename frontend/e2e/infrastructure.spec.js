const { test, expect } = require("./fixtures");

test("blocks unexpected external requests", async ({ page }) => {
  const result = await page.evaluate(async () => {
    try {
      await fetch("https://example.com/");
      return "allowed";
    } catch {
      return "blocked";
    }
  });

  expect(result).toBe("blocked");
});
