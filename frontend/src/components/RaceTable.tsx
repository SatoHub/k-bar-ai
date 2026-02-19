"use client";

import Link from "next/link";
import type { RaceListItem } from "@/lib/api";

type Props = {
  items: RaceListItem[];
};

function formatCourse(surface: string | null, distance: number | null): string {
  if (!surface && !distance) return "-";
  const s = surface === "芝" ? "芝" : surface === "ダート" ? "ダ" : (surface ?? "");
  const d = distance ? `${distance}m` : "";
  return `${s}${d}`;
}

function GradeBadge({ grade }: { grade: string | null }) {
  if (!grade) return <span style={{ color: "var(--text-muted)" }}>-</span>;

  const isGraded = /^G[I]+$/i.test(grade) || /^G[1-3]$/i.test(grade);

  if (isGraded) {
    return (
      <span
        className="inline-flex items-center rounded-full px-2 py-0.5 text-xs font-bold"
        style={{
          backgroundColor: "var(--cta)",
          color: "#fff",
        }}
      >
        {grade}
      </span>
    );
  }

  return (
    <span
      className="inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium"
      style={{
        backgroundColor: "var(--accent-muted)",
        color: "var(--accent-hover)",
      }}
    >
      {grade}
    </span>
  );
}

export default function RaceTable({ items }: Props) {
  if (items.length === 0) {
    return (
      <div
        className="glass-card p-8 text-center"
        style={{ color: "var(--text-muted)" }}
      >
        レースが見つかりません
      </div>
    );
  }

  return (
    <div className="glass-card overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr
            className="text-left text-xs font-medium uppercase tracking-wider"
            style={{
              backgroundColor: "var(--bg-elevated)",
              color: "var(--text-secondary)",
            }}
          >
            <th className="px-4 py-3">日付</th>
            <th className="px-4 py-3">競馬場</th>
            <th className="px-4 py-3 text-center">R</th>
            <th className="px-4 py-3">レース名</th>
            <th className="px-4 py-3">コース</th>
            <th className="px-4 py-3">天候</th>
            <th className="px-4 py-3">馬場状態</th>
            <th className="px-4 py-3">グレード</th>
          </tr>
        </thead>
        <tbody>
          {items.map((race) => (
            <tr
              key={race.id}
              className="transition-colors"
              style={{
                borderBottom: "1px solid var(--border)",
                cursor: "default",
              }}
              onMouseEnter={(e) =>
                (e.currentTarget.style.backgroundColor = "var(--bg-card-hover)")
              }
              onMouseLeave={(e) =>
                (e.currentTarget.style.backgroundColor = "transparent")
              }
            >
              <td
                className="whitespace-nowrap px-4 py-3"
                style={{ color: "var(--text-secondary)" }}
              >
                {race.race_date}
              </td>
              <td className="whitespace-nowrap px-4 py-3">
                {race.racecourse_name ?? "-"}
              </td>
              <td
                className="whitespace-nowrap px-4 py-3 text-center"
                style={{ color: "var(--text-secondary)" }}
              >
                {race.race_number ?? "-"}
              </td>
              <td className="px-4 py-3">
                <Link
                  href={`/races/${race.race_id}`}
                  className="cursor-pointer font-medium"
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
                  {race.race_name ?? "-"}
                </Link>
              </td>
              <td className="whitespace-nowrap px-4 py-3">
                {formatCourse(race.surface, race.distance_m)}
              </td>
              <td className="whitespace-nowrap px-4 py-3">
                {race.weather ?? "-"}
              </td>
              <td className="whitespace-nowrap px-4 py-3">
                {race.track_condition ?? "-"}
              </td>
              <td className="whitespace-nowrap px-4 py-3">
                <GradeBadge grade={race.graded_race ?? null} />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
