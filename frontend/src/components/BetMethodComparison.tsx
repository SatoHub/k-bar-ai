"use client";

/**
 * 全買い方の組数比較 ＋ 各組のオッズ一覧。
 * 馬を選ぶと「通常 / ボックス / フォーメーション / 流し」の組数を横並び比較し、
 * 選んだ買い方の全組み合わせのオッズ（netkeiba・全券種）を一覧表示する。
 */

import React, { useEffect, useMemo, useState, useCallback } from "react";
import {
  fetchOddsTable,
  type RaceEntry,
  type OddsComboEntry,
} from "@/lib/api";
import {
  getPointCount,
  expandCombinations,
  type BuyingMethodType,
} from "@/lib/betCalculations";

const BET_TYPES = [
  { value: "tansho", label: "単勝", picks: 1, ordered: false, isWaku: false },
  { value: "fukusho", label: "複勝", picks: 1, ordered: false, isWaku: false },
  { value: "wakuren", label: "枠連", picks: 2, ordered: false, isWaku: true },
  { value: "umaren", label: "馬連", picks: 2, ordered: false, isWaku: false },
  { value: "umatan", label: "馬単", picks: 2, ordered: true, isWaku: false },
  { value: "wide", label: "ワイド", picks: 2, ordered: false, isWaku: false },
  { value: "sanrenpuku", label: "三連複", picks: 3, ordered: false, isWaku: false },
  { value: "sanrentan", label: "三連単", picks: 3, ordered: true, isWaku: false },
] as const;

type BetTypeDef = (typeof BET_TYPES)[number];

const METHODS: { value: BuyingMethodType; label: string; desc: string }[] = [
  { value: "normal", label: "通常", desc: "ちょうど必要頭数を選ぶ（1点）" },
  { value: "box", label: "ボックス", desc: "選んだ馬の総当たり" },
  { value: "formation", label: "フォーメーション", desc: "着順ごとに候補を指定" },
  { value: "nagashi", label: "流し", desc: "軸＋相手の組合せ" },
];

const STATUS_LABEL: Record<string, string> = {
  result: "確定",
  middle: "暫定",
  yoso: "予想",
};

function getTypeDef(betType: string): BetTypeDef {
  return BET_TYPES.find((t) => t.value === betType) ?? BET_TYPES[0];
}

/** combo（馬ID配列）→ netkeibaオッズキー "01-02-03" に変換 */
function buildComboKey(
  comboIds: string[],
  ordered: boolean,
  isWaku: boolean,
  idToPost: Map<string, number>,
): string | null {
  const nums: number[] = [];
  for (const id of comboIds) {
    const n = isWaku ? Number(id) : idToPost.get(id);
    if (!n || Number.isNaN(n)) return null;
    nums.push(n);
  }
  const arranged = ordered ? nums : [...nums].sort((a, b) => a - b);
  return arranged.map((n) => String(n).padStart(2, "0")).join("-");
}

type Props = {
  raceIdStr: string; // netkeiba race_id (オッズ取得用)
  entries: RaceEntry[];
};

