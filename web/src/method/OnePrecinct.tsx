import { useState } from "react";
import { fmtInt, fmtPct, truncate } from "../format";
import { useWidth } from "../hooks";
import type { StepProps } from "./Step";
import { people } from "./wording";

interface Props extends StepProps {
  precinct: number;
  onAnother: () => void;
}

function ribbon(x0: number, x1: number, from: [number, number], to: [number, number]): string {
  const middle = (x0 + x1) / 2;
  return (
    `M${x0},${from[0]} C${middle},${from[0]} ${middle},${to[0]} ${x1},${to[0]} ` +
    `L${x1},${to[1]} C${middle},${to[1]} ${middle},${from[1]} ${x0},${from[1]} Z`
  );
}

/**
 * One precinct split into the followed group and everybody else in both
 * elections. The slider moves through every flow between them that gives
 * exactly these results.
 */
export function OnePrecinct(props: Props) {
  const { inputs, source, target, previousYear, currentYear, colorOf, words, precinct, onAnother } = props;
  const [ref, width] = useWidth<HTMLDivElement>(560);
  // Where the slider stands between the least and the most that is possible
  const [position, setPosition] = useState(0.5);

  const data = inputs.precincts[precinct];
  const sourceName = inputs.sources[source];
  const targetName = inputs.targets[target];
  const everyone = data.registered;
  const before = Math.round((data.previous[source] / 100) * everyone);
  const after = Math.round((data.current[target] / 100) * everyone);
  const least = Math.max(0, before + after - everyone);
  const most = Math.min(before, after);
  const moved = Math.round(least + position * (most - least));

  const height = width < 420 ? 250 : 300;
  const top = 30;
  const gap = 8;
  const bar = 22;
  const side = Math.min(190, Math.max(96, width * 0.27));
  const left = side;
  const right = width - side - bar;
  const scale = (height - top - gap - 4) / everyone;
  const restLeft = top + before * scale + gap;
  const restRight = top + after * scale + gap;
  const chars = Math.floor(side / 7.2);
  const sourceColor = colorOf(sourceName);
  const targetColor = colorOf(targetName);
  const x0 = left + bar;
  const y = (value: number) => value * scale;

  const label = (text: string, count: number, x: number, at: number, anchor: "end" | "start") => (
    <>
      <text className="label-strong" x={x} y={at + 13} textAnchor={anchor}>
        {truncate(text, chars)}
      </text>
      <text x={x} y={at + 29} textAnchor={anchor}>
        {fmtInt(count)} {people(count)}
      </text>
    </>
  );

  return (
    <div className="method-split">
      <div ref={ref}>
        <svg
          className="chart"
          width={width}
          height={height}
          role="img"
          aria-label={`Okrsek ${data.id}: složení voličů v letech ${previousYear} a ${currentYear} a možné přesuny mezi nimi`}
        >
          <text className="label" x={left + bar / 2} y={14} textAnchor="middle">
            {previousYear}
          </text>
          <text className="label" x={right + bar / 2} y={14} textAnchor="middle">
            {currentYear}
          </text>

          <path
            d={ribbon(x0, right, [restLeft + y(after - moved), restLeft + y(everyone - before)], [restRight + y(before - moved), restRight + y(everyone - after)])}
            fill="var(--series-nonvoter)"
            opacity={0.4}
          />
          <path
            d={ribbon(x0, right, [restLeft, restLeft + y(after - moved)], [top + y(moved), top + y(after)])}
            fill={targetColor}
            opacity={0.22}
          />
          <path
            d={ribbon(x0, right, [top + y(moved), top + y(before)], [restRight, restRight + y(before - moved)])}
            fill={sourceColor}
            opacity={0.22}
          />
          <path d={ribbon(x0, right, [top, top + y(moved)], [top, top + y(moved)])} fill={sourceColor} opacity={0.7} />

          <rect x={left} y={top} width={bar} height={Math.max(y(before), 1)} rx={3} fill={sourceColor} />
          <rect x={left} y={restLeft} width={bar} height={y(everyone - before)} rx={3} fill="var(--series-rest)" />
          <rect x={right} y={top} width={bar} height={Math.max(y(after), 1)} rx={3} fill={targetColor} />
          <rect x={right} y={restRight} width={bar} height={y(everyone - after)} rx={3} fill="var(--series-rest)" />

          {label(words.short(sourceName), before, left - 10, top - 2, "end")}
          {label("Všichni ostatní", everyone - before, left - 10, Math.max(restLeft, top + 38), "end")}
          {label(words.short(targetName), after, right + bar + 10, top - 2, "start")}
          {label("Všichni ostatní", everyone - after, right + bar + 10, Math.max(restRight, top + 38), "start")}
        </svg>
      </div>

      <div className="method-panel">
        <div className="method-panel-head">
          <span className="field-label">Okrsek {data.id}</span>
          <button className="text-button" onClick={onAnother}>
            Zkusit jiný okrsek
          </button>
        </div>
        <p className="method-result num">
          Z {fmtInt(before)} lidí, kteří {words.votedPlural(sourceName, previousYear)}, jich{" "}
          <strong>{fmtInt(moved)}</strong> {words.voted(moved, targetName, currentYear)}.
          <span className="method-big">{fmtPct(before ? (moved / before) * 100 : 0, 0)}</span>
        </p>
        <input
          className="method-range"
          type="range"
          min={least}
          max={most}
          step={1}
          value={moved}
          disabled={most === least}
          aria-label="Kolik z nich to mohlo být"
          onChange={(event) => setPosition(most > least ? (Number(event.target.value) - least) / (most - least) : 0.5)}
        />
        <div className="method-range-ends num">
          <span>nejméně {fmtInt(least)}</span>
          <span>nejvíce {fmtInt(most)}</span>
        </div>
        <p className="note" style={{ marginTop: 14 }}>
          Ať jezdec posunete kamkoli, oba sloupce zůstanou stejné. Výsledky tohoto okrsku tedy připouštějí cokoli od{" "}
          {fmtPct(before ? (least / before) * 100 : 0, 0)} do {fmtPct(before ? (most / before) * 100 : 0, 0)}.
        </p>
      </div>
    </div>
  );
}
