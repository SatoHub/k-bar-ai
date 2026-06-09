/**
 * 本日（2026-02-28）のデータ整合性チェック
 * - 全レースの取得確認
 * - 全出走馬の取得確認
 * - 全レースのAI予想確認
 * - 全レースのオッズ取得確認
 */
import { test, expect } from "@playwright/test";

const TODAY = "2026-02-28";
const BASE_URL = "http://localhost:3000";
const API_BASE = "http://localhost:8000/api/v1";

// 本日の開催場
const EXPECTED_VENUES = ["中山", "小倉", "阪神"];
const RACES_PER_VENUE = 12;
const TOTAL_RACES = 36;

test.describe("本日のデータ整合性チェック", () => {
  test("1. API: 全レース取得確認", async ({ request }) => {
    const resp = await request.get(
      `${API_BASE}/races?date=${TODAY}&per_page=100`,
    );
    expect(resp.ok()).toBeTruthy();
    const data = await resp.json();
    const races = data.items || data;

    console.log(`\n=== レース取得状況 ===`);
    console.log(`取得レース数: ${races.length} / 期待: ${TOTAL_RACES}`);

    // 開催場ごとのレース数
    const byVenue: Record<string, any[]> = {};
    for (const race of races) {
      const venue = race.racecourse_name;
      if (!byVenue[venue]) byVenue[venue] = [];
      byVenue[venue].push(race);
    }

    for (const venue of EXPECTED_VENUES) {
      const count = byVenue[venue]?.length || 0;
      console.log(
        `  ${venue}: ${count}R ${count === RACES_PER_VENUE ? "✅" : "❌"}`,
      );
    }

    // stub_only のレースがないか
    const stubs = races.filter((r: any) => r.stub_only);
    console.log(`  stub_onlyレース: ${stubs.length}件`);
    if (stubs.length > 0) {
      for (const s of stubs) {
        console.log(
          `    ⚠ ${s.racecourse_name} ${s.race_number}R ${s.race_name} (stub_only)`,
        );
      }
    }

    expect(races.length).toBe(TOTAL_RACES);
  });

  test("2. API: 全出走馬の取得確認", async ({ request }) => {
    const resp = await request.get(
      `${API_BASE}/races?date=${TODAY}&per_page=100`,
    );
    const data = await resp.json();
    const races = data.items || data;

    console.log(`\n=== 出走馬取得状況 ===`);

    let totalEntries = 0;
    let racesWithFewEntries = 0;
    const problems: string[] = [];

    for (const race of races) {
      const detailResp = await request.get(
        `${API_BASE}/races/${race.race_id}`,
      );
      if (!detailResp.ok()) {
        problems.push(
          `${race.racecourse_name} ${race.race_number}R: API エラー (${detailResp.status()})`,
        );
        continue;
      }
      const detail = await detailResp.json();
      const entries = detail.entries || [];
      totalEntries += entries.length;

      // head_countとentriesの数が一致するか
      if (race.head_count && entries.length !== race.head_count) {
        problems.push(
          `${race.racecourse_name} ${race.race_number}R: entries=${entries.length} vs head_count=${race.head_count}`,
        );
      }

      // 出走馬が極端に少ないレース
      if (entries.length < 5) {
        racesWithFewEntries++;
        console.log(
          `  ⚠ ${race.racecourse_name} ${race.race_number}R: ${entries.length}頭 (少頭数)`,
        );
      }

      // 馬名が空のエントリがないか（horse.name を確認）
      const noName = entries.filter(
        (e: any) => !e.horse || !e.horse.name,
      );
      if (noName.length > 0) {
        problems.push(
          `${race.racecourse_name} ${race.race_number}R: 馬名なし ${noName.length}件`,
        );
      }

      // 騎手が空のエントリ
      const noJockey = entries.filter(
        (e: any) => !e.jockey || !e.jockey.name,
      );
      if (noJockey.length > 0) {
        problems.push(
          `${race.racecourse_name} ${race.race_number}R: 騎手名なし ${noJockey.length}件`,
        );
      }
    }

    console.log(`  総出走馬数: ${totalEntries}`);
    console.log(`  少頭数レース: ${racesWithFewEntries}件`);
    console.log(`  問題: ${problems.length}件`);
    for (const p of problems) {
      console.log(`    ❌ ${p}`);
    }

    expect(problems.length).toBe(0);
  });

  test("3. API: 全レースのAI予想確認", async ({ request }) => {
    const resp = await request.get(
      `${API_BASE}/races?date=${TODAY}&per_page=100`,
    );
    const data = await resp.json();
    const races = data.items || data;

    console.log(`\n=== AI予想状況 ===`);

    let racesWithPrediction = 0;
    let racesWithoutPrediction = 0;
    let totalPredictions = 0;
    const problems: string[] = [];

    for (const race of races) {
      // 正しいパス: /predictions/{race_id}
      const predResp = await request.get(
        `${API_BASE}/predictions/${race.race_id}`,
      );
      if (!predResp.ok()) {
        problems.push(
          `${race.racecourse_name} ${race.race_number}R: 予想API エラー (${predResp.status()})`,
        );
        racesWithoutPrediction++;
        continue;
      }
      const predData = await predResp.json();
      const predList = predData.predictions || [];

      if (predList.length === 0) {
        racesWithoutPrediction++;
        problems.push(
          `${race.racecourse_name} ${race.race_number}R ${race.race_name}: AI予想なし`,
        );
      } else {
        racesWithPrediction++;
        totalPredictions += predList.length;

        // predicted_positionが全て同じ（バグの可能性）
        const positions = predList.map((p: any) => p.predicted_position);
        const uniquePositions = new Set(positions);
        if (uniquePositions.size === 1 && predList.length > 1) {
          problems.push(
            `${race.racecourse_name} ${race.race_number}R: 全馬同順位(=${positions[0]})`,
          );
        }

        // horse_nameが空
        const noName = predList.filter((p: any) => !p.horse_name);
        if (noName.length > 0) {
          problems.push(
            `${race.racecourse_name} ${race.race_number}R: 予想に馬名なし ${noName.length}件`,
          );
        }

        // head_countと予想数の整合性
        if (race.head_count && predList.length !== race.head_count) {
          console.log(
            `  ⚠ ${race.racecourse_name} ${race.race_number}R: 予想${predList.length}件 vs 出走${race.head_count}頭`,
          );
        }
      }
    }

    console.log(`  予想ありレース: ${racesWithPrediction} / ${TOTAL_RACES}`);
    console.log(`  予想なしレース: ${racesWithoutPrediction}`);
    console.log(`  総予想数: ${totalPredictions}`);
    console.log(`  問題: ${problems.length}件`);
    for (const p of problems) {
      console.log(`    ❌ ${p}`);
    }

    expect(racesWithoutPrediction).toBe(0);
  });

  test("4. API: 全レースのオッズ取得確認", async ({ request }) => {
    const resp = await request.get(
      `${API_BASE}/races?date=${TODAY}&per_page=100`,
    );
    const data = await resp.json();
    const races = data.items || data;

    console.log(`\n=== オッズ取得状況 ===`);

    let racesWithOdds = 0;
    let racesWithoutOdds = 0;
    const problems: string[] = [];

    for (const race of races) {
      const oddsResp = await request.get(
        `${API_BASE}/races/${race.race_id}/odds`,
      );
      if (!oddsResp.ok()) {
        racesWithoutOdds++;
        problems.push(
          `${race.racecourse_name} ${race.race_number}R: オッズAPI エラー (${oddsResp.status()})`,
        );
        continue;
      }
      const oddsData = await oddsResp.json();
      const oddsList = oddsData.entries || [];

      if (oddsList.length === 0) {
        racesWithoutOdds++;
        problems.push(
          `${race.racecourse_name} ${race.race_number}R ${race.race_name}: オッズなし`,
        );
      } else {
        racesWithOdds++;

        // win_oddsがnull/0の馬
        const noOdds = oddsList.filter(
          (o: any) => !o.win_odds || o.win_odds <= 0,
        );
        if (noOdds.length > 0) {
          problems.push(
            `${race.racecourse_name} ${race.race_number}R: win_odds欠損 ${noOdds.length}頭`,
          );
        }
      }
    }

    console.log(`  オッズありレース: ${racesWithOdds} / ${TOTAL_RACES}`);
    console.log(`  オッズなしレース: ${racesWithoutOdds}`);
    console.log(`  問題: ${problems.length}件`);
    for (const p of problems) {
      console.log(`    ❌ ${p}`);
    }

    if (racesWithoutOdds > 0) {
      console.log(`\n  ⚠ ${racesWithoutOdds}レースでオッズ未取得`);
    }

    expect(racesWithoutOdds).toBe(0);
  });

  test("5. UI: レース一覧ページ表示確認", async ({ page }) => {
    await page.goto(`${BASE_URL}/races?date=${TODAY}`);
    await page.waitForLoadState("networkidle");
    await page.waitForTimeout(3000);

    console.log(`\n=== UI レース一覧表示 ===`);

    await page.screenshot({
      path: "e2e/screenshots/integrity-races-list.png",
      fullPage: true,
    });

    // レースカードまたはテーブル行の数
    const raceLinks = page.locator("a[href*='/races/']");
    const count = await raceLinks.count();
    console.log(`  レースリンク数: ${count}`);

    // 各開催場のタブ
    for (const venue of EXPECTED_VENUES) {
      const tab = page.getByText(venue, { exact: false });
      const tabCount = await tab.count();
      console.log(`  ${venue}タブ: ${tabCount > 0 ? "あり ✅" : "なし ❌"}`);
    }

    expect(count).toBeGreaterThan(0);
  });

  test("6. UI: レース詳細 - AI予想・オッズ・出走馬の表示確認", async ({
    page,
    request,
  }) => {
    const resp = await request.get(
      `${API_BASE}/races?date=${TODAY}&per_page=100`,
    );
    const data = await resp.json();
    const races = data.items || data;

    console.log(`\n=== UI レース詳細確認 ===`);

    // 各開催場から代表レース1つずつ + 重賞(あれば)
    const toCheck: any[] = [];
    const checkedVenues = new Set<string>();
    for (const race of races) {
      if (!checkedVenues.has(race.racecourse_name)) {
        toCheck.push(race);
        checkedVenues.add(race.racecourse_name);
      }
      if (race.graded_race) {
        toCheck.push(race);
      }
    }

    for (const race of toCheck.slice(0, 4)) {
      console.log(
        `\n  --- ${race.racecourse_name} ${race.race_number}R ${race.race_name} ---`,
      );

      await page.goto(`${BASE_URL}/races/${race.race_id}`);
      await page.waitForLoadState("networkidle");
      await page.waitForTimeout(2000);

      await page.screenshot({
        path: `e2e/screenshots/integrity-detail-${race.racecourse_name}-${race.race_number}R.png`,
        fullPage: true,
      });

      // ページ全体のテキスト
      const bodyText = (await page.locator("body").textContent()) || "";

      // 出走馬テーブル
      const hasEntryTable =
        bodyText.includes("枠") || bodyText.includes("馬番");
      console.log(
        `    出走馬テーブル: ${hasEntryTable ? "表示 ✅" : "非表示 ❌"}`,
      );

      // AI予想
      const hasAIPrediction =
        bodyText.includes("AI予想") || bodyText.includes("predicted");
      console.log(
        `    AI予想: ${hasAIPrediction ? "表示 ✅" : "非表示 ❌"}`,
      );

      // AI予想に馬名が出ているか
      const predResp = await request.get(
        `${API_BASE}/predictions/${race.race_id}`,
      );
      if (predResp.ok()) {
        const predData = await predResp.json();
        const firstHorse = predData.predictions?.[0]?.horse_name;
        if (firstHorse) {
          const horseInPage = bodyText.includes(firstHorse);
          console.log(
            `    AI予想1位(${firstHorse}): ${horseInPage ? "表示あり ✅" : "表示なし ❌"}`,
          );
        }
      }

      // オッズ
      const hasOdds =
        bodyText.includes("オッズ") && bodyText.includes("倍");
      console.log(`    オッズデータ: ${hasOdds ? "表示 ✅" : "なし ❌"}`);
    }
  });

  test("7. 総合サマリーレポート", async ({ request }) => {
    const resp = await request.get(
      `${API_BASE}/races?date=${TODAY}&per_page=100`,
    );
    const data = await resp.json();
    const races = data.items || data;

    let totalEntries = 0;
    let entriesWithHorseName = 0;
    let entriesWithJockey = 0;
    let racesWithPreds = 0;
    let racesWithOdds = 0;
    let totalPreds = 0;
    let totalOdds = 0;
    const stubRaces = races.filter((r: any) => r.stub_only).length;

    for (const race of races) {
      // Entries
      const detailResp = await request.get(
        `${API_BASE}/races/${race.race_id}`,
      );
      if (detailResp.ok()) {
        const detail = await detailResp.json();
        const entries = detail.entries || [];
        totalEntries += entries.length;
        entriesWithHorseName += entries.filter(
          (e: any) => e.horse?.name,
        ).length;
        entriesWithJockey += entries.filter(
          (e: any) => e.jockey?.name,
        ).length;
      }

      // Predictions
      const predResp = await request.get(
        `${API_BASE}/predictions/${race.race_id}`,
      );
      if (predResp.ok()) {
        const preds = await predResp.json();
        const predList = preds.predictions || [];
        if (predList.length > 0) {
          racesWithPreds++;
          totalPreds += predList.length;
        }
      }

      // Odds
      const oddsResp = await request.get(
        `${API_BASE}/races/${race.race_id}/odds`,
      );
      if (oddsResp.ok()) {
        const odds = await oddsResp.json();
        const oddsList = odds.entries || [];
        if (oddsList.length > 0) {
          racesWithOdds++;
          totalOdds += oddsList.length;
        }
      }
    }

    console.log(`\n╔═══════════════════════════════════════════════════╗`);
    console.log(`║        本日(${TODAY})データ整合性サマリー          ║`);
    console.log(`╠═══════════════════════════════════════════════════╣`);
    console.log(
      `║ レース数:       ${String(races.length).padStart(3)} / ${TOTAL_RACES}                ${races.length === TOTAL_RACES ? "✅" : "❌"} ║`,
    );
    console.log(
      `║ stub_onlyレース: ${String(stubRaces).padStart(3)}                        ${stubRaces === 0 ? "✅" : "⚠"} ║`,
    );
    console.log(
      `║ 出走馬数:       ${String(totalEntries).padStart(3)}                       ${totalEntries > 0 ? "✅" : "❌"} ║`,
    );
    console.log(
      `║ 馬名あり:       ${String(entriesWithHorseName).padStart(3)} / ${totalEntries}             ${entriesWithHorseName === totalEntries ? "✅" : "❌"} ║`,
    );
    console.log(
      `║ 騎手名あり:     ${String(entriesWithJockey).padStart(3)} / ${totalEntries}             ${entriesWithJockey === totalEntries ? "✅" : "❌"} ║`,
    );
    console.log(
      `║ AI予想:         ${String(racesWithPreds).padStart(3)} / ${TOTAL_RACES} レース        ${racesWithPreds === TOTAL_RACES ? "✅" : "❌"} ║`,
    );
    console.log(
      `║ 予想馬数:       ${String(totalPreds).padStart(3)}                       ${totalPreds > 0 ? "✅" : "❌"} ║`,
    );
    console.log(
      `║ オッズ:         ${String(racesWithOdds).padStart(3)} / ${TOTAL_RACES} レース        ${racesWithOdds === TOTAL_RACES ? "✅" : "❌"} ║`,
    );
    console.log(
      `║ オッズ件数:     ${String(totalOdds).padStart(3)}                       ${totalOdds > 0 ? "✅" : "❌"} ║`,
    );
    console.log(`╚═══════════════════════════════════════════════════╝`);
  });
});
