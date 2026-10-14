import { lazy, Suspense, useState } from "react";
import { Link } from "react-router-dom";
import { Loading } from "../components/State";
import { downloadCsv, fmtInt, fmtNum } from "../format";
import { Figure, thousands } from "./blocks";
import { KINDS } from "./centreShared";
import { campPart, type TargetDistrict, type TargetPrecinct, type TargetsAnalysis } from "./targetsShared";

// The map library is large; it loads only when the article is opened
const TargetsMap = lazy(() => import("./TargetsMap"));

const round = (value: number | null) => (value == null ? null : Math.round(value));
const names = (items: { name: string }[]) =>
  items.length > 1
    ? `${items
        .slice(0, -1)
        .map((item) => item.name)
        .join(", ")} a ${items[items.length - 1].name}`
    : (items[0]?.name ?? "");

interface Column<Row> {
  key: string;
  head: string;
  value: (row: Row) => string | number | null;
  format?: (value: number) => string;
}

interface SortedTableProps<Row> {
  rows: Row[];
  columns: Column<Row>[];
  initial: string;
  /** Rows shown before the reader asks for all */
  shown: number;
  /** How the first column is drawn, e.g. as a link */
  first?: (row: Row) => React.ReactNode;
  fileName: string;
  rowKey: (row: Row) => string;
}

