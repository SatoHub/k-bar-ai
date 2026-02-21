"use client";

type Props = {
  shapData: Record<string, number>;
};

// Japanese feature name mapping
const FEATURE_LABELS: Record<string, string> = {
  win_odds: "単勝オッズ",
  win_favorite: "人気順",
  weight_carried_kg: "斤量",
  horse_age: "馬齢",
  distance_m: "距離",
  finish_position_avg: "平均着順",
  last_3f_time: "上がり3F",
  horse_weight_kg: "馬体重",
  horse_weight_diff: "体重増減",
  jockey_win_rate: "騎手勝率",
  trainer_win_rate: "調教師勝率",
  surface: "馬場種別",
  track_condition: "馬場状態",
  bracket_number: "枠番",
  post_position: "馬番",
};

function getLabel(key: string): string {
  return FEATURE_LABELS[key] ?? key;
}

export default function ShapChart({ shapData }: Props) {
  // Sort by absolute value, show top 8
  const sorted = Object.entries(shapData)
    .sort(([, a], [, b]) => Math.abs(b) - Math.abs(a))
    .slice(0, 8);

  if (sorted.length === 0) return null;

  const maxAbs = Math.max(...sorted.map(([, v]) => Math.abs(v)), 0.001);

  return (
    <div className="space-y-1.5">
      {sorted.map(([key, value]) => {
        const pct = (Math.abs(value) / maxAbs) * 100;
        const isPositive = value >= 0;
        return (
          <div key={key} className="flex items-center gap-2 text-xs">
            <span
              className="w-20 shrink-0 text-right truncate"
              style={{ color: "var(--text-secondary)" }}
              title={getLabel(key)}
            >
              {getLabel(key)}
            </span>
            <div className="flex-1 flex items-center">
              <div
                className="relative h-4 flex-1"
                style={{ backgroundColor: "transparent" }}
              >
                {/* Center line */}
                <div
                  className="absolute top-0 bottom-0 left-1/2"
                  style={{
                    width: 1,
                    backgroundColor: "var(--border)",
                  }}
                />
                {/* Bar */}
                <div
                  className="absolute top-0.5 bottom-0.5 rounded-sm"
                  style={{
                    backgroundColor: isPositive
                      ? "rgba(59,130,246,0.7)"
                      : "rgba(239,68,68,0.7)",
                    left: isPositive ? "50%" : `${50 - pct / 2}%`,
                    width: `${pct / 2}%`,
                  }}
                />
              </div>
            </div>
            <span
              className="w-12 shrink-0 text-right tabular-nums"
              style={{
                color: isPositive ? "var(--accent)" : "var(--red)",
              }}
            >
              {value > 0 ? "+" : ""}
              {value.toFixed(3)}
            </span>
          </div>
        );
      })}
    </div>
  );
}
