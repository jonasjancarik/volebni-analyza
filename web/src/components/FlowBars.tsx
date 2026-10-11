import { fmtPct, fmtRange, listName } from "../format";

export interface FlowBar {
  name: string;
  label: string;
  color: string;
  value: number;
  low: number;
  high: number;
}

/** Bars with the estimate and a whisker for the range it moves in. */
export function FlowBars({ bars }: { bars: FlowBar[] }) {
  const shown = bars.filter((bar) => bar.value >= 0.5 || bar.high >= 3).sort((a, b) => b.value - a.value);
  const scale = Math.max(...shown.map((bar) => bar.high), 1) * 1.02;
  return (
    <div style={{ display: "grid", gridTemplateColumns: "minmax(0, 1fr)", gap: 10 }}>
      {shown.map((bar) => (
        <div key={bar.name}>
          <div style={{ display: "flex", justifyContent: "space-between", gap: 12, alignItems: "baseline" }}>
            <span className="small" style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }} title={bar.name}>
              {listName(bar.label)}
            </span>
            <span className="num" style={{ whiteSpace: "nowrap" }}>
              <span className="share">{fmtPct(bar.value, 0)}</span>{" "}
              <span className="small muted">{fmtRange(bar.low, bar.high)}</span>
            </span>
          </div>
          <div style={{ position: "relative", height: 10, marginTop: 4 }}>
            <div
              style={{
                position: "absolute",
                inset: "1px auto 1px 0",
                width: `${(bar.value / scale) * 100}%`,
                minWidth: 2,
                background: bar.color,
                borderRadius: "0 4px 4px 0",
              }}
            />
            <div
              title={`Rozpětí odhadu ${fmtRange(bar.low, bar.high)}`}
              style={{
                position: "absolute",
                top: 4,
                height: 2,
                left: `${(bar.low / scale) * 100}%`,
                width: `${((bar.high - bar.low) / scale) * 100}%`,
                background: "var(--ink)",
                boxShadow: "0 0 0 1px var(--surface)",
                borderRadius: 1,
              }}
            />
          </div>
        </div>
      ))}
    </div>
  );
}
