"use client";

import React, { useState } from "react";
import Link from "next/link";
import type { PredictionEntry, UpsetScore } from "@/lib/api";
import ConfidenceBadge from "./ConfidenceBadge";
import ShapChart from "./ShapChart";

type Props = {
  predictions: PredictionEntry[];
  modelVersion: string | null;
  upset?: UpsetScore | null;
};

const COL_COUNT = 6;

const UPSET_STYLE: Record<
  UpsetScore["level"],
  { label: string; bg: string; fg: string; border: string }
> = {
  high: { label: "荒れ度 高", bg: "#fef2f2", fg: "#b91c1c", border: "#fecaca" },
  mid: { label: "荒れ度 中", bg: "#fffbeb", fg: "#b45309", border: "#fde68a" },
  low: { label: "荒れ度 低", bg: "#f0fdf4", fg: "#15803d", border: "#bbf7d0" },
};

function UpsetBanner({ upset }: { upset: UpsetScore }) {
  const s = UPSET_STYLE[upset.level] ?? UPSET_STYLE.mid;
  return (
    <div
      className="flex flex-wrap items-center gap-x-3 gap-y-1 px-4 py-2.5 text-xs"
      style={{ backgroundColor: s.bg, borderBottom: "1px solid var(--border)" }}
    >
      <span
        className="rounded-full px-2.5 py-0.5 font-semibold"
        style={{ backgroundColor: "#fff", color: s.fg, border: `1px solid ${s.border}` }}
      >
        {s.label}
      </span>
      <span style={{ color: s.fg }} className="font-medium">
        波乱確率 {Math.round(upset.expected_upset_rate * 100)}%
        <span style={{ opacity: 0.7 }}>（上位{Math.round(upset.percentile * 100)}%）</span>
      </span>
      <span style={{ color: "var(--text-secondary)" }}>{upset.hint}</span>
    </div>
  );
}

