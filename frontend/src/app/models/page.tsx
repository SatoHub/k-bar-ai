"use client";

import { useEffect, useState, useCallback } from "react";
import {
  fetchModels,
  fetchModelMetrics,
  type ModelVersion,
  type ModelMetrics,
} from "@/lib/api";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function fmtPct(v: number | null): string {
  if (v == null) return "-";
  return `${(v * 100).toFixed(1)}%`;
}

function fmtNum(v: number | null): string {
  if (v == null) return "-";
  return v.toLocaleString("ja-JP");
}

function fmtDate(iso: string): string {
  return new Date(iso).toLocaleDateString("ja-JP", {
    year: "numeric",
    month: "long",
    day: "numeric",
  });
}

// ---------------------------------------------------------------------------
// Metric display definition
// ---------------------------------------------------------------------------

type MetricDef = {
  label: string;
  render: (m: ModelMetrics) => string;
};

const METRIC_DEFS: MetricDef[] = [
  { label: "正解率", render: (m) => fmtPct(m.accuracy) },
  { label: "F1スコア", render: (m) => fmtPct(m.f1) },
  { label: "ROC-AUC", render: (m) => fmtPct(m.roc_auc) },
  { label: "学習データ行数", render: (m) => fmtNum(m.train_rows) },
  { label: "テストデータ行数", render: (m) => fmtNum(m.test_rows) },
  { label: "ベストイテレーション", render: (m) => fmtNum(m.best_iteration) },
  { label: "カットオフ年", render: (m) => (m.cutoff_year != null ? String(m.cutoff_year) : "-") },
  { label: "単勝的中率", render: (m) => fmtPct(m.win_hit_rate) },
  { label: "複勝的中率", render: (m) => fmtPct(m.place_hit_rate) },
  { label: "検証レース数", render: (m) => fmtNum(m.unique_races) },
];

// ---------------------------------------------------------------------------
// Expandable model card
// ---------------------------------------------------------------------------

function ModelCard({ model }: { model: ModelVersion }) {
  const [open, setOpen] = useState(false);
  const [metrics, setMetrics] = useState<ModelMetrics | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const toggle = useCallback(() => {
    setOpen((prev) => {
      const next = !prev;
      if (next && !metrics && !loading) {
        setLoading(true);
        setError(null);
        fetchModelMetrics(model.version)
          .then(setMetrics)
          .catch((e: Error) => setError(e.message))
          .finally(() => setLoading(false));
      }
      return next;
    });
  }, [metrics, loading, model.version]);

  const accuracyPct = model.accuracy != null ? `${(model.accuracy * 100).toFixed(1)}%` : null;

  return (
    <div className="glass-card-interactive overflow-hidden">
      {/* Header -- always visible */}
      <button
        type="button"
        onClick={toggle}
        className="flex w-full items-center justify-between gap-4 p-6 text-left cursor-pointer"
      >
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-3">
            <h3
              className="text-lg font-bold"
              style={{ color: "var(--text-primary)" }}
            >
              {model.version}
            </h3>
            {accuracyPct && (
              <span
                className="rounded-full px-2.5 py-0.5 text-xs font-medium"
                style={{
                  backgroundColor: "var(--accent-muted)",
                  color: "var(--accent)",
                }}
              >
                正解率 {accuracyPct}
              </span>
            )}
          </div>
          {model.description && (
            <p
              className="mt-1 text-sm"
              style={{ color: "var(--text-secondary)" }}
            >
              {model.description}
            </p>
          )}
          <p
            className="mt-1 text-xs"
            style={{ color: "var(--text-muted)" }}
          >
            {fmtDate(model.created_at)}
          </p>
        </div>

        <svg
          className="h-5 w-5 shrink-0"
          style={{
            color: "var(--text-muted)",
            transition: "transform 0.2s ease-out",
            transform: open ? "rotate(180deg)" : "rotate(0deg)",
          }}
          fill="none"
          viewBox="0 0 24 24"
          strokeWidth={2}
          stroke="currentColor"
        >
          <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
        </svg>
      </button>

      {/* Expanded metrics */}
      {open && (
        <div
          className="px-6 pb-6 pt-4"
          style={{
            borderTop: "1px solid var(--border)",
            backgroundColor: "var(--bg-surface)",
          }}
        >
          {loading && (
            <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 animate-pulse">
              {Array.from({ length: 10 }).map((_, i) => (
                <div key={i} className="space-y-2">
                  <div
                    className="h-3 w-20 rounded"
                    style={{ backgroundColor: "var(--bg-elevated)" }}
                  />
                  <div
                    className="h-5 w-16 rounded"
                    style={{ backgroundColor: "var(--bg-elevated)" }}
                  />
                </div>
              ))}
            </div>
          )}

          {error && (
            <p className="text-sm" style={{ color: "var(--red)" }}>
              メトリクスの取得に失敗しました: {error}
            </p>
          )}

          {metrics && (
            <div className="grid grid-cols-2 gap-4 sm:grid-cols-3">
              {METRIC_DEFS.map(({ label, render }) => (
                <div key={label}>
                  <p
                    className="text-xs"
                    style={{ color: "var(--text-secondary)" }}
                  >
                    {label}
                  </p>
                  <p
                    className="text-lg font-bold"
                    style={{ color: "var(--text-primary)" }}
                  >
                    {render(metrics)}
                  </p>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------

export default function ModelsPage() {
  const [models, setModels] = useState<ModelVersion[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchModels()
      .then((res) => setModels(res.items))
      .catch((e: Error) => setError(e.message));
  }, []);

  return (
    <>
      <h1
        className="mb-6 text-2xl font-bold"
        style={{ color: "var(--text-primary)" }}
      >
        モデル管理
      </h1>

      {error && (
        <div className="glass-card p-6">
          <p className="text-sm" style={{ color: "var(--red)" }}>
            データの取得に失敗しました: {error}
          </p>
        </div>
      )}

      {!models && !error && (
        <div className="space-y-4">
          {Array.from({ length: 3 }).map((_, i) => (
            <div key={i} className="glass-card p-6 animate-pulse">
              <div className="space-y-3">
                <div
                  className="h-5 w-40 rounded"
                  style={{ backgroundColor: "var(--bg-elevated)" }}
                />
                <div
                  className="h-3 w-64 rounded"
                  style={{ backgroundColor: "var(--bg-elevated)" }}
                />
                <div
                  className="h-3 w-28 rounded"
                  style={{ backgroundColor: "var(--bg-elevated)" }}
                />
              </div>
            </div>
          ))}
        </div>
      )}

      {models && models.length === 0 && (
        <div className="glass-card p-6 text-center">
          <p style={{ color: "var(--text-secondary)" }}>
            モデルが登録されていません
          </p>
        </div>
      )}

      {models && models.length > 0 && (
        <div className="space-y-4">
          {models.map((m) => (
            <ModelCard key={m.id} model={m} />
          ))}
        </div>
      )}
    </>
  );
}
