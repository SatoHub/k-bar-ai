"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import {
  fetchRaceDetail,
  fetchPredictions,
  type RaceDetail,
  type RacePredictionResponse,
} from "@/lib/api";
import PredictionTable from "@/components/PredictionTable";
import EntryTable from "@/components/EntryTable";

export default function RaceDetailPage({
  params,
}: {
  params: Promise<{ raceId: string }>;
}) {
  const { raceId } = React.use(params);

  const [race, setRace] = useState<RaceDetail | null>(null);
  const [predictions, setPredictions] = useState<RacePredictionResponse | null>(
    null,
  );
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function load() {
      setLoading(true);
      setError(null);
      try {
        const [raceData, predData] = await Promise.all([
          fetchRaceDetail(raceId),
          fetchPredictions(raceId).catch(() => null),
        ]);
        if (cancelled) return;
        setRace(raceData);
        setPredictions(predData);
      } catch (e) {
        if (cancelled) return;
        setError(e instanceof Error ? e.message : "データの取得に失敗しました");
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    load();
    return () => {
      cancelled = true;
    };
  }, [raceId]);

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

  if (error || !race) {
    return (
      <div className="py-12 text-center">
        <div className="glass-card mx-auto max-w-md p-6">
          <p className="text-sm" style={{ color: "var(--red)" }}>
            {error ?? "レースが見つかりません"}
          </p>
          <Link
            href="/races"
            className="mt-4 inline-block text-sm cursor-pointer"
            style={{
              color: "var(--accent)",
              transition: "color 200ms ease-out",
            }}
            onMouseEnter={(e) => {
              e.currentTarget.style.color = "var(--accent-hover)";
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.color = "var(--accent)";
            }}
          >
            レース一覧に戻る
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Back link */}
      <Link
        href="/races"
        className="inline-flex items-center gap-1 text-sm cursor-pointer"
        style={{
          color: "var(--text-muted)",
          transition: "color 200ms ease-out",
        }}
        onMouseEnter={(e) => {
          e.currentTarget.style.color = "var(--text-primary)";
        }}
        onMouseLeave={(e) => {
          e.currentTarget.style.color = "var(--text-muted)";
        }}
      >
        <svg
          className="h-4 w-4"
          fill="none"
          stroke="currentColor"
          strokeWidth={2}
          viewBox="0 0 24 24"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            d="M15 19l-7-7 7-7"
          />
        </svg>
        レース一覧に戻る
      </Link>

      {/* Race header */}
      <div className="glass-card p-5">
        <div className="flex flex-wrap items-start justify-between gap-2">
          <div>
            <h1
              className="text-xl font-bold"
              style={{ color: "var(--text-primary)" }}
            >
              {race.race_name ?? `第${race.race_number}レース`}
            </h1>
            {race.graded_race && (
              <span
                className="mt-1 inline-block rounded-full px-2.5 py-0.5 text-xs font-medium"
                style={{
                  backgroundColor: "var(--cta)",
                  color: "#fff",
                }}
              >
                {race.graded_race}
              </span>
            )}
          </div>
          <span
            className="text-sm"
            style={{ color: "var(--text-secondary)" }}
          >
            {race.race_date}
          </span>
        </div>

        <div
          className="mt-3 flex flex-wrap gap-x-4 gap-y-1 text-sm"
          style={{ color: "var(--text-secondary)" }}
        >
          {race.racecourse_name && (
            <span>{race.racecourse_name}</span>
          )}
          {(race.surface || race.distance_m) && (
            <span>
              {race.surface ?? ""}
              {race.distance_m ? ` ${race.distance_m}m` : ""}
              {race.direction ? ` (${race.direction})` : ""}
            </span>
          )}
          {race.weather && <span>天候: {race.weather}</span>}
          {race.track_condition && <span>馬場: {race.track_condition}</span>}
        </div>
      </div>

      {/* Predictions */}
      {predictions && predictions.predictions.length > 0 && (
        <PredictionTable
          predictions={predictions.predictions}
          modelVersion={predictions.model_version}
        />
      )}

      {/* Entries / Results */}
      <EntryTable entries={race.entries} />
    </div>
  );
}
