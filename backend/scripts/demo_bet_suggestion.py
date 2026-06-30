"""府中牝馬S(本番データ)で買い目自動提案エンジンを実演。

本番APIから予想(予想順・荒れ度)とレース詳細(馬番・単勝オッズ・人気)を取得し、
予算3000円で suggest() を実行して結果を表示する。
（comboオッズはライブ取得していないため払戻はフェアオッズ推定＝目安）
"""

import base64
import json
import os
import sys
import urllib.request

from app.services.bet_suggestion import suggest

# Configure via env: KBAR_API_BASE, KBAR_API_USER, KBAR_API_PASS
BASE = os.environ.get("KBAR_API_BASE", "http://localhost:8000/api/v1")
_USER = os.environ.get("KBAR_API_USER", "")
_PASS = os.environ.get("KBAR_API_PASS", "")
AUTH = base64.b64encode(f"{_USER}:{_PASS}".encode()).decode()
RID = sys.argv[1] if len(sys.argv) > 1 else "202605030611"
BUDGET = int(sys.argv[2]) if len(sys.argv) > 2 else 3000

BET_JA = {"fukusho": "複勝", "wide": "ワイド", "umaren": "馬連",
          "trio": "三連複", "trifecta": "三連単"}


def get(path):
    req = urllib.request.Request(f"{BASE}{path}", headers={"Authorization": f"Basic {AUTH}"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def main():
    pred = get(f"/predictions/{RID}")
    race = get(f"/races/{RID}")

    # name -> entry (post, odds, fav)
    by_name = {}
    for e in race["entries"]:
        by_name[e["horse"]["name"]] = {
            "post": e["post_position"],
            "win_odds": float(e["win_odds"]) if e.get("win_odds") else None,
            "win_favorite": e.get("win_favorite"),
        }

    horses, ranked_pairs = [], []
    for p in pred["predictions"]:
        e = by_name.get(p["horse_name"])
        if not e or not e["post"] or not e["win_odds"]:
            continue
        horses.append(e)
        ranked_pairs.append((p["predicted_position"], e["post"]))
    ranked = [post for _, post in sorted(ranked_pairs)]

    level = (pred.get("upset") or {}).get("level", "mid")
    post_to_name = {v["post"]: k for k, v in by_name.items()}

    print(f"\n=== {pred['racecourse_name']} {pred['race_name']} / 予算{BUDGET}円 ===")
    up = pred.get("upset") or {}
    print(f"荒れ度: {up.get('level')} (波乱{round((up.get('expected_upset_rate') or 0)*100)}%) "
          f"→ 狙い自動切替")

    def show(title, res):
        print(f"\n--- {title} (配分{res['total_allocated']}円 / mode={res['alloc_mode']}) ---")
        for s in res["suggestions"]:
            mark = "★おすすめ " if s["recommended"] else "         "
            stake = (f"{s['stake_min']}円" if s["stake_min"] == s["stake_max"]
                     else f"{s['stake_min']}〜{s['stake_max']}円")
            gami = "ガミ無" if s["gami_free"] else "ガミ有"
            drop = f" / ガミ除外{s['dropped_points']}点" if s["dropped_points"] else ""
            print(f"{mark}【{BET_JA.get(s['bet_type'], s['bet_type'])}】{s['rationale']}")
            print(f"          {s['points']}点 (1点{stake}) = 計{s['cost']}円 [{gami}]{drop}"
                  f" / 的中率 {s['hit_rate']*100:.1f}%"
                  f" / 払戻 {s['payout_min']:,}〜{s['payout_max']:,}円"
                  + ("(推定)" if s["odds_estimated"] else ""))
            if s["axis"]:
                names = "・".join(post_to_name.get(h, str(h)) for h in (s["axis"] or [])[:1])
                print(f"          軸: {names} / 相手: "
                      + "・".join(post_to_name.get(h, str(h)) for h in s["horses"][:6]))

    show("おまかせ × ガミ防止(既定)", suggest(BUDGET, horses, ranked, level))
    show("おまかせ × 均等買い", suggest(BUDGET, horses, ranked, level, alloc_mode="flat"))
    show("券種手動: 三連複+三連単+ワイド(予算指定)",
         suggest(BUDGET, horses, ranked, level,
                 bet_types=["trio", "trifecta", "wide"],
                 type_budgets={"trio": 3000, "trifecta": 2000, "wide": 1000}))


if __name__ == "__main__":
    main()
