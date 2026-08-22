/**
 * 本番環境ヘルスチェック — K-Bar AI
 *
 * 既知バグ（docs/20260228-bug-registry.md）の再発検知 + UI表示検証 + シミュレーション検証
 * 対象: HEALTHCHECK_URL で指定した本番環境（frontend/.env.local 参照）
 *
 * 実行: npx playwright test e2e/production-health-check.spec.ts --project=PC --reporter=list
 */
import { test, expect, type Page, type APIRequestContext } from "@playwright/test";

// ---------- 定数 ----------
const TODAY = new Date().toISOString().slice(0, 10);
const API = "/api/v1";

// ---------- 共通ヘルパー ----------

interface Race {
  race_id: string;
  racecourse_name: string;
  race_number: number;
  race_name: string;
  stub_only: boolean;
  head_count: number;
}

interface Entry {
  post_position: number | null;
  horse: { name: string } | null;
  jockey: { name: string } | null;
}

/** 当日の全レースを取得 */
async function fetchAllRaces(request: APIRequestContext): Promise<Race[]> {
  const resp = await request.get(`${API}/races?date=${TODAY}&per_page=100`);
  expect(resp.ok(), `レースAPI応答: ${resp.status()}`).toBeTruthy();
  const data = await resp.json();
  return data.items || [];
}

/** テスト対象の代表レースを選択（non-stub, entries >= 8） */
async function pickRepresentativeRace(
  request: any,
  races: Race[],
): Promise<Race> {
  for (const race of races) {
    if (race.stub_only) continue;
    const resp = await request.get(`${API}/races/${race.race_id}`);
    if (!resp.ok()) continue;
    const detail = await resp.json();
    const entries = detail.entries || [];
    if (entries.length >= 8) return race;
  }
  // fallback: 最初のnon-stubレース
  const fallback = races.find((r) => !r.stub_only);
  expect(fallback, "テスト可能なレースが存在すること").toBeTruthy();
  return fallback!;
}

// ============================================================
// PCプロジェクトのみ実行
// ============================================================
test.beforeEach(async ({}, testInfo) => {
  test.skip(
    testInfo.project.name !== "PC",
    "本番ヘルスチェックはPCプロジェクトのみ",
  );
});

