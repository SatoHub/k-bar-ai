"use client";

import { useEffect, useState } from "react";

type Props = {
  racecourses: string[];
  initialYearMonth?: string;
  initialWeek?: string;
  initialDate?: string;
  initialRacecourse?: string;
  onFilter: (filters: {
    date?: string;
    year_month?: string;
    week?: string;
    racecourse?: string;
  }) => void;
};

function getCurrentYearMonth(): string {
  const now = new Date();
  return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}`;
}

function generateYearMonthOptions(): { value: string; label: string }[] {
  const options: { value: string; label: string }[] = [];
  const now = new Date();
  // Show 2 years back + 2 months forward
  for (let offset = -24; offset <= 2; offset++) {
    const d = new Date(now.getFullYear(), now.getMonth() + offset, 1);
    const value = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`;
    const label = `${d.getFullYear()}年${d.getMonth() + 1}月`;
    options.push({ value, label });
  }
  return options.reverse();
}

const inputStyle = {
  backgroundColor: "var(--bg-elevated)",
  border: "1px solid var(--border-light)",
  color: "var(--text-primary)",
  transition: "border-color 200ms ease-out",
};

export default function RaceFilters({
  racecourses,
  initialYearMonth = "",
  initialWeek = "",
  initialDate = "",
  initialRacecourse = "",
  onFilter,
}: Props) {
  const [yearMonth, setYearMonth] = useState(initialYearMonth);
  const [week, setWeek] = useState(initialWeek);
  const [date, setDate] = useState(initialDate);
  const [racecourse, setRacecourse] = useState(initialRacecourse);

  // Sync local state when URL params change (e.g. calendar day click)
  useEffect(() => { setYearMonth(initialYearMonth); }, [initialYearMonth]);
  useEffect(() => { setWeek(initialWeek); }, [initialWeek]);
  useEffect(() => { setDate(initialDate); }, [initialDate]);
  useEffect(() => { setRacecourse(initialRacecourse); }, [initialRacecourse]);

  const yearMonthOptions = generateYearMonthOptions();

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    onFilter({
      date: date || undefined,
      year_month: !date ? yearMonth || undefined : undefined,
      week: !date && yearMonth && week ? week : undefined,
      racecourse: racecourse || undefined,
    });
  }

  function handleClear() {
    setYearMonth("");
    setWeek("");
    setDate("");
    setRacecourse("");
    onFilter({});
  }

  return (
    <form
      onSubmit={handleSubmit}
      className="glass-card p-4"
    >
      <div className="grid grid-cols-2 gap-3 sm:flex sm:flex-wrap sm:items-end">
        {/* Year-Month select */}
        <div className="min-w-0 flex flex-col gap-1">
          <label
            htmlFor="filter-year-month"
            className="text-xs sm:text-sm font-medium"
            style={{ color: "var(--text-secondary)" }}
          >
            年月
          </label>
          <select
            id="filter-year-month"
            value={yearMonth}
            onChange={(e) => {
              setYearMonth(e.target.value);
              if (!e.target.value) setWeek("");
            }}
            className="w-full rounded-md px-2 py-2 text-sm focus:outline-none sm:w-auto sm:px-3"
            style={inputStyle}
            disabled={!!date}
          >
            <option value="">すべて</option>
            {yearMonthOptions.map((opt) => (
              <option key={opt.value} value={opt.value}>
                {opt.label}
              </option>
            ))}
          </select>
        </div>

        {/* Week select */}
        <div className="min-w-0 flex flex-col gap-1">
          <label
            htmlFor="filter-week"
            className="text-xs sm:text-sm font-medium"
            style={{ color: "var(--text-secondary)" }}
          >
            週
          </label>
          <select
            id="filter-week"
            value={week}
            onChange={(e) => setWeek(e.target.value)}
            className="w-full rounded-md px-2 py-2 text-sm focus:outline-none sm:w-auto sm:px-3"
            style={inputStyle}
            disabled={!yearMonth || !!date}
          >
            <option value="">全週</option>
            <option value="1">第1週</option>
            <option value="2">第2週</option>
            <option value="3">第3週</option>
            <option value="4">第4週</option>
            <option value="5">第5週</option>
          </select>
        </div>

        {/* Specific date */}
        <div className="col-span-2 min-w-0 flex flex-col gap-1 sm:col-span-1">
          <label
            htmlFor="filter-date"
            className="text-xs sm:text-sm font-medium"
            style={{ color: "var(--text-secondary)" }}
          >
            日付指定
          </label>
          <input
            id="filter-date"
            type="date"
            value={date}
            onChange={(e) => setDate(e.target.value)}
            className="w-full rounded-md px-2 py-2 text-sm focus:outline-none sm:w-auto sm:px-3"
            style={inputStyle}
          />
        </div>

        {/* Racecourse */}
        <div className="col-span-2 min-w-0 flex flex-col gap-1 sm:col-span-1">
          <label
            htmlFor="filter-racecourse"
            className="text-xs sm:text-sm font-medium"
            style={{ color: "var(--text-secondary)" }}
          >
            競馬場
          </label>
          <select
            id="filter-racecourse"
            value={racecourse}
            onChange={(e) => setRacecourse(e.target.value)}
            className="w-full rounded-md px-2 py-2 text-sm focus:outline-none sm:w-auto sm:px-3"
            style={inputStyle}
          >
            <option value="">すべて</option>
            {racecourses.map((rc) => (
              <option key={rc} value={rc}>
                {rc}
              </option>
            ))}
          </select>
        </div>

        {/* Buttons */}
        <div className="col-span-2 flex gap-2 sm:col-span-1">
          <button
            type="submit"
            className="flex-1 cursor-pointer rounded-md px-4 py-2 text-sm font-medium sm:flex-none"
            style={{
              backgroundColor: "var(--accent)",
              color: "#fff",
              transition: "background-color 200ms ease-out",
            }}
            onMouseEnter={(e) =>
              (e.currentTarget.style.backgroundColor = "var(--accent-hover)")
            }
            onMouseLeave={(e) =>
              (e.currentTarget.style.backgroundColor = "var(--accent)")
            }
          >
            検索
          </button>
          <button
            type="button"
            onClick={handleClear}
            className="flex-1 cursor-pointer rounded-md px-4 py-2 text-sm font-medium sm:flex-none"
            style={{
              backgroundColor: "transparent",
              border: "1px solid var(--border-light)",
              color: "var(--text-secondary)",
              transition: "background-color 200ms ease-out, color 200ms ease-out",
            }}
            onMouseEnter={(e) => {
              e.currentTarget.style.backgroundColor = "var(--bg-elevated)";
              e.currentTarget.style.color = "var(--text-primary)";
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.backgroundColor = "transparent";
              e.currentTarget.style.color = "var(--text-secondary)";
            }}
          >
            クリア
          </button>
        </div>
      </div>
    </form>
  );
}
