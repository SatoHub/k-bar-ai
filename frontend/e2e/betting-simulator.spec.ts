import { test, expect, type Page } from "@playwright/test";

/**
 * 馬券シミュレーター拡張テスト
 * - ボックス・フォーメーション・流し買いのUI・点数計算を確認
 */

/** Find a non-stub race and navigate to its simulate page */
async function gotoSimulate(page: Page) {
  // Use the API to find a non-stub race with enough entries
  const resp = await page.request.get(`/api/v1/races?limit=50`);
  const data = await resp.json();
  const race = data.items?.find(
    (r: { stub_only: boolean; head_count: number }) =>
      !r.stub_only && r.head_count >= 8,
  );

  if (!race) {
    test.skip(true, "No non-stub race with entries found");
    return;
  }

  // Backend uses race_id (string like "202605010801"), not UUID
  await page.goto(`/races/${race.race_id}/simulate`);
  await page.waitForLoadState("networkidle");
}

/** Wait for simulator to load */
async function waitForSimulator(page: Page) {
  await expect(
    page.locator("text=馬券シミュレーション").first(),
  ).toBeVisible({ timeout: 20000 });
}

// ============================
// 基本表示テスト
// ============================

test.describe("馬券シミュレーター: 基本表示", () => {
  test("シミュレーターが表示される", async ({ page }) => {
    await gotoSimulate(page);
    await waitForSimulator(page);
    // 馬券種ピルが表示される
    await expect(page.locator("button", { hasText: "単勝" }).first()).toBeVisible();
    await expect(page.locator("button", { hasText: "馬連" }).first()).toBeVisible();
    await expect(page.locator("button", { hasText: "三連単" }).first()).toBeVisible();
  });

  test("合計点数サマリーが表示される", async ({ page }) => {
    await gotoSimulate(page);
    await waitForSimulator(page);
    await expect(page.locator("text=合計点数").first()).toBeVisible();
    await expect(page.locator("text=合計投資").first()).toBeVisible();
    await expect(page.locator("text=推定払戻合計").first()).toBeVisible();
  });
});

// ============================
// 買い方切替テスト
// ============================

test.describe("馬券シミュレーター: 買い方ピル", () => {
  test("馬連選択時にボックス・フォーメーション・流しが表示される", async ({ page }) => {
    await gotoSimulate(page);
    await waitForSimulator(page);

    // 馬連を選択
    await page.locator("button", { hasText: "馬連" }).first().click();
    await page.waitForTimeout(500);

    // 買い方ピルが表示される
    await expect(page.locator("button", { hasText: "通常" }).first()).toBeVisible();
    await expect(page.locator("button", { hasText: "ボックス" }).first()).toBeVisible();
    await expect(page.locator("button", { hasText: "フォーメーション" }).first()).toBeVisible();
    await expect(page.locator("button", { hasText: "流し" }).first()).toBeVisible();
  });

  test("単勝選択時はボックス等が表示されない", async ({ page }) => {
    await gotoSimulate(page);
    await waitForSimulator(page);

    // 単勝はデフォルト、買い方選択は通常のみなのでピル自体が1つ=非表示
    // ボックスボタンが存在しないことを確認
    const boxButtons = page.locator("button").filter({ hasText: /^ボックス$/ });
    await expect(boxButtons).toHaveCount(0);
  });
});

// ============================
// ボックスモードテスト
// ============================

