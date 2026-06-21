"use client";

import React, { useMemo, useState } from "react";
import {
  fetchBetSuggestion,
  type BetSuggestionItem,
  type BetSuggestionResponse,
  type RaceEntry,
} from "@/lib/api";
import { wakuColor } from "./ComboBadges";

const BET_JA: Record<string, string> = {
  tansho: "単勝",
  fukusho: "複勝",
  umaren: "馬連",
  wide: "ワイド",
  umatan: "馬単",
  trio: "三連複",
  trifecta: "三連単",
};

const METHOD_JA: Record<string, string> = {
  single: "単一",
  box: "ボックス",
  formation: "フォーメーション",
  nagashi: "流し",
  nagashi_multi: "軸マルチ",
};

const ALLOC_MODES: { key: string; label: string }[] = [
  { key: "gami_avoid", label: "ガミ防止" },
  { key: "odds_weighted", label: "オッズ傾斜" },
  { key: "flat", label: "均等" },
];

// 表示順(すべての券種)
const ALL_BET_TYPES = ["tansho", "fukusho", "umaren", "wide", "umatan", "trio", "trifecta"];

const LEVEL_JA: Record<string, string> = { low: "低", mid: "中", high: "高" };
const QUICK_BUDGETS = [1000, 3000, 5000, 10000];

type Props = { raceId: string; entries: RaceEntry[] };

