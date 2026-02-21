"use client";

import { useMemo } from "react";
import type { PredictionEntry, RaceEntry } from "@/lib/api";

const BET_TYPES = [
  { value: "tansho", label: "単勝", picks: 1, ordered: false, desc: "1着を当てる" },
  { value: "fukusho", label: "複勝", picks: 1, ordered: false, desc: "3着以内を当てる" },
  { value: "umaren", label: "馬連", picks: 2, ordered: false, desc: "1-2着の組合せ" },
  { value: "umatan", label: "馬単", picks: 2, ordered: true, desc: "1-2着を着順通り" },
  { value: "wide", label: "ワイド", picks: 2, ordered: false, desc: "3着以内の2頭" },
  { value: "sanrenpuku", label: "三連複", picks: 3, ordered: false, desc: "1-3着の組合せ" },
  { value: "sanrentan", label: "三連単", picks: 3, ordered: true, desc: "1-3着を着順通り" },
] as const;

const RANK_MARKS = ["◎", "○", "▲", "△", "☆"] as const;

const RANK_COLORS = [
  "#F59E0B", // gold — 本命
  "#3B82F6", // blue — 対抗
  "#EF4444", // red — 単穴
  "#8B5CF6", // purple — 連穴
  "#6B7280", // gray
];

type EnrichedPrediction = PredictionEntry & {
  post_position: number | null;
  bracket_number: number | null;
};

type Props = {
  predictions: PredictionEntry[];
  entries: RaceEntry[];
  onSelectBet?: (betType: string, horseIds: string[]) => void;
};

function confidenceBadge(confidence: string | null) {
  const c = confidence ?? "medium";
  const styles: Record<string, { bg: string; text: string; label: string }> = {
    high: { bg: "rgba(34,197,94,0.15)", text: "var(--green)", label: "高" },
    medium: { bg: "rgba(234,179,8,0.15)", text: "#EAB308", label: "中" },
    low: { bg: "rgba(239,68,68,0.15)", text: "var(--red)", label: "低" },
  };
  const s = styles[c] ?? styles.medium;
  return (
    <span
      className="rounded-full px-1.5 py-0.5 text-[10px] font-semibold"
      style={{ backgroundColor: s.bg, color: s.text }}
    >
      {s.label}
    </span>
  );
}

