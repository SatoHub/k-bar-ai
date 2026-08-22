"""
予算指定の買い目自動提案エンジン (おまかせ＝荒れ度連動)。

入力した予算と、AI予想ランク・各馬の単勝オッズ・荒れ度スコアから、
券種ごとの推奨買い目・点数・配分・想定的中率・想定払戻を返す。

方針 (この機能の正直な前提):
  控除率20%があり、平均では市場(オッズ)を上回れない。よって本エンジンは
  「予算と狙いに合った理にかなった買い目」を組むものであり、利益を保証しない。
  確率は市場オッズ(の控除前確率)を基準に Harville モデルで算出するため、
  想定的中率は現実的な値になる。狙い(stance)は荒れ度で自動切替する:

    荒れ度 低  → 的中重視 (複勝・ワイド・少点数)
    荒れ度 中  → バランス (ワイド + 三連複 軸1頭流し)
    荒れ度 高  → 配当重視 (三連複/三連単で人気薄を絡めた広め)

純粋関数。DB/ネットワークに依存しない (呼び出し側がオッズ・予想を渡す)。
"""

from __future__ import annotations

from itertools import combinations, permutations

TAKEOUT = 0.20  # 控除率 (払戻推定の控除前→控除後変換に使用)
UNIT = 100  # 1点あたり最小賭け金(円)


# ---------------------------------------------------------------------------
# 確率エンジン (市場オッズ → Harville)
# ---------------------------------------------------------------------------
def win_probs(horses: list[dict]) -> dict[int, float]:
    """単勝オッズの逆数を正規化(控除前)した勝率を返す。post -> prob。"""
    inv = {h["post"]: 1.0 / h["win_odds"] for h in horses if h.get("win_odds")}
    s = sum(inv.values())
    return {p: v / s for p, v in inv.items()} if s > 0 else {}


def ordered_triple_probs(wp: dict[int, float]) -> dict[tuple[int, int, int], float]:
    """Harville モデルで全順序付き上位3着 (a,b,c) の確率を算出。"""
    posts = list(wp)
    res: dict[tuple[int, int, int], float] = {}
    for a, b, c in permutations(posts, 3):
        da = 1.0 - wp[a]
        dc = 1.0 - wp[a] - wp[b]
        if da <= 0 or dc <= 0:
            continue
        res[(a, b, c)] = wp[a] * (wp[b] / da) * (wp[c] / dc)
    return res


def _p_cover(triples: dict, predicate) -> float:
    """predicate(a,b,c)->bool を満たす順序付き3着の確率合計。"""
    return sum(p for (a, b, c), p in triples.items() if predicate(a, b, c))


# 券種ごとの「この買い目が当たる確率」
def p_fukusho(triples, x):  # 複勝: x が3着以内
    return _p_cover(triples, lambda a, b, c: x in (a, b, c))


def p_wide(triples, x, y):  # ワイド: x,y 両方3着以内
    return _p_cover(triples, lambda a, b, c: x in (a, b, c) and y in (a, b, c))


def p_umaren(triples, x, y):  # 馬連: x,y が1,2着(順不同)
    s = {x, y}
    return _p_cover(triples, lambda a, b, c: {a, b} == s)


def p_trio(triples, combo):  # 三連複: 3頭が1-3着(順不同)
    s = set(combo)
    return _p_cover(triples, lambda a, b, c: {a, b, c} == s)


def p_trifecta(triples, a, b, c):  # 三連単
    return triples.get((a, b, c), 0.0)


def p_tansho(triples, x):  # 単勝: x が1着
    return _p_cover(triples, lambda a, b, c: a == x)


def p_umatan(triples, x, y):  # 馬単: x→y が1,2着
    return _p_cover(triples, lambda a, b, c: a == x and b == y)


# ---------------------------------------------------------------------------
# 買い目候補の生成 (荒れ度連動)
# ---------------------------------------------------------------------------
def _fair_odds(prob: float) -> float:
    """確率から控除後フェアオッズを推定 (ライブのcomboオッズが無い場合の目安)。"""
    if prob <= 0:
        return 0.0
    return (1.0 / prob) * (1.0 - TAKEOUT)


