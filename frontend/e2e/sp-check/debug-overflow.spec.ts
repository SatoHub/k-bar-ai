import { test, expect } from "@playwright/test";

test.use({ viewport: { width: 375, height: 667 } });

test("Debug overflow on results page", async ({ page }) => {
  await page.goto("/results", {
    waitUntil: "networkidle",
    timeout: 15000,
  });
  await page.waitForTimeout(3000);

  // Check all elements that overflow
  const overflowInfo = await page.evaluate(() => {
    const vw = document.documentElement.clientWidth;
    const results: { tag: string; className: string; scrollW: number; clientW: number; rect: string }[] = [];
    
    document.querySelectorAll("*").forEach((el) => {
      const rect = el.getBoundingClientRect();
      if (rect.right > vw + 1) {
        results.push({
          tag: el.tagName,
          className: (el.className || "").toString().substring(0, 80),
          scrollW: el.scrollWidth,
          clientW: el.clientWidth,
          rect: `left=${Math.round(rect.left)} right=${Math.round(rect.right)} width=${Math.round(rect.width)}`,
        });
      }
    });
    
    return {
      viewport: vw,
      docScrollWidth: document.documentElement.scrollWidth,
      bodyScrollWidth: document.body.scrollWidth,
      overflowing: results.slice(0, 20),
    };
  });

  console.log("=== OVERFLOW DEBUG ===");
  console.log(JSON.stringify(overflowInfo, null, 2));
  
  await page.screenshot({
    path: "e2e/sp-check/03-results-debug.png",
    fullPage: true,
  });
});
