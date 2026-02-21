"use client";

import { useState, useMemo, useEffect } from "react";
import { createBet, type RaceEntry, type BetRecord } from "@/lib/api";

const BET_TYPES = [
  { value: "tansho", label: "単勝", picks: 1, ordered: false, desc: "1着を当てる" },
  { value: "fukusho", label: "複勝", picks: 1, ordered: false, desc: "3着以内を当てる" },
  { value: "umaren", label: "馬連", picks: 2, ordered: false, desc: "1-2着の組合せ" },
  { value: "umatan", label: "馬単", picks: 2, ordered: true, desc: "1-2着を着順通り" },
  { value: "wide", label: "ワイド", picks: 2, ordered: false, desc: "3着以内の2頭" },
  { value: "sanrenpuku", label: "三連複", picks: 3, ordered: false, desc: "1-3着の組合せ" },
  { value: "sanrentan", label: "三連単", picks: 3, ordered: true, desc: "1-3着を着順通り" },
] as const;

type BetTypeDef = (typeof BET_TYPES)[number];

type SessionBet = {
  id: string;
  betType: string;
  horseNames: string;
  amount: number;
  odds: number | null;
  payout: number | null;
};

type Props = {
  raceId: string;
  raceDate: string;
  entries: RaceEntry[];
  sessionBets: SessionBet[];
  onBetSaved: (bet: SessionBet) => void;
  prefillBetType?: string | null;
  prefillHorseIds?: string[] | null;
  onPrefillConsumed?: () => void;
};

const PICK_LABELS_ORDERED: Record<number, string[]> = {
  2: ["1着", "2着"],
  3: ["1着", "2着", "3着"],
};

const PICK_LABELS_UNORDERED: Record<number, string[]> = {
  2: ["馬1", "馬2"],
  3: ["馬1", "馬2", "馬3"],
};

function calculatePayout(amount: number, odds: number): number {
  return Math.floor((amount * odds) / 100) * 100;
}

export type { SessionBet };

