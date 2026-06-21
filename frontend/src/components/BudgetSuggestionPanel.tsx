"use client";

import React, { useState } from "react";
import {
  fetchBetSuggestion,
  type BetSuggestionItem,
  type BetSuggestionResponse,
} from "@/lib/api";

const BET_JA: Record<string, string> = {
  fukusho: "複勝",
  wide: "ワイド",
  umaren: "馬連",
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

const ALL_BET_TYPES = ["fukusho", "wide", "umaren", "trio", "trifecta"];

const LEVEL_JA: Record<string, string> = { low: "低", mid: "中", high: "高" };

type Props = { raceId: string };

export default function BudgetSuggestionPanel({ raceId }: Props) {
  const [budget, setBudget] = useState(3000);
  const [allocMode, setAllocMode] = useState("gami_avoid");
  const [manual, setManual] = useState(false);
  const [betTypes, setBetTypes] = useState<string[]>(["trio", "wide"]);
  const [result, setResult] = useState<BetSuggestionResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function run() {
    setLoading(true);
    setError(null);
    try {
      const res = await fetchBetSuggestion(raceId, {
        budget,
        alloc_mode: allocMode,
        bet_types: manual ? betTypes : null,
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

  const names = result?.names ?? {};
  const horseLabel = (h: number) => names[String(h)] ?? `${h}番`;

  return (
    <div className="glass-card overflow-hidden">
      <div
        className="flex items-center gap-2 px-4 py-3"
        style={{ borderBottom: "1px solid var(--border)" }}
      >
        <div
          className="w-1 self-stretch rounded-full"
          style={{ backgroundColor: "var(--accent)" }}
        />
        <h2 className="text-base font-semibold" style={{ color: "var(--text-primary)" }}>
          予算から買い目を自動提案
        </h2>
      </div>

      <div className="p-4 space-y-3">
        {/* 予算入力 */}
        <div className="flex items-center gap-2 flex-wrap">
          <label className="text-sm" style={{ color: "var(--text-secondary)" }}>
            予算
          </label>
          <input
            type="number"
            min={100}
            step={100}
            value={budget}
            onChange={(e) => setBudget(Math.max(100, Number(e.target.value)))}
            className="w-28 rounded-md px-2 py-1 text-sm"
            style={{
              backgroundColor: "var(--bg-secondary)",
              border: "1px solid var(--border)",
              color: "var(--text-primary)",
            }}
          />
          <span className="text-sm" style={{ color: "var(--text-secondary)" }}>
            円
          </span>
          {[1000, 3000, 5000, 10000].map((b) => (
            <button
              key={b}
              onClick={() => setBudget(b)}
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

        {/* 券種選択 */}
        <div className="flex items-center gap-2 flex-wrap">
          <button
            onClick={() => setManual((v) => !v)}
            className="rounded-full px-3 py-0.5 text-xs font-medium"
            style={{
              backgroundColor: !manual ? "var(--accent)" : "var(--bg-secondary)",
              color: !manual ? "#fff" : "var(--text-secondary)",
              border: "1px solid var(--border)",
            }}
          >
            {manual ? "券種: 手動" : "券種: おまかせ"}
          </button>
          {manual &&
            ALL_BET_TYPES.map((t) => (
              <button
                key={t}
                onClick={() => toggleBet(t)}
                className="rounded-full px-2.5 py-0.5 text-xs"
                style={{
                  backgroundColor: betTypes.includes(t)
                    ? "var(--accent-muted)"
                    : "var(--bg-secondary)",
                  color: betTypes.includes(t) ? "var(--accent)" : "var(--text-secondary)",
                  border: "1px solid var(--border)",
                }}
              >
                {BET_JA[t]}
              </button>
            ))}
        </div>

        <button
          onClick={run}
          disabled={loading}
          className="rounded-md px-4 py-2 text-sm font-semibold w-full sm:w-auto"
          style={{ backgroundColor: "var(--accent)", color: "#fff", opacity: loading ? 0.6 : 1 }}
        >
          {loading ? "オッズ取得中…" : "買い目を提案"}
        </button>

        {error && (
          <p className="text-sm" style={{ color: "#dc2626" }}>
            {error}
          </p>
        )}

        {result && <Results result={result} horseLabel={horseLabel} />}
      </div>
    </div>
  );
}

function Results({
  result,
  horseLabel,
}: {
  result: BetSuggestionResponse;
  horseLabel: (h: number) => string;
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
          荒れ度 <b style={{ color: "var(--text-primary)" }}>{LEVEL_JA[result.upset_level] ?? result.upset_level}</b>
        </span>
        <span>・配分 {result.total_allocated.toLocaleString()}/{result.budget.toLocaleString()}円</span>
        <span>・{result.odds_live ? "ライブオッズ" : "オッズ推定"}</span>
      </div>
      {result.suggestions.map((s, i) => (
        <SuggestionCard key={i} s={s} horseLabel={horseLabel} />
      ))}
      <p className="text-[11px] leading-snug pt-1" style={{ color: "var(--text-secondary)" }}>
        ※「ガミ無」=当たれば必ず投資額以上の払戻。控除率20%があり利益は保証されません。
      </p>
    </div>
  );
}

function SuggestionCard({
  s,
  horseLabel,
}: {
  s: BetSuggestionItem;
  horseLabel: (h: number) => string;
}) {
  const stake =
    s.stake_min === s.stake_max
      ? `${s.stake_min}円`
      : `${s.stake_min}〜${s.stake_max}円`;
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
        <div className="text-xs mt-1" style={{ color: "var(--text-secondary)" }}>
          軸: {s.axis.map(horseLabel).join("・")} / 相手:{" "}
          {s.horses.slice(0, 6).map(horseLabel).join("・")}
        </div>
      )}
      {(!s.axis || s.axis.length === 0) && s.horses.length > 0 && (
        <div className="text-xs mt-1" style={{ color: "var(--text-secondary)" }}>
          馬: {s.horses.map(horseLabel).join("・")}
        </div>
      )}
    </div>
  );
}
