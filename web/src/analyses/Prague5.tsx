import { lazy, Suspense, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { Scatter } from "../components/Scatter";
import { Loading } from "../components/State";
import { downloadCsv, fmtInt, fmtNum, fmtPct, plural } from "../format";
import {
  bare,
  CampSeats,
  ElectionBars,
  Figure,
  groupColors,
  type HeatColumn,
  HeatTable,
  hundreds,
  label,
  points,
  ResultsTable,
} from "./blocks";
import {
  type Area,
  BLOCS,
  type BlocScenario,
  change,
  KIND_NAMES,
  localOverCity,
  type Prague5Analysis,
  type Precinct,
  right,
  winner,
} from "./prague5Shared";
import "./prague5.css";

// The map library is large; it loads only when the article is opened
const Prague5Map = lazy(() => import("./Prague5Map"));

/** Lists that have no colour of their own in Praha 5 take that of their closest relative */
const SAME_COLOR: Record<string, string> = { prahaSobe: "praha5Sobe", spolu: "ods", odsTop: "ods", odsTopKdu: "ods" };

const ORDINALS = ["první", "druhý", "třetí", "čtvrtý", "pátý", "šestý", "sedmý", "osmý", "devátý", "desátý", "jedenáctý", "dvanáctý"];
const ordinal = (count: number) => ORDINALS[count - 1] ?? `${count}.`;

const FIFTHS = ["nejslabší pětina", "druhá pětina", "prostřední pětina", "čtvrtá pětina", "nejsilnější pětina"];

/** 959 → "960" */
const tens = (people: number) => fmtInt(Math.round(people / 10) * 10);
const pct = (value: number) => fmtNum(value);
const seatsWord = (count: number) => plural(count, "mandát", "mandáty", "mandátů");

/** "v 73", "ve 14": the preposition follows how the number is read */
function inCount(count: number): string {
  const first = count < 20 ? count : Math.floor(count / 10) * 10;
  return `${[2, 3, 4, 12, 13, 14, 20, 30, 40].includes(first) ? "ve" : "v"} ${fmtInt(count)}`;
}

/** The same list, or its closest counterpart, on the ballot of the district and on that of the city */
const PAIRS: { key: string; name: string; cityName?: string; local: string[]; city: string[]; previous?: [string, string] }[] = [
  { key: "praha5Sobe", name: "Praha 5 Sobě", cityName: "Praha Sobě", local: ["praha5Sobe"], city: ["prahaSobe"], previous: ["praha5Sobe", "prahaSobe"] },
  { key: "ods", name: "ODS a TOP 09 s lidovci", cityName: "Spolu (ODS a TOP 09)", local: ["ods", "top"], city: ["spolu"] },
  { key: "stan", name: "STAN", local: ["stan"], city: ["stan"], previous: ["stan", "stan"] },
  { key: "sen", name: "SEN", local: ["sen"], city: ["sen"] },
  { key: "ano", name: "ANO", local: ["ano"], city: ["ano"], previous: ["ano", "ano"] },
  { key: "pirati", name: "Piráti", local: ["pirati"], city: ["pirati"], previous: ["pirati", "pirati"] },
  { key: "spd", name: "SPD", local: ["spd"], city: ["spd"], previous: ["spd", "spd"] },
  { key: "motoriste", name: "Motoristé a Svobodní", cityName: "Motoristé", local: ["motoriste"], city: ["motoriste"] },
  { key: "nasePraha5", name: "Naše Praha 5", local: ["nasePraha5"], city: [] },
];

interface BallotRow {
  key: string;
  name: string;
  cityName?: string;
  local: number;
  city: number | null;
  previousGap: number | null;
}

function ballotRows(district: Area): BallotRow[] {
  const total = (shares: Record<string, number | null>, keys: string[]) =>
    keys.reduce((sum, key) => sum + (shares[key] ?? 0), 0);
  return PAIRS.map((pair) => ({
    key: pair.key,
    name: pair.name,
    cityName: pair.cityName,
    local: total(district.local, pair.local),
    city: pair.city.length ? total(district.city, pair.city) : null,
    previousGap: pair.previous ? localOverCity(district, pair.previous[0], pair.previous[1], true) : null,
  }));
}

interface TwoBallotsProps {
  rows: BallotRow[];
  ballots: number;
  years: { current: string; previous: string };
  colorOf: (key: string) => string;
}

/** Each list on the two ballots the same voters filled in: for the council of the district and of the city. */
function TwoBallots({ rows, ballots, years, colorOf }: TwoBallotsProps) {
  const top = Math.max(...rows.flatMap((row) => [row.local, row.city ?? 0])) * 1.04;
  const at = (value: number) => `${(value / top) * 100}%`;
  return (
    <>
      <div className="ballot-key">
        <span>
          <span className="mark" /> do zastupitelstva Prahy 5
        </span>
        <span>
          <span className="mark city" /> do zastupitelstva hlavního města
        </span>
      </div>
      <div className="table-wrap">
        <table className="data matrix">
          <thead>
            <tr>
              <th>Kandidátka</th>
              <th aria-label="Graf obou výsledků" />
              <th className="col">Do Prahy 5</th>
              <th className="col">Do hlavního města</th>
              <th className="col">Rozdíl v bodech</th>
              <th className="col">Rozdíl ve voličích</th>
              <th className="col">Rozdíl v roce {years.previous}</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => {
              const gap = row.city != null ? row.local - row.city : null;
              const color = colorOf(row.key);
              return (
                <tr key={row.key}>
                  <td>
                    <span className="split-name">
                      <span className="swatch" style={{ background: color }} />
                      {row.name}
                    </span>
                    {row.cityName && <div className="small muted">do hlavního města {row.cityName}</div>}
                  </td>
                  <td>
                    <div className="ballot-track" aria-hidden>
                      {row.city != null && (
                        <span
                          className="between"
                          style={{ left: at(Math.min(row.local, row.city)), width: at(Math.abs(row.local - row.city)) }}
                        />
                      )}
                      {row.city != null && <span className="mark city" style={{ left: at(row.city), color }} />}
                      <span className="mark" style={{ left: at(row.local), background: color }} />
                    </div>
                  </td>
                  <td className="heat plain">
                    <span className="share">{fmtPct(row.local)}</span>
                  </td>
                  <td className="heat plain">{row.city != null ? fmtPct(row.city) : "nekandidovala"}</td>
                  <td className="heat plain">{gap != null ? bare(gap) : "–"}</td>
                  <td className="heat plain">
                    {gap != null ? `${gap < 0 ? "−" : "+"}${tens((Math.abs(gap) / 100) * ballots)}` : "–"}
                  </td>
                  <td className="heat plain muted">{row.previousGap != null ? bare(row.previousGap) : "–"}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </>
  );
}

interface BlocScenariosProps {
  scenarios: BlocScenario[];
  majority: number;
  describe: (scenario: BlocScenario) => { title: string; detail?: string };
}

/** Seats of both camps under changed votes. */
function BlocScenarios({ scenarios, majority, describe }: BlocScenariosProps) {
  const actual = scenarios[0];
  const seat = (scenario: BlocScenario, key: string) => (
    <td className="r" key={key}>
      <span className={scenario.seats[key] === actual.seats[key] ? "" : "share"}>{scenario.seats[key]}</span>
    </td>
  );
  const enough = (count: number) => count >= majority;
  return (
    <div className="table-wrap">
      <table className="data scenarios bloc-scenarios">
        <thead>
          <tr>
            <th>Co by se změnilo</th>
            <th className="r">Praha 5 Sobě</th>
            <th className="r">Piráti</th>
            <th className="r">SEN</th>
            <th className="r sum">Dohromady</th>
            <th className="r">ODS</th>
            <th className="r">TOP 09</th>
            <th className="r">STAN</th>
            <th className="r">ANO</th>
            <th className="r sum">Dohromady</th>
          </tr>
        </thead>
        <tbody>
          {scenarios.map((scenario) => {
            const text = describe(scenario);
            const own = ["praha5Sobe", "pirati", "sen"].filter((key) => key in scenario.seats);
            return (
              <tr key={scenario.key} className={scenario === actual ? "is-actual" : undefined}>
                <td>
                  <div>{text.title}</div>
                  {text.detail && <div className="small muted">{text.detail}</div>}
                </td>
                {scenario.seats.joint != null && (
                  <td className="joint num" colSpan={3 - own.length}>
                    <span className="share">{scenario.seats.joint}</span> společně
                  </td>
                )}
                {own.map((key) => seat(scenario, key))}
                <td className="r sum">
                  <span className={scenario.blocs.coalition2022 === actual.blocs.coalition2022 ? "" : "share"}>
                    {scenario.blocs.coalition2022}
                  </span>
                </td>
                {["ods", "top", "stan", "ano"].map((key) => seat(scenario, key))}
                <td className="r sum">
                  <span className={`verdict ${enough(scenario.blocs.townHall) ? "has-majority" : "no-majority"}`}>
                    <strong className="num">{scenario.blocs.townHall}</strong>{" "}
                    {enough(scenario.blocs.townHall) ? "většina" : "bez většiny"}
                  </span>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

interface Column {
  key: string;
  head: string;
  value: (precinct: Precinct) => number | string | null;
  format?: (value: number) => string;
}

/** Every precinct with the numbers the article works with; a click on a heading sorts by it. */
function PrecinctList({ precincts, years, mapPath }: { precincts: Precinct[]; years: Prague5Analysis["years"]; mapPath: string }) {
  const [sort, setSort] = useState<{ key: string; down: boolean }>({ key: "id", down: false });
  const share = (key: string) => (precinct: Precinct) => precinct.local[key];
  const columns: Column[] = [
    { key: "id", head: "Okrsek", value: (precinct) => precinct.id },
    { key: "part", head: "Čtvrť", value: (precinct) => precinct.part ?? "" },
    { key: "registered", head: "Voliči", value: (precinct) => precinct.registered, format: fmtInt },
    { key: "turnout", head: "Účast", value: (precinct) => precinct.turnout.now, format: pct },
    { key: "before", head: `Piráti ${years.previous}`, value: (precinct) => precinct.previousLocal.pirati, format: pct },
    { key: "pirati", head: `Piráti ${years.current}`, value: share("pirati"), format: pct },
    { key: "change", head: "Změna", value: (precinct) => change(precinct, "pirati"), format: bare },
    { key: "city", head: "Piráti, magistrát", value: (precinct) => precinct.city.pirati, format: pct },
    ...["praha5Sobe", "sen", "stan", "ods", "ano"].map((key) => ({ key, head: label(key), value: share(key), format: pct })),
  ];
  const sorted = columns.find((column) => column.key === sort.key)!;
  const rows = [...precincts].sort((a, b) => {
    const [first, second] = [sorted.value(a), sorted.value(b)];
    const order =
      typeof first === "string" || typeof second === "string"
        ? String(first).localeCompare(String(second), "cs")
        : (first ?? -Infinity) - (second ?? -Infinity);
    return sort.down ? -order : order;
  });
  const cell = (column: Column, precinct: Precinct) => {
    const value = column.value(precinct);
    return typeof value === "number" && column.format ? column.format(value) : (value ?? "–");
  };

  return (
    <>
      <div className="table-wrap">
        <table className="data precinct-list">
          <thead>
            <tr>
              {columns.map((column, index) => (
                <th
                  key={column.key}
                  className={`sortable ${index > 1 ? "r" : ""} ${sort.key === column.key ? "sorted" : ""}`}
                  aria-sort={sort.key === column.key ? (sort.down ? "descending" : "ascending") : undefined}
                  // Numbers are first sorted from the largest, names from the start of the alphabet
                  onClick={() => setSort({ key: column.key, down: sort.key === column.key ? !sort.down : index > 1 })}
                >
                  {column.head}
                  {sort.key === column.key && (sort.down ? " ↓" : " ↑")}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((precinct) => (
              <tr key={precinct.id}>
                {columns.map((column, index) => (
                  <td key={column.key} className={index > 1 ? "r" : undefined}>
                    {index === 0 ? (
                      <Link className="inline-link" to={`${mapPath}?okrsek=${precinct.id}`}>
                        {precinct.id}
                      </Link>
                    ) : (
                      cell(column, precinct)
                    )}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <button
        className="text-button"
        style={{ marginTop: 12 }}
        onClick={() =>
          downloadCsv("praha-5-okrsky-2026.csv", [
            columns.map((column) => column.head),
            ...rows.map((precinct) => columns.map((column) => column.value(precinct))),
          ])
        }
      >
        Stáhnout tabulku jako CSV
      </button>
    </>
  );
}

export function Prague5({ data }: { data: Prague5Analysis }) {
  const { years, seats, majority, district, precincts, groups } = data;
  const ownColor = groupColors(data.lists);
  const colorOf = (key: string) => ownColor(SAME_COLOR[key] ?? key);
  const navigate = useNavigate();
  const councilPath = `/${data.council.election}/${data.council.code}`;

  const list = (key: string) => data.lists.find((item) => item.key === key)!;
  const [praha5Sobe, ods, stan, sen, ano, pirati, top] = ["praha5Sobe", "ods", "stan", "sen", "ano", "pirati", "top"].map(list);
  const previousList = (key: string) => data.previousLists.find((item) => item.key === key);
  const bloc = (key: string) => data.blocs.find((item) => item.key === key)!;
  const [coalition, townHall] = [bloc("coalition2022"), bloc("townHall")];
  const scenario = (key: string) => data.scenarios.find((item) => item.key === key);
  const inLine = (key: string) => data.nextInLine.find((item) => item.key === key);
  const [nextSobe, nextPirati, nextTop] = [inLine("praha5Sobe"), inLine("pirati"), inLine("top")];
  const lastSeatInCoalition = BLOCS[0].lists.includes(data.lastSeat.key);
  const [newPirati, fromStan, jointThree] = [scenario("new-pirati"), scenario("stan-to-pirati"), scenario("joint-three")];
  const ofVoters = (item: BlocScenario) => ((item.voters ?? 0) / data.summary.ballots) * 100;

  // The two ballots of the same voters
  const ballots = ballotRows(district).sort((a, b) => b.local - a.local);
  const ballot = (key: string) => ballots.find((row) => row.key === key)!;
  const gap = (key: string) => ballot(key).local - (ballot(key).city ?? 0);
  const inVoters = (pointsOfShare: number) => (Math.abs(pointsOfShare) / 100) * data.summary.ballots;

  // Precincts
  const { counts } = data;
  const fell = counts.fell.pirati;
  const fromMost = (won: Record<string, number>) => Object.entries(won).sort((a, b) => b[1] - a[1]);
  const [winners, winnersBefore] = [fromMost(counts.winners.now), fromMost(counts.winners.then)];
  const [weakest, strongest] = [data.fifths[0], data.fifths[data.fifths.length - 1]];

  // Neighbourhoods and housing
  const group = (key: string) => groups.find((item) => item.key === key);
  const barrandov = group("barrandov");
  const senGrewMostOnBarrandov = [...groups].sort((a, b) => change(b, "sen") - change(a, "sen"))[0]?.key === "barrandov";
  const byShare = (key: string) => [...groups].sort((a, b) => (b.local[key] ?? 0) - (a.local[key] ?? 0));
  const others = groups.filter((item) => item.key !== "barrandov");
  /** The Pirates' share for the council of Praha 5 in the previous election, in percent of their share for Parliament */
  const localOverParliament = (area: Area) => ((area.previousLocal.pirati ?? 0) / (area.parliamentary.pirati ?? 1)) * 100;
  const kind = (key: string) => data.kinds.find((item) => item.kind === key);
  const [panel, newer] = [kind("panel"), kind("newer")];
  /** Kind of housing in which a list has its best result */
  const strongestIn = (key: string) => [...data.kinds].sort((a, b) => (b.local[key] ?? 0) - (a.local[key] ?? 0))[0]?.kind;
  const registeredIn = (rows: Precinct[]) => rows.reduce((sum, precinct) => sum + precinct.registered, 0);
  const newerPrecincts = precincts.filter((precinct) => precinct.kind === "newer");
  const newerOnBarrandov =
    (registeredIn(newerPrecincts.filter((precinct) => precinct.group === "barrandov")) / registeredIn(newerPrecincts)) * 100;

  // Voters in three elections
  const voters = (share: number | null | undefined, when: "then" | "now") =>
    share != null ? (share / 100) * district.ballots[when] : null;
  const inElections = (key: string, mid: number | null) => ({
    key,
    values: [voters(district.previousLocal[key], "then"), mid, voters(district.local[key], "now")],
  });
  const electionRows = [
    inElections("praha5Sobe", null),
    {
      key: "odsTopKdu",
      values: [voters(right(district, true), "then"), data.parliamentaryVotes.spolu, voters(right(district), "now")],
    },
    inElections("stan", data.parliamentaryVotes.stan),
    inElections("sen", null),
    inElections("ano", data.parliamentaryVotes.ano),
    inElections("pirati", data.parliamentaryVotes.pirati),
  ];
  const piratiVotes = data.parliamentaryVotes.pirati;
  const piratiCity = voters(district.city.pirati, "now") ?? 0;
  const coalitionVoters = voters(coalition.share.now, "now") ?? 0;
  const turnoutDrop = (1 - district.ballots.now / district.ballots.mid) * 100;

  const describe = (item: BlocScenario): { title: string; detail?: string } => {
    const share = item.voters ? `${fmtPct(ofVoters(item))} těch, kdo přišli volit` : undefined;
    switch (item.key) {
      case "actual":
        return { title: "Skutečný výsledek" };
      case "pirati-one-more":
        return { title: `${fmtInt(item.voters ?? 0)} voličů navíc pro Piráty`, detail: "mandát by vzali kandidátce SEN" };
      case "joint-two":
        return { title: "Společná kandidátka Prahy 5 Sobě a Pirátů", detail: "prostý součet jejich hlasů" };
      case "joint-three":
        return { title: "Společná kandidátka Prahy 5 Sobě, Pirátů a SEN", detail: "prostý součet jejich hlasů" };
      case "stan-to-pirati":
        return { title: `${tens(item.voters ?? 0)} voličů STAN volí Piráty`, detail: share };
      default:
        return { title: `${tens(item.voters ?? 0)} nových voličů Pirátů`, detail: share };
    }
  };

  const seatRow = (previous: boolean) => ({
    year: previous ? years.previous : years.current,
    groups: BLOCS.map((item) => ({
      label: item.name,
      parts: item.lists.map((key) => ({
        key,
        seats: previous ? (previousList(key)?.seats ?? 0) : (data.lists.find((entry) => entry.key === key)?.seats ?? 0),
      })),
    })),
  });

  const shareColumns = <Row extends Area>(): HeatColumn<Row>[] =>
    ["praha5Sobe", "ods", "stan", "sen", "ano", "pirati"].map((key) => ({
      group: `Podíl hlasů ${years.current}`,
      head: label(key),
      value: (row: Row) => row.local[key] ?? 0,
      format: pct,
      tint: colorOf(key),
    }));
  const areaColumns = <Row extends Area>(): HeatColumn<Row>[] => [
    { head: "Zapsaní voliči", value: (row) => row.registered, format: fmtInt },
    { head: `Účast ${years.current}`, value: (row) => row.turnout.now ?? 0, format: pct },
    ...shareColumns<Row>(),
    { group: "Piráti", head: years.previous, value: (row) => row.previousLocal.pirati ?? 0, format: pct, tint: colorOf("pirati") },
    { group: "Piráti", head: "změna", value: (row) => change(row, "pirati"), format: bare, tint: "change" },
    {
      group: "Piráti",
      head: `Sněmovna ${years.parliamentary}`,
      value: (row) => row.parliamentary.pirati ?? 0,
      format: pct,
      tint: colorOf("pirati"),
    },
  ];
  const fifthColumns: HeatColumn<Area>[] = [
    { group: "Piráti", head: years.previous, value: (row) => row.previousLocal.pirati ?? 0, format: pct, tint: colorOf("pirati") },
    { group: "Piráti", head: years.current, value: (row) => row.local.pirati ?? 0, format: pct, tint: colorOf("pirati") },
    { group: "Piráti", head: "změna", value: (row) => change(row, "pirati"), format: bare, tint: "change" },
    ...["praha5Sobe", "sen", "stan", "ano"].map(
      (key): HeatColumn<Area> => ({
        group: "Změna ostatních",
        head: label(key),
        value: (row) => change(row, key),
        format: bare,
        tint: "change",
      }),
    ),
    {
      group: "Změna ostatních",
      head: "ODS, TOP 09 a KDU-ČSL",
      value: (row) => right(row) - right(row, true),
      format: bare,
      tint: "change",
    },
  ];

  return (
    <>
      <div className="tiles article-tiles">
        <div className="tile">
          <div className="value num">
            {pirati.seats} z {seats}
          </div>
          <div className="label">
            {seatsWord(pirati.seats)} mají Piráti, v roce {years.previous} jich bylo {pirati.previousSeats}
          </div>
        </div>
        <div className="tile">
          <div className="value num">{townHall.seats.now}</div>
          <div className="label">
            mandátů mají ODS, TOP 09, STAN a ANO, které radnici vedou od prosince 2024; k většině stačí {majority}
          </div>
        </div>
        {nextPirati && (
          <div className="tile">
            <div className="value num">{fmtInt(nextPirati.missingVoters)}</div>
            <div className="label">voličů chybělo Pirátům, aby získali {ordinal(nextPirati.seat)} mandát</div>
          </div>
        )}
        <div className="tile">
          <div className="value num">
            {fmtNum(ballot("pirati").local)} a {fmtPct(ballot("pirati").city ?? 0)}
          </div>
          <div className="label">dostali Piráti od stejných voličů do zastupitelstva Prahy 5 a do pražského</div>
        </div>
      </div>

      <section className="prose">
        <h2>Shrnutí</h2>
        <p>
          Piráti mají v zastupitelstvu páté městské části {pirati.seats} {seatsWord(pirati.seats)} místo{" "}
          {pirati.previousSeats}.
          Jejich podíl klesl z {fmtNum(pirati.previousShare ?? 0)} na {fmtPct(pirati.share)}. Horší výsledek než
          před čtyřmi lety mají {inCount(fell)} z {precincts.length} okrsků
          {barrandov && <>, nejvíc ztratili na Barrandově, kde byli nejsilnější</>}.
        </p>
        <p>
          Praha 5 Sobě, Piráti a SEN, které po volbách {years.previous} složily radu s nejtěsnější většinou, mají
          dohromady {coalition.seats.now} mandátů místo {coalition.seats.then}. ODS, TOP 09, STAN a ANO, které
          radnici vedou od prosince 2024, jich mají {townHall.seats.now} a většinu by složily samy.
        </p>
        {nextSobe && nextPirati && (
          <p>
            Poslední mandát připadl kandidátce {label(data.lastSeat.key)}. Praze 5 Sobě k němu chybělo asi{" "}
            {fmtInt(nextSobe.missingVoters)} voličů a Pirátům {fmtInt(nextPirati.missingVoters)}. Poměr sil by to
            nezměnilo, mandát by ztratil {label(data.lastSeat.key)}.
          </p>
        )}
        <p>
          STAN dostal do místního zastupitelstva {fmtPct(ballot("stan").local)} hlasů, do pražského od stejných voličů{" "}
          {fmtPct(ballot("stan").city ?? 0)}. Rozdíl si místně rozdělily hlavně ODS s TOP 09, SEN a Naše Praha 5.
        </p>
      </section>

      <section className="prose">
        <h2>Výsledek a dva tábory</h2>
        <p>
          Po volbách v roce {years.previous} vedla radnici koalice Prahy 5 Sobě, Pirátů a SEN 21, která měla{" "}
          {coalition.seats.then} hlasů ze {seats}. V prosinci 2024 zastupitelé radu odvolali a novou zvolily ODS, TOP
          09, ANO a STAN. Graf řadí mandáty podle těchto dvou táborů.
        </p>
      </section>

      <Figure title="Mandáty podle táborů" sub={`Zastupitelstvo městské části Praha 5, ${seats} mandátů`}>
        <CampSeats rows={[seatRow(true), seatRow(false)]} seats={seats} majority={majority} colorOf={colorOf} />
      </Figure>

      <Figure
        title="Výsledky kandidátek"
        sub="Podíl ze všech platných hlasů; kandidátky, které dostaly aspoň 2 %"
        note={`ODS a TOP 09 kandidovaly v roce ${years.previous} společně (${fmtPct(previousList("odsTop")?.share ?? 0)} a ${previousList("odsTop")?.seats} mandátů), KDU-ČSL tehdy se Zelenými (${fmtPct(previousList("kduZeleni")?.share ?? 0)}, bez mandátu). Letos šla ODS sama a TOP 09 s KDU-ČSL. SEN je kandidátka s podporou senátora Václava Lásky, v roce ${years.previous} pod názvem Koalice SEN 21 pro Prahu 5.`}
      >
        <ResultsTable
          lists={data.lists}
          years={years}
          colorOf={colorOf}
          withoutPrevious={{ ods: "jiná sestava", top: "jiná sestava" }}
        />
      </Figure>

      <section className="prose">
        <p>
          Piráti ztratili {(pirati.previousSeats ?? 0) - pirati.seats} {seatsWord((pirati.previousSeats ?? 0) - pirati.seats)}{" "}
          a ANO {(ano.previousSeats ?? 0) - ano.seats}. STAN jich má {stan.seats} místo {stan.previousSeats} a SEN{" "}
          {sen.seats} místo {sen.previousSeats}. Praha 5 Sobě drží {praha5Sobe.seats}, stejně jako ODS s TOP 09
          a lidovci dohromady ({ods.seats} + {top.seats}).
        </p>
        <p>
          Na kandidátky, které se do zastupitelstva nedostaly, připadlo {fmtPct(data.withoutSeats)} hlasů.
        </p>
      </section>

      <section className="prose">
        <h2>Poslední mandát</h2>
        <p>
          Poslední, {seats}. mandát připadl kandidátce {label(data.lastSeat.key)} jako její {ordinal(data.lastSeat.seat)}.
          Těsně za ním skončily tři další:
          {nextSobe && (
            <>
              {" "}
              {ordinal(nextSobe.seat)} mandát Prahy 5 Sobě (chybělo {fmtInt(nextSobe.missingVotes)} hlasů, tedy asi{" "}
              {fmtInt(nextSobe.missingVoters)} voličů),
            </>
          )}
          {nextPirati && (
            <>
              {" "}
              {ordinal(nextPirati.seat)} mandát Pirátů ({fmtInt(nextPirati.missingVotes)} hlasů, asi{" "}
              {fmtInt(nextPirati.missingVoters)} voličů)
            </>
          )}
          {nextTop && (
            <>
              {" "}
              a {ordinal(nextTop.seat)} mandát TOP 09 s lidovci (asi {fmtInt(nextTop.missingVoters)} voličů)
            </>
          )}
          .
        </p>
        <p>
          V prvních dvou případech by se mandát jen přesunul uvnitř jednoho tábora
          {nextTop && lastSeatInCoalition && (
            <>
              , třetí by poměr posunul na {coalition.seats.now - 1} : {townHall.seats.now + 1}
            </>
          )}
          . Poměr {coalition.seats.now} : {townHall.seats.now} by nezměnila ani společná kandidátka Prahy 5 Sobě
          a Pirátů.
        </p>
      </section>

      <Figure
        title="Co by změnilo poměr sil"
        sub="Přepočet mandátů podle stejných pravidel; všechno, co řádek nezmiňuje, zůstává jako ve skutečnosti"
      >
        <BlocScenarios scenarios={data.scenarios} majority={majority} describe={describe} />
      </Figure>

      {newPirati && fromStan && (
        <section className="prose">
          <p>
            Většinu ODS, TOP 09, STAN a ANO by ukončily až dva mandáty navíc pro druhý tábor: asi{" "}
            {tens(newPirati.voters ?? 0)} nových voličů Pirátů, tedy {fmtPct(ofVoters(newPirati))} těch, kdo přišli,
            nebo asi {tens(fromStan.voters ?? 0)} lidí, kteří by místo STAN volili Piráty.
            {jointThree && (
              <>
                {" "}
                Společná kandidátka všech tří by přidala{" "}
                {jointThree.blocs.coalition2022 - coalition.seats.now === 1
                  ? "jeden mandát"
                  : `${jointThree.blocs.coalition2022 - coalition.seats.now} mandáty`}
                .
              </>
            )}
          </p>
        </section>
      )}

      <section className="prose">
        <h2>Dva lístky, stejní voliči</h2>
        <p>
          Každý volič dostal dva hlasovací lístky: do zastupitelstva Prahy 5 a do zastupitelstva hlavního města. Ve
          všech {precincts.length} okrscích tak jde srovnat, jak titíž lidé hlasovali o radnici a o magistrátu.
        </p>
      </section>

      <Figure
        title="Podíl hlasů na obou lístcích"
        sub={`Podíl hlasů v Praze 5 v roce ${years.current}. Rozdíl říká, o kolik víc dostala kandidátka do zastupitelstva Prahy 5 než do pražského.`}
        note={`Rozdíl ve voličích je rozdíl podílů krát počet odevzdaných obálek. V roce ${years.previous} SEN do pražského zastupitelstva nekandidoval a ODS s TOP 09 a KDU-ČSL šly do obou voleb v jiných sestavách, proto u nich srovnání chybí.`}
      >
        <TwoBallots rows={ballots} ballots={data.summary.ballots} years={years} colorOf={colorOf} />
      </Figure>

      <section className="prose">
        <p>
          Piráti dostali do zastupitelstva Prahy 5 o {fmtNum(Math.abs(gap("pirati")))} bodu méně než do pražského,
          v přepočtu asi o {tens(inVoters(gap("pirati")))} voličů. Místně měli méně{" "}
          {inCount(counts.lowerLocally.pirati)} z {precincts.length} okrsků. Před čtyřmi lety byl rozdíl {fmtNum(Math.abs(ballot("pirati").previousGap ?? 0))}{" "}
          bodu; tehdy na pražském lístku chyběl SEN, který v Praze 5 dostal{" "}
          {fmtPct(district.previousLocal.sen ?? 0)}.
        </p>
        <p>
          Letos SEN kandidoval do obou zastupitelstev. V Praze 5 dostal na pražském lístku{" "}
          {fmtPct(district.city.sen ?? 0)}, v celé Praze {fmtPct(data.cityWide.now.sen ?? 0)}. Piráti tu na stejném
          lístku klesli z {fmtNum(district.previousCity.pirati ?? 0)} na {fmtPct(district.city.pirati ?? 0)}.
        </p>
        <p>
          Největší rozdíl mezi lístky má STAN: do pražského zastupitelstva ho volilo asi o{" "}
          {tens(inVoters(gap("stan")))} lidí víc než do zastupitelstva Prahy 5. Místně méně dostal{" "}
          {inCount(counts.lowerLocally.stan)} z {precincts.length} okrsků. Víc než na pražském lístku naopak místně mají
          ODS s TOP 09 a lidovci ({points(gap("ods"))} proti Spolu), SEN ({points(gap("sen"))}) a Naše Praha 5, která
          do pražského zastupitelstva nekandidovala ({fmtPct(ballot("nasePraha5").local)}).
        </p>
        <p>Jsou to rozdíly součtů. Říkají, kolik hlasů kde přebývá a chybí, ne kdo je komu dal.</p>
      </section>

      <section className="prose">
        <h2>Okrsky</h2>
        <p>
          {winners.map(([key, precinctsWon], index) => (
            <span key={key}>
              {index === 0
                ? `${label(key)} má nejvíc hlasů ${inCount(precinctsWon)} z ${precincts.length} okrsků`
                : `${index === winners.length - 1 ? " a " : ", "}${label(key)} ${inCount(precinctsWon)}`}
            </span>
          ))}
          . V roce {years.previous} vedla{" "}
          {winnersBefore
            .slice(0, 2)
            .map(([key, precinctsWon]) => `${key === "odsTop" ? "společná kandidátka ODS a TOP 09" : label(key)} ${inCount(precinctsWon)}`)
            .join(" a ")}
          ; letos se hlasy ODS a TOP 09 dělí mezi dvě kandidátky.
        </p>
        <p>
          Praha 5 Sobě, Piráti a SEN mají dohromady víc hlasů než ODS, TOP 09, STAN a ANO{" "}
          {inCount(counts.coalitionAhead.now)} okrscích, před čtyřmi lety {inCount(counts.coalitionAhead.then)}.
        </p>
      </section>

      <Figure
        title="Okrsky na mapě"
        sub="Vyberte, co má mapa ukazovat. Najetím na okrsek uvidíte jeho údaje, kliknutím ho otevřete v mapě výsledků."
      >
        <Suspense fallback={<Loading text="Načítám mapu…" />}>
          <Prague5Map data={data} colorOf={colorOf} />
        </Suspense>
      </Figure>

      <section className="prose">
        <h2>Kde Piráti ztráceli</h2>
        <p>
          Podíl Pirátů klesl {inCount(fell)} z {precincts.length} okrsků, nejvíc tam, kde byli v roce {years.previous}{" "}
          nejsilnější.
        </p>
      </section>

      <Figure
        title={`Okrsky podle toho, jak silní v nich byli Piráti v roce ${years.previous}`}
        sub={`V každé pětině je asi ${weakest.precincts} okrsků. Podíly v procentech, změny v procentních bodech; modrá znamená zisk a červená ztrátu.`}
        note={`V roce ${years.previous} jsou u ODS, TOP 09 a KDU-ČSL sečtené jejich dvě tehdejší kandidátky, i když na jedné z nich byli také Zelení.`}
      >
        <HeatTable rows={data.fifths} rowHead="Okrsky" rowLabel={(row) => FIFTHS[data.fifths.indexOf(row)]} columns={fifthColumns} />
      </Figure>

      <section className="prose">
        <p>
          V nejslabší pětině Piráti ztratili {fmtNum(Math.abs(change(weakest, "pirati")))} bodu, v nejsilnější{" "}
          {fmtNum(Math.abs(change(strongest, "pirati")))}. STAN přitom přidal všude zhruba stejně, od{" "}
          {fmtNum(Math.min(...data.fifths.map((fifth) => change(fifth, "stan"))))} do{" "}
          {fmtNum(Math.max(...data.fifths.map((fifth) => change(fifth, "stan"))))} bodu, a posílil{" "}
          {counts.rose.stan === counts.compared
            ? `ve všech ${counts.compared} okrscích`
            : `${inCount(counts.rose.stan)} z ${counts.compared} okrsků`}
          .
          V někdejších pirátských baštách navíc rostly Praha 5 Sobě ({points(change(strongest, "praha5Sobe"))}) a SEN (
          {points(change(strongest, "sen"))}).
        </p>
      </section>

      <Figure
        title={`Piráti v okrscích v letech ${years.previous} a ${years.current}`}
        sub="Každá tečka je okrsek, velikost odpovídá počtu voličů. Pod úhlopříčkou jsou okrsky, kde Piráti ztratili. Kliknutím okrsek otevřete v mapě výsledků."
      >
        <Scatter
          points={precincts
            .filter((precinct) => precinct.previousLocal.pirati != null && precinct.local.pirati != null)
            .map((precinct) => ({
              id: precinct.id,
              label: `Okrsek ${precinct.id}${precinct.part ? ` · ${precinct.part}` : ""}`,
              previous: precinct.previousLocal.pirati ?? 0,
              current: precinct.local.pirati ?? 0,
              size: precinct.registered,
            }))}
          previousYear={years.previous}
          currentYear={years.current}
          selected={null}
          onSelect={(id) => navigate(`${councilPath}/mapa?okrsek=${id}`)}
          color={colorOf("pirati")}
        />
      </Figure>

      <section className="prose">
        <h2>Čtvrti</h2>
        <p>
          Okrsky jsou tu spojené do {groups.length === 4 ? "čtyř" : groups.length} celků podle částí obce. Barrandov,
          který patří k Hlubočepům, je vedený zvlášť.
        </p>
      </section>

      <Figure
        title="Čtvrti Prahy 5"
        sub="Volby do zastupitelstva Prahy 5. Podíly v procentech hlasů, změna v procentních bodech."
        note={
          data.unusual.length > 0
            ? `Účast je bez okrsku ${data.unusual.map((precinct) => precinct.id).join(", ")}, kde je zapsáno ${fmtInt(data.unusual[0].registered)} voličů a přišlo jich ${fmtPct(data.unusual[0].turnout)}. S ním vychází účast celé Prahy 5 na ${fmtPct(data.summary.turnout)}.`
            : undefined
        }
      >
        <HeatTable rows={groups} rowHead="Čtvrť" rowLabel={(row) => row.name} columns={areaColumns<(typeof groups)[number]>()} />
      </Figure>

      {barrandov && (
        <section className="prose">
          <p>
            Na Barrandově měli Piráti v roce {years.previous} {fmtPct(barrandov.previousLocal.pirati ?? 0)}, nejvíc
            z celé Prahy 5, a letos {fmtPct(barrandov.local.pirati ?? 0)}. Nejvíc hlasů tam má{" "}
            {label(winner(barrandov))} ({fmtPct(barrandov.local[winner(barrandov)] ?? 0)})
            {byShare("ano")[0].key === "barrandov" && (
              <> a ANO tam má {fmtPct(barrandov.local.ano ?? 0)}, víc než v ostatních celcích</>
            )}
            .
          </p>
          <p>
            Barrandovský výsledek z roku {years.previous} se přitom vymykal. Piráti tam tehdy do zastupitelstva Prahy
            5 dostali skoro stejný podíl hlasů jako loni do Sněmovny ({fmtNum(barrandov.previousLocal.pirati ?? 0)}{" "}
            a {fmtPct(barrandov.parliamentary.pirati ?? 0)}). Jinde měli místně jen{" "}
            {fmtNum(Math.min(...others.map(localOverParliament)), 0)} až{" "}
            {fmtPct(Math.max(...others.map(localOverParliament)), 0)} svého sněmovního podílu.
          </p>
          <p>
            Praha 5 Sobě má nejvíc hlasů v celku {byShare("praha5Sobe")[0].name} (
            {fmtPct(byShare("praha5Sobe")[0].local.praha5Sobe ?? 0)}) a nejméně v celku{" "}
            {byShare("praha5Sobe")[groups.length - 1].name} (
            {fmtPct(byShare("praha5Sobe")[groups.length - 1].local.praha5Sobe ?? 0)}). ODS a STAN mají všude podobně.
          </p>
        </section>
      )}

      {data.kinds.length > 0 && (
        <>
          <Figure
            title="Okrsky podle převažující zástavby"
            sub={`Okrsek patří k tomu druhu zástavby, ve kterém je aspoň polovina jeho bytů.${data.unusual.length > 0 ? ` Účast je opět bez okrsku ${data.unusual.map((precinct) => precinct.id).join(", ")}.` : ""}`}
          >
            <HeatTable
              rows={data.kinds}
              rowHead="Zástavba"
              rowLabel={(row) => KIND_NAMES[row.kind] ?? row.kind}
              columns={areaColumns<(typeof data.kinds)[number]>()}
            />
          </Figure>
          {panel && newer && (
            <section className="prose">
              <p>
                {["sen", "ano"].every((key) => strongestIn(key) === "panel") && (
                  <>
                    V okrscích panelových domů mají SEN ({fmtPct(panel.local.sen ?? 0)}) a ANO (
                    {fmtPct(panel.local.ano ?? 0)}) víc než v jiné zástavbě.{" "}
                  </>
                )}
                Nejvíc Piráti ztratili v novějších bytových domech, z{" "}
                {fmtNum(newer.previousLocal.pirati ?? 0)} na {fmtPct(newer.local.pirati ?? 0)};{" "}
                {fmtPct(newerOnBarrandov, 0)} voličů z těchto okrsků bydlí na Barrandově.
              </p>
            </section>
          )}
        </>
      )}

      <section className="card">
        <details className="more">
          <summary>Všech {precincts.length} okrsků v tabulce</summary>
          <div className="more-body">
            <p className="note" style={{ marginBottom: 12 }}>
              Kliknutím na záhlaví sloupce tabulku seřadíte, číslo okrsku ho otevře v mapě výsledků.
            </p>
            <PrecinctList precincts={precincts} years={years} mapPath={`${councilPath}/mapa`} />
          </div>
        </details>
      </section>

      <section className="prose">
        <h2>Proti sněmovním volbám</h2>
        <p>
          Do Sněmovny loni v Praze 5 volilo Piráty {hundreds(piratiVotes)} lidí ({fmtPct(district.parliamentary.pirati ?? 0)}).
          Letos jim do zastupitelstva Prahy 5 dalo hlas asi {hundreds(pirati.voters)} voličů a do pražského{" "}
          {hundreds(piratiCity)}. K volbám ovšem přišlo o {fmtPct(turnoutDrop, 0)} méně lidí.
        </p>
      </section>

      <Figure
        title="Kolik lidí volilo kterou kandidátku"
        sub={`Volby do zastupitelstva Prahy 5 v letech ${years.previous} a ${years.current} a sněmovní volby ${years.parliamentary} ve stejných okrscích`}
        note={`Hlasy v komunálních volbách jsou přepočtené na voliče. V roce ${years.previous} jsou u ODS, TOP 09 a KDU-ČSL sečtené jejich dvě tehdejší kandidátky, i když na jedné z nich byli také Zelení.`}
      >
        <ElectionBars
          rows={electionRows}
          elections={[`Praha 5, ${years.previous}`, `Sněmovna ${years.parliamentary}`, `Praha 5, ${years.current}`]}
          colorOf={colorOf}
          format={hundreds}
        />
      </Figure>

      <section className="prose">
        <p>
          Praha 5 Sobě, Piráti a SEN mají dohromady asi {hundreds(coalitionVoters)} voličů, o{" "}
          {fmtPct((coalitionVoters / piratiVotes - 1) * 100, 0)} víc, než kolik bylo loni sněmovních voličů Pirátů.
          Koho loni volili dnešní voliči Prahy 5 Sobě a SEN, se z těchto čísel nepozná.
        </p>
      </section>

      <section className="prose">
        <h2>Co z toho plyne</h2>
        <p>
          Místní ztráta Pirátů je menší než jejich ztráta na pražském lístku: v Praze 5 klesli do místního
          zastupitelstva z {fmtNum(pirati.previousShare ?? 0)} na {fmtPct(pirati.share)}, do pražského z{" "}
          {fmtNum(district.previousCity.pirati ?? 0)} na {fmtPct(district.city.pirati ?? 0)}. Místně ale už před
          čtyřmi lety dostávali výrazně méně než na pražském lístku.
        </p>
        {nextPirati && newPirati && (
          <p>
            Čtvrtý mandát Pirátům unikl o {fmtInt(nextPirati.missingVoters)} voličů, poměr sil v zastupitelstvu by ale
            změnilo až asi {tens(newPirati.voters ?? 0)} voličů navíc.
          </p>
        )}
        {barrandov && (
          <p>
            Největší ztráty jsou na Barrandově, kde žije {fmtPct((barrandov.registered / district.registered) * 100, 0)}{" "}
            voličů Prahy 5{senGrewMostOnBarrandov && " a kde letos nejvíc posílil SEN"}.
          </p>
        )}
        <p>
          STAN má v Praze 5 na místním lístku o {fmtPct((1 - ballot("stan").local / (ballot("stan").city ?? 1)) * 100, 0)}{" "}
          méně hlasů než na pražském. Nejméně tolik jeho pražských voličů volí do zastupitelstva Prahy 5 někoho
          jiného.
        </p>
        <p>Proč voliči hlasovali na obou lístcích různě a proč Piráty opouštěli, z výsledků vyčíst nejde.</p>
      </section>

      <section className="card method-notes">
        <h3>Jak se to počítalo</h3>
        <p className="note">
          Mandáty jsou přepočítané d&apos;Hondtovou metodou s pětiprocentní klauzulí a scénáře mění jen uvedené
          hlasy. Volič má v Praze 5 až {seats} hlasů; počty voličů jsou přepočtené z hlasů průměrem{" "}
          {fmtNum(data.votesPerBallot)} platného hlasu na odevzdanou obálku.
        </p>
        <p className="note">
          Čtvrti jsou části obce z registru adres (RÚIAN): okrsek patří tam, kde má nejvíc adres. Barrandov částí
          obce není, jsou to okrsky Hlubočep na barrandovské plošině. Zástavba je z registru budov stejně jako
          v analýze{" "}
          <Link className="inline-link" to="/analyzy/praha-2026-centrum-sidliste-predmesti">
            Centrum, sídliště a předměstí
          </Link>
          ; rodinných domů je v Praze 5 málo, proto jsou sloučené se smíšenou zástavbou.
        </p>
        {data.unusual.length > 0 && (
          <p className="note">
            Do okrsku {data.unusual[0].id} patří adresa radnice, kde jsou úředně hlášení lidé bez jiného trvalého
            pobytu. Má proto {fmtInt(data.unusual[0].registered)} zapsaných voličů a účast{" "}
            {fmtPct(data.unusual[0].turnout)}. Do účasti čtvrtí a zástavby se nepočítá, do podílů hlasů ano.
          </p>
        )}
        <p className="note">
          Odhad přesunů voličů mezi kandidátkami tu chybí: z {precincts.length} okrsků vychází jen hrubě a sestavy
          kandidátek se od roku {years.previous} změnily.{" "}
          <Link className="inline-link" to={`${councilPath}/presuny`}>
            Hrubý odhad je na stránce Prahy 5
          </Link>
        </p>
      </section>
    </>
  );
}
