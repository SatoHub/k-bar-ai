"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { fetchResultsSummary, type ResultsSummary } from "@/lib/api";

const BET_TYPE_LABELS: Record<string, string> = {
  tansho: "単勝",
  fukusho: "複勝",
  wakuren: "枠連",
  umaren: "馬連",
  umatan: "馬単",
  wide: "ワイド",
  sanrenpuku: "三連複",
  sanrentan: "三連単",
};

const BET_TYPE_ORDER = [
  "tansho",
  "fukusho",
  "wakuren",
  "umaren",
  "umatan",
  "wide",
  "sanrenpuku",
  "sanrentan",
];

function rateColor(rate: number): string {
  if (rate >= 40) return "var(--green)";
  if (rate >= 20) return "var(--accent)";
  if (rate >= 10) return "var(--text-primary)";
  return "var(--text-muted)";
}

function barGradient(rate: number): string {
  if (rate >= 40) return "linear-gradient(90deg, #22c55e, #16a34a)";
  if (rate >= 20) return "linear-gradient(90deg, #3b82f6, #8b5cf6)";
  if (rate >= 10) return "linear-gradient(90deg, #6b7280, #9ca3af)";
  return "linear-gradient(90deg, #374151, #4b5563)";
}

export default function AiHitRateCard() {
  const [summary, setSummary] = useState<ResultsSummary | null>(null);

  useEffect(() => {
    fetchResultsSummary()
      .then(setSummary)
      .catch(() => {});
  }, []);

  if (!summary || summary.total_races === 0) return null;

  const hitRates = summary.hit_rates;

  return (
    <div className="glass-card overflow-hidden">
      {/* Header */}
      <div
        className="flex items-center justify-between px-5 py-3"
        style={{ borderBottom: "1px solid var(--border)" }}
      >
        <div className="flex items-center gap-2">
          <div
            className="flex h-7 w-7 items-center justify-center rounded-lg"
            style={{
              background: "linear-gradient(135deg, #f59e0b, #ef4444)",
            }}
          >
            <svg
              viewBox="0 0 24 24"
              fill="none"
              stroke="#fff"
              strokeWidth={2}
              className="h-4 w-4"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                d="M11.48 3.499a.562.562 0 0 1 1.04 0l2.125 5.111a.563.563 0 0 0 .475.345l5.518.442c.499.04.701.663.321.988l-4.204 3.602a.563.563 0 0 0-.182.557l1.285 5.385a.562.562 0 0 1-.84.61l-4.725-2.885a.562.562 0 0 0-.586 0L6.982 20.54a.562.562 0 0 1-.84-.61l1.285-5.386a.562.562 0 0 0-.182-.557l-4.204-3.602a.562.562 0 0 1 .321-.988l5.518-.442a.563.563 0 0 0 .475-.345L11.48 3.5Z"
              />
            </svg>
          </div>
          <div>
            <h3
              className="text-sm font-bold"
              style={{ color: "var(--text-primary)" }}
            >
              AI予想 的中率
            </h3>
            <span className="text-[10px]" style={{ color: "var(--text-muted)" }}>
              {summary.period} / {summary.total_races}レース
            </span>
          </div>
        </div>
        <Link
          href="/results"
          className="text-xs cursor-pointer font-medium"
          style={{ color: "var(--accent)" }}
        >
          詳細 &rarr;
        </Link>
      </div>

      {/* Grid of 8 bet types */}
      <div className="grid grid-cols-2 sm:grid-cols-4">
        {BET_TYPE_ORDER.map((key, idx) => {
          const entry = hitRates[key];
          if (!entry) return null;
          const label = BET_TYPE_LABELS[key] ?? key;
          const isLast = idx >= BET_TYPE_ORDER.length - 4;
          const isEven = idx % 2 === 0;

          return (
            <div
              key={key}
              className="px-4 py-3"
              style={{
                borderRight: isEven ? "1px solid var(--border)" : "none",
                borderBottom: !isLast ? "1px solid var(--border)" : "none",
              }}
            >
              <div className="flex items-center justify-between mb-1">
                <span
                  className="text-[11px] font-semibold"
                  style={{ color: "var(--text-secondary)" }}
                >
                  {label}
                </span>
                <span
                  className="text-xs font-medium tabular-nums"
                  style={{ color: "var(--text-muted)" }}
                >
                  {entry.hits}/{entry.total}
                </span>
              </div>
              <div
                className="text-xl font-bold tabular-nums"
                style={{ color: rateColor(entry.rate) }}
              >
                {entry.rate.toFixed(1)}
                <span className="text-xs font-normal ml-0.5">%</span>
              </div>
              {/* Progress bar */}
              <div
                className="mt-1.5 h-1.5 w-full overflow-hidden rounded-full"
                style={{ backgroundColor: "rgba(255,255,255,0.06)" }}
              >
                <div
                  className="h-full rounded-full transition-all duration-500"
                  style={{
                    width: `${Math.min(entry.rate, 100)}%`,
                    background: barGradient(entry.rate),
                  }}
                />
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
