"use client";

/**
 * 馬場情報（含水率・クッション値）表示。JRA公式の開催日スクレイピング由来。
 * GET /races/{id}/track-condition の detail がある時だけ表示する。
 */

import React from "react";
import type { TrackConditionResponse } from "@/lib/api";

function Metric({
  label,
  value,
  unit,
  emphasis = false,
}: {
  label: string;
  value: number | null;
  unit: string;
  emphasis?: boolean;
}) {
  return (
    <div className="flex flex-col">
      <span className="text-[11px]" style={{ color: "var(--text-muted)" }}>
        {label}
      </span>
      <span
        className={emphasis ? "text-lg font-bold tabular-nums" : "text-sm font-semibold tabular-nums"}
        style={{ color: value == null ? "var(--text-muted)" : "var(--text-primary)" }}
      >
        {value == null ? "—" : `${value}${unit}`}
      </span>
    </div>
  );
}

export default function TrackConditionInfo({
  data,
}: {
  data: TrackConditionResponse | null;
}) {
  const d = data?.detail;
  if (!d) return null;
  const hasTurf = d.turf_moisture_goal != null || d.turf_moisture_4c != null || d.cushion_value != null;
  const hasDirt = d.dirt_moisture_goal != null || d.dirt_moisture_4c != null;

  return (
    <div className="glass-card p-5">
      <div className="mb-3 flex items-center gap-2">
        <h2 className="text-base font-semibold" style={{ color: "var(--text-primary)" }}>
          馬場情報
        </h2>
        <span
          className="rounded px-1.5 py-0.5 text-[10px] font-medium"
          style={{ backgroundColor: "rgba(59,130,246,0.15)", color: "#60a5fa" }}
        >
          JRA公式
        </span>
      </div>

      <div className="flex flex-wrap gap-x-8 gap-y-3">
        {d.cushion_value != null && (
          <Metric label="クッション値（芝）" value={d.cushion_value} unit="" emphasis />
        )}
        {hasTurf && (
          <div className="flex flex-col gap-1">
            <span className="text-[11px] font-semibold" style={{ color: "var(--text-muted)" }}>
              芝 含水率
            </span>
            <div className="flex gap-4">
              <Metric label="ゴール前" value={d.turf_moisture_goal} unit="%" />
              <Metric label="4コーナー" value={d.turf_moisture_4c} unit="%" />
            </div>
          </div>
        )}
        {hasDirt && (
          <div className="flex flex-col gap-1">
            <span className="text-[11px] font-semibold" style={{ color: "var(--text-muted)" }}>
              ダート 含水率
            </span>
            <div className="flex gap-4">
              <Metric label="ゴール前" value={d.dirt_moisture_goal} unit="%" />
              <Metric label="4コーナー" value={d.dirt_moisture_4c} unit="%" />
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