test.describe("馬券シミュレーター: ボックス", () => {
  test("馬連ボックスで馬を選択すると点数が計算される", async ({ page }) => {
    await gotoSimulate(page);
    await waitForSimulator(page);

    // 馬連を選択
    await page.locator("button", { hasText: "馬連" }).first().click();
    await page.waitForTimeout(500);

    // ボックスを選択
    await page.locator("button", { hasText: "ボックス" }).first().click();
    await page.waitForTimeout(500);

    // チェックボックスグリッドが表示される
    await expect(page.locator("text=対象馬を選択").first()).toBeVisible();

    // Find horse buttons in the checkbox grid area (after the label)
    const gridSection = page.locator("text=対象馬を選択").first().locator("..").locator("..");
    const horseButtons = gridSection.locator(".flex.flex-wrap button");

    const count = await horseButtons.count();
    // Click first 4 horse buttons
    const clickCount = Math.min(4, count);
    for (let i = 0; i < clickCount; i++) {
      await horseButtons.nth(i).click();
      await page.waitForTimeout(100);
    }

    if (clickCount >= 4) {
      // C(4,2)=6点 should be displayed
      await expect(
        page.locator("text=/6点/").first(),
      ).toBeVisible({ timeout: 5000 });
    }
  });

  test("三連単ボックスで5頭=60点が表示される", async ({ page }) => {
    await gotoSimulate(page);
    await waitForSimulator(page);

    // 三連単を選択
    await page.locator("button", { hasText: "三連単" }).first().click();
    await page.waitForTimeout(500);

    // ボックスを選択
    await page.locator("button", { hasText: "ボックス" }).first().click();
    await page.waitForTimeout(500);

    // Find horse buttons
    const gridSection = page.locator("text=対象馬を選択").first().locator("..").locator("..");
    const horseButtons = gridSection.locator(".flex.flex-wrap button");

    const count = await horseButtons.count();
    const clickCount = Math.min(5, count);
    for (let i = 0; i < clickCount; i++) {
      await horseButtons.nth(i).click();
      await page.waitForTimeout(100);
    }

    if (clickCount >= 5) {
      // P(5,3)=60点
      await expect(
        page.locator("text=/60点/").first(),
      ).toBeVisible({ timeout: 5000 });
    }
  });

  test("馬連ボックスの買い目一覧が表示される", async ({ page }) => {
    await gotoSimulate(page);
    await waitForSimulator(page);

    // 馬連ボックスに切り替え
    await page.locator("button", { hasText: "馬連" }).first().click();
    await page.waitForTimeout(500);
    await page.locator("button", { hasText: "ボックス" }).first().click();
    await page.waitForTimeout(500);

    // 3頭選択 → C(3,2)=3点（10点以下なので自動展開）
    const gridSection = page.locator("text=対象馬を選択").first().locator("..").locator("..");
    const horseButtons = gridSection.locator(".flex.flex-wrap button");
    for (let i = 0; i < 3; i++) {
      await horseButtons.nth(i).click();
      await page.waitForTimeout(100);
    }

    // 買い目一覧が表示される
    await expect(
      page.locator("text=買い目一覧").first(),
    ).toBeVisible({ timeout: 5000 });
  });
});

// ============================
// フォーメーションモードテスト
// ============================

test.describe("馬券シミュレーター: フォーメーション", () => {
  test("馬単フォーメーションで着順別に候補を選択できる", async ({ page }) => {
    await gotoSimulate(page);
    await waitForSimulator(page);

    // 馬単を選択
    await page.locator("button", { hasText: "馬単" }).first().click();
    await page.waitForTimeout(500);

    // フォーメーションを選択
    await page.locator("button", { hasText: "フォーメーション" }).first().click();
    await page.waitForTimeout(500);

    // 1着候補、2着候補のラベルが表示される
    await expect(page.locator("text=1着候補").first()).toBeVisible();
    await expect(page.locator("text=2着候補").first()).toBeVisible();
  });

  test("三連複フォーメーションで3つの着順候補が表示される", async ({ page }) => {
    await gotoSimulate(page);
    await waitForSimulator(page);

    // 三連複を選択
    await page.locator("button", { hasText: "三連複" }).first().click();
    await page.waitForTimeout(500);

    // フォーメーションを選択
    await page.locator("button", { hasText: "フォーメーション" }).first().click();
    await page.waitForTimeout(500);

    // 馬1候補、馬2候補、馬3候補が表示される（unorderedなので「馬X候補」）
    await expect(page.locator("text=馬1候補").first()).toBeVisible();
    await expect(page.locator("text=馬2候補").first()).toBeVisible();
    await expect(page.locator("text=馬3候補").first()).toBeVisible();
  });
});

// ============================
// 流しモードテスト
// ============================