export default function AiRecommendations({
  predictions,
  entries,
  onSelectBet,
}: Props) {
  const enriched = useMemo<EnrichedPrediction[]>(() => {
    return predictions
      .map((p) => {
        const entry = entries.find((e) => e.horse.id === p.horse_id);
        return {
          ...p,
          post_position: entry?.post_position ?? null,
          bracket_number: entry?.bracket_number ?? null,
        };
      })
      .sort((a, b) => (b.predicted_score ?? 0) - (a.predicted_score ?? 0));
  }, [predictions, entries]);

  if (enriched.length === 0) {
    return (
      <div
        className="flex flex-col items-center justify-center rounded-xl py-12"
        style={{
          backgroundColor: "var(--bg-elevated)",
          border: "1px solid var(--border)",
        }}
      >
        <svg
          className="mb-3 h-10 w-10"
          fill="none"
          stroke="currentColor"
          strokeWidth={1.5}
          viewBox="0 0 24 24"
          style={{ color: "var(--text-muted)" }}
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            d="M9.75 3.104v5.714a2.25 2.25 0 01-.659 1.591L5 14.5M9.75 3.104c-.251.023-.501.05-.75.082m.75-.082a24.301 24.301 0 014.5 0m0 0v5.714a2.25 2.25 0 00.659 1.591L19 14.5M14.25 3.104c.251.023.501.05.75.082M19 14.5l-2.47 2.47a3.375 3.375 0 01-4.06.58l-.5-.29a3.375 3.375 0 00-4.06.58L5 14.5"
          />
        </svg>
        <p className="text-sm font-medium" style={{ color: "var(--text-muted)" }}>
          AI予想データがありません
        </p>
        <p className="mt-1 text-xs" style={{ color: "var(--text-muted)" }}>
          予想実行後に推奨買い目が表示されます
        </p>
      </div>
    );
  }

  // Top 5 horses for recommendation
  const top5 = enriched.slice(0, 5);

  function horseLabel(p: EnrichedPrediction, rankIdx: number) {
    const mark = RANK_MARKS[rankIdx] ?? "";
    const pos = p.post_position ?? "?";
    return `${mark} ${pos}. ${p.horse_name ?? "不明"}`;
  }

  function scoreBar(score: number | null) {
    const s = score ?? 0;
    const pct = Math.min(s * 100, 100);
    return (
      <div className="flex items-center gap-2">
        <div
          className="h-1.5 flex-1 overflow-hidden rounded-full"
          style={{ backgroundColor: "rgba(255,255,255,0.06)" }}
        >
          <div
            className="h-full rounded-full transition-all duration-500"
            style={{
              width: `${pct}%`,
              background: "linear-gradient(90deg, var(--accent), #8B5CF6)",
            }}
          />
        </div>
        <span
          className="text-[10px] font-semibold tabular-nums"
          style={{ color: "var(--text-muted)", minWidth: "2rem", textAlign: "right" }}
        >
          {(s * 100).toFixed(0)}pt
        </span>
      </div>
    );
  }

  function renderBetRecommendation(bt: (typeof BET_TYPES)[number]) {
    const { value, label, picks, ordered } = bt;

    // Determine horses to recommend
    let recommended: EnrichedPrediction[];
    if (value === "fukusho" || value === "wide") {
      // For place-related bets, recommend top 3
      recommended = top5.slice(0, 3);
    } else {
      recommended = top5.slice(0, picks);
    }

    const horseIds = recommended.map((r) => r.horse_id);

    // Format the recommendation display
    let display: string;
    const positions = recommended.map((r) => r.post_position ?? "?");

    if (ordered && picks >= 2) {
      display = positions.join(" → ");
    } else if (picks >= 2) {
      display = positions.join(" - ");
    } else {
      display = String(positions[0]);
    }

    // For wide, show all 3 combinations from top 3
    let wideCombinations: string[] | null = null;
    if (value === "wide" && recommended.length >= 3) {
      wideCombinations = [
        `${recommended[0].post_position ?? "?"}-${recommended[1].post_position ?? "?"}`,
        `${recommended[0].post_position ?? "?"}-${recommended[2].post_position ?? "?"}`,
        `${recommended[1].post_position ?? "?"}-${recommended[2].post_position ?? "?"}`,
      ];
    }

    return (
      <div
        key={value}
        className="group cursor-pointer rounded-lg p-3 transition-all duration-200"
        style={{ backgroundColor: "rgba(255,255,255,0.02)" }}
        onClick={() => onSelectBet?.(value, horseIds)}
        onMouseEnter={(e) => {
          e.currentTarget.style.backgroundColor = "rgba(59,130,246,0.08)";
          e.currentTarget.style.boxShadow = "0 0 0 1px rgba(59,130,246,0.3)";
        }}
        onMouseLeave={(e) => {
          e.currentTarget.style.backgroundColor = "rgba(255,255,255,0.02)";
          e.currentTarget.style.boxShadow = "none";
        }}
      >
        <div className="mb-2 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <span
              className="inline-flex rounded-md px-2 py-0.5 text-xs font-bold"
              style={{
                background: "linear-gradient(135deg, var(--accent), #8B5CF6)",
                color: "#fff",
              }}
            >
              {label}
            </span>
            <span className="text-[10px]" style={{ color: "var(--text-muted)" }}>
              {bt.desc}
            </span>
          </div>
          <svg
            className="h-3.5 w-3.5 opacity-0 transition-opacity duration-200 group-hover:opacity-100"
            fill="none"
            stroke="currentColor"
            strokeWidth={2}
            viewBox="0 0 24 24"
            style={{ color: "var(--accent)" }}
          >
            <path strokeLinecap="round" strokeLinejoin="round" d="M13 7l5 5m0 0l-5 5m5-5H6" />
          </svg>
        </div>

        {/* Recommended horses */}
        <div className="space-y-1.5">
          {recommended.map((p, idx) => (
            <div key={p.horse_id} className="flex items-center gap-2">
              <span
                className="text-sm font-bold"
                style={{ color: RANK_COLORS[idx], minWidth: "1rem", textAlign: "center" }}
              >
                {RANK_MARKS[idx]}
              </span>
              <span
                className="inline-flex h-5 w-5 items-center justify-center rounded text-[10px] font-semibold"
                style={{
                  backgroundColor: "rgba(255,255,255,0.06)",
                  color: "var(--text-secondary)",
                }}
              >
                {p.post_position ?? "?"}
              </span>
              <span className="text-xs font-medium" style={{ color: "var(--text-primary)" }}>
                {p.horse_name ?? "不明"}
              </span>
              <div className="flex-1">{scoreBar(p.predicted_score)}</div>
              {confidenceBadge(p.confidence)}
            </div>
          ))}
        </div>

        {/* Bet notation */}
        <div className="mt-2 flex items-center gap-2">
          <span className="text-[10px] font-medium" style={{ color: "var(--text-muted)" }}>
            買い目:
          </span>
          {value === "wide" && wideCombinations ? (
            <div className="flex flex-wrap gap-1.5">
              {wideCombinations.map((combo, i) => (
                <span
                  key={`${combo}-${i}`}
                  className="rounded-md px-2 py-0.5 text-xs font-semibold tabular-nums"
                  style={{
                    backgroundColor: "rgba(59,130,246,0.12)",
                    color: "var(--accent)",
                  }}
                >
                  {combo}
                </span>
              ))}
            </div>
          ) : (
            <span
              className="rounded-md px-2 py-0.5 text-xs font-semibold tabular-nums"
              style={{
                backgroundColor: "rgba(59,130,246,0.12)",
                color: "var(--accent)",
              }}
            >
              {display}
            </span>
          )}
          {(value === "wide" || value === "fukusho") && (
            <span className="text-[10px]" style={{ color: "var(--text-muted)" }}>
              BOX
            </span>
          )}
        </div>
      </div>
    );
  }

  return (
    <div
      className="overflow-hidden rounded-xl"
      style={{
        backgroundColor: "var(--bg-elevated)",
        border: "1px solid var(--border)",
      }}
    >
      {/* Header */}
      <div
        className="flex items-center justify-between px-5 py-3"
        style={{
          borderBottom: "1px solid var(--border)",
          background:
            "linear-gradient(135deg, rgba(234,179,8,0.08), rgba(239,68,68,0.05))",
        }}
      >
        <div className="flex items-center gap-2">
          <div
            className="flex h-7 w-7 items-center justify-center rounded-lg"
            style={{
              background: "linear-gradient(135deg, #F59E0B, #EF4444)",
            }}
          >
            <svg
              className="h-4 w-4"
              fill="none"
              stroke="#fff"
              strokeWidth={2}
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z"
              />
            </svg>
          </div>
          <div>
            <h2
              className="text-sm font-bold"
              style={{ color: "var(--text-primary)" }}
            >
              AI推奨買い目
            </h2>
            <span className="text-[10px]" style={{ color: "var(--text-muted)" }}>
              クリックでシミュレーターに反映
            </span>
          </div>
        </div>
      </div>

      {/* Top horses summary */}
      <div
        className="px-5 py-3"
        style={{ borderBottom: "1px solid var(--border)" }}
      >
        <div className="mb-2 text-[10px] font-semibold uppercase tracking-wider" style={{ color: "var(--text-muted)" }}>
          AI総合ランキング
        </div>
        <div className="flex flex-wrap gap-2">
          {top5.map((p, idx) => (
            <div
              key={p.horse_id}
              className="flex items-center gap-1.5 rounded-lg px-2.5 py-1.5"
              style={{
                backgroundColor: idx === 0 ? "rgba(245,158,11,0.1)" : "rgba(255,255,255,0.03)",
                border: idx === 0 ? "1px solid rgba(245,158,11,0.3)" : "1px solid var(--border)",
              }}
            >
              <span
                className="text-sm font-bold"
                style={{ color: RANK_COLORS[idx] }}
              >
                {RANK_MARKS[idx]}
              </span>
              <span
                className="text-xs font-medium"
                style={{ color: "var(--text-primary)" }}
              >
                {p.post_position ?? "?"}. {p.horse_name ?? "不明"}
              </span>
              <span
                className="text-[10px] font-semibold tabular-nums"
                style={{ color: "var(--text-muted)" }}
              >
                {((p.predicted_score ?? 0) * 100).toFixed(0)}pt
              </span>
            </div>
          ))}
        </div>
      </div>

      {/* Recommendations per bet type */}
      <div className="divide-y" style={{ borderColor: "var(--border)" }}>
        {BET_TYPES.map((bt, i) => (
          <div key={bt.value} style={{ borderTop: i > 0 ? "1px solid var(--border)" : "none" }}>
            {renderBetRecommendation(bt)}
          </div>
        ))}
      </div>
    </div>
  );
}
