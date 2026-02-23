/**
 * 馬券の組合せ計算ロジック（ボックス・フォーメーション・流し）
 */

export type BuyingMethodType = "normal" | "box" | "formation" | "nagashi";

// --- Math helpers ---

/** C(n, k) = n! / (k! * (n-k)!) */
function combination(n: number, k: number): number {
  if (k < 0 || k > n) return 0;
  if (k === 0 || k === n) return 1;
  // Use the smaller k for efficiency
  const kk = Math.min(k, n - k);
  let result = 1;
  for (let i = 0; i < kk; i++) {
    result = (result * (n - i)) / (i + 1);
  }
  return Math.round(result);
}

/** P(n, k) = n! / (n-k)! */
function permutation(n: number, k: number): number {
  if (k < 0 || k > n) return 0;
  let result = 1;
  for (let i = 0; i < k; i++) {
    result *= n - i;
  }
  return result;
}

// --- Box (ボックス) ---

/**
 * ボックスの点数計算
 * @param n 選択頭数
 * @param picks 馬券の必要頭数 (2 for 馬連/馬単, 3 for 三連複/三連単)
 * @param ordered true=順列 (馬単/三連単), false=組合せ (馬連/三連複/ワイド/枠連)
 */
export function boxCombinationCount(
  n: number,
  picks: number,
  ordered: boolean,
): number {
  if (n < picks) return 0;
  return ordered ? permutation(n, picks) : combination(n, picks);
}

/**
 * ボックスの全組合せ生成
 * @returns 例: [["1","3"], ["1","5"], ["3","5"]] (馬連3頭ボックス)
 */
export function generateBoxCombinations(
  horses: string[],
  picks: number,
  ordered: boolean,
): string[][] {
  if (horses.length < picks) return [];

  if (ordered) {
    // Permutations
    const result: string[][] = [];
    const generate = (current: string[], remaining: string[]) => {
      if (current.length === picks) {
        result.push([...current]);
        return;
      }
      for (let i = 0; i < remaining.length; i++) {
        current.push(remaining[i]);
        generate(current, [...remaining.slice(0, i), ...remaining.slice(i + 1)]);
        current.pop();
      }
    };
    generate([], horses);
    return result;
  } else {
    // Combinations
    const result: string[][] = [];
    const generate = (start: number, current: string[]) => {
      if (current.length === picks) {
        result.push([...current]);
        return;
      }
      for (let i = start; i < horses.length; i++) {
        current.push(horses[i]);
        generate(i + 1, current);
        current.pop();
      }
    };
    generate(0, []);
    return result;
  }
}

// --- Formation (フォーメーション) ---

/**
 * フォーメーションの点数計算
 * @param sets 各着順の候補馬リスト [[1着候補], [2着候補], [3着候補]]
 * @param ordered true=着順あり (馬単/三連単)
 */
export function formationCombinationCount(
  sets: string[][],
  ordered: boolean,
): number {
  const combos = generateFormationCombinations(sets, ordered);
  return combos.length;
}

/**
 * フォーメーションの全組合せ生成
 * 重複組合せは除外 (同じ馬が複数着順に入ることはない)
 */
export function generateFormationCombinations(
  sets: string[][],
  ordered: boolean,
): string[][] {
  if (sets.length === 0 || sets.some((s) => s.length === 0)) return [];

  const result: string[][] = [];
  const seen = new Set<string>();

  const generate = (depth: number, current: string[], usedSet: Set<string>) => {
    if (depth === sets.length) {
      // For unordered, normalize to sorted to deduplicate
      const key = ordered ? current.join(",") : [...current].sort().join(",");
      if (!seen.has(key)) {
        seen.add(key);
        result.push([...current]);
      }
      return;
    }
    for (const horse of sets[depth]) {
      if (usedSet.has(horse)) continue; // Same horse can't appear twice
      current.push(horse);
      usedSet.add(horse);
      generate(depth + 1, current, usedSet);
      current.pop();
      usedSet.delete(horse);
    }
  };

  generate(0, [], new Set());
  return result;
}

// --- Nagashi (流し) ---

/**
 * 流しの点数計算
 * @param axisHorses 軸馬リスト (1頭軸 or 2頭軸)
 * @param partners 相手馬リスト
 * @param picks 馬券の必要頭数
 * @param ordered 着順あり/なし
 * @param axisPositions 軸馬の固定位置 (ordered時: [0]=1着固定 etc). undefined=全位置
 */
