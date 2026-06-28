"use client";

import React, { useMemo, useState } from "react";
import {
  fetchHedge,
  type BetSuggestionItem,
  type BetSuggestionResponse,
  type RaceEntry,
} from "@/lib/api";
import { wakuColor } from "./ComboBadges";

const BET_JA: Record<string, string> = {
  tansho: "単勝", fukusho: "複勝", umaren: "馬連",
  wide: "ワイド", umatan: "馬単", trio: "三連複", trifecta: "三連単",
};
const BET_OPTIONS = ["tansho", "fukusho", "umaren", "wide", "umatan", "trio", "trifecta"];
const QUICK = [2000, 5000, 10000];

type Props = { raceId: string; entries: RaceEntry[] };

export default function HedgePanel({ raceId, entries }: Props) {
  const [budgetStr, setBudgetStr] = useState("6000");
  const [ratio, setRatio] = useState(0.5); // 本命比率
  const [honmeiBet, setHonmeiBet] = useState("trio");
  const [anaBet, setAnaBet] = useState("wide");
  const [result, setResult] = useState<BetSuggestionResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const budget = parseInt(budgetStr.replace(/[^0-9]/g, ""), 10) || 0;
  const invalid = budget < 200;

  const bracketByPost = useMemo(() => {
    const m: Record<number, number | null> = {};
    for (const e of entries) if (e.post_position != null) m[e.post_position] = e.bracket_number;
    return m;
  }, [entries]);

  async function run() {
    if (invalid) return;
    setLoading(true);
    setError(null);
    try {
      setResult(
        await fetchHedge(raceId, {
          budget,
          honmei_ratio: ratio,
          honmei_bet: honmeiBet,
          ana_bet: anaBet,
        }),
      );
    } catch (e) {
      setError(e instanceof Error ? e.message : "取得に失敗しました");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="glass-card overflow-hidden">
      <div className="flex items-center gap-2 px-4 py-3" style={{ borderBottom: "1px solid var(--border)" }}>
        <div className="w-1 self-stretch rounded-full" style={{ backgroundColor: "var(--accent)" }} />
        <h2 className="text-base font-semibold" style={{ color: "var(--text-primary)" }}>
          荒れ対応ヘッジ（本命2頭マルチ軸で広くカバー）
        </h2>
      </div>

      <div className="p-4 space-y-3">
        <p className="text-xs" style={{ color: "var(--text-secondary)" }}>
          メイン＝本命2頭マルチ軸のフォーメーションで順当〜やや波乱を連続カバー（本命のどちらか1頭絡みで的中）。
          荒れ度が高いときは穴3頭の保険を追加。各サイドともガミ防止配分。穴検出に最大1〜2分かかります。
        </p>

        <div>
          <div className="flex items-center gap-2 flex-wrap">
            <label className="text-sm" style={{ color: "var(--text-secondary)" }}>予算</label>
            <input
              type="text" inputMode="numeric" value={budgetStr}
              onChange={(e) => setBudgetStr(e.target.value)} aria-invalid={invalid}
              className="w-28 rounded-md px-2 py-1 text-sm outline-none"
              style={{
                backgroundColor: "var(--bg-secondary)",
                border: `1px solid ${invalid ? "#dc2626" : "var(--border)"}`,
                boxShadow: invalid ? "0 0 0 2px rgba(220,38,38,0.2)" : "none",
                color: "var(--text-primary)",
              }}
            />
            <span className="text-sm" style={{ color: "var(--text-secondary)" }}>円</span>
            {QUICK.map((b) => (
              <button key={b} onClick={() => setBudgetStr(String(b))}
                className="rounded-full px-2.5 py-0.5 text-xs"
                style={{
                  backgroundColor: budget === b ? "var(--accent)" : "var(--bg-secondary)",
                  color: budget === b ? "#fff" : "var(--text-secondary)",
                  border: "1px solid var(--border)",
                }}>
                {b.toLocaleString()}
              </button>
            ))}
          </div>
          {invalid && <p className="text-xs mt-1" style={{ color: "#dc2626" }}>200円以上を入力してください</p>}
        </div>

        {/* 券種選択 */}
        <div className="flex items-center gap-3 flex-wrap">
          <label className="text-sm flex items-center gap-1" style={{ color: "var(--text-secondary)" }}>
            メイン
            <select
              value={honmeiBet}
              onChange={(e) => setHonmeiBet(e.target.value)}
              className="rounded-md px-2 py-1 text-sm"
              style={{ backgroundColor: "var(--bg-secondary)", border: "1px solid var(--border)", color: "var(--text-primary)" }}
            >
              {BET_OPTIONS.map((b) => (
                <option key={b} value={b} style={{ backgroundColor: "#1e2530", color: "#ffffff" }}>
                  {BET_JA[b]}
                </option>
              ))}
            </select>
          </label>
          <label className="text-sm flex items-center gap-1" style={{ color: "var(--text-secondary)" }}>
            保険(大波乱)
            <select
              value={anaBet}
              onChange={(e) => setAnaBet(e.target.value)}
              className="rounded-md px-2 py-1 text-sm"
              style={{ backgroundColor: "var(--bg-secondary)", border: "1px solid var(--border)", color: "var(--text-primary)" }}
            >
              {BET_OPTIONS.map((b) => (
                <option key={b} value={b} style={{ backgroundColor: "#1e2530", color: "#ffffff" }}>
                  {BET_JA[b]}
                </option>
              ))}
            </select>
          </label>
        </div>

        {/* 配分 */}
        <div>
          <div className="flex items-center justify-between text-xs" style={{ color: "var(--text-secondary)" }}>
            <span>
              配分: メイン({BET_JA[honmeiBet]}) {Math.round(ratio * 100)}% / 保険({BET_JA[anaBet]}) {Math.round((1 - ratio) * 100)}%
            </span>
          </div>
          <input
            type="range" min={0} max={100} step={10}
            value={Math.round(ratio * 100)}
            onChange={(e) => setRatio(Number(e.target.value) / 100)}
            className="w-full mt-1"
          />
        </div>

        <button onClick={run} disabled={invalid || loading}
          className="rounded-md px-4 py-2 text-sm font-semibold w-full sm:w-auto"
          style={{ backgroundColor: "var(--accent)", color: "#fff", opacity: invalid || loading ? 0.5 : 1 }}>
          {loading ? "穴検出＋オッズ取得中…(最大1〜2分)" : "ヘッジ買い目を作成"}
        </button>

        {error && <p className="text-sm" style={{ color: "#dc2626" }}>{error}</p>}

        {result && (
          <div className="space-y-2 pt-1">
            {result.coverage_note && (
              <p className="text-xs rounded-md p-2"
                style={{ backgroundColor: "var(--bg-secondary)", color: "var(--text-secondary)" }}>
                {result.coverage_note}
              </p>
            )}
            <div className="flex items-center gap-2 flex-wrap text-xs" style={{ color: "var(--text-secondary)" }}>
              <span>配分 {result.total_allocated.toLocaleString()}/{result.budget.toLocaleString()}円</span>
              <span>・{result.odds_live ? "ライブオッズ" : "オッズ推定"}</span>
            </div>
            {result.suggestions.length === 0 ? (
              <p className="text-sm" style={{ color: "var(--text-secondary)" }}>
                {result.message ?? "買い目を作成できませんでした"}
              </p>
            ) : (
              result.suggestions.map((s, i) => (
                <LegCard key={i} s={s} bracketByPost={bracketByPost} names={result.names} />
              ))
            )}
            <p className="text-[11px] leading-snug pt-1" style={{ color: "var(--text-secondary)" }}>
              ※「ガミ無」=当たれば投資以上。完全カバーではなく、控除率20%で利益は保証されません。
            </p>
          </div>
        )}
      </div>
    </div>
  );
}

function Badge({ post, bracket }: { post: number; bracket: number | null }) {
  const c = wakuColor(bracket);
  return (
    <span className="inline-flex h-5 min-w-[1.25rem] items-center justify-center rounded px-1 text-[11px] font-bold tabular-nums"
      style={{ backgroundColor: c.bg, color: c.fg, border: "1px solid rgba(0,0,0,0.25)" }}>
      {post}
    </span>
  );
}

function LegCard({
  s, bracketByPost, names,
}: {
  s: BetSuggestionItem;
  bracketByPost: Record<number, number | null>;
  names: Record<string, string>;
}) {
  const stake = s.stake_min === s.stake_max ? `${s.stake_min}円` : `${s.stake_min}〜${s.stake_max}円`;
  const axisSet = new Set(s.axis ?? []);
  const combos = s.combos ?? [];
  return (
    <div className="rounded-lg p-3" style={{ backgroundColor: "var(--bg-secondary)", border: "1px solid var(--border)" }}>
      <div className="flex items-center gap-2 flex-wrap">
        <span className="text-sm font-bold" style={{ color: "var(--text-primary)" }}>
          {BET_JA[s.bet_type] ?? s.bet_type}
        </span>
        <span className="rounded px-1.5 py-0.5 text-[11px] font-medium"
          style={{ backgroundColor: s.gami_free ? "#f0fdf4" : "#fef2f2", color: s.gami_free ? "#15803d" : "#b91c1c" }}>
          {s.gami_free ? "ガミ無" : "ガミ有"}
        </span>
      </div>
      <p className="text-xs mt-1" style={{ color: "var(--text-secondary)" }}>{s.rationale}</p>
      <div className="text-sm mt-1.5" style={{ color: "var(--text-primary)" }}>
        {s.points}点 (1点{stake}) = <b>計{s.cost.toLocaleString()}円</b>
        {s.dropped_points > 0 && (
          <span className="text-xs" style={{ color: "var(--text-secondary)" }}> / ガミ除外{s.dropped_points}点</span>
        )}
      </div>
      <div className="text-xs mt-0.5" style={{ color: "var(--text-secondary)" }}>
        想定的中率 {(s.hit_rate * 100).toFixed(1)}% / 払戻 {s.payout_min.toLocaleString()}〜{s.payout_max.toLocaleString()}円
        {s.odds_estimated ? "(推定)" : ""}
      </div>
      {s.axis && s.axis.length > 0 && (
        <div className="flex items-center gap-1 flex-wrap mt-1.5">
          <span className="text-xs" style={{ color: "var(--text-secondary)" }}>軸</span>
          {s.axis.map((p, i) => (
            <span key={i} className="inline-flex items-center gap-0.5" title={names[String(p)] ?? ""}>
              <Badge post={p} bracket={bracketByPost[p] ?? null} />
            </span>
          ))}
        </div>
      )}

      {/* 実際に買う組み合わせ一覧 */}
      {combos.length > 0 && (
        <div className="mt-2 space-y-1">
          <div className="text-[11px]" style={{ color: "var(--text-secondary)" }}>買い目（{combos.length}点）</div>
          {combos.map((c, i) => (
            <div key={i} className="flex items-center gap-1.5 flex-wrap text-xs">
              <div className="flex items-center gap-0.5">
                {c.combo.map((p, j) => (
                  <React.Fragment key={j}>
                    {j > 0 && <span style={{ color: "var(--text-secondary)" }}>-</span>}
                    <span title={names[String(p)] ?? ""} className="inline-flex items-center">
                      <Badge post={p} bracket={bracketByPost[p] ?? null} />
                      {axisSet.has(p) && <span className="text-[9px] ml-0.5" style={{ color: "var(--accent)" }}>軸</span>}
                    </span>
                  </React.Fragment>
                ))}
              </div>
              <span className="tabular-nums" style={{ color: "var(--text-secondary)" }}>
                {c.stake.toLocaleString()}円
                {c.odds != null && ` × ${c.odds.toFixed(1)}倍`}
                {c.payout != null && ` = ${c.payout.toLocaleString()}円`}
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