export default function BetMethodComparison({ raceIdStr, entries }: Props) {
  const [betType, setBetType] = useState<string>("sanrentan");
  const [activeMethod, setActiveMethod] = useState<BuyingMethodType>("box");
  // 馬の選択（馬ID）。枠連のときは枠番文字列。
  const [pool, setPool] = useState<string[]>([]);
  const [axisIds, setAxisIds] = useState<string[]>([]);
  // フォーメーション: 各着順の候補（馬ID）
  const [formationSets, setFormationSets] = useState<string[][]>([[], [], []]);

  const [oddsTable, setOddsTable] = useState<OddsComboEntry[] | null>(null);
  const [oddsStatus, setOddsStatus] = useState<string | null>(null);
  const [oddsDatetime, setOddsDatetime] = useState<string | null>(null);
  const [oddsLoading, setOddsLoading] = useState(false);
  const [oddsError, setOddsError] = useState<string | null>(null);

  const typeDef = getTypeDef(betType);
  const { picks, ordered, isWaku } = typeDef;

  // 選択候補（枠連は枠番、それ以外は出走馬）
  const options = useMemo(() => {
    if (isWaku) {
      const brackets = new Set<number>();
      for (const e of entries) {
        if (e.bracket_number != null) brackets.add(e.bracket_number);
      }
      return [...brackets]
        .sort((a, b) => a - b)
        .map((b) => ({ id: String(b), label: `${b}枠`, num: b, odds: null as number | null }));
    }
    return [...entries]
      .filter((e) => e.post_position != null)
      .sort((a, b) => (a.post_position ?? 0) - (b.post_position ?? 0))
      .map((e) => ({
        id: e.horse.id,
        label: `${e.post_position} ${e.horse.name ?? "—"}`,
        num: e.post_position ?? 0,
        odds: e.win_odds,
      }));
  }, [entries, isWaku]);

  const idToPost = useMemo(() => {
    const m = new Map<string, number>();
    if (isWaku) {
      for (const o of options) m.set(o.id, o.num);
    } else {
      for (const e of entries) {
        if (e.post_position != null) m.set(e.horse.id, e.post_position);
      }
    }
    return m;
  }, [entries, options, isWaku]);

  const labelOf = useCallback(
    (id: string) => {
      if (isWaku) return `${id}枠`;
      const post = idToPost.get(id);
      return post != null ? String(post) : id;
    },
    [idToPost, isWaku],
  );

  // 券種が変わったら選択をリセット
  useEffect(() => {
    setPool([]);
    setAxisIds([]);
    setFormationSets(Array.from({ length: Math.max(picks, 1) }, () => []));
    if (picks === 1) setActiveMethod("normal");
    else if (activeMethod === "normal") setActiveMethod("box");
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [betType]);

  // オッズ表を券種ごとに取得（picks>=1 すべて）
  useEffect(() => {
    let cancelled = false;
    setOddsLoading(true);
    setOddsError(null);
    setOddsTable(null);
    fetchOddsTable(raceIdStr, betType)
      .then((res) => {
        if (cancelled) return;
        setOddsTable(res.combos);
        setOddsStatus(res.status);
        setOddsDatetime(res.official_datetime);
        if (res.combos.length === 0) {
          setOddsError("オッズが取得できませんでした（発売前/締切後の可能性）");
        }
      })
      .catch(() => {
        if (!cancelled) setOddsError("オッズの取得に失敗しました");
      })
      .finally(() => {
        if (!cancelled) setOddsLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [raceIdStr, betType]);

  const oddsMap = useMemo(() => {
    const m = new Map<string, OddsComboEntry>();
    for (const c of oddsTable ?? []) m.set(c.combo, c);
    return m;
  }, [oddsTable]);

  // 各買い方の組数
  const counts = useMemo(() => {
    const def = { picks, ordered };
    const normal = pool.length === picks ? 1 : 0;
    const box =
      pool.length >= picks
        ? getPointCount(
            {
              buyingMethod: "box",
              betType,
              boxSelections: pool,
              formationSets: [],
              axisHorses: [],
              partnerHorses: [],
            },
            def,
          )
        : 0;
    const partners = pool.filter((id) => !axisIds.includes(id));
    const nagashi =
      axisIds.length >= 1 && axisIds.length < picks
        ? getPointCount(
            {
              buyingMethod: "nagashi",
              betType,
              boxSelections: [],
              formationSets: [],
              axisHorses: axisIds,
              partnerHorses: partners,
            },
            def,
          )
        : 0;
    const formationReady =
      formationSets.length === picks && formationSets.every((s) => s.length > 0);
    const formation = formationReady
      ? getPointCount(
          {
            buyingMethod: "formation",
            betType,
            boxSelections: [],
            formationSets,
            axisHorses: [],
            partnerHorses: [],
          },
          def,
        )
      : 0;
    return { normal, box, nagashi, formation };
  }, [pool, axisIds, formationSets, picks, ordered, betType]);

  // 選択中の買い方の全組み合わせ
  const activeCombos = useMemo(() => {
    const def = { picks, ordered };
    if (activeMethod === "normal") {
      return pool.length === picks ? [pool] : [];
    }
    return expandCombinations(
      {
        buyingMethod: activeMethod,
        betType,
        boxSelections: pool,
        formationSets,
        axisHorses: axisIds,
        partnerHorses: pool.filter((id) => !axisIds.includes(id)),
      },
      def,
    );
  }, [activeMethod, pool, axisIds, formationSets, picks, ordered, betType]);

  // 組み合わせ＋オッズ
  const comboRows = useMemo(() => {
    return activeCombos.map((combo) => {
      const key = buildComboKey(combo, ordered, isWaku, idToPost);
      const entry = key ? oddsMap.get(key) : undefined;
      return {
        combo,
        label: combo.map(labelOf).join(ordered ? " → " : " - "),
        odds: entry?.odds ?? null,
        oddsLow: entry?.odds_low ?? null,
        oddsHigh: entry?.odds_high ?? null,
      };
    });
  }, [activeCombos, ordered, isWaku, idToPost, oddsMap, labelOf]);

  // 統計（オッズが取れた組のみ）
  const stats = useMemo(() => {
    const vals = comboRows
      .map((r) => r.odds)
      .filter((v): v is number => v != null && v > 0);
    if (vals.length === 0) {
      return { count: comboRows.length, min: null, max: null, avg: null, withOdds: 0 };
    }
    const min = Math.min(...vals);
    const max = Math.max(...vals);
    const avg = vals.reduce((a, b) => a + b, 0) / vals.length;
    return { count: comboRows.length, min, max, avg, withOdds: vals.length };
  }, [comboRows]);

  function togglePool(id: string) {
    setPool((prev) =>
      prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id],
    );
    setAxisIds((prev) => prev.filter((x) => x !== id || pool.includes(id)));
  }

  function toggleAxis(id: string) {
    setAxisIds((prev) =>
      prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id],
    );
  }

  function toggleFormation(posIdx: number, id: string) {
    setFormationSets((prev) => {
      const next = prev.map((s) => [...s]);
      const set = next[posIdx];
      const i = set.indexOf(id);
      if (i >= 0) set.splice(i, 1);
      else set.push(id);
      return next;
    });
  }

  const card: React.CSSProperties = {
    backgroundColor: "var(--bg-elevated)",
    border: "1px solid var(--border)",
  };

  return (
    <div className="space-y-4 rounded-xl p-5" style={card}>
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
            d="M9 17V7m4 10V11m4 6V9M5 21h14a2 2 0 002-2V5a2 2 0 00-2-2H5a2 2 0 00-2 2v14a2 2 0 002 2z"
          />
        </svg>
        <h2 className="text-sm font-bold" style={{ color: "var(--text-primary)" }}>
          組数・オッズ比較
        </h2>
      </div>

      {/* 券種選択 */}
      <div className="flex flex-wrap gap-1.5">
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

      {/* 馬選択 */}
      <div>
        <p className="mb-1.5 text-xs font-medium" style={{ color: "var(--text-muted)" }}>
          {isWaku ? "枠を選択" : "馬を選択"}
        </p>
        <div className="flex flex-wrap gap-1.5">
          {options.map((o) => {
            const selected = pool.includes(o.id);
            const isAxis = axisIds.includes(o.id);
            return (
              <button
                key={o.id}
                type="button"
                onClick={() => togglePool(o.id)}
                className="cursor-pointer rounded-lg px-2.5 py-1.5 text-xs font-medium tabular-nums transition-all duration-150"
                style={{
                  background: selected
                    ? isAxis
                      ? "linear-gradient(135deg, #F59E0B, #EF4444)"
                      : "rgba(59,130,246,0.18)"
                    : "rgba(255,255,255,0.03)",
                  color: selected ? "var(--text-primary)" : "var(--text-muted)",
                  border: selected
                    ? "1px solid var(--accent)"
                    : "1px solid var(--border)",
                }}
                title={o.odds != null ? `単勝 ${o.odds}倍` : undefined}
              >
                {o.label}
              </button>
            );
          })}
        </div>
        {pool.length === 0 && (
          <p className="mt-1.5 text-xs" style={{ color: "var(--text-muted)" }}>
            {isWaku ? "枠" : "馬"}を選ぶと各買い方の組数が表示されます
          </p>
        )}
      </div>

      {/* 流し: 軸指定 */}
      {picks >= 2 && pool.length >= 1 && (
        <div>
          <p className="mb-1.5 text-xs font-medium" style={{ color: "var(--text-muted)" }}>
            流しの軸（選択馬から指定 / オレンジ表示）
          </p>
          <div className="flex flex-wrap gap-1.5">
            {pool.map((id) => {
              const isAxis = axisIds.includes(id);
              return (
                <button
                  key={id}
                  type="button"
                  onClick={() => toggleAxis(id)}
                  className="cursor-pointer rounded-lg px-2.5 py-1 text-xs font-medium transition-all duration-150"
                  style={{
                    background: isAxis
                      ? "linear-gradient(135deg, #F59E0B, #EF4444)"
                      : "rgba(255,255,255,0.04)",
                    color: isAxis ? "#fff" : "var(--text-muted)",
                    border: isAxis ? "none" : "1px solid var(--border)",
                  }}
                >
                  {labelOf(id)}
                </button>
              );
            })}
          </div>
        </div>
      )}

      {/* フォーメーション: 着順別 */}
      {picks >= 2 && pool.length >= 1 && (
        <details>
          <summary
            className="cursor-pointer text-xs font-medium"
            style={{ color: "var(--text-muted)" }}
          >
            フォーメーション着順設定（任意）
          </summary>
          <div className="mt-2 space-y-2">
            {Array.from({ length: picks }, (_, pos) => (
              <div key={pos} className="flex flex-wrap items-center gap-1.5">
                <span
                  className="w-12 shrink-0 text-xs font-medium"
                  style={{ color: "var(--text-secondary)" }}
                >
                  {pos + 1}着
                </span>
                {pool.map((id) => {
                  const on = formationSets[pos]?.includes(id);
                  return (
                    <button
                      key={id}
                      type="button"
                      onClick={() => toggleFormation(pos, id)}
                      className="cursor-pointer rounded-md px-2 py-0.5 text-xs tabular-nums transition-all duration-150"
                      style={{
                        background: on ? "rgba(59,130,246,0.18)" : "rgba(255,255,255,0.03)",
                        color: on ? "var(--text-primary)" : "var(--text-muted)",
                        border: on ? "1px solid var(--accent)" : "1px solid var(--border)",
                      }}
                    >
                      {labelOf(id)}
                    </button>
                  );
                })}
              </div>
            ))}
          </div>
        </details>
      )}

      {/* 組数比較 */}
      <div className="overflow-hidden rounded-lg" style={{ border: "1px solid var(--border)" }}>
        <table className="w-full text-sm">
          <thead>
            <tr
              className="text-left text-[10px] font-semibold uppercase tracking-wider"
              style={{ backgroundColor: "rgba(255,255,255,0.02)", color: "var(--text-muted)" }}
            >
              <th className="px-4 py-2">買い方</th>
              <th className="px-4 py-2 text-right">組数</th>
              <th className="px-4 py-2 text-right">100円/点 合計</th>
              <th className="px-4 py-2">説明</th>
            </tr>
          </thead>
          <tbody>
            {METHODS.map((m) => {
              const count = counts[m.value];
              const disabled =
                (m.value === "normal" && picks > 1 && count === 0) ||
                (m.value !== "normal" && picks === 1) ||
                count === 0;
              const isActive = activeMethod === m.value;
              return (
                <tr
                  key={m.value}
                  onClick={() => !disabled && setActiveMethod(m.value)}
                  className="transition-colors duration-150"
                  style={{
                    borderTop: "1px solid var(--border)",
                    cursor: disabled ? "default" : "pointer",
                    backgroundColor: isActive ? "rgba(59,130,246,0.08)" : "transparent",
                    opacity: disabled ? 0.4 : 1,
                  }}
                >
                  <td className="px-4 py-2.5 font-medium" style={{ color: "var(--text-primary)" }}>
                    <span className="inline-flex items-center gap-1.5">
                      {isActive && !disabled && (
                        <span
                          className="inline-block h-1.5 w-1.5 rounded-full"
                          style={{ backgroundColor: "var(--accent)" }}
                        />
                      )}
                      {m.label}
                    </span>
                  </td>
                  <td
                    className="px-4 py-2.5 text-right font-bold tabular-nums"
                    style={{ color: count > 0 ? "var(--accent)" : "var(--text-muted)" }}
                  >
                    {count > 0 ? `${count.toLocaleString()}点` : "—"}
                  </td>
                  <td
                    className="px-4 py-2.5 text-right tabular-nums"
                    style={{ color: "var(--text-secondary)" }}
                  >
                    {count > 0 ? `${(count * 100).toLocaleString()}円` : "—"}
                  </td>
                  <td className="px-4 py-2.5 text-xs" style={{ color: "var(--text-muted)" }}>
                    {m.desc}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      {/* 各組オッズ一覧 */}
      <div>
        <div className="mb-2 flex items-center justify-between">
          <h3 className="text-xs font-bold" style={{ color: "var(--text-primary)" }}>
            {METHODS.find((m) => m.value === activeMethod)?.label} の組み合わせオッズ
          </h3>
          <div className="flex items-center gap-2">
            {oddsStatus && STATUS_LABEL[oddsStatus] && (
              <span
                className="rounded px-1.5 py-0.5 text-[10px] font-medium"
                style={{
                  backgroundColor: "rgba(255,255,255,0.05)",
                  color: "var(--text-secondary)",
                }}
              >
                {STATUS_LABEL[oddsStatus]}オッズ
              </span>
            )}
            {oddsDatetime && (
              <span className="text-[10px]" style={{ color: "var(--text-muted)" }}>
                {oddsDatetime}
              </span>
            )}
          </div>
        </div>

        {/* 統計サマリー */}
        {comboRows.length > 0 && (
          <div className="mb-2 grid grid-cols-2 gap-2 sm:grid-cols-4">
            {[
              { label: "組数", value: `${stats.count.toLocaleString()}点` },
              {
                label: "最小オッズ",
                value: stats.min != null ? `${stats.min.toFixed(1)}倍` : "—",
              },
              {
                label: "最大オッズ",
                value: stats.max != null ? `${stats.max.toFixed(1)}倍` : "—",
              },
              {
                label: "平均オッズ",
                value: stats.avg != null ? `${stats.avg.toFixed(1)}倍` : "—",
              },
            ].map((s) => (
              <div
                key={s.label}
                className="rounded-lg px-3 py-2"
                style={{ backgroundColor: "rgba(255,255,255,0.03)", border: "1px solid var(--border)" }}
              >
                <p className="text-[10px]" style={{ color: "var(--text-muted)" }}>
                  {s.label}
                </p>
                <p className="text-sm font-bold tabular-nums" style={{ color: "var(--text-primary)" }}>
                  {s.value}
                </p>
              </div>
            ))}
          </div>
        )}

        {oddsLoading && (
          <p className="py-4 text-center text-xs" style={{ color: "var(--text-muted)" }}>
            オッズ取得中...
          </p>
        )}
        {!oddsLoading && oddsError && (
          <p className="py-4 text-center text-xs" style={{ color: "var(--text-muted)" }}>
            {oddsError}
          </p>
        )}

        {!oddsLoading && comboRows.length > 0 && (
          <div
            className="max-h-80 overflow-auto rounded-lg"
            style={{ border: "1px solid var(--border)" }}
          >
            <table className="w-full text-sm">
              <thead className="sticky top-0">
                <tr
                  className="text-left text-[10px] font-semibold uppercase tracking-wider"
                  style={{ backgroundColor: "var(--bg-elevated)", color: "var(--text-muted)" }}
                >
                  <th className="px-4 py-2">組み合わせ</th>
                  <th className="px-4 py-2 text-right">オッズ</th>
                  <th className="px-4 py-2 text-right">払戻目安(100円)</th>
                </tr>
              </thead>
              <tbody>
                {comboRows.map((r, i) => {
                  const oddsText =
                    r.oddsLow != null && r.oddsHigh != null && r.oddsLow !== r.oddsHigh
                      ? `${r.oddsLow.toFixed(1)}〜${r.oddsHigh.toFixed(1)}倍`
                      : r.odds != null
                        ? `${r.odds.toFixed(1)}倍`
                        : "—";
                  const payout = r.odds != null ? Math.floor(r.odds * 100) : null;
                  return (
                    <tr
                      key={i}
                      style={{
                        borderTop: i === 0 ? "none" : "1px solid var(--border)",
                      }}
                    >
                      <td
                        className="px-4 py-2 font-medium tabular-nums"
                        style={{ color: "var(--text-primary)" }}
                      >
                        {r.label}
                      </td>
                      <td
                        className="px-4 py-2 text-right font-semibold tabular-nums"
                        style={{
                          color:
                            r.odds != null && r.odds <= 10
                              ? "var(--accent)"
                              : "var(--text-secondary)",
                        }}
                      >
                        {oddsText}
                      </td>
                      <td
                        className="px-4 py-2 text-right tabular-nums"
                        style={{ color: "var(--text-muted)" }}
                      >
                        {payout != null ? `${payout.toLocaleString()}円` : "—"}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}

        {!oddsLoading && !oddsError && comboRows.length === 0 && pool.length > 0 && (
          <p className="py-4 text-center text-xs" style={{ color: "var(--text-muted)" }}>
            この買い方で表示できる組み合わせがありません（条件を確認してください）
          </p>
        )}
      </div>
    </div>
  );
}
