import { fmtPct, fmtPp, listName } from "../format";

export interface ResultRow {
  key: string;
  name: string;
  color: string;
  share: number;
  /** Position of the comparison tick on the same scale as `share` */
  reference?: number | null;
  /** Difference shown next to the share, in percentage points */
  change?: number | null;
  seats?: number | null;
  focus?: boolean;
}

interface Props {
  rows: ResultRow[];
  showSeats?: boolean;
  changeLabel?: string;
  /** Heading of the name column */
  nameLabel?: string;
  referenceTitle?: (row: ResultRow) => string;
}

/** Lists as rows: name, a bar for the share and a tick for what it is compared with. */
export function ResultRows({ rows, showSeats, changeLabel, nameLabel, referenceTitle }: Props) {
  const scale = Math.max(...rows.map((row) => Math.max(row.share, row.reference ?? 0)), 1) * 1.04;
  const rowClass = `result-row${showSeats ? "" : " no-seats"}`;
  return (
    <div className="results">
      <div className={`${rowClass} header`}>
        <span>{nameLabel ?? "Kandidátka"}</span>
        <span>Podíl hlasů</span>
        <span>{changeLabel ?? ""}</span>
        {showSeats && <span>Mandáty</span>}
      </div>
      {rows.map((row) => (
        <div key={row.key} className={`${rowClass}${row.focus ? " is-focus" : ""}`}>
          <div style={{ minWidth: 0 }}>
            <div className="result-name" title={row.name}>
              <span className="swatch" style={{ background: row.color }} />
              <span className="text">{listName(row.name)}</span>
            </div>
            <div className="result-bar">
              <div className="fill" style={{ width: `${(row.share / scale) * 100}%`, background: row.color }} />
              {row.reference != null && (
                <div
                  className="tick"
                  style={{ left: `${(row.reference / scale) * 100}%` }}
                  title={referenceTitle?.(row)}
                />
              )}
            </div>
          </div>
          <span className="right share num">{fmtPct(row.share)}</span>
          <span className={`right small num ${row.change == null ? "muted" : row.change >= 0 ? "delta up" : "delta down"}`}>
            {row.change == null ? "" : fmtPp(row.change)}
          </span>
          {showSeats && <span className="right num">{row.seats ? row.seats : <span className="muted">–</span>}</span>}
        </div>
      ))}
    </div>
  );
}
