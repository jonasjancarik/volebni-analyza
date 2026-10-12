import type { ComparedPrecinct, Council, Precinct } from "../api";
import { fmtInt, fmtPct, fmtPp } from "../format";
import { MapLink } from "./MapLink";
import { LazyMiniMap } from "./LazyMiniMap";
import { ResultRows } from "./ResultRows";

interface Props {
  council: Council;
  precinct: Precinct;
  colors: string[];
  focus: number;
  compared?: ComparedPrecinct;
  previousYear?: string;
  /** Show where the precinct lies; off where the map is already showing it */
  map?: boolean;
  onClose: () => void;
}

/** Everything about one precinct: turnout and how its lists did against the whole council. */
export function PrecinctDetail({ council, precinct, colors, focus, compared, previousYear, map, onClose }: Props) {
  const total = precinct.votes.reduce((sum, votes) => sum + votes, 0) || 1;
  const area = council.areas.find((item) => item.code === precinct.area);
  const wholeName = council.election.type === "parliamentary" ? "celý kraj" : council.areas.length ? "celé město" : "celá obec";
  const rows = council.lists
    .map((list, index) => ({
      key: list.number,
      name: list.name,
      color: colors[index],
      share: (precinct.votes[index] / total) * 100,
      reference: list.share,
      change: (precinct.votes[index] / total) * 100 - list.share,
      focus: index === focus,
    }))
    .sort((a, b) => b.share - a.share)
    .filter((row, position) => position < 8 || row.focus);
  const turnoutChange = compared ? compared.turnout[1] - compared.turnout[0] : null;

  return (
    <>
      <div className="detail-head">
        <div>
          <h3>Okrsek {precinct.number}</h3>
          {area && <div className="small muted">{area.name}</div>}
        </div>
        <button className="icon-button" onClick={onClose} aria-label="Zavřít detail okrsku">
          <svg width="12" height="12" viewBox="0 0 12 12" aria-hidden>
            <path d="M1.5 1.5l9 9m0-9l-9 9" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" />
          </svg>
        </button>
      </div>
      {map && (
        <div className="detail-map">
          <LazyMiniMap precinct={precinct.id} />
          <MapLink precinct={precinct.id} label="Otevřít na velké mapě" />
        </div>
      )}
      <div className="mini-stats num">
        <div>
          <div className="label">Účast</div>
          <div className="value">{fmtPct(precinct.turnout)}</div>
          {turnoutChange != null && (
            <div className={`small delta ${turnoutChange >= 0 ? "up" : "down"}`}>{fmtPp(turnoutChange)}</div>
          )}
        </div>
        <div>
          <div className="label">Zapsaní voliči</div>
          <div className="value">{fmtInt(precinct.registered)}</div>
        </div>
        <div>
          <div className="label">Přišlo volit</div>
          <div className="value">{fmtInt(precinct.ballots)}</div>
        </div>
      </div>
      <ResultRows
        rows={rows}
        changeLabel="Proti průměru"
        nameLabel={council.election.type === "parliamentary" ? "Strana" : "Kandidátka"}
        referenceTitle={(row) => `${wholeName}: ${fmtPct(row.reference ?? 0)}`}
      />
      <p className="note" style={{ marginTop: 12 }}>
        Čárka ukazuje výsledek za {wholeName === "celá obec" ? "celou obec" : wholeName}.
        {turnoutChange != null && previousYear ? ` Změna účasti je proti roku ${previousYear}.` : ""}
      </p>
    </>
  );
}
