"use client";

import { useEffect, useState, useCallback, useMemo } from "react";
import Link from "next/link";
import {
  fetchBets,
  fetchBetSummary,
  updateBet,
  type BetRecord,
  type BetRaceInfo,
  type BetSummary,
} from "@/lib/api";
import Pagination from "@/components/Pagination";
import { wakuColor } from "@/components/ComboBadges";

const BET_TYPE_LABELS: Record<string, string> = {
  tansho: "単勝",
  fukusho: "複勝",
  wakuren: "枠連",
  umaren: "馬連",
  umatan: "馬単",
  wide: "ワイド",
  sanrenpuku: "3連複",
  sanrentan: "3連単",
};

const ORDERED_BETS = new Set(["umatan", "sanrentan"]);
const POSITION_MARKS = ["", "1着", "2着", "3着"];

type RaceGroup = {
  key: string;
  info: BetRaceInfo | null;
  bets: BetRecord[];
};

export default function BetsPage() {
  const [items, setItems] = useState<BetRecord[]>([]);
  const [summary, setSummary] = useState<BetSummary | null>(null);
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [loading, setLoading] = useState(true);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editPayout, setEditPayout] = useState<string>("");
  const [editHit, setEditHit] = useState<boolean>(false);

  const loadData = useCallback(async () => {
    setLoading(true);
    try {
      const [betsRes, summaryRes] = await Promise.all([
        fetchBets({ page, per_page: 100 }),
        fetchBetSummary(),
      ]);
      setItems(betsRes.items);
      setTotalPages(Math.max(1, Math.ceil(betsRes.total / 100)));
      setSummary(summaryRes);
    } catch {
      // ignore
    } finally {
      setLoading(false);
    }
  }, [page]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  // レースごとにまとめる（出現順を維持）
  const groups = useMemo<RaceGroup[]>(() => {
    const map = new Map<string, RaceGroup>();
    const order: string[] = [];
    for (const bet of items) {
      const key = bet.race_id ?? `nor-${bet.id}`;
      if (!map.has(key)) {
        map.set(key, { key, info: bet.race_info, bets: [] });
        order.push(key);
      }
      map.get(key)!.bets.push(bet);
    }
    return order.map((k) => map.get(k)!);
  }, [items]);

  function startEdit(bet: BetRecord) {
    setEditingId(bet.id);
    setEditPayout(bet.actual_payout !== null ? String(bet.actual_payout) : "");
    setEditHit(bet.is_hit ?? false);
  }

  async function saveEdit() {
    if (!editingId) return;
    await updateBet(editingId, {
      actual_payout: editPayout ? Number(editPayout) : null,
      is_hit: editHit,
    });
    setEditingId(null);
    loadData();
  }

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold" style={{ color: "var(--text-primary)" }}>
        収支管理
      </h1>

      {/* Summary cards */}
      {summary && summary.total_bets > 0 && (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {[
            { label: "総賭け金", value: `¥${summary.total_amount.toLocaleString()}` },
            { label: "総回収", value: `¥${summary.total_payout.toLocaleString()}` },
            {
              label: "回収率",
              value: `${summary.recovery_rate.toFixed(1)}%`,
              color: summary.recovery_rate >= 100 ? "var(--green)" : "var(--red)",
            },
            {
              label: "的中率",
              value: `${summary.hit_rate.toFixed(1)}% (${summary.hit_count}/${summary.total_bets})`,
            },
          ].map((card) => (
            <div key={card.label} className="glass-card p-4 text-center">
              <div className="text-xs font-medium" style={{ color: "var(--text-secondary)" }}>
                {card.label}
              </div>
              <div
                className="mt-1 text-xl font-bold tabular-nums"
                style={{ color: card.color ?? "var(--text-primary)" }}
              >
                {card.value}
              </div>
            </div>
          ))}
        </div>
      )}

      {loading ? (
        <div className="glass-card p-8 text-center" style={{ color: "var(--text-muted)" }}>
          読み込み中...
        </div>
      ) : groups.length === 0 ? (
        <div className="glass-card p-8 text-center text-sm" style={{ color: "var(--text-muted)" }}>
          馬券記録がありません。レース詳細ページのシミュレーターから記録できます。
        </div>
      ) : (
        <div className="space-y-4">
          {groups.map((g) => (
            <RaceCard
              key={g.key}
              group={g}
              editingId={editingId}
              editPayout={editPayout}
              editHit={editHit}
              onStartEdit={startEdit}
              onChangePayout={setEditPayout}
              onChangeHit={setEditHit}
              onSave={saveEdit}
              onCancel={() => setEditingId(null)}
            />
          ))}
        </div>
      )}

      {totalPages > 1 && (
        <Pagination page={page} totalPages={totalPages} onPageChange={setPage} />
      )}
    </div>
  );
}