export default function PredictionTable({ predictions, modelVersion, upset }: Props) {
  const [expandedId, setExpandedId] = useState<string | null>(null);

  if (predictions.length === 0) {
    return (
      <div
        className="glass-card p-8 text-center text-sm"
        style={{ color: "var(--text-secondary)" }}
      >
        このレースの予測はありません
      </div>
    );
  }

  const sorted = [...predictions].sort(
    (a, b) => (b.predicted_score ?? 0) - (a.predicted_score ?? 0),
  );

  function toggleExpand(id: string) {
    setExpandedId((prev) => (prev === id ? null : id));
  }

  return (
    <div className="glass-card overflow-hidden">
      <div
        className="flex items-center justify-between px-4 py-3"
        style={{ borderBottom: "1px solid var(--border)" }}
      >
        <div className="flex items-center gap-2">
          <div
            className="w-1 self-stretch rounded-full"
            style={{ backgroundColor: "var(--accent)" }}
          />
          <h2
            className="text-base font-semibold"
            style={{ color: "var(--text-primary)" }}
          >
            AI 予測
          </h2>
        </div>
        {modelVersion && (
          <span
            className="rounded-full px-2.5 py-0.5 text-xs font-medium"
            style={{
              backgroundColor: "var(--accent-muted)",
              color: "var(--accent)",
            }}
          >
            {modelVersion}
          </span>
        )}
      </div>

      {upset && <UpsetBanner upset={upset} />}

      {/* Mobile: card layout */}
      <div className="sm:hidden divide-y" style={{ borderColor: "var(--border)" }}>
        {sorted.map((p, idx) => {
          const rank = idx + 1;
          const hit = rank <= 3 && p.actual_finish !== null && p.actual_finish <= 3;
          const score = Number(p.predicted_score ?? 0);
          const hasShap = p.shap_data && Object.keys(p.shap_data).length > 0;
          const hasExplanation = !!p.explanation;
          const canExpand = hasShap || hasExplanation;
          const isExpanded = expandedId === p.id;

          return (
            <div
              key={p.id}
              className="px-4 py-3"
              style={{
                borderColor: "var(--border)",
                backgroundColor: hit ? "rgba(63,185,80,0.08)" : undefined,
              }}
            >
              <div className="flex items-center justify-between gap-2">
                <div className="flex items-center gap-2.5">
                  <span
                    className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full text-xs font-bold"
                    style={{
                      backgroundColor: rank <= 3 ? "var(--accent)" : "var(--bg-elevated)",
                      color: rank <= 3 ? "#fff" : "var(--text-secondary)",
                    }}
                  >
                    {rank}
                  </span>
                  <Link
                    href={`/horses/${p.horse_id}`}
                    className="font-medium text-sm"
                    style={{ color: "var(--accent)" }}
                  >
                    {p.horse_name ?? "---"}
                  </Link>
                </div>
                <div className="flex items-center gap-2">
                  <ConfidenceBadge confidence={p.confidence} />
                  {p.actual_finish !== null && (
                    <span className="text-xs" style={{ color: "var(--text-muted)" }}>
                      着順: {p.actual_finish}
                    </span>
                  )}
                </div>
              </div>
              <div className="mt-2 flex items-center gap-2">
                <div
                  className="relative h-3 flex-1 overflow-hidden rounded-full"
                  style={{ backgroundColor: "var(--bg-elevated)" }}
                >
                  <div
                    className="absolute inset-y-0 left-0 rounded-full"
                    style={{
                      width: `${Math.min(score * 100, 100)}%`,
                      backgroundColor: "var(--accent)",
                    }}
                  />
                </div>
                <span
                  className="w-9 text-right text-xs tabular-nums"
                  style={{ color: "var(--text-secondary)" }}
                >
                  {score.toFixed(2)}
                </span>
              </div>
              {canExpand && (
                <>
                  <button
                    type="button"
                    onClick={() => toggleExpand(p.id)}
                    className="mt-2 cursor-pointer rounded-full px-2.5 py-0.5 text-xs font-medium"
                    style={{
                      backgroundColor: "var(--accent-muted)",
                      color: "var(--accent)",
                    }}
                  >
                    {isExpanded ? "閉じる" : hasShap ? "SHAP分析" : "説明を見る"}
                  </button>
                  {isExpanded && (
                    <div
                      className="mt-2 rounded-lg p-3 text-xs leading-relaxed"
                      style={{
                        backgroundColor: "var(--bg-elevated)",
                        border: "1px solid var(--border)",
                        color: "var(--text-secondary)",
                      }}
                    >
                      {hasShap && p.shap_data ? (
                        <ShapChart shapData={p.shap_data} />
                      ) : (
                        <span className="whitespace-pre-wrap">{p.explanation}</span>
                      )}
                    </div>
                  )}
                </>
              )}
            </div>
          );
        })}
      </div>

      {/* Desktop: table layout */}
      <div className="hidden sm:block overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr
              className="text-left text-xs font-medium uppercase"
              style={{
                backgroundColor: "var(--bg-elevated)",
                color: "var(--text-secondary)",
              }}
            >
              <th className="px-4 py-2 w-16">順位</th>
              <th className="px-4 py-2 w-56">馬名</th>
              <th className="px-4 py-2 w-52">予測スコア</th>
              <th className="px-4 py-2 w-20">信頼度</th>
              <th className="px-4 py-2 w-20">実着順</th>
              <th className="px-4 py-2">予想根拠</th>
            </tr>
          </thead>
          <tbody>
            {sorted.map((p, idx) => {
              const rank = idx + 1;
              const hit =
                rank <= 3 &&
                p.actual_finish !== null &&
                p.actual_finish <= 3;
              const score = Number(p.predicted_score ?? 0);
              const hasShap = p.shap_data && Object.keys(p.shap_data).length > 0;
              const hasExplanation = !!p.explanation;
              const isExpanded = expandedId === p.id;

              return (
                <React.Fragment key={p.id}>
                  <tr
                    className="[&>td]:align-top"
                    style={{
                      borderBottom: isExpanded ? "none" : "1px solid var(--border)",
                      backgroundColor: hit
                        ? "rgba(63,185,80,0.08)"
                        : undefined,
                      transition: "background-color 200ms ease-out",
                    }}
                    onMouseEnter={(e) => {
                      if (!hit)
                        e.currentTarget.style.backgroundColor =
                          "var(--bg-card-hover)";
                    }}
                    onMouseLeave={(e) => {
                      if (!hit)
                        e.currentTarget.style.backgroundColor = "transparent";
                    }}
                  >
                    <td
                      className="px-4 py-2 text-center font-medium"
                      style={{ color: "var(--text-primary)" }}
                    >
                      {rank}
                    </td>
                    <td className="px-4 py-2 font-medium">
                      <Link
                        href={`/horses/${p.horse_id}`}
                        className="cursor-pointer"
                        style={{
                          color: "var(--accent)",
                          transition: "color 200ms ease-out",
                        }}
                        onMouseEnter={(e) =>
                          (e.currentTarget.style.color = "var(--accent-hover)")
                        }
                        onMouseLeave={(e) =>
                          (e.currentTarget.style.color = "var(--accent)")
                        }
                      >
                        {p.horse_name ?? "---"}
                      </Link>
                    </td>
                    <td className="px-4 py-2">
                      <div className="flex items-center gap-2">
                        <div
                          className="relative h-4 flex-1 overflow-hidden rounded-full"
                          style={{ backgroundColor: "var(--bg-elevated)" }}
                        >
                          <div
                            className="absolute inset-y-0 left-0 rounded-full"
                            style={{
                              width: `${Math.min(score * 100, 100)}%`,
                              backgroundColor: "var(--accent)",
                              transition: "width 200ms ease-out",
                            }}
                          />
                        </div>
                        <span
                          className="w-10 text-right text-xs tabular-nums"
                          style={{ color: "var(--text-secondary)" }}
                        >
                          {score.toFixed(2)}
                        </span>
                      </div>
                    </td>
                    <td className="px-4 py-2">
                      <ConfidenceBadge confidence={p.confidence} />
                    </td>
                    <td
                      className="px-4 py-2 text-center"
                      style={{ color: "var(--text-secondary)" }}
                    >
                      {p.actual_finish ?? "---"}
                    </td>
                    <td className="px-4 py-2">
                      {hasExplanation && (
                        <p
                          className="text-xs leading-relaxed"
                          style={{ color: "var(--text-secondary)" }}
                        >
                          {p.explanation?.replace(
                            /^この馬の予想根拠[:：]\s*/,
                            "",
                          )}
                        </p>
                      )}
                      {hasShap && (
                        <button
                          type="button"
                          onClick={() => toggleExpand(p.id)}
                          className="mt-1.5 cursor-pointer rounded-full px-2.5 py-0.5 text-xs font-medium"
                          style={{
                            backgroundColor: "var(--accent-muted)",
                            color: "var(--accent)",
                          }}
                        >
                          {isExpanded ? "閉じる" : "SHAP分析"}
                        </button>
                      )}
                      {!hasExplanation && !hasShap && (
                        <span
                          className="text-xs"
                          style={{ color: "var(--text-muted)" }}
                        >
                          —
                        </span>
                      )}
                    </td>
                  </tr>
                  {isExpanded && (
                    <tr style={{ borderBottom: "1px solid var(--border)" }}>
                      <td colSpan={COL_COUNT} className="px-4 pb-3 pt-0">
                        <div
                          className="rounded-lg p-4 text-xs leading-relaxed"
                          style={{
                            backgroundColor: "var(--bg-elevated)",
                            border: "1px solid var(--border)",
                            color: "var(--text-secondary)",
                          }}
                        >
                          {hasShap && p.shap_data ? (
                            <ShapChart shapData={p.shap_data} />
                          ) : (
                            <span className="whitespace-pre-wrap">{p.explanation}</span>
                          )}
                        </div>
                      </td>
                    </tr>
                  )}
                </React.Fragment>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
