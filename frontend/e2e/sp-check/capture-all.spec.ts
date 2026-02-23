import { test, expect } from "@playwright/test";

// iPhone SE viewport
test.use({ viewport: { width: 375, height: 667 } });

const pages = [
  { name: "01-dashboard", url: "/" },
  { name: "02-races", url: "/races" },
  { name: "03-results", url: "/results" },
  { name: "04-bets", url: "/bets" },
  { name: "05-models", url: "/models" },
];

for (const page of pages) {
  test(`SP screenshot: ${page.name}`, async ({ page: p }) => {
    await p.goto(`${page.url}`, {
      waitUntil: "networkidle",
      timeout: 15000,
    });
    await p.waitForTimeout(1000);

    // Check no horizontal overflow
    const overflowX = await p.evaluate(() => {
      return document.documentElement.scrollWidth > document.documentElement.clientWidth;
    });

    await p.screenshot({
      path: `e2e/sp-check/${page.name}.png`,
      fullPage: true,
    });

    // Scroll down and capture bottom
    const scrollHeight = await p.evaluate(() => document.documentElement.scrollHeight);
    if (scrollHeight > 667) {
      await p.evaluate(() => window.scrollTo(0, document.documentElement.scrollHeight));
      await p.waitForTimeout(500);
      await p.screenshot({
        path: `e2e/sp-check/${page.name}-bottom.png`,
        fullPage: true,
      });
    }

    if (overflowX) {
      console.log(`WARNING: ${page.name} has horizontal overflow!`);
    }
  });
}

// Race detail page - need a real race ID
test("SP screenshot: race detail", async ({ page }) => {
  // First get a race ID from the races page
  await page.goto("/races", {
    waitUntil: "networkidle",
    timeout: 15000,
  });
  await page.waitForTimeout(1000);

  // Try to find a race link
  const raceLink = page.locator('a[href*="/races/"]').first();
  if (await raceLink.count() > 0) {
    await raceLink.click();
    await page.waitForTimeout(2000);
    await page.screenshot({
      path: "e2e/sp-check/06-race-detail.png",
      fullPage: true,
    });
  }
});
