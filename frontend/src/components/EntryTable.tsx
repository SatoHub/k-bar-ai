"use client";

import Link from "next/link";
import type { RaceEntry } from "@/lib/api";

type Props = {
  entries: RaceEntry[];
  isUpcoming?: boolean;
};

const BRACKET_COLORS: Record<number, string> = {
  1: "#ffffff",
  2: "#1a1a1a",
  3: "#dc2626",
  4: "#2563eb",
  5: "#eab308",
  6: "#16a34a",
  7: "#ea580c",
  8: "#ec4899",
};

function formatTime(tenths: number | null): string {
  if (tenths === null) return "---";
  const totalSeconds = tenths / 10;
  const minutes = Math.floor(totalSeconds / 60);
  const seconds = totalSeconds % 60;
  const sWhole = Math.floor(seconds);
  const sTenth = Math.round((seconds - sWhole) * 10);
  return `${minutes}:${String(sWhole).padStart(2, "0")}.${sTenth}`;
}

function BracketCircle({ bracket }: { bracket: number | null }) {
  if (bracket === null) return <span>---</span>;
  const color = BRACKET_COLORS[bracket] ?? "#9ca3af";
  const isDark = bracket === 2;
  const isWhite = bracket === 1;
  const isYellow = bracket === 5;

  return (
    <span
      className="inline-flex h-6 w-6 items-center justify-center rounded-full text-xs font-bold"
      style={{
        backgroundColor: color,
        color: isWhite || isYellow ? "#111" : isDark ? "#ccc" : "#fff",
        border: isWhite
          ? "1px solid var(--border-light)"
          : isDark
            ? "1px solid var(--border-light)"
            : undefined,
        boxShadow: "0 0 4px rgba(0,0,0,0.3)",
      }}
    >
      {bracket}
    </span>
  );
}

