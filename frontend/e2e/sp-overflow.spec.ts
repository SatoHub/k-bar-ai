import { test, expect } from "@playwright/test";

/**
 * SP表示でページがビューポート幅をはみ出していないことを検証
 */
test.describe("SP: 横はみ出しチェック", () => {
  test("レース一覧ページが画面幅に収まる", async ({ page, isMobile }) => {
    test.skip(!isMobile, "SPのみのテスト");
    await page.goto("/races");
    // ページ読み込み完了を待つ
    await page.waitForLoadState("networkidle");
    await page.waitForTimeout(1000);

    const viewportWidth = page.viewportSize()!.width;
    const bodyScrollWidth = await page.evaluate(() => document.body.scrollWidth);

    expect(bodyScrollWidth).toBeLessThanOrEqual(viewportWidth + 1); // 1px tolerance
  });

  test("ダッシュボードが画面幅に収まる", async ({ page, isMobile }) => {
    test.skip(!isMobile, "SPのみのテスト");
    await page.goto("/");
    await page.waitForLoadState("networkidle");
    await page.waitForTimeout(1000);

    const viewportWidth = page.viewportSize()!.width;
    const bodyScrollWidth = await page.evaluate(() => document.body.scrollWidth);

    expect(bodyScrollWidth).toBeLessThanOrEqual(viewportWidth + 1);
  });

  test("収支ページが画面幅に収まる", async ({ page, isMobile }) => {
    test.skip(!isMobile, "SPのみのテスト");
    await page.goto("/bets");
    await page.waitForLoadState("networkidle");
    await page.waitForTimeout(1000);

    const viewportWidth = page.viewportSize()!.width;
    const bodyScrollWidth = await page.evaluate(() => document.body.scrollWidth);

    expect(bodyScrollWidth).toBeLessThanOrEqual(viewportWidth + 1);
  });

  test("AI成績ページが画面幅に収まる", async ({ page, isMobile }) => {
    test.skip(!isMobile, "SPのみのテスト");
    await page.goto("/results");
    await page.waitForLoadState("networkidle");
    await page.waitForTimeout(1000);

    const viewportWidth = page.viewportSize()!.width;
    const bodyScrollWidth = await page.evaluate(() => document.body.scrollWidth);

    expect(bodyScrollWidth).toBeLessThanOrEqual(viewportWidth + 1);
  });

  test("モデル管理ページが画面幅に収まる", async ({ page, isMobile }) => {
    test.skip(!isMobile, "SPのみのテスト");
    await page.goto("/models");
    await page.waitForLoadState("networkidle");
    await page.waitForTimeout(1000);

    const viewportWidth = page.viewportSize()!.width;
    const bodyScrollWidth = await page.evaluate(() => document.body.scrollWidth);

    expect(bodyScrollWidth).toBeLessThanOrEqual(viewportWidth + 1);
  });
});
