"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { fetchBetSummary, settleBets, type BetSummary } from "@/lib/api";

export default function BetSummaryCard() {
  const [summary, setSummary] = useState<BetSummary | null>(null);
  const [settling, setSettling] = useState(false);

  const load = useCallback(() => {
    fetchBetSummary()
      .then(setSummary)
      .catch(() => {});
  }, []);

  useEffect(() => {
    // サマリー取得時にバックエンドが自動判定するので、開くだけで最新に
    load();
  }, [load]);

  const handleSettle = useCallback(async () => {
    setSettling(true);
    try {
      await settleBets();
      load();
    } catch {
      // ignore
    } finally {
      setSettling(false);
    }
  }, [load]);

  if (!summary || summary.total_bets === 0) return null;

  return (
    <div className="glass-card p-5">
      <div className="flex items-center justify-between mb-3">
        <h3
          className="text-sm font-semibold"
          style={{ color: "var(--text-primary)" }}
        >
          収支サマリー
        </h3>
        <div className="flex items-center gap-3">
          <button
            type="button"
            onClick={handleSettle}
            disabled={settling}
            className="text-xs cursor-pointer"
            style={{ color: "var(--text-muted)", opacity: settling ? 0.5 : 1 }}
            title="結果が出ている馬券の当落を再判定して収支に反映"
          >
            {settling ? "判定中..." : "再判定"}
          </button>
          <Link
            href="/bets"
            className="text-xs cursor-pointer"
            style={{ color: "var(--accent)" }}
          >
            詳細を見る &rarr;
          </Link>
        </div>
      </div>
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <div>
          <div
            className="text-xs"
            style={{ color: "var(--text-secondary)" }}
          >
            総賭け金
          </div>
          <div
            className="text-sm font-bold tabular-nums"
            style={{ color: "var(--text-primary)" }}
          >
            ¥{summary.total_amount.toLocaleString()}
          </div>
        </div>
        <div>
          <div
            className="text-xs"
            style={{ color: "var(--text-secondary)" }}
          >
            総回収
          </div>
          <div
            className="text-sm font-bold tabular-nums"
            style={{ color: "var(--text-primary)" }}
          >
            ¥{summary.total_payout.toLocaleString()}
          </div>
        </div>
        <div>
          <div
            className="text-xs"
            style={{ color: "var(--text-secondary)" }}
          >
            回収率
          </div>
          <div
            className="text-sm font-bold tabular-nums"
            style={{
              color:
                summary.recovery_rate >= 100
                  ? "var(--green)"
                  : "var(--red)",
            }}
          >
            {summary.recovery_rate.toFixed(1)}%
          </div>
        </div>
        <div>
          <div
            className="text-xs"
            style={{ color: "var(--text-secondary)" }}
          >
            的中率
          </div>
          <div
            className="text-sm font-bold tabular-nums"
            style={{ color: "var(--text-primary)" }}
          >
            {summary.hit_rate.toFixed(1)}%
          </div>
        </div>
      </div>
    </div>
  );
}
