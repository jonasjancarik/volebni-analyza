import { fmtInt, fmtNum, fmtPct, fmtPp } from "../format";
import { useTooltip, useWidth } from "../hooks";

export interface ScatterPoint {
  id: string;
  label: string;
  previous: number;
  current: number;
  size: number;
}

interface Props {
  points: ScatterPoint[];
  previousYear: string;
  currentYear: string;
  selected: string | null;
  onSelect: (id: string) => void;
}

function ticks(max: number): number[] {
  const step = [1, 2, 5, 10, 20, 25].find((candidate) => max / candidate <= 6) ?? 50;
  return Array.from({ length: Math.floor(max / step) + 1 }, (_, i) => i * step);
}

/** Each precinct by its value last time (across) and now (up); above the diagonal means a gain. */
export function Scatter({ points, previousYear, currentYear, selected, onSelect }: Props) {
  const [ref, width] = useWidth<HTMLDivElement>(560);
  const tooltip = useTooltip();
  const height = Math.min(460, Math.max(300, width * 0.72));
  const margin = { top: 12, right: 16, bottom: 40, left: 44 };
  const max = Math.max(...points.map((point) => Math.max(point.previous, point.current)), 1) * 1.06;
  const largest = Math.max(...points.map((point) => point.size), 1);
  const innerWidth = width - margin.left - margin.right;
  const innerHeight = height - margin.top - margin.bottom;
  const x = (value: number) => margin.left + (value / max) * innerWidth;
  const y = (value: number) => margin.top + innerHeight - (value / max) * innerHeight;
  const radius = (size: number) => 2.5 + Math.sqrt(size / largest) * 5;
  const marks = ticks(max);
  // Small precincts on top, so that large ones do not hide them
  const ordered = [...points].sort((a, b) => b.size - a.size);

  return (
    <div ref={ref}>
      <svg className="chart" width={width} height={height} role="img" aria-label={`Okrsky podle výsledku v letech ${previousYear} a ${currentYear}`}>
        {marks.map((mark) => (
          <g key={mark}>
            <line className="grid-line" x1={x(mark)} x2={x(mark)} y1={margin.top} y2={margin.top + innerHeight} />
            <line className="grid-line" x1={margin.left} x2={margin.left + innerWidth} y1={y(mark)} y2={y(mark)} />
            <text x={x(mark)} y={margin.top + innerHeight + 16} textAnchor="middle">
              {fmtNum(mark, 0)}
            </text>
            <text x={margin.left - 8} y={y(mark)} dy="0.35em" textAnchor="end">
              {fmtNum(mark, 0)}
            </text>
          </g>
        ))}
        <line className="axis-line" x1={x(0)} y1={y(0)} x2={x(max)} y2={y(max)} />
        <text x={x(max) - 6} y={y(max) + 16} textAnchor="end">
          beze změny
        </text>
        <text x={margin.left + innerWidth} y={height - 4} textAnchor="end">
          {previousYear} (%)
        </text>
        <text x={margin.left} y={margin.top + 2} dx={6} dy="0.35em">
          {currentYear} (%)
        </text>
        {ordered.map((point) => (
          <circle
            key={point.id}
            cx={x(point.previous)}
            cy={y(point.current)}
            r={radius(point.size) + (point.id === selected ? 2 : 0)}
            fill="var(--series-1)"
            fillOpacity={point.id === selected ? 1 : 0.55}
            stroke={point.id === selected ? "var(--ink)" : "var(--surface)"}
            strokeWidth={point.id === selected ? 2 : 1}
            style={{ cursor: "pointer" }}
            onClick={() => onSelect(point.id)}
            onMouseMove={(event) =>
              tooltip.show(
                event,
                <>
                  <div className="t-title">{point.label}</div>
                  <div>
                    {fmtPct(point.previous)} → {fmtPct(point.current)} ({fmtPp(point.current - point.previous)})
                  </div>
                  <div className="t-sub">{fmtInt(point.size)} zapsaných voličů</div>
                </>,
              )
            }
            onMouseLeave={tooltip.hide}
          />
        ))}
      </svg>
      {tooltip.element}
    </div>
  );
}
