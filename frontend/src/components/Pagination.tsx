"use client";

type Props = {
  page: number;
  totalPages: number;
  onPageChange: (page: number) => void;
};

export default function Pagination({ page, totalPages, onPageChange }: Props) {
  if (totalPages <= 1) return null;

  // Show at most 5 page numbers around the current page
  const start = Math.max(1, page - 2);
  const end = Math.min(totalPages, start + 4);
  const adjustedStart = Math.max(1, end - 4);

  const pages: number[] = [];
  for (let i = adjustedStart; i <= end; i++) {
    pages.push(i);
  }

  const btnBase =
    "inline-flex items-center justify-center rounded-md px-3 py-2 text-sm font-medium";

  return (
    <nav className="flex items-center justify-center gap-1" aria-label="ページ送り">
      <button
        onClick={() => onPageChange(page - 1)}
        disabled={page <= 1}
        className={btnBase}
        style={{
          backgroundColor: page <= 1 ? "transparent" : "var(--bg-elevated)",
          color: page <= 1 ? "var(--text-muted)" : "var(--text-secondary)",
          opacity: page <= 1 ? 0.4 : 1,
          cursor: page <= 1 ? "not-allowed" : "pointer",
          transition: "background-color 200ms ease-out, color 200ms ease-out",
        }}
        onMouseEnter={(e) => {
          if (page > 1) {
            e.currentTarget.style.backgroundColor = "var(--bg-card-hover)";
            e.currentTarget.style.color = "var(--text-primary)";
          }
        }}
        onMouseLeave={(e) => {
          if (page > 1) {
            e.currentTarget.style.backgroundColor = "var(--bg-elevated)";
            e.currentTarget.style.color = "var(--text-secondary)";
          }
        }}
      >
        前へ
      </button>

      {pages.map((p) => (
        <button
          key={p}
          onClick={() => onPageChange(p)}
          className={`${btnBase} cursor-pointer`}
          style={{
            backgroundColor:
              p === page ? "var(--accent)" : "var(--bg-elevated)",
            color: p === page ? "#fff" : "var(--text-secondary)",
            transition:
              "background-color 200ms ease-out, color 200ms ease-out",
          }}
          onMouseEnter={(e) => {
            if (p !== page) {
              e.currentTarget.style.backgroundColor = "var(--bg-card-hover)";
              e.currentTarget.style.color = "var(--text-primary)";
            }
          }}
          onMouseLeave={(e) => {
            if (p !== page) {
              e.currentTarget.style.backgroundColor = "var(--bg-elevated)";
              e.currentTarget.style.color = "var(--text-secondary)";
            }
          }}
        >
          {p}
        </button>
      ))}

      <button
        onClick={() => onPageChange(page + 1)}
        disabled={page >= totalPages}
        className={btnBase}
        style={{
          backgroundColor:
            page >= totalPages ? "transparent" : "var(--bg-elevated)",
          color:
            page >= totalPages ? "var(--text-muted)" : "var(--text-secondary)",
          opacity: page >= totalPages ? 0.4 : 1,
          cursor: page >= totalPages ? "not-allowed" : "pointer",
          transition: "background-color 200ms ease-out, color 200ms ease-out",
        }}
        onMouseEnter={(e) => {
          if (page < totalPages) {
            e.currentTarget.style.backgroundColor = "var(--bg-card-hover)";
            e.currentTarget.style.color = "var(--text-primary)";
          }
        }}
        onMouseLeave={(e) => {
          if (page < totalPages) {
            e.currentTarget.style.backgroundColor = "var(--bg-elevated)";
            e.currentTarget.style.color = "var(--text-secondary)";
          }
        }}
      >
        次へ
      </button>
    </nav>
  );
}