export default function EntryTable({ entries, isUpcoming }: Props) {
  const sorted = isUpcoming
    ? [...entries].sort(
        (a, b) => (a.post_position ?? 999) - (b.post_position ?? 999),
      )
    : [...entries].sort((a, b) => {
        if (a.finish_position === null && b.finish_position === null) return 0;
        if (a.finish_position === null) return 1;
        if (b.finish_position === null) return -1;
        return a.finish_position - b.finish_position;
      });

  return (
    <div className="glass-card overflow-hidden">
      <div
        className="flex items-center gap-2 px-4 py-3"
        style={{ borderBottom: "1px solid var(--border)" }}
      >
        <h2
          className="text-base font-semibold"
          style={{ color: "var(--text-primary)" }}
        >
          {isUpcoming ? "出馬表" : "出走表 / 結果"}
        </h2>
        {isUpcoming && (
          <span
            className="rounded-full px-2 py-0.5 text-xs font-medium"
            style={{
              backgroundColor: "rgba(59,130,246,0.15)",
              color: "var(--accent)",
            }}
          >
            出走前
          </span>
        )}
      </div>

      <div className="overflow-x-auto">
        <table className="w-full text-sm whitespace-nowrap">
          <thead>
            <tr
              className="text-left text-xs font-medium uppercase"
              style={{
                backgroundColor: "var(--bg-elevated)",
                color: "var(--text-secondary)",
              }}
            >
              <th className="px-3 py-2">枠</th>
              <th className="px-3 py-2">馬番</th>
              <th className="px-3 py-2">馬名</th>
              <th className="px-3 py-2">騎手</th>
              <th className="px-3 py-2">調教師</th>
              <th className="px-3 py-2">馬齢</th>
              <th className="px-3 py-2">斤量</th>
              {isUpcoming ? (
                <>
                  <th className="px-3 py-2">馬体重</th>
                  <th className="px-3 py-2">増減</th>
                </>
              ) : (
                <>
                  <th className="px-3 py-2">着順</th>
                  <th className="px-3 py-2">タイム</th>
                  <th className="px-3 py-2">着差</th>
                  <th className="px-3 py-2">上がり3F</th>
                  <th className="px-3 py-2">オッズ</th>
                  <th className="px-3 py-2">人気</th>
                </>
              )}
            </tr>
          </thead>
          <tbody>
            {sorted.map((e) => (
              <tr
                key={e.id}
                style={{
                  borderBottom: "1px solid var(--border)",
                  transition: "background-color 200ms ease-out",
                }}
                onMouseEnter={(ev) => {
                  ev.currentTarget.style.backgroundColor =
                    "var(--bg-card-hover)";
                }}
                onMouseLeave={(ev) => {
                  ev.currentTarget.style.backgroundColor = "transparent";
                }}
              >
                <td className="px-3 py-2 text-center">
                  <BracketCircle bracket={e.bracket_number} />
                </td>
                <td
                  className="px-3 py-2 text-center tabular-nums"
                  style={{ color: "var(--text-secondary)" }}
                >
                  {e.post_position ?? "---"}
                </td>
                <td className="px-3 py-2 font-medium">
                  <Link
                    href={`/horses/${e.horse.id}`}
                    className="cursor-pointer"
                    style={{
                      color: "var(--accent)",
                      transition: "color 200ms ease-out",
                    }}
                    onMouseEnter={(ev) =>
                      (ev.currentTarget.style.color = "var(--accent-hover)")
                    }
                    onMouseLeave={(ev) =>
                      (ev.currentTarget.style.color = "var(--accent)")
                    }
                  >
                    {e.horse.name}
                  </Link>
                </td>
                <td
                  className="px-3 py-2"
                  style={{ color: "var(--text-secondary)" }}
                >
                  {e.jockey?.name ?? "---"}
                </td>
                <td
                  className="px-3 py-2"
                  style={{ color: "var(--text-secondary)" }}
                >
                  {e.trainer?.name ?? "---"}
                </td>
                <td
                  className="px-3 py-2 text-center tabular-nums"
                  style={{ color: "var(--text-secondary)" }}
                >
                  {e.horse_age ?? "---"}
                </td>
                <td
                  className="px-3 py-2 text-right tabular-nums"
                  style={{ color: "var(--text-secondary)" }}
                >
                  {e.weight_carried_kg !== null
                    ? `${Number(e.weight_carried_kg)}kg`
                    : "---"}
                </td>
                {isUpcoming ? (
                  <>
                    <td
                      className="px-3 py-2 text-right tabular-nums"
                      style={{ color: "var(--text-secondary)" }}
                    >
                      {e.horse_weight_kg !== null
                        ? `${e.horse_weight_kg}kg`
                        : "---"}
                    </td>
                    <td
                      className="px-3 py-2 text-right tabular-nums"
                      style={{
                        color:
                          e.horse_weight_diff !== null && e.horse_weight_diff > 0
                            ? "var(--red)"
                            : e.horse_weight_diff !== null &&
                                e.horse_weight_diff < 0
                              ? "var(--accent)"
                              : "var(--text-secondary)",
                      }}
                    >
                      {e.horse_weight_diff !== null
                        ? `${e.horse_weight_diff > 0 ? "+" : ""}${e.horse_weight_diff}`
                        : "---"}
                    </td>
                  </>
                ) : (
                  <>
                    <td
                      className="px-3 py-2 text-center font-medium"
                      style={{ color: "var(--text-primary)" }}
                    >
                      {e.finish_position ?? e.finish_note ?? "---"}
                    </td>
                    <td
                      className="px-3 py-2 text-right tabular-nums"
                      style={{ color: "var(--text-secondary)" }}
                    >
                      {formatTime(e.total_time_tenths)}
                    </td>
                    <td
                      className="px-3 py-2 text-center"
                      style={{ color: "var(--text-secondary)" }}
                    >
                      {e.margin ?? "---"}
                    </td>
                    <td
                      className="px-3 py-2 text-right tabular-nums"
                      style={{ color: "var(--text-secondary)" }}
                    >
                      {e.last_3f_time !== null
                        ? Number(e.last_3f_time).toFixed(1)
                        : "---"}
                    </td>
                    <td
                      className="px-3 py-2 text-right tabular-nums"
                      style={{ color: "var(--text-secondary)" }}
                    >
                      {e.win_odds !== null
                        ? Number(e.win_odds).toFixed(1)
                        : "---"}
                    </td>
                    <td
                      className="px-3 py-2 text-center"
                      style={{ color: "var(--text-secondary)" }}
                    >
                      {e.win_favorite ?? "---"}
                    </td>
                  </>
                )}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