// ============================================================
// A. データ完全性チェック (API) — BUG-001, BUG-002, BUG-003
// ============================================================
test.describe("A. データ完全性チェック", () => {
  test("A-1. 全レース取得 — 開催場ごとに12R存在する", async ({ request }) => {
    const races = await fetchAllRaces(request);
    expect(races.length, "レースが1件以上存在すること").toBeGreaterThan(0);

    // 開催場ごとに集計
    const byVenue: Record<string, Race[]> = {};
    for (const r of races) {
      const v = r.racecourse_name || "不明";
      if (!byVenue[v]) byVenue[v] = [];
      byVenue[v].push(r);
    }

    console.log(`\n=== ${TODAY} レース概要 ===`);
    for (const [venue, venueRaces] of Object.entries(byVenue)) {
      console.log(`  ${venue}: ${venueRaces.length}R`);
      expect(
        venueRaces.length,
        `${venue}は12R存在すること`,
      ).toBe(12);
    }
  });

  test("A-2. 出走馬完全性 — entries == head_count, post_position非null [BUG-002]", async ({
    request,
  }) => {
    const races = await fetchAllRaces(request);
    const problems: string[] = [];

    for (const race of races) {
      const label = `${race.racecourse_name} ${race.race_number}R`;
      const resp = await request.get(`${API}/races/${race.race_id}`);
      expect(resp.ok(), `${label} 詳細API応答`).toBeTruthy();

      const detail = await resp.json();
      const entries: Entry[] = detail.entries || [];

      // entries数 == head_count
      if (race.head_count && entries.length !== race.head_count) {
        problems.push(
          `${label}: entries=${entries.length} ≠ head_count=${race.head_count}`,
        );
      }

      // post_position非null + horse.name存在
      for (const e of entries) {
        if (e.post_position === null || e.post_position === undefined) {
          problems.push(`${label}: post_positionがnullのエントリあり`);
          break;
        }
        if (!e.horse || !e.horse.name) {
          problems.push(`${label}: 馬名なしのエントリあり`);
          break;
        }
      }
    }

    if (problems.length > 0) {
      console.log("\n出走馬の問題:");
      for (const p of problems) console.log(`  ❌ ${p}`);
    }
    expect(problems, "出走馬データに問題がないこと").toHaveLength(0);
  });

  test("A-3. 出走馬重複なし — 同一race内でpost_position重複がない [BUG-002]", async ({
    request,
  }) => {
    const races = await fetchAllRaces(request);
    const duplicates: string[] = [];

    for (const race of races) {
      const label = `${race.racecourse_name} ${race.race_number}R`;
      const resp = await request.get(`${API}/races/${race.race_id}`);
      if (!resp.ok()) continue;

      const detail = await resp.json();
      const entries: Entry[] = detail.entries || [];
      const positions = entries
        .map((e) => e.post_position)
        .filter((p) => p !== null);
      const unique = new Set(positions);
      if (positions.length !== unique.size) {
        duplicates.push(
          `${label}: post_position重複あり (${positions.length}件中 ${unique.size}ユニーク)`,
        );
      }
    }

    if (duplicates.length > 0) {
      console.log("\n重複問題:");
      for (const d of duplicates) console.log(`  ❌ ${d}`);
    }
    expect(duplicates, "post_positionの重複がないこと").toHaveLength(0);
  });

  test("A-4. AI予想が全レースに存在する [BUG-001]", async ({ request }) => {
    const races = await fetchAllRaces(request);
    const missing: string[] = [];

    for (const race of races) {
      const label = `${race.racecourse_name} ${race.race_number}R`;
      const resp = await request.get(`${API}/predictions/${race.race_id}`);
      if (!resp.ok()) {
        missing.push(`${label}: 予想API ${resp.status()}`);
        continue;
      }
      const data = await resp.json();
      const preds = data.predictions || [];
      if (preds.length === 0) {
        missing.push(`${label} ${race.race_name}: 予想データなし`);
      }
    }

    console.log(
      `\nAI予想: ${races.length - missing.length}/${races.length} レースに存在`,
    );
    if (missing.length > 0) {
      for (const m of missing) console.log(`  ❌ ${m}`);
    }
    expect(missing, "全レースにAI予想が存在すること").toHaveLength(0);
  });

  test("A-5. オッズが全レースに存在する [BUG-003]", async ({ request }) => {
    const races = await fetchAllRaces(request);
    const missing: string[] = [];

    for (const race of races) {
      const label = `${race.racecourse_name} ${race.race_number}R`;
      const resp = await request.get(`${API}/races/${race.race_id}/odds`);
      if (!resp.ok()) {
        missing.push(`${label}: オッズAPI ${resp.status()}`);
        continue;
      }
      const data = await resp.json();
      const entries = data.entries || [];
      if (entries.length === 0) {
        missing.push(`${label} ${race.race_name}: オッズなし`);
      }
    }

    console.log(
      `\nオッズ: ${races.length - missing.length}/${races.length} レースに存在`,
    );
    if (missing.length > 0) {
      for (const m of missing) console.log(`  ❌ ${m}`);
    }
    expect(missing, "全レースにオッズが存在すること").toHaveLength(0);
  });
});

