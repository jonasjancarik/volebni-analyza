import { Link } from "react-router-dom";
import { type Place, useElections, useOverview } from "./api";
import { Search } from "./components/Search";
import { Loading, Problem } from "./components/State";
import { fmtCompact, fmtInt, fmtPct, fmtPp, listName } from "./format";

function PlaceCard({ place, electionId, scale }: { place: Place; electionId: string; scale: number }) {
  const change = place.previousTurnout != null ? place.turnout - place.previousTurnout : null;
  return (
    <Link to={`/${electionId}/${place.code}`} className="place-card">
      <h3>{place.name}</h3>
      <div className="sub num">{fmtInt(place.registered)} zapsaných voličů</div>
      {place.winner && (
        <>
          <div className="winner">
            <span className="share num">{fmtPct(place.winner.share)}</span>{" "}
            <span className="muted">{listName(place.winner.name)}</span>
          </div>
          <div className="track" aria-hidden>
            <span style={{ width: `${(place.winner.share / scale) * 100}%` }} />
          </div>
        </>
      )}
      <div className="foot num">
        <span>Účast {fmtPct(place.turnout)}</span>
        {change != null && <span className={`delta ${change >= 0 ? "up" : "down"}`}>{fmtPp(change)}</span>}
      </div>
    </Link>
  );
}

export function Home({ electionId }: { electionId: string }) {
  const overview = useOverview(electionId);
  const elections = useElections();
  const election = elections.data?.find((item) => item.id === electionId);
  if (overview.isPending || !election) return <Loading text="Načítám výsledky voleb…" />;
  if (overview.error) return <Problem error={overview.error} />;

  const data = overview.data;
  const parliamentary = data.kind === "parliamentary";
  const scale = Math.max(...data.places.map((place) => place.winner?.share ?? 0), 1);
  const change = data.previousTurnout != null ? data.turnout - data.previousTurnout : null;

  return (
    <div className="page">
      <section className="hero">
        <h1>{election.name}</h1>
        <p className="lede">
          {parliamentary
            ? "Výsledky stran, kandidáti a mapa okrsků ve všech čtrnácti krajích."
            : `Výsledky, mapa okrsků a přesuny voličů od minulých voleb pro všech ${fmtInt(data.councils)} zastupitelstev obcí, měst a městských částí.`}
        </p>
        <Search electionId={electionId} large autoFocus parliamentary={parliamentary} />
        <div className="hero-stats">
          <div className="hero-stat">
            <div className="value">{fmtPct(data.turnout)}</div>
            <div className="label">
              volební účast
              {change != null && election.previousYear && (
                <>
                  , <span className={`delta ${change >= 0 ? "up" : "down"}`}>{fmtPp(change)}</span> proti roku{" "}
                  {election.previousYear}
                </>
              )}
            </div>
          </div>
          <div className="hero-stat">
            <div className="value">{fmtCompact(data.registered)}</div>
            <div className="label">zapsaných voličů</div>
          </div>
          {data.lists[0] && (
            <div className="hero-stat">
              <div className="value">{fmtPct(data.lists[0].share)}</div>
              <div className="label">získal vítěz, {listName(data.lists[0].name)}</div>
            </div>
          )}
          {!parliamentary && (
            <div className="hero-stat">
              <div className="value">{fmtInt(data.councils)}</div>
              <div className="label">zastupitelstev</div>
            </div>
          )}
        </div>
      </section>

      <div className="section-head">
        <h2>{parliamentary ? "Kraje" : "Největší města"}</h2>
        <span className="hint">
          {parliamentary ? "Vítězná strana a účast v kraji" : "Vítězná kandidátka a účast; ostatní obce najdete hledáním"}
        </span>
      </div>
      <div className="place-grid">
        {data.places.map((place) => (
          <PlaceCard key={place.code} place={place} electionId={electionId} scale={scale} />
        ))}
      </div>
    </div>
  );
}
