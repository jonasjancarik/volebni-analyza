import { useId } from "react";
import { fmtInt, fmtNum, fmtPct } from "../format";
import { useTooltip, useWidth } from "../hooks";
import type { StepProps } from "./Step";

interface Props extends StepProps {
  precinct: number;
  onPick: (precinct: number) => void;
}

export function ticks(low: number, high: number, wanted = 6): number[] {
  const span = high - low;
  const step = [0.5, 1, 2, 5, 10, 20, 25].find((candidate) => span / candidate <= wanted) ?? 50;
  const first = Math.ceil(low / step) * step;
  return Array.from({ length: Math.floor((high - first) / step) + 1 }, (_, i) => first + i * step);
}

/** The straight line that fits the precincts best, larger precincts counting more. */
export function fitLine(xs: number[], ys: number[], weights: number[]) {
  const total = weights.reduce((sum, weight) => sum + weight, 0);
  const meanX = xs.reduce((sum, value, i) => sum + value * weights[i], 0) / total;
  const meanY = ys.reduce((sum, value, i) => sum + value * weights[i], 0) / total;
  let covariance = 0;
  let variance = 0;
  xs.forEach((value, i) => {
    covariance += weights[i] * (value - meanX) * (ys[i] - meanY);
    variance += weights[i] * (value - meanX) ** 2;
  });
  const slope = variance > 0 ? covariance / variance : 0;
  return { slope, intercept: meanY - slope * meanX };
}

/** Every precinct by the followed group's strength last time (across) and the followed list's now (up). */
export function PrecinctCloud(props: Props) {
  const { inputs, source, target, previousYear, currentYear, words, precinct, onPick } = props;
  const [ref, width] = useWidth<HTMLDivElement>(640);
  const tooltip = useTooltip();
  const clip = useId();

  const sourceName = inputs.sources[source];
  const targetName = inputs.targets[target];
  const xs = inputs.precincts.map((item) => item.previous[source]);
  const ys = inputs.precincts.map((item) => item.current[target]);
  const sizes = inputs.precincts.map((item) => item.registered);
  const line = fitLine(xs, ys, sizes);

  const height = Math.min(430, Math.max(300, width * 0.62));
  const margin = { top: 26, right: 16, bottom: 46, left: 46 };
  const maxX = Math.max(...xs, 1) * 1.06;
  const maxY = Math.max(...ys, 1) * 1.08;
  const largest = Math.max(...sizes, 1);
  const innerWidth = width - margin.left - margin.right;
  const innerHeight = height - margin.top - margin.bottom;
  const x = (value: number) => margin.left + (value / maxX) * innerWidth;
  const y = (value: number) => margin.top + innerHeight - (value / maxY) * innerHeight;
  const radius = (size: number) => 2.2 + Math.sqrt(size / largest) * 4.5;
  const color = words.mark(targetName);
  const order = inputs.precincts.map((_, index) => index).sort((a, b) => sizes[b] - sizes[a]);

  // Read literally, the line says how the followed group and everyone else voted
  const fromGroup = line.intercept + line.slope * 100;
  const per100 = Math.round(line.slope * 100);
  const impossible = fromGroup > 100 || fromGroup < 0 || line.intercept < 0;

  return (
    <>
      <div ref={ref}>
        <svg
          className="chart"
          width={width}
          height={height}
          role="img"
          aria-label={`Okrsky podle podílu skupiny ${words.short(sourceName)} v roce ${previousYear} a skupiny ${words.short(targetName)} v roce ${currentYear}`}
        >
          <defs>
            <clipPath id={clip}>
              <rect x={margin.left} y={margin.top} width={innerWidth} height={innerHeight} />
            </clipPath>
          </defs>
          {ticks(0, maxX).map((mark) => (
            <g key={`x${mark}`}>
              <line className="grid-line" x1={x(mark)} x2={x(mark)} y1={margin.top} y2={margin.top + innerHeight} />
              <text x={x(mark)} y={margin.top + innerHeight + 16} textAnchor="middle">
                {fmtNum(mark, 0)}
              </text>
            </g>
          ))}
          {ticks(0, maxY).map((mark) => (
            <g key={`y${mark}`}>
              <line className="grid-line" x1={margin.left} x2={margin.left + innerWidth} y1={y(mark)} y2={y(mark)} />
              <text x={margin.left - 8} y={y(mark)} dy="0.35em" textAnchor="end">
                {fmtNum(mark, 0)}
              </text>
            </g>
          ))}
          <text x={margin.left + innerWidth} y={height - 6} textAnchor="end">
            {words.short(sourceName)} {previousYear}, % zapsaných voličů →
          </text>
          <text x={margin.left - 34} y={12}>
            ↑ {words.short(targetName)} {currentYear}, % zapsaných voličů
          </text>
          {order.map((index) => {
            const item = inputs.precincts[index];
            const picked = index === precinct;
            return (
              <circle
                key={item.id}
                cx={x(xs[index])}
                cy={y(ys[index])}
                r={radius(sizes[index]) + (picked ? 2 : 0)}
                fill={color}
                fillOpacity={picked ? 1 : 0.5}
                stroke={picked ? "var(--ink)" : "var(--surface)"}
                strokeWidth={picked ? 2 : 0.75}
                style={{ cursor: "pointer" }}
                onClick={() => onPick(index)}
                onMouseMove={(event) =>
                  tooltip.show(
                    event,
                    <>
                      <div className="t-title">Okrsek {item.id}</div>
                      <div>
                        {words.short(sourceName)} {previousYear}: {fmtPct(xs[index])}
                      </div>
                      <div>
                        {words.short(targetName)} {currentYear}: {fmtPct(ys[index])}
                      </div>
                      <div className="t-sub">{fmtInt(item.registered)} zapsaných voličů</div>
                    </>,
                  )
                }
                onMouseLeave={tooltip.hide}
              />
            );
          })}
          <line
            clipPath={`url(#${clip})`}
            x1={x(0)}
            y1={y(line.intercept)}
            x2={x(maxX)}
            y2={y(line.intercept + line.slope * maxX)}
            stroke="var(--ink)"
            strokeWidth={2}
            strokeLinecap="round"
          />
        </svg>
        {tooltip.element}
      </div>
      <div className="method-after">
        <p className="method-result num">
          Kde je o 100 víc lidí, kteří {words.votedPlural(sourceName, previousYear)}, tam je v průměru o{" "}
          <strong>
            {fmtInt(Math.abs(per100))} {per100 < 0 ? "méně" : "víc"}
          </strong>{" "}
          těch, kteří {words.votedPlural(targetName, currentYear)}.
        </p>
        <p className="note">
          {impossible
            ? `Doslova se ale přímka brát nedá: vyšlo by z ní, že takto se zachovalo ${fmtPct(fromGroup, 0)} lidí z této skupiny a ${fmtPct(line.intercept, 0)} všech ostatních, což je nesmysl. `
            : `Doslova vzato by to znamenalo, že takto se zachovalo ${fmtPct(fromGroup, 0)} lidí z této skupiny a ${fmtPct(line.intercept, 0)} všech ostatních. `}
          Jedna přímka totiž háže všechny ostatní do jednoho pytle, přestože se voliči různých kandidátek chovají různě a
          bývají silní ve stejných okrscích. Proto je potřeba počítat všechny skupiny najednou. Vybraný okrsek z prvního
          kroku je zvýrazněný; kliknutím na jiný bod ho vyměníte.
        </p>
      </div>
    </>
  );
}
