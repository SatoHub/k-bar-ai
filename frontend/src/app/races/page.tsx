"use client";

import { useEffect, useState, useCallback, useMemo, Suspense } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import {
  fetchRaces,
  fetchDataStatus,
  scrapeShutuba,
  scrapeOdds,
  scrapeResults,
  runPredict,
  scrapeCalendar,
  scrapeAll,
  fetchScrapeStatus,
  type RaceListItem,
  type ScrapeResponse,
} from "@/lib/api";
import { decodeRacecourse } from "@/lib/racecourse";
import RaceCalendar from "@/components/RaceCalendar";
import RaceTable from "@/components/RaceTable";
import Pagination from "@/components/Pagination";

function RacesContent() {
  const router = useRouter();
  const searchParams = useSearchParams();

  const paramDate = searchParams.get("date") ?? "";
  const paramYearMonth = searchParams.get("year_month") ?? "";
  const paramWeek = searchParams.get("week") ?? "";
  const paramRacecourse = searchParams.get("racecourse") ?? "";
  const paramPage = Number(searchParams.get("page") ?? "1");

  const [items, setItems] = useState<RaceListItem[]>([]);
  const [totalPages, setTotalPages] = useState(1);
  const [page, setPage] = useState(paramPage);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [dataMaxMonth, setDataMaxMonth] = useState<string>("");
  const [runningTasks, setRunningTasks] = useState<Record<string, boolean>>({});
  const [taskMsg, setTaskMsg] = useState<string | null>(null);

  // Client-side racecourse tab filter (independent of URL params)
  const [selectedCourse, setSelectedCourse] = useState<string | null>(null);

  // Derive current year-month for calendar (from filter or default to latest data)
  const defaultYearMonth = (() => {
    const now = new Date();
    return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}`;
  })();

  const calendarYearMonth =
    paramYearMonth ||
    (paramDate ? paramDate.substring(0, 7) : "") ||
    dataMaxMonth ||
    defaultYearMonth;

  // Redirect to today's date on initial visit (no URL params)
  const hasParams = searchParams.toString().length > 0;
  useEffect(() => {
    if (!hasParams) {
      const today = new Date();
      const yyyy = today.getFullYear();
      const mm = String(today.getMonth() + 1).padStart(2, "0");
      const dd = String(today.getDate()).padStart(2, "0");
      router.replace(`/races?date=${yyyy}-${mm}-${dd}`);
    }
  }, [hasParams, router]);

  // Fetch data range once (for calendar default month)
  useEffect(() => {
    fetchDataStatus()
      .then((ds) => {
        // Default calendar to the latest month with data
        if (ds.date_max) {
          setDataMaxMonth(ds.date_max.substring(0, 7));
        }
      })
      .catch(() => {});
  }, []);

  // Fetch races whenever URL params change
  const loadRaces = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      // When filtering by date, show all races (up to 50 per day max)
      const perPage = paramDate ? 50 : 20;
      const params = {
        date: paramDate || undefined,
        year_month: !paramDate ? paramYearMonth || undefined : undefined,
        week:
          !paramDate && paramYearMonth && paramWeek ? paramWeek : undefined,
        racecourse: paramRacecourse || undefined,
        page: paramPage,
        per_page: perPage,
      };
      const res = await fetchRaces(params);
      setItems(res.items);
      setTotalPages(Math.max(1, Math.ceil(res.total / perPage)));
      setPage(res.page);
    } catch (e) {
      setError(e instanceof Error ? e.message : "データの取得に失敗しました");
    } finally {
      setLoading(false);
    }
  }, [paramDate, paramYearMonth, paramWeek, paramRacecourse, paramPage]);

  useEffect(() => {
    loadRaces();
  }, [loadRaces]);

  // Reset course tab when filters change
  useEffect(() => {
    setSelectedCourse(null);
  }, [paramDate, paramYearMonth, paramWeek, paramRacecourse]);

  // Resolve racecourse name for each item (from DB or decoded from race_id)
  function getCourseName(item: RaceListItem): string | null {
    return item.racecourse_name ?? decodeRacecourse(item.race_id);
  }

  // Extract unique racecourse names for tabs
  const availableCourses = useMemo(() => {
    const courses = Array.from(
      new Set(
        items
          .map(getCourseName)
          .filter((n): n is string => n !== null && n !== ""),
      ),
    );
    return courses;
  }, [items]);

  // Client-side filtered items
  const filteredItems = useMemo(() => {
    if (!selectedCourse) return items;
    return items.filter((item) => getCourseName(item) === selectedCourse);
  }, [items, selectedCourse]);

  function updateParams(updates: Record<string, string | undefined>) {
    const sp = new URLSearchParams(searchParams.toString());
    for (const [key, value] of Object.entries(updates)) {
      if (value) {
        sp.set(key, value);
      } else {
        sp.delete(key);
      }
    }
    router.push(`/races?${sp.toString()}`);
  }

  function handleCalendarDayClick(dateStr: string) {
    updateParams({
      date: dateStr,
      year_month: undefined,
      week: undefined,
      page: undefined,
    });
  }

  function handlePageChange(newPage: number) {
    updateParams({ page: String(newPage) });
  }

  const anyRunning = Object.values(runningTasks).some(Boolean);

  async function runTask(
    taskKey: string,
    statusKey: "shutuba" | "odds" | "results" | "predict" | "calendar" | "all",
    apiFn: () => Promise<ScrapeResponse>,
  ) {
    setRunningTasks((prev) => ({ ...prev, [taskKey]: true }));
    setTaskMsg(null);
    try {
      const res = await apiFn();
      setTaskMsg(res.message);
      if (res.success) {
        const poll = setInterval(async () => {
          try {
            const st = await fetchScrapeStatus(statusKey, paramDate || undefined);
            if (!st.running) {
              clearInterval(poll);
              setRunningTasks((prev) => ({ ...prev, [taskKey]: false }));
              setTaskMsg(`${taskKey} が完了しました。`);
              loadRaces();
            }
          } catch {
            clearInterval(poll);
            setRunningTasks((prev) => ({ ...prev, [taskKey]: false }));
          }
        }, 5000);
      } else {
        setRunningTasks((prev) => ({ ...prev, [taskKey]: false }));
      }
    } catch (e) {
      setTaskMsg(e instanceof Error ? e.message : "実行に失敗しました");
      setRunningTasks((prev) => ({ ...prev, [taskKey]: false }));
    }
  }

  // Count races per course for tab badges
  function courseCount(course: string): number {
    return items.filter((item) => getCourseName(item) === course).length;
  }

  return (
    <>
      <div className="grid gap-6 lg:grid-cols-[1fr_280px]">
        <div className="min-w-0 space-y-6">
          {/* Data operation buttons */}
          <div
            className="glass-card p-4"
          >
            <div className="mb-2 text-xs font-semibold" style={{ color: "var(--text-muted)" }}>
              データ取得・実行
            </div>
            <div className="flex flex-wrap gap-2">
              {([
                { key: "出馬表", statusKey: "shutuba" as const, fn: () => scrapeShutuba(paramDate || undefined) },
                { key: "オッズ", statusKey: "odds" as const, fn: () => scrapeOdds(paramDate || undefined) },
                { key: "レース結果", statusKey: "results" as const, fn: () => scrapeResults(paramDate || undefined) },
                { key: "AI予想", statusKey: "predict" as const, fn: () => runPredict(paramDate || undefined) },
                { key: "カレンダー", statusKey: "calendar" as const, fn: () => scrapeCalendar() },
              ]).map((t) => (
                <button
                  key={t.key}
                  type="button"
                  onClick={() => runTask(t.key, t.statusKey, t.fn)}
                  disabled={anyRunning}
                  className="cursor-pointer rounded-lg px-3 py-1.5 text-sm font-medium transition-all duration-200 disabled:opacity-50 disabled:cursor-not-allowed"
                  style={{
                    backgroundColor: runningTasks[t.key] ? "var(--bg-elevated)" : "rgba(59,130,246,0.1)",
                    color: runningTasks[t.key] ? "var(--text-secondary)" : "var(--accent)",
                    border: "1px solid var(--border)",
                  }}
                >
                  {runningTasks[t.key] ? (
                    <span className="flex items-center gap-1.5">
                      <svg className="h-3.5 w-3.5 animate-spin" viewBox="0 0 24 24" fill="none">
                        <circle cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="3" strokeDasharray="31.4 31.4" />
                      </svg>
                      {t.key}...
                    </span>
                  ) : (
                    t.key
                  )}
                </button>
              ))}
              <button
                type="button"
                onClick={() => runTask("一括実行", "all", () => scrapeAll(paramDate || undefined))}
                disabled={anyRunning}
                className="cursor-pointer rounded-lg px-3 py-1.5 text-sm font-semibold transition-all duration-200 disabled:opacity-50 disabled:cursor-not-allowed"
                style={{
                  backgroundColor: runningTasks["一括実行"] ? "var(--bg-elevated)" : "var(--accent)",
                  color: runningTasks["一括実行"] ? "var(--text-secondary)" : "#fff",
                  border: "1px solid transparent",
                }}
              >
                {runningTasks["一括実行"] ? (
                  <span className="flex items-center gap-1.5">
                    <svg className="h-3.5 w-3.5 animate-spin" viewBox="0 0 24 24" fill="none">
                      <circle cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="3" strokeDasharray="31.4 31.4" />
                    </svg>
                    実行中...
                  </span>
                ) : (
                  "一括実行"
                )}
              </button>
            </div>
            {taskMsg && (
              <p className="mt-2 text-sm" style={{ color: "var(--text-secondary)" }}>
                {taskMsg}
              </p>
            )}
          </div>

          {/* Calendar — mobile: above table, desktop: sidebar */}
          <div className="lg:hidden">
            <RaceCalendar
              yearMonth={calendarYearMonth}
              onDayClick={handleCalendarDayClick}
              selectedDate={paramDate}
            />
          </div>

          {/* Racecourse tabs — only when viewing a specific date */}
          {paramDate && availableCourses.length > 1 && (
            <div
              className="flex flex-wrap gap-1.5 rounded-xl p-2"
              style={{
                backgroundColor: "var(--bg-elevated)",
                border: "1px solid var(--border)",
              }}
            >
              <button
                type="button"
                onClick={() => setSelectedCourse(null)}
                className="cursor-pointer rounded-lg px-4 py-2 text-sm font-medium transition-all duration-200"
                style={{
                  backgroundColor: selectedCourse === null
                    ? "var(--accent)"
                    : "transparent",
                  color: selectedCourse === null ? "#fff" : "var(--text-secondary)",
                  boxShadow: selectedCourse === null
                    ? "0 2px 8px rgba(59,130,246,0.3)"
                    : "none",
                }}
                onMouseEnter={(e) => {
                  if (selectedCourse !== null) {
                    e.currentTarget.style.backgroundColor = "rgba(255,255,255,0.05)";
                    e.currentTarget.style.color = "var(--text-primary)";
                  }
                }}
                onMouseLeave={(e) => {
                  if (selectedCourse !== null) {
                    e.currentTarget.style.backgroundColor = "transparent";
                    e.currentTarget.style.color = "var(--text-secondary)";
                  }
                }}
              >
                すべて
                <span className="ml-1.5 rounded-full px-1.5 py-0.5 text-[10px] font-semibold"
                  style={{
                    backgroundColor: selectedCourse === null
                      ? "rgba(255,255,255,0.25)"
                      : "rgba(255,255,255,0.08)",
                  }}
                >
                  {items.length}
                </span>
              </button>
              {availableCourses.map((course) => (
                <button
                  key={course}
                  type="button"
                  onClick={() => setSelectedCourse(course)}
                  className="cursor-pointer rounded-lg px-4 py-2 text-sm font-medium transition-all duration-200"
                  style={{
                    backgroundColor: selectedCourse === course
                      ? "var(--accent)"
                      : "transparent",
                    color: selectedCourse === course
                      ? "#fff"
                      : "var(--text-secondary)",
                    boxShadow: selectedCourse === course
                      ? "0 2px 8px rgba(59,130,246,0.3)"
                      : "none",
                  }}
                  onMouseEnter={(e) => {
                    if (selectedCourse !== course) {
                      e.currentTarget.style.backgroundColor = "rgba(255,255,255,0.05)";
                      e.currentTarget.style.color = "var(--text-primary)";
                    }
                  }}
                  onMouseLeave={(e) => {
                    if (selectedCourse !== course) {
                      e.currentTarget.style.backgroundColor = "transparent";
                      e.currentTarget.style.color = "var(--text-secondary)";
                    }
                  }}
                >
                  {course}
                  <span className="ml-1.5 rounded-full px-1.5 py-0.5 text-[10px] font-semibold"
                    style={{
                      backgroundColor: selectedCourse === course
                        ? "rgba(255,255,255,0.25)"
                        : "rgba(255,255,255,0.08)",
                    }}
                  >
                    {courseCount(course)}
                  </span>
                </button>
              ))}
            </div>
          )}

          {loading ? (
            <div
              className="glass-card p-8 text-center"
              style={{ color: "var(--text-muted)" }}
            >
              読み込み中...
            </div>
          ) : error ? (
            <div
              className="glass-card p-8 text-center"
              style={{ color: "var(--red)" }}
            >
              {error}
            </div>
          ) : (
            <>
              <RaceTable items={filteredItems} />
              {!selectedCourse && (
                <Pagination
                  page={page}
                  totalPages={totalPages}
                  onPageChange={handlePageChange}
                />
              )}
            </>
          )}
        </div>

        {/* Calendar sidebar — desktop only */}
        <div className="hidden lg:block">
          <RaceCalendar
            yearMonth={calendarYearMonth}
            onDayClick={handleCalendarDayClick}
            selectedDate={paramDate}
          />
        </div>
      </div>
    </>
  );
}

function GuideSection() {
  return (
    <details
      className="group mb-6"
      style={{
        backgroundColor: "var(--bg-card)",
        border: "1px solid var(--border)",
        borderLeft: "3px solid var(--accent)",
        borderRadius: "12px",
      }}
    >
      <summary
        className="flex cursor-pointer items-center gap-2 px-5 py-3 text-sm font-semibold select-none"
        style={{ color: "var(--text-primary)" }}
      >
        <svg
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth={1.5}
          className="h-5 w-5 shrink-0"
          style={{ color: "var(--accent)" }}
        >
          <circle cx="12" cy="12" r="10" />
          <path strokeLinecap="round" d="M12 16v.01M12 12a2 2 0 1 0-2-2" />
        </svg>
        この画面の使い方（クリックで開閉）
      </summary>

      <div
        className="px-5 pb-5 pt-4 text-sm leading-relaxed"
        style={{
          borderTop: "1px solid var(--border)",
          color: "var(--text-secondary)",
        }}
      >
        <div className="mb-4">
          <p className="font-semibold" style={{ color: "var(--text-primary)" }}>
            <span
              className="mr-1.5 inline-flex h-5 w-5 items-center justify-center rounded-full text-[10px] font-bold"
              style={{ backgroundColor: "var(--accent)", color: "#fff" }}
            >
              1
            </span>
            フィルタで絞り込む
          </p>
          <p className="mt-1 ml-7">
            <b style={{ color: "var(--text-primary)" }}>「年月」</b>と
            <b style={{ color: "var(--text-primary)" }}>「週」</b>
            で月単位・週単位に絞り込めます。
            右側のカレンダーからレースのある日をクリックしても絞り込めます。
          </p>
        </div>

        <div className="mb-4">
          <p className="font-semibold" style={{ color: "var(--text-primary)" }}>
            <span
              className="mr-1.5 inline-flex h-5 w-5 items-center justify-center rounded-full text-[10px] font-bold"
              style={{ backgroundColor: "var(--accent)", color: "#fff" }}
            >
              2
            </span>
            テーブルの見方
          </p>
          <ul className="mt-2 ml-7 space-y-1.5">
            <li><b style={{ color: "var(--text-primary)" }}>レース名</b> — クリックすると詳細ページへ移動</li>
            <li><b style={{ color: "var(--text-primary)" }}>コース</b> — 「芝1600m」＝芝コース1600m</li>
            <li><b style={{ color: "var(--text-primary)" }}>グレード</b> — 重賞レースの格付け（GI・GII・GIII）</li>
          </ul>
        </div>

        <div>
          <p className="font-semibold" style={{ color: "var(--text-primary)" }}>
            <span
              className="mr-1.5 inline-flex h-5 w-5 items-center justify-center rounded-full text-[10px] font-bold"
              style={{ backgroundColor: "var(--accent)", color: "#fff" }}
            >
              3
            </span>
            おすすめの見方
          </p>
          <ul className="mt-2 ml-7 space-y-1.5">
            <li>重賞レースを選ぶと、AI予測の精度を実感しやすいです</li>
            <li>馬場状態が「重」「不良」のレースは波乱が起きやすいです</li>
          </ul>
        </div>
      </div>
    </details>
  );
}

export default function RacesPage() {
  return (
    <div>
      <h1
        className="mb-6 text-2xl font-bold"
        style={{ color: "var(--text-primary)" }}
      >
        レース一覧
      </h1>
      <GuideSection />
      <Suspense
        fallback={
          <div
            className="glass-card p-8 text-center"
            style={{ color: "var(--text-muted)" }}
          >
            読み込み中...
          </div>
        }
      >
        <RacesContent />
      </Suspense>
    </div>
  );
}
