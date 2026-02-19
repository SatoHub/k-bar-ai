"use client";

import { useState } from "react";

type Props = {
  explanation: string | null;
};

export default function ExplanationCard({ explanation }: Props) {
  const [open, setOpen] = useState(false);

  if (!explanation) return null;

  return (
    <div className="mt-1">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="rounded-full px-2.5 py-0.5 text-xs font-medium cursor-pointer"
        style={{
          backgroundColor: "var(--accent-muted)",
          color: "var(--accent)",
          transition: "background-color 200ms ease-out, color 200ms ease-out",
        }}
        onMouseEnter={(e) => {
          e.currentTarget.style.backgroundColor = "var(--accent-glow)";
          e.currentTarget.style.color = "var(--accent-hover)";
        }}
        onMouseLeave={(e) => {
          e.currentTarget.style.backgroundColor = "var(--accent-muted)";
          e.currentTarget.style.color = "var(--accent)";
        }}
      >
        {open ? "閉じる" : "説明を見る"}
      </button>
      {open && (
        <div
          className="mt-1 rounded-md p-3 text-xs leading-relaxed whitespace-pre-wrap"
          style={{
            backgroundColor: "var(--bg-elevated)",
            border: "1px solid var(--border)",
            color: "var(--text-secondary)",
          }}
        >
          {explanation}
        </div>
      )}
    </div>
  );
}
