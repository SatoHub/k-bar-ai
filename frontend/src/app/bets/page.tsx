"use client";

import { useEffect, useState, useCallback } from "react";
import Link from "next/link";
import {
  fetchBets,
  fetchBetSummary,
  updateBet,
  type BetRecord,
  type BetSummary,
} from "@/lib/api";
import Pagination from "@/components/Pagination";

const BET_TYPE_LABELS: Record<string, string> = {
  tansho: "単勝",
  fukusho: "複勝",
  umaren: "馬連",
  umatan: "馬単",
  wide: "ワイド",
  sanrenpuku: "3連複",
  sanrentan: "3連単",
};

const POSITION_MARKS = ["", "1着", "2着", "3着"];

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
        fetchBets({ page, per_page: 20 }),
        fetchBetSummary(),
      ]);
      setItems(betsRes.items);
      setTotalPages(Math.max(1, Math.ceil(betsRes.total / 20)));
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
      <h1
        className="text-2xl font-bold"
        style={{ color: "var(--text-primary)" }}
      >
        収支管理
      </h1>

      {/* Summary cards */}
      {summary && summary.total_bets > 0 && (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {[
            {
              label: "総賭け金",
              value: `¥${summary.total_amount.toLocaleString()}`,
            },
            {
              label: "総回収",
              value: `¥${summary.total_payout.toLocaleString()}`,
            },
            {
              label: "回収率",
              value: `${summary.recovery_rate.toFixed(1)}%`,
              color:
                summary.recovery_rate >= 100 ? "var(--green)" : "var(--red)",
            },
            {
              label: "的中率",
              value: `${summary.hit_rate.toFixed(1)}% (${summary.hit_count}/${summary.total_bets})`,
            },
          ].map((card) => (
            <div key={card.label} className="glass-card p-4 text-center">
              <div
                className="text-xs font-medium"
                style={{ color: "var(--text-secondary)" }}
              >
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

      {/* Bet history table */}
      <div className="glass-card overflow-hidden">
        <div
          className="px-4 py-3"
          style={{ borderBottom: "1px solid var(--border)" }}
        >
          <h2
            className="text-base font-semibold"
            style={{ color: "var(--text-primary)" }}
          >
            馬券履歴
          </h2>
        </div>

        {loading ? (
          <div
            className="p-8 text-center"
            style={{ color: "var(--text-muted)" }}
          >
            読み込み中...
          </div>
        ) : items.length === 0 ? (
          <div
            className="p-8 text-center text-sm"
            style={{ color: "var(--text-muted)" }}
          >
            馬券記録がありません。レース詳細ページのシミュレーターから記録できます。
          </div>
        ) : (
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
                  <th className="px-3 py-2">レース</th>
                  <th className="px-3 py-2">馬券種</th>
                  <th className="hidden sm:table-cell px-3 py-2">馬名</th>
                  <th className="px-3 py-2 text-right">掛け金</th>
                  <th className="hidden sm:table-cell px-3 py-2 text-right">オッズ</th>
                  <th className="hidden sm:table-cell px-3 py-2 text-right">払戻</th>
                  <th className="px-3 py-2 text-center">的中</th>
                  <th className="hidden lg:table-cell px-3 py-2">レース結果</th>
                  <th className="px-3 py-2">操作</th>
                </tr>
              </thead>
              <tbody>
                {items.map((bet) => {
                  const isEditing = editingId === bet.id;
                  const ri = bet.race_info;
                  return (
                    <tr
                      key={bet.id}
                      style={{
                        borderBottom: "1px solid var(--border)",
                        backgroundColor:
                          bet.is_hit === true
                            ? "rgba(63,185,80,0.08)"
                            : undefined,
                      }}
                    >
                      {/* 日付 */}
                      <td
                        className="px-3 py-2"
                        style={{ color: "var(--text-secondary)" }}
                      >
                        {bet.bet_date}
                      </td>

                      {/* レース情報 */}
                      <td className="px-3 py-2">
                        {ri ? (
                          <Link
                            href={`/races/${ri.race_id_str}`}
                            className="hover:underline"
                            style={{ color: "var(--accent)" }}
                          >
                            <span className="font-medium">
                              {ri.racecourse_name ?? ""}
                              {ri.race_number != null ? ` ${ri.race_number}R` : ""}
                            </span>
                            {ri.race_name && (
                              <span
                                className="ml-1 text-xs"
                                style={{ color: "var(--text-muted)" }}
                              >
                                {ri.race_name}
                              </span>
                            )}
                          </Link>
                        ) : (
                          <span style={{ color: "var(--text-muted)" }}>---</span>
                        )}
                      </td>

                      {/* 馬券種 */}
                      <td className="px-3 py-2">
                        {BET_TYPE_LABELS[bet.bet_type] ?? bet.bet_type}
                      </td>

                      {/* 馬名 */}
                      <td
                        className="hidden sm:table-cell px-3 py-2 font-medium"
                        style={{ color: "var(--text-primary)" }}
                      >
                        {bet.horse_names}
                      </td>

                      {/* 掛け金 */}
                      <td className="px-3 py-2 text-right tabular-nums">
                        ¥{bet.amount_yen.toLocaleString()}
                      </td>

                      {/* オッズ */}
                      <td className="hidden sm:table-cell px-3 py-2 text-right tabular-nums">
                        {bet.odds_at_bet !== null
                          ? Number(bet.odds_at_bet).toFixed(1)
                          : "---"}
                      </td>

                      {/* 払戻 */}
                      <td className="hidden sm:table-cell px-3 py-2 text-right tabular-nums">
                        {isEditing ? (
                          <input
                            type="number"
                            value={editPayout}
                            onChange={(e) => setEditPayout(e.target.value)}
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
                      </td>

                      {/* 的中 */}
                      <td className="px-3 py-2 text-center">
                        {isEditing ? (
                          <input
                            type="checkbox"
                            checked={editHit}
                            onChange={(e) => setEditHit(e.target.checked)}
                          />
                        ) : bet.is_hit === true ? (
                          <span style={{ color: "var(--green)" }}>○</span>
                        ) : bet.is_hit === false ? (
                          <span style={{ color: "var(--red)" }}>×</span>
                        ) : (
                          "---"
                        )}
                      </td>

                      {/* レース結果 (上位3着) */}
                      <td className="hidden lg:table-cell px-3 py-2">
                        {ri && ri.result_top3.length > 0 ? (
                          <div className="flex flex-col gap-0.5">
                            {ri.result_top3.map((r) => (
                              <span
                                key={r.finish_position}
                                className="text-xs"
                                style={{ color: "var(--text-secondary)" }}
                              >
                                <span
                                  className="inline-block w-7 text-right font-medium tabular-nums mr-1"
                                  style={{
                                    color:
                                      r.finish_position === 1
                                        ? "var(--yellow)"
                                        : r.finish_position === 2
                                          ? "var(--text-secondary)"
                                          : "var(--text-muted)",
                                  }}
                                >
                                  {POSITION_MARKS[r.finish_position] ?? `${r.finish_position}着`}
                                </span>
                                {r.horse_name}
                              </span>
                            ))}
                          </div>
                        ) : (
                          <span
                            className="text-xs"
                            style={{ color: "var(--text-muted)" }}
                          >
                            未確定
                          </span>
                        )}
                      </td>

                      {/* 操作 */}
                      <td className="px-3 py-2">
                        {isEditing ? (
                          <div className="flex gap-2">
                            <button
                              type="button"
                              onClick={saveEdit}
                              className="cursor-pointer text-xs font-medium"
                              style={{ color: "var(--accent)" }}
                            >
                              保存
                            </button>
                            <button
                              type="button"
                              onClick={() => setEditingId(null)}
                              className="cursor-pointer text-xs"
                              style={{ color: "var(--text-muted)" }}
                            >
                              取消
                            </button>
                          </div>
                        ) : (
                          <button
                            type="button"
                            onClick={() => startEdit(bet)}
                            className="cursor-pointer text-xs"
                            style={{ color: "var(--text-secondary)" }}
                          >
                            結果入力
                          </button>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {totalPages > 1 && (
        <Pagination
          page={page}
          totalPages={totalPages}
          onPageChange={setPage}
        />
      )}
    </div>
  );
}