export default function BettingSimulator({
  raceId,
  raceDate,
  entries,
  sessionBets,
  onBetSaved,
  prefillBetType,
  prefillHorseIds,
  onPrefillConsumed,
}: Props) {
  const [betType, setBetType] = useState<string>("tansho");
  const [selectedHorses, setSelectedHorses] = useState<string[]>([""]);
  const [manualOdds, setManualOdds] = useState<string>("");
  const [amount, setAmount] = useState<number>(100);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [showGuide, setShowGuide] = useState(true);

  // Handle prefill from AI recommendations
  useEffect(() => {
    if (!prefillBetType || !prefillHorseIds) return;
    const newType = BET_TYPES.find((t) => t.value === prefillBetType);
    if (!newType) return;

    setBetType(prefillBetType);
    // Adjust horse IDs to match the expected picks count
    const picks = newType.picks;
    const adjusted = prefillHorseIds.slice(0, picks);
    while (adjusted.length < picks) adjusted.push("");
    setSelectedHorses(adjusted);
    setManualOdds("");
    setMessage(null);
    onPrefillConsumed?.();
  }, [prefillBetType, prefillHorseIds, onPrefillConsumed]);

  const currentType: BetTypeDef =
    BET_TYPES.find((t) => t.value === betType) ?? BET_TYPES[0];

  function handleBetTypeChange(value: string) {
    setBetType(value);
    const newType = BET_TYPES.find((t) => t.value === value) ?? BET_TYPES[0];
    setSelectedHorses(Array(newType.picks).fill(""));
    setManualOdds("");
    setMessage(null);
  }

  function handleHorseChange(index: number, horseId: string) {
    setSelectedHorses((prev) => {
      const next = [...prev];
      next[index] = horseId;
      return next;
    });
  }

  const sortedEntries = useMemo(
    () =>
      [...entries].sort(
        (a, b) => (a.post_position ?? 999) - (b.post_position ?? 999),
      ),
    [entries],
  );

  const isAutoOdds = betType === "tansho";
  const autoOdds = useMemo(() => {
    if (!isAutoOdds || !selectedHorses[0]) return null;
    const entry = entries.find((e) => e.horse.id === selectedHorses[0]);
    return entry?.win_odds ?? null;
  }, [isAutoOdds, selectedHorses, entries]);

  const effectiveOdds = isAutoOdds
    ? autoOdds
    : manualOdds
      ? parseFloat(manualOdds)
      : null;

  const allSelected =
    selectedHorses.length === currentType.picks &&
    selectedHorses.every((h) => h !== "");

  const estimatedPayout =
    effectiveOdds !== null && effectiveOdds > 0 && amount > 0
      ? calculatePayout(amount, effectiveOdds)
      : null;

  function getHorseNames(): string {
    return selectedHorses
      .map((hid) => entries.find((e) => e.horse.id === hid)?.horse.name ?? "")
      .filter(Boolean)
      .join(", ");
  }

  const canSave = allSelected && amount > 0;

  async function handleSave() {
    if (!canSave) return;
    setSaving(true);
    setMessage(null);
    try {
      const record: BetRecord = await createBet({
        race_id: raceId,
        bet_date: raceDate,
        bet_type: betType,
        horse_names: getHorseNames(),
        amount_yen: amount,
        odds_at_bet: effectiveOdds,
      });
      const sessionBet: SessionBet = {
        id: record.id,
        betType: currentType.label,
        horseNames: getHorseNames(),
        amount,
        odds: effectiveOdds,
        payout: estimatedPayout,
      };
      onBetSaved(sessionBet);
      setMessage("馬券を記録しました");
    } catch {
      setMessage("記録に失敗しました");
    } finally {
      setSaving(false);
    }
  }

  const pickLabels = currentType.ordered
    ? PICK_LABELS_ORDERED[currentType.picks]
    : PICK_LABELS_UNORDERED[currentType.picks];

  // Current step indicator
  const currentStep = !allSelected ? 1 : effectiveOdds === null ? 2 : 3;

  const totalSessionAmount = sessionBets.reduce((sum, b) => sum + b.amount, 0);
  const totalSessionPayout = sessionBets.reduce(
    (sum, b) => sum + (b.payout ?? 0),
    0,
  );

  return (
    <div className="space-y-4">
      {/* Usage guide - collapsible */}
      {showGuide && (
        <div
          className="relative overflow-hidden rounded-xl p-[1px]"
          style={{
            background:
              "linear-gradient(135deg, rgba(59,130,246,0.3), rgba(139,92,246,0.3))",
          }}
        >
          <div
            className="rounded-xl p-4"
            style={{ backgroundColor: "var(--bg-elevated)" }}
          >
            <div className="mb-3 flex items-center justify-between">
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
                    d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
                  />
                </svg>
                <span
                  className="text-xs font-semibold tracking-wide uppercase"
                  style={{ color: "var(--accent)" }}
                >
                  使い方
                </span>
              </div>
              <button
                type="button"
                onClick={() => setShowGuide(false)}
                className="cursor-pointer rounded-md px-2 py-1 text-xs transition-colors duration-200"
                style={{ color: "var(--text-muted)" }}
                onMouseEnter={(e) => {
                  e.currentTarget.style.color = "var(--text-primary)";
                  e.currentTarget.style.backgroundColor =
                    "rgba(255,255,255,0.05)";
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.color = "var(--text-muted)";
                  e.currentTarget.style.backgroundColor = "transparent";
                }}
              >
                閉じる
              </button>
            </div>

            <div className="grid grid-cols-1 gap-2 sm:grid-cols-3">
              {[
                {
                  step: "1",
                  title: "馬券種・馬を選ぶ",
                  desc: "7種の馬券種から選択し、馬をドロップダウンから指定",
                },
                {
                  step: "2",
                  title: "オッズ・掛け金を入力",
                  desc: "単勝は自動取得。他は手入力。掛け金は100円単位",
                },
                {
                  step: "3",
                  title: "記録する",
                  desc: "推定払戻を確認して記録。収支管理ページでも確認可能",
                },
              ].map((s) => (
                <div
                  key={s.step}
                  className="flex gap-3 rounded-lg p-3"
                  style={{ backgroundColor: "rgba(255,255,255,0.03)" }}
                >
                  <div
                    className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full text-xs font-bold"
                    style={{
                      background:
                        "linear-gradient(135deg, var(--accent), #8B5CF6)",
                      color: "#fff",
                    }}
                  >
                    {s.step}
                  </div>
                  <div>
                    <div
                      className="text-xs font-semibold"
                      style={{ color: "var(--text-primary)" }}
                    >
                      {s.title}
                    </div>
                    <div
                      className="mt-0.5 text-xs leading-relaxed"
                      style={{ color: "var(--text-muted)" }}
                    >
                      {s.desc}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* Main simulator card */}
      <div
        className="relative overflow-hidden rounded-xl"
        style={{
          backgroundColor: "var(--bg-elevated)",
          border: "1px solid var(--border)",
        }}
      >
        {/* Header */}
        <div
          className="flex items-center justify-between px-5 py-3"
          style={{
            borderBottom: "1px solid var(--border)",
            background:
              "linear-gradient(135deg, rgba(59,130,246,0.06), rgba(139,92,246,0.06))",
          }}
        >
          <div className="flex items-center gap-3">
            <div
              className="flex h-8 w-8 items-center justify-center rounded-lg"
              style={{
                background:
                  "linear-gradient(135deg, var(--accent), #8B5CF6)",
              }}
            >
              <svg
                className="h-4 w-4"
                fill="none"
                stroke="#fff"
                strokeWidth={2}
                viewBox="0 0 24 24"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  d="M9 7h6m0 10v-3m-3 3h.01M9 17h.01M9 14h.01M12 14h.01M15 11h.01M12 11h.01M9 11h.01M7 21h10a2 2 0 002-2V5a2 2 0 00-2-2H7a2 2 0 00-2 2v14a2 2 0 002 2z"
                />
              </svg>
            </div>
            <div>
              <h2
                className="text-sm font-bold"
                style={{ color: "var(--text-primary)" }}
              >
                馬券シミュレーション
              </h2>
              <span
                className="text-xs"
                style={{ color: "var(--text-muted)" }}
              >
                {currentType.label} - {currentType.desc}
              </span>
            </div>
          </div>
          {!showGuide && (
            <button
              type="button"
              onClick={() => setShowGuide(true)}
              className="cursor-pointer rounded-md px-2.5 py-1 text-xs font-medium transition-colors duration-200"
              style={{
                color: "var(--accent)",
                border: "1px solid rgba(59,130,246,0.3)",
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.backgroundColor =
                  "rgba(59,130,246,0.1)";
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.backgroundColor = "transparent";
              }}
            >
              使い方
            </button>
          )}
        </div>

        <div className="p-5">
          {/* Step 1: Bet type selection - pill buttons */}
          <div className="mb-5">
            <div className="mb-2 flex items-center gap-2">
              <div
                className="flex h-5 w-5 items-center justify-center rounded-full text-[10px] font-bold"
                style={{
                  background:
                    currentStep >= 1
                      ? "linear-gradient(135deg, var(--accent), #8B5CF6)"
                      : "var(--border)",
                  color: "#fff",
                }}
              >
                1
              </div>
              <span
                className="text-xs font-semibold"
                style={{ color: "var(--text-secondary)" }}
              >
                馬券種を選択
              </span>
            </div>
            <div className="flex flex-wrap gap-1.5">
              {BET_TYPES.map((t) => (
                <button
                  key={t.value}
                  type="button"
                  onClick={() => handleBetTypeChange(t.value)}
                  className="cursor-pointer rounded-lg px-3 py-1.5 text-xs font-medium transition-all duration-200"
                  style={{
                    backgroundColor:
                      betType === t.value
                        ? "var(--accent)"
                        : "rgba(255,255,255,0.05)",
                    color:
                      betType === t.value ? "#fff" : "var(--text-secondary)",
                    border:
                      betType === t.value
                        ? "1px solid var(--accent)"
                        : "1px solid var(--border)",
                    boxShadow:
                      betType === t.value
                        ? "0 0 12px rgba(59,130,246,0.3)"
                        : "none",
                  }}
                  onMouseEnter={(e) => {
                    if (betType !== t.value) {
                      e.currentTarget.style.borderColor =
                        "rgba(59,130,246,0.5)";
                      e.currentTarget.style.color = "var(--text-primary)";
                    }
                  }}
                  onMouseLeave={(e) => {
                    if (betType !== t.value) {
                      e.currentTarget.style.borderColor = "var(--border)";
                      e.currentTarget.style.color = "var(--text-secondary)";
                    }
                  }}
                >
                  {t.label}
                  <span
                    className="ml-1 opacity-60"
                    style={{ fontSize: "10px" }}
                  >
                    {t.picks}頭
                  </span>
                </button>
              ))}
            </div>
          </div>

          {/* Step 1b: Horse selection */}
          <div className="mb-5">
            <div className="mb-2 flex items-center gap-2">
              <div
                className="h-px flex-1"
                style={{ backgroundColor: "var(--border)" }}
              />
              <span
                className="text-xs"
                style={{ color: "var(--text-muted)" }}
              >
                馬を選択
              </span>
              <div
                className="h-px flex-1"
                style={{ backgroundColor: "var(--border)" }}
              />
            </div>
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
              {selectedHorses.map((sel, idx) => (
                <div key={idx}>
                  <label
                    className="mb-1 block text-xs font-medium"
                    style={{ color: "var(--text-secondary)" }}
                  >
                    {currentType.picks === 1
                      ? "馬選択"
                      : (pickLabels?.[idx] ?? `馬${idx + 1}`)}
                  </label>
                  <select
                    value={sel}
                    onChange={(e) => handleHorseChange(idx, e.target.value)}
                    className="w-full cursor-pointer rounded-lg px-3 py-2.5 text-sm transition-colors duration-200"
                    style={{
                      backgroundColor: "rgba(255,255,255,0.03)",
                      border: sel
                        ? "1px solid var(--accent)"
                        : "1px solid var(--border)",
                      color: "var(--text-primary)",
                      boxShadow: sel
                        ? "0 0 8px rgba(59,130,246,0.15)"
                        : "none",
                    }}
                  >
                    <option value="">選択してください</option>
                    {sortedEntries
                      .filter(
                        (e) =>
                          e.horse.id === sel ||
                          !selectedHorses.some(
                            (h, i) => i !== idx && h === e.horse.id,
                          ),
                      )
                      .map((e) => (
                        <option key={e.horse.id} value={e.horse.id}>
                          {e.post_position ?? "?"}. {e.horse.name}
                          {e.win_odds !== null
                            ? ` (${Number(e.win_odds).toFixed(1)}倍)`
                            : ""}
                        </option>
                      ))}
                  </select>
                </div>
              ))}
            </div>
          </div>

          {/* Step 2: Odds & Amount */}
          <div className="mb-5">
            <div className="mb-2 flex items-center gap-2">
              <div
                className="flex h-5 w-5 items-center justify-center rounded-full text-[10px] font-bold"
                style={{
                  background:
                    currentStep >= 2
                      ? "linear-gradient(135deg, var(--accent), #8B5CF6)"
                      : "var(--border)",
                  color: "#fff",
                }}
              >
                2
              </div>
              <span
                className="text-xs font-semibold"
                style={{ color: "var(--text-secondary)" }}
              >
                オッズ・掛け金
              </span>
            </div>
            <div className="grid grid-cols-2 gap-3">
              {/* Odds */}
              <div>
                <label
                  className="mb-1 block text-xs font-medium"
                  style={{ color: "var(--text-secondary)" }}
                >
                  オッズ
                  {isAutoOdds && (
                    <span
                      className="ml-1.5 rounded-full px-1.5 py-0.5 text-[10px]"
                      style={{
                        backgroundColor: "rgba(59,130,246,0.15)",
                        color: "var(--accent)",
                      }}
                    >
                      自動
                    </span>
                  )}
                </label>
                {isAutoOdds ? (
                  <div
                    className="rounded-lg px-3 py-2.5 text-sm font-semibold tabular-nums"
                    style={{
                      backgroundColor: "rgba(255,255,255,0.03)",
                      border: "1px solid var(--border)",
                      color:
                        autoOdds !== null
                          ? "var(--text-primary)"
                          : "var(--text-muted)",
                    }}
                  >
                    {autoOdds !== null ? `${autoOdds.toFixed(1)} 倍` : "---"}
                  </div>
                ) : (
                  <input
                    type="number"
                    min={1}
                    step={0.1}
                    value={manualOdds}
                    onChange={(e) => setManualOdds(e.target.value)}
                    placeholder="例: 12.5"
                    className="w-full rounded-lg px-3 py-2.5 text-sm tabular-nums transition-colors duration-200"
                    style={{
                      backgroundColor: "rgba(255,255,255,0.03)",
                      border: "1px solid var(--border)",
                      color: "var(--text-primary)",
                    }}
                    onFocus={(e) => {
                      e.currentTarget.style.borderColor = "var(--accent)";
                      e.currentTarget.style.boxShadow =
                        "0 0 8px rgba(59,130,246,0.15)";
                    }}
                    onBlur={(e) => {
                      e.currentTarget.style.borderColor = "var(--border)";
                      e.currentTarget.style.boxShadow = "none";
                    }}
                  />
                )}
              </div>

              {/* Amount */}
              <div>
                <label
                  className="mb-1 block text-xs font-medium"
                  style={{ color: "var(--text-secondary)" }}
                >
                  掛け金
                </label>
                <div className="relative">
                  <input
                    type="number"
                    min={100}
                    step={100}
                    value={amount}
                    onChange={(e) => setAmount(Number(e.target.value))}
                    className="w-full rounded-lg px-3 py-2.5 pr-8 text-sm tabular-nums transition-colors duration-200"
                    style={{
                      backgroundColor: "rgba(255,255,255,0.03)",
                      border: "1px solid var(--border)",
                      color: "var(--text-primary)",
                    }}
                    onFocus={(e) => {
                      e.currentTarget.style.borderColor = "var(--accent)";
                      e.currentTarget.style.boxShadow =
                        "0 0 8px rgba(59,130,246,0.15)";
                    }}
                    onBlur={(e) => {
                      e.currentTarget.style.borderColor = "var(--border)";
                      e.currentTarget.style.boxShadow = "none";
                    }}
                  />
                  <span
                    className="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 text-xs"
                    style={{ color: "var(--text-muted)" }}
                  >
                    円
                  </span>
                </div>
              </div>
            </div>
          </div>

          {/* Step 3: Result & Save */}
          <div>
            <div className="mb-3 flex items-center gap-2">
              <div
                className="flex h-5 w-5 items-center justify-center rounded-full text-[10px] font-bold"
                style={{
                  background:
                    currentStep >= 3
                      ? "linear-gradient(135deg, var(--accent), #8B5CF6)"
                      : "var(--border)",
                  color: "#fff",
                }}
              >
                3
              </div>
              <span
                className="text-xs font-semibold"
                style={{ color: "var(--text-secondary)" }}
              >
                確認・記録
              </span>
            </div>

            {/* Payout display */}
            <div
              className="mb-4 rounded-xl p-4 text-center"
              style={{
                background:
                  estimatedPayout !== null
                    ? "linear-gradient(135deg, rgba(34,197,94,0.1), rgba(16,185,129,0.05))"
                    : "rgba(255,255,255,0.02)",
                border:
                  estimatedPayout !== null
                    ? "1px solid rgba(34,197,94,0.3)"
                    : "1px solid var(--border)",
              }}
            >
              <div
                className="mb-1 text-xs font-medium"
                style={{ color: "var(--text-muted)" }}
              >
                推定払戻額
              </div>
              <div
                className="text-2xl font-bold tabular-nums"
                style={{
                  color:
                    estimatedPayout !== null
                      ? "var(--green)"
                      : "var(--text-muted)",
                  textShadow:
                    estimatedPayout !== null
                      ? "0 0 20px rgba(34,197,94,0.3)"
                      : "none",
                }}
              >
                {estimatedPayout !== null
                  ? `¥${estimatedPayout.toLocaleString()}`
                  : "---"}
              </div>
              {estimatedPayout !== null && amount > 0 && (
                <div
                  className="mt-1 text-xs tabular-nums"
                  style={{ color: "var(--text-muted)" }}
                >
                  回収率{" "}
                  <span style={{ color: "var(--green)" }}>
                    {((estimatedPayout / amount) * 100).toFixed(0)}%
                  </span>
                </div>
              )}
            </div>

            {/* Save button */}
            <button
              type="button"
              onClick={handleSave}
              disabled={!canSave || saving}
              className="w-full cursor-pointer rounded-xl py-3 text-sm font-bold transition-all duration-200"
              style={{
                background: canSave
                  ? "linear-gradient(135deg, var(--accent), #8B5CF6)"
                  : "var(--border)",
                color: canSave ? "#fff" : "var(--text-muted)",
                opacity: saving ? 0.6 : 1,
                boxShadow: canSave
                  ? "0 4px 15px rgba(59,130,246,0.3)"
                  : "none",
              }}
              onMouseEnter={(e) => {
                if (canSave) {
                  e.currentTarget.style.boxShadow =
                    "0 6px 20px rgba(59,130,246,0.4)";
                  e.currentTarget.style.transform = "translateY(-1px)";
                }
              }}
              onMouseLeave={(e) => {
                if (canSave) {
                  e.currentTarget.style.boxShadow =
                    "0 4px 15px rgba(59,130,246,0.3)";
                  e.currentTarget.style.transform = "translateY(0)";
                }
              }}
            >
              {saving ? "保存中..." : "この馬券を記録する"}
            </button>

            {message && (
              <div
                className="mt-2 rounded-lg px-3 py-2 text-center text-xs"
                style={{
                  backgroundColor: message.includes("失敗")
                    ? "rgba(239,68,68,0.1)"
                    : "rgba(34,197,94,0.1)",
                  color: message.includes("失敗")
                    ? "var(--red)"
                    : "var(--green)",
                }}
              >
                {message}
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Session bet records */}
      {sessionBets.length > 0 && (
        <div
          className="overflow-hidden rounded-xl"
          style={{
            backgroundColor: "var(--bg-elevated)",
            border: "1px solid var(--border)",
          }}
        >
          <div
            className="flex items-center justify-between px-5 py-3"
            style={{ borderBottom: "1px solid var(--border)" }}
          >
            <h3
              className="text-sm font-bold"
              style={{ color: "var(--text-primary)" }}
            >
              セッション内記録
              <span
                className="ml-2 rounded-full px-2 py-0.5 text-xs font-normal"
                style={{
                  backgroundColor: "rgba(59,130,246,0.15)",
                  color: "var(--accent)",
                }}
              >
                {sessionBets.length}件
              </span>
            </h3>
            <div className="flex items-center gap-4">
              <div className="text-right">
                <div
                  className="text-[10px]"
                  style={{ color: "var(--text-muted)" }}
                >
                  合計投資
                </div>
                <div
                  className="text-xs font-semibold tabular-nums"
                  style={{ color: "var(--text-primary)" }}
                >
                  ¥{totalSessionAmount.toLocaleString()}
                </div>
              </div>
              <div className="text-right">
                <div
                  className="text-[10px]"
                  style={{ color: "var(--text-muted)" }}
                >
                  推定払戻合計
                </div>
                <div
                  className="text-xs font-semibold tabular-nums"
                  style={{ color: "var(--green)" }}
                >
                  ¥{totalSessionPayout.toLocaleString()}
                </div>
              </div>
            </div>
          </div>
          <div className="divide-y" style={{ borderColor: "var(--border)" }}>
            {sessionBets.map((b, i) => (
              <div
                key={b.id}
                className="flex items-center justify-between px-5 py-3 transition-colors duration-150"
                style={{
                  borderBottom:
                    i < sessionBets.length - 1
                      ? "1px solid var(--border)"
                      : "none",
                }}
                onMouseEnter={(e) => {
                  e.currentTarget.style.backgroundColor =
                    "rgba(255,255,255,0.02)";
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.backgroundColor = "transparent";
                }}
              >
                <div className="flex items-center gap-3">
                  <span
                    className="inline-flex rounded-md px-2 py-0.5 text-xs font-medium"
                    style={{
                      backgroundColor: "rgba(139,92,246,0.15)",
                      color: "#A78BFA",
                    }}
                  >
                    {b.betType}
                  </span>
                  <span
                    className="text-sm"
                    style={{ color: "var(--text-primary)" }}
                  >
                    {b.horseNames}
                  </span>
                </div>
                <div className="flex items-center gap-4 text-right">
                  <span
                    className="text-xs tabular-nums"
                    style={{ color: "var(--text-muted)" }}
                  >
                    {b.odds !== null ? `${b.odds.toFixed(1)}倍` : ""}
                  </span>
                  <span
                    className="text-xs tabular-nums"
                    style={{ color: "var(--text-secondary)" }}
                  >
                    ¥{b.amount.toLocaleString()}
                  </span>
                  <span
                    className="text-sm font-semibold tabular-nums"
                    style={{ color: "var(--green)" }}
                  >
                    {b.payout !== null
                      ? `¥${b.payout.toLocaleString()}`
                      : "---"}
                  </span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
