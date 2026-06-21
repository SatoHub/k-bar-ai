"use client";

import React, { useState } from "react";
import { fetchSleepers, type SleeperEntry, type SleeperResponse } from "@/lib/api";
import { wakuColor } from "./ComboBadges";

type Props = { raceId: string };

export default function SleeperPanel({ raceId }: Props) {
  const [result, setResult] = useState<SleeperResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function run() {
    setLoading(true);
    setError(null);
    try {
      setResult(await fetchSleepers(raceId, 5));
    } catch (e) {
      setError(e instanceof Error ? e.message : "取得に失敗しました");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="glass-card overflow-hidden">
      <div
        className="flex items-center gap-2 px-4 py-3"
        style={{ borderBottom: "1px solid var(--border)" }}
      >
        <div className="w-1 self-stretch rounded-full" style={{ backgroundColor: "var(--accent)" }} />
        <h2 className="text-base font-semibold" style={{ color: "var(--text-primary)" }}>
          巻き返し穴を探す
        </h2>
      </div>

      <div className="p-4 space-y-3">
        <p className="text-xs" style={{ color: "var(--text-secondary)" }}>
          人気薄馬の全成績(netkeiba)を調べ、「今走の馬場で実績があるのに前走の条件替わり等で
          人気を落とした馬」を炙り出します。馬ごとに取得するため数十秒かかります。
        </p>

        {!result && (
          <button
            onClick={run}
            disabled={loading}
            className="rounded-md px-4 py-2 text-sm font-semibold w-full sm:w-auto"
            style={{ backgroundColor: "var(--accent)", color: "#fff", opacity: loading ? 0.6 : 1 }}
          >
            {loading ? "全成績を解析中…(数十秒)" : "穴馬を探す"}
          </button>
        )}

        {error && (
          <p className="text-sm" style={{ color: "#dc2626" }}>
            {error}
          </p>
        )}

        {result && <Results result={result} onRefresh={run} loading={loading} />}
      </div>
    </div>
  );
}

function Results({
  result,
  onRefresh,
  loading,
}: {
  result: SleeperResponse;
  onRefresh: () => void;
  loading: boolean;
}) {
  const flagged = result.entries.filter((e) => e.is_sleeper);
  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between">
        <span className="text-xs" style={{ color: "var(--text-secondary)" }}>
          {result.analyzed}頭を分析 / {result.surface}・
          <b style={{ color: flagged.length ? "#dc2626" : "var(--text-primary)" }}>
            穴候補 {flagged.length}頭
          </b>
        </span>
        <button
          onClick={onRefresh}
          disabled={loading}
          className="text-xs"
          style={{ color: "var(--accent)" }}
        >
          {loading ? "更新中…" : "再取得"}
        </button>
      </div>

      {result.entries.length === 0 ? (
        <p className="text-sm" style={{ color: "var(--text-secondary)" }}>
          {result.message ?? "分析対象がありませんでした"}
        </p>
      ) : (
        <div className="space-y-1.5">
          {result.entries.map((e, i) => (
            <SleeperRow key={i} e={e} />
          ))}
        </div>
      )}
      <p className="text-[11px] leading-snug pt-1" style={{ color: "var(--text-secondary)" }}>
        ※「条件替わりで人気急落の実力馬」を優先表示。ヒモ候補の参考に。利益は保証されません。
      </p>
    </div>
  );
}

function SleeperRow({ e }: { e: SleeperEntry }) {
  const c = wakuColor(e.bracket_number);
  return (
    <div
      className="rounded-lg p-2.5"
      style={{
        backgroundColor: e.is_sleeper ? "rgba(220,38,38,0.08)" : "var(--bg-secondary)",
        border: `1px solid ${e.is_sleeper ? "rgba(220,38,38,0.4)" : "var(--border)"}`,
      }}
    >
      <div className="flex items-center gap-2 flex-wrap">
        {e.is_sleeper && <span className="text-xs font-bold" style={{ color: "#dc2626" }}>🔴穴</span>}
        {e.post_position != null && (
          <span
            className="inline-flex h-5 min-w-[1.25rem] items-center justify-center rounded px-1 text-[11px] font-bold tabular-nums"
            style={{ backgroundColor: c.bg, color: c.fg, border: "1px solid rgba(0,0,0,0.25)" }}
          >
            {e.post_position}
          </span>
        )}
        <span className="text-sm font-medium" style={{ color: "var(--text-primary)" }}>
          {e.horse_name}
        </span>
        <span className="text-xs" style={{ color: "var(--text-secondary)" }}>
          {e.win_favorite}人気
        </span>
        <span className="ml-auto text-xs tabular-nums" style={{ color: "var(--text-secondary)" }}>
          穴度 <b style={{ color: e.is_sleeper ? "#dc2626" : "var(--text-primary)" }}>{e.score.toFixed(2)}</b>
        </span>
      </div>
      <p className="text-[11px] mt-1" style={{ color: "var(--text-secondary)" }}>
        {e.reason}
      </p>
    </div>
  );
}
