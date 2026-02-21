"use client";

type Props = {
  score: number; // 0-3
};

export default function AptitudeIndicator({ score }: Props) {
  if (score === 0) {
    return (
      <span className="text-xs" style={{ color: "var(--text-muted)" }}>
        -
      </span>
    );
  }

  return (
    <span
      className="text-xs"
      style={{
        color:
          score >= 3
            ? "var(--cta)"
            : score >= 2
              ? "var(--accent)"
              : "var(--text-secondary)",
      }}
      title={`コース適性: ${score}/3`}
    >
      {"★".repeat(score)}
      {"☆".repeat(3 - score)}
    </span>
  );
}
