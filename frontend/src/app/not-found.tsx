export default function NotFound() {
  return (
    <div className="flex flex-col items-center justify-center py-20">
      <h1
        className="text-4xl font-bold"
        style={{ color: "var(--text-primary)" }}
      >
        404
      </h1>
      <p className="mt-2 text-sm" style={{ color: "var(--text-muted)" }}>
        ページが見つかりません
      </p>
    </div>
  );
}