def _build_menu(ranked: list[int], horses_by_post: dict, level: str) -> list[dict]:
    """荒れ度levelに応じた買い目メニュー(bet種・買い目・狙い・配分重み)を返す。

    ranked: AI予想の良い順の馬番リスト。
    """
    r = ranked

    def odds(p):
        return horses_by_post[p]["win_odds"]

    # 人気薄(穴)候補 = 予想上位8頭のうちオッズが高い順
    ana_pool = sorted(r[: min(8, len(r))], key=lambda p: -odds(p))

    menu: list[dict] = []
    if level == "low":  # 堅い → 的中重視
        menu.append(
            {
                "bet": "fukusho",
                "method": "single",
                "horses": [r[0]],
                "rationale": "本命の複勝で手堅く",
                "weight": 3,
            }
        )
        if len(r) >= 3:
            menu.append(
                {
                    "bet": "wide",
                    "method": "box",
                    "horses": r[:3],
                    "rationale": "上位3頭のワイドBOX",
                    "weight": 4,
                }
            )
        if len(r) >= 5:
            menu.append(
                {
                    "bet": "trio",
                    "method": "nagashi",
                    "axis": [r[0]],
                    "partners": r[1:5],
                    "rationale": "本命軸の三連複流し",
                    "weight": 3,
                }
            )
    elif level == "high":  # 荒れ → 配当重視
        # 三連複: 本命2頭 + 穴3頭の広めBOX/フォーメーション
        core = r[:2]
        partners = list(dict.fromkeys(core + r[2:5] + ana_pool[:2]))
        menu.append(
            {
                "bet": "trio",
                "method": "nagashi",
                "axis": [r[0]],
                "partners": [p for p in partners if p != r[0]][:6],
                "rationale": "本命軸→人気薄まで広げた三連複(高配当狙い)",
                "weight": 4,
            }
        )
        menu.append(
            {
                "bet": "trifecta",
                "method": "nagashi_multi",
                "axis": [r[0]],
                "partners": [p for p in partners if p != r[0]][:5],
                "rationale": "本命1頭マルチの三連単(一発)",
                "weight": 2,
            }
        )
        if len(ana_pool) >= 1:
            menu.append(
                {
                    "bet": "wide",
                    "method": "formation",
                    "sets": [[r[0]], ana_pool[:2]],
                    "rationale": "本命×人気薄のワイドで押さえ",
                    "weight": 2,
                }
            )
    else:  # mid → バランス
        if len(r) >= 3:
            menu.append(
                {
                    "bet": "wide",
                    "method": "box",
                    "horses": r[:3],
                    "rationale": "上位3頭のワイドBOX",
                    "weight": 3,
                }
            )
        if len(r) >= 6:
            menu.append(
                {
                    "bet": "trio",
                    "method": "nagashi",
                    "axis": [r[0]],
                    "partners": r[1:6],
                    "rationale": "本命軸の三連複流し",
                    "weight": 4,
                }
            )
        if len(r) >= 4:
            menu.append(
                {
                    "bet": "umaren",
                    "method": "box",
                    "horses": r[:3],
                    "rationale": "上位3頭の馬連BOX",
                    "weight": 2,
                }
            )
    return menu


def _item_for_type(bet: str, ranked: list[int], level: str) -> dict | None:
    """券種を手動指定したときの、その券種の標準的な買い目構成。"""
    r = ranked
    if bet == "tansho" and len(r) >= 1:
        return {
            "bet": "tansho",
            "method": "single",
            "horses": [r[0]],
            "rationale": "本命の単勝",
            "weight": 1,
        }
    if bet == "umatan" and len(r) >= 4:
        return {
            "bet": "umatan",
            "method": "formation",
            "sets": [[r[0]], r[1:4]],
            "rationale": "本命1着→上位への馬単",
            "weight": 1,
        }
    if bet == "fukusho" and len(r) >= 1:
        return {
            "bet": "fukusho",
            "method": "single",
            "horses": [r[0]],
            "rationale": "本命の複勝",
            "weight": 1,
        }
    if bet == "wide" and len(r) >= 3:
        return {
            "bet": "wide",
            "method": "box",
            "horses": r[:3],
            "rationale": "上位3頭のワイドBOX",
            "weight": 1,
        }
    if bet == "umaren" and len(r) >= 3:
        return {
            "bet": "umaren",
            "method": "box",
            "horses": r[:3],
            "rationale": "上位3頭の馬連BOX",
            "weight": 1,
        }
    if bet == "trio" and len(r) >= 4:
        np_ = 4 if level == "low" else 6
        return {
            "bet": "trio",
            "method": "nagashi",
            "axis": [r[0]],
            "partners": r[1 : 1 + np_],
            "rationale": "本命軸の三連複流し",
            "weight": 1,
        }
    if bet == "trifecta" and len(r) >= 4:
        return {
            "bet": "trifecta",
            "method": "nagashi_multi",
            "axis": [r[0]],
            "partners": r[1:6],
            "rationale": "本命1頭マルチの三連単",
            "weight": 1,
        }
    return None


