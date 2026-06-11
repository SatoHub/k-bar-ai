"use client";

import { Fragment, useState } from "react";
import Link from "next/link";
import type { HorsePedigree, PastRaceRecord, RaceEntry } from "@/lib/api";

type Props = {
  entries: RaceEntry[];
  isUpcoming?: boolean;
  /** 過去走（馬柱）: horse.id → 直近N走 */
  pastByHorse?: Record<string, PastRaceRecord[]>;
  /** 血統: horse.id → 父/母父（JRA-VAN由来） */
  pedigreeByHorse?: Record<string, HorsePedigree>;
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

function shortDate(iso: string): string {
  // "2009-02-07" -> "09.2.7"
  const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(iso);
  if (!m) return iso;
  return `${m[1].slice(2)}.${Number(m[2])}.${Number(m[3])}`;
}

function finishColor(pos: number | null): string {
  if (pos === 1) return "var(--red)";
  if (pos === 2 || pos === 3) return "var(--accent)";
  return "var(--text-primary)";
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

/** 馬柱: 1頭の過去走を競馬新聞風のミニテーブルで表示 */
function PastRacesPanel({ records }: { records: PastRaceRecord[] }) {
  if (records.length === 0) {
    return (
      <div
        className="px-4 py-3 text-xs"
        style={{ color: "var(--text-secondary)" }}
      >
        過去走データがありません
      </div>
    );
  }
  return (
    <div className="overflow-x-auto px-3 py-2">
      <table className="w-full text-xs whitespace-nowrap">
        <thead>
          <tr style={{ color: "var(--text-secondary)" }}>
            <th className="px-2 py-1 text-left font-medium">日付</th>
            <th className="px-2 py-1 text-left font-medium">開催</th>
            <th className="px-2 py-1 text-left font-medium">レース</th>
            <th className="px-2 py-1 text-left font-medium">距離/馬場</th>
            <th className="px-2 py-1 text-center font-medium">着順</th>
            <th className="px-2 py-1 text-left font-medium">騎手</th>
            <th className="px-2 py-1 text-right font-medium">斤量</th>
            <th className="px-2 py-1 text-right font-medium">タイム</th>
            <th className="px-2 py-1 text-right font-medium">上3F</th>
            <th className="px-2 py-1 text-center font-medium">通過</th>
            <th className="px-2 py-1 text-center font-medium">人気</th>
            <th className="px-2 py-1 text-right font-medium">オッズ</th>
          </tr>
        </thead>
        <tbody>
          {records.map((r, i) => (
            <tr
              key={`${r.race_id}-${i}`}
              style={{ borderTop: "1px solid var(--border)" }}
            >
              <td className="px-2 py-1 tabular-nums">{shortDate(r.race_date)}</td>
              <td className="px-2 py-1">
                {(r.racecourse_name ?? "") +
                  (r.race_number ? `${r.race_number}R` : "")}
              </td>
              <td className="px-2 py-1">
                <Link
                  href={`/races/${r.race_id}`}
                  style={{ color: "var(--accent)" }}
                >
                  {r.race_name ?? "---"}
                </Link>
                {r.graded_race && (
                  <span
                    className="ml-1 rounded px-1 text-[10px] font-bold"
                    style={{
                      backgroundColor: "rgba(234,179,8,0.18)",
                      color: "#eab308",
                    }}
                  >
                    {r.graded_race}
                  </span>
                )}
              </td>
              <td className="px-2 py-1" style={{ color: "var(--text-secondary)" }}>
                {(r.surface ?? "") + (r.distance_m ?? "")}
                {r.track_condition ? ` ${r.track_condition}` : ""}
              </td>
              <td
                className="px-2 py-1 text-center font-semibold tabular-nums"
                style={{ color: finishColor(r.finish_position) }}
              >
                {r.finish_position ?? r.finish_note ?? "-"}
                {r.field_size ? (
                  <span
                    className="text-[10px]"
                    style={{ color: "var(--text-secondary)" }}
                  >
                    /{r.field_size}
                  </span>
                ) : null}
              </td>
              <td className="px-2 py-1" style={{ color: "var(--text-secondary)" }}>
                {r.jockey_name ?? "---"}
              </td>
              <td
                className="px-2 py-1 text-right tabular-nums"
                style={{ color: "var(--text-secondary)" }}
              >
                {r.weight_carried_kg !== null
                  ? Number(r.weight_carried_kg)
                  : "--"}
              </td>
              <td
                className="px-2 py-1 text-right tabular-nums"
                style={{ color: "var(--text-secondary)" }}
              >
                {formatTime(r.total_time_tenths)}
              </td>
              <td
                className="px-2 py-1 text-right tabular-nums"
                style={{ color: "var(--text-secondary)" }}
              >
                {r.last_3f_time !== null ? Number(r.last_3f_time).toFixed(1) : "--"}
              </td>
              <td
                className="px-2 py-1 text-center tabular-nums"
                style={{ color: "var(--text-secondary)" }}
              >
                {r.corner_passing ?? "-"}
              </td>
              <td
                className="px-2 py-1 text-center tabular-nums"
                style={{ color: "var(--text-secondary)" }}
              >
                {r.win_favorite ?? "-"}
              </td>
              <td
                className="px-2 py-1 text-right tabular-nums"
                style={{ color: "var(--text-secondary)" }}
              >
                {r.win_odds !== null ? Number(r.win_odds).toFixed(1) : "--"}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export default function EntryTable({
  entries,
  isUpcoming,
  pastByHorse,
  pedigreeByHorse,
}: Props) {
  const hasPast = !!pastByHorse && Object.keys(pastByHorse).length > 0;
  const [expanded, setExpanded] = useState<Set<string>>(new Set());
  const [allOpen, setAllOpen] = useState(false);

  const toggle = (horseId: string) =>
    setExpanded((prev) => {
      const next = new Set(prev);
      if (next.has(horseId)) next.delete(horseId);
      else next.add(horseId);
      return next;
    });

  const toggleAll = () => {
    if (allOpen) {
      setExpanded(new Set());
      setAllOpen(false);
    } else {
      setExpanded(new Set(entries.map((e) => e.horse.id)));
      setAllOpen(true);
    }
  };

  const colCount = (hasPast ? 1 : 0) + 7 + (isUpcoming ? 2 : 6);

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
        {hasPast && (
          <button
            onClick={toggleAll}
            className="ml-auto rounded-full px-3 py-1 text-xs font-medium"
            style={{
              backgroundColor: "var(--bg-elevated)",
              color: "var(--text-secondary)",
              border: "1px solid var(--border)",
            }}
          >
            {allOpen ? "馬柱を全て閉じる" : "馬柱を全て開く"}
          </button>
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
              {hasPast && <th className="px-2 py-2">馬柱</th>}
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
            {sorted.map((e) => {
              const records = pastByHorse?.[e.horse.id];
              const isOpen = expanded.has(e.horse.id);
              return (
                <Fragment key={e.id}>
                  <tr
                    style={{
                      borderBottom: isOpen
                        ? "none"
                        : "1px solid var(--border)",
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
                    {hasPast && (
                      <td className="px-2 py-2 text-center">
                        {records && records.length > 0 ? (
                          <button
                            onClick={() => toggle(e.horse.id)}
                            className="inline-flex h-6 w-6 items-center justify-center rounded text-xs"
                            style={{
                              backgroundColor: isOpen
                                ? "var(--accent)"
                                : "var(--bg-elevated)",
                              color: isOpen ? "#fff" : "var(--text-secondary)",
                              border: "1px solid var(--border)",
                            }}
                            aria-label="過去走を表示"
                          >
                            {isOpen ? "▲" : "▼"}
                          </button>
                        ) : (
                          <span style={{ color: "var(--text-secondary)" }}>
                            -
                          </span>
                        )}
                      </td>
                    )}
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
                      {(() => {
                        const ped = pedigreeByHorse?.[e.horse.id];
                        if (!ped || (!ped.sire && !ped.broodmare_sire))
                          return null;
                        return (
                          <div
                            className="mt-0.5 text-[11px] leading-tight"
                            style={{ color: "var(--text-muted)" }}
                          >
                            {ped.sire ?? "—"}
                            {ped.broodmare_sire ? ` / 母父 ${ped.broodmare_sire}` : ""}
                          </div>
                        );
                      })()}
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
                              e.horse_weight_diff !== null &&
                              e.horse_weight_diff > 0
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
                  {hasPast && isOpen && (
                    <tr style={{ borderBottom: "1px solid var(--border)" }}>
                      <td
                        colSpan={colCount}
                        style={{ backgroundColor: "var(--bg-elevated)" }}
                      >
                        <PastRacesPanel records={records ?? []} />
                      </td>
                    </tr>
                  )}
                </Fragment>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