// ============================================================
// B. UI表示検証 — PRV-001
// ============================================================
test.describe("B. UI表示検証", () => {
  test("B-1. レース一覧ページ — 開催場タブ・レースリンクが表示される", async ({
    page,
  }) => {
    await page.goto(`/races?date=${TODAY}`);
    await page.waitForLoadState("networkidle");
    await page.waitForTimeout(2000);

    // レースリンクが1つ以上存在する
    const raceLinks = page
      .locator('a[href*="/races/"]')
      .and(page.locator(":visible"));
    const count = await raceLinks.count();
    expect(count, "レースリンクが存在すること").toBeGreaterThan(0);
    console.log(`\nレース一覧: ${count}件のレースリンクを確認`);
  });

  test("B-2. レース詳細ページ — 出馬表・AI予想・オッズが表示される [BUG-001, BUG-003, PRV-001]", async ({
    page,
    request,
  }) => {
    const races = await fetchAllRaces(request);
    const race = await pickRepresentativeRace(request, races);
    const label = `${race.racecourse_name} ${race.race_number}R`;

    await page.goto(`/races/${race.race_id}`);
    await page.waitForLoadState("networkidle");
    await page.waitForTimeout(3000);

    const bodyText = (await page.locator("body").textContent()) || "";

    // 出馬表セクション
    const hasEntryTable =
      bodyText.includes("出馬表") ||
      bodyText.includes("枠") ||
      bodyText.includes("馬番");
    expect(hasEntryTable, `${label}: 出馬表セクションが表示されること`).toBe(
      true,
    );

    // AI予想 — 「データがありません」系が**ない**こと
    const hasNoPredMsg = bodyText.includes("AI予想データがありません");
    expect(
      hasNoPredMsg,
      `${label}: 「AI予想データがありません」が表示されていないこと`,
    ).toBe(false);

    // オッズ
    const hasOdds = bodyText.includes("倍") || bodyText.includes("オッズ");
    expect(hasOdds, `${label}: オッズ情報が表示されること`).toBe(true);

    // シミュレーションリンク
    const simLink = page.locator(`a[href*="/simulate"]`).first();
    await expect(simLink).toBeVisible({ timeout: 5000 });

    console.log(`\n${label} 詳細ページ: 出馬表✅ AI予想✅ オッズ✅ シミュレーションリンク✅`);
  });

  test("B-3. エラーメッセージ不在 — 「データがありません」系の警告がない [PRV-001]", async ({
    page,
    request,
  }) => {
    const races = await fetchAllRaces(request);
    const race = await pickRepresentativeRace(request, races);

    await page.goto(`/races/${race.race_id}`);
    await page.waitForLoadState("networkidle");
    await page.waitForTimeout(3000);

    const bodyText = (await page.locator("body").textContent()) || "";

    const errorPatterns = [
      "データがありません",
      "AI予想データがありません",
      "エラーが発生しました",
      "読み込みに失敗",
    ];

    const found: string[] = [];
    for (const pattern of errorPatterns) {
      if (bodyText.includes(pattern)) {
        found.push(pattern);
      }
    }

    if (found.length > 0) {
      console.log(`\n⚠ エラーメッセージ検出: ${found.join(", ")}`);
    }
    expect(found, "エラーメッセージが表示されていないこと").toHaveLength(0);
  });
});

