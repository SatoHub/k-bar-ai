"use client";

/**
 * 全券種オッズのタブ表示（レース詳細用・netkeiba）。
 * 8券種を切り替え、選んだ券種の全組み合わせオッズを一覧表示する。
 * 三連単などは組数が膨大なため、人気順で上位のみ表示（総点数は明記）。
 */

import React, { useEffect, useMemo, useState } from "react";
import { fetchOddsTable, type RaceEntry, type OddsComboEntry } from "@/lib/api";

const BET_TYPES = [
  { value: "tansho", label: "単勝", single: true, ordered: false, isWaku: false },
  { value: "fukusho", label: "複勝", single: true, ordered: false, isWaku: false },
  { value: "wakuren", label: "枠連", single: false, ordered: false, isWaku: true },
  { value: "umaren", label: "馬連", single: false, ordered: false, isWaku: false },
  { value: "umatan", label: "馬単", single: false, ordered: true, isWaku: false },
  { value: "wide", label: "ワイド", single: false, ordered: false, isWaku: false },
  { value: "sanrenpuku", label: "三連複", single: false, ordered: false, isWaku: false },
  { value: "sanrentan", label: "三連単", single: false, ordered: true, isWaku: false },
] as const;

const STATUS_LABEL: Record<string, string> = {
  result: "確定",
  middle: "暫定",
  yoso: "予想",
};

const MAX_ROWS = 200;

type Props = {
  raceIdStr: string;
  entries: RaceEntry[];
};

