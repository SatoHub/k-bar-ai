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

// --- Nagashi patterns (着順固定 / マルチ) ---

/**
 * 流しの着順パターン定義。
 * - axisPositions: 軸馬を固定する着順（0=1着, 1=2着, 2=3着）。
 *   axisHorses[i] が axisPositions[i] の着に入る。undefined = マルチ（全着順網羅）。
 * - multi: true のとき軸の着順を入れ替えた組合せも全て購入（JRAのマルチ投票）。
 */
export type NagashiPattern = {
  key: string;
  label: string;
  axisPositions?: number[];
  multi: boolean;
  desc: string;
};

/**
 * 券種・軸頭数に応じて、ネット馬券（JRA即PAT）で選べる流しパターンを返す。
 * @param picks 必要頭数（2 or 3）
 * @param ordered 着順あり（馬単/三連単）
 * @param axisCount 軸の頭数（1 or 2）
 */
export function getNagashiPatterns(
  picks: number,
  ordered: boolean,
  axisCount: number,
): NagashiPattern[] {
  if (picks < 2) return [];

  // 着順なし（枠連/馬連/ワイド/三連複）
  if (!ordered) {
    return [
      {
        key: "std",
        label: axisCount >= 2 ? "軸2頭ながし" : "軸1頭ながし",
        multi: false,
        desc:
          axisCount >= 2
            ? "軸2頭＋相手1頭（着順不問）"
            : "軸1頭＋相手（着順不問）",
      },
    ];
  }

  // 馬単（着順あり・2頭）— 軸は1頭
  if (picks === 2) {
    return [
      { key: "pos1", label: "1着ながし", axisPositions: [0], multi: false, desc: "軸を1着に固定" },
      { key: "pos2", label: "2着ながし", axisPositions: [1], multi: false, desc: "軸を2着に固定" },
      { key: "multi", label: "マルチ", multi: true, desc: "1着・2着の入れ替えも両取り（2倍）" },
    ];
  }

  // 三連単（着順あり・3頭）
  if (axisCount >= 2) {
    return [
      { key: "pos12", label: "1・2着ながし", axisPositions: [0, 1], multi: false, desc: "①を1着・②を2着に固定" },
      { key: "pos13", label: "1・3着ながし", axisPositions: [0, 2], multi: false, desc: "①を1着・②を3着に固定" },
      { key: "pos23", label: "2・3着ながし", axisPositions: [1, 2], multi: false, desc: "①を2着・②を3着に固定" },
      { key: "multi", label: "軸2頭マルチ", multi: true, desc: "軸2頭の全着順を網羅（相手1頭につき6通り）" },
    ];
  }
  return [
    { key: "pos1", label: "1着ながし", axisPositions: [0], multi: false, desc: "軸を1着に固定" },
    { key: "pos2", label: "2着ながし", axisPositions: [1], multi: false, desc: "軸を2着に固定" },
    { key: "pos3", label: "3着ながし", axisPositions: [2], multi: false, desc: "軸を3着に固定" },
    { key: "multi", label: "軸1頭マルチ", multi: true, desc: "軸の全着順を網羅（相手の組合せ×6通り）" },
  ];
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
