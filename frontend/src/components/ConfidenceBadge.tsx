type Props = {
  confidence: string | null;
};

const LABEL_MAP: Record<string, string> = {
  high: "高",
  medium: "中",
  low: "低",
};

export default function ConfidenceBadge({ confidence }: Props) {
  if (!confidence) {
    return (
      <span
        className="inline-block rounded-full px-2.5 py-0.5 text-xs font-medium"
        style={{ color: "var(--text-muted)" }}
      >
        &mdash;
      </span>
    );
  }

  const label = LABEL_MAP[confidence] ?? confidence;

  let bg: string;
  let color: string;

  switch (confidence) {
    case "high":
      bg = "rgba(63,185,80,0.15)";
      color = "var(--green)";
      break;
    case "medium":
      bg = "rgba(210,153,34,0.15)";
      color = "var(--yellow)";
      break;
    default:
      bg = "var(--bg-elevated)";
      color = "var(--text-muted)";
      break;
  }

  return (
    <span
      className="inline-block rounded-full px-2.5 py-0.5 text-xs font-medium"
      style={{ backgroundColor: bg, color }}
    >
      {label}
    </span>
  );
}