export default function AllOddsTabs({ raceIdStr, entries }: Props) {
  const [betType, setBetType] = useState<string>("tansho");
  const [combos, setCombos] = useState<OddsComboEntry[] | null>(null);
  const [status, setStatus] = useState<string | null>(null);
  const [datetime, setDatetime] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const def = BET_TYPES.find((t) => t.value === betType) ?? BET_TYPES[0];

  const postToName = useMemo(() => {
    const m = new Map<number, string>();
    for (const e of entries) {
      if (e.post_position != null) m.set(e.post_position, e.horse.name ?? "—");
    }
    return m;
  }, [entries]);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    setCombos(null);
    fetchOddsTable(raceIdStr, betType)
      .then((res) => {
        if (cancelled) return;
        setCombos(res.combos);
        setStatus(res.status);
        setDatetime(res.official_datetime);
        if (res.combos.length === 0) {
          setError("オッズが取得できませんでした（発売前/締切後の可能性）");
        }
      })
      .catch(() => {
        if (!cancelled) setError("オッズの取得に失敗しました");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [raceIdStr, betType]);

  // 表示用に整形（人気順 → なければオッズ昇順）
  const rows = useMemo(() => {
    const list = (combos ?? []).filter((c) => c.odds != null && c.odds > 0);
    list.sort((a, b) => {
      if (a.favorite != null && b.favorite != null) return a.favorite - b.favorite;
      return (a.odds ?? 1e9) - (b.odds ?? 1e9);
    });
    return list;
  }, [combos]);

  function formatCombo(key: string): string {
    const parts = key.split("-").map((p) => String(parseInt(p, 10)));
    if (def.isWaku) return parts.map((p) => `${p}枠`).join(" - ");
    return parts.join(def.ordered ? " → " : " - ");
  }

  function comboNames(key: string): string {
    if (def.isWaku) return "";
    return key
      .split("-")
      .map((p) => postToName.get(parseInt(p, 10)) ?? "—")
      .join(def.ordered ? " → " : " / ");
  }

  function oddsText(c: OddsComboEntry): string {
    if (c.odds_low != null && c.odds_high != null && c.odds_low !== c.odds_high) {
      return `${c.odds_low.toFixed(1)}〜${c.odds_high.toFixed(1)}`;
    }
    return c.odds != null ? c.odds.toFixed(1) : "---";
  }

  const shown = rows.slice(0, MAX_ROWS);

  return (
    <div className="glass-card overflow-hidden">
      <div
        className="flex items-center justify-between px-4 py-3"
        style={{ borderBottom: "1px solid var(--border)" }}
      >
        <h2 className="text-base font-semibold" style={{ color: "var(--text-primary)" }}>
          全券種オッズ
        </h2>
        <div className="flex items-center gap-2">
          {status && STATUS_LABEL[status] && (
            <span
              className="rounded px-1.5 py-0.5 text-[10px] font-medium"
              style={{ backgroundColor: "var(--bg-elevated)", color: "var(--text-secondary)" }}
            >
              {STATUS_LABEL[status]}
            </span>
          )}
          {datetime && (
            <span className="hidden sm:inline text-[10px]" style={{ color: "var(--text-muted)" }}>
              {datetime}
            </span>
          )}
        </div>
      </div>

      {/* 券種タブ */}
      <div className="flex flex-wrap gap-1.5 px-4 py-3" style={{ borderBottom: "1px solid var(--border)" }}>
        {BET_TYPES.map((t) => {
          const active = t.value === betType;
          return (
            <button
              key={t.value}
              type="button"
              onClick={() => setBetType(t.value)}
              className="cursor-pointer rounded-lg px-3 py-1.5 text-xs font-medium transition-all duration-150"
              style={{
                background: active
                  ? "linear-gradient(135deg, var(--accent), #8B5CF6)"
                  : "rgba(255,255,255,0.04)",
                color: active ? "#fff" : "var(--text-secondary)",
                border: active ? "none" : "1px solid var(--border)",
              }}
            >
              {t.label}
            </button>
          );
        })}
      </div>

      {loading && (
        <p className="py-6 text-center text-xs" style={{ color: "var(--text-muted)" }}>
          オッズ取得中...
        </p>
      )}
      {!loading && error && (
        <p className="py-6 text-center text-xs" style={{ color: "var(--text-muted)" }}>
          {error}
        </p>
      )}

      {!loading && !error && shown.length > 0 && (
        <>
          {rows.length > MAX_ROWS && (
            <p className="px-4 pt-2 text-[11px]" style={{ color: "var(--text-muted)" }}>
              全{rows.length.toLocaleString()}点中、人気上位{MAX_ROWS}点を表示
            </p>
          )}
          <div className="max-h-[28rem] overflow-auto">
            <table className="w-full text-sm whitespace-nowrap">
              <thead className="sticky top-0">
                <tr
                  className="text-left text-xs font-medium uppercase"
                  style={{ backgroundColor: "var(--bg-elevated)", color: "var(--text-secondary)" }}
                >
                  <th className="px-3 py-2">{def.isWaku ? "枠" : def.single ? "馬番" : "組み合わせ"}</th>
                  {!def.isWaku && <th className="px-3 py-2">馬名</th>}
                  <th className="px-3 py-2 text-right">オッズ</th>
                  <th className="px-3 py-2 text-center">人気</th>
                </tr>
              </thead>
              <tbody>
                {shown.map((c) => (
                  <tr key={c.combo} style={{ borderBottom: "1px solid var(--border)" }}>
                    <td
                      className="px-3 py-2 font-medium tabular-nums"
                      style={{ color: "var(--text-primary)" }}
                    >
                      {formatCombo(c.combo)}
                    </td>
                    {!def.isWaku && (
                      <td className="px-3 py-2" style={{ color: "var(--text-secondary)" }}>
                        {comboNames(c.combo)}
                      </td>
                    )}
                    <td
                      className="px-3 py-2 text-right font-semibold tabular-nums"
                      style={{
                        color:
                          c.odds != null && c.odds <= 10
                            ? "var(--accent)"
                            : "var(--text-primary)",
                      }}
                    >
                      {oddsText(c)}
                    </td>
                    <td
                      className="px-3 py-2 text-center tabular-nums"
                      style={{ color: "var(--text-secondary)" }}
                    >
                      {c.favorite ?? "---"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </div>
  );
}
