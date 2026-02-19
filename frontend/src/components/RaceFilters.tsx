"use client";

import { useState } from "react";

type Props = {
  racecourses: string[];
  initialDate?: string;
  initialRacecourse?: string;
  onFilter: (filters: { date?: string; racecourse?: string }) => void;
};

export default function RaceFilters({
  racecourses,
  initialDate = "",
  initialRacecourse = "",
  onFilter,
}: Props) {
  const [date, setDate] = useState(initialDate);
  const [racecourse, setRacecourse] = useState(initialRacecourse);

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    onFilter({
      date: date || undefined,
      racecourse: racecourse || undefined,
    });
  }

  function handleClear() {
    setDate("");
    setRacecourse("");
    onFilter({});
  }

  return (
    <form
      onSubmit={handleSubmit}
      className="glass-card flex flex-wrap items-end gap-3 p-4"
    >
      <div className="flex flex-col gap-1">
        <label
          htmlFor="filter-date"
          className="text-sm font-medium"
          style={{ color: "var(--text-secondary)" }}
        >
          日付
        </label>
        <input
          id="filter-date"
          type="date"
          value={date}
          onChange={(e) => setDate(e.target.value)}
          className="rounded-md px-3 py-2 text-sm focus:outline-none"
          style={{
            backgroundColor: "var(--bg-elevated)",
            border: "1px solid var(--border-light)",
            color: "var(--text-primary)",
            transition: "border-color 200ms ease-out",
          }}
          onFocus={(e) =>
            (e.currentTarget.style.borderColor = "var(--border-accent)")
          }
          onBlur={(e) =>
            (e.currentTarget.style.borderColor = "var(--border-light)")
          }
        />
      </div>

      <div className="flex flex-col gap-1">
        <label
          htmlFor="filter-racecourse"
          className="text-sm font-medium"
          style={{ color: "var(--text-secondary)" }}
        >
          競馬場
        </label>
        <select
          id="filter-racecourse"
          value={racecourse}
          onChange={(e) => setRacecourse(e.target.value)}
          className="rounded-md px-3 py-2 text-sm focus:outline-none"
          style={{
            backgroundColor: "var(--bg-elevated)",
            border: "1px solid var(--border-light)",
            color: "var(--text-primary)",
            transition: "border-color 200ms ease-out",
          }}
          onFocus={(e) =>
            (e.currentTarget.style.borderColor = "var(--border-accent)")
          }
          onBlur={(e) =>
            (e.currentTarget.style.borderColor = "var(--border-light)")
          }
        >
          <option value="">すべて</option>
          {racecourses.map((rc) => (
            <option key={rc} value={rc}>
              {rc}
            </option>
          ))}
        </select>
      </div>

      <button
        type="submit"
        className="cursor-pointer rounded-md px-4 py-2 text-sm font-medium"
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
        className="cursor-pointer rounded-md px-4 py-2 text-sm font-medium"
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
    </form>
  );
}
