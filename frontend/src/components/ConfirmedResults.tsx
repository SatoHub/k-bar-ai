"use client";

/**
 * 確定オッズ・払戻（JRA-VAN由来）表示コンポーネント。
 * 自己完結テーブル confirmed_win_odds / confirmed_payouts を GET /races/{id}/confirmed で取得。
 * 払戻は券種ごとに枠色バッジ（馬番）+ 金額/人気で表示。確定単勝オッズは馬番順の小表で表示。
 */

import React from "react";
import type {
  ConfirmedDataResponse,
  ConfirmedPayouts,
  RaceEntry,
} from "@/lib/api";
import { wakuColor } from "./ComboBadges";

// "010204" → [1, 2, 4]
function parseKumi(kumi: string | null): number[] {
  if (!kumi) return [];
  const out: number[] = [];
  for (let i = 0; i + 2 <= kumi.length; i += 2) {
    const n = Number(kumi.slice(i, i + 2));
    if (!Number.isNaN(n) && n > 0) out.push(n);
  }
  return out;
}

function UmabanBadges({
  umabans,
  entries,
  ordered,
}: {
  umabans: number[];
  entries: RaceEntry[];
  ordered: boolean;
}) {
  return (
    <span className="inline-flex flex-wrap items-center gap-x-0.5 gap-y-1">
      {umabans.map((num, i) => {
        const e = entries.find((en) => en.post_position === num);
        const c = wakuColor(e?.bracket_number ?? null);
        return (
          <span key={i} className="inline-flex items-center">
            {i > 0 && (
              <span
                className="mx-0.5 text-[10px]"
                style={{ color: "var(--text-muted)" }}
              >
                {ordered ? "→" : "-"}
              </span>
            )}
            <span
              title={e?.horse.name ?? String(num)}
              className="inline-flex h-5 min-w-[1.25rem] items-center justify-center rounded px-1 text-[11px] font-bold tabular-nums"
              style={{
                backgroundColor: c.bg,
                color: c.fg,
                border: "1px solid rgba(0,0,0,0.25)",
              }}
            >
              {num}
            </span>
          </span>
        );
      })}
    </span>
  );
}

function yen(n: number | null | undefined): string {
  if (n == null) return "—";
  return `${n.toLocaleString()}円`;
}

type Row = {
  label: string;
  kumi: string | null;
  pay: number | null;
  ninki?: number | null;
  ordered: boolean;
};

function PayoutRows({
  payouts,
  entries,
}: {
  payouts: ConfirmedPayouts;
  entries: RaceEntry[];
}) {
  const rows: Row[] = [
    { label: "単勝", kumi: payouts.tan_umaban, pay: payouts.tan_pay, ninki: payouts.tan_ninki, ordered: false },
    { label: "複勝", kumi: payouts.fuku_umaban, pay: payouts.fuku_pay, ninki: payouts.fuku_ninki, ordered: false },
    { label: "馬連", kumi: payouts.umaren_kumi, pay: payouts.umaren_pay, ordered: false },
    { label: "ワイド", kumi: payouts.wide_kumi, pay: payouts.wide_pay, ordered: false },
    { label: "馬単", kumi: payouts.umatan_kumi, pay: payouts.umatan_pay, ordered: true },
    { label: "三連複", kumi: payouts.sanrenfuku_kumi, pay: payouts.sanrenfuku_pay, ordered: false },
    { label: "三連単", kumi: payouts.sanrentan_kumi, pay: payouts.sanrentan_pay, ordered: true },
  ].filter((r) => r.kumi || r.pay != null);

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <tbody>
          {rows.map((r) => (
            <tr
              key={r.label}
              className="border-b"
              style={{ borderColor: "var(--border-subtle, rgba(255,255,255,0.06))" }}
            >
              <td
                className="whitespace-nowrap py-1.5 pr-3 text-xs font-semibold"
                style={{ color: "var(--text-muted)" }}
              >
                {r.label}
              </td>
              <td className="py-1.5 pr-3">
                <UmabanBadges
                  umabans={parseKumi(r.kumi)}
                  entries={entries}
                  ordered={r.ordered}
                />
              </td>
              <td
                className="whitespace-nowrap py-1.5 text-right font-bold tabular-nums"
                style={{ color: "var(--text-primary)" }}
              >
                {yen(r.pay)}
                {r.ninki != null && (
                  <span
                    className="ml-1 text-[11px] font-normal"
                    style={{ color: "var(--text-muted)" }}
                  >
                    ({r.ninki}人気)
                  </span>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export default function ConfirmedResults({
  confirmed,
  entries,
}: {
  confirmed: ConfirmedDataResponse | null;
  entries: RaceEntry[];
}) {
  if (!confirmed) return null;
  const hasOdds = confirmed.win_odds.length > 0;
  const hasPayouts = confirmed.payouts != null;
  if (!hasOdds && !hasPayouts) return null;

  return (
    <div className="glass-card p-5">
      <div className="mb-3 flex items-center gap-2">
        <h2
          className="text-base font-semibold"
          style={{ color: "var(--text-primary)" }}
        >
          確定オッズ・払戻
        </h2>
        <span
          className="rounded px-1.5 py-0.5 text-[10px] font-medium"
          style={{
            backgroundColor: "rgba(34,197,94,0.15)",
            color: "#22c55e",
          }}
        >
          JRA-VAN
        </span>
      </div>

      {hasPayouts && confirmed.payouts && (
        <PayoutRows payouts={confirmed.payouts} entries={entries} />
      )}

      {hasOdds && (
        <div className="mt-4">
          <h3
            className="mb-2 text-xs font-semibold"
            style={{ color: "var(--text-muted)" }}
          >
            確定単勝オッズ
          </h3>
          <div className="flex flex-wrap gap-1.5">
            {confirmed.win_odds.map((o) => {
              const e = entries.find((en) => en.post_position === o.umaban);
              const c = wakuColor(e?.bracket_number ?? null);
              return (
                <span
                  key={o.umaban}
                  title={e?.horse.name ?? String(o.umaban)}
                  className="inline-flex items-center gap-1 rounded px-1.5 py-1 text-xs tabular-nums"
                  style={{
                    backgroundColor: "rgba(255,255,255,0.04)",
                    border: "1px solid rgba(255,255,255,0.08)",
                  }}
                >
                  <span
                    className="inline-flex h-5 min-w-[1.25rem] items-center justify-center rounded px-1 text-[11px] font-bold"
                    style={{
                      backgroundColor: c.bg,
                      color: c.fg,
                      border: "1px solid rgba(0,0,0,0.25)",
                    }}
                  >
                    {o.umaban}
                  </span>
                  <span style={{ color: "var(--text-primary)" }}>
                    {o.win_odds != null ? o.win_odds.toFixed(1) : "—"}
                  </span>
                  {o.win_favorite != null && (
                    <span
                      className="text-[10px]"
                      style={{ color: "var(--text-muted)" }}
                    >
                      {o.win_favorite}人気
                    </span>
                  )}
                </span>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}
