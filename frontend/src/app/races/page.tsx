"use client";

import { useEffect, useState, useCallback, Suspense } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import {
  fetchRaces,
  fetchDataStatus,
  type RaceListItem,
} from "@/lib/api";
import RaceFilters from "@/components/RaceFilters";
import RaceTable from "@/components/RaceTable";
import Pagination from "@/components/Pagination";

function RacesContent() {
  const router = useRouter();
  const searchParams = useSearchParams();

  const paramDate = searchParams.get("date") ?? "";
  const paramRacecourse = searchParams.get("racecourse") ?? "";
  const paramPage = Number(searchParams.get("page") ?? "1");

  const [items, setItems] = useState<RaceListItem[]>([]);
  const [totalPages, setTotalPages] = useState(1);
  const [page, setPage] = useState(paramPage);
  const [racecourses, setRacecourses] = useState<string[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Fetch racecourse list once
  useEffect(() => {
    fetchDataStatus()
      .then((ds) => setRacecourses(ds.racecourses))
      .catch(() => {});
  }, []);

  // Fetch races whenever URL params change
  const loadRaces = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const perPage = 20;
      const res = await fetchRaces({
        date: paramDate || undefined,
        racecourse: paramRacecourse || undefined,
        page: paramPage,
        per_page: perPage,
      });
      setItems(res.items);
      setTotalPages(Math.max(1, Math.ceil(res.total / perPage)));
      setPage(res.page);
    } catch (e) {
      setError(e instanceof Error ? e.message : "データの取得に失敗しました");
    } finally {
      setLoading(false);
    }
  }, [paramDate, paramRacecourse, paramPage]);

  useEffect(() => {
    loadRaces();
  }, [loadRaces]);

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

  function handleFilter(filters: { date?: string; racecourse?: string }) {
    updateParams({ date: filters.date, racecourse: filters.racecourse, page: undefined });
  }

  function handlePageChange(newPage: number) {
    updateParams({ page: String(newPage) });
  }

  return (
    <>
      <RaceFilters
        racecourses={racecourses}
        initialDate={paramDate}
        initialRacecourse={paramRacecourse}
        onFilter={handleFilter}
      />

      <div className="mt-6">
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
            <RaceTable items={items} />
            <div className="mt-4">
              <Pagination
                page={page}
                totalPages={totalPages}
                onPageChange={handlePageChange}
              />
            </div>
          </>
        )}
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
        {/* Filter guide */}
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
            上部の<b style={{ color: "var(--text-primary)" }}>「日付」</b>と
            <b style={{ color: "var(--text-primary)" }}>「競馬場」</b>
            で表示するレースを絞り込めます。
            特定の開催日だけ見たい場合は日付を選択し、「検索」を押してください。
            「クリア」で条件をリセットできます。
          </p>
        </div>

        {/* Table columns guide */}
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
            <li><b style={{ color: "var(--text-primary)" }}>日付</b> — レース開催日</li>
            <li><b style={{ color: "var(--text-primary)" }}>競馬場</b> — 開催場名（東京、中山、阪神 など）</li>
            <li><b style={{ color: "var(--text-primary)" }}>R</b> — 第何レースか（1R〜12R）</li>
            <li><b style={{ color: "var(--text-primary)" }}>レース名</b> — クリックすると詳細ページへ移動し、<b style={{ color: "var(--text-primary)" }}>AI予測と出走結果</b>が確認できます</li>
            <li><b style={{ color: "var(--text-primary)" }}>コース</b> — 「芝1600m」＝芝コース1600m、「ダ1200m」＝ダートコース1200m</li>
            <li><b style={{ color: "var(--text-primary)" }}>天候</b> — 当日の天気（晴、曇、雨 など）</li>
            <li><b style={{ color: "var(--text-primary)" }}>馬場状態</b> — 馬場のコンディション。<b style={{ color: "var(--text-primary)" }}>良</b>が最も乾いた状態、<b style={{ color: "var(--text-primary)" }}>稍重→重→不良</b>の順に水分を含みます</li>
            <li><b style={{ color: "var(--text-primary)" }}>グレード</b> — 重賞レースの格付け（GI・GII・GIII など）。空欄は一般レースです</li>
          </ul>
        </div>

        {/* Tips */}
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
            <li>まずは<b style={{ color: "var(--text-primary)" }}>グレード列にGI・GIIなどが入っている重賞レース</b>を選ぶと、AI予測の精度を実感しやすいです</li>
            <li>気になるレース名をクリックすると、<b style={{ color: "var(--text-primary)" }}>AIの予測順位・信頼度・判断根拠</b>と<b style={{ color: "var(--text-primary)" }}>実際の着順</b>を並べて確認できます</li>
            <li>馬場状態が「重」「不良」のレースは波乱が起きやすく、AI予測がどう対応しているか比べてみるのも面白いです</li>
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
