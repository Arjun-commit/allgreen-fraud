// Activity density bar over time. Red zones = suspicious pauses.
// Placeholder — in prod, render actual event density from raw events.

interface SessionTimelineProps {
  durationMs: number;
  // TODO: accept actual event density data
}

export default function SessionTimeline({ durationMs }: SessionTimelineProps) {
  // Generate some visual blocks based on duration
  const totalSecs = Math.max(1, Math.floor(durationMs / 1000));
  const blocks = Math.min(totalSecs, 60); // max 60 blocks

  // Fake density — in prod this would come from real event data
  const densities = Array.from({ length: blocks }, (_, i) => {
    // Create a pattern: some normal activity, some pauses
    const phase = i / blocks;
    if (phase > 0.3 && phase < 0.45) return 0.1; // suspicious pause
    if (phase > 0.7 && phase < 0.8) return 0.15; // another pause
    return 0.4 + Math.random() * 0.5; // normal activity
  });

  return (
    <div>
      <div className="flex gap-px h-6 rounded overflow-hidden">
        {densities.map((d, i) => (
          <div
            key={i}
            className="flex-1"
            style={{
              backgroundColor: d < 0.2
                ? `rgba(239, 68, 68, ${0.3 + (1 - d) * 0.5})`  // red for pauses
                : `rgba(34, 197, 94, ${0.2 + d * 0.6})`,        // green for activity
            }}
          />
        ))}
      </div>
      <div className="flex justify-between mt-1 text-xs text-gray-400">
        <span>0s</span>
        <span>{(durationMs / 1000).toFixed(0)}s</span>
      </div>
    </div>
  );
}
