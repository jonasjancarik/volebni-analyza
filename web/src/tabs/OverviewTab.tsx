import { useState } from "react";
import type { TabProps } from "../Council";
import { Histogram } from "../components/Histogram";
import { ResultRows } from "../components/ResultRows";
import { SeatChart } from "../components/SeatChart";
import { fmtInt, fmtPct, fmtPp, fmtSignedInt, listName, plural } from "../format";

const SHOWN = 10;

export function OverviewTab({ council, colors, focus }: TabProps) {
  const [showAll, setShowAll] = useState(false);
  const { lists, summary, previousSummary, previous } = council;
  const parliamentary = council.election.type === "parliamentary";
  const listWord = parliamentary ? "strana" : "kandidátka";

  if (lists.length === 0) {
    return <div className="banner neutral">Pro toto zastupitelstvo nejsou výsledky kandidátek k dispozici.</div>;
  }

  const [winner, second] = lists;
  const turnoutChange = previousSummary ? summary.turnout - previousSummary.turnout : null;
  const hasPrevious = lists.some((list) => list.previous);
  const hasSeats = council.seats > 0;
  const recalculated = lists.some((list) => Math.abs(list.officialShare - list.share) > 0.05);

  const visible = lists
    .map((list, index) => ({ list, index }))
    .filter(({ index }) => showAll || index < SHOWN || index === focus);
  const rows = visible.map(({ list, index }) => ({
    key: list.number,
    name: list.name,
    color: colors[index],
    share: list.share,
    reference: list.previous?.share,
    change: list.previous ? list.share - list.previous.share : null,
    seats: list.seats,
    focus: index === focus && lists.length > 1,
  }));

  const turnouts = council.precincts.filter((precinct) => precinct.registered > 0).map((precinct) => precinct.turnout);
  const withSeats = lists.filter((list) => list.seats > 0).length;

  return (
    <div className="stack">
      <div className="overview-top">
        <p className="lead">
          Nejvíc hlasů získala {listWord} <strong>{listName(winner.name)}</strong>, {fmtPct(winner.share)}
          {second && (
            <>
              , s náskokem {fmtPp(winner.share - second.share).replace("+", "")} před {parliamentary ? "stranou" : "kandidátkou"}{" "}
              <strong>{listName(second.name)}</strong>
            </>
          )}
          .
        </p>
        <div className="tiles">
          <div className="tile">
            <div className="label">Volební účast</div>
            <div className="value">{summary.turnout > 0 ? fmtPct(summary.turnout) : "–"}</div>
            {turnoutChange != null && previous && (
              <div className={`delta ${turnoutChange >= 0 ? "up" : "down"}`}>
                {fmtPp(turnoutChange)} proti {previous.year}
              </div>
            )}
          </div>
          <div className="tile">
            <div className="label">Zapsaní voliči</div>
            <div className="value">{fmtInt(summary.registered)}</div>
            {previousSummary && previous && (
              <div className="delta">
                {fmtSignedInt(summary.registered - previousSummary.registered)} proti {previous.year}
              </div>
            )}
          </div>
          {hasSeats && (
            <div className="tile">
              <div className="label">Mandáty</div>
              <div className="value">{council.seats}</div>
              <div className="delta">
                získalo je {withSeats} z {lists.length} {plural(lists.length, "kandidátky", "kandidátek", "kandidátek")}
              </div>
            </div>
          )}
        </div>
      </div>

      <div className={hasSeats || turnouts.length >= 8 ? "grid two" : "grid"}>
        <section className="card">
          <div className="card-head">
            <div>
              <h2>Výsledky {parliamentary ? "stran" : "kandidátek"}</h2>
              <div className="card-sub">Podíl ze všech platných hlasů</div>
            </div>
            {hasPrevious && previous && (
              <div className="legend">
                <span className="legend-item">
                  <span className="tick-key" /> výsledek {previous.year}
                </span>
              </div>
            )}
          </div>
          <ResultRows
            rows={rows}
            showSeats={hasSeats}
            nameLabel={parliamentary ? "Strana" : "Kandidátka"}
            changeLabel={hasPrevious && previous ? `Proti ${previous.year}` : ""}
            referenceTitle={(row) => `${previous?.year}: ${fmtPct(row.reference ?? 0)}`}
          />
          {lists.length > SHOWN && (
            <button className="text-button" onClick={() => setShowAll(!showAll)}>
              {showAll ? "Zobrazit jen nejsilnější" : `Zobrazit všech ${lists.length}`}
            </button>
          )}
          <div style={{ marginTop: 14 }}>
            {hasPrevious && previous && (
              <p className="note">
                Srovnání s rokem {previous.year} je jen u kandidátek, které tehdy kandidovaly pod stejným názvem.
              </p>
            )}
            {!parliamentary && summary.validVotes > summary.registered && (
              <p className="note">
                Každý volič může rozdat tolik hlasů, kolik se volí zastupitelů, proto se podíly počítají z hlasů, ne z
                voličů.
              </p>
            )}
            {recalculated && (
              <p className="note">
                O překročení pětiprocentní hranice rozhoduje přepočtený podíl, který ČSÚ upravuje u kandidátek s méně
                kandidáty, než kolik se volí zastupitelů. Najdete ho v datech ke stažení.
              </p>
            )}
          </div>
        </section>

        {(hasSeats || turnouts.length >= 8) && (
          <div className="stack">
            {hasSeats && (
              <section className="card">
                <div className="card-head">
                  <div>
                    <h2>Složení zastupitelstva</h2>
                    {previous && hasPrevious && <div className="card-sub">V závorce změna proti roku {previous.year}</div>}
                  </div>
                </div>
                <SeatChart lists={lists} colors={colors} focus={focus} />
              </section>
            )}
            {turnouts.length >= 8 && (
              <section className="card">
                <div className="card-head">
                  <div>
                    <h2>Účast v okrscích</h2>
                    <div className="card-sub">
                      Od {fmtPct(Math.min(...turnouts))} do {fmtPct(Math.max(...turnouts))} v {fmtInt(turnouts.length)}{" "}
                      okrscích
                    </div>
                  </div>
                </div>
                <Histogram values={turnouts} overall={summary.turnout} />
              </section>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
