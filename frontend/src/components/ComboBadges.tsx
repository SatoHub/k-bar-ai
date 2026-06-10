"use client";

/**
 * 馬券の買い目（組み合わせ）を、JRA公式の枠番カラー付き馬番バッジで表示する共通コンポーネント。
 * netkeiba/ネット馬券の見せ方に準拠。馬名はホバーのtitleツールチップに格納。
 */

import React from "react";
import type { RaceEntry } from "@/lib/api";

// JRA公式の枠番カラー（1白/2黒/3赤/4青/5黄/6緑/7橙/8桃）
export const WAKU_COLORS: Record<number, { bg: string; fg: string }> = {
  1: { bg: "#f3f4f6", fg: "#111827" },
  2: { bg: "#1f2937", fg: "#f9fafb" },
  3: { bg: "#e0353b", fg: "#ffffff" },
  4: { bg: "#2563eb", fg: "#ffffff" },
  5: { bg: "#f5c518", fg: "#1a1a1a" },
  6: { bg: "#1ea64a", fg: "#ffffff" },
  7: { bg: "#f08a24", fg: "#1a1a1a" },
  8: { bg: "#ec6f9e", fg: "#1a1a1a" },
};

export function wakuColor(
  bracket: number | null | undefined,
): { bg: string; fg: string } {
  if (bracket && WAKU_COLORS[bracket]) return WAKU_COLORS[bracket];
  return { bg: "rgba(255,255,255,0.08)", fg: "var(--text-primary)" };
}

export default function ComboBadges({
  combo,
  entries,
  isWaku,
  ordered,
  size = "sm",
}: {
  combo: string[];
  entries: RaceEntry[];
  isWaku: boolean;
  ordered: boolean;
  size?: "sm" | "md";
}) {
  const items = combo.map((id) => {
    if (isWaku) {
      const w = Number(id);
      return { num: w as number | null, bracket: w, name: `${w}枠` };
    }
    const e = entries.find((en) => en.horse.id === id);
    return {
      num: e?.post_position ?? null,
      bracket: e?.bracket_number ?? null,
      name: e?.horse.name ?? id,
    };
  });

  const badgeCls =
    size === "md"
      ? "h-6 min-w-[1.5rem] text-xs"
      : "h-5 min-w-[1.25rem] text-[11px]";

  return (
    <span className="inline-flex flex-wrap items-center gap-x-0.5 gap-y-1">
      {items.map((it, i) => {
        const c = wakuColor(it.bracket);
        return (
          <span key={i} className="inline-flex items-center">
            {i > 0 && (
              <span className="mx-0.5 text-[10px]" style={{ color: "var(--text-muted)" }}>
                {ordered ? "→" : ""}
              </span>
            )}
            <span
              title={`${it.num ?? "?"} ${it.name}`}
              className={`inline-flex items-center justify-center rounded px-1 font-bold tabular-nums ${badgeCls}`}
              style={{
                backgroundColor: c.bg,
                color: c.fg,
                border: "1px solid rgba(0,0,0,0.25)",
              }}
            >
              {isWaku ? `${it.num}枠` : (it.num ?? "?")}
            </span>
          </span>
        );
      })}
    </span>
  );
}
