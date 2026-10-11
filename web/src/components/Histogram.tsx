import { fmtInt, fmtNum, fmtPct, plural } from "../format";
import { useTooltip, useWidth } from "../hooks";

interface Props {
  values: number[];
  /** Value for the whole council, drawn as a line */
  overall: number;
  unit?: string;
}

function binStep(span: number): number {
  for (const step of [1, 2, 2.5, 5, 10]) if (span / step <= 16) return step;
  return 20;
}

/** How many precincts fall into each band of turnout. */
export function Histogram({ values, overall }: Props) {
  const [ref, width] = useWidth<HTMLDivElement>(420);
  const tooltip = useTooltip();
  const height = 190;
  const margin = { top: 22, right: 8, bottom: 24, left: 8 };

  const min = Math.min(...values);
  const max = Math.max(...values);
  const step = binStep(max - min || 1);
  const start = Math.floor(min / step) * step;
  const count = Math.max(1, Math.ceil((max - start) / step + 1e-9));
  const bins = Array.from({ length: count }, (_, i) => ({ from: start + i * step, size: 0 }));
  for (const value of values) bins[Math.min(count - 1, Math.floor((value - start) / step))].size += 1;

  const end = start + count * step;
  const tallest = Math.max(...bins.map((bin) => bin.size));
  const innerWidth = width - margin.left - margin.right;
  const innerHeight = height - margin.top - margin.bottom;
  const x = (value: number) => margin.left + ((value - start) / (end - start)) * innerWidth;
  const barWidth = innerWidth / count;
  const overallX = x(Math.min(Math.max(overall, start), end));
  const labelEvery = Math.ceil(count / Math.max(2, Math.floor(innerWidth / 48)));

  return (
    <div ref={ref}>
      <svg className="chart" width={width} height={height} role="img" aria-label="Rozložení účasti v okrscích">
        {bins.map((bin, i) => {
          const barHeight = (bin.size / tallest) * innerHeight;
          return (
            <g key={bin.from}>
              {bin.size > 0 && (
                <path
                  d={roundedTop(x(bin.from) + 1, margin.top + innerHeight - barHeight, Math.max(barWidth - 2, 1), barHeight)}
                  fill="var(--series-1)"
                />
              )}
              <rect
                x={x(bin.from)}
                y={margin.top}
                width={barWidth}
                height={innerHeight}
                fill="transparent"
                onMouseMove={(event) =>
                  tooltip.show(
                    event,
                    <>
                      <div className="t-title">
                        Účast {fmtNum(bin.from, step % 1 ? 1 : 0)}–{fmtPct(bin.from + step, step % 1 ? 1 : 0)}
                      </div>
                      <div className="t-sub">
                        {fmtInt(bin.size)} {plural(bin.size, "okrsek", "okrsky", "okrsků")}
                      </div>
                    </>,
                  )
                }
                onMouseLeave={tooltip.hide}
              />
              {i % labelEvery === 0 && (
                <text x={x(bin.from)} y={height - 6} textAnchor="middle">
                  {fmtNum(bin.from, 0)}
                </text>
              )}
            </g>
          );
        })}
        <line className="axis-line" x1={margin.left} x2={width - margin.right} y1={margin.top + innerHeight} y2={margin.top + innerHeight} />
        <line x1={overallX} x2={overallX} y1={margin.top - 6} y2={margin.top + innerHeight} stroke="var(--ink)" strokeWidth={1.5} />
        <text
          className="label-strong"
          x={overallX + (overallX > width * 0.7 ? -6 : 6)}
          y={margin.top - 8}
          textAnchor={overallX > width * 0.7 ? "end" : "start"}
        >
          celkem {fmtPct(overall)}
        </text>
        <text x={width - margin.right} y={height - 6} textAnchor="end">
          %
        </text>
      </svg>
      {tooltip.element}
    </div>
  );
}

/** A column with a rounded top and a square foot on the baseline */
function roundedTop(x: number, y: number, width: number, height: number): string {
  const r = Math.min(3, width / 2, height);
  return `M${x},${y + height}V${y + r}Q${x},${y} ${x + r},${y}H${x + width - r}Q${x + width},${y} ${x + width},${y + r}V${y + height}Z`;
}