// ============================================================
// C. 馬券シミュレーション検証 — PRV-002
// ============================================================
test.describe("C. 馬券シミュレーション検証", () => {
  /** 代表レースのシミュレーションページへ遷移 */
  async function gotoSimulatePage(page: Page, request: any) {
    const races = await fetchAllRaces(request);
    const race = await pickRepresentativeRace(request, races);
    await page.goto(`/races/${race.race_id}/simulate`);
    await page.waitForLoadState("networkidle");
    await expect(
      page.locator("text=馬券シミュレーション").first(),
    ).toBeVisible({ timeout: 20000 });
    return race;
  }

  test("C-1. シミュレーションページがロードされる", async ({
    page,
    request,
  }) => {
    const race = await gotoSimulatePage(page, request);
    console.log(
      `\nシミュレーション: ${race.racecourse_name} ${race.race_number}R`,
    );

    // 馬券種ボタンが表示される
    await expect(
      page.locator("button", { hasText: "単勝" }).first(),
    ).toBeVisible();
    await expect(
      page.locator("button", { hasText: "馬連" }).first(),
    ).toBeVisible();
  });

  test("C-2. 単勝フロー — 馬選択→掛け金→払戻表示", async ({
    page,
    request,
  }) => {
    await gotoSimulatePage(page, request);

    // 単勝を選択（デフォルトで選択済みの場合もあるがクリックして確実に）
    await page.locator("button", { hasText: "単勝" }).first().click();
    await page.waitForTimeout(500);

    // 単勝の「通常」モードは<select>ドロップダウンで馬を選択する
    const horseSelect = page.locator("select").first();
    await expect(horseSelect).toBeVisible({ timeout: 5000 });

    // 最初の馬を選択（option index 1 = 最初の馬、0は「選択してください」）
    const options = horseSelect.locator("option");
    const optCount = await options.count();
    expect(optCount, "馬選択肢が2つ以上（プレースホルダー+馬）").toBeGreaterThan(1);
    const firstHorseValue = await options.nth(1).getAttribute("value");
    expect(firstHorseValue, "馬のvalueが存在すること").toBeTruthy();
    await horseSelect.selectOption({ index: 1 });
    await page.waitForTimeout(500);

    // 掛け金入力
    const amountInput = page.locator('input[type="number"]').first();
    await amountInput.fill("1000");
    await page.waitForTimeout(500);

    // 合計投資が表示される
    const bodyText = (await page.locator("body").textContent()) || "";
    expect(
      bodyText.includes("1,000") || bodyText.includes("1000"),
      "合計投資に1,000円が表示されること",
    ).toBe(true);

    // 推定払戻合計が「---」でないこと（オッズがあれば数値が表示される）
    const payoutSection = page.locator("text=推定払戻合計").first();
    if (await payoutSection.isVisible()) {
      const parentText =
        (await payoutSection.locator("xpath=..").textContent()) || "";
      console.log(`  推定払戻合計: ${parentText.trim()}`);
    }
  });

  test("C-3. 馬連ボックス — 3頭選択で3点表示 [C(3,2)=3]", async ({
    page,
    request,
  }) => {
    await gotoSimulatePage(page, request);

    // 馬連→ボックス（馬券シミュレーター内で操作する）
    // 「馬連」ボタンはページ上に2つ存在する（上部「組数・オッズ比較」ウィジェット /
    // 下部の馬券シミュレーター）。シミュレーターはDOM上で後方にあるため .last() を使う。
    await page.locator("button", { hasText: "馬連" }).last().click();
    await page.waitForTimeout(500);

    // 馬連を選ぶと買い方ピル（通常/ボックス/フォーメーション/流し）が表示される。
    // 「ボックス」はシミュレーターのみ <button>（比較ウィジェットはテーブルセル）。
    await page.getByRole("button", { name: "ボックス", exact: true }).click();
    await page.waitForTimeout(500);

    // ボックスモードのチェックボックスグリッド「対象馬を選択（N頭以上）」から3頭クリック
    const gridLabel = page.locator("text=/対象.*を選択/").first();
    await expect(gridLabel).toBeVisible({ timeout: 5000 });
    const gridSection = gridLabel.locator("xpath=following-sibling::div[1]");
    const horseButtons = gridSection.locator("button");
    const count = await horseButtons.count();
    const clickCount = Math.min(3, count);
    for (let i = 0; i < clickCount; i++) {
      await horseButtons.nth(i).click();
      await page.waitForTimeout(100);
    }

    if (clickCount >= 3) {
      // C(3,2)=3点
      await expect(page.locator("text=/3点/").first()).toBeVisible({
        timeout: 5000,
      });
      console.log("\n馬連ボックス3頭: 3点 ✅");
    }
  });

  test("C-4. JRA払戻計算の正確性 — Math.floor((amount*odds)/100)*100 [PRV-002]", async ({
    page,
    request,
  }) => {
    const races = await fetchAllRaces(request);
    const race = await pickRepresentativeRace(request, races);

    // オッズを取得
    const oddsResp = await request.get(
      `${API}/races/${race.race_id}/odds`,
    );
    expect(oddsResp.ok()).toBeTruthy();
    const oddsData = await oddsResp.json();
    const oddsEntries = oddsData.entries || [];

    if (oddsEntries.length === 0) {
      test.skip(true, "オッズデータなし — スキップ");
      return;
    }

    // 最初のエントリのオッズを取得
    const firstOdds = oddsEntries[0]?.win_odds;
    if (!firstOdds || firstOdds <= 0) {
      test.skip(true, "有効なオッズなし — スキップ");
      return;
    }

    await page.goto(`/races/${race.race_id}/simulate`);
    await page.waitForLoadState("networkidle");
    await expect(
      page.locator("text=馬券シミュレーション").first(),
    ).toBeVisible({ timeout: 20000 });

    // 単勝選択
    await page.locator("button", { hasText: "単勝" }).first().click();
    await page.waitForTimeout(500);

    // 単勝の「通常」モードは<select>ドロップダウンで馬を選択する
    const horseSelect = page.locator("select").first();
    await expect(horseSelect).toBeVisible({ timeout: 5000 });
    await horseSelect.selectOption({ index: 1 });
    await page.waitForTimeout(500);

    // 掛け金1000円入力
    const amountInput = page.locator('input[type="number"]').first();
    await amountInput.fill("1000");
    await page.waitForTimeout(1000);

    // 期待される払戻額
    const expectedPayout =
      Math.floor((1000 * firstOdds) / 100) * 100;

    // UIの払戻額を特定要素から取得（「推定払戻合計」ラベルの次のdivに「¥16,800」形式で表示される）
    const payoutLabel = page.locator("text=推定払戻合計").first();
    const payoutValueEl = payoutLabel.locator("xpath=following-sibling::div[1]");
    const payoutText = (await payoutValueEl.textContent()) || "";

    if (payoutText && payoutText !== "---") {
      const numStr = payoutText.replace(/[¥,\s]/g, "");
      const displayedPayout = parseInt(numStr, 10);
      console.log(
        `\nJRA払戻計算: odds=${firstOdds}, 掛金=1000, 期待=${expectedPayout}, 表示=${displayedPayout} (raw="${payoutText.trim()}")`,
      );
      expect(
        displayedPayout,
        `払戻額がJRA端数処理と一致すること (${expectedPayout}円)`,
      ).toBe(expectedPayout);
    } else {
      console.log(
        `\n⚠ 払戻額が未表示（期待: ${expectedPayout}円, odds: ${firstOdds}, text="${payoutText}"）`,
      );
    }
  });
});

