"use client";

import { useEffect, useState, useCallback } from "react";
import Link from "next/link";
import {
  fetchResults,
  fetchResultsSummary,
  fetchResultsRacecourses,
  fetchResultsCalendar,
  fetchLatestResultDate,
  type RaceResultWithAI,
  type ResultsSummary,
  type ResultsCalendarDay,
} from "@/lib/api";

const BET_TYPE_LABELS: Record<string, string> = {
  tansho: "単勝",
  fukusho: "複勝",
  umaren: "馬連",
  umatan: "馬単",
  wide: "ワイド",
  sanrenpuku: "3連複",
  sanrentan: "3連単",
};

const BET_TYPE_ORDER = [
  "tansho",
  "fukusho",
  "umaren",
  "umatan",
  "wide",
  "sanrenpuku",
  "sanrentan",
];

const DAY_LABELS = ["日", "月", "火", "水", "木", "金", "土"];
const POSITION_MARKS = ["", "1着", "2着", "3着"];

function formatYM(year: number, month: number): string {
  return `${year}-${String(month).padStart(2, "0")}`;
}

export default function ResultsPage() {
  const now = new Date();
  const [calYear, setCalYear] = useState(now.getFullYear());
  const [calMonth, setCalMonth] = useState(now.getMonth() + 1);
  const [calDays, setCalDays] = useState<ResultsCalendarDay[]>([]);
  const [calLoading, setCalLoading] = useState(false);

  const [selectedDate, setSelectedDate] = useState<string | null>(null);
  const [racecourses, setRacecourses] = useState<string[]>([]);
  const [selectedRC, setSelectedRC] = useState<string | null>(null);
  const [items, setItems] = useState<RaceResultWithAI[]>([]);
  const [summary, setSummary] = useState<ResultsSummary | null>(null);
  const [loading, setLoading] = useState(false);
  const [initialized, setInitialized] = useState(false);

  const ym = formatYM(calYear, calMonth);

  // On mount: jump to latest result date
  useEffect(() => {
    let cancelled = false;
    fetchLatestResultDate()
      .then((res) => {
        if (cancelled) return;
        if (res.latest_date) {
          const [y, m, d] = res.latest_date.split("-").map(Number);
          setCalYear(y);
          setCalMonth(m);
          setSelectedDate(res.latest_date);
        }
        setInitialized(true);
      })
      .catch(() => {
        if (!cancelled) setInitialized(true);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  // Load calendar when month changes
  useEffect(() => {
    if (!initialized) return;
    setCalLoading(true);
    fetchResultsCalendar(ym)
      .then((res) => setCalDays(res.days))
      .catch(() => setCalDays([]))
      .finally(() => setCalLoading(false));
  }, [ym, initialized]);

  // Load summary when month changes
  useEffect(() => {
    if (!initialized) return;
    fetchResultsSummary(ym).then(setSummary).catch(() => setSummary(null));
  }, [ym, initialized]);

  // Load racecourses when date changes
  useEffect(() => {
    if (!selectedDate) {
      setRacecourses([]);
      return;
    }
    fetchResultsRacecourses(selectedDate)
      .then((res) => setRacecourses(res.racecourses))
      .catch(() => setRacecourses([]));
  }, [selectedDate]);

  // Reset RC selection when date changes
  useEffect(() => {
    setSelectedRC(null);
  }, [selectedDate]);

  // Load results when date or racecourse changes
  const loadResults = useCallback(async () => {
    if (!selectedDate) {
      setItems([]);
      return;
    }
    setLoading(true);
    try {
      const res = await fetchResults({
        date: selectedDate,
        racecourse: selectedRC ?? undefined,
      });
      setItems(res.items);
    } catch {
      setItems([]);
    } finally {
      setLoading(false);
    }
  }, [selectedDate, selectedRC]);

  useEffect(() => {
    loadResults();
  }, [loadResults]);

  // Calendar navigation
  function goMonth(delta: number) {
    const d = new Date(calYear, calMonth - 1 + delta, 1);
    setCalYear(d.getFullYear());
    setCalMonth(d.getMonth() + 1);
  }

  function onDayClick(dateStr: string) {
    setSelectedDate(dateStr);
  }

  // Calendar rendering data
  const firstDay = new Date(calYear, calMonth - 1, 1);
  const startDow = firstDay.getDay();
  const daysInMonth = new Date(calYear, calMonth, 0).getDate();

  const raceCountMap = new Map<number, number>();
  for (const d of calDays) {
    const dayNum = parseInt(d.date.split("-")[2], 10);
    raceCountMap.set(dayNum, d.race_count);
  }

  const cells: (number | null)[] = [];
  for (let i = 0; i < startDow; i++) cells.push(null);
  for (let d = 1; d <= daysInMonth; d++) cells.push(d);
  while (cells.length % 7 !== 0) cells.push(null);

  const selectedDay = selectedDate
    ? parseInt(selectedDate.split("-")[2], 10)
    : null;
  const selectedDateMonth = selectedDate
    ? selectedDate.substring(0, 7)
    : null;

  return (
    <div className="space-y-6">
      <h1
        className="text-2xl font-bold"
        style={{ color: "var(--text-primary)" }}
      >
        AI予想成績
      </h1>

      <div className="grid gap-6 lg:grid-cols-[280px_1fr] min-w-0">
        {/* Left: Calendar + Summary */}
        <div className="space-y-4">
          {/* Calendar */}
          <div className="glass-card p-4">
            <div className="mb-3 flex items-center justify-between">
              <button
                type="button"
                onClick={() => goMonth(-1)}
                className="cursor-pointer rounded-md p-1 transition-colors"
                style={{ color: "var(--text-secondary)" }}
                aria-label="前月"
              >
                <svg
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth={2}
                  className="h-4 w-4"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    d="M15 19l-7-7 7-7"
                  />
                </svg>
              </button>
              <div
                className="text-sm font-semibold"
                style={{ color: "var(--text-primary)" }}
              >
                {calYear}年{calMonth}月
              </div>
              <button
                type="button"
                onClick={() => goMonth(1)}
                className="cursor-pointer rounded-md p-1 transition-colors"
                style={{ color: "var(--text-secondary)" }}
                aria-label="次月"
              >
                <svg
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth={2}
                  className="h-4 w-4"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    d="M9 5l7 7-7 7"
                  />
                </svg>
              </button>
            </div>

            {calLoading ? (
              <div
                className="py-4 text-center text-xs"
                style={{ color: "var(--text-muted)" }}
              >
                読み込み中...
              </div>
            ) : (
              <>
                <div className="grid grid-cols-7 gap-1 text-center text-xs">
                  {DAY_LABELS.map((label, i) => (
                    <div
                      key={label}
                      className="py-1 font-medium"
                      style={{
                        color:
                          i === 0
                            ? "var(--red)"
                            : i === 6
                              ? "var(--accent)"
                              : "var(--text-secondary)",
                      }}
                    >
                      {label}
                    </div>
                  ))}

                  {cells.map((day, idx) => {
                    if (day === null) {
                      return <div key={`e-${idx}`} />;
                    }
                    const count = raceCountMap.get(day) ?? 0;
                    const hasRaces = count > 0;
                    const isSelected =
                      selectedDateMonth === ym && selectedDay === day;

                    return (
                      <button
                        key={day}
                        type="button"
                        onClick={() =>
                          hasRaces &&
                          onDayClick(
                            `${calYear}-${String(calMonth).padStart(2, "0")}-${String(day).padStart(2, "0")}`,
                          )
                        }
                        disabled={!hasRaces}
                        className="relative rounded-md py-1.5 transition-colors"
                        style={{
                          backgroundColor: isSelected
                            ? "var(--accent)"
                            : hasRaces
                              ? "var(--bg-elevated)"
                              : "transparent",
                          color: isSelected
                            ? "#fff"
                            : hasRaces
                              ? "var(--text-primary)"
                              : "var(--text-muted)",
                          cursor: hasRaces ? "pointer" : "default",
                        }}
                      >
                        {day}
                        {hasRaces && (
                          <span
                            className="absolute -top-0.5 -right-0.5 flex h-3.5 w-3.5 items-center justify-center rounded-full text-[9px] font-bold"
                            style={{
                              backgroundColor: isSelected
                                ? "#fff"
                                : "var(--accent)",
                              color: isSelected ? "var(--accent)" : "#fff",
                            }}
                          >
                            {count > 99 ? "+" : count}
                          </span>
                        )}
                      </button>
                    );
                  })}
                </div>

                <div
                  className="mt-2 text-center text-xs"
                  style={{ color: "var(--text-muted)" }}
                >
                  {calDays.length > 0
                    ? `${calDays.length}開催日 / ${calDays.reduce((s, d) => s + d.race_count, 0)}レース`
                    : "この月の確定結果はありません"}
                </div>
              </>
            )}
          </div>

          {/* Monthly summary cards */}
          {summary && summary.total_races > 0 && (
            <div className="glass-card p-4">
              <div
                className="mb-2 text-xs font-semibold"
                style={{ color: "var(--text-secondary)" }}
              >
                {calYear}年{calMonth}月 AI的中率
              </div>
              <div className="grid grid-cols-3 sm:grid-cols-4 gap-2">
                {BET_TYPE_ORDER.map((key) => {
                  const hr = summary.hit_rates[key];
                  if (!hr) return null;
                  return (
                    <div key={key} className="text-center">
                      <div
                        className="text-[10px] font-medium"
                        style={{ color: "var(--text-muted)" }}
                      >
                        {BET_TYPE_LABELS[key]}
                      </div>
                      <div
                        className="text-sm font-bold tabular-nums"
                        style={{
                          color:
                            hr.rate > 0
                              ? "var(--accent)"
                              : "var(--text-muted)",
                        }}
                      >
                        {hr.rate}%
                      </div>
                      <div
                        className="text-[10px] tabular-nums"
                        style={{ color: "var(--text-muted)" }}
                      >
                        {hr.hits}/{hr.total}
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          )}
        </div>

        {/* Right: Results */}
        <div className="space-y-4 min-w-0">
          {/* Racecourse tabs */}
          {selectedDate && racecourses.length > 0 && (
            <div className="flex gap-1 flex-wrap">
              <button
                type="button"
                onClick={() => {
                  setSelectedRC(null);
                }}
                className="cursor-pointer rounded-lg px-3 py-1.5 text-sm font-medium transition-colors"
                style={{
                  backgroundColor:
                    selectedRC === null
                      ? "var(--accent-muted)"
                      : "var(--bg-elevated)",
                  color:
                    selectedRC === null
                      ? "var(--accent-hover)"
                      : "var(--text-secondary)",
                }}
              >
                全場
              </button>
              {racecourses.map((rc) => (
                <button
                  key={rc}
                  type="button"
                  onClick={() => setSelectedRC(rc)}
                  className="cursor-pointer rounded-lg px-3 py-1.5 text-sm font-medium transition-colors"
                  style={{
                    backgroundColor:
                      selectedRC === rc
                        ? "var(--accent-muted)"
                        : "var(--bg-elevated)",
                    color:
                      selectedRC === rc
                        ? "var(--accent-hover)"
                        : "var(--text-secondary)",
                  }}
                >
                  {rc}
                </button>
              ))}
            </div>
          )}

          {/* Results table */}
          <div className="glass-card overflow-hidden">
            <div
              className="px-4 py-3"
              style={{ borderBottom: "1px solid var(--border)" }}
            >
              <h2
                className="text-base font-semibold"
                style={{ color: "var(--text-primary)" }}
              >
                {selectedDate
                  ? (() => {
                      const [, m, d] = selectedDate.split("-").map(Number);
                      return `${m}月${d}日のレース結果`;
                    })()
                  : "レース結果"}
                {selectedRC && (
                  <span
                    className="ml-2 text-sm font-normal"
                    style={{ color: "var(--text-muted)" }}
                  >
                    — {selectedRC}
                  </span>
                )}
              </h2>
            </div>

            {!selectedDate ? (
              <div
                className="p-8 text-center text-sm"
                style={{ color: "var(--text-muted)" }}
              >
                カレンダーから日付を選択してください
              </div>
            ) : loading ? (
              <div
                className="p-8 text-center"
                style={{ color: "var(--text-muted)" }}
              >
                読み込み中...
              </div>
            ) : items.length === 0 ? (
              <div
                className="p-8 text-center text-sm"
                style={{ color: "var(--text-muted)" }}
              >
                この日に確定済みレースはありません
              </div>
            ) : (
              <>
                {/* Mobile: card layout */}
                <div className="md:hidden">
                  {items.map((item) => (
                    <div
                      key={item.race_id_str}
                      className="px-3 py-3"
                      style={{ borderBottom: "1px solid var(--border)" }}
                    >
                      <div className="flex items-start justify-between gap-2">
                        <div className="min-w-0 flex-1">
                          <Link
                            href={`/races/${item.race_id_str}`}
                            className="hover:underline"
                            style={{ color: "var(--accent)" }}
                          >
                            <span
                              className="font-medium tabular-nums"
                              style={{ color: "var(--text-secondary)" }}
                            >
                              {item.race_number ?? "-"}R
                            </span>
                            <span className="ml-1 font-medium">
                              {item.racecourse_name ?? ""}
                            </span>
                            {item.race_name && (
                              <span
                                className="ml-1 text-xs"
                                style={{ color: "var(--text-muted)" }}
                              >
                                {item.race_name}
                              </span>
                            )}
                          </Link>
                          {item.surface && item.distance_m && (
                            <div
                              className="text-xs"
                              style={{ color: "var(--text-muted)" }}
                            >
                              {item.surface}{item.distance_m}m
                            </div>
                          )}
                        </div>
                        <div className="shrink-0">
                          {item.ai_prediction ? (
                            <HitBadges ai={item.ai_prediction} />
                          ) : (
                            <span
                              className="text-xs"
                              style={{ color: "var(--text-muted)" }}
                            >
                              ---
                            </span>
                          )}
                        </div>
                      </div>

                      <div className="mt-2 grid grid-cols-2 gap-2">
                        {/* 結果 TOP3 */}
                        <div>
                          <div
                            className="mb-0.5 text-[10px] font-medium"
                            style={{ color: "var(--text-muted)" }}
                          >
                            結果
                          </div>
                          {item.result_top3.length > 0 ? (
                            <div className="flex flex-col gap-0.5">
                              {item.result_top3.map((r) => (
                                <span
                                  key={r.finish_position}
                                  className="text-xs truncate"
                                  style={{ color: "var(--text-secondary)" }}
                                >
                                  <span
                                    className="font-medium tabular-nums mr-0.5"
                                    style={{
                                      color:
                                        r.finish_position === 1
                                          ? "var(--yellow)"
                                          : "var(--text-muted)",
                                    }}
                                  >
                                    {r.finish_position}.
                                  </span>
                                  {r.horse_name}
                                </span>
                              ))}
                            </div>
                          ) : (
                            <span
                              className="text-xs"
                              style={{ color: "var(--text-muted)" }}
                            >
                              ---
                            </span>
                          )}
                        </div>

                        {/* AI予想 TOP3 */}
                        <div>
                          <div
                            className="mb-0.5 text-[10px] font-medium"
                            style={{ color: "var(--text-muted)" }}
                          >
                            AI予想
                          </div>
                          {item.ai_prediction ? (
                            <div className="flex flex-col gap-0.5">
                              {item.ai_prediction.predicted_top3.map((p) => (
                                <span
                                  key={p.rank}
                                  className="text-xs truncate"
                                  style={{ color: "var(--text-secondary)" }}
                                >
                                  <span
                                    className="font-medium tabular-nums mr-0.5"
                                    style={{ color: "var(--text-muted)" }}
                                  >
                                    {p.rank}.
                                  </span>
                                  {p.horse_name}
                                </span>
                              ))}
                            </div>
                          ) : (
                            <span
                              className="text-xs"
                              style={{ color: "var(--text-muted)" }}
                            >
                              予想なし
                            </span>
                          )}
                        </div>
                      </div>
                    </div>
                  ))}
                </div>

                {/* Desktop: table layout */}
                <div className="hidden md:block overflow-x-auto">
                  <table className="w-full text-sm whitespace-nowrap">
                    <thead>
                      <tr
                        className="text-left text-xs font-medium"
                        style={{
                          backgroundColor: "var(--bg-elevated)",
                          color: "var(--text-secondary)",
                        }}
                      >
                        <th className="px-3 py-2">R</th>
                        <th className="px-3 py-2">レース</th>
                        <th className="px-3 py-2">結果 TOP3</th>
                        <th className="px-3 py-2">AI予想 TOP3</th>
                        <th className="px-3 py-2 text-center">的中</th>
                      </tr>
                    </thead>
                    <tbody>
                      {items.map((item) => (
                        <tr
                          key={item.race_id_str}
                          style={{ borderBottom: "1px solid var(--border)" }}
                        >
                          <td
                            className="px-3 py-2 font-medium tabular-nums"
                            style={{ color: "var(--text-secondary)" }}
                          >
                            {item.race_number ?? "-"}
                          </td>
                          <td className="px-3 py-2">
                            <Link
                              href={`/races/${item.race_id_str}`}
                              className="hover:underline"
                              style={{ color: "var(--accent)" }}
                            >
                              <span className="font-medium">
                                {item.racecourse_name ?? ""}
                              </span>
                              {item.race_name && (
                                <span
                                  className="ml-1 text-xs"
                                  style={{ color: "var(--text-muted)" }}
                                >
                                  {item.race_name}
                                </span>
                              )}
                            </Link>
                            {item.surface && item.distance_m && (
                              <div
                                className="text-xs"
                                style={{ color: "var(--text-muted)" }}
                              >
                                {item.surface}{item.distance_m}m
                              </div>
                            )}
                          </td>
                          <td className="px-3 py-2">
                            {item.result_top3.length > 0 ? (
                              <div className="flex flex-col gap-0.5">
                                {item.result_top3.map((r) => (
                                  <span
                                    key={r.finish_position}
                                    className="text-xs"
                                    style={{ color: "var(--text-secondary)" }}
                                  >
                                    <span
                                      className="inline-block w-7 text-right font-medium tabular-nums mr-1"
                                      style={{
                                        color:
                                          r.finish_position === 1
                                            ? "var(--yellow)"
                                            : r.finish_position === 2
                                              ? "var(--text-secondary)"
                                              : "var(--text-muted)",
                                      }}
                                    >
                                      {POSITION_MARKS[r.finish_position] ??
                                        `${r.finish_position}着`}
                                    </span>
                                    {r.horse_name}
                                    {r.win_odds != null && (
                                      <span
                                        className="ml-1"
                                        style={{ color: "var(--text-muted)" }}
                                      >
                                        ({r.win_odds.toFixed(1)})
                                      </span>
                                    )}
                                  </span>
                                ))}
                              </div>
                            ) : (
                              <span
                                className="text-xs"
                                style={{ color: "var(--text-muted)" }}
                              >
                                ---
                              </span>
                            )}
                          </td>
                          <td className="px-3 py-2">
                            {item.ai_prediction ? (
                              <div className="flex flex-col gap-0.5">
                                {item.ai_prediction.predicted_top3.map((p) => (
                                  <span
                                    key={p.rank}
                                    className="text-xs"
                                    style={{ color: "var(--text-secondary)" }}
                                  >
                                    <span
                                      className="inline-block w-4 text-right font-medium tabular-nums mr-1"
                                      style={{ color: "var(--text-muted)" }}
                                    >
                                      {p.rank}.
                                    </span>
                                    {p.horse_name}
                                  </span>
                                ))}
                              </div>
                            ) : (
                              <span
                                className="text-xs"
                                style={{ color: "var(--text-muted)" }}
                              >
                                予想なし
                              </span>
                            )}
                          </td>
                          <td className="px-3 py-2 text-center">
                            {item.ai_prediction ? (
                              <HitBadges ai={item.ai_prediction} />
                            ) : (
                              <span
                                className="text-xs"
                                style={{ color: "var(--text-muted)" }}
                              >
                                ---
                              </span>
                            )}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

/** Compact hit badges showing which bet types hit */
function HitBadges({
  ai,
}: {
  ai: NonNullable<RaceResultWithAI["ai_prediction"]>;
}) {
  const badges: { label: string; hit: boolean }[] = [
    { label: "単", hit: ai.tansho_hit },
    { label: "複", hit: ai.fukusho_hit },
    { label: "連", hit: ai.umaren_hit },
    { label: "馬単", hit: ai.umatan_hit },
    { label: "W", hit: ai.wide_hit },
    { label: "3複", hit: ai.sanrenpuku_hit },
    { label: "3単", hit: ai.sanrentan_hit },
  ];

  const anyHit = badges.some((b) => b.hit);
  if (!anyHit) {
    return (
      <span className="text-xs" style={{ color: "var(--text-muted)" }}>
        ×
      </span>
    );
  }

  return (
    <div className="flex flex-wrap justify-center gap-1">
      {badges
        .filter((b) => b.hit)
        .map((b) => (
          <span
            key={b.label}
            className="inline-block rounded px-1.5 py-0.5 text-xs font-medium"
            style={{
              backgroundColor: "rgba(63,185,80,0.15)",
              color: "var(--green)",
            }}
          >
            {b.label}○
          </span>
        ))}
    </div>
  );
}
