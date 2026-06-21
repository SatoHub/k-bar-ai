"""Unit tests for the budget bet-suggestion engine (pure functions, no DB)."""

from app.services.bet_suggestion import (
    ordered_triple_probs,
    p_fukusho,
    p_tansho,
    p_umatan,
    suggest,
    win_probs,
)

# 8-horse synthetic field: clear favorite first
HORSES = [
    {"post": 1, "win_odds": 2.0, "win_favorite": 1},
    {"post": 2, "win_odds": 4.0, "win_favorite": 2},
    {"post": 3, "win_odds": 6.0, "win_favorite": 3},
    {"post": 4, "win_odds": 9.0, "win_favorite": 4},
    {"post": 5, "win_odds": 15.0, "win_favorite": 5},
    {"post": 6, "win_odds": 25.0, "win_favorite": 6},
    {"post": 7, "win_odds": 40.0, "win_favorite": 7},
    {"post": 8, "win_odds": 80.0, "win_favorite": 8},
]
RANKED = [1, 2, 3, 4, 5, 6, 7, 8]  # model agrees with market here


def test_win_probs_normalized():
    wp = win_probs(HORSES)
    assert abs(sum(wp.values()) - 1.0) < 1e-9
    assert wp[1] > wp[8]  # favorite has higher prob


def test_triple_probs_and_fukusho_monotonic():
    triples = ordered_triple_probs(win_probs(HORSES))
    # total probability over all ordered triples ~ 1
    assert abs(sum(triples.values()) - 1.0) < 1e-6
    # favorite is likelier to place than the longshot
    assert p_fukusho(triples, 1) > p_fukusho(triples, 8)
    # any place prob is a valid probability
    assert 0 < p_fukusho(triples, 1) < 1


def test_stance_switches_with_upset_level():
    # flatモードで券種構成を確認(gami_avoidは短オッズ券種を除外するため)
    low = suggest(3000, HORSES, RANKED, "low", alloc_mode="flat")
    high = suggest(3000, HORSES, RANKED, "high", alloc_mode="flat")
    low_types = {s["bet_type"] for s in low["suggestions"]}
    high_types = {s["bet_type"] for s in high["suggestions"]}
    # 堅い → 複勝/ワイド中心、荒れ → 三連複/三連単中心
    assert "fukusho" in low_types
    assert "trifecta" in high_types
    assert low_types != high_types


def test_budget_not_exceeded():
    for level in ("low", "mid", "high"):
        for mode in ("gami_avoid", "odds_weighted", "flat"):
            res = suggest(3000, HORSES, RANKED, level, alloc_mode=mode)
            assert res["total_allocated"] <= 3000
            if res["suggestions"]:
                assert sum(1 for s in res["suggestions"] if s["recommended"]) == 1


def test_flat_mode_uses_budget_fully():
    res = suggest(3000, HORSES, RANKED, "high", alloc_mode="flat")
    assert res["total_allocated"] >= 3000 - 100  # 端数(<100円)のみ許容


def test_gami_avoid_is_gami_free():
    # ガミ防止モードでは、どの提案も「当たれば投資以上」(gami_free) になる
    for level in ("low", "mid", "high"):
        res = suggest(6000, HORSES, RANKED, level, alloc_mode="gami_avoid")
        for s in res["suggestions"]:
            assert s["gami_free"], (level, s["bet_type"])


def test_manual_bet_types_and_budgets():
    res = suggest(
        6000, HORSES, RANKED, "high",
        bet_types=["trio", "trifecta", "wide"],
        type_budgets={"trio": 3000, "trifecta": 2000, "wide": 1000},
    )
    types = {s["bet_type"] for s in res["suggestions"]}
    assert types <= {"trio", "trifecta", "wide"}
    # 各券種は指定予算以内
    for s in res["suggestions"]:
        assert s["cost"] <= {"trio": 3000, "trifecta": 2000, "wide": 1000}[s["bet_type"]]


def test_tansho_umatan_probs_and_selection():
    triples = ordered_triple_probs(win_probs(HORSES))
    # 単勝(1着)確率 < 複勝(3着内)確率
    assert p_tansho(triples, 1) < p_fukusho(triples, 1)
    # 馬単(1→2)は単勝(1着)以下
    assert p_umatan(triples, 1, 2) <= p_tansho(triples, 1)
    # 全7券種を手動指定して提案できる
    res = suggest(6000, HORSES, RANKED, "mid",
                  bet_types=["tansho", "fukusho", "umaren", "wide", "umatan", "trio", "trifecta"])
    assert res["total_allocated"] <= 6000
    assert len(res["suggestions"]) >= 4


def test_low_budget_drops_unaffordable_bets():
    res = suggest(500, HORSES, RANKED, "low")
    assert res["total_allocated"] <= 500
    assert len(res["suggestions"]) >= 1
