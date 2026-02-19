"use client";

import { useEffect, useState } from "react";
import { fetchModels, type ModelVersion } from "@/lib/api";

export default function ModelMetricsCard() {
  const [model, setModel] = useState<ModelVersion | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchModels()
      .then((res) => {
        if (res.items.length > 0) {
          setModel(res.items[0]);
        }
      })
      .catch((e: Error) => setError(e.message));
  }, []);

  if (error) {
    return (
      <div className="glass-card p-6">
        <h2
          className="mb-4 text-lg font-semibold"
          style={{ color: "var(--text-primary)" }}
        >
          モデル性能
        </h2>
        <p className="text-sm" style={{ color: "var(--red)" }}>
          データの取得に失敗しました: {error}
        </p>
      </div>
    );
  }

  if (!model) {
    return (
      <div className="glass-card p-6 animate-pulse">
        <h2
          className="mb-4 text-lg font-semibold"
          style={{ color: "var(--text-primary)" }}
        >
          モデル性能
        </h2>
        <div className="space-y-4">
          <div
            className="h-4 w-32 rounded"
            style={{ backgroundColor: "var(--bg-elevated)" }}
          />
          <div
            className="h-8 w-24 rounded"
            style={{ backgroundColor: "var(--bg-elevated)" }}
          />
          <div
            className="h-3 w-28 rounded"
            style={{ backgroundColor: "var(--bg-elevated)" }}
          />
        </div>
      </div>
    );
  }

  const accuracyPct =
    model.accuracy != null ? (model.accuracy * 100).toFixed(1) : null;

  const createdDate = new Date(model.created_at).toLocaleDateString("ja-JP", {
    year: "numeric",
    month: "long",
    day: "numeric",
  });

  return (
    <div className="glass-card p-6">
      <div className="mb-5 flex items-center justify-between">
        <h2
          className="text-lg font-semibold"
          style={{ color: "var(--text-primary)" }}
        >
          モデル性能
        </h2>
        <span
          className="rounded-full px-3 py-1 text-xs font-semibold"
          style={{
            backgroundColor: "var(--accent-muted)",
            color: "var(--accent)",
            border: "1px solid var(--border-accent)",
          }}
        >
          {model.version}
        </span>
      </div>

      {accuracyPct != null && (
        <div className="mb-5 flex items-baseline gap-1">
          <span
            className="text-5xl font-bold tracking-tight"
            style={{ color: "var(--text-primary)" }}
          >
            {accuracyPct}
          </span>
          <span
            className="text-2xl font-semibold"
            style={{ color: "var(--text-secondary)" }}
          >
            %
          </span>
          <span
            className="ml-2 text-xs font-medium"
            style={{ color: "var(--text-muted)" }}
          >
            精度
          </span>
        </div>
      )}

      {model.description && (
        <div
          className="mb-4 pb-4"
          style={{ borderBottom: "1px solid var(--border)" }}
        >
          <p
            className="text-xs font-medium"
            style={{ color: "var(--text-secondary)" }}
          >
            説明
          </p>
          <p
            className="mt-1 text-sm"
            style={{ color: "var(--text-secondary)" }}
          >
            {model.description}
          </p>
        </div>
      )}

      <div className="flex items-center gap-2">
        <svg
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth={1.5}
          className="h-4 w-4"
          style={{ color: "var(--text-muted)" }}
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            d="M6.75 3v2.25M17.25 3v2.25M3 18.75V7.5a2.25 2.25 0 0 1 2.25-2.25h13.5A2.25 2.25 0 0 1 21 7.5v11.25m-18 0A2.25 2.25 0 0 0 5.25 21h13.5A2.25 2.25 0 0 0 21 18.75m-18 0v-7.5A2.25 2.25 0 0 1 5.25 9h13.5A2.25 2.25 0 0 1 21 11.25v7.5"
          />
        </svg>
        <p className="text-sm" style={{ color: "var(--text-muted)" }}>
          {createdDate}
        </p>
      </div>
    </div>
  );
}
