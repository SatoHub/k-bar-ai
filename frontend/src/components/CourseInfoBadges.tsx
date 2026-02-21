"use client";

type Props = {
  surface: string | null;
  trackCondition: string | null;
  weather: string | null;
  distanceM: number | null;
  direction: string | null;
};

function weatherIcon(weather: string): string {
  if (weather.includes("晴")) return "☀";
  if (weather.includes("曇")) return "☁";
  if (weather.includes("雨")) return "🌧";
  if (weather.includes("雪")) return "❄";
  return "–";
}

function conditionColor(condition: string): string {
  switch (condition) {
    case "良":
      return "var(--green)";
    case "稍重":
      return "var(--accent)";
    case "重":
      return "var(--cta)";
    case "不良":
      return "var(--red)";
    default:
      return "var(--text-secondary)";
  }
}

export default function CourseInfoBadges({
  surface,
  trackCondition,
  weather,
  distanceM,
  direction,
}: Props) {
  return (
    <div className="flex flex-wrap items-center gap-2">
      {/* Surface badge */}
      {surface && (
        <span
          className="inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-semibold"
          style={{
            backgroundColor:
              surface === "芝"
                ? "rgba(34,197,94,0.15)"
                : "rgba(180,120,60,0.15)",
            color: surface === "芝" ? "var(--green)" : "#b4783c",
          }}
        >
          {surface}
        </span>
      )}

      {/* Distance + direction */}
      {distanceM && (
        <span
          className="inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium"
          style={{
            backgroundColor: "var(--bg-elevated)",
            color: "var(--text-primary)",
          }}
        >
          {distanceM}m{direction ? ` (${direction})` : ""}
        </span>
      )}

      {/* Track condition */}
      {trackCondition && (
        <span
          className="inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-semibold"
          style={{
            backgroundColor: `color-mix(in srgb, ${conditionColor(trackCondition)} 15%, transparent)`,
            color: conditionColor(trackCondition),
          }}
        >
          馬場: {trackCondition}
        </span>
      )}

      {/* Weather */}
      {weather && (
        <span
          className="inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-xs font-medium"
          style={{
            backgroundColor: "var(--bg-elevated)",
            color: "var(--text-secondary)",
          }}
        >
          {weatherIcon(weather)} {weather}
        </span>
      )}
    </div>
  );
}
