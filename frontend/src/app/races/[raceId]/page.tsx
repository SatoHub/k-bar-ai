"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import {
  fetchRaceDetail,
  fetchPredictions,
  fetchOdds,
  fetchOddsHistory,
  fetchPastPerformances,
  fetchPedigree,
  fetchConfirmedData,
  fetchTrackCondition,
  refreshOdds,
  type RaceDetail,
  type RacePredictionResponse,
  type OddsResponse,
  type OddsHistoryResponse,
  type PastRaceRecord,
  type HorsePedigree,
  type ConfirmedDataResponse,
  type TrackConditionResponse,
} from "@/lib/api";
import PredictionTable from "@/components/PredictionTable";
import BudgetSuggestionPanel from "@/components/BudgetSuggestionPanel";
import SleeperPanel from "@/components/SleeperPanel";
import HedgePanel from "@/components/HedgePanel";
import EntryTable from "@/components/EntryTable";
import CourseInfoBadges from "@/components/CourseInfoBadges";
import OddsChart from "@/components/OddsChart";
import ConfirmedResults from "@/components/ConfirmedResults";
import TrackConditionInfo from "@/components/TrackConditionInfo";

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
  const [odds, setOdds] = useState<OddsResponse | null>(null);
  const [oddsHistory, setOddsHistory] = useState<OddsHistoryResponse | null>(null);
  const [pastByHorse, setPastByHorse] = useState<
    Record<string, PastRaceRecord[]>
  >({});
  const [pedigreeByHorse, setPedigreeByHorse] = useState<
    Record<string, HorsePedigree>
  >({});
  const [confirmed, setConfirmed] = useState<ConfirmedDataResponse | null>(null);
  const [trackCond, setTrackCond] = useState<TrackConditionResponse | null>(null);
  const [refreshing, setRefreshing] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function load() {
      setLoading(true);
      setError(null);
      try {
        const [
          raceData,
          predData,
          oddsData,
          oddsHistData,
          pastData,
          pedData,
          confData,
          tcData,
        ] = await Promise.all([
          fetchRaceDetail(raceId),
          fetchPredictions(raceId).catch(() => null),
          fetchOdds(raceId).catch(() => null),
          fetchOddsHistory(raceId).catch(() => null),
          fetchPastPerformances(raceId, 5).catch(() => null),
          fetchPedigree(raceId).catch(() => null),
          fetchConfirmedData(raceId).catch(() => null),
          fetchTrackCondition(raceId).catch(() => null),
        ]);
        if (cancelled) return;
        setRace(raceData);
        setPredictions(predData);
        setOdds(oddsData);
        setOddsHistory(oddsHistData);
        setConfirmed(confData);
        setTrackCond(tcData);
        if (pastData) {
          const map: Record<string, PastRaceRecord[]> = {};
          for (const h of pastData.horses) map[h.horse_id] = h.records;
          setPastByHorse(map);
        } else {
          setPastByHorse({});
        }
        if (pedData) {
          const pmap: Record<string, HorsePedigree> = {};
          for (const h of pedData.horses) pmap[h.horse_id] = h;
          setPedigreeByHorse(pmap);
        } else {
          setPedigreeByHorse({});
        }
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

  // Determine if this is an upcoming race (no finish positions)
  const isUpcoming =
    race.entries.length > 0 &&
    race.entries.every((e) => e.finish_position === null && !e.finish_note);

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
            <div className="flex items-center gap-2">
              <h1
                className="text-xl font-bold"
                style={{ color: "var(--text-primary)" }}
              >
                {race.race_name ?? `第${race.race_number}レース`}
              </h1>
              {isUpcoming && (
                <span
                  className="rounded-full px-2.5 py-0.5 text-xs font-medium"
                  style={{
                    backgroundColor: "rgba(59,130,246,0.15)",
                    color: "var(--accent)",
                  }}
                >
                  出走前
                </span>
              )}
            </div>
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

        {/* Course info badges */}
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

      {/* Predictions */}
      {predictions && predictions.predictions.length > 0 && (
        <PredictionTable
          predictions={predictions.predictions}
          modelVersion={predictions.model_version}
          upset={predictions.upset}
        />
      )}

      {/* 予算から買い目を自動提案 */}
      {predictions && predictions.predictions.length > 0 && (
        <BudgetSuggestionPanel raceId={race.race_id} entries={race.entries} />
      )}

      {/* 巻き返し穴を探す */}
      {race.entries.length > 0 && <SleeperPanel raceId={race.race_id} />}

      {/* 荒れ対応ヘッジ(本命三連複+穴ワイド) */}
      {predictions && predictions.predictions.length > 0 && (
        <HedgePanel raceId={race.race_id} entries={race.entries} />
      )}

      {/* Odds section */}
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
            <div className="flex items-center gap-2 sm:gap-3">
              {odds.fetched_at && (
                <span
                  className="hidden sm:inline text-xs"
                  style={{ color: "var(--text-muted)" }}
                >
                  更新: {new Date(odds.fetched_at).toLocaleString("ja-JP")}
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
                    style={{ borderBottom: "1px solid var(--border)" }}
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
                      {o.win_odds !== null ? o.win_odds.toFixed(1) : "---"}
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

      {/* 馬場情報（含水率・クッション値・JRA公式） */}
      <TrackConditionInfo data={trackCond} />

      {/* 確定オッズ・払戻（JRA-VAN） */}
      <ConfirmedResults confirmed={confirmed} entries={race.entries} />

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

      {/* Entries / Results */}
      <EntryTable
        entries={race.entries}
        isUpcoming={isUpcoming}
        pastByHorse={pastByHorse}
        pedigreeByHorse={pedigreeByHorse}
      />

      {/* Link to simulation page */}
      <div className="flex justify-center">
        <Link
          href={`/races/${raceId}/simulate`}
          className="inline-flex items-center gap-2 rounded-lg px-6 py-3 text-sm font-medium cursor-pointer"
          style={{
            backgroundColor: "var(--accent)",
            color: "#fff",
            transition: "opacity 200ms ease-out",
          }}
          onMouseEnter={(e) => {
            e.currentTarget.style.opacity = "0.85";
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.opacity = "1";
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
              d="M9 7h6m0 10v-3m-3 3h.01M9 17h.01M9 14h.01M12 14h.01M15 11h.01M12 11h.01M9 11h.01M7 21h10a2 2 0 002-2V5a2 2 0 00-2-2H7a2 2 0 00-2 2v14a2 2 0 002 2z"
            />
          </svg>
          馬券シミュレーションページへ
        </Link>
      </div>
    </div>
  );
}
