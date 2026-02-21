"use client";

import { useEffect, useState, useCallback, useRef } from "react";
import {
  fetchSchedulerStatus,
  triggerSchedulerJob,
  pauseScheduler,
  resumeScheduler,
  type SchedulerStatus as SchedulerStatusType,
} from "@/lib/api";

const STATUS_COLORS: Record<string, string> = {
  success: "var(--green)",
  error: "var(--red)",
  skipped: "var(--text-muted)",
};

type ToastType = "success" | "error" | "warning";

type Toast = {
  id: number;
  type: ToastType;
  message: string;
};

const TOAST_STYLES: Record<ToastType, { bg: string; border: string; text: string }> = {
  success: {
    bg: "rgba(34,197,94,0.12)",
    border: "rgba(34,197,94,0.3)",
    text: "var(--green)",
  },
  error: {
    bg: "rgba(239,68,68,0.12)",
    border: "rgba(239,68,68,0.3)",
    text: "var(--red)",
  },
  warning: {
    bg: "rgba(234,179,8,0.12)",
    border: "rgba(234,179,8,0.3)",
    text: "var(--yellow)",
  },
};

function formatTime(iso: string | null): string {
  if (!iso) return "—";
  try {
    const d = new Date(iso);
    return d.toLocaleTimeString("ja-JP", {
      hour: "2-digit",
      minute: "2-digit",
      month: "short",
      day: "numeric",
    });
  } catch {
    return iso;
  }
}

