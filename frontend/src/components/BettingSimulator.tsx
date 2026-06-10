"use client";

import { useState, useMemo, useCallback, useEffect } from "react";
import {
  createBet,
  fetchComboOdds,
  fetchOddsTable,
  type RaceEntry,
  type BetRecord,
  type OddsComboEntry,
} from "@/lib/api";
import {
  type BuyingMethodType,
  getPointCount,
  expandCombinations,
} from "@/lib/betCalculations";

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

const BUYING_METHODS: {
  value: BuyingMethodType;
  label: string;
  supportedBetTypes: string[];
}[] = [
  {
    value: "normal",
    label: "通常",
    supportedBetTypes: ["tansho", "fukusho", "wakuren", "umaren", "umatan", "wide", "sanrenpuku", "sanrentan"],
  },
  {
    value: "box",
    label: "ボックス",
    supportedBetTypes: ["wakuren", "umaren", "umatan", "wide", "sanrenpuku", "sanrentan"],
  },
  {
    value: "formation",
    label: "フォーメーション",
    supportedBetTypes: ["umaren", "umatan", "wide", "sanrenpuku", "sanrentan"],
  },
  {
    value: "nagashi",
    label: "流し",
    supportedBetTypes: ["umaren", "umatan", "wide", "sanrenpuku", "sanrentan"],
  },
];

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
  buyingMethod: BuyingMethodType;
  selectedHorses: string[];       // normal mode selections
  boxSelections: string[];        // box mode: selected horse IDs
  formationSets: string[][];      // formation mode: per-position candidates
  axisHorses: string[];           // nagashi mode: axis horses
  partnerHorses: string[];        // nagashi mode: partner horses
  nagashiAxisCount: 1 | 2;        // nagashi mode: 1 or 2 axis horses
  nagashiAxisPositions: number[]; // nagashi ordered: which positions axis horses fix to
  manualOdds: string;
  amount: number;                 // 通常=掛け金 / 複数買い=1点あたりの既定掛け金
  fetchedOdds: number | null;
  oddsFetching: boolean;
  oddsFetchFailed: boolean;
  showCombinations: boolean;      // toggle for combination preview
  comboAmounts: Record<string, number>; // 複数買い: 買い目ごとの個別掛け金（未設定はamount）
  comboOdds: Record<string, number>;    // 複数買い: 買い目ごとの自動取得オッズ
};

type Props = {
  raceId: string;
  raceIdStr: string;
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
    buyingMethod: "normal",
    selectedHorses: Array(typeDef.picks).fill(""),
    boxSelections: [],
    formationSets: Array(typeDef.picks).fill(null).map(() => []),
    axisHorses: [],
    partnerHorses: [],
    nagashiAxisCount: 1,
    nagashiAxisPositions: [0], // default: axis at 1st position
    manualOdds: "",
    amount: 100,
    fetchedOdds: null,
    oddsFetching: false,
    oddsFetchFailed: false,
    showCombinations: false,
    comboAmounts: {},
    comboOdds: {},
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
  // Manual override takes priority
  if (slot.manualOdds) return parseFloat(slot.manualOdds);
  // Fetched odds (from API)
  if (slot.fetchedOdds !== null) return slot.fetchedOdds;
  // Tansho fallback: use entry win_odds
  if (slot.betType === "tansho" && slot.selectedHorses[0]) {
    const withOdds = entries.find(
      (e) => e.horse.id === slot.selectedHorses[0] && e.win_odds !== null,
    );
    const raw = withOdds
      ? withOdds.win_odds
      : (entries.find((e) => e.horse.id === slot.selectedHorses[0])?.win_odds ?? null);
    return raw !== null ? Number(raw) : null;
  }
  return null;
}

function getSlotPointCount(slot: BetSlotState): number {
  const typeDef = getTypeDef(slot.betType);
  return getPointCount(
    {
      buyingMethod: slot.buyingMethod,
      betType: slot.betType,
      boxSelections: slot.boxSelections,
      formationSets: slot.formationSets,
      axisHorses: slot.axisHorses,
      partnerHorses: slot.partnerHorses,
      nagashiAxisPositions: slot.nagashiAxisPositions,
    },
    { picks: typeDef.picks, ordered: typeDef.ordered },
  );
}

/** horse.id → 馬番(post_position) のマップ */
function buildIdToPost(entries: RaceEntry[]): Map<string, number> {
  const m = new Map<string, number>();
  for (const e of entries) {
    if (e.post_position != null) m.set(e.horse.id, e.post_position);
  }
  return m;
}

/** combo（馬ID配列 or 枠番）→ netkeibaオッズキー "01-02-03" */
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

/** 複数買いの全買い目（馬ID配列）を展開。通常は空配列。 */
function getSlotCombos(slot: BetSlotState): string[][] {
  if (slot.buyingMethod === "normal") return [];
  const typeDef = getTypeDef(slot.betType);
  return expandCombinations(
    {
      buyingMethod: slot.buyingMethod,
      betType: slot.betType,
      boxSelections: slot.boxSelections,
      formationSets: slot.formationSets,
      axisHorses: slot.axisHorses,
      partnerHorses: slot.partnerHorses,
      nagashiAxisPositions: slot.nagashiAxisPositions,
    },
    { picks: typeDef.picks, ordered: typeDef.ordered },
  );
}