export function nagashiCombinationCount(
  axisHorses: string[],
  partners: string[],
  picks: number,
  ordered: boolean,
  axisPositions?: number[],
): number {
  const combos = generateNagashiCombinations(
    axisHorses,
    partners,
    picks,
    ordered,
    axisPositions,
  );
  return combos.length;
}

/**
 * 流しの全組合せ生成
 */
export function generateNagashiCombinations(
  axisHorses: string[],
  partners: string[],
  picks: number,
  ordered: boolean,
  axisPositions?: number[],
): string[][] {
  const axisCount = axisHorses.length;
  const partnerPicks = picks - axisCount;

  if (partnerPicks < 1 || partners.length < partnerPicks) return [];

  // Get all partner combinations/permutations needed
  const partnerCombos = ordered && !axisPositions
    ? generateBoxCombinations(partners, partnerPicks, true)
    : generateBoxCombinations(partners, partnerPicks, false);

  const result: string[][] = [];
  const seen = new Set<string>();

  if (!ordered) {
    // Unordered: axis + each partner combo, sorted for dedup
    for (const pc of partnerCombos) {
      const combo = [...axisHorses, ...pc];
      const key = [...combo].sort().join(",");
      if (!seen.has(key)) {
        seen.add(key);
        result.push(combo);
      }
    }
  } else if (axisPositions && axisPositions.length === axisCount) {
    // Ordered with fixed axis positions
    for (const pc of partnerCombos) {
      // Place axis horses at their fixed positions, fill rest with partner permutations
      const partnerPerms = generateBoxCombinations(pc, pc.length, true);
      for (const pp of partnerPerms) {
        const combo = new Array<string>(picks);
        let pIdx = 0;
        for (let pos = 0; pos < picks; pos++) {
          const axisIdx = axisPositions.indexOf(pos);
          if (axisIdx >= 0) {
            combo[pos] = axisHorses[axisIdx];
          } else {
            combo[pos] = pp[pIdx++];
          }
        }
        const key = combo.join(",");
        if (!seen.has(key)) {
          seen.add(key);
          result.push(combo);
        }
      }
    }
  } else {
    // Ordered without fixed positions: axis can be at any position
    // Generate all permutations of [axisHorses + partnerCombo]
    for (const pc of partnerCombos) {
      const all = [...axisHorses, ...pc];
      const perms = generateBoxCombinations(all, picks, true);
      for (const perm of perms) {
        // Ensure all axis horses are included
        if (axisHorses.every((a) => perm.includes(a))) {
          const key = perm.join(",");
          if (!seen.has(key)) {
            seen.add(key);
            result.push(perm);
          }
        }
      }
    }
  }

  return result;
}

// --- Unified interface ---

export type BetSlotForCalc = {
  buyingMethod: BuyingMethodType;
  betType: string;
  boxSelections: string[];
  formationSets: string[][];
  axisHorses: string[];
  partnerHorses: string[];
  nagashiAxisPositions?: number[];
};

type BetTypeDef = {
  picks: number;
  ordered: boolean;
};

/**
 * 統一的な点数取得
 */
export function getPointCount(slot: BetSlotForCalc, typeDef: BetTypeDef): number {
  switch (slot.buyingMethod) {
    case "normal":
      return 1;
    case "box":
      return boxCombinationCount(
        slot.boxSelections.length,
        typeDef.picks,
        typeDef.ordered,
      );
    case "formation":
      return formationCombinationCount(slot.formationSets, typeDef.ordered);
    case "nagashi":
      return nagashiCombinationCount(
        slot.axisHorses,
        slot.partnerHorses,
        typeDef.picks,
        typeDef.ordered,
        slot.nagashiAxisPositions,
      );
    default:
      return 1;
  }
}

/**
 * 統一的な組合せ展開
 * @returns 各組合せの馬IDリスト
 */
export function expandCombinations(
  slot: BetSlotForCalc,
  typeDef: BetTypeDef,
): string[][] {
  switch (slot.buyingMethod) {
    case "normal":
      return []; // Normal doesn't expand
    case "box":
      return generateBoxCombinations(
        slot.boxSelections,
        typeDef.picks,
        typeDef.ordered,
      );
    case "formation":
      return generateFormationCombinations(slot.formationSets, typeDef.ordered);
    case "nagashi":
      return generateNagashiCombinations(
        slot.axisHorses,
        slot.partnerHorses,
        typeDef.picks,
        typeDef.ordered,
        slot.nagashiAxisPositions,
      );
    default:
      return [];
  }
}
