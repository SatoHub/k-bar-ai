"use client";

import { useState, useMemo, useCallback, useEffect } from "react";
import { createBet, type RaceEntry, type BetRecord } from "@/lib/api";

const BET_TYPES = [
  { value: "tansho", label: "単勝", picks: 1, ordered: false, desc: "1着を当てる", isWaku: false },
  { value: "fukusho", label: "複勝", picks: 1, ordered: false, desc: "3着以内を当てる", isWaku: false },
  { value: "wakuren", label: "枠連", picks: 2, ordered: false, desc: "1-2着の枠番組合せ", isWaku: true },
  { value: "umaren", label: "馬連", picks: 2, ordered: false, desc: "1-2着の組合せ", isWaku: false },
  { value: "umatan", label: "馬単", picks: 2, ordered: true, desc: "1-2着を着順通り", isWaku: false },
  { value: "wide", label: "ワイド", picks: 2, ordered: false, desc: "3着以内の2頭", isWaku: false },
  { value: "sanrenpuku", label: "三連複", picks: 3, ordered: false, desc: "1-3着の組合せ", isWaku: false },
  { value: "sanrentan", label: "三連単", picks: 3, ordered: true, desc: "1-3着を着順通り", isWaku: false },
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

type BetSlotState = {
  slotId: string;
  betType: string;
  selectedHorses: string[];
  manualOdds: string;
  amount: number;
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

const PICK_LABELS_WAKU: string[] = ["枠1", "枠2"];

function calculatePayout(amount: number, odds: number): number {
  return Math.floor((amount * odds) / 100) * 100;
}

let slotCounter = 0;
function newSlotId(): string {
  return `slot-${++slotCounter}-${Date.now()}`;
}

function createSlot(betType = "tansho"): BetSlotState {
  const typeDef = BET_TYPES.find((t) => t.value === betType) ?? BET_TYPES[0];
  return {
    slotId: newSlotId(),
    betType,
    selectedHorses: Array(typeDef.picks).fill(""),
    manualOdds: "",
    amount: 100,
  };
}

export type { SessionBet };

/* ─── Per-slot helper functions ─── */

function getTypeDef(betType: string): BetTypeDef {
  return BET_TYPES.find((t) => t.value === betType) ?? BET_TYPES[0];
}

function getSlotOdds(
  slot: BetSlotState,
  entries: RaceEntry[],
): number | null {
  const typeDef = getTypeDef(slot.betType);
  if (slot.betType === "tansho" && slot.selectedHorses[0]) {
    const withOdds = entries.find(
      (e) => e.horse.id === slot.selectedHorses[0] && e.win_odds !== null,
    );
    const raw = withOdds
      ? withOdds.win_odds
      : (entries.find((e) => e.horse.id === slot.selectedHorses[0])?.win_odds ?? null);
    return raw !== null ? Number(raw) : null;
  }
  return slot.manualOdds ? parseFloat(slot.manualOdds) : null;
}

function isSlotComplete(slot: BetSlotState): boolean {
  const typeDef = getTypeDef(slot.betType);
  return (
    slot.selectedHorses.length === typeDef.picks &&
    slot.selectedHorses.every((h) => h !== "") &&
    slot.amount > 0
  );
}

function getHorseNamesForSlot(
  slot: BetSlotState,
  entries: RaceEntry[],
): string {
  const typeDef = getTypeDef(slot.betType);
  if (typeDef.isWaku) {
    return slot.selectedHorses
      .filter(Boolean)
      .map((w) => `${w}枠`)
      .join(", ");
  }
  return slot.selectedHorses
    .map((hid) => entries.find((e) => e.horse.id === hid)?.horse.name ?? "")
    .filter(Boolean)
    .join(", ");
}

/* ─── Single Bet Slot Card ─── */

function BetSlotCard({
  slot,
  index,
  total,
  entries,
  sortedEntries,
  availableWakus,
  onUpdate,
  onRemove,
}: {
  slot: BetSlotState;
  index: number;
  total: number;
  entries: RaceEntry[];
  sortedEntries: RaceEntry[];
  availableWakus: number[];
  onUpdate: (slotId: string, patch: Partial<BetSlotState>) => void;
  onRemove: (slotId: string) => void;
}) {
  const typeDef = getTypeDef(slot.betType);
  const isAutoOdds = slot.betType === "tansho";
  const effectiveOdds = getSlotOdds(slot, entries);
  const allSelected =
    slot.selectedHorses.length === typeDef.picks &&
    slot.selectedHorses.every((h) => h !== "");
  const estimatedPayout =
    effectiveOdds !== null && effectiveOdds > 0 && slot.amount > 0
      ? calculatePayout(slot.amount, effectiveOdds)
      : null;

  const pickLabels = typeDef.isWaku
    ? PICK_LABELS_WAKU
    : typeDef.ordered
      ? PICK_LABELS_ORDERED[typeDef.picks]
      : PICK_LABELS_UNORDERED[typeDef.picks];

  function handleBetTypeChange(value: string) {
    const newType = BET_TYPES.find((t) => t.value === value) ?? BET_TYPES[0];
    onUpdate(slot.slotId, {
      betType: value,
      selectedHorses: Array(newType.picks).fill(""),
      manualOdds: "",
    });
  }

  function handleHorseChange(idx: number, horseId: string) {
    const next = [...slot.selectedHorses];
    next[idx] = horseId;
    onUpdate(slot.slotId, { selectedHorses: next });
  }

  return (
    <div
      className="relative overflow-hidden rounded-xl"
      style={{
        backgroundColor: "var(--bg-elevated)",
        border: "1px solid var(--border)",
      }}
    >
      {/* Card Header */}
      <div
        className="flex items-center justify-between px-4 py-2.5"
        style={{
          borderBottom: "1px solid var(--border)",
          background:
            "linear-gradient(135deg, rgba(59,130,246,0.06), rgba(139,92,246,0.06))",
        }}
      >
        <div className="flex items-center gap-2">
          <div
            className="flex h-6 w-6 items-center justify-center rounded-lg text-xs font-bold"
            style={{
              background: "linear-gradient(135deg, var(--accent), #8B5CF6)",
              color: "#fff",
            }}
          >
            {index + 1}
          </div>
          <span
            className="text-xs font-semibold"
            style={{ color: "var(--text-primary)" }}
          >
            {typeDef.label}
          </span>
          <span className="text-xs" style={{ color: "var(--text-muted)" }}>
            {typeDef.desc}
          </span>
        </div>
        <div className="flex items-center gap-2">
          {/* Payout badge */}
          {estimatedPayout !== null && (
            <span
              className="rounded-full px-2 py-0.5 text-xs font-semibold tabular-nums"
              style={{
                backgroundColor: "rgba(34,197,94,0.15)",
                color: "var(--green)",
              }}
            >
              ¥{estimatedPayout.toLocaleString()}
            </span>
          )}
          {total > 1 && (
            <button
              type="button"
              onClick={() => onRemove(slot.slotId)}
              className="flex h-6 w-6 cursor-pointer items-center justify-center rounded-md text-sm transition-colors duration-150"
              style={{ color: "var(--text-muted)" }}
              onMouseEnter={(e) => {
                e.currentTarget.style.color = "var(--red)";
                e.currentTarget.style.backgroundColor = "rgba(239,68,68,0.1)";
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.color = "var(--text-muted)";
                e.currentTarget.style.backgroundColor = "transparent";
              }}
              title="この馬券を削除"
            >
              ×
            </button>
          )}
        </div>
      </div>

      <div className="p-4 space-y-3">
        {/* Bet type pills */}
        <div className="flex flex-wrap gap-1">
          {BET_TYPES.map((t) => (
            <button
              key={t.value}
              type="button"
              onClick={() => handleBetTypeChange(t.value)}
              className="cursor-pointer rounded-md px-2 py-1 text-xs font-medium transition-all duration-200"
              style={{
                backgroundColor:
                  slot.betType === t.value
                    ? "var(--accent)"
                    : "rgba(255,255,255,0.05)",
                color: slot.betType === t.value ? "#fff" : "var(--text-muted)",
                border:
                  slot.betType === t.value
                    ? "1px solid var(--accent)"
                    : "1px solid transparent",
              }}
            >
              {t.label}
            </button>
          ))}
        </div>

        {/* Horse / Waku selection */}
        <div className="grid grid-cols-1 gap-2 sm:grid-cols-3">
          {slot.selectedHorses.map((sel, idx) => (
            <div key={idx}>
              <label
                className="mb-0.5 block text-[10px] font-medium"
                style={{ color: "var(--text-muted)" }}
              >
                {typeDef.isWaku
                  ? (pickLabels?.[idx] ?? `枠${idx + 1}`)
                  : typeDef.picks === 1
                    ? "馬選択"
                    : (pickLabels?.[idx] ?? `馬${idx + 1}`)}
              </label>
              {typeDef.isWaku ? (
                <select
                  value={sel}
                  onChange={(e) => handleHorseChange(idx, e.target.value)}
                  className="w-full cursor-pointer rounded-lg px-2.5 py-2 text-sm transition-colors duration-200"
                  style={{
                    backgroundColor: "#fff",
                    border: sel ? "1px solid var(--accent)" : "1px solid var(--border)",
                    color: "#000",
                  }}
                >
                  <option value="">枠を選択</option>
                  {availableWakus
                    .filter(
                      (w) =>
                        String(w) === sel ||
                        !slot.selectedHorses.some((h, i) => i !== idx && h === String(w)),
                    )
                    .map((w) => {
                      const horses = entries
                        .filter((e) => e.bracket_number === w)
                        .map((e) => e.horse.name)
                        .join("・");
                      return (
                        <option key={w} value={String(w)}>
                          {w}枠 ({horses})
                        </option>
                      );
                    })}
                </select>
              ) : (
                <select
                  value={sel}
                  onChange={(e) => handleHorseChange(idx, e.target.value)}
                  className="w-full cursor-pointer rounded-lg px-2.5 py-2 text-sm transition-colors duration-200"
                  style={{
                    backgroundColor: "#fff",
                    border: sel ? "1px solid var(--accent)" : "1px solid var(--border)",
                    color: "#000",
                  }}
                >
                  <option value="">選択してください</option>
                  {sortedEntries
                    .filter(
                      (e) =>
                        e.horse.id === sel ||
                        !slot.selectedHorses.some((h, i) => i !== idx && h === e.horse.id),
                    )
                    .map((e, i) => (
                      <option key={`${e.horse.id}-${i}`} value={e.horse.id}>
                        {e.post_position ?? "?"}. {e.horse.name}
                        {e.win_odds !== null ? ` (${Number(e.win_odds).toFixed(1)}倍)` : ""}
                      </option>
                    ))}
                </select>
              )}
            </div>
          ))}
        </div>

        {/* Odds & Amount row */}
        <div className="grid grid-cols-2 gap-2">
          <div>
            <label
              className="mb-0.5 block text-[10px] font-medium"
              style={{ color: "var(--text-muted)" }}
            >
              オッズ
              {isAutoOdds && (
                <span
                  className="ml-1 rounded-full px-1 py-0.5 text-[9px]"
                  style={{ backgroundColor: "rgba(59,130,246,0.15)", color: "var(--accent)" }}
                >
                  自動
                </span>
              )}
            </label>
            {isAutoOdds ? (
              <div
                className="rounded-lg px-2.5 py-2 text-sm font-semibold tabular-nums"
                style={{
                  backgroundColor: "rgba(255,255,255,0.03)",
                  border: "1px solid var(--border)",
                  color: effectiveOdds !== null ? "var(--text-primary)" : "var(--text-muted)",
                }}
              >
                {effectiveOdds !== null ? `${effectiveOdds.toFixed(1)} 倍` : "---"}
              </div>
            ) : (
              <input
                type="number"
                min={1}
                step={0.1}
                value={slot.manualOdds}
                onChange={(e) => onUpdate(slot.slotId, { manualOdds: e.target.value })}
                placeholder="例: 12.5"
                className="w-full rounded-lg px-2.5 py-2 text-sm tabular-nums"
                style={{
                  backgroundColor: "rgba(255,255,255,0.03)",
                  border: "1px solid var(--border)",
                  color: "var(--text-primary)",
                }}
              />
            )}
          </div>
          <div>
            <label
              className="mb-0.5 block text-[10px] font-medium"
              style={{ color: "var(--text-muted)" }}
            >
              掛け金
            </label>
            <div className="relative">
              <input
                type="number"
                min={100}
                step={100}
                value={slot.amount}
                onChange={(e) => onUpdate(slot.slotId, { amount: Number(e.target.value) })}
                className="w-full rounded-lg px-2.5 py-2 pr-7 text-sm tabular-nums"
                style={{
                  backgroundColor: "rgba(255,255,255,0.03)",
                  border: "1px solid var(--border)",
                  color: "var(--text-primary)",
                }}
              />
              <span
                className="pointer-events-none absolute right-2.5 top-1/2 -translate-y-1/2 text-[10px]"
                style={{ color: "var(--text-muted)" }}
              >
                円
              </span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

/* ─── Main BettingSimulator (multi-slot) ─── */

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
  const [slots, setSlots] = useState<BetSlotState[]>([createSlot()]);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [showGuide, setShowGuide] = useState(true);

  // Handle prefill from AI recommendations → add as a new slot
  useEffect(() => {
    if (!prefillBetType || !prefillHorseIds) return;
    const newType = BET_TYPES.find((t) => t.value === prefillBetType);
    if (!newType) return;

    const picks = newType.picks;
    const adjusted = prefillHorseIds.slice(0, picks);
    while (adjusted.length < picks) adjusted.push("");

    setSlots((prev) => {
      // If the first slot is still empty/default, replace it
      const first = prev[0];
      const firstIsEmpty =
        prev.length === 1 &&
        first.betType === "tansho" &&
        first.selectedHorses.every((h) => h === "");
      if (firstIsEmpty) {
        return [
          {
            ...first,
            betType: prefillBetType,
            selectedHorses: adjusted,
            manualOdds: "",
          },
        ];
      }
      // Otherwise add a new slot
      return [
        ...prev,
        {
          slotId: newSlotId(),
          betType: prefillBetType,
          selectedHorses: adjusted,
          manualOdds: "",
          amount: 100,
        },
      ];
    });
    setMessage(null);
    onPrefillConsumed?.();
  }, [prefillBetType, prefillHorseIds, onPrefillConsumed]);

  const sortedEntries = useMemo(
    () => [...entries].sort((a, b) => (a.post_position ?? 999) - (b.post_position ?? 999)),
    [entries],
  );

  const availableWakus = useMemo(() => {
    const wakus = new Set<number>();
    for (const e of entries) {
      if (e.bracket_number != null) wakus.add(e.bracket_number);
    }
    return Array.from(wakus).sort((a, b) => a - b);
  }, [entries]);

  const updateSlot = useCallback((slotId: string, patch: Partial<BetSlotState>) => {
    setSlots((prev) =>
      prev.map((s) => (s.slotId === slotId ? { ...s, ...patch } : s)),
    );
  }, []);

  const removeSlot = useCallback((slotId: string) => {
    setSlots((prev) => prev.filter((s) => s.slotId !== slotId));
  }, []);

  const addSlot = useCallback(() => {
    setSlots((prev) => [...prev, createSlot()]);
  }, []);

  // Aggregated stats
  const slotStats = useMemo(() => {
    let totalAmount = 0;
    let totalPayout = 0;
    let allComplete = true;
    let completeCount = 0;
    for (const slot of slots) {
      totalAmount += slot.amount;
      const odds = getSlotOdds(slot, entries);
      if (odds !== null && odds > 0 && slot.amount > 0) {
        totalPayout += calculatePayout(slot.amount, odds);
      }
      if (isSlotComplete(slot)) {
        completeCount++;
      } else {
        allComplete = false;
      }
    }
    return { totalAmount, totalPayout, allComplete, completeCount };
  }, [slots, entries]);

  async function handleSaveAll() {
    if (!slotStats.allComplete) return;
    setSaving(true);
    setMessage(null);

    const savedBets: SessionBet[] = [];
    let failCount = 0;

    for (const slot of slots) {
      const typeDef = getTypeDef(slot.betType);
      const odds = getSlotOdds(slot, entries);
      const payout =
        odds !== null && odds > 0 && slot.amount > 0
          ? calculatePayout(slot.amount, odds)
          : null;
      try {
        const record: BetRecord = await createBet({
          race_id: raceId,
          bet_date: raceDate,
          bet_type: slot.betType,
          horse_names: getHorseNamesForSlot(slot, entries),
          amount_yen: slot.amount,
          odds_at_bet: odds,
        });
        savedBets.push({
          id: record.id,
          betType: typeDef.label,
          horseNames: getHorseNamesForSlot(slot, entries),
          amount: slot.amount,
          odds,
          payout,
        });
      } catch {
        failCount++;
      }
    }

    for (const bet of savedBets) {
      onBetSaved(bet);
    }

    if (failCount === 0) {
      setMessage(`${savedBets.length}件の馬券を記録しました`);
      // Reset to single empty slot
      setSlots([createSlot()]);
    } else {
      setMessage(`${savedBets.length}件記録、${failCount}件失敗`);
    }
    setSaving(false);
  }

  const totalSessionAmount = sessionBets.reduce((sum, b) => sum + b.amount, 0);
  const totalSessionPayout = sessionBets.reduce((sum, b) => sum + (b.payout ?? 0), 0);

  return (
    <div className="space-y-4">
      {/* Usage guide - collapsible */}
      {showGuide && (
        <div
          className="relative overflow-hidden rounded-xl p-[1px]"
          style={{
            background: "linear-gradient(135deg, rgba(59,130,246,0.3), rgba(139,92,246,0.3))",
          }}
        >
          <div className="rounded-xl p-4" style={{ backgroundColor: "var(--bg-elevated)" }}>
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
                  e.currentTarget.style.backgroundColor = "rgba(255,255,255,0.05)";
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
                { step: "1", title: "馬券を設定", desc: "馬券種・馬・オッズ・掛け金を入力" },
                { step: "2", title: "複数追加OK", desc: "「＋ 馬券を追加」で同時に複数設定可能" },
                { step: "3", title: "まとめて記録", desc: "合計を確認してまとめて記録。収支管理でも確認可能" },
              ].map((s) => (
                <div
                  key={s.step}
                  className="flex gap-3 rounded-lg p-3"
                  style={{ backgroundColor: "rgba(255,255,255,0.03)" }}
                >
                  <div
                    className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full text-xs font-bold"
                    style={{
                      background: "linear-gradient(135deg, var(--accent), #8B5CF6)",
                      color: "#fff",
                    }}
                  >
                    {s.step}
                  </div>
                  <div>
                    <div className="text-xs font-semibold" style={{ color: "var(--text-primary)" }}>
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

      {/* Section header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div
            className="flex h-8 w-8 items-center justify-center rounded-lg"
            style={{ background: "linear-gradient(135deg, var(--accent), #8B5CF6)" }}
          >
            <svg className="h-4 w-4" fill="none" stroke="#fff" strokeWidth={2} viewBox="0 0 24 24">
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                d="M9 7h6m0 10v-3m-3 3h.01M9 17h.01M9 14h.01M12 14h.01M15 11h.01M12 11h.01M9 11h.01M7 21h10a2 2 0 002-2V5a2 2 0 00-2-2H7a2 2 0 00-2 2v14a2 2 0 002 2z"
              />
            </svg>
          </div>
          <div>
            <h2 className="text-sm font-bold" style={{ color: "var(--text-primary)" }}>
              馬券シミュレーション
            </h2>
            <span className="text-xs" style={{ color: "var(--text-muted)" }}>
              {slots.length}件の馬券を設定中
            </span>
          </div>
        </div>
        <div className="flex items-center gap-2">
          {!showGuide && (
            <button
              type="button"
              onClick={() => setShowGuide(true)}
              className="cursor-pointer rounded-md px-2.5 py-1 text-xs font-medium transition-colors duration-200"
              style={{ color: "var(--accent)", border: "1px solid rgba(59,130,246,0.3)" }}
              onMouseEnter={(e) => {
                e.currentTarget.style.backgroundColor = "rgba(59,130,246,0.1)";
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.backgroundColor = "transparent";
              }}
            >
              使い方
            </button>
          )}
        </div>
      </div>

      {/* Bet slot cards */}
      <div className="space-y-3">
        {slots.map((slot, index) => (
          <BetSlotCard
            key={slot.slotId}
            slot={slot}
            index={index}
            total={slots.length}
            entries={entries}
            sortedEntries={sortedEntries}
            availableWakus={availableWakus}
            onUpdate={updateSlot}
            onRemove={removeSlot}
          />
        ))}
      </div>

      {/* Add slot button */}
      <button
        type="button"
        onClick={addSlot}
        className="flex w-full cursor-pointer items-center justify-center gap-2 rounded-xl py-3 text-sm font-medium transition-all duration-200"
        style={{
          border: "2px dashed var(--border)",
          color: "var(--text-muted)",
          backgroundColor: "transparent",
        }}
        onMouseEnter={(e) => {
          e.currentTarget.style.borderColor = "var(--accent)";
          e.currentTarget.style.color = "var(--accent)";
          e.currentTarget.style.backgroundColor = "rgba(59,130,246,0.05)";
        }}
        onMouseLeave={(e) => {
          e.currentTarget.style.borderColor = "var(--border)";
          e.currentTarget.style.color = "var(--text-muted)";
          e.currentTarget.style.backgroundColor = "transparent";
        }}
      >
        <svg className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" d="M12 4v16m8-8H4" />
        </svg>
        馬券を追加
      </button>

      {/* Combined summary & Save */}
      <div
        className="overflow-hidden rounded-xl"
        style={{
          backgroundColor: "var(--bg-elevated)",
          border: "1px solid var(--border)",
        }}
      >
        <div className="p-4">
          {/* Summary grid */}
          <div className="mb-4 grid grid-cols-3 gap-3 text-center">
            <div
              className="rounded-lg p-3"
              style={{ backgroundColor: "rgba(255,255,255,0.03)" }}
            >
              <div className="text-[10px] font-medium" style={{ color: "var(--text-muted)" }}>
                馬券数
              </div>
              <div className="text-lg font-bold tabular-nums" style={{ color: "var(--text-primary)" }}>
                {slots.length}
                <span className="text-xs font-normal" style={{ color: "var(--text-muted)" }}>件</span>
              </div>
            </div>
            <div
              className="rounded-lg p-3"
              style={{ backgroundColor: "rgba(255,255,255,0.03)" }}
            >
              <div className="text-[10px] font-medium" style={{ color: "var(--text-muted)" }}>
                合計投資
              </div>
              <div className="text-lg font-bold tabular-nums" style={{ color: "var(--text-primary)" }}>
                ¥{slotStats.totalAmount.toLocaleString()}
              </div>
            </div>
            <div
              className="rounded-lg p-3"
              style={{
                backgroundColor: "rgba(34,197,94,0.08)",
                border: slotStats.totalPayout > 0 ? "1px solid rgba(34,197,94,0.2)" : "none",
              }}
            >
              <div className="text-[10px] font-medium" style={{ color: "var(--text-muted)" }}>
                推定払戻合計
              </div>
              <div
                className="text-lg font-bold tabular-nums"
                style={{
                  color: slotStats.totalPayout > 0 ? "var(--green)" : "var(--text-muted)",
                }}
              >
                {slotStats.totalPayout > 0
                  ? `¥${slotStats.totalPayout.toLocaleString()}`
                  : "---"}
              </div>
            </div>
          </div>

          {/* Save all button */}
          <button
            type="button"
            onClick={handleSaveAll}
            disabled={!slotStats.allComplete || saving}
            className="w-full cursor-pointer rounded-xl py-3 text-sm font-bold transition-all duration-200"
            style={{
              background: slotStats.allComplete
                ? "linear-gradient(135deg, var(--accent), #8B5CF6)"
                : "var(--border)",
              color: slotStats.allComplete ? "#fff" : "var(--text-muted)",
              opacity: saving ? 0.6 : 1,
              boxShadow: slotStats.allComplete ? "0 4px 15px rgba(59,130,246,0.3)" : "none",
            }}
            onMouseEnter={(e) => {
              if (slotStats.allComplete) {
                e.currentTarget.style.boxShadow = "0 6px 20px rgba(59,130,246,0.4)";
                e.currentTarget.style.transform = "translateY(-1px)";
              }
            }}
            onMouseLeave={(e) => {
              if (slotStats.allComplete) {
                e.currentTarget.style.boxShadow = "0 4px 15px rgba(59,130,246,0.3)";
                e.currentTarget.style.transform = "translateY(0)";
              }
            }}
          >
            {saving
              ? "保存中..."
              : slotStats.allComplete
                ? `${slots.length}件の馬券をまとめて記録する`
                : `未入力の馬券があります（${slotStats.completeCount}/${slots.length}件入力済み）`}
          </button>

          {message && (
            <div
              className="mt-2 rounded-lg px-3 py-2 text-center text-xs"
              style={{
                backgroundColor: message.includes("失敗")
                  ? "rgba(239,68,68,0.1)"
                  : "rgba(34,197,94,0.1)",
                color: message.includes("失敗") ? "var(--red)" : "var(--green)",
              }}
            >
              {message}
            </div>
          )}
        </div>
      </div>

      {/* Session bet records (previously saved) */}
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
            <h3 className="text-sm font-bold" style={{ color: "var(--text-primary)" }}>
              記録済み馬券
              <span
                className="ml-2 rounded-full px-2 py-0.5 text-xs font-normal"
                style={{ backgroundColor: "rgba(59,130,246,0.15)", color: "var(--accent)" }}
              >
                {sessionBets.length}件
              </span>
            </h3>
            <div className="flex items-center gap-4">
              <div className="text-right">
                <div className="text-[10px]" style={{ color: "var(--text-muted)" }}>
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
                <div className="text-[10px]" style={{ color: "var(--text-muted)" }}>
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
                  borderBottom: i < sessionBets.length - 1 ? "1px solid var(--border)" : "none",
                }}
                onMouseEnter={(e) => {
                  e.currentTarget.style.backgroundColor = "rgba(255,255,255,0.02)";
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.backgroundColor = "transparent";
                }}
              >
                <div className="flex items-center gap-3">
                  <span
                    className="inline-flex rounded-md px-2 py-0.5 text-xs font-medium"
                    style={{ backgroundColor: "rgba(139,92,246,0.15)", color: "#A78BFA" }}
                  >
                    {b.betType}
                  </span>
                  <span className="text-sm" style={{ color: "var(--text-primary)" }}>
                    {b.horseNames}
                  </span>
                </div>
                <div className="flex items-center gap-4 text-right">
                  <span className="text-xs tabular-nums" style={{ color: "var(--text-muted)" }}>
                    {b.odds !== null ? `${b.odds.toFixed(1)}倍` : ""}
                  </span>
                  <span className="text-xs tabular-nums" style={{ color: "var(--text-secondary)" }}>
                    ¥{b.amount.toLocaleString()}
                  </span>
                  <span
                    className="text-sm font-semibold tabular-nums"
                    style={{ color: "var(--green)" }}
                  >
                    {b.payout !== null ? `¥${b.payout.toLocaleString()}` : "---"}
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
