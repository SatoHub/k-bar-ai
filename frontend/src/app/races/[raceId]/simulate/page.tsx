"use client";

import React, { useEffect, useState, useCallback } from "react";
import Link from "next/link";
import {
  fetchRaceDetail,
  fetchOdds,
  fetchOddsHistory,
  fetchPredictions,
  refreshOdds,
  type RaceDetail,
  type OddsResponse,
  type OddsHistoryResponse,
  type RacePredictionResponse,
} from "@/lib/api";
import CourseInfoBadges from "@/components/CourseInfoBadges";
import OddsChart from "@/components/OddsChart";
import AiRecommendations from "@/components/AiRecommendations";
import BettingSimulator, {
  type SessionBet,
} from "@/components/BettingSimulator";
import BetMethodComparison from "@/components/BetMethodComparison";

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
  const [predictions, setPredictions] = useState<RacePredictionResponse | null>(
    null,
  );
  const [refreshing, setRefreshing] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [sessionBets, setSessionBets] = useState<SessionBet[]>([]);

  // State for auto-filling the simulator from AI recommendations
  const [prefillBetType, setPrefillBetType] = useState<string | null>(null);
  const [prefillHorseIds, setPrefillHorseIds] = useState<string[] | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function load() {
      setLoading(true);
      setError(null);
      try {
        const [raceData, oddsData, oddsHistData, predData] = await Promise.all([
          fetchRaceDetail(raceId),
          fetchOdds(raceId).catch(() => null),
          fetchOddsHistory(raceId).catch(() => null),
          fetchPredictions(raceId).catch(() => null),
        ]);
        if (cancelled) return;
        setRace(raceData);
        setOdds(oddsData);
        setOddsHistory(oddsHistData);
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

  const handleSelectBet = useCallback(
    (betType: string, horseIds: string[]) => {
      setPrefillBetType(betType);
      setPrefillHorseIds(horseIds);
    },
    [],
  );

  // Clear prefill after it's consumed by the simulator
  const handlePrefillConsumed = useCallback(() => {
    setPrefillBetType(null);
    setPrefillHorseIds(null);
  }, []);

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
        className="inline-flex items-center gap-1.5 text-sm cursor-pointer transition-colors duration-200"
        style={{ color: "var(--text-muted)" }}
        onMouseEnter={(e) => {
          e.currentTarget.style.color = "var(--accent)";
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

      {/* Race header - enhanced */}
      <div
        className="relative overflow-hidden rounded-xl p-5"
        style={{
          backgroundColor: "var(--bg-elevated)",
          border: "1px solid var(--border)",
        }}
      >
        {/* Decorative gradient */}
        <div
          className="pointer-events-none absolute inset-0"
          style={{
            background:
              "linear-gradient(135deg, rgba(59,130,246,0.08) 0%, transparent 50%, rgba(139,92,246,0.05) 100%)",
          }}
        />
        <div className="relative">
          <div className="flex flex-wrap items-start justify-between gap-2">
            <div>
              <div className="flex items-center gap-3">
                <div
                  className="flex h-10 w-10 items-center justify-center rounded-xl"
                  style={{
                    background:
                      "linear-gradient(135deg, var(--accent), #8B5CF6)",
                    boxShadow: "0 4px 15px rgba(59,130,246,0.3)",
                  }}
                >
                  <svg
                    className="h-5 w-5"
                    fill="none"
                    stroke="#fff"
                    strokeWidth={2}
                    viewBox="0 0 24 24"
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      d="M9 7h6m0 10v-3m-3 3h.01M9 17h.01M9 14h.01M12 14h.01M15 11h.01M12 11h.01M9 11h.01M7 21h10a2 2 0 002-2V5a2 2 0 00-2-2H7a2 2 0 00-2 2v14a2 2 0 002 2z"
                    />
                  </svg>
                </div>
                <div>
                  <h1
                    className="text-lg font-bold"
                    style={{ color: "var(--text-primary)" }}
                  >
                    {race.race_name ?? `第${race.race_number}レース`}
                  </h1>
                  <span
                    className="text-xs font-medium tracking-wide uppercase"
                    style={{ color: "var(--accent)" }}
                  >
                    Betting Simulation
                  </span>
                </div>
              </div>
            </div>
            <span
              className="rounded-lg px-3 py-1.5 text-xs font-medium"
              style={{
                backgroundColor: "rgba(255,255,255,0.05)",
                color: "var(--text-secondary)",
                border: "1px solid var(--border)",
              }}
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
      </div>

      {/* 組数・オッズ比較（全買い方・全券種） */}
      {race.entries.length > 0 && (
        <BetMethodComparison raceIdStr={race.race_id} entries={race.entries} />
      )}

      {/* Two-column layout */}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        {/* Left: AI Recommendations + Odds info */}
        <div className="space-y-4">
          {/* AI Recommendations */}
          {predictions && (
            <AiRecommendations
              predictions={predictions.predictions}
              entries={race.entries}
              onSelectBet={handleSelectBet}
            />
          )}

          {/* Odds table */}
          {odds && odds.entries.length > 0 && (
            <div
              className="overflow-hidden rounded-xl"
              style={{
                backgroundColor: "var(--bg-elevated)",
                border: "1px solid var(--border)",
              }}
            >
              <div
                className="flex items-center justify-between px-5 py-3"
                style={{ borderBottom: "1px solid var(--border)" }}
              >
                <div className="flex items-center gap-2">
                  <svg
                    className="h-4 w-4"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth={2}
                    viewBox="0 0 24 24"
                    style={{ color: "var(--accent)" }}
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      d="M13 7h8m0 0v8m0-8l-8 8-4-4-6 6"
                    />
                  </svg>
                  <h2
                    className="text-sm font-bold"
                    style={{ color: "var(--text-primary)" }}
                  >
                    単勝オッズ
                  </h2>
                </div>
                <div className="flex items-center gap-2 sm:gap-3">
                  {odds.fetched_at && (
                    <span
                      className="hidden sm:inline text-[10px]"
                      style={{ color: "var(--text-muted)" }}
                    >
                      {new Date(odds.fetched_at).toLocaleString("ja-JP")}
                    </span>
                  )}
                  <button
                    type="button"
                    onClick={handleRefreshOdds}
                    disabled={refreshing}
                    className="cursor-pointer rounded-lg px-3 py-1.5 text-xs font-medium transition-all duration-200"
                    style={{
                      background: refreshing
                        ? "var(--border)"
                        : "linear-gradient(135deg, var(--accent), #8B5CF6)",
                      color: "#fff",
                      opacity: refreshing ? 0.5 : 1,
                      boxShadow: refreshing
                        ? "none"
                        : "0 2px 8px rgba(59,130,246,0.3)",
                    }}
                    onMouseEnter={(e) => {
                      if (!refreshing) {
                        e.currentTarget.style.boxShadow =
                          "0 4px 12px rgba(59,130,246,0.4)";
                      }
                    }}
                    onMouseLeave={(e) => {
                      if (!refreshing) {
                        e.currentTarget.style.boxShadow =
                          "0 2px 8px rgba(59,130,246,0.3)";
                      }
                    }}
                  >
                    {refreshing ? "更新中..." : "更新"}
                  </button>
                </div>
              </div>
              <div className="overflow-x-auto">
                <table className="w-full text-sm whitespace-nowrap">
                  <thead>
                    <tr
                      className="text-left text-[10px] font-semibold uppercase tracking-wider"
                      style={{
                        backgroundColor: "rgba(255,255,255,0.02)",
                        color: "var(--text-muted)",
                      }}
                    >
                      <th className="px-4 py-2.5">馬番</th>
                      <th className="px-4 py-2.5">馬名</th>
                      <th className="px-4 py-2.5 text-right">オッズ</th>
                      <th className="px-4 py-2.5 text-center">人気</th>
                    </tr>
                  </thead>
                  <tbody>
                    {odds.entries.map((o, i) => (
                      <tr
                        key={o.post_position}
                        className="transition-colors duration-150 cursor-default"
                        style={{
                          borderBottom:
                            i < odds.entries.length - 1
                              ? "1px solid var(--border)"
                              : "none",
                        }}
                        onMouseEnter={(e) => {
                          e.currentTarget.style.backgroundColor =
                            "rgba(59,130,246,0.04)";
                        }}
                        onMouseLeave={(e) => {
                          e.currentTarget.style.backgroundColor =
                            "transparent";
                        }}
                      >
                        <td
                          className="px-4 py-2.5 text-center tabular-nums"
                          style={{ color: "var(--text-muted)" }}
                        >
                          <span
                            className="inline-flex h-6 w-6 items-center justify-center rounded-md text-xs font-medium"
                            style={{
                              backgroundColor: "rgba(255,255,255,0.05)",
                            }}
                          >
                            {o.post_position}
                          </span>
                        </td>
                        <td
                          className="px-4 py-2.5 font-medium"
                          style={{ color: "var(--text-primary)" }}
                        >
                          {o.horse_name ?? "---"}
                        </td>
                        <td
                          className="px-4 py-2.5 text-right font-semibold tabular-nums"
                          style={{
                            color:
                              o.win_odds !== null && o.win_odds <= 5
                                ? "var(--accent)"
                                : "var(--text-primary)",
                          }}
                        >
                          {o.win_odds !== null
                            ? `${o.win_odds.toFixed(1)}倍`
                            : "---"}
                        </td>
                        <td className="px-4 py-2.5 text-center">
                          {o.win_favorite !== null && o.win_favorite <= 3 ? (
                            <span
                              className="inline-flex h-5 min-w-5 items-center justify-center rounded-full px-1.5 text-[10px] font-bold"
                              style={{
                                background:
                                  o.win_favorite === 1
                                    ? "linear-gradient(135deg, #F59E0B, #EF4444)"
                                    : o.win_favorite === 2
                                      ? "linear-gradient(135deg, #6B7280, #9CA3AF)"
                                      : "linear-gradient(135deg, #92400E, #B45309)",
                                color: "#fff",
                              }}
                            >
                              {o.win_favorite}
                            </span>
                          ) : (
                            <span
                              className="text-xs"
                              style={{ color: "var(--text-muted)" }}
                            >
                              {o.win_favorite ?? "---"}
                            </span>
                          )}
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
            <div
              className="rounded-xl p-5"
              style={{
                backgroundColor: "var(--bg-elevated)",
                border: "1px solid var(--border)",
              }}
            >
              <div className="mb-3 flex items-center gap-2">
                <svg
                  className="h-4 w-4"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth={2}
                  viewBox="0 0 24 24"
                  style={{ color: "var(--accent)" }}
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    d="M7 12l3-3 3 3 4-4M8 21l4-4 4 4M3 4h18M4 4h16v12a1 1 0 01-1 1H5a1 1 0 01-1-1V4z"
                  />
                </svg>
                <h2
                  className="text-sm font-bold"
                  style={{ color: "var(--text-primary)" }}
                >
                  オッズ変動
                </h2>
              </div>
              <OddsChart history={oddsHistory.history} />
            </div>
          )}

          {/* No odds AND no predictions fallback */}
          {(!odds || odds.entries.length === 0) &&
            (!oddsHistory || oddsHistory.history.length < 2) &&
            !predictions && (
              <div
                className="flex flex-col items-center justify-center rounded-xl py-16"
                style={{
                  backgroundColor: "var(--bg-elevated)",
                  border: "1px solid var(--border)",
                }}
              >
                <svg
                  className="mb-3 h-10 w-10"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth={1.5}
                  viewBox="0 0 24 24"
                  style={{ color: "var(--text-muted)" }}
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    d="M13 7h8m0 0v8m0-8l-8 8-4-4-6 6"
                  />
                </svg>
                <p
                  className="text-sm font-medium"
                  style={{ color: "var(--text-muted)" }}
                >
                  データがありません
                </p>
                <p
                  className="mt-1 text-xs"
                  style={{ color: "var(--text-muted)" }}
                >
                  AI予想実行・オッズ更新後に表示されます
                </p>
              </div>
            )}
        </div>

        {/* Right: Simulator */}
        <div>
          <BettingSimulator
            raceId={race.id}
            raceIdStr={race.race_id}
            raceDate={race.race_date}
            entries={race.entries}
            sessionBets={sessionBets}
            onBetSaved={handleBetSaved}
            prefillBetType={prefillBetType}
            prefillHorseIds={prefillHorseIds}
            onPrefillConsumed={handlePrefillConsumed}
          />
        </div>
      </div>
    </div>
  );
}