def _combos_for(item: dict) -> list[tuple]:
    """メニュー項目を実際の買い目(馬番タプル)のリストに展開。"""
    if item.get("combos") is not None:  # 買い目を直接指定(ヘッジ等)
        return [tuple(c) for c in item["combos"]]
    bet = item["bet"]
    ordered = bet in ("trifecta", "umatan")
    if item["method"] == "single":
        return [tuple(item["horses"])]
    if item["method"] == "box":
        k = {"wide": 2, "umaren": 2, "trio": 3, "trifecta": 3}[bet]
        combos = combinations(item["horses"], k)
        if ordered:
            combos = (
                p for h in combinations(item["horses"], k) for p in permutations(h)
            )
        return [tuple(c) for c in combos]
    if item["method"] == "formation":
        s1, s2 = item["sets"]
        pairs = [(a, b) for a in s1 for b in s2 if a != b]
        if not ordered:  # ワイド/馬連等は順不同→重複ペアを除去
            seen, out = set(), []
            for p in pairs:
                key = tuple(sorted(p))
                if key not in seen:
                    seen.add(key)
                    out.append(p)
            return out
        return pairs
    if item["method"] in ("nagashi", "nagashi_multi"):
        axis = item["axis"]
        partners = item["partners"]
        if bet == "trio":  # 軸1頭 + 相手から2頭
            return [
                tuple(sorted((axis[0], *pair))) for pair in combinations(partners, 2)
            ]
        if bet == "trifecta":  # 軸1頭マルチ(全着順) + 相手から2頭
            res = []
            for pair in combinations(partners, 2):
                trio = [axis[0], *pair]
                res.extend(permutations(trio))
            return list(dict.fromkeys(res))
    return []


def _bet_prob(triples, bet, combo) -> float:
    if bet == "tansho":
        return p_tansho(triples, combo[0])
    if bet == "fukusho":
        return p_fukusho(triples, combo[0])
    if bet == "wide":
        return p_wide(triples, combo[0], combo[1])
    if bet == "umaren":
        return p_umaren(triples, combo[0], combo[1])
    if bet == "umatan":
        return p_umatan(triples, combo[0], combo[1])
    if bet == "trio":
        return p_trio(triples, combo)
    if bet == "trifecta":
        return p_trifecta(triples, *combo)
    return 0.0


# ---------------------------------------------------------------------------
# 配分アルゴリズム (モード別)
# ---------------------------------------------------------------------------
def _round_unit(x: float) -> int:
    return max(0, int(round(x / UNIT)) * UNIT)


def _trim_to_target(stakes: list[int], fund: list[int], target: int) -> None:
    """sum(stakes) <= target になるよう、最大stakeからUNIT単位で削る(in-place)。
    fund の点数 <= target//UNIT が前提(全てUNITでも超えない)。"""
    while sum(stakes) > target:
        big = [i for i in fund if stakes[i] > UNIT]
        if not big:
            break
        stakes[max(big, key=lambda i: stakes[i])] -= UNIT


