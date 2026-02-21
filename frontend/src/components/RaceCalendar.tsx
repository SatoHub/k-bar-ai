"use client";

import { useEffect, useState } from "react";
import { fetchCalendar, type CalendarDay } from "@/lib/api";

type Props = {
  yearMonth: string; // "YYYY-MM"
  onDayClick: (date: string) => void;
  onMonthChange?: (yearMonth: string) => void;
  selectedDate?: string;
};

const DAY_LABELS = ["日", "月", "火", "水", "木", "金", "土"];

function shiftMonth(ym: string, delta: number): string {
  const [y, m] = ym.split("-").map(Number);
  const d = new Date(y, m - 1 + delta, 1);
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`;
}

export default function RaceCalendar({
  yearMonth,
  onDayClick,
  onMonthChange,
  selectedDate,
}: Props) {
  const [currentYM, setCurrentYM] = useState(yearMonth);
  const [days, setDays] = useState<CalendarDay[]>([]);
  const [loading, setLoading] = useState(false);

  // Sync when parent changes yearMonth
  useEffect(() => {
    setCurrentYM(yearMonth);
  }, [yearMonth]);

  useEffect(() => {
    if (!currentYM) return;
    setLoading(true);
    fetchCalendar(currentYM)
      .then((res) => setDays(res.days))
      .catch(() => setDays([]))
      .finally(() => setLoading(false));
  }, [currentYM]);

  const [yearStr, monthStr] = currentYM.split("-");
  const year = parseInt(yearStr, 10);
  const month = parseInt(monthStr, 10);
  const firstDay = new Date(year, month - 1, 1);
  const startDow = firstDay.getDay();
  const daysInMonth = new Date(year, month, 0).getDate();

  const raceCountMap = new Map<number, number>();
  for (const d of days) {
    const dayNum = parseInt(d.date.split("-")[2], 10);
    raceCountMap.set(dayNum, d.race_count);
  }

  const totalRaces = days.reduce((sum, d) => sum + d.race_count, 0);

  const cells: (number | null)[] = [];
  for (let i = 0; i < startDow; i++) cells.push(null);
  for (let d = 1; d <= daysInMonth; d++) cells.push(d);
  while (cells.length % 7 !== 0) cells.push(null);

  function goMonth(delta: number) {
    const next = shiftMonth(currentYM, delta);
    setCurrentYM(next);
    onMonthChange?.(next);
  }

  return (
    <div className="glass-card p-4">
      {/* Month navigation */}
      <div className="mb-3 flex items-center justify-between">
        <button
          type="button"
          onClick={() => goMonth(-1)}
          className="rounded-md p-1 transition-colors cursor-pointer"
          style={{ color: "var(--text-secondary)" }}
          onMouseEnter={(e) =>
            (e.currentTarget.style.color = "var(--text-primary)")
          }
          onMouseLeave={(e) =>
            (e.currentTarget.style.color = "var(--text-secondary)")
          }
          aria-label="前月"
        >
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} className="h-4 w-4">
            <path strokeLinecap="round" strokeLinejoin="round" d="M15 19l-7-7 7-7" />
          </svg>
        </button>
        <div className="text-sm font-semibold" style={{ color: "var(--text-primary)" }}>
          {year}年{month}月
        </div>
        <button
          type="button"
          onClick={() => goMonth(1)}
          className="rounded-md p-1 transition-colors cursor-pointer"
          style={{ color: "var(--text-secondary)" }}
          onMouseEnter={(e) =>
            (e.currentTarget.style.color = "var(--text-primary)")
          }
          onMouseLeave={(e) =>
            (e.currentTarget.style.color = "var(--text-secondary)")
          }
          aria-label="次月"
        >
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} className="h-4 w-4">
            <path strokeLinecap="round" strokeLinejoin="round" d="M9 5l7 7-7 7" />
          </svg>
        </button>
      </div>

      {loading ? (
        <div className="py-4 text-center text-xs" style={{ color: "var(--text-muted)" }}>
          読み込み中...
        </div>
      ) : (
        <>
          <div className="grid grid-cols-7 gap-1 text-center text-xs">
            {/* Header */}
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

            {/* Day cells */}
            {cells.map((day, idx) => {
              if (day === null) {
                return <div key={`empty-${idx}`} />;
              }

              const dateStr = `${yearStr}-${monthStr}-${String(day).padStart(2, "0")}`;
              const count = raceCountMap.get(day) ?? 0;
              const isSelected = selectedDate === dateStr;
              const hasRaces = count > 0;

              return (
                <button
                  key={day}
                  type="button"
                  onClick={() => hasRaces && onDayClick(dateStr)}
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
                        backgroundColor: isSelected ? "#fff" : "var(--accent)",
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

          {/* Summary */}
          <div
            className="mt-2 text-center text-xs"
            style={{ color: "var(--text-muted)" }}
          >
            {totalRaces > 0
              ? `${days.length}日間 / ${totalRaces}レース`
              : "この月のレースデータはありません"}
          </div>
        </>
      )}
    </div>
  );
}
