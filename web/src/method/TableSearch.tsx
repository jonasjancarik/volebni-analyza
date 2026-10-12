import { useEffect, useMemo, useState } from "react";
import { fmtInt, fmtNum, fmtPct, truncate } from "../format";
import { prefersReducedMotion, useSeen, useTooltip, useWidth } from "../hooks";
import { type Model, predictColumn, type Snapshot } from "./model";
import { ticks } from "./PrecinctCloud";
import type { StepProps } from "./Step";

interface Props extends StepProps {
  model: Model;
  snapshots: Snapshot[];
  onPick: (source: number, target: number) => void;
}

const DURATION = 7000;

const blend = (from: number, to: number, share: number) => from + (to - from) * share;

/**
 * The search for the transition table, played back from an even split to the
 * result, next to how well the table of each moment reproduces the precincts.
 */
export function TableSearch({ inputs, source, target, currentYear, previousYear, words, model, snapshots, onPick }: Props) {
  const last = snapshots.length - 1;
  const [frame, setFrame] = useState(() => (prefersReducedMotion() ? last : 0));
  const [playing, setPlaying] = useState(false);
  const [started, setStarted] = useState(false);
  const [seenRef, seen] = useSeen<HTMLDivElement>(0.5);
  const [ref, width] = useWidth<HTMLDivElement>(640);
  const tooltip = useTooltip();

  // Starts by itself the first time the reader gets here
  useEffect(() => {
    if (seen && !started && !prefersReducedMotion()) {
      setStarted(true);
      setPlaying(true);
    }
  }, [seen, started]);

  useEffect(() => {
    if (!playing) return;
    let previous: number | null = null;
    let handle = requestAnimationFrame(function tick(now) {
      const elapsed = previous == null ? 0 : now - previous;
      previous = now;
      setFrame((current) => {
        const next = Math.min(last, current + (elapsed / DURATION) * last);
        if (next >= last) setPlaying(false);
        return next;
      });
      handle = requestAnimationFrame(tick);
    });
    return () => cancelAnimationFrame(handle);
  }, [playing, last]);

  const predictions = useMemo(
    () => snapshots.map((snapshot) => predictColumn(model, snapshot.matrices, target)),
    [model, snapshots, target],
  );

  const index = Math.min(Math.floor(frame), last);
  const following = Math.min(index + 1, last);
  const share = frame - index;
  const from = snapshots[index];
  const to = snapshots[following];
  const matrix = from.matrix.map((row, r) => row.map((value, c) => blend(value, to.matrix[r][c], share) * 100));
  const explained = Math.max(0, blend(from.explained, to.explained, share));
  const iteration = Math.round(blend(from.iteration, to.iteration, share));
  const finished = frame >= last;

  const actual = inputs.precincts.map((precinct) => precinct.current[target]);
  const predicted = predictions[index].map((value, i) => blend(value, predictions[following][i], share) * 100);
  const max =
    Math.max(...actual, ...predictions[last].map((value) => value * 100), 100 / inputs.targets.length, 1) * 1.08;
  // The same size as the chart of the previous step
  const height = Math.min(430, Math.max(300, width * 0.62));
  const margin = { top: 26, right: 16, bottom: 46, left: 46 };
  const inner = width - margin.left - margin.right;
  const innerHeight = height - margin.top - margin.bottom;
  const x = (value: number) => margin.left + (Math.min(value, max) / max) * inner;
  const y = (value: number) => margin.top + innerHeight - (Math.min(value, max) / max) * innerHeight;
  const color = words.mark(inputs.targets[target]);
  const targetName = words.short(inputs.targets[target]);

  const play = () => {
    if (finished) setFrame(0);
    setStarted(true);
    setPlaying(true);
  };

  return (
    <div ref={seenRef}>
      <div className="method-player">
        <button className="button" onClick={playing ? () => setPlaying(false) : play}>
          {playing ? "Pozastavit" : finished ? "Přehrát znovu" : frame > 0 ? "Pokračovat" : "Spustit hledání"}
        </button>
        <input
          className="method-range"
          type="range"
          min={0}
          max={last}
          step={0.01}
          value={frame}
          aria-label="Průběh hledání"
          onChange={(event) => {
            setPlaying(false);
            setStarted(true);
            setFrame(Number(event.target.value));
          }}
        />
        <span className="method-count num">
          {fmtInt(iteration)}. úprava z {fmtInt(snapshots[last].iteration)}
        </span>
      </div>

      <div className="method-search">
        <div>
          <div className="method-caption">
            Tabulka přesunů: kolik procent každé skupiny z roku {previousYear} skončilo kde v roce {currentYear}
          </div>
          <div className="table-wrap">
            <table className="data matrix method-matrix">
              <thead>
                <tr>
                  <th />
                  {inputs.targets.map((name, c) => (
                    <th key={name} className={`col${c === target ? " on" : ""}`} title={name}>
                      {truncate(words.short(name), 22)}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {inputs.sources.map((name, r) => (
                  <tr key={name}>
                    <th scope="row" className={r === source ? "on" : undefined} title={name}>
                      {truncate(words.short(name), 24)}
                    </th>
                    {inputs.targets.map((targetGroup, c) => {
                      const value = matrix[r][c];
                      const picked = r === source && c === target;
                      return (
                        <td
                          key={targetGroup}
                          className={`heat${picked ? " picked" : ""}`}
                          aria-selected={picked}
                          onClick={() => onPick(r, c)}
                          style={{
                            background: `color-mix(in srgb, var(--series-1) ${Math.round(Math.min(value, 100) * 0.75)}%, var(--surface-2))`,
                            color: value > 55 ? "#fff" : "var(--ink)",
                          }}
                        >
                          {fmtNum(value, 0)}
                        </td>
                      );
                    })}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        <div ref={ref}>
          <div className="method-caption">
            Jak tabulka sedí na okrsky: {targetName} {currentYear}
          </div>
          <svg
            className="chart"
            width={width}
            height={height}
            role="img"
            aria-label={`Výsledek skupiny ${targetName} v okrscích podle tabulky a ve skutečnosti`}
          >
            {ticks(0, max).map((mark) => (
              <g key={mark}>
                <line className="grid-line" x1={x(mark)} x2={x(mark)} y1={margin.top} y2={margin.top + innerHeight} />
                <line className="grid-line" x1={margin.left} x2={margin.left + inner} y1={y(mark)} y2={y(mark)} />
                <text x={x(mark)} y={margin.top + innerHeight + 16} textAnchor="middle">
                  {fmtNum(mark, 0)}
                </text>
                <text x={margin.left - 8} y={y(mark)} dy="0.35em" textAnchor="end">
                  {fmtNum(mark, 0)}
                </text>
              </g>
            ))}
            <line className="axis-line" x1={x(0)} y1={y(0)} x2={x(max)} y2={y(max)} strokeDasharray="4 4" />
            <text x={x(max) - 4} y={y(max) + 14} textAnchor="end">
              přesná shoda
            </text>
            <text x={margin.left + inner} y={height - 6} textAnchor="end">
              podle tabulky, % zapsaných →
            </text>
            <text x={margin.left - 34} y={12}>
              ↑ skutečný výsledek, % zapsaných
            </text>
            {inputs.precincts.map((precinct, i) => (
              <circle
                key={precinct.id}
                cx={x(predicted[i])}
                cy={y(actual[i])}
                r={3}
                fill={color}
                fillOpacity={0.5}
                onMouseMove={(event) =>
                  tooltip.show(
                    event,
                    <>
                      <div className="t-title">Okrsek {precinct.id}</div>
                      <div>podle tabulky {fmtPct(predicted[i])}</div>
                      <div>ve skutečnosti {fmtPct(actual[i])}</div>
                    </>,
                  )
                }
                onMouseLeave={tooltip.hide}
              />
            ))}
          </svg>
          {tooltip.element}
        </div>
      </div>

      <div className="method-meter">
        <div className="method-meter-track">
          <span style={{ width: `${Math.min(explained, 100)}%` }} />
        </div>
        <p className="method-result num">
          Tabulka vysvětluje <strong>{fmtPct(explained, 0)}</strong> rozdílů mezi okrsky.
        </p>
      </div>
    </div>
  );
}
