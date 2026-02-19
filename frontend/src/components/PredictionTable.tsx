"use client";

import type { PredictionEntry } from "@/lib/api";
import ConfidenceBadge from "./ConfidenceBadge";
import ExplanationCard from "./ExplanationCard";

type Props = {
  predictions: PredictionEntry[];
  modelVersion: string | null;
};

export default function PredictionTable({ predictions, modelVersion }: Props) {
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

      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr
              className="text-left text-xs font-medium uppercase"
              style={{
                backgroundColor: "var(--bg-elevated)",
                color: "var(--text-secondary)",
              }}
            >
              <th className="px-4 py-2 w-12">順位</th>
              <th className="px-4 py-2">馬名</th>
              <th className="px-4 py-2 w-48">予測スコア</th>
              <th className="px-4 py-2 w-20">信頼度</th>
              <th className="px-4 py-2 w-20">実着順</th>
              <th className="px-4 py-2 w-24">説明</th>
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

              return (
                <tr
                  key={p.id}
                  style={{
                    borderBottom: "1px solid var(--border)",
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
                  <td
                    className="px-4 py-2 font-medium"
                    style={{ color: "var(--text-primary)" }}
                  >
                    {p.horse_name ?? "---"}
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
                    <ExplanationCard explanation={p.explanation} />
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