test.describe("馬券シミュレーター: 流し", () => {
  test("馬連流しで軸馬選択UIが表示される", async ({ page }) => {
    await gotoSimulate(page);
    await waitForSimulator(page);

    // 馬連を選択
    await page.locator("button", { hasText: "馬連" }).first().click();
    await page.waitForTimeout(500);

    // 流しを選択
    await page.locator("button", { hasText: "流し" }).first().click();
    await page.waitForTimeout(500);

    // 軸馬選択UIが表示される
    await expect(page.locator("text=軸馬").first()).toBeVisible();
    await expect(page.locator("text=相手馬を選択").first()).toBeVisible();
  });

  test("三連複流しで1頭軸/2頭軸トグルが表示される", async ({ page }) => {
    await gotoSimulate(page);
    await waitForSimulator(page);

    // 三連複を選択
    await page.locator("button", { hasText: "三連複" }).first().click();
    await page.waitForTimeout(500);

    // 流しを選択
    await page.locator("button", { hasText: "流し" }).first().click();
    await page.waitForTimeout(500);

    // 軸タイプ選択が表示される（3頭買いの場合のみ）
    await expect(page.locator("button", { hasText: "1頭軸" }).first()).toBeVisible();
    await expect(page.locator("button", { hasText: "2頭軸" }).first()).toBeVisible();
  });

  test("三連単流しで軸馬位置選択が表示される", async ({ page }) => {
    await gotoSimulate(page);
    await waitForSimulator(page);

    // 三連単を選択
    await page.locator("button", { hasText: "三連単" }).first().click();
    await page.waitForTimeout(500);

    // 流しを選択
    await page.locator("button", { hasText: "流し" }).first().click();
    await page.waitForTimeout(500);

    // 軸馬位置が表示される（ordered bet type）
    await expect(page.locator("text=軸馬位置").first()).toBeVisible();
    await expect(page.locator("button", { hasText: "1着固定" }).first()).toBeVisible();
  });
});

// ============================
// 馬券追加・削除テスト
// ============================

test.describe("馬券シミュレーター: スロット操作", () => {
  test("馬券を追加できる", async ({ page }) => {
    await gotoSimulate(page);
    await waitForSimulator(page);

    // 現在のスロット数を確認（削除ボタンは1スロットの場合非表示）
    const addBtn = page.locator("button", { hasText: "馬券を追加" }).first();

    // 追加ボタンをクリック
    await addBtn.click();
    await page.waitForTimeout(500);

    // 2スロットになると削除ボタン（×）が2個表示される
    const deleteButtons = page.locator("button[title='この馬券を削除']");
    await expect(deleteButtons).toHaveCount(2, { timeout: 5000 });
  });

  test("100点超で大量買い警告が表示される", async ({ page }) => {
    await gotoSimulate(page);
    await waitForSimulator(page);

    // 三連単ボックスで8頭以上選択 → P(8,3)=336点
    await page.locator("button", { hasText: "三連単" }).first().click();
    await page.waitForTimeout(500);
    await page.locator("button", { hasText: "ボックス" }).first().click();
    await page.waitForTimeout(500);

    const gridSection = page.locator("text=対象馬を選択").first().locator("..").locator("..");
    const horseButtons = gridSection.locator(".flex.flex-wrap button");
    const count = await horseButtons.count();
    const clickCount = Math.min(8, count);
    for (let i = 0; i < clickCount; i++) {
      await horseButtons.nth(i).click();
      await page.waitForTimeout(50);
    }

    if (clickCount >= 8) {
      // 大量買い警告が表示される
      await expect(
        page.locator("text=/大量買い/").first(),
      ).toBeVisible({ timeout: 5000 });
    }
  });
});

// ============================
// モバイル表示テスト
// ============================

test.describe("馬券シミュレーター: レスポンシブ", () => {
  test("SP表示でチェックボックスグリッドが崩れない", async ({ page, isMobile }) => {
    test.skip(!isMobile, "SPのみのテスト");

    await gotoSimulate(page);
    await waitForSimulator(page);

    // 馬連ボックスに切り替え
    await page.locator("button", { hasText: "馬連" }).first().click();
    await page.waitForTimeout(500);
    await page.locator("button", { hasText: "ボックス" }).first().click();
    await page.waitForTimeout(500);

    // 横スクロールが発生していないことを確認
    const bodyWidth = await page.evaluate(() => document.body.scrollWidth);
    const viewportWidth = await page.evaluate(() => window.innerWidth);
    expect(bodyWidth).toBeLessThanOrEqual(viewportWidth + 5);
  });
});
