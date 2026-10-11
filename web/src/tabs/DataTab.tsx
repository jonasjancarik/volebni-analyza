import { useQueryClient } from "@tanstack/react-query";
import type { Comparison } from "../api";
import type { TabProps } from "../Council";
import { downloadCsv, fmtInt, plural } from "../format";

const round = (value: number) => Number(value.toFixed(2));

export function DataTab({ council }: TabProps) {
  const { election, lists, precincts, areas, previous } = council;
  const client = useQueryClient();
  const prefix = `${election.id}_${council.code}`;
  const areaNames = new Map(areas.map((area) => [area.code, area.name]));
  const parliamentary = election.type === "parliamentary";

  const downloadLists = () =>
    downloadCsv(`${prefix}_kandidatky.csv`, [
      [
        "cislo", "kandidatka", "hlasy", "podil_hlasu_pct", "prepocteny_podil_csu_pct", "mandaty",
        ...(previous ? [`podil_${previous.year}_pct`, `mandaty_${previous.year}`] : []),
      ],
      ...lists.map((list) => [
        list.number, list.fullName, list.votes, round(list.share), list.officialShare, list.seats,
        ...(previous ? [list.previous ? round(list.previous.share) : "", list.previous?.seats ?? ""] : []),
      ]),
    ]);

  const downloadPrecincts = () =>
    downloadCsv(`${prefix}_okrsky.csv`, [
      ["okrsek", "uzemi", "zapsani_volici", "odevzdane_obalky", "ucast_pct", ...lists.map((list) => list.name)],
      ...precincts.map((precinct) => [
        precinct.number, areaNames.get(precinct.area) ?? "", precinct.registered, precinct.ballots, precinct.turnout,
        ...precinct.votes,
      ]),
    ]);

  // Offered once the estimate has been computed on the Přesuny voličů tab
  const flows = client.getQueryData<Comparison>(["comparison", election.id, council.code, null])?.flows;
  const downloadFlows = () => {
    if (!flows) return;
    downloadCsv(`${prefix}_presuny.csv`, [
      ["skupina_" + previous?.year, "skupina_" + election.year, "podil_skupiny_pct", "odhad_od_pct", "odhad_do_pct", "podil_vsech_volicu_pct"],
      ...flows.sources.flatMap((source, row) =>
        flows.targets.map((target, column) => [
          source, target, flows.transitions[row][column], flows.transitionsLow[row][column],
          flows.transitionsHigh[row][column], flows.electorate[row][column],
        ]),
      ),
    ]);
  };

  return (
    <section className="card" style={{ maxWidth: 760 }}>
      <h2>Data ke stažení</h2>
      <div className="card-sub">Soubory CSV se středníkem jako oddělovačem, otevřete je v Excelu i v Tabulkách Google.</div>
      <div className="downloads" style={{ marginTop: 10 }}>
        <div className="download">
          <div>
            <h3>Výsledky {parliamentary ? "stran" : "kandidátek"}</h3>
            <div className="small muted">
              {lists.length} {plural(lists.length, "řádek", "řádky", "řádků")}: hlasy, podíly{council.seats > 0 ? ", mandáty" : ""}
              {previous ? ` a srovnání s rokem ${previous.year}` : ""}
            </div>
          </div>
          <button className="button" onClick={downloadLists}>
            Stáhnout CSV
          </button>
        </div>
        <div className="download">
          <div>
            <h3>Okrsky</h3>
            <div className="small muted">
              {fmtInt(precincts.length)} {plural(precincts.length, "okrsek", "okrsky", "okrsků")}: účast a hlasy pro
              každou {parliamentary ? "stranu" : "kandidátku"}
            </div>
          </div>
          <button className="button" onClick={downloadPrecincts}>
            Stáhnout CSV
          </button>
        </div>
        {previous && (
          <div className="download">
            <div>
              <h3>Odhad přesunů voličů</h3>
              <div className="small muted">
                {flows
                  ? `Každá dvojice skupin ${previous.year} → ${election.year} s odhadem a jeho rozpětím`
                  : "Nejdřív otevřete kartu Přesuny voličů, odhad se tam spočítá."}
              </div>
            </div>
            <button className="button" onClick={downloadFlows} disabled={!flows} style={{ opacity: flows ? 1 : 0.45 }}>
              Stáhnout CSV
            </button>
          </div>
        )}
      </div>
      <p className="note" style={{ marginTop: 16 }}>
        Zdrojem jsou otevřená data Českého statistického úřadu z volby.cz.
      </p>
    </section>
  );
}
