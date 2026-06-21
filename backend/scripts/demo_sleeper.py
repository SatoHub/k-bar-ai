"""府中牝馬S(本番データ)で巻き返し穴(sleeper)検出を実演。

本番から出走馬(馬番/人気/netkeiba_id/馬名)とレース馬場を取得し、人気薄(>=5番人気)の
各馬のnetkeiba全成績をスクレイプ→compute_sleeperで穴度を算出して表示する。
ミアネーロ(芝重賞実績→前走ダート大敗→14人気)が炙り出されるかを確認する。
"""

import asyncio
import base64
import datetime
import json
import sys
import urllib.request

from app.scraper.netkeiba import NetkeibaScraper
from app.services.sleeper import compute_sleeper

BASE = "http://133.117.72.213/api/v1"
AUTH = base64.b64encode(b"admin:kbar2026ai").decode()
RID = sys.argv[1] if len(sys.argv) > 1 else "202605030611"
MIN_FAV = int(sys.argv[2]) if len(sys.argv) > 2 else 5


def get(path):
    req = urllib.request.Request(f"{BASE}{path}", headers={"Authorization": f"Basic {AUTH}"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


async def main():
    race = get(f"/races/{RID}")
    surface = race.get("surface")
    rdate = datetime.date.fromisoformat(race["race_date"])
    print(f"=== {race['racecourse_name']} {race['race_name']} ({surface}{race['distance_m']}m) ===")

    targets = [
        e for e in race["entries"]
        if e.get("win_favorite") and e["win_favorite"] >= MIN_FAV and e["horse"].get("netkeiba_id")
    ]
    targets.sort(key=lambda e: e["win_favorite"])

    results = []
    async with NetkeibaScraper(headless=True) as nk:
        for e in targets:
            nid = e["horse"]["netkeiba_id"]
            try:
                career = await nk.scrape_horse_career(nid)
            except Exception as ex:  # noqa: BLE001
                print(f"  {e['horse']['name']}: career取得失敗 {ex}")
                continue
            s = compute_sleeper(surface, e["win_favorite"], career, before_date=rdate)
            results.append((e, s, len(career)))

    results.sort(key=lambda x: -x[1]["score"])
    print(f"\n人気{MIN_FAV}番手以下 {len(results)}頭を分析:\n")
    for e, s, ncareer in results:
        mark = "🔴穴" if s["is_sleeper"] else "  "
        print(f"{mark} {e['win_favorite']:>2}人気 {e['horse']['name']:<12} "
              f"穴度{s['score']:.2f} (全{ncareer}走) {s['reason']}")


if __name__ == "__main__":
    asyncio.run(main())
