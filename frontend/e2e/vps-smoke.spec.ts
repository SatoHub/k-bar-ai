import { test, expect } from "@playwright/test";

// =============================
// PC & SP 共通スモークテスト
// =============================

/** SP時にモバイルナビ内の可視リンクを返すヘルパー */
function visibleLink(page: import("@playwright/test").Page, href: string) {
  return page.locator(`a[href="${href}"]`).and(page.locator(":visible"));
}

test.describe("ダッシュボード", () => {
  test("ページが表示される", async ({ page }) => {
    await page.goto("/");
    await expect(page).toHaveTitle(/K-Bar AI/);
    await expect(page.locator("text=K-Bar AI").first()).toBeVisible();
  });

  test("ナビゲーションリンクが存在する", async ({ page, isMobile }) => {
    await page.goto("/");
    if (isMobile) {
      const menuBtn = page.locator('button[aria-label="メニュー"]');
      await expect(menuBtn).toBeVisible();
      await menuBtn.click();
      // モバイルナビ内のリンクを確認
      const mobileNav = page.locator("nav.md\\:hidden");
      await expect(mobileNav.locator('a[href="/races"]')).toBeVisible();
      await expect(mobileNav.locator('a[href="/bets"]')).toBeVisible();
      await expect(mobileNav.locator('a[href="/results"]')).toBeVisible();
      await expect(mobileNav.locator('a[href="/models"]')).toBeVisible();
    } else {
      await expect(page.locator('a[href="/races"]').first()).toBeVisible();
      await expect(page.locator('a[href="/bets"]').first()).toBeVisible();
      await expect(page.locator('a[href="/results"]').first()).toBeVisible();
      await expect(page.locator('a[href="/models"]').first()).toBeVisible();
    }
  });
});

test.describe("レース一覧", () => {
  test("ページが表示される", async ({ page }) => {
    await page.goto("/races");
    // main エリア内の見出しを確認
    await expect(page.locator("main h1, main h2").first()).toBeVisible({ timeout: 10000 });
  });

  test("カレンダーが表示される", async ({ page, isMobile }) => {
    await page.goto("/races");
    if (isMobile) {
      // SP: カード表示なのでカレンダーのgridを確認
      await expect(page.locator(".grid.grid-cols-7").first()).toBeVisible({ timeout: 10000 });
    } else {
      await expect(page.locator("table").first()).toBeVisible({ timeout: 10000 });
    }
  });
});

test.describe("収支ページ", () => {
  test("ページが表示される", async ({ page }) => {
    await page.goto("/bets");
    await expect(page.locator("main").first()).toBeVisible();
    // ページコンテンツが読み込まれる
    await expect(page.locator("main h1, main h2, main >> text=収支").first()).toBeVisible({ timeout: 10000 });
  });
});

test.describe("AI成績ページ", () => {
  test("ページが表示される", async ({ page }) => {
    await page.goto("/results");
    await expect(page.locator("main h1, main h2").first()).toBeVisible({ timeout: 10000 });
  });
});

test.describe("モデル管理ページ", () => {
  test("ページが表示される", async ({ page }) => {
    await page.goto("/models");
    await expect(page.locator("main h1, main h2").first()).toBeVisible({ timeout: 10000 });
  });
});

test.describe("レスポンシブ表示", () => {
  test("ヘッダーの表示切替", async ({ page, isMobile }) => {
    await page.goto("/");
    if (isMobile) {
      // SP: ハンバーガーボタンが見える
      await expect(page.locator('button[aria-label="メニュー"]')).toBeVisible();
    } else {
      // PC: デスクトップnavが見える、ハンバーガーは非表示
      await expect(page.locator("nav").first()).toBeVisible();
      await expect(page.locator('button[aria-label="メニュー"]')).toBeHidden();
    }
  });

  test("SP: ハンバーガーメニュー開閉", async ({ page, isMobile }) => {
    test.skip(!isMobile, "SPのみのテスト");
    await page.goto("/");
    const menuBtn = page.locator('button[aria-label="メニュー"]');

    // メニューを開く
    await menuBtn.click();
    const mobileNav = page.locator("nav.md\\:hidden");
    await expect(mobileNav).toBeVisible();

    // リンクをクリックするとメニューが閉じる（ページ遷移）
    await mobileNav.locator('a[href="/races"]').click();
    await expect(page).toHaveURL(/\/races/);
    // ページ遷移後、モバイルメニューは閉じているはず
    await expect(page.locator("nav.md\\:hidden")).toBeHidden();
  });
});

test.describe("ページ遷移", () => {
  test("ダッシュボード → レース一覧 → ダッシュボード", async ({ page, isMobile }) => {
    await page.goto("/");

    if (isMobile) {
      await page.locator('button[aria-label="メニュー"]').click();
      await page.locator("nav.md\\:hidden").locator('a[href="/races"]').click();
    } else {
      await page.locator('a[href="/races"]').first().click();
    }
    await expect(page).toHaveURL(/\/races/);

    if (isMobile) {
      await page.locator('button[aria-label="メニュー"]').click();
      await page.locator("nav.md\\:hidden").locator('a[href="/"]').click();
    } else {
      await page.locator('a[href="/"]').first().click();
    }
    await expect(page).toHaveURL(/\/$/);
  });
});