function RaceCard({
  group,
  editingId,
  editPayout,
  editHit,
  onStartEdit,
  onChangePayout,
  onChangeHit,
  onSave,
  onCancel,
}: {
  group: RaceGroup;
  editingId: string | null;
  editPayout: string;
  editHit: boolean;
  onStartEdit: (b: BetRecord) => void;
  onChangePayout: (v: string) => void;
  onChangeHit: (v: boolean) => void;
  onSave: () => void;
  onCancel: () => void;
}) {
  const { info, bets } = group;
  const totalAmount = bets.reduce((s, b) => s + b.amount_yen, 0);
  const totalPayout = bets.reduce((s, b) => s + (b.actual_payout ?? 0), 0);
  const settled = bets.some((b) => b.is_hit !== null);
  const profit = totalPayout - totalAmount;

  // 馬名 -> {馬番, 枠}
  const nameMap = new Map<string, { post: number | null; bracket: number | null }>();
  for (const e of info?.entries ?? []) {
    nameMap.set(e.horse_name, { post: e.post_position, bracket: e.bracket_number });
  }

  return (
    <div className="glass-card overflow-hidden">
      {/* レースヘッダー */}
      <div
        className="flex flex-wrap items-center justify-between gap-2 px-4 py-3"
        style={{ borderBottom: "1px solid var(--border)", backgroundColor: "var(--bg-elevated)" }}
      >
        <div className="min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="text-xs" style={{ color: "var(--text-muted)" }}>
              {bets[0].bet_date}
            </span>
            {info ? (
              <Link
                href={`/races/${info.race_id_str}`}
                className="font-semibold hover:underline"
                style={{ color: "var(--accent)" }}
              >
                {info.racecourse_name ?? ""}
                {info.race_number != null ? ` ${info.race_number}R` : ""}
                {info.race_name ? ` ${info.race_name}` : ""}
              </Link>
            ) : (
              <span className="font-semibold" style={{ color: "var(--text-primary)" }}>
                レース未紐付け
              </span>
            )}
          </div>
          {info && info.result_top3.length > 0 && (
            <div className="mt-0.5 flex items-center gap-2 flex-wrap text-[11px]" style={{ color: "var(--text-muted)" }}>
              {info.result_top3.map((r) => (
                <span key={r.finish_position}>
                  {POSITION_MARKS[r.finish_position] ?? `${r.finish_position}着`} {r.horse_name}
                </span>
              ))}
            </div>
          )}
        </div>
        <div className="text-right text-xs tabular-nums" style={{ color: "var(--text-secondary)" }}>
          <div>
            {bets.length}点 / 賭 ¥{totalAmount.toLocaleString()}
          </div>
          {settled && (
            <div>
              回 ¥{totalPayout.toLocaleString()} ・
              <span
                className="font-semibold ml-1"
                style={{ color: profit >= 0 ? "var(--green)" : "var(--red)" }}
              >
                {profit >= 0 ? "+" : ""}
                {profit.toLocaleString()}
              </span>
            </div>
          )}
        </div>
      </div>

      {/* 馬券一覧 */}
      <div className="divide-y" style={{ borderColor: "var(--border)" }}>
        {bets.map((bet) => {
          const isEditing = editingId === bet.id;
          const tokens = bet.horse_names.split(/[,、]\s*/).filter(Boolean);
          const ordered = ORDERED_BETS.has(bet.bet_type);
          return (
            <div
              key={bet.id}
              className="px-4 py-2.5"
              style={{
                backgroundColor:
                  bet.is_hit === true ? "rgba(63,185,80,0.08)" : undefined,
              }}
            >
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0">
                  {/* 馬券種 + 組み合わせ(枠色馬番 + 馬名) */}
                  <div className="flex items-center gap-2 flex-wrap">
                    <span
                      className="rounded px-1.5 py-0.5 text-[11px] font-semibold shrink-0"
                      style={{ backgroundColor: "var(--accent-muted)", color: "var(--accent)" }}
                    >
                      {BET_TYPE_LABELS[bet.bet_type] ?? bet.bet_type}
                    </span>
                    <span className="inline-flex items-center gap-0.5 flex-wrap">
                      {tokens.map((name, i) => {
                        const m = nameMap.get(name);
                        const c = wakuColor(m?.bracket ?? null);
                        return (
                          <span key={i} className="inline-flex items-center">
                            {i > 0 && (
                              <span className="mx-0.5 text-[10px]" style={{ color: "var(--text-muted)" }}>
                                {ordered ? "→" : "・"}
                              </span>
                            )}
                            {m?.post != null && (
                              <span
                                className="inline-flex h-5 min-w-[1.25rem] items-center justify-center rounded px-1 text-[11px] font-bold tabular-nums mr-1"
                                style={{ backgroundColor: c.bg, color: c.fg, border: "1px solid rgba(0,0,0,0.25)" }}
                              >
                                {m.post}
                              </span>
                            )}
                            <span className="text-sm" style={{ color: "var(--text-primary)" }}>
                              {name}
                            </span>
                          </span>
                        );
                      })}
                    </span>
                  </div>

                  {/* 金額・オッズ・払戻 */}
                  <div className="mt-1 flex items-center gap-3 flex-wrap text-xs tabular-nums" style={{ color: "var(--text-secondary)" }}>
                    <span>掛 ¥{bet.amount_yen.toLocaleString()}</span>
                    <span>
                      オッズ {bet.odds_at_bet !== null ? Number(bet.odds_at_bet).toFixed(1) : "---"}
                    </span>
                    <span>
                      払戻{" "}
                      {isEditing ? (
                        <input
                          type="number"
                          value={editPayout}
                          onChange={(e) => onChangePayout(e.target.value)}
                          className="w-20 rounded px-1 py-0.5 text-xs"
                          style={{
                            backgroundColor: "var(--bg-elevated)",
                            border: "1px solid var(--border-light)",
                            color: "var(--text-primary)",
                          }}
                        />
                      ) : bet.actual_payout !== null ? (
                        `¥${bet.actual_payout.toLocaleString()}`
                      ) : (
                        "---"
                      )}
                    </span>
                    <span>
                      的中{" "}
                      {isEditing ? (
                        <input
                          type="checkbox"
                          checked={editHit}
                          onChange={(e) => onChangeHit(e.target.checked)}
                        />
                      ) : bet.is_hit === true ? (
                        <span style={{ color: "var(--green)" }}>○</span>
                      ) : bet.is_hit === false ? (
                        <span style={{ color: "var(--red)" }}>×</span>
                      ) : (
                        "---"
                      )}
                    </span>
                  </div>
                </div>

                {/* 操作 */}
                <div className="shrink-0">
                  {isEditing ? (
                    <div className="flex gap-2">
                      <button
                        type="button"
                        onClick={onSave}
                        className="cursor-pointer text-xs font-medium"
                        style={{ color: "var(--accent)" }}
                      >
                        保存
                      </button>
                      <button
                        type="button"
                        onClick={onCancel}
                        className="cursor-pointer text-xs"
                        style={{ color: "var(--text-muted)" }}
                      >
                        取消
                      </button>
                    </div>
                  ) : (
                    <button
                      type="button"
                      onClick={() => onStartEdit(bet)}
                      className="cursor-pointer text-xs"
                      style={{ color: "var(--text-secondary)" }}
                    >
                      結果入力
                    </button>
                  )}
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
