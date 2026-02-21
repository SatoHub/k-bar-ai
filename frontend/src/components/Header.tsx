"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const NAV_ITEMS = [
  { href: "/", label: "ダッシュボード" },
  { href: "/races", label: "レース一覧" },
  { href: "/bets", label: "収支" },
  { href: "/results", label: "AI成績" },
  { href: "/models", label: "モデル管理" },
] as const;

export default function Header() {
  const pathname = usePathname();

  return (
    <header className="sticky top-0 z-50 border-b" style={{ backgroundColor: "var(--bg-surface)", borderColor: "var(--border)" }}>
      <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
        <div className="flex h-14 items-center justify-between">
          <Link href="/" className="flex items-center gap-2 text-lg font-bold tracking-tight" style={{ color: "var(--text-primary)" }}>
            <span className="flex h-7 w-7 items-center justify-center rounded-lg text-xs font-black text-white" style={{ backgroundColor: "var(--accent)" }}>
              K
            </span>
            <span>K-Bar AI</span>
          </Link>

          <nav className="flex gap-1">
            {NAV_ITEMS.map(({ href, label }) => {
              const active =
                href === "/"
                  ? pathname === "/"
                  : pathname.startsWith(href);
              return (
                <Link
                  key={href}
                  href={href}
                  className="rounded-lg px-3 py-1.5 text-sm font-medium transition-colors duration-200"
                  style={{
                    backgroundColor: active ? "var(--accent-muted)" : "transparent",
                    color: active ? "var(--accent-hover)" : "var(--text-secondary)",
                  }}
                  onMouseEnter={(e) => {
                    if (!active) {
                      e.currentTarget.style.backgroundColor = "var(--bg-elevated)";
                      e.currentTarget.style.color = "var(--text-primary)";
                    }
                  }}
                  onMouseLeave={(e) => {
                    if (!active) {
                      e.currentTarget.style.backgroundColor = "transparent";
                      e.currentTarget.style.color = "var(--text-secondary)";
                    }
                  }}
                >
                  {label}
                </Link>
              );
            })}
          </nav>
        </div>
      </div>
    </header>
  );
}
