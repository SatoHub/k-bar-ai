export default function Footer() {
  return (
    <footer className="border-t" style={{ borderColor: "var(--border)", backgroundColor: "var(--bg-surface)" }}>
      <div className="mx-auto max-w-[1760px] px-4 py-4 sm:px-6 lg:px-8">
        <p className="text-center text-xs" style={{ color: "var(--text-muted)" }}>
          K-Bar AI &mdash; 競馬AI予想アプリ
        </p>
      </div>
    </footer>
  );
}