export default function BudgetSuggestionPanel({ raceId, entries }: Props) {
  const [budgetStr, setBudgetStr] = useState("3000");
  const [allocMode, setAllocMode] = useState("gami_avoid");
  const [betTypes, setBetTypes] = useState<string[]>(["trio", "wide"]);
  const [result, setResult] = useState<BetSuggestionResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const budget = parseInt(budgetStr.replace(/[^0-9]/g, ""), 10) || 0;
  const budgetInvalid = budget < 100;
  const noBetTypes = betTypes.length === 0;
  const canSubmit = !budgetInvalid && !noBetTypes && !loading;

  // 馬番 -> 枠番
  const bracketByPost = useMemo(() => {
    const m: Record<number, number | null> = {};
    for (const e of entries) {
      if (e.post_position != null) m[e.post_position] = e.bracket_number;
    }
    return m;
  }, [entries]);

  async function run() {
    if (!canSubmit) return;
    setLoading(true);
    setError(null);
    try {
      const res = await fetchBetSuggestion(raceId, {
        budget,
        alloc_mode: allocMode,
        bet_types: betTypes,
      });
      setResult(res);
    } catch (e) {
      setError(e instanceof Error ? e.message : "提案の取得に失敗しました");
    } finally {
      setLoading(false);
    }
  }

  function toggleBet(t: string) {
    setBetTypes((prev) =>
      prev.includes(t) ? prev.filter((x) => x !== t) : [...prev, t],
    );
  }

  return (
    <div className="glass-card overflow-hidden">
      <div
        className="flex items-center gap-2 px-4 py-3"
        style={{ borderBottom: "1px solid var(--border)" }}
      >
        <div className="w-1 self-stretch rounded-full" style={{ backgroundColor: "var(--accent)" }} />
        <h2 className="text-base font-semibold" style={{ color: "var(--text-primary)" }}>
          予算から買い目を自動提案
        </h2>
      </div>

      <div className="p-4 space-y-3">
        {/* 予算入力 */}
        <div>
          <div className="flex items-center gap-2 flex-wrap">
            <label className="text-sm" style={{ color: "var(--text-secondary)" }}>
              予算
            </label>
            <input
              type="text"
              inputMode="numeric"
              value={budgetStr}
              onChange={(e) => setBudgetStr(e.target.value)}
              aria-invalid={budgetInvalid}
              className="w-28 rounded-md px-2 py-1 text-sm outline-none"
              style={{
                backgroundColor: "var(--bg-secondary)",
                border: `1px solid ${budgetInvalid ? "#dc2626" : "var(--border)"}`,
                boxShadow: budgetInvalid ? "0 0 0 2px rgba(220,38,38,0.2)" : "none",
                color: "var(--text-primary)",
              }}
            />
            <span className="text-sm" style={{ color: "var(--text-secondary)" }}>
              円
            </span>
            {QUICK_BUDGETS.map((b) => (
              <button
                key={b}
                onClick={() => setBudgetStr(String(b))}
                className="rounded-full px-2.5 py-0.5 text-xs"
                style={{
                  backgroundColor: budget === b ? "var(--accent)" : "var(--bg-secondary)",
                  color: budget === b ? "#fff" : "var(--text-secondary)",
                  border: "1px solid var(--border)",
                }}
              >
                {b.toLocaleString()}
              </button>
            ))}
          </div>
          {budgetInvalid && (
            <p className="text-xs mt-1" style={{ color: "#dc2626" }}>
              100円以上を入力してください
            </p>
          )}
        </div>

        {/* 配分モード */}
        <div className="flex items-center gap-2 flex-wrap">
          <span className="text-sm" style={{ color: "var(--text-secondary)" }}>
            配分
          </span>
          {ALLOC_MODES.map((m) => (
            <button
              key={m.key}
              onClick={() => setAllocMode(m.key)}
              className="rounded-full px-3 py-0.5 text-xs font-medium"
              style={{
                backgroundColor: allocMode === m.key ? "var(--accent)" : "var(--bg-secondary)",
                color: allocMode === m.key ? "#fff" : "var(--text-secondary)",
                border: "1px solid var(--border)",
              }}
            >
              {m.label}
            </button>
          ))}
        </div>

        {/* 券種選択(すべて表示・複数選択) */}
        <div>
          <div className="flex items-center gap-2 flex-wrap">
            <span className="text-sm" style={{ color: "var(--text-secondary)" }}>
              券種
            </span>
            {ALL_BET_TYPES.map((t) => {
              const on = betTypes.includes(t);
              return (
                <button
                  key={t}
                  onClick={() => toggleBet(t)}
                  className="rounded-full px-2.5 py-0.5 text-xs font-medium"
                  style={{
                    backgroundColor: on ? "var(--accent)" : "var(--bg-secondary)",
                    color: on ? "#fff" : "var(--text-secondary)",
                    border: "1px solid var(--border)",
                  }}
                >
                  {BET_JA[t]}
                </button>
              );
            })}
          </div>
          {noBetTypes && (
            <p className="text-xs mt-1" style={{ color: "#dc2626" }}>
              券種を1つ以上選択してください
            </p>
          )}
          {!noBetTypes && (
            <p className="text-[11px] mt-1" style={{ color: "var(--text-secondary)" }}>
              選択した{betTypes.length}券種で予算を配分します
            </p>
          )}
        </div>

        <button
          onClick={run}
          disabled={!canSubmit}
          className="rounded-md px-4 py-2 text-sm font-semibold w-full sm:w-auto"
          style={{ backgroundColor: "var(--accent)", color: "#fff", opacity: canSubmit ? 1 : 0.5 }}
        >
          {loading ? "オッズ取得中…" : "買い目を提案"}
        </button>

        {error && (
          <p className="text-sm" style={{ color: "#dc2626" }}>
            {error}
          </p>
        )}

        {result && <Results result={result} bracketByPost={bracketByPost} />}
      </div>
    </div>
  );
}

function WakuBadge({ post, bracket }: { post: number; bracket: number | null }) {
  const c = wakuColor(bracket);
  return (
    <span
      className="inline-flex h-5 min-w-[1.25rem] items-center justify-center rounded px-1 text-[11px] font-bold tabular-nums"
      style={{ backgroundColor: c.bg, color: c.fg, border: "1px solid rgba(0,0,0,0.25)" }}
    >
      {post}
    </span>
  );
}

function HorseList({
  posts,
  bracketByPost,
}: {
  posts: number[];
  bracketByPost: Record<number, number | null>;
}) {
  return (
    <span className="inline-flex flex-wrap items-center gap-0.5">
      {posts.map((p) => (
        <WakuBadge key={p} post={p} bracket={bracketByPost[p] ?? null} />
      ))}
    </span>
  );
}

