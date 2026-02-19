"use client";

import { useEffect, useState } from "react";
import { fetchDataStatus, type DataStatus } from "@/lib/api";

function IconRace() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.5} className="h-5 w-5">
      <path strokeLinecap="round" strokeLinejoin="round" d="M3 3v1.5M3 21v-6m0 0 2.77-.693a9 9 0 0 1 6.208.682l.108.054a9 9 0 0 0 6.086.71l3.114-.732a48.524 48.524 0 0 1-.005-10.499l-3.11.732a9 9 0 0 1-6.085-.711l-.108-.054a9 9 0 0 0-6.208-.682L3 4.5M3 15V4.5" />
    </svg>
  );
}

function IconEntry() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.5} className="h-5 w-5">
      <path strokeLinecap="round" strokeLinejoin="round" d="M3.75 12h16.5m-16.5 3.75h16.5M3.75 19.5h16.5M5.625 4.5h12.75a1.875 1.875 0 0 1 0 3.75H5.625a1.875 1.875 0 0 1 0-3.75Z" />
    </svg>
  );
}

function IconHorse() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.5} className="h-5 w-5">
      <path strokeLinecap="round" strokeLinejoin="round" d="M12 2.25c-1.5 2-4 3.5-6 3.5v3.5c0 4.5 3 8.5 6 12.5 3-4 6-8 6-12.5v-3.5c-2 0-4.5-1.5-6-3.5Z" />
    </svg>
  );
}

function IconJockey() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.5} className="h-5 w-5">
      <path strokeLinecap="round" strokeLinejoin="round" d="M15.75 6a3.75 3.75 0 1 1-7.5 0 3.75 3.75 0 0 1 7.5 0ZM4.501 20.118a7.5 7.5 0 0 1 14.998 0A17.933 17.933 0 0 1 12 21.75c-2.676 0-5.216-.584-7.499-1.632Z" />
    </svg>
  );
}

function IconTrainer() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.5} className="h-5 w-5">
      <path strokeLinecap="round" strokeLinejoin="round" d="M4.26 10.147a60.438 60.438 0 0 0-.491 6.347A48.62 48.62 0 0 1 12 20.904a48.62 48.62 0 0 1 8.232-4.41 60.46 60.46 0 0 0-.491-6.347m-15.482 0a23.54 23.54 0 0 0-2.688 6.882 48.358 48.358 0 0 1 3.32-1.339A23.508 23.508 0 0 1 4.26 10.147Zm15.482 0a23.54 23.54 0 0 1 2.688 6.882 48.358 48.358 0 0 0-3.32-1.339 23.508 23.508 0 0 0 .632-5.543Zm-11.226-.01A23.451 23.451 0 0 1 12 5.904a23.451 23.451 0 0 1 3.484 4.233" />
    </svg>
  );
}

const STAT_ICONS = [IconRace, IconEntry, IconHorse, IconJockey, IconTrainer];

export default function DataStatusCard() {
  const [data, setData] = useState<DataStatus | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchDataStatus()
      .then(setData)
      .catch((e: Error) => setError(e.message));
  }, []);

  if (error) {
    return (
      <div className="glass-card p-6">
        <h2
          className="mb-4 text-lg font-semibold"
          style={{ color: "var(--text-primary)" }}
        >
          データ状況
        </h2>
        <p className="text-sm" style={{ color: "var(--red)" }}>
          データの取得に失敗しました: {error}
        </p>
      </div>
    );
  }

  if (!data) {
    return (
      <div className="glass-card p-6 animate-pulse">
        <h2
          className="mb-4 text-lg font-semibold"
          style={{ color: "var(--text-primary)" }}
        >
          データ状況
        </h2>
        <div className="grid grid-cols-2 gap-4 sm:grid-cols-3">
          {Array.from({ length: 5 }).map((_, i) => (
            <div key={i} className="space-y-2">
              <div
                className="h-3 w-16 rounded"
                style={{ backgroundColor: "var(--bg-elevated)" }}
              />
              <div
                className="h-6 w-20 rounded"
                style={{ backgroundColor: "var(--bg-elevated)" }}
              />
            </div>
          ))}
        </div>
      </div>
    );
  }

  const stats = [
    { label: "レース数", value: data.total_races.toLocaleString() },
    { label: "出走数", value: data.total_entries.toLocaleString() },
    { label: "馬", value: data.total_horses.toLocaleString() },
    { label: "騎手", value: data.total_jockeys.toLocaleString() },
    { label: "調教師", value: data.total_trainers.toLocaleString() },
  ];

  return (
    <div className="glass-card p-6">
      <h2
        className="mb-5 text-lg font-semibold"
        style={{ color: "var(--text-primary)" }}
      >
        データ状況
      </h2>

      <div className="grid grid-cols-2 gap-4 sm:grid-cols-3">
        {stats.map(({ label, value }, idx) => {
          const Icon = STAT_ICONS[idx];
          return (
            <div key={label} className="flex items-start gap-3">
              <div
                className="mt-0.5 flex h-9 w-9 shrink-0 items-center justify-center rounded-lg"
                style={{
                  backgroundColor: "var(--accent-muted)",
                  color: "var(--accent)",
                }}
              >
                <Icon />
              </div>
              <div>
                <p
                  className="text-xs font-medium"
                  style={{ color: "var(--text-secondary)" }}
                >
                  {label}
                </p>
                <p
                  className="text-xl font-bold"
                  style={{ color: "var(--text-primary)" }}
                >
                  {value}
                </p>
              </div>
            </div>
          );
        })}
      </div>

      {(data.date_min || data.date_max) && (
        <div
          className="mt-5 pt-4"
          style={{ borderTop: "1px solid var(--border)" }}
        >
          <p
            className="text-xs font-medium"
            style={{ color: "var(--text-secondary)" }}
          >
            対象期間
          </p>
          <p
            className="mt-1 text-sm font-medium"
            style={{ color: "var(--text-primary)" }}
          >
            {data.date_min ?? "?"} ~ {data.date_max ?? "?"}
          </p>
        </div>
      )}

      {data.racecourses.length > 0 && (
        <div
          className="mt-4 pt-4"
          style={{ borderTop: "1px solid var(--border)" }}
        >
          <p
            className="mb-2 text-xs font-medium"
            style={{ color: "var(--text-secondary)" }}
          >
            競馬場
          </p>
          <div className="flex flex-wrap gap-1.5">
            {data.racecourses.map((name) => (
              <span
                key={name}
                className="rounded-full px-2.5 py-0.5 text-xs font-medium"
                style={{
                  backgroundColor: "var(--bg-elevated)",
                  color: "var(--text-secondary)",
                  border: "1px solid var(--border-light)",
                }}
              >
                {name}
              </span>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