def _alloc_flat(rows: list[dict], target: int) -> tuple[list[int], list[int]]:
    """均等買い。買える点数を超える場合は的中確率の低い買い目を除外。"""
    n = len(rows)
    if n == 0 or target < UNIT:
        return [0] * n, []
    k = min(n, target // UNIT)  # 資金で買える点数上限
    fund = sorted(range(n), key=lambda i: -rows[i]["prob"])[:k]
    dropped = [i for i in range(n) if i not in set(fund)]
    base = max(UNIT, (target // k // UNIT) * UNIT)
    stakes = [0] * n
    for i in fund:
        stakes[i] = base
    _trim_to_target(stakes, fund, target)
    remaining = target - sum(stakes)
    order = sorted(fund, key=lambda i: -rows[i]["prob"])
    j = 0
    while remaining >= UNIT and order:
        stakes[order[j % len(order)]] += UNIT
        remaining -= UNIT
        j += 1
    return stakes, dropped


def _alloc_weighted(rows: list[dict], target: int) -> tuple[list[int], list[int]]:
    """オッズ傾斜配分。stake ∝ 1/odds(低オッズ厚め)→払戻を平準化。"""
    n = len(rows)
    if n == 0 or target < UNIT:
        return [0] * n, []
    k = min(n, target // UNIT)
    fund = sorted(range(n), key=lambda i: rows[i]["odds"])[:k]  # 低オッズ優先で資金化
    dropped = [i for i in range(n) if i not in set(fund)]
    w = {i: 1.0 / rows[i]["odds"] for i in fund}
    sw = sum(w.values()) or 1
    stakes = [0] * n
    for i in fund:
        stakes[i] = max(UNIT, _round_unit(target * w[i] / sw))
    _trim_to_target(stakes, fund, target)
    return stakes, dropped


def _alloc_gami_avoid(rows: list[dict], target: int) -> tuple[list[int], list[int]]:
    """ガミ防止配分。当たっても投資割れする低オッズ買い目を除外し、
    残りをオッズ傾斜配分(等払戻)にして「どれが当たっても払戻>=投資」を保証する。

    原理: 残す集合で Σ(1/odds) <= 1 なら stake ∝ 1/odds の等払戻配分で
    払戻 R = 投資/Σ(1/odds) >= 投資 となりガミが出ない。最後に各買い目の
    払戻>=投資を実検証し、崩れていれば低オッズを更に除外して再配分する。
    """
    n = len(rows)
    if n == 0 or target < UNIT:
        return [0] * n, []
    order = sorted(range(n), key=lambda i: rows[i]["odds"])  # 低オッズ順
    maxk = target // UNIT

    def S(ks):
        return sum(1.0 / rows[i]["odds"] for i in ks)

    kept = list(order)
    # 点数上限 & Σ(1/odds)<=0.98(丸め余裕) になるまで低オッズを除外
    while kept and (len(kept) > maxk or S(kept) > 0.98):
        kept.pop(0)

    def allocate(ks):
        sw = sum(1.0 / rows[i]["odds"] for i in ks) or 1
        st = [0] * n
        for i in ks:
            st[i] = max(UNIT, _round_unit(target / rows[i]["odds"] / sw))
        _trim_to_target(st, ks, target)
        return st

    stakes = [0] * n
    while kept:
        stakes = allocate(kept)
        cost = sum(stakes)
        if all(stakes[i] * rows[i]["odds"] >= cost for i in kept if stakes[i] > 0):
            break  # ガミ無を確認
        kept.pop(0)  # 低オッズを更に除外して再挑戦
    dropped = [i for i in order if stakes[i] == 0]
    return stakes, dropped


_ALLOCATORS = {
    "flat": _alloc_flat,
    "odds_weighted": _alloc_weighted,
    "gami_avoid": _alloc_gami_avoid,
}


# ---------------------------------------------------------------------------
# 公開API
# ---------------------------------------------------------------------------
def suggest(
    budget: int,
    horses: list[dict],
    ranked: list[int],
    upset_level: str,
    odds_lookup: dict | None = None,
    alloc_mode: str = "gami_avoid",
    bet_types: list[str] | None = None,
    type_budgets: dict[str, int] | None = None,
    menu_override: list[dict] | None = None,
) -> dict:
    """買い目提案を生成。

    Args:
        budget: 予算(円)
        horses: [{"post":int, "win_odds":float, "win_favorite":int}, ...]
        ranked: AI予想の良い順の馬番リスト
        upset_level: "low" | "mid" | "high"
        odds_lookup: {bet_type: {combo_key(0埋め連結): odds}}。無ければフェアオッズ推定。
        alloc_mode: "gami_avoid"(既定) | "odds_weighted" | "flat"。
        bet_types: 券種を手動指定(例 ["trio","trifecta","wide"])。Noneなら荒れ度でおまかせ。
        type_budgets: 券種ごとの予算(例 {"trio":3000,"wide":1000})。Noneなら重み配分。
        menu_override: 買い目構成を直接指定(ヘッジ等の独自構成用)。指定時は bet_types/
            おまかせより優先。各item={bet,method,horses|axis+partners|sets,rationale,weight}。
    """
    wp = win_probs(horses)
    triples = ordered_triple_probs(wp)
    by_post = {h["post"]: h for h in horses}
    if menu_override is not None:  # 独自構成(ヘッジ等)
        menu = menu_override
    elif bet_types:  # 券種を手動指定
        menu = [
            m for m in (_item_for_type(b, ranked, upset_level) for b in bet_types) if m
        ]
    else:  # おまかせ(荒れ度で自動選択)
        menu = _build_menu(ranked, by_post, upset_level)

    def lookup_odds(bet, combo):
        if odds_lookup and bet in odds_lookup:
            ordered = bet in ("trifecta", "umatan")
            arranged = combo if ordered else tuple(sorted(combo))
            key = "".join(f"{n:02d}" for n in arranged)
            o = odds_lookup[bet].get(key)
            if o:
                return float(o), False
        return _fair_odds(_bet_prob(triples, bet, combo)), True

    # 各メニュー項目を評価
    items = []
    for m in menu:
        combos = _combos_for(m)
        if not combos:
            continue
        points = len(combos)
        rows = []
        est_used = False
        for c in combos:
            p = _bet_prob(triples, m["bet"], c)
            o, est = lookup_odds(m["bet"], c)
            est_used = est_used or est
            rows.append({"combo": c, "prob": p, "odds": o})
        hit_rate = sum(r["prob"] for r in rows)  # 排他的券種は和=的中率
        items.append(
            {
                **m,
                "points": points,
                "rows": rows,
                "hit_rate": hit_rate,
                "odds_estimated": est_used,
            }
        )

    # 予算配分: モード別アロケータで券種ごとに配分
    allocator = _ALLOCATORS.get(alloc_mode, _alloc_gami_avoid)
    order = sorted(items, key=lambda x: -x["weight"])
    remaining = budget
    suggestions = []
    for k, i in enumerate(order):
        rows = i["rows"]
        if i.get("budget") is not None:  # 項目ごとに予算指定(ヘッジ等)
            tb = min(remaining, int(i["budget"]))
        elif type_budgets is not None:
            tb = min(remaining, int(type_budgets.get(i["bet"], 0)))
        elif k == len(order) - 1:
            tb = remaining  # 最後の券種に残予算を寄せて使い切る
        else:
            rem_w = sum(j["weight"] for j in order[k:]) or 1
            tb = _round_unit(remaining * i["weight"] / rem_w)
        if tb < UNIT:
            continue

        stakes, dropped = allocator(rows, tb)
        cost = sum(stakes)
        if cost < UNIT:
            continue
        remaining -= cost

        kept = [(r, s) for r, s in zip(rows, stakes) if s > 0]
        kept.sort(key=lambda rs: -rs[0]["prob"])  # 的中しやすい順
        payouts = [r["odds"] * s for r, s in kept]
        exp_return = sum(r["prob"] * r["odds"] * s for r, s in kept)
        min_payout = round(min(payouts)) if payouts else 0
        combos_out = [
            {
                "combo": list(r["combo"]),
                "stake": s,
                "odds": round(r["odds"], 1) if r["odds"] else None,
                "payout": round(r["odds"] * s) if r["odds"] else None,
            }
            for r, s in kept
        ]
        suggestions.append(
            {
                "bet_type": i["bet"],
                "method": i["method"],
                "horses": i.get("horses") or i.get("partners") or [],
                "axis": i.get("axis"),
                "combos": combos_out,  # 実際に買う組み合わせ(馬番・掛け金・オッズ)
                "points": len(kept),
                "dropped_points": len(dropped),  # ガミ回避で除外した買い目数
                "stake_min": min((s for _, s in kept), default=0),
                "stake_max": max((s for _, s in kept), default=0),
                "cost": cost,
                "hit_rate": round(sum(r["prob"] for r, _ in kept), 4),
                "ev_ratio": round(exp_return / cost, 3) if cost else 0,
                "payout_min": min_payout,
                "payout_max": round(max(payouts)) if payouts else 0,
                "gami_free": bool(payouts)
                and min_payout >= cost,  # 当たれば必ず投資以上
                "odds_estimated": i["odds_estimated"],
                "rationale": i["rationale"],
                "recommended": False,
            }
        )

    # おすすめ: low/midは的中率最大、highは想定払戻(payout_max)最大
    if suggestions:
        if upset_level == "high":
            best = max(suggestions, key=lambda s: s["payout_max"])
        else:
            best = max(suggestions, key=lambda s: s["hit_rate"])
        best["recommended"] = True

    return {
        "budget": budget,
        "upset_level": upset_level,
        "alloc_mode": alloc_mode,
        "total_allocated": sum(s["cost"] for s in suggestions),
        "suggestions": suggestions,
    }