/** A table sorted by a click on a heading, with the first rows shown and the rest on request. */
function SortedTable<Row>({ rows, columns, initial, shown, first, fileName, rowKey }: SortedTableProps<Row>) {
  const [sort, setSort] = useState({ key: initial, down: true });
  const [all, setAll] = useState(false);
  const sorted = columns.find((column) => column.key === sort.key)!;
  const ordered = [...rows].sort((a, b) => {
    const [one, two] = [sorted.value(a), sorted.value(b)];
    const order =
      typeof one === "string" || typeof two === "string"
        ? String(one ?? "").localeCompare(String(two ?? ""), "cs")
        : (one ?? -Infinity) - (two ?? -Infinity);
    return sort.down ? -order : order;
  });
  const visible = all ? ordered : ordered.slice(0, shown);
  const cell = (column: Column<Row>, row: Row) => {
    const value = column.value(row);
    return typeof value === "number" && column.format ? column.format(value) : (value ?? "–");
  };

  return (
    <>
      <div className="table-wrap">
        <table className="data precinct-list">
          <thead>
            <tr>
              {columns.map((column) => (
                <th
                  key={column.key}
                  className={`sortable ${column.format ? "r" : ""} ${sort.key === column.key ? "sorted" : ""}`}
                  aria-sort={sort.key === column.key ? (sort.down ? "descending" : "ascending") : undefined}
                  // Numbers are first sorted from the largest, names from the start of the alphabet
                  onClick={() => setSort({ key: column.key, down: sort.key === column.key ? !sort.down : Boolean(column.format) })}
                >
                  {column.head}
                  {sort.key === column.key && (sort.down ? " ↓" : " ↑")}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {visible.map((row) => (
              <tr key={rowKey(row)}>
                {columns.map((column, index) => (
                  <td key={column.key} className={column.format ? "r" : undefined}>
                    {index === 0 && first ? first(row) : cell(column, row)}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div style={{ display: "flex", gap: 20, marginTop: 12, flexWrap: "wrap" }}>
        {rows.length > shown && (
          <button className="text-button" onClick={() => setAll(!all)}>
            {all ? `Zobrazit jen prvních ${shown}` : `Zobrazit všech ${fmtInt(rows.length)}`}
          </button>
        )}
        <button
          className="text-button"
          onClick={() =>
            downloadCsv(fileName, [
              columns.map((column) => column.head),
              ...ordered.map((row) => columns.map((column) => column.value(row))),
            ])
          }
        >
          Stáhnout tabulku jako CSV
        </button>
      </div>
    </>
  );
}

export function PragueTargets({ data }: { data: TargetsAnalysis }) {
  const { years, districts, precincts } = data;
  const districtOf = new Map(districts.map((district) => [district.code, district]));
  const mapPath = `/${data.council.election}/${data.council.code}/mapa`;

  const close = districts
    .filter((district) => district.list && district.list.missingVoters < 100)
    .sort((a, b) => a.list!.missingVoters - b.list!.missingVoters);
  const large = districts.filter((district) => district.registered >= 20000);
  const mostStayedHome = [...large].sort((a, b) => b.stayedHome - a.stayedHome).slice(0, 4);
  const mostAtStan = [...large].sort((a, b) => b.atStan - a.atStan).slice(0, 4);
  const sharedTurf = large
    .filter((district) => (district.piratiOfCamp ?? 100) < 33)
    .sort((a, b) => (a.piratiOfCamp ?? 0) - (b.piratiOfCamp ?? 0));

  const districtColumns: Column<TargetDistrict>[] = [
    { key: "name", head: "Městská část", value: (district) => district.name },
    { key: "registered", head: "Voliči", value: (district) => district.registered, format: fmtInt },
    { key: "stayedHome", head: "Nepřišli", value: (district) => round(district.stayedHome), format: fmtInt },
    { key: "atStan", head: "Odešli ke STAN", value: (district) => round(district.atStan), format: fmtInt },
    {
      key: "camp",
      head: "Díl Pirátů",
      value: (district) => (district.piratiOfCamp == null ? null : Math.round(district.piratiOfCamp)),
      format: (value) => `${fmtInt(value)} %`,
    },
    { key: "list", head: "Kandidátka s Piráty", value: (district) => district.list?.name ?? null },
    { key: "seats", head: "Mandáty", value: (district) => district.list?.seats ?? null, format: fmtInt },
    {
      key: "missing",
      head: "Chybělo k dalšímu",
      value: (district) => district.list?.missingVoters ?? null,
      format: fmtInt,
    },
  ];

  const precinctColumns: Column<TargetPrecinct>[] = [
    { key: "id", head: "Okrsek", value: (precinct) => precinct.id },
    { key: "district", head: "Městská část", value: (precinct) => districtOf.get(precinct.area)?.name ?? null },
    { key: "kind", head: "Zástavba", value: (precinct) => (precinct.kind ? KINDS[precinct.kind]?.name : null) ?? null },
    { key: "registered", head: "Voliči", value: (precinct) => precinct.registered, format: fmtInt },
    { key: "turnout", head: "Účast", value: (precinct) => precinct.turnout, format: (value) => fmtNum(value) },
    { key: "stayedHome", head: "Nepřišli", value: (precinct) => round(precinct.stayedHome), format: fmtInt },
    { key: "atStan", head: "Odešli ke STAN", value: (precinct) => round(precinct.atStan), format: fmtInt },
    { key: "pirati", head: "Piráti", value: (precinct) => precinct.pirati, format: (value) => fmtNum(value) },
    { key: "prahaSobe", head: "Praha Sobě", value: (precinct) => precinct.prahaSobe, format: (value) => fmtNum(value) },
    {
      key: "piratiMid",
      head: "Piráti do Sněmovny",
      value: (precinct) => precinct.piratiMid,
      format: (value) => fmtNum(value),
    },
    {
      key: "camp",
      head: "Díl Pirátů",
      value: (precinct) => round(campPart(precinct)),
      format: (value) => `${fmtInt(value)} %`,
    },
    {
      key: "missing",
      head: "Chybělo k mandátu v části",
      value: (precinct) => districtOf.get(precinct.area)?.list?.missingVoters ?? null,
      format: fmtInt,
    },
  ];

  return (
    <>
      <div className="tiles article-tiles">
        <div className="tile">
          <div className="value num">{thousands(data.stayedHome)}</div>
          <div className="label">
            loňských voličů Pirátů do Sněmovny letos nepřišlo k volbám, i podle opatrného odhadu
          </div>
        </div>
        <div className="tile">
          <div className="value num">{thousands(data.atStan)}</div>
          <div className="label">voličů Pirátů z roku {years.previous} letos volilo STAN</div>
        </div>
        <div className="tile">
          <div className="value num">{close.length}</div>
          <div className="label">městské části, kde Pirátům k dalšímu mandátu chybělo méně než 100 voličů</div>
        </div>
      </div>

      <section className="prose">
        <h2>Shrnutí</h2>
        <ul className="takeaways">
          <li>
            Nejvíc lidí, kteří loni volili Piráty do Sněmovny a letos nepřišli, bydlí v částech{" "}
            {names(mostStayedHome)}. Jsou to velké části s nízkou účastí, takže tam jde hlavně o to lidi k volbám
            přivést.
          </li>
          <li>
            Nejvíc bývalých voličů Pirátů odešlo ke STAN v částech {names(mostAtStan)}. Tady jde spíš o přesvědčování.
          </li>
          <li>
            O mandát v zastupitelstvu městské části šlo o desítky lidí v částech{" "}
            {names(close.map((district) => ({ name: `${district.name} (${fmtInt(district.list!.missingVoters)})` })))}.
          </li>
          <li>
            V částech {names(sharedTurf)} mají Piráti méně než třetinu hlasů Pirátů a Prahy Sobě. Hlasy navíc by
            tam Piráti brali z velké části Praze Sobě. Pro většinu na magistrátu má tam větší smysl přivést lidi,
            kteří nepřišli, než přetahovat voliče.
          </li>
        </ul>
      </section>

      <section className="prose">
        <h2>Jak mapu číst</h2>
        <p>Mapa má tři vrstvy a každá ukazuje jiný druh práce.</p>
        <p>
          <strong>Nepřišli k volbám</strong> ukazuje, kolik lidí, kteří v roce {years.parliamentary} volili Piráty do
          Sněmovny, v okrsku letos nejspíš k volbám nepřišlo. Tady pomáhá být vidět, mluvit se sousedy a připomenout
          jim volby.
        </p>
        <p>
          <strong>Odešli ke STAN</strong> ukazuje, kolik voličů Pirátů z roku {years.previous} letos podle odhadu
          volilo STAN. Tihle lidé volit chodí, jen dnes volí jinak; pomůže, když uvidí, co Piráti v jejich okolí
          dělají.
        </p>
        <p>
          <strong>Další mandát v městské části</strong> ukazuje, kolik voličů chybělo kandidátce s Piráty k dalšímu
          mandátu v zastupitelstvu městské části. Kde jde o desítky lidí, rozhoduje o složení radnice i pár aktivních
          sousedů.
        </p>
        <p>Vrstvy v druhé řadě pomáhají vybrat mezi okrsky: díl Pirátů z hlasů obou kandidátek, účast a výsledek do Sněmovny.</p>
      </section>

      <Figure
        title="Okrsky na mapě"
        sub="Vyberte vrstvu. Najetím na okrsek uvidíte jeho čísla, kliknutím ho otevřete v mapě výsledků."
      >
        <Suspense fallback={<Loading text="Načítám mapu…" />}>
          <TargetsMap data={data} />
        </Suspense>
      </Figure>

      <Figure
        title="Městské části"
        sub="Seřazené od největšího počtu lidí, kteří nepřišli. Kliknutím na záhlaví sloupce tabulku seřadíte."
        note={`„Díl Pirátů“ je podíl Pirátů z hlasů Pirátů a Prahy Sobě do zastupitelstva hlavního města. „Chybělo k dalšímu“ je počet voličů, se kterými by kandidátka s Piráty získala v zastupitelstvu městské části o mandát víc. Odhad odchodu ke STAN je pro jednotlivé části hrubý.`}
      >
        <SortedTable
          rows={districts.filter((district) => district.registered >= 3000)}
          columns={districtColumns}
          initial="stayedHome"
          shown={20}
          fileName="mistni-prace-piratu-mestske-casti.csv"
          rowKey={(district) => district.code}
        />
      </Figure>

      <Figure
        title={`Všech ${fmtInt(precincts.length)} okrsků`}
        sub="Seřazené od největšího počtu lidí, kteří nepřišli. Podíly jsou v procentech hlasů do zastupitelstva hlavního města, číslo okrsku ho otevře v mapě výsledků."
      >
        <SortedTable
          rows={precincts}
          columns={precinctColumns}
          initial="stayedHome"
          shown={40}
          first={(precinct) => (
            <Link className="inline-link" to={`${mapPath}?okrsek=${precinct.id}`}>
              {precinct.id}
            </Link>
          )}
          fileName="mistni-prace-piratu-okrsky.csv"
          rowKey={(precinct) => precinct.id}
        />
      </Figure>

      <section className="card method-notes">
        <h3>Jak se to počítalo</h3>
        <p className="note">
          <strong>Nepřišli k volbám.</strong> Počet lidí, kteří v okrsku loni volili do Sněmovny a letos ne, krát
          loňský podíl Pirátů v okrsku. Lidé, kteří loni přišli s voličským průkazem odjinud, se odečítají, protože
          v okrsku nebydlí. Počítá se, že voliči Pirátů zůstávali doma stejně často jako ostatní v okrsku. Podle
          celoměstského odhadu přesunů zůstávali doma častěji, nepřišlo jich 50 až 69 %. Skutečná čísla jsou proto
          spíš vyšší, pořadí okrsků se tím ale mění málo. {fmtInt(data.unusual)} okrsků odhad nemá: buď se od
          loňska výrazně změnil počet jejich voličů, nebo v nich letos volila méně než čtvrtina zapsaných. To bývá
          adresa úřadu, kde jsou hlášení lidé bez jiného bydliště.
        </p>
        <p className="note">
          <strong>Odešli ke STAN.</strong> Odhad přesunů voličů dělí okrsky do {data.precinctTypes} skupin podle toho,
          jak volily v roce {years.previous}, a pro každou zvlášť odhaduje, kolik voličů Pirátů přešlo ke STAN. Číslo
          okrsku je tento podíl krát počet voličů Pirátů v okrsku v roce {years.previous}. Okrsky téže skupiny se tedy
          liší jen tím, kolik tam Piráti tehdy měli voličů. Okrsky, které nejde s rokem {years.previous} srovnat, odhad
          nemají.
        </p>
        <p className="note">
          <strong>Další mandát.</strong> Počítá se kandidátka, na které Piráti do zastupitelstva městské části
          kandidovali, i společná s jinými stranami. Mandáty jsou přepočítané d&apos;Hondtovou metodou s
          pětiprocentní klauzulí a chybějící hlasy přepočtené na voliče průměrným počtem hlasů na jednu obálku v dané
          městské části.
        </p>
        <p className="note">
          Všechno jsou to součty a odhady za okrsky, ne údaje o jednotlivých lidech.{" "}
          <Link className="inline-link" to="/analyzy/praha-2026-pirati-praha-sobe">
            Přečíst si analýzu výsledku Pirátů a Prahy Sobě
          </Link>
        </p>
      </section>
    </>
  );
}