function Results({
  result,
  bracketByPost,
}: {
  result: BetSuggestionResponse;
  bracketByPost: Record<number, number | null>;
}) {
  if (!result.suggestions.length) {
    return (
      <p className="text-sm" style={{ color: "var(--text-secondary)" }}>
        {result.message ?? "提案できる買い目がありませんでした"}
      </p>
    );
  }
  return (
    <div className="space-y-2 pt-1">
      <div className="flex items-center gap-2 flex-wrap text-xs" style={{ color: "var(--text-secondary)" }}>
        <span>
          荒れ度{" "}
          <b style={{ color: "var(--text-primary)" }}>
            {LEVEL_JA[result.upset_level] ?? result.upset_level}
          </b>
        </span>
        <span>・配分 {result.total_allocated.toLocaleString()}/{result.budget.toLocaleString()}円</span>
        <span>・{result.odds_live ? "ライブオッズ" : "オッズ推定"}</span>
      </div>
      {result.suggestions.map((s, i) => (
        <SuggestionCard key={i} s={s} bracketByPost={bracketByPost} />
      ))}
      <p className="text-[11px] leading-snug pt-1" style={{ color: "var(--text-secondary)" }}>
        ※「ガミ無」=当たれば必ず投資額以上の払戻。控除率20%があり利益は保証されません。
      </p>
    </div>
  );
}

function SuggestionCard({
  s,
  bracketByPost,
}: {
  s: BetSuggestionItem;
  bracketByPost: Record<number, number | null>;
}) {
  const stake =
    s.stake_min === s.stake_max ? `${s.stake_min}円` : `${s.stake_min}〜${s.stake_max}円`;
  return (
    <div
      className="rounded-lg p-3"
      style={{
        backgroundColor: s.recommended ? "var(--accent-muted)" : "var(--bg-secondary)",
        border: `1px solid ${s.recommended ? "var(--accent)" : "var(--border)"}`,
      }}
    >
      <div className="flex items-center gap-2 flex-wrap">
        {s.recommended && (
          <span
            className="rounded-full px-2 py-0.5 text-[11px] font-bold"
            style={{ backgroundColor: "var(--accent)", color: "#fff" }}
          >
            ★おすすめ
          </span>
        )}
        <span className="text-sm font-bold" style={{ color: "var(--text-primary)" }}>
          {BET_JA[s.bet_type] ?? s.bet_type}
        </span>
        <span className="text-xs" style={{ color: "var(--text-secondary)" }}>
          {METHOD_JA[s.method] ?? s.method}
        </span>
        <span
          className="rounded px-1.5 py-0.5 text-[11px] font-medium"
          style={{
            backgroundColor: s.gami_free ? "#f0fdf4" : "#fef2f2",
            color: s.gami_free ? "#15803d" : "#b91c1c",
          }}
        >
          {s.gami_free ? "ガミ無" : "ガミ有"}
        </span>
      </div>

      <p className="text-xs mt-1" style={{ color: "var(--text-secondary)" }}>
        {s.rationale}
      </p>

      <div className="text-sm mt-1.5" style={{ color: "var(--text-primary)" }}>
        {s.points}点 (1点{stake}) = <b>計{s.cost.toLocaleString()}円</b>
        {s.dropped_points > 0 && (
          <span className="text-xs" style={{ color: "var(--text-secondary)" }}>
            {" "}/ ガミ除外{s.dropped_points}点
          </span>
        )}
      </div>

      <div className="text-xs mt-0.5" style={{ color: "var(--text-secondary)" }}>
        想定的中率 {(s.hit_rate * 100).toFixed(1)}% / 的中時払戻 {s.payout_min.toLocaleString()}〜
        {s.payout_max.toLocaleString()}円{s.odds_estimated ? "(推定)" : ""}
      </div>

      {s.axis && s.axis.length > 0 && (
        <div className="flex items-center gap-1 flex-wrap text-xs mt-1.5" style={{ color: "var(--text-secondary)" }}>
          <span>軸</span>
          <HorseList posts={s.axis} bracketByPost={bracketByPost} />
          <span>相手</span>
          <HorseList posts={s.horses.slice(0, 6)} bracketByPost={bracketByPost} />
        </div>
      )}
      {(!s.axis || s.axis.length === 0) && s.horses.length > 0 && (
        <div className="flex items-center gap-1 flex-wrap text-xs mt-1.5" style={{ color: "var(--text-secondary)" }}>
          <span>馬</span>
          <HorseList posts={s.horses} bracketByPost={bracketByPost} />
        </div>
      )}
    </div>
  );
}
