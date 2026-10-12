import { useEffect, useRef, useState } from "react";
import { fmtInt, fmtNum, fmtPct, fmtRange } from "../format";
import { prefersReducedMotion, useSeen, useWidth } from "../hooks";
import { type Matrix, type Model, randomSource, resampledMatrix } from "./model";
import { ticks } from "./PrecinctCloud";
import type { StepProps } from "./Step";

interface Props extends StepProps {
  model: Model;
  /** The matrices of the full estimate, where every repeated fit starts */
  result: Matrix[];
}

const DRAWS = 100;

/**
 * The estimate repeated on precincts drawn at random: every dot is one
 * repetition, and their spread is the range shown next to the results.
 */
export function Resampling({ inputs, flows, source, target, previousYear, currentYear, words, model, result }: Props) {
  const [draws, setDraws] = useState<Matrix[]>([]);
  const [round, setRound] = useState(0);
  const [seenRef, seen] = useSeen<HTMLDivElement>(0.5);
  const [ref, width] = useWidth<HTMLDivElement>(640);
  const random = useRef(randomSource(1));

  useEffect(() => {
    if (!seen) return;
    random.current = randomSource(round + 1);
    if (prefersReducedMotion()) {
      setDraws(Array.from({ length: DRAWS }, () => resampledMatrix(model, result, random.current)));
      return;
    }
    setDraws([]);
    let count = 0;
    let handle = requestAnimationFrame(function tick() {
      const draw = resampledMatrix(model, result, random.current);
      setDraws((current) => [...current, draw]);
      count += 1;
      if (count < DRAWS) handle = requestAnimationFrame(tick);
    });
    return () => cancelAnimationFrame(handle);
  }, [seen, round, model, result]);

  const estimate = flows.transitions[source][target];
  const low = flows.transitionsLow[source][target];
  const high = flows.transitionsHigh[source][target];
  const values = draws.map((draw) => draw[source][target] * 100);
  const inside = values.filter((value) => value >= low && value <= high).length;
  const done = draws.length >= DRAWS;

  const pad = Math.max((high - low) * 0.9, 3);
  const from = Math.max(0, low - pad);
  const to = Math.min(100, high + pad);
  const height = 230;
  const margin = { top: 34, right: 14, bottom: 30, left: 14 };
  const inner = width - margin.left - margin.right;
  const floor = height - margin.bottom;
  const x = (value: number) => margin.left + ((value - from) / (to - from)) * inner;

  // Dots pile up in columns, like a histogram built one repetition at a time
  const columns = Math.max(10, Math.min(46, Math.floor(inner / 9)));
  const piles = new Array(columns).fill(0);
  const dots = values.map((value) => {
    const column = Math.min(columns - 1, Math.max(0, Math.floor(((value - from) / (to - from)) * columns)));
    return { column, level: piles[column]++ };
  });
  const tallest = Math.max(...piles, 1);
  const rise = Math.min(inner / columns, 13, (floor - margin.top - 8) / tallest);
  const color = words.mark(inputs.targets[target]);

  return (
    <div ref={seenRef}>
      <div ref={ref}>
        <svg
          className="chart"
          width={width}
          height={height}
          role="img"
          aria-label={`Odhady z opakovaných výpočtů na náhodně vylosovaných okrscích, ${fmtRange(low, high)}`}
        >
          <rect x={x(low)} y={margin.top} width={x(high) - x(low)} height={floor - margin.top} fill="var(--accent-soft)" rx={4} />
          <line className="axis-line" x1={margin.left} x2={margin.left + inner} y1={floor} y2={floor} />
          {ticks(from, to, 8).map((mark) => (
            <text key={mark} x={x(mark)} y={floor + 17} textAnchor="middle">
              {fmtNum(mark, 0)} %
            </text>
          ))}
          {dots.map((dot, i) => (
            <circle
              key={i}
              className="method-dot"
              cx={margin.left + ((dot.column + 0.5) / columns) * inner}
              cy={floor - rise / 2 - 1 - dot.level * rise}
              r={rise / 2 - 0.8}
              fill={color}
              fillOpacity={i === dots.length - 1 && !done ? 1 : 0.7}
            />
          ))}
          <line x1={x(estimate)} x2={x(estimate)} y1={margin.top - 6} y2={floor} stroke="var(--ink)" strokeWidth={2} />
          <text
            className="label-strong"
            x={x(estimate)}
            y={margin.top - 14}
            textAnchor={x(estimate) > width - 110 ? "end" : x(estimate) < 110 ? "start" : "middle"}
          >
            odhad ze všech okrsků {fmtPct(estimate, 0)}
          </text>
        </svg>
      </div>
      <div className="method-after">
        <div className="method-panel-head">
          <span className="legend-item small muted">
            <span className="swatch" style={{ background: "var(--accent-soft)", border: "1px solid var(--line-strong)" }} />
            rozpětí uvedené u výsledků, {fmtRange(low, high)}
          </span>
          <button className="text-button" onClick={() => setRound((current) => current + 1)} disabled={!done && seen}>
            Losovat znovu
          </button>
        </div>
        <p className="method-result num">
          {done ? (
            <>
              V <strong>
                {fmtInt(inside)} ze {DRAWS}
              </strong>{" "}
              losování vyšlo, že z lidí, kteří {words.votedPlural(inputs.sources[source], previousYear)}, jich{" "}
              {fmtRange(low, high)} {words.voted(5, inputs.targets[target], currentYear)}.
            </>
          ) : (
            <>
              {fmtInt(draws.length)}. losování ze {DRAWS}
            </>
          )}
        </p>
      </div>
    </div>
  );
}
