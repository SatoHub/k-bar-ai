"use client";

import { useState } from "react";
import { createBet, type RaceEntry } from "@/lib/api";

type Props = {
  raceId: string;
  raceDate: string;
  entries: RaceEntry[];
};

const BET_TYPES = [
  { value: "tansho", label: "単勝" },
  { value: "fukusho", label: "複勝" },
] as const;

export default function BettingSimulator({
  raceId,
  raceDate,
  entries,
}: Props) {
  const [betType, setBetType] = useState<string>("tansho");
  const [selectedHorse, setSelectedHorse] = useState<string>("");
  const [amount, setAmount] = useState<number>(100);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState<string | null>(null);

  const selectedEntry = entries.find((e) => e.horse.id === selectedHorse);
  const odds = selectedEntry?.win_odds ?? null;

  // JRA payout calculation: floor(amount * odds / 100) * 100
  const estimatedPayout =
    odds !== null && amount > 0
      ? Math.floor((amount * odds) / 100) * 100
      : null;

  async function handleSave() {
    if (!selectedHorse || amount <= 0) return;
    setSaving(true);
    setMessage(null);
    try {
      await createBet({
        race_id: raceId,
        bet_date: raceDate,
        bet_type: betType,
        horse_names: selectedEntry?.horse.name ?? "",
        amount_yen: amount,
        odds_at_bet: odds,
      });
      setMessage("馬券を記録しました");
    } catch {
      setMessage("記録に失敗しました");
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="glass-card p-5">
      <h2
        className="mb-4 text-base font-semibold"
        style={{ color: "var(--text-primary)" }}
      >
        馬券シミュレーション
      </h2>

      <div className="flex flex-wrap gap-4">
        {/* Bet type */}
        <div className="flex flex-col gap-1">
          <label
            className="text-xs font-medium"
            style={{ color: "var(--text-secondary)" }}
          >
            馬券種
          </label>
          <select
            value={betType}
            onChange={(e) => setBetType(e.target.value)}
            className="rounded-md px-3 py-2 text-sm"
            style={{
              backgroundColor: "var(--bg-elevated)",
              border: "1px solid var(--border-light)",
              color: "var(--text-primary)",
            }}
          >
            {BET_TYPES.map((t) => (
              <option key={t.value} value={t.value}>
                {t.label}
              </option>
            ))}
          </select>
        </div>

        {/* Horse selection */}
        <div className="flex flex-col gap-1">
          <label
            className="text-xs font-medium"
            style={{ color: "var(--text-secondary)" }}
          >
            馬選択
          </label>
          <select
            value={selectedHorse}
            onChange={(e) => setSelectedHorse(e.target.value)}
            className="rounded-md px-3 py-2 text-sm"
            style={{
              backgroundColor: "var(--bg-elevated)",
              border: "1px solid var(--border-light)",
              color: "var(--text-primary)",
            }}
          >
            <option value="">選択してください</option>
            {entries
              .sort(
                (a, b) =>
                  (a.post_position ?? 999) - (b.post_position ?? 999),
              )
              .map((e) => (
                <option key={e.horse.id} value={e.horse.id}>
                  {e.post_position ?? "?"}. {e.horse.name}
                  {e.win_odds !== null ? ` (${Number(e.win_odds).toFixed(1)}倍)` : ""}
                </option>
              ))}
          </select>
        </div>

        {/* Amount */}
        <div className="flex flex-col gap-1">
          <label
            className="text-xs font-medium"
            style={{ color: "var(--text-secondary)" }}
          >
            掛け金 (円)
          </label>
          <input
            type="number"
            min={100}
            step={100}
            value={amount}
            onChange={(e) => setAmount(Number(e.target.value))}
            className="w-28 rounded-md px-3 py-2 text-sm tabular-nums"
            style={{
              backgroundColor: "var(--bg-elevated)",
              border: "1px solid var(--border-light)",
              color: "var(--text-primary)",
            }}
          />
        </div>

        {/* Estimated payout */}
        <div className="flex flex-col gap-1">
          <label
            className="text-xs font-medium"
            style={{ color: "var(--text-secondary)" }}
          >
            推定払戻
          </label>
          <div
            className="rounded-md px-3 py-2 text-sm font-medium tabular-nums"
            style={{
              backgroundColor: "var(--bg-elevated)",
              color:
                estimatedPayout !== null
                  ? "var(--green)"
                  : "var(--text-muted)",
            }}
          >
            {estimatedPayout !== null
              ? `¥${estimatedPayout.toLocaleString()}`
              : "---"}
          </div>
        </div>
      </div>

      <div className="mt-4 flex items-center gap-3">
        <button
          type="button"
          onClick={handleSave}
          disabled={!selectedHorse || amount <= 0 || saving}
          className="cursor-pointer rounded-md px-4 py-2 text-sm font-medium"
          style={{
            backgroundColor:
              !selectedHorse || amount <= 0
                ? "var(--bg-elevated)"
                : "var(--accent)",
            color:
              !selectedHorse || amount <= 0
                ? "var(--text-muted)"
                : "#fff",
            opacity: saving ? 0.5 : 1,
          }}
        >
          {saving ? "保存中..." : "この馬券を記録する"}
        </button>
        {message && (
          <span
            className="text-xs"
            style={{ color: "var(--text-secondary)" }}
          >
            {message}
          </span>
        )}
      </div>
    </div>
  );
}