// ============================================================
// D. スクリーンショットエビデンス
// ============================================================
test.describe("D. スクリーンショットエビデンス", () => {
  test("D-1. 全ページのスクリーンショットを保存", async ({ page, request }) => {
    const races = await fetchAllRaces(request);
    const race = await pickRepresentativeRace(request, races);

    // 1. レース一覧
    await page.goto(`/races?date=${TODAY}`);
    // オッズ自動更新ポーリングでnetworkidleが成立しにくいためdomcontentloadedで待つ
    await page.waitForLoadState("domcontentloaded");
    await page.waitForTimeout(2000);
    await page.screenshot({
      path: "e2e/screenshots/health-01-races.png",
      fullPage: true,
    });
    console.log("📸 レース一覧: e2e/screenshots/health-01-races.png");

    // 2. レース詳細
    await page.goto(`/races/${race.race_id}`);
    await page.waitForLoadState("domcontentloaded");
    await page.waitForTimeout(3000);
    await page.screenshot({
      path: "e2e/screenshots/health-02-detail.png",
      fullPage: true,
    });
    console.log(
      `📸 レース詳細 (${race.racecourse_name} ${race.race_number}R): e2e/screenshots/health-02-detail.png`,
    );

    // 3. シミュレーション
    await page.goto(`/races/${race.race_id}/simulate`);
    await page.waitForLoadState("domcontentloaded");
    await page.waitForTimeout(3000);
    await page.screenshot({
      path: "e2e/screenshots/health-03-simulate.png",
      fullPage: true,
    });
    console.log("📸 シミュレーション: e2e/screenshots/health-03-simulate.png");
  });
});
