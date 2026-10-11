import type { CandidateList } from "../api";
import { listName, plural } from "../format";
import { useWidth } from "../hooks";

interface Props {
  lists: CandidateList[];
  colors: string[];
  focus: number;
}

/** One dot per seat, lists side by side from the strongest. */
export function SeatChart({ lists, colors, focus }: Props) {
  const [ref, width] = useWidth<HTMLDivElement>(360);
  const seated = lists.map((list, index) => ({ list, index })).filter((item) => item.list.seats > 0);
  const total = seated.reduce((sum, item) => sum + item.list.seats, 0);
  const majority = Math.floor(total / 2) + 1;

  const rows = total <= 15 ? 1 : total <= 35 ? 3 : 5;
  const columns = Math.ceil(total / rows);
  const pitch = Math.min(18, Math.floor(width / columns));
  const radius = Math.max(2.5, pitch / 2 - 1.5);
  const seats: { color: string; dim: boolean }[] = [];
  for (const { list, index } of seated) {
    for (let i = 0; i < list.seats; i += 1) seats.push({ color: colors[index], dim: false });
  }
  const height = rows * pitch;

  return (
    <div ref={ref}>
      <svg
        className="chart"
        width={columns * pitch}
        height={height}
        role="img"
        aria-label={`Rozdělení ${total} mandátů mezi kandidátky`}
        style={{ width: columns * pitch }}
      >
        {seats.map((seat, i) => (
          // Filled column by column, so that each list forms one block
          <circle
            key={i}
            cx={Math.floor(i / rows) * pitch + pitch / 2}
            cy={(i % rows) * pitch + pitch / 2}
            r={radius}
            fill={seat.color}
          />
        ))}
      </svg>
      <div className="legend" style={{ marginTop: 16, flexDirection: "column", gap: 7 }}>
        {seated.map(({ list, index }) => (
          <span className="legend-item" key={list.number} style={{ fontWeight: index === focus ? 620 : undefined }}>
            <span className="swatch" style={{ background: colors[index] }} />
            <span style={{ flex: 1, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
              {listName(list.name)}
            </span>
            <span className="num" style={{ color: "var(--ink)" }}>
              {list.seats}
              {list.previous ? (
                <span className="muted"> {seatChange(list.seats - list.previous.seats)}</span>
              ) : null}
            </span>
          </span>
        ))}
      </div>
      <p className="note" style={{ marginTop: 14 }}>
        Většinu má {majority} z {total} {plural(total, "mandátu", "mandátů", "mandátů")}.
      </p>
    </div>
  );
}

function seatChange(change: number): string {
  if (change === 0) return "(±0)";
  return change > 0 ? `(+${change})` : `(−${Math.abs(change)})`;
}