export default function SchedulerStatus() {
  const [status, setStatus] = useState<SchedulerStatusType | null>(null);
  const [loading, setLoading] = useState(true);
  const [triggering, setTriggering] = useState<string | null>(null);
  const [toasts, setToasts] = useState<Toast[]>([]);
  const toastIdRef = useRef(0);

  const addToast = useCallback((type: ToastType, message: string) => {
    const id = ++toastIdRef.current;
    setToasts((prev) => [...prev, { id, type, message }]);
    setTimeout(() => {
      setToasts((prev) => prev.filter((t) => t.id !== id));
    }, 3000);
  }, []);

  const load = useCallback(() => {
    return fetchSchedulerStatus()
      .then((data) => {
        setStatus(data);
        return data;
      })
      .catch(() => {
        setStatus(null);
        return null;
      })
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    load();
    const interval = setInterval(load, 30_000);
    return () => clearInterval(interval);
  }, [load]);

  const handleTrigger = async (jobId: string) => {
    setTriggering(jobId);

    // 現在の last_run を記録
    const jobBefore = status?.jobs.find((j) => j.id === jobId);
    const lastRunBefore = jobBefore?.last_run ?? null;

    try {
      await triggerSchedulerJob(jobId);
    } catch (err) {
      const message =
        err instanceof Error ? err.message : "ジョブの実行に失敗しました";
      addToast("error", message);
      setTriggering(null);
      return;
    }

    // ポーリング: 3秒間隔 × 最大40回（2分）で last_run の変化を検知
    const MAX_POLLS = 40;
    const POLL_INTERVAL = 3000;
    let found = false;
    let notifiedRunning = false;
    for (let i = 0; i < MAX_POLLS; i++) {
      await new Promise((r) => setTimeout(r, POLL_INTERVAL));
      const freshStatus = await load();
      if (!freshStatus) continue;

      const jobAfter = freshStatus.jobs.find((j) => j.id === jobId);
      if (jobAfter && jobAfter.last_run !== lastRunBefore) {
        found = true;
        if (jobAfter.last_status === "success") {
          const detail = jobAfter.last_detail ? ` — ${jobAfter.last_detail}` : "";
          addToast("success", `${jobAfter.name} 完了${detail}`);
        } else if (jobAfter.last_status === "error") {
          const detail = jobAfter.last_detail || "不明なエラー";
          addToast("error", `${jobAfter.name} 失敗: ${detail}`);
        } else {
          addToast("success", `${jobAfter.name} 完了`);
        }
        break;
      }

      // 15秒経過で中間フィードバック
      if (!notifiedRunning && i * POLL_INTERVAL >= 15000) {
        notifiedRunning = true;
        addToast("warning", "処理中...完了まで少々お待ちください");
      }
    }

    if (!found) {
      addToast("warning", "ジョブがまだ実行中です。ステータスは自動更新されます");
    }

    setTriggering(null);
  };

  const handleTogglePause = async () => {
    try {
      if (status?.paused) {
        await resumeScheduler();
      } else {
        await pauseScheduler();
      }
      load();
    } catch {
      // ignore
    }
  };

  if (loading) {
    return (
      <div className="glass-card p-4">
        <div
          className="text-sm"
          style={{ color: "var(--text-muted)" }}
        >
          スケジューラー読み込み中...
        </div>
      </div>
    );
  }

  if (!status) {
    return (
      <div className="glass-card p-4">
        <div className="text-sm" style={{ color: "var(--text-muted)" }}>
          スケジューラー情報を取得できません
        </div>
      </div>
    );
  }

  return (
    <div className="glass-card p-5">
      {/* Toast notifications */}
      {toasts.length > 0 && (
        <div className="flex flex-col gap-1.5 mb-3">
          {toasts.map((toast) => {
            const style = TOAST_STYLES[toast.type];
            return (
              <div
                key={toast.id}
                className="text-xs px-3 py-2 rounded-md border"
                style={{
                  backgroundColor: style.bg,
                  borderColor: style.border,
                  color: style.text,
                }}
              >
                {toast.type === "success" && "✓ "}
                {toast.type === "error" && "✗ "}
                {toast.type === "warning" && "⏳ "}
                {toast.message}
              </div>
            );
          })}
        </div>
      )}

      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <div
            className="h-2.5 w-2.5 rounded-full"
            style={{
              backgroundColor: status.running
                ? status.paused
                  ? "var(--yellow)"
                  : "var(--green)"
                : "var(--red)",
            }}
          />
          <h3
            className="text-sm font-semibold"
            style={{ color: "var(--text-primary)" }}
          >
            自動データ取得
          </h3>
          <span
            className="text-xs px-1.5 py-0.5 rounded"
            style={{
              backgroundColor: "var(--bg-elevated)",
              color: "var(--text-secondary)",
            }}
          >
            {status.running
              ? status.paused
                ? "一時停止中"
                : "稼働中"
              : "停止"}
          </span>
        </div>
        {status.running && (
          <button
            type="button"
            onClick={handleTogglePause}
            className="text-xs px-2.5 py-1 rounded transition-colors cursor-pointer"
            style={{
              backgroundColor: "var(--bg-elevated)",
              color: "var(--text-secondary)",
            }}
          >
            {status.paused ? "再開" : "一時停止"}
          </button>
        )}
      </div>

      <div className="space-y-2">
        {status.jobs.map((job) => (
          <div
            key={job.id}
            className="flex items-center justify-between py-1.5 px-2 rounded"
            style={{ backgroundColor: "var(--bg-elevated)" }}
          >
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2">
                <span
                  className="text-xs font-medium truncate"
                  style={{ color: "var(--text-primary)" }}
                >
                  {job.name}
                </span>
                {job.last_status && (
                  <span
                    className="text-[10px] px-1 py-0.5 rounded"
                    style={{
                      color: STATUS_COLORS[job.last_status] || "var(--text-muted)",
                    }}
                  >
                    {job.last_status === "success"
                      ? "OK"
                      : job.last_status === "error"
                        ? "ERR"
                        : job.last_status}
                  </span>
                )}
              </div>
              <div
                className="text-[10px] mt-0.5"
                style={{ color: "var(--text-muted)" }}
              >
                {job.next_run
                  ? `次回: ${formatTime(job.next_run)}`
                  : "未スケジュール"}
                {job.last_detail && (
                  <span className="ml-2">{job.last_detail}</span>
                )}
              </div>
            </div>
            <button
              type="button"
              onClick={() => handleTrigger(job.id)}
              disabled={triggering !== null}
              className="text-[10px] px-2 py-1 rounded transition-colors cursor-pointer shrink-0 ml-2"
              style={{
                backgroundColor: "var(--accent-muted)",
                color: "var(--accent)",
                opacity: triggering !== null ? 0.5 : 1,
              }}
            >
              {triggering === job.id ? "実行中..." : "実行"}
            </button>
          </div>
        ))}
      </div>
    </div>
  );
}
