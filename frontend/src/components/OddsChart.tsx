"use client";

import { useMemo } from "react";
import type { OddsHistoryPoint } from "@/lib/api";

type Props = {
  history: OddsHistoryPoint[];
};

const BRACKET_COLORS: Record<number, string> = {
  1: "#ffffff",
  2: "#6b7280",
  3: "#dc2626",
  4: "#2563eb",
  5: "#eab308",
  6: "#16a34a",
  7: "#ea580c",
  8: "#ec4899",
};

function getColor(postPosition: number): string {
  return BRACKET_COLORS[((postPosition - 1) % 8) + 1] ?? "#9ca3af";
}

export default function OddsChart({ history }: Props) {
  const data = useMemo(() => {
    if (history.length < 2) return null;

    // Group by post_position
    const byHorse = new Map<number, { name: string; points: { t: number; odds: number }[] }>();
    const allTimes: number[] = [];

    for (const h of history) {
      if (!byHorse.has(h.post_position)) {
        byHorse.set(h.post_position, {
          name: h.horse_name ?? `馬番${h.post_position}`,
          points: [],
        });
      }
      const t = new Date(h.fetched_at ?? "").getTime();
      byHorse.get(h.post_position)!.points.push({ t, odds: h.win_odds });
      allTimes.push(t);
    }

    // Need at least 2 distinct time points total
    const uniqueTimes = [...new Set(allTimes)].sort((a, b) => a - b);
    if (uniqueTimes.length < 2) return null;

    const tMin = uniqueTimes[0];
    const tMax = uniqueTimes[uniqueTimes.length - 1];

    // Find odds range
    let oddsMin = Infinity;
    let oddsMax = 0;
    for (const [, v] of byHorse) {
      for (const p of v.points) {
        if (p.odds < oddsMin) oddsMin = p.odds;
        if (p.odds > oddsMax) oddsMax = p.odds;
      }
    }
    // Pad
    oddsMin = Math.max(0, oddsMin - 1);
    oddsMax = oddsMax + 2;

    return { byHorse, tMin, tMax, oddsMin, oddsMax };
  }, [history]);

  if (!data) {
    return (
      <div
        className="py-4 text-center text-xs"
        style={{ color: "var(--text-muted)" }}
      >
        オッズ変動データが不足しています
      </div>
    );
  }

  const { byHorse, tMin, tMax, oddsMin, oddsMax } = data;
  const W = 600;
  const H = 300;
  const PAD = { top: 20, right: 120, bottom: 30, left: 50 };
  const chartW = W - PAD.left - PAD.right;
  const chartH = H - PAD.top - PAD.bottom;

  function scaleX(t: number): number {
    return PAD.left + ((t - tMin) / (tMax - tMin || 1)) * chartW;
  }

  function scaleY(odds: number): number {
    return PAD.top + ((oddsMax - odds) / (oddsMax - oddsMin || 1)) * chartH;
  }

  // Generate Y-axis ticks
  const yTicks: number[] = [];
  const yStep = Math.max(1, Math.ceil((oddsMax - oddsMin) / 5));
  for (let v = Math.ceil(oddsMin); v <= oddsMax; v += yStep) {
    yTicks.push(v);
  }

  return (
    <div className="overflow-x-auto">
      <svg
        viewBox={`0 0 ${W} ${H}`}
        className="w-full"
        style={{ minWidth: 400, maxWidth: 600 }}
      >
        {/* Grid lines */}
        {yTicks.map((v) => (
          <g key={v}>
            <line
              x1={PAD.left}
              y1={scaleY(v)}
              x2={PAD.left + chartW}
              y2={scaleY(v)}
              stroke="var(--border)"
              strokeWidth={0.5}
            />
            <text
              x={PAD.left - 6}
              y={scaleY(v)}
              textAnchor="end"
              dominantBaseline="middle"
              fontSize={10}
              fill="var(--text-secondary)"
            >
              {v.toFixed(1)}
            </text>
          </g>
        ))}

        {/* Lines per horse */}
        {[...byHorse.entries()].map(([post, { name, points }]) => {
          if (points.length < 2) return null;
          const sorted = [...points].sort((a, b) => a.t - b.t);
          const pathD = sorted
            .map((p, i) => `${i === 0 ? "M" : "L"}${scaleX(p.t)},${scaleY(p.odds)}`)
            .join(" ");
          const color = getColor(post);
          const lastPt = sorted[sorted.length - 1];

          return (
            <g key={post}>
              <path
                d={pathD}
                fill="none"
                stroke={color}
                strokeWidth={2}
                strokeLinecap="round"
                strokeLinejoin="round"
              />
              {/* Dots */}
              {sorted.map((p, i) => (
                <circle
                  key={i}
                  cx={scaleX(p.t)}
                  cy={scaleY(p.odds)}
                  r={3}
                  fill={color}
                />
              ))}
              {/* Label at end */}
              <text
                x={scaleX(lastPt.t) + 6}
                y={scaleY(lastPt.odds)}
                fontSize={9}
                fill={color}
                dominantBaseline="middle"
              >
                {post}. {name.length > 6 ? name.substring(0, 6) + "…" : name}
              </text>
            </g>
          );
        })}

        {/* Axes */}
        <line
          x1={PAD.left}
          y1={PAD.top}
          x2={PAD.left}
          y2={PAD.top + chartH}
          stroke="var(--text-muted)"
          strokeWidth={1}
        />
        <line
          x1={PAD.left}
          y1={PAD.top + chartH}
          x2={PAD.left + chartW}
          y2={PAD.top + chartH}
          stroke="var(--text-muted)"
          strokeWidth={1}
        />
      </svg>
    </div>
  );
}
