"use client";

import { useEffect, useState } from "react";
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

  const load = () => {
    fetchSchedulerStatus()
      .then(setStatus)
      .catch(() => setStatus(null))
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    load();
    const interval = setInterval(load, 30_000);
    return () => clearInterval(interval);
  }, []);

  const handleTrigger = async (jobId: string) => {
    setTriggering(jobId);
    try {
      await triggerSchedulerJob(jobId);
      setTimeout(load, 2000);
    } catch {
      // ignore
    } finally {
      setTriggering(null);
    }
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
              disabled={triggering === job.id}
              className="text-[10px] px-2 py-1 rounded transition-colors cursor-pointer shrink-0 ml-2"
              style={{
                backgroundColor: "var(--accent-muted)",
                color: "var(--accent)",
                opacity: triggering === job.id ? 0.5 : 1,
              }}
            >
              {triggering === job.id ? "..." : "実行"}
            </button>
          </div>
        ))}
      </div>
    </div>
  );
}
