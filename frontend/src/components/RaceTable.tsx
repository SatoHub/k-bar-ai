"use client";

import Link from "next/link";
import type { RaceListItem } from "@/lib/api";
import { decodeRacecourse, decodeRaceName } from "@/lib/racecourse";

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

/**
 * Determine race status based on post_time, race_date, and finish data.
 * Returns: "finished" | "running" | "upcoming" | null
 */
function getRaceStatus(
  raceDate: string,
  postTime: string | null,
): "finished" | "running" | "upcoming" | null {
  if (!postTime) return null;

  const now = new Date();
  const today = now.toISOString().slice(0, 10);

  // Future date → upcoming
  if (raceDate > today) return "upcoming";
  // Past date → finished
  if (raceDate < today) return "finished";

  // Same day: compare time
  const [h, m] = postTime.split(":").map(Number);
  const postMinutes = h * 60 + m;
  const nowMinutes = now.getHours() * 60 + now.getMinutes();

  // Race takes ~2-4 minutes. If 10 min past post_time, consider finished.
  if (nowMinutes >= postMinutes + 10) return "finished";
  // Within 10 min of post_time, could be running
  if (nowMinutes >= postMinutes - 2) return "running";
  return "upcoming";
}

function StatusBadge({ status }: { status: "finished" | "running" | "upcoming" | null }) {
  if (!status) return null;

  const config = {
    finished: { label: "終了", bg: "rgba(107,114,128,0.2)", color: "var(--text-muted)" },
    running: { label: "発走中", bg: "rgba(239,68,68,0.15)", color: "#EF4444" },
    upcoming: { label: "未発走", bg: "rgba(34,197,94,0.15)", color: "var(--green)" },
  };

  const c = config[status];
  return (
    <span
      className="inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[10px] font-semibold"
      style={{ backgroundColor: c.bg, color: c.color }}
    >
      {status === "running" && (
        <span className="relative flex h-1.5 w-1.5">
          <span
            className="absolute inline-flex h-full w-full animate-ping rounded-full opacity-75"
            style={{ backgroundColor: c.color }}
          />
          <span
            className="relative inline-flex h-1.5 w-1.5 rounded-full"
            style={{ backgroundColor: c.color }}
          />
        </span>
      )}
      {c.label}
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
    <>
      {/* Mobile: card layout */}
      <div className="space-y-2 sm:hidden">
        {items.map((race) => {
          const status = getRaceStatus(race.race_date, race.post_time);
          const isFinished = status === "finished";
          const courseName = race.racecourse_name ?? decodeRacecourse(race.race_id) ?? "-";
          const course = formatCourse(race.surface, race.distance_m);

          return (
            <Link
              key={race.id}
              href={`/races/${race.race_id}`}
              className="block rounded-xl p-3 transition-colors"
              style={{
                backgroundColor: "var(--bg-card)",
                border: "1px solid var(--border)",
                opacity: isFinished ? 0.5 : 1,
              }}
            >
              <div className="flex items-center justify-between gap-2">
                <div className="flex items-center gap-2 text-xs" style={{ color: "var(--text-secondary)" }}>
                  <span className="tabular-nums">{race.race_date}</span>
                  <span className="tabular-nums font-medium" style={{ color: status === "upcoming" ? "var(--text-primary)" : "var(--text-secondary)" }}>
                    {race.post_time ? race.post_time.slice(0, 5) : ""}
                  </span>
                  <StatusBadge status={status} />
                </div>
                <GradeBadge grade={race.graded_race ?? null} />
              </div>
              <div className="mt-1.5 font-medium text-sm" style={{ color: "var(--accent)" }}>
                {race.race_name ?? decodeRaceName(race.race_id, race.race_number)}
              </div>
              <div className="mt-1 flex items-center gap-2 text-xs" style={{ color: "var(--text-muted)" }}>
                <span>{courseName}</span>
                <span>{race.race_number}R</span>
                <span>{course}</span>
                {race.track_condition && <span>{race.track_condition}</span>}
              </div>
            </Link>
          );
        })}
      </div>

      {/* Desktop: table layout */}
      <div className="hidden sm:block glass-card overflow-x-auto">
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
              <th className="px-4 py-3">発走</th>
              <th className="px-4 py-3">状態</th>
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
            {items.map((race) => {
              const status = getRaceStatus(race.race_date, race.post_time);
              const isFinished = status === "finished";

              return (
                <tr
                  key={race.id}
                  className="transition-colors"
                  style={{
                    borderBottom: "1px solid var(--border)",
                    cursor: "default",
                    opacity: isFinished ? 0.5 : 1,
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
                  <td
                    className="whitespace-nowrap px-4 py-3 tabular-nums font-medium"
                    style={{ color: status === "upcoming" ? "var(--text-primary)" : "var(--text-secondary)" }}
                  >
                    {race.post_time ? race.post_time.slice(0, 5) : "-"}
                  </td>
                  <td className="whitespace-nowrap px-4 py-3">
                    <StatusBadge status={status} />
                  </td>
                  <td className="whitespace-nowrap px-4 py-3">
                    {race.racecourse_name ?? decodeRacecourse(race.race_id) ?? "-"}
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
                      {race.race_name ?? decodeRaceName(race.race_id, race.race_number)}
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
              );
            })}
          </tbody>
        </table>
      </div>
    </>
  );
}
