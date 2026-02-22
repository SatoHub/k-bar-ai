import Link from "next/link";
import AiHitRateCard from "@/components/AiHitRateCard";
import BetSummaryCard from "@/components/BetSummaryCard";
import DataStatusCard from "@/components/DataStatusCard";
import ModelMetricsCard from "@/components/ModelMetricsCard";
import SchedulerStatus from "@/components/SchedulerStatus";

// Step icons as SVG components
function IconDatabase() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.5} className="h-8 w-8">
      <ellipse cx="12" cy="6" rx="8" ry="3" />
      <path d="M4 6v6c0 1.657 3.582 3 8 3s8-1.343 8-3V6" />
      <path d="M4 12v6c0 1.657 3.582 3 8 3s8-1.343 8-3v-6" />
    </svg>
  );
}

function IconSearch() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.5} className="h-8 w-8">
      <circle cx="11" cy="11" r="7" />
      <path strokeLinecap="round" d="m20 20-3.5-3.5" />
      <path strokeLinecap="round" d="M11 8v6M8 11h6" />
    </svg>
  );
}

function IconSparkles() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.5} className="h-8 w-8">
      <path strokeLinecap="round" strokeLinejoin="round" d="M9.813 15.904 9 18.75l-.813-2.846a4.5 4.5 0 0 0-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 0 0 3.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 0 0 3.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 0 0-3.09 3.09Z" />
      <path strokeLinecap="round" strokeLinejoin="round" d="M18.259 8.715 18 9.75l-.259-1.035a3.375 3.375 0 0 0-2.455-2.456L14.25 6l1.036-.259a3.375 3.375 0 0 0 2.455-2.456L18 2.25l.259 1.035a3.375 3.375 0 0 0 2.455 2.456L21.75 6l-1.036.259a3.375 3.375 0 0 0-2.455 2.456Z" />
    </svg>
  );
}

function IconChart() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.5} className="h-8 w-8">
      <path strokeLinecap="round" strokeLinejoin="round" d="M3 3v18h18" />
      <path strokeLinecap="round" strokeLinejoin="round" d="M7 16V12M11 16V8M15 16v-2M19 16V6" />
    </svg>
  );
}

const STEP_ICONS = [IconDatabase, IconSearch, IconSparkles, IconChart];

type Step = {
  number: string;
  title: string;
  description: string;
  href?: string;
};

const STEPS: Step[] = [
  {
    number: "1",
    title: "データを確認",
    description: "下のカードで取り込み済みのレース数やモデル性能を確認できます。",
  },
  {
    number: "2",
    title: "レースを探す",
    href: "/races",
    description:
      "レース一覧から日付や競馬場で絞り込み、気になるレースを選びます。",
  },
  {
    number: "3",
    title: "AI予測を見る",
    description:
      "レース詳細ページでAIの予測順位・スコア・信頼度と、判断根拠（SHAP説明）を確認できます。",
  },
  {
    number: "4",
    title: "モデルを比較",
    href: "/models",
    description:
      "モデル管理ページで各バージョンの正解率やF1スコアなどの性能指標を比較できます。",
  },
];

export default function DashboardPage() {
  return (
    <div className="space-y-8">
      <h1
        className="text-3xl font-bold tracking-tight"
        style={{ color: "var(--text-primary)" }}
      >
        ダッシュボード
      </h1>

      {/* How to use guide */}
      <div
        className="glass-card p-6"
        style={{ borderLeft: "3px solid var(--accent)" }}
      >
        <div className="flex items-center gap-3 mb-5">
          <div
            className="flex h-8 w-8 items-center justify-center rounded-lg"
            style={{
              backgroundColor: "var(--accent-muted)",
              color: "var(--accent)",
            }}
          >
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.5} className="h-5 w-5">
              <path strokeLinecap="round" strokeLinejoin="round" d="m11.25 11.25.041-.02a.75.75 0 0 1 1.063.852l-.708 2.836a.75.75 0 0 0 1.063.853l.041-.021M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0Zm-9-3.75h.008v.008H12V8.25Z" />
            </svg>
          </div>
          <h2
            className="text-base font-semibold"
            style={{ color: "var(--text-primary)" }}
          >
            K-Bar AI の使い方
          </h2>
        </div>
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {STEPS.map((step, idx) => {
            const Icon = STEP_ICONS[idx];
            const inner = (
              <div className="flex flex-col items-center text-center">
                <div
                  className="flex h-14 w-14 items-center justify-center rounded-full"
                  style={{
                    backgroundColor: "var(--accent-muted)",
                    color: "var(--accent)",
                  }}
                >
                  <Icon />
                </div>
                <span
                  className="mt-2 inline-flex h-5 w-5 items-center justify-center rounded-full text-[10px] font-bold"
                  style={{
                    backgroundColor: "var(--accent)",
                    color: "#ffffff",
                  }}
                >
                  {step.number}
                </span>
                <p
                  className="mt-2 text-sm font-semibold"
                  style={{ color: "var(--text-primary)" }}
                >
                  {step.title}
                </p>
                <p
                  className="mt-1 text-xs leading-relaxed"
                  style={{ color: "var(--text-secondary)" }}
                >
                  {step.description}
                </p>
                {step.href && (
                  <span
                    className="mt-2 text-xs font-medium"
                    style={{ color: "var(--accent)" }}
                  >
                    ページを開く &rarr;
                  </span>
                )}
              </div>
            );

            return step.href ? (
              <Link
                key={step.number}
                href={step.href}
                className="glass-card-interactive p-4"
              >
                {inner}
              </Link>
            ) : (
              <div
                key={step.number}
                className="glass-card p-4"
              >
                {inner}
              </div>
            );
          })}
        </div>
      </div>

      {/* AI hit rate summary */}
      <AiHitRateCard />

      {/* Scheduler status */}
      <SchedulerStatus />

      {/* Bet summary */}
      <BetSummaryCard />

      {/* Data & Model overview */}
      <div className="grid gap-6 md:grid-cols-2">
        <DataStatusCard />
        <ModelMetricsCard />
      </div>

      <div className="glass-card p-6 flex items-center justify-between">
        <p
          className="text-sm"
          style={{ color: "var(--text-secondary)" }}
        >
          レースデータを確認して予測を始めましょう
        </p>
        <Link
          href="/races"
          className="btn-accent inline-flex items-center gap-2 rounded-lg px-5 py-2.5 text-sm font-medium transition-colors duration-200 cursor-pointer"
        >
          レース一覧を見る
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} className="h-4 w-4">
            <path strokeLinecap="round" strokeLinejoin="round" d="M13.5 4.5 21 12m0 0-7.5 7.5M21 12H3" />
          </svg>
        </Link>
      </div>
    </div>
  );
}
