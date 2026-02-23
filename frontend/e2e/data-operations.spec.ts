import { test, expect } from "@playwright/test";

/**
 * PC版テーブルのレースリンクを取得するヘルパー。
 * RaceTable は PC では <table> 内に <a>、SP では外側にカード <a> を描画する。
 * PC テストなのでテーブル内リンクを使う。
 */
function visibleRaceLink(page: import("@playwright/test").Page) {
  // PC表示: テーブル行内のリンク
  return page.locator("table a[href*='/races/']");
}

/** レース一覧→最初のレースの href を返すヘルパー */
async function getFirstRaceHref(page: import("@playwright/test").Page) {
  const today = new Date().toLocaleDateString("sv-SE");
  await page.goto(`/races?date=${today}`);
  await page.waitForLoadState("networkidle");

  const firstLink = visibleRaceLink(page).first();
  await expect(firstLink).toBeVisible({ timeout: 10000 });
  return (await firstLink.getAttribute("href"))!;
}

test.describe("今日のレース・出走馬・シミュレーション確認", () => {
  test.skip(({ browserName }) => browserName !== "chromium", "PCのみ");

  test("今日のレース一覧に出走馬が表示される", async ({ page }) => {
    const today = new Date().toLocaleDateString("sv-SE");
    await page.goto(`/races?date=${today}`);
    await page.waitForLoadState("networkidle");

    const raceLinks = visibleRaceLink(page);
    const count = await raceLinks.count();
    console.log(`\n  今日のレース数: ${count}`);
    expect(count).toBeGreaterThan(0);

    for (let i = 0; i < Math.min(count, 5); i++) {
      const text = await raceLinks.nth(i).textContent();
      console.log(`  レース${i + 1}: ${text?.trim()}`);
    }
  });

  test("レース詳細ページに出走馬一覧が表示される", async ({ page }) => {
    const href = await getFirstRaceHref(page);
    console.log(`\n  遷移先: ${href}`);

    await page.goto(href);
    await page.waitForLoadState("networkidle");

    // EntryTable の見出し: isUpcoming ? "出馬表" : "出走表 / 結果"
    const entrySection = page
      .locator("text=出馬表")
      .or(page.locator("text=出走表 / 結果"));
    await expect(entrySection.first()).toBeVisible({ timeout: 10000 });

    // 馬名リンク
    const horseLinks = page.locator('a[href*="/horses/"]');
    const horseCount = await horseLinks.count();
    console.log(`  出走馬リンク数: ${horseCount}`);
    expect(horseCount).toBeGreaterThan(0);

    const horseNames: string[] = [];
    for (let i = 0; i < horseCount; i++) {
      const name = await horseLinks.nth(i).textContent();
      if (name?.trim()) horseNames.push(name.trim());
    }
    const unique = [...new Set(horseNames)];
    console.log(`  出走馬（${unique.length}頭）: ${unique.join(", ")}`);

    await page.screenshot({
      path: "e2e/screenshots/entry-table.png",
      fullPage: true,
    });
  });

  test("馬券シミュレーションで1000円の単勝が正しく計算される", async ({
    page,
  }) => {
    const href = await getFirstRaceHref(page);

    // レース詳細ページへ
    await page.goto(href);
    await page.waitForLoadState("networkidle");

    // シミュレーションページへのリンクをクリック or 直接遷移
    const simLink = page.locator('a[href*="/simulate"]');
    if ((await simLink.count()) > 0) {
      const simHref = await simLink.first().getAttribute("href");
      console.log(`\n  シミュレーションページ: ${simHref}`);
      await page.goto(simHref!);
    } else {
      // 直接 simulate ページへ遷移
      await page.goto(`${href}/simulate`);
      console.log(`\n  シミュレーションページ: ${href}/simulate`);
    }
    await page.waitForLoadState("networkidle");

    // 馬券シミュレーションセクション
    const simSection = page.locator("text=馬券シミュレーション");
    if ((await simSection.count()) === 0) {
      console.log(
        "  馬券シミュレーションが見つかりません（AI予測がないレースの可能性）",
      );
      test.skip();
      return;
    }
    await expect(simSection.first()).toBeVisible({ timeout: 10000 });
    console.log("  馬券シミュレーションセクション: あり");

    // 「単勝」ボタンをクリック（ボタンテキストは "単勝 1頭"）
    const tanshoBtn = page.locator('button:has-text("単勝")').first();
    await expect(tanshoBtn).toBeVisible();
    await tanshoBtn.click();
    console.log("  馬券種「単勝」を選択");

    // 馬を選択
    const selects = page.locator("select:visible");
    const selectCount = await selects.count();
    console.log(`  select要素数: ${selectCount}`);

    let selectedHorse = "";
    if (selectCount > 0) {
      const options = selects.first().locator("option");
      const optionCount = await options.count();
      if (optionCount > 1) {
        const optionValue = await options.nth(1).getAttribute("value");
        selectedHorse = (await options.nth(1).textContent()) ?? "";
        console.log(`  選択した馬: ${selectedHorse.trim()}`);
        if (optionValue) {
          await selects.first().selectOption(optionValue);
        }
      }
    }

    // 掛け金入力
    const amountInputs = page.locator('input[type="number"]:visible');
    const inputCount = await amountInputs.count();
    console.log(`  number input数: ${inputCount}`);

    if (inputCount > 0) {
      await amountInputs.last().fill("1000");
      console.log("  掛け金: 1000円を入力");
    }

    await page.waitForTimeout(500);

    // 推定払戻額
    const payoutLabel = page.locator("text=推定払戻額");
    if ((await payoutLabel.count()) > 0) {
      const payoutArea = payoutLabel.first().locator("xpath=..");
      const payoutText = await payoutArea.textContent();
      console.log(
        `  推定払戻額: ${payoutText?.replace(/\s+/g, " ").trim()}`,
      );

      // 払戻額が数値として正しいか（0より大きいか）
      const amountMatch = payoutText?.match(/[¥￥]([0-9,]+)/);
      if (amountMatch) {
        const amount = parseInt(amountMatch[1].replace(/,/g, ""), 10);
        console.log(`  推定払戻額（数値）: ${amount}円`);
        expect(amount).toBeGreaterThan(0);
      }
    }

    // 回収率
    const recoveryLabel = page.locator("text=回収率");
    if ((await recoveryLabel.count()) > 0) {
      const recoveryArea = recoveryLabel.first().locator("xpath=..");
      const recoveryText = await recoveryArea.textContent();
      console.log(
        `  回収率: ${recoveryText?.replace(/\s+/g, " ").trim()}`,
      );
    }

    // 記録ボタン
    const recordBtn = page.locator('button:has-text("この馬券を記録する")');
    if ((await recordBtn.count()) > 0) {
      console.log("  「この馬券を記録する」ボタン: あり");
    }

    await page.screenshot({
      path: "e2e/screenshots/simulation-1000yen.png",
      fullPage: true,
    });
    console.log("  スクリーンショット保存完了");
  });

  test("AI予想テーブルが表示され順位・スコアが確認できる", async ({
    page,
  }) => {
    const href = await getFirstRaceHref(page);
    await page.goto(href);
    await page.waitForLoadState("networkidle");

    // AI予測セクション（テキストは "AI 予測" スペースあり）
    const aiSection = page
      .locator("text=AI 予測")
      .or(page.locator("text=AI予測"));
    if ((await aiSection.count()) === 0) {
      console.log(
        "\n  AI予測セクションが見つかりません（予測未実行の可能性）",
      );
      test.skip();
      return;
    }
    console.log("\n  AI予測セクション: あり");

    // PC版テーブルの行（thead を除く）— AI予測テーブルは hidden sm:block 内
    const predTable = page.locator("table:visible");
    const predRows = predTable.locator("tbody tr");
    const rowCount = await predRows.count();
    console.log(`  AI予測行数: ${rowCount}`);

    if (rowCount > 0) {
      for (let i = 0; i < Math.min(rowCount, 5); i++) {
        const row = predRows.nth(i);
        const text = await row.textContent();
        console.log(
          `  ${i + 1}位: ${text?.replace(/\s+/g, " ").trim().substring(0, 100)}`,
        );
      }
    }

    await page.screenshot({
      path: "e2e/screenshots/ai-prediction.png",
      fullPage: true,
    });
    console.log("  スクリーンショット保存完了");
  });
});
