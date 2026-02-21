"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import {
  fetchRaceDetail,
  fetchOdds,
  fetchOddsHistory,
  refreshOdds,
  type RaceDetail,
  type OddsResponse,
  type OddsHistoryResponse,
} from "@/lib/api";
import CourseInfoBadges from "@/components/CourseInfoBadges";
import OddsChart from "@/components/OddsChart";
import BettingSimulator, {
  type SessionBet,
} from "@/components/BettingSimulator";

export default function SimulatePage({
  params,
}: {
  params: Promise<{ raceId: string }>;
}) {
  const { raceId } = React.use(params);

  const [race, setRace] = useState<RaceDetail | null>(null);
  const [odds, setOdds] = useState<OddsResponse | null>(null);
  const [oddsHistory, setOddsHistory] = useState<OddsHistoryResponse | null>(
    null,
  );
  const [refreshing, setRefreshing] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [sessionBets, setSessionBets] = useState<SessionBet[]>([]);

  useEffect(() => {
    let cancelled = false;

    async function load() {
      setLoading(true);
      setError(null);
      try {
        const [raceData, oddsData, oddsHistData] = await Promise.all([
          fetchRaceDetail(raceId),
          fetchOdds(raceId).catch(() => null),
          fetchOddsHistory(raceId).catch(() => null),
        ]);
        if (cancelled) return;
        setRace(raceData);
        setOdds(oddsData);
        setOddsHistory(oddsHistData);
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

  async function handleRefreshOdds() {
    setRefreshing(true);
    try {
      const [newOdds, newHistory] = await Promise.all([
        refreshOdds(raceId),
        fetchOddsHistory(raceId).catch(() => null),
      ]);
      setOdds(newOdds);
      if (newHistory) setOddsHistory(newHistory);
    } catch {
      // ignore
    } finally {
      setRefreshing(false);
    }
  }

  function handleBetSaved(bet: SessionBet) {
    setSessionBets((prev) => [...prev, bet]);
  }

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
            style={{ color: "var(--accent)" }}
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
        href={`/races/${raceId}`}
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
        レース詳細に戻る
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
            <span
              className="mt-1 inline-block text-xs"
              style={{ color: "var(--text-secondary)" }}
            >
              馬券シミュレーション
            </span>
          </div>
          <span
            className="text-sm"
            style={{ color: "var(--text-secondary)" }}
          >
            {race.race_date}
          </span>
        </div>

        <div className="mt-3 flex flex-wrap items-center gap-x-3 gap-y-2">
          {race.racecourse_name && (
            <span
              className="text-sm font-medium"
              style={{ color: "var(--text-secondary)" }}
            >
              {race.racecourse_name}
            </span>
          )}
          <CourseInfoBadges
            surface={race.surface}
            trackCondition={race.track_condition}
            weather={race.weather}
            distanceM={race.distance_m}
            direction={race.direction}
          />
        </div>
      </div>

      {/* Two-column layout */}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        {/* Left: Odds info */}
        <div className="space-y-6">
          {/* Odds table */}
          {odds && odds.entries.length > 0 && (
            <div className="glass-card overflow-hidden">
              <div
                className="flex items-center justify-between px-4 py-3"
                style={{ borderBottom: "1px solid var(--border)" }}
              >
                <h2
                  className="text-base font-semibold"
                  style={{ color: "var(--text-primary)" }}
                >
                  オッズ
                </h2>
                <div className="flex items-center gap-3">
                  {odds.fetched_at && (
                    <span
                      className="text-xs"
                      style={{ color: "var(--text-muted)" }}
                    >
                      更新:{" "}
                      {new Date(odds.fetched_at).toLocaleString("ja-JP")}
                    </span>
                  )}
                  <button
                    type="button"
                    onClick={handleRefreshOdds}
                    disabled={refreshing}
                    className="cursor-pointer rounded-md px-3 py-1 text-xs font-medium"
                    style={{
                      backgroundColor: "var(--accent)",
                      color: "#fff",
                      opacity: refreshing ? 0.5 : 1,
                    }}
                  >
                    {refreshing ? "更新中..." : "オッズ更新"}
                  </button>
                </div>
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
                      <th className="px-3 py-2">馬番</th>
                      <th className="px-3 py-2">馬名</th>
                      <th className="px-3 py-2">単勝オッズ</th>
                      <th className="px-3 py-2">人気</th>
                    </tr>
                  </thead>
                  <tbody>
                    {odds.entries.map((o) => (
                      <tr
                        key={o.post_position}
                        style={{
                          borderBottom: "1px solid var(--border)",
                        }}
                      >
                        <td
                          className="px-3 py-2 text-center tabular-nums"
                          style={{ color: "var(--text-secondary)" }}
                        >
                          {o.post_position}
                        </td>
                        <td
                          className="px-3 py-2 font-medium"
                          style={{ color: "var(--text-primary)" }}
                        >
                          {o.horse_name ?? "---"}
                        </td>
                        <td
                          className="px-3 py-2 text-right tabular-nums"
                          style={{ color: "var(--text-primary)" }}
                        >
                          {o.win_odds !== null
                            ? o.win_odds.toFixed(1)
                            : "---"}
                        </td>
                        <td
                          className="px-3 py-2 text-center"
                          style={{ color: "var(--text-secondary)" }}
                        >
                          {o.win_favorite ?? "---"}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* Odds history chart */}
          {oddsHistory && oddsHistory.history.length >= 2 && (
            <div className="glass-card p-5">
              <h2
                className="mb-3 text-base font-semibold"
                style={{ color: "var(--text-primary)" }}
              >
                オッズ変動グラフ
              </h2>
              <OddsChart history={oddsHistory.history} />
            </div>
          )}
        </div>

        {/* Right: Simulator */}
        <div>
          <BettingSimulator
            raceId={race.id}
            raceDate={race.race_date}
            entries={race.entries}
            sessionBets={sessionBets}
            onBetSaved={handleBetSaved}
          />
        </div>
      </div>
    </div>
  );
}
