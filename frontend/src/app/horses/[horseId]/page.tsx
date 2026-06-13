"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import { fetchHorseDetail, type HorseDetail } from "@/lib/api";

const PLACEHOLDER_SVG = `data:image/svg+xml,${encodeURIComponent('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 240 320" fill="none"><rect width="240" height="320" rx="12" fill="#1a1a2e"/><path d="M120 100c-20 0-36 16-36 36s16 36 36 36 36-16 36-36-16-36-36-36zm-8 48l-16-8v-8l24 12 24-12v8l-16 8-8 4-8-4z" fill="#334155"/><text x="120" y="250" text-anchor="middle" fill="#475569" font-size="14" font-family="sans-serif">No Image</text></svg>')}`;

export default function HorseDetailPage({
  params,
}: {
  params: Promise<{ horseId: string }>;
}) {
  const { horseId } = React.use(params);

  const [horse, setHorse] = useState<HorseDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [imgError, setImgError] = useState(false);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    fetchHorseDetail(horseId)
      .then((data) => {
        if (!cancelled) setHorse(data);
      })
      .catch((e) => {
        if (!cancelled)
          setError(
            e instanceof Error ? e.message : "データの取得に失敗しました",
          );
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [horseId]);

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <div
          className="h-8 w-8 animate-spin rounded-full"
          style={{
            border: "4px solid var(--border-light)",
            borderTopColor: "var(--accent)",
          }}
        />
      </div>
    );
  }

  if (error || !horse) {
    return (
      <div className="py-12 text-center">
        <div className="glass-card mx-auto max-w-md p-6">
          <p className="text-sm" style={{ color: "var(--red)" }}>
            {error ?? "馬が見つかりません"}
          </p>
        </div>
      </div>
    );
  }

  const imageUrl =
    !imgError && horse.image_url ? horse.image_url : PLACEHOLDER_SVG;

  return (
    <div className="space-y-6">
      {/* Header with image */}
      <div className="glass-card p-6">
        <div className="flex flex-col sm:flex-row gap-6">
          {/* Horse image */}
          <div className="shrink-0">
            <img
              src={imageUrl}
              alt={horse.name}
              width={160}
              height={213}
              className="rounded-xl object-cover"
              style={{
                backgroundColor: "var(--bg-elevated)",
                width: 160,
                height: 213,
              }}
              onError={() => setImgError(true)}
            />
          </div>

          {/* Horse info */}
          <div className="flex-1">
            <h1
              className="text-2xl font-bold"
              style={{ color: "var(--text-primary)" }}
            >
              {horse.name}
            </h1>
            <p
              className="mt-1 text-sm"
              style={{ color: "var(--text-secondary)" }}
            >
              {horse.sex ?? "不明"}{" "}
              {horse.netkeiba_id && (
                <span style={{ color: "var(--text-muted)" }}>
                  (netkeiba: {horse.netkeiba_id})
                </span>
              )}
            </p>

            {/* Stats summary */}
            <div className="mt-4 grid grid-cols-2 gap-3 sm:grid-cols-5">
              {[
                { label: "出走", value: horse.total_runs },
                { label: "勝利", value: horse.wins },
                { label: "複勝", value: horse.place_count },
                {
                  label: "勝率",
                  value: `${(horse.win_rate * 100).toFixed(1)}%`,
                },
                {
                  label: "複勝率",
                  value: `${(horse.place_rate * 100).toFixed(1)}%`,
                },
              ].map((s) => (
                <div
                  key={s.label}
                  className="rounded-lg p-3 text-center"
                  style={{ backgroundColor: "var(--bg-elevated)" }}
                >
                  <div
                    className="text-xs font-medium"
                    style={{ color: "var(--text-secondary)" }}
                  >
                    {s.label}
                  </div>
                  <div
                    className="mt-1 text-lg font-bold tabular-nums"
                    style={{ color: "var(--text-primary)" }}
                  >
                    {s.value}
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>

      {/* Surface stats */}
      {Object.keys(horse.surface_stats).length > 0 && (
        <div className="glass-card p-5">
          <h2
            className="mb-3 text-base font-semibold"
            style={{ color: "var(--text-primary)" }}
          >
            馬場別成績
          </h2>
          <div className="space-y-2">
            {Object.entries(horse.surface_stats).map(([surface, stats]) => {
              const total = stats.runs;
              const winPct = total > 0 ? (stats.wins / total) * 100 : 0;
              const placePct = total > 0 ? (stats.place / total) * 100 : 0;
              return (
                <div key={surface} className="flex items-center gap-3">
                  <span
                    className="w-12 text-sm font-medium"
                    style={{ color: "var(--text-primary)" }}
                  >
                    {surface}
                  </span>
                  <div
                    className="flex-1 h-5 rounded-full overflow-hidden"
                    style={{ backgroundColor: "var(--bg-elevated)" }}
                  >
                    {/* Place rate bar (wider, behind) */}
                    <div
                      className="h-full rounded-full relative"
                      style={{
                        width: `${Math.max(placePct, 2)}%`,
                        backgroundColor: "rgba(59,130,246,0.3)",
                      }}
                    >
                      {/* Win rate bar (narrower, in front) */}
                      <div
                        className="absolute inset-y-0 left-0 rounded-full"
                        style={{
                          width:
                            placePct > 0
                              ? `${(winPct / placePct) * 100}%`
                              : "0%",
                          backgroundColor: "var(--accent)",
                        }}
                      />
                    </div>
                  </div>
                  <span
                    className="w-28 text-right text-xs tabular-nums"
                    style={{ color: "var(--text-secondary)" }}
                  >
                    {stats.runs}走 {stats.wins}勝 複{stats.place}
                  </span>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Race history */}
      <div className="glass-card overflow-hidden">
        <div
          className="px-4 py-3"
          style={{ borderBottom: "1px solid var(--border)" }}
        >
          <h2
            className="text-base font-semibold"
            style={{ color: "var(--text-primary)" }}
          >
            過去レース一覧
          </h2>
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
                <th className="px-3 py-2">日付</th>
                <th className="px-3 py-2">競馬場</th>
                <th className="px-3 py-2">レース名</th>
                <th className="px-3 py-2">コース</th>
                <th className="px-3 py-2">馬場</th>
                <th className="px-3 py-2">着順</th>
                <th className="px-3 py-2">オッズ</th>
                <th className="px-3 py-2">騎手</th>
              </tr>
            </thead>
            <tbody>
              {horse.records.map((r, idx) => (
                <tr
                  key={`${r.race_id}-${idx}`}
                  style={{
                    borderBottom: "1px solid var(--border)",
                    transition: "background-color 200ms ease-out",
                  }}
                  onMouseEnter={(e) =>
                    (e.currentTarget.style.backgroundColor =
                      "var(--bg-card-hover)")
                  }
                  onMouseLeave={(e) =>
                    (e.currentTarget.style.backgroundColor = "transparent")
                  }
                >
                  <td
                    className="px-3 py-2"
                    style={{ color: "var(--text-secondary)" }}
                  >
                    {r.race_date}
                  </td>
                  <td className="px-3 py-2">
                    {r.racecourse_name ?? "---"}
                  </td>
                  <td className="px-3 py-2">
                    <Link
                      href={`/races/${r.race_id}`}
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
                      {r.race_name ?? "---"}
                    </Link>
                  </td>
                  <td className="px-3 py-2">
                    {r.surface ?? ""}{r.distance_m ? `${r.distance_m}m` : ""}
                  </td>
                  <td className="px-3 py-2">
                    {r.track_condition ?? "---"}
                  </td>
                  <td
                    className="px-3 py-2 text-center font-medium"
                    style={{
                      color:
                        r.finish_position === 1
                          ? "var(--cta)"
                          : r.finish_position !== null && r.finish_position <= 3
                            ? "var(--accent)"
                            : "var(--text-primary)",
                    }}
                  >
                    {r.finish_position ?? r.finish_note ?? "---"}
                  </td>
                  <td
                    className="px-3 py-2 text-right tabular-nums"
                    style={{ color: "var(--text-secondary)" }}
                  >
                    {r.win_odds !== null ? r.win_odds.toFixed(1) : "---"}
                  </td>
                  <td
                    className="px-3 py-2"
                    style={{ color: "var(--text-secondary)" }}
                  >
                    {r.jockey_name ?? "---"}
                  </td>
                </tr>
              ))}
              {horse.records.length === 0 && (
                <tr>
                  <td
                    colSpan={8}
                    className="px-3 py-6 text-center"
                    style={{ color: "var(--text-muted)" }}
                  >
                    レース記録がありません
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
