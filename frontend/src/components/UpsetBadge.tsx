"use client";

type Props = {
  score: number | null | undefined; // 0.0 - 1.0
};

export default function UpsetBadge({ score }: Props) {
  if (score === null || score === undefined) return null;

  let label: string;
  let bg: string;
  let fg: string;

  if (score >= 0.7) {
    label = "荒";
    bg = "rgba(239,68,68,0.15)";
    fg = "var(--red)";
  } else if (score >= 0.4) {
    label = "普通";
    bg = "rgba(234,179,8,0.15)";
    fg = "#ca8a04";
  } else {
    label = "本命";
    bg = "rgba(34,197,94,0.15)";
    fg = "var(--green)";
  }

  return (
    <span
      className="inline-flex items-center rounded-full px-2 py-0.5 text-xs font-semibold"
      style={{ backgroundColor: bg, color: fg }}
      title={`荒れ度: ${(score * 100).toFixed(0)}%`}
    >
      {label}
    </span>
  );
}
