/**
 * Semi-circular gauge for risk scores. Used in case detail.
 *
 * Simple SVG arc — no external charting lib needed.
 */

interface RiskGaugeProps {
  label: string;
  value: number; // 0 to 1
  size?: number;
}

function scoreColor(v: number): string {
  if (v < 0.45) return "#22c55e";
  if (v < 0.65) return "#eab308";
  if (v < 0.80) return "#f97316";
  return "#ef4444";
}

export default function RiskGauge({ label, value, size = 120 }: RiskGaugeProps) {
  const radius = size * 0.38;
  const cx = size / 2;
  const cy = size * 0.55;
  const angle = Math.PI * value; // 0..PI for a semicircle
  const x = cx + radius * Math.cos(Math.PI - angle);
  const y = cy - radius * Math.sin(Math.PI - angle);

  // Arc path from left (0) to the value point
  const largeArc = value > 0.5 ? 1 : 0;
  const startX = cx - radius;
  const startY = cy;

  return (
    <div className="flex flex-col items-center">
      <svg width={size} height={size * 0.65} viewBox={`0 0 ${size} ${size * 0.65}`}>
        {/* Background arc */}
        <path
          d={`M ${startX} ${cy} A ${radius} ${radius} 0 1 1 ${cx + radius} ${cy}`}
          fill="none"
          stroke="#e5e7eb"
          strokeWidth={8}
          strokeLinecap="round"
        />
        {/* Value arc */}
        {value > 0.01 && (
          <path
            d={`M ${startX} ${startY} A ${radius} ${radius} 0 ${largeArc} 1 ${x} ${y}`}
            fill="none"
            stroke={scoreColor(value)}
            strokeWidth={8}
            strokeLinecap="round"
          />
        )}
        {/* Score text */}
        <text
          x={cx}
          y={cy - 4}
          textAnchor="middle"
          className="text-lg font-bold"
          fill={scoreColor(value)}
        >
          {(value * 100).toFixed(0)}
        </text>
      </svg>
      <span className="text-xs text-gray-500 -mt-1">{label}</span>
    </div>
  );
}