/** 買い目ごとの掛け金（個別指定がなければ既定amount） */
function getComboAmount(slot: BetSlotState, key: string | null): number {
  if (key && slot.comboAmounts[key] != null) return slot.comboAmounts[key];
  return slot.amount;
}

/** スロットの合計賭け金（複数買いは買い目ごとの合算） */
function getSlotTotalCost(slot: BetSlotState, entries: RaceEntry[]): number {
  if (slot.buyingMethod === "normal") return slot.amount;
  const typeDef = getTypeDef(slot.betType);
  const idToPost = buildIdToPost(entries);
  let total = 0;
  for (const combo of getSlotCombos(slot)) {
    const key = buildComboKey(combo, typeDef.ordered, typeDef.isWaku, idToPost);
    total += getComboAmount(slot, key);
  }
  return total;
}

function isSlotComplete(slot: BetSlotState): boolean {
  const typeDef = getTypeDef(slot.betType);
  if (slot.amount <= 0) return false;

  switch (slot.buyingMethod) {
    case "normal":
      return (
        slot.selectedHorses.length === typeDef.picks &&
        slot.selectedHorses.every((h) => h !== "")
      );
    case "box":
      return slot.boxSelections.length >= typeDef.picks;
    case "formation":
      return (
        slot.formationSets.length === typeDef.picks &&
        slot.formationSets.every((s) => s.length > 0) &&
        getSlotPointCount(slot) > 0
      );
    case "nagashi": {
      // Axis count must match the configured nagashi mode (1-axis or 2-axis)
      if (slot.axisHorses.length !== slot.nagashiAxisCount) return false;
      const neededPartners = typeDef.picks - slot.axisHorses.length;
      return (
        slot.partnerHorses.length >= neededPartners &&
        getSlotPointCount(slot) > 0
      );
    }
    default:
      return false;
  }
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

/* ─── Horse Checkbox Grid (inline sub-component) ─── */

function HorseCheckboxGrid({
  entries,
  selected,
  onChange,
  label,
  isWaku,
  availableWakus,
}: {
  entries: RaceEntry[];
  selected: string[];
  onChange: (next: string[]) => void;
  label?: string;
  isWaku?: boolean;
  availableWakus?: number[];
}) {
  const items = isWaku
    ? (availableWakus ?? []).map((w) => ({
        id: String(w),
        label: `${w}枠`,
      }))
    : [...entries]
        .sort((a, b) => (a.post_position ?? 999) - (b.post_position ?? 999))
        .map((e) => ({
          id: e.horse.id,
          label: `${e.post_position ?? "?"}${e.horse.name}`,
        }));

  function toggle(id: string) {
    onChange(
      selected.includes(id)
        ? selected.filter((s) => s !== id)
        : [...selected, id],
    );
  }

  return (
    <div>
      {label && (
        <label
          className="mb-1 block text-[10px] font-medium"
          style={{ color: "var(--text-muted)" }}
        >
          {label}
        </label>
      )}
      <div className="flex flex-wrap gap-1">
        {items.length === 0 && (
          <span className="text-xs italic" style={{ color: "var(--text-muted)" }}>
            出走馬データなし
          </span>
        )}
        {items.map((item) => {
          const active = selected.includes(item.id);
          return (
            <button
              key={item.id}
              type="button"
              onClick={() => toggle(item.id)}
              className="cursor-pointer rounded-md px-2 py-1.5 text-xs font-medium transition-all duration-150"
              style={{
                backgroundColor: active ? "var(--accent)" : "rgba(255,255,255,0.05)",
                color: active ? "#fff" : "var(--text-muted)",
                border: active ? "1px solid var(--accent)" : "1px solid var(--border)",
              }}
            >
              {item.label}
            </button>
          );
        })}
      </div>
    </div>
  );
}

/* ─── Combination Breakdown（買い目別オッズ＋個別賭け金） ─── */

function ComboBreakdown({
  combos,
  slot,
  entries,
  isWaku,
  ordered,
  idToPost,
  oddsMap,
  oddsLoading,
  oddsStatus,
  onAmountChange,
  onResetAmounts,
}: {
  combos: string[][];
  slot: BetSlotState;
  entries: RaceEntry[];
  isWaku: boolean;
  ordered: boolean;
  idToPost: Map<string, number>;
  oddsMap: Map<string, OddsComboEntry>;
  oddsLoading: boolean;
  oddsStatus: string | null;
  onAmountChange: (key: string, amount: number) => void;
  onResetAmounts: () => void;
}) {
  const count = combos.length;

  function resolveLabel(id: string): string {
    if (isWaku) return `${id}枠`;
    const entry = entries.find((e) => e.horse.id === id);
    return entry ? `${entry.post_position ?? "?"}${entry.horse.name}` : id;
  }

  const rows = useMemo(() => {
    return combos.map((combo) => {
      const key = buildComboKey(combo, ordered, isWaku, idToPost);
      const entry = key ? oddsMap.get(key) : undefined;
      const odds = entry?.odds ?? null;
      const amount = getComboAmount(slot, key);
      const payout = odds != null && odds > 0 ? calculatePayout(amount, odds) : null;
      return {
        key,
        label: combo.map(resolveLabel).join(ordered ? " → " : " - "),
        odds,
        oddsLow: entry?.odds_low ?? null,
        oddsHigh: entry?.odds_high ?? null,
        amount,
        payout,
      };
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [combos, ordered, isWaku, idToPost, oddsMap, slot.comboAmounts, slot.amount]);

  const totalStake = rows.reduce((s, r) => s + (r.amount || 0), 0);
  const hasCustom = Object.keys(slot.comboAmounts).length > 0;

  if (count === 0) return null;

  return (
    <div>
      <div className="mb-1 flex items-center justify-between">
        <span className="text-[10px] font-medium" style={{ color: "var(--text-muted)" }}>
          買い目別オッズ・賭け金（{count}点）
          {oddsLoading && (
            <span className="ml-1" style={{ color: "var(--accent)" }}>
              オッズ取得中...
            </span>
          )}
          {!oddsLoading && oddsStatus && (
            <span className="ml-1" style={{ color: "var(--text-muted)" }}>
              {oddsStatus === "result" ? "確定" : oddsStatus === "middle" ? "暫定" : "予想"}オッズ
            </span>
          )}
        </span>
        {hasCustom && (
          <button
            type="button"
            onClick={onResetAmounts}
            className="cursor-pointer text-[10px] font-medium"
            style={{ color: "var(--accent)" }}
            title="全買い目を「1点あたり掛け金」に戻す"
          >
            均等に戻す
          </button>
        )}
      </div>
      <div
        className="max-h-60 overflow-y-auto rounded-lg"
        style={{ border: "1px solid var(--border)" }}
      >
        <table className="w-full text-xs">
          <thead className="sticky top-0">
            <tr
              className="text-left text-[9px] font-semibold uppercase tracking-wider"
              style={{ backgroundColor: "var(--bg-elevated)", color: "var(--text-muted)" }}
            >
              <th className="px-2 py-1.5">買い目</th>
              <th className="px-2 py-1.5 text-right">オッズ</th>
              <th className="px-2 py-1.5 text-right">掛け金</th>
              <th className="px-2 py-1.5 text-right">的中時払戻</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r, i) => {
              const oddsText =
                r.oddsLow != null && r.oddsHigh != null && r.oddsLow !== r.oddsHigh
                  ? `${r.oddsLow.toFixed(1)}〜${r.oddsHigh.toFixed(1)}`
                  : r.odds != null
                    ? `${r.odds.toFixed(1)}`
                    : "—";
              return (
                <tr
                  key={r.key ?? i}
                  style={{ borderTop: i === 0 ? "none" : "1px solid var(--border)" }}
                >
                  <td
                    className="px-2 py-1 font-medium tabular-nums"
                    style={{ color: "var(--text-primary)" }}
                  >
                    {r.label}
                  </td>
                  <td
                    className="px-2 py-1 text-right tabular-nums"
                    style={{
                      color:
                        r.odds != null && r.odds <= 10
                          ? "var(--accent)"
                          : "var(--text-secondary)",
                    }}
                  >
                    {oddsText}
                  </td>
                  <td className="px-2 py-1 text-right">
                    <input
                      type="number"
                      min={0}
                      step={100}
                      value={r.amount}
                      disabled={!r.key}
                      onChange={(e) =>
                        r.key && onAmountChange(r.key, Number(e.target.value))
                      }
                      className="w-16 rounded px-1 py-0.5 text-right text-xs tabular-nums"
                      style={{
                        backgroundColor: "rgba(255,255,255,0.04)",
                        border: "1px solid var(--border)",
                        color: "var(--text-primary)",
                      }}
                    />
                  </td>
                  <td
                    className="px-2 py-1 text-right tabular-nums"
                    style={{ color: "var(--text-muted)" }}
                  >
                    {r.payout != null ? `¥${r.payout.toLocaleString()}` : "—"}
                  </td>
                </tr>
              );
            })}
          </tbody>
          <tfoot>
            <tr style={{ borderTop: "1px solid var(--border)", backgroundColor: "rgba(255,255,255,0.02)" }}>
              <td className="px-2 py-1.5 text-[10px] font-semibold" style={{ color: "var(--text-muted)" }}>
                合計
              </td>
              <td />
              <td
                className="px-2 py-1.5 text-right text-xs font-bold tabular-nums"
                style={{ color: "var(--text-primary)" }}
              >
                ¥{totalStake.toLocaleString()}
              </td>
              <td />
            </tr>
          </tfoot>
        </table>
      </div>
    </div>
  );
}

/* ─── Single Bet Slot Card ─── */

function BetSlotCard({
  slot,
  index,
  total,
  raceId,
  entries,
  sortedEntries,
  availableWakus,
  onUpdate,
  onRemove,
}: {
  slot: BetSlotState;
  index: number;
  total: number;
  raceId: string;
  entries: RaceEntry[];
  sortedEntries: RaceEntry[];
  availableWakus: number[];
  onUpdate: (slotId: string, patch: Partial<BetSlotState>) => void;
  onRemove: (slotId: string) => void;
}) {
  const typeDef = getTypeDef(slot.betType);
  const effectiveOdds = getSlotOdds(slot, entries);
  const pointCount = getSlotPointCount(slot);
  const totalCost = getSlotTotalCost(slot, entries);

  // For normal mode: auto-fetch odds when all horses are selected
  const isNormal = slot.buyingMethod === "normal";
  const isMulti = !isNormal;
  const oddsSupported = slot.betType !== "tansho" && slot.betType !== "fukusho";

  // 馬番マップ（買い目→オッズキー変換用）
  const idToPost = useMemo(() => buildIdToPost(entries), [entries]);

  // 複数買い: 券種の全組オッズ表を自動取得
  const [oddsTable, setOddsTable] = useState<OddsComboEntry[] | null>(null);
  const [oddsTableLoading, setOddsTableLoading] = useState(false);
  const [oddsTableStatus, setOddsTableStatus] = useState<string | null>(null);

  useEffect(() => {
    if (!isMulti || !oddsSupported) {
      setOddsTable(null);
      setOddsTableStatus(null);
      return;
    }
    let cancelled = false;
    setOddsTableLoading(true);
    fetchOddsTable(raceId, slot.betType)
      .then((res) => {
        if (cancelled) return;
        setOddsTable(res.combos);
        setOddsTableStatus(res.status);
      })
      .catch(() => {
        if (!cancelled) setOddsTable(null);
      })
      .finally(() => {
        if (!cancelled) setOddsTableLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [raceId, slot.betType, isMulti, oddsSupported]);

  const oddsMap = useMemo(() => {
    const m = new Map<string, OddsComboEntry>();
    for (const c of oddsTable ?? []) m.set(c.combo, c);
    return m;
  }, [oddsTable]);
  const allHorsesSelected = isNormal &&
    slot.selectedHorses.length === typeDef.picks &&
    slot.selectedHorses.every((h) => h !== "");
  const selectionsKey = slot.selectedHorses.join(",");

  useEffect(() => {
    if (!isNormal || !allHorsesSelected || slot.manualOdds) return;
    if (slot.betType === "tansho") return;

    let cancelled = false;
    onUpdate(slot.slotId, { oddsFetching: true, fetchedOdds: null, oddsFetchFailed: false });

    let selections: number[];
    if (typeDef.isWaku) {
      selections = slot.selectedHorses.map(Number);
    } else {
      selections = slot.selectedHorses.map((hid) => {
        const entry = entries.find((e) => e.horse.id === hid);
        return entry?.post_position ?? 0;
      }).filter((n) => n > 0);
    }

    if (selections.length !== typeDef.picks) {
      onUpdate(slot.slotId, { oddsFetching: false, oddsFetchFailed: true });
      return;
    }

    fetchComboOdds(raceId, slot.betType, selections)
      .then((res) => {
        if (!cancelled) {
          if (res.odds !== null) {
            onUpdate(slot.slotId, { fetchedOdds: res.odds, oddsFetching: false, oddsFetchFailed: false });
          } else {
            onUpdate(slot.slotId, { oddsFetching: false, oddsFetchFailed: true });
          }
        }
      })
      .catch(() => {
        if (!cancelled) {
          onUpdate(slot.slotId, { oddsFetching: false, oddsFetchFailed: true });
        }
      });

    return () => { cancelled = true; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [slot.betType, selectionsKey, allHorsesSelected, isNormal]);

  const estimatedPayout =
    isNormal && effectiveOdds !== null && effectiveOdds > 0 && slot.amount > 0
      ? calculatePayout(slot.amount, effectiveOdds)
      : null;

  const pickLabels = typeDef.isWaku
    ? PICK_LABELS_WAKU
    : typeDef.ordered
      ? PICK_LABELS_ORDERED[typeDef.picks]
      : PICK_LABELS_UNORDERED[typeDef.picks];

  // Available buying methods for the current bet type
  const availableMethods = BUYING_METHODS.filter((m) =>
    m.supportedBetTypes.includes(slot.betType),
  );

  // Get combinations for non-normal modes
  const combinations = useMemo(() => {
    if (slot.buyingMethod === "normal") return [];
    return expandCombinations(
      {
        buyingMethod: slot.buyingMethod,
        betType: slot.betType,
        boxSelections: slot.boxSelections,
        formationSets: slot.formationSets,
        axisHorses: slot.axisHorses,
        partnerHorses: slot.partnerHorses,
        nagashiAxisPositions: slot.nagashiAxisPositions,
      },
      { picks: typeDef.picks, ordered: typeDef.ordered },
    );
  }, [
    slot.buyingMethod, slot.betType, slot.boxSelections,
    slot.formationSets, slot.axisHorses, slot.partnerHorses,
    slot.nagashiAxisPositions, typeDef.picks, typeDef.ordered,
  ]);

  // 展開した買い目の自動オッズを抽出（保存・集計用にスロットへ永続化）
  const comboOddsForState = useMemo(() => {
    const m: Record<string, number> = {};
    for (const combo of combinations) {
      const key = buildComboKey(combo, typeDef.ordered, typeDef.isWaku, idToPost);
      if (!key) continue;
      const e = oddsMap.get(key);
      if (e?.odds != null) m[key] = e.odds;
    }
    return m;
  }, [combinations, typeDef.ordered, typeDef.isWaku, idToPost, oddsMap]);

  useEffect(() => {
    const cur = slot.comboOdds ?? {};
    const next = comboOddsForState;
    const keys = Object.keys(next);
    const same =
      keys.length === Object.keys(cur).length &&
      keys.every((k) => cur[k] === next[k]);
    if (!same) onUpdate(slot.slotId, { comboOdds: next });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [comboOddsForState]);

  function handleBetTypeChange(value: string) {
    const newType = BET_TYPES.find((t) => t.value === value) ?? BET_TYPES[0];
    // Reset buying method if not supported
    const methodSupported = BUYING_METHODS.find(
      (m) => m.value === slot.buyingMethod,
    )?.supportedBetTypes.includes(value);
    onUpdate(slot.slotId, {
      betType: value,
      buyingMethod: methodSupported ? slot.buyingMethod : "normal",
      selectedHorses: Array(newType.picks).fill(""),
      boxSelections: [],
      formationSets: Array(newType.picks).fill(null).map(() => []),
      axisHorses: [],
      partnerHorses: [],
      nagashiAxisPositions: [0],
      manualOdds: "",
      fetchedOdds: null,
      oddsFetching: false,
      oddsFetchFailed: false,
      showCombinations: false,
      comboAmounts: {},
      comboOdds: {},
    });
  }

  function handleBuyingMethodChange(method: BuyingMethodType) {
    onUpdate(slot.slotId, {
      buyingMethod: method,
      selectedHorses: Array(typeDef.picks).fill(""),
      boxSelections: [],
      formationSets: Array(typeDef.picks).fill(null).map(() => []),
      axisHorses: [],
      partnerHorses: [],
      nagashiAxisPositions: [0],
      manualOdds: "",
      fetchedOdds: null,
      oddsFetching: false,
      oddsFetchFailed: false,
      showCombinations: false,
      comboAmounts: {},
      comboOdds: {},
    });
  }

  function handleHorseChange(idx: number, horseId: string) {
    const next = [...slot.selectedHorses];
    next[idx] = horseId;
    onUpdate(slot.slotId, { selectedHorses: next });
  }

  // Formation: labels per position
  const formationLabels = typeDef.ordered
    ? (PICK_LABELS_ORDERED[typeDef.picks] ?? [])
    : (PICK_LABELS_UNORDERED[typeDef.picks] ?? []);

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
          {slot.buyingMethod !== "normal" && (
            <span
              className="rounded-full px-1.5 py-0.5 text-[9px] font-medium"
              style={{ backgroundColor: "rgba(139,92,246,0.15)", color: "#A78BFA" }}
            >
              {BUYING_METHODS.find((m) => m.value === slot.buyingMethod)?.label}
            </span>
          )}
          <span className="text-xs" style={{ color: "var(--text-muted)" }}>
            {typeDef.desc}
          </span>
        </div>
        <div className="flex items-center gap-2">
          {/* Point count & cost badge for multi-bet modes */}
          {slot.buyingMethod !== "normal" && pointCount > 0 && (
            <span
              className="rounded-full px-2 py-0.5 text-[10px] font-semibold tabular-nums"
              style={{
                backgroundColor: "rgba(59,130,246,0.15)",
                color: "var(--accent)",
              }}
            >
              {pointCount}点 ¥{totalCost.toLocaleString()}
            </span>
          )}
          {/* Payout badge (normal mode only) */}
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
        {/* No entries warning */}
        {entries.length === 0 && (
          <div
            className="flex items-center gap-2 rounded-lg px-3 py-2.5 text-xs"
            style={{
              backgroundColor: "rgba(245,158,11,0.1)",
              color: "#F59E0B",
              border: "1px solid rgba(245,158,11,0.2)",
            }}
          >
            <svg className="h-4 w-4 shrink-0" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
            </svg>
            出馬表データが未取得のため馬を選択できません。出馬表スクレイピング実行後にご利用ください。
          </div>
        )}

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

        {/* Buying method pills (only show if more than 1 method available) */}
        {availableMethods.length > 1 && (
          <div className="flex flex-wrap gap-1">
            {availableMethods.map((m) => (
              <button
                key={m.value}
                type="button"
                onClick={() => handleBuyingMethodChange(m.value)}
                className="cursor-pointer rounded-full px-2.5 py-1 text-[10px] font-medium transition-all duration-200"
                style={{
                  backgroundColor:
                    slot.buyingMethod === m.value
                      ? "rgba(139,92,246,0.9)"
                      : "rgba(255,255,255,0.03)",
                  color: slot.buyingMethod === m.value ? "#fff" : "var(--text-muted)",
                  border:
                    slot.buyingMethod === m.value
                      ? "1px solid rgba(139,92,246,0.9)"
                      : "1px solid var(--border)",
                }}
              >
                {m.label}
              </button>
            ))}
          </div>
        )}

        {/* ===== NORMAL MODE ===== */}
        {slot.buyingMethod === "normal" && (
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
        )}

        {/* ===== BOX MODE ===== */}
        {slot.buyingMethod === "box" && (
          <div className="space-y-2">
            <HorseCheckboxGrid
              entries={sortedEntries}
              selected={slot.boxSelections}
              onChange={(next) => onUpdate(slot.slotId, { boxSelections: next, manualOdds: "", fetchedOdds: null })}
              label={`対象${typeDef.isWaku ? "枠" : "馬"}を選択（${typeDef.picks}頭以上）`}
              isWaku={typeDef.isWaku}
              availableWakus={availableWakus}
            />
            {slot.boxSelections.length >= typeDef.picks && (
              <div className="text-xs tabular-nums" style={{ color: "var(--text-secondary)" }}>
                {slot.boxSelections.length}頭選択 = <strong>{pointCount}点</strong> × ¥{slot.amount.toLocaleString()} = <strong style={{ color: "var(--accent)" }}>¥{totalCost.toLocaleString()}</strong>
              </div>
            )}
          </div>
        )}

        {/* ===== FORMATION MODE ===== */}
        {slot.buyingMethod === "formation" && (
          <div className="space-y-2">
            {Array.from({ length: typeDef.picks }).map((_, posIdx) => (
              <HorseCheckboxGrid
                key={posIdx}
                entries={sortedEntries}
                selected={slot.formationSets[posIdx] ?? []}
                onChange={(next) => {
                  const newSets = [...slot.formationSets];
                  newSets[posIdx] = next;
                  onUpdate(slot.slotId, { formationSets: newSets, manualOdds: "", fetchedOdds: null });
                }}
                label={`${formationLabels[posIdx] ?? `${posIdx + 1}着`}候補`}
                isWaku={typeDef.isWaku}
                availableWakus={availableWakus}
              />
            ))}
            {pointCount > 0 && (
              <div className="text-xs tabular-nums" style={{ color: "var(--text-secondary)" }}>
                <strong>{pointCount}点</strong> × ¥{slot.amount.toLocaleString()} = <strong style={{ color: "var(--accent)" }}>¥{totalCost.toLocaleString()}</strong>
              </div>
            )}
          </div>
        )}

        {/* ===== NAGASHI MODE ===== */}
        {slot.buyingMethod === "nagashi" && (
          <div className="space-y-2">
            {/* Axis count toggle */}
            {typeDef.picks === 3 && (
              <div className="flex items-center gap-2">
                <span className="text-[10px] font-medium" style={{ color: "var(--text-muted)" }}>
                  軸タイプ:
                </span>
                {([1, 2] as const).map((n) => (
                  <button
                    key={n}
                    type="button"
                    onClick={() => {
                      const newPositions = n === 1 ? [0] : [0, 1];
                      onUpdate(slot.slotId, {
                        nagashiAxisCount: n,
                        axisHorses: slot.axisHorses.slice(0, n),
                        nagashiAxisPositions: newPositions,
                        manualOdds: "",
                        fetchedOdds: null,
                      });
                    }}
                    className="cursor-pointer rounded-full px-2 py-0.5 text-[10px] font-medium transition-all duration-150"
                    style={{
                      backgroundColor: slot.nagashiAxisCount === n ? "var(--accent)" : "rgba(255,255,255,0.05)",
                      color: slot.nagashiAxisCount === n ? "#fff" : "var(--text-muted)",
                      border: slot.nagashiAxisCount === n ? "1px solid var(--accent)" : "1px solid var(--border)",
                    }}
                  >
                    {n}頭軸
                  </button>
                ))}
              </div>
            )}

            {/* Axis position selector (for ordered bet types) */}
            {typeDef.ordered && (
              <div className="flex items-center gap-2">
                <span className="text-[10px] font-medium" style={{ color: "var(--text-muted)" }}>
                  軸馬位置:
                </span>
                {Array.from({ length: typeDef.picks }).map((_, pos) => {
                  // For 2-axis, each axis gets one position
                  const axisIdx = slot.nagashiAxisPositions.indexOf(pos);
                  const isSelected = axisIdx >= 0;
                  return (
                    <button
                      key={pos}
                      type="button"
                      onClick={() => {
                        if (slot.nagashiAxisCount === 1) {
                          onUpdate(slot.slotId, { nagashiAxisPositions: [pos], manualOdds: "", fetchedOdds: null });
                        } else {
                          // Toggle position for 2-axis
                          let newPos = [...slot.nagashiAxisPositions];
                          if (isSelected) {
                            newPos = newPos.filter((p) => p !== pos);
                          } else {
                            newPos.push(pos);
                            if (newPos.length > slot.nagashiAxisCount) {
                              newPos = newPos.slice(-slot.nagashiAxisCount);
                            }
                          }
                          newPos.sort((a, b) => a - b);
                          onUpdate(slot.slotId, { nagashiAxisPositions: newPos, manualOdds: "", fetchedOdds: null });
                        }
                      }}
                      className="cursor-pointer rounded-full px-2 py-0.5 text-[10px] font-medium transition-all duration-150"
                      style={{
                        backgroundColor: isSelected ? "rgba(139,92,246,0.9)" : "rgba(255,255,255,0.05)",
                        color: isSelected ? "#fff" : "var(--text-muted)",
                        border: isSelected ? "1px solid rgba(139,92,246,0.9)" : "1px solid var(--border)",
                      }}
                    >
                      {pos + 1}着固定
                    </button>
                  );
                })}
              </div>
            )}

            {/* Axis horse selection */}
            <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
              {Array.from({ length: slot.nagashiAxisCount }).map((_, axIdx) => (
                <div key={axIdx}>
                  <label
                    className="mb-0.5 block text-[10px] font-medium"
                    style={{ color: "var(--text-muted)" }}
                  >
                    軸馬{slot.nagashiAxisCount > 1 ? ` ${axIdx + 1}` : ""}
                  </label>
                  <select
                    value={slot.axisHorses[axIdx] ?? ""}
                    onChange={(e) => {
                      const next = [...slot.axisHorses];
                      next[axIdx] = e.target.value;
                      // Remove from partners if selected as axis
                      const newPartners = slot.partnerHorses.filter(
                        (p) => !next.includes(p),
                      );
                      onUpdate(slot.slotId, {
                        axisHorses: next.filter(Boolean),
                        partnerHorses: newPartners,
                        manualOdds: "",
                        fetchedOdds: null,
                      });
                    }}
                    className="w-full cursor-pointer rounded-lg px-2.5 py-2 text-sm transition-colors duration-200"
                    style={{
                      backgroundColor: "#fff",
                      border: slot.axisHorses[axIdx] ? "1px solid var(--accent)" : "1px solid var(--border)",
                      color: "#000",
                    }}
                  >
                    <option value="">軸馬を選択</option>
                    {sortedEntries
                      .filter(
                        (e) =>
                          e.horse.id === slot.axisHorses[axIdx] ||
                          !slot.axisHorses.some((a, i) => i !== axIdx && a === e.horse.id),
                      )
                      .map((e, i) => (
                        <option key={`${e.horse.id}-${i}`} value={e.horse.id}>
                          {e.post_position ?? "?"}. {e.horse.name}
                          {e.win_odds !== null ? ` (${Number(e.win_odds).toFixed(1)}倍)` : ""}
                        </option>
                      ))}
                  </select>
                </div>
              ))}
            </div>

            {/* Partner horse checkboxes */}
            <HorseCheckboxGrid
              entries={sortedEntries.filter(
                (e) => !slot.axisHorses.includes(e.horse.id),
              )}
              selected={slot.partnerHorses}
              onChange={(next) =>
                onUpdate(slot.slotId, { partnerHorses: next, manualOdds: "", fetchedOdds: null })
              }
              label="相手馬を選択"
            />

            {pointCount > 0 && (
              <div className="text-xs tabular-nums" style={{ color: "var(--text-secondary)" }}>
                <strong>{pointCount}点</strong> × ¥{slot.amount.toLocaleString()} = <strong style={{ color: "var(--accent)" }}>¥{totalCost.toLocaleString()}</strong>
              </div>
            )}
          </div>
        )}

        {/* 買い目別オッズ・賭け金（複数買い） */}
        {isMulti && combinations.length > 0 && (
          <ComboBreakdown
            combos={combinations}
            slot={slot}
            entries={entries}
            isWaku={typeDef.isWaku}
            ordered={typeDef.ordered}
            idToPost={idToPost}
            oddsMap={oddsMap}
            oddsLoading={oddsTableLoading}
            oddsStatus={oddsTableStatus}
            onAmountChange={(key, amount) =>
              onUpdate(slot.slotId, {
                comboAmounts: { ...slot.comboAmounts, [key]: amount },
              })
            }
            onResetAmounts={() => onUpdate(slot.slotId, { comboAmounts: {} })}
          />
        )}

        {/* Large combination warning */}
        {slot.buyingMethod !== "normal" && pointCount > 100 && (
          <div
            className="rounded-lg px-3 py-2 text-xs"
            style={{
              backgroundColor: "rgba(245,158,11,0.1)",
              color: "#F59E0B",
              border: "1px solid rgba(245,158,11,0.2)",
            }}
          >
            {pointCount}点の大量買いです。合計 ¥{totalCost.toLocaleString()} になります。
          </div>
        )}

        {/* Odds & Amount row */}
        <div className={`grid gap-2 ${isMulti ? "grid-cols-1" : "grid-cols-2"}`}>
          {isNormal && (
          <div>
            <label
              className="mb-0.5 block text-[10px] font-medium"
              style={{ color: "var(--text-muted)" }}
            >
              {slot.buyingMethod !== "normal" ? "代表オッズ" : "オッズ"}
              {slot.oddsFetching && (
                <span
                  className="ml-1 rounded-full px-1 py-0.5 text-[9px]"
                  style={{ backgroundColor: "rgba(59,130,246,0.15)", color: "var(--accent)" }}
                >
                  取得中...
                </span>
              )}
              {!slot.oddsFetching && effectiveOdds !== null && !slot.manualOdds && (
                <span
                  className="ml-1 rounded-full px-1 py-0.5 text-[9px]"
                  style={{ backgroundColor: "rgba(34,197,94,0.15)", color: "var(--green)" }}
                >
                  自動
                </span>
              )}
              {!slot.oddsFetching && slot.oddsFetchFailed && effectiveOdds === null && !slot.manualOdds && (
                <span
                  className="ml-1 rounded-full px-1 py-0.5 text-[9px]"
                  style={{ backgroundColor: "rgba(239,68,68,0.15)", color: "var(--red)" }}
                >
                  取得不可
                </span>
              )}
            </label>
            {effectiveOdds !== null && !slot.manualOdds ? (
              <div className="flex items-center gap-1">
                <div
                  className="flex-1 rounded-lg px-2.5 py-2 text-sm font-semibold tabular-nums"
                  style={{
                    backgroundColor: "rgba(255,255,255,0.03)",
                    border: "1px solid var(--border)",
                    color: "var(--text-primary)",
                  }}
                >
                  {effectiveOdds.toFixed(1)} 倍
                </div>
                <button
                  type="button"
                  onClick={() => onUpdate(slot.slotId, { manualOdds: String(effectiveOdds.toFixed(1)) })}
                  className="cursor-pointer rounded px-1.5 py-2 text-[9px] transition-colors"
                  style={{ color: "var(--text-muted)" }}
                  title="手動で上書き"
                >
                  編集
                </button>
              </div>
            ) : (
              <input
                type="number"
                min={1}
                step={0.1}
                value={slot.manualOdds}
                onChange={(e) => onUpdate(slot.slotId, { manualOdds: e.target.value, fetchedOdds: null })}
                placeholder={
                  slot.buyingMethod !== "normal"
                    ? "代表オッズを入力"
                    : slot.oddsFetching
                      ? "取得中..."
                      : slot.oddsFetchFailed
                        ? "オッズを入力"
                        : allHorsesSelected
                          ? "自動取得中..."
                          : "例: 12.5"
                }
                className="w-full rounded-lg px-2.5 py-2 text-sm tabular-nums"
                style={{
                  backgroundColor: "rgba(255,255,255,0.03)",
                  border: "1px solid var(--border)",
                  color: "var(--text-primary)",
                }}
              />
            )}
          </div>
          )}
          <div>
            <label
              className="mb-0.5 block text-[10px] font-medium"
              style={{ color: "var(--text-muted)" }}
            >
              {isMulti ? "1点あたり掛け金（全買い目の初期値）" : "掛け金"}
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
  raceIdStr,
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
      const newType = BET_TYPES.find((t) => t.value === prefillBetType) ?? BET_TYPES[0];
      return [
        ...prev,
        {
          slotId: newSlotId(),
          betType: prefillBetType,
          buyingMethod: "normal" as BuyingMethodType,
          selectedHorses: adjusted,
          boxSelections: [],
          formationSets: Array(newType.picks).fill(null).map(() => []),
          axisHorses: [],
          partnerHorses: [],
          nagashiAxisCount: 1 as const,
          nagashiAxisPositions: [0],
          manualOdds: "",
          amount: 100,
          fetchedOdds: null,
          oddsFetching: false,
          oddsFetchFailed: false,
          showCombinations: false,
          comboAmounts: {},
          comboOdds: {},
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
    let totalPoints = 0;
    let totalAmount = 0;
    let totalPayout = 0;
    let allComplete = true;
    let completeCount = 0;
    for (const slot of slots) {
      const points = getSlotPointCount(slot);
      totalPoints += points;
      if (slot.buyingMethod === "normal") {
        totalAmount += slot.amount;
        const odds = getSlotOdds(slot, entries);
        if (odds !== null && odds > 0 && slot.amount > 0) {
          totalPayout += calculatePayout(slot.amount, odds);
        }
      } else {
        // 複数買い: 買い目ごとの掛け金を合算。払戻は的中1点あたりの最大払戻。
        const typeDef = getTypeDef(slot.betType);
        const idToPost = buildIdToPost(entries);
        let maxPayout = 0;
        for (const combo of getSlotCombos(slot)) {
          const key = buildComboKey(combo, typeDef.ordered, typeDef.isWaku, idToPost);
          const amt = getComboAmount(slot, key);
          totalAmount += amt;
          const o = key ? slot.comboOdds[key] : undefined;
          if (o != null && o > 0 && amt > 0) {
            maxPayout = Math.max(maxPayout, calculatePayout(amt, o));
          }
        }
        totalPayout += maxPayout;
      }
      if (isSlotComplete(slot)) {
        completeCount++;
      } else {
        allComplete = false;
      }
    }
    return { totalPoints, totalAmount, totalPayout, allComplete, completeCount };
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

      if (slot.buyingMethod === "normal") {
        // Normal: save single bet
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
      } else {
        // Multi-bet: expand combinations and save each
        const combos = expandCombinations(
          {
            buyingMethod: slot.buyingMethod,
            betType: slot.betType,
            boxSelections: slot.boxSelections,
            formationSets: slot.formationSets,
            axisHorses: slot.axisHorses,
            partnerHorses: slot.partnerHorses,
            nagashiAxisPositions: slot.nagashiAxisPositions,
          },
          { picks: typeDef.picks, ordered: typeDef.ordered },
        );
        const idToPost = buildIdToPost(entries);
        for (const combo of combos) {
          const key = buildComboKey(combo, typeDef.ordered, typeDef.isWaku, idToPost);
          const comboAmount = getComboAmount(slot, key);
          const comboOdds = key && slot.comboOdds[key] != null ? slot.comboOdds[key] : null;
          const horseNames = typeDef.isWaku
            ? combo.map((w) => `${w}枠`).join(", ")
            : combo
                .map((hid) => entries.find((e) => e.horse.id === hid)?.horse.name ?? "")
                .filter(Boolean)
                .join(", ");
          try {
            const record: BetRecord = await createBet({
              race_id: raceId,
              bet_date: raceDate,
              bet_type: slot.betType,
              horse_names: horseNames,
              amount_yen: comboAmount,
              odds_at_bet: comboOdds,
            });
            savedBets.push({
              id: record.id,
              betType: typeDef.label,
              horseNames,
              amount: comboAmount,
              odds: comboOdds,
              payout:
                comboOdds !== null && comboOdds > 0
                  ? calculatePayout(comboAmount, comboOdds)
                  : null,
            });
          } catch {
            failCount++;
          }
        }
      }
    }

    for (const bet of savedBets) {
      onBetSaved(bet);
    }

    if (failCount === 0) {
      setMessage(`${savedBets.length}件の馬券を記録しました`);
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
              {slots.length}件（{slotStats.totalPoints}点）を設定中
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
            raceId={raceIdStr}
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
                合計点数
              </div>
              <div className="text-lg font-bold tabular-nums" style={{ color: "var(--text-primary)" }}>
                {slotStats.totalPoints}
                <span className="text-xs font-normal" style={{ color: "var(--text-muted)" }}>点</span>
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
                ? `${slotStats.totalPoints}点の馬券をまとめて記録する（¥${slotStats.totalAmount.toLocaleString()}）`
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
