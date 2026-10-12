import { useState } from "react";
import { Link } from "react-router-dom";
import { downloadCsv, fmtInt, fmtNum, fmtPct, plural } from "../format";
import { bare, label } from "./blocks";
import { type Area, change, localOverCity, type Precinct } from "./districtShared";

const ORDINALS = ["první", "druhý", "třetí", "čtvrtý", "pátý", "šestý", "sedmý", "osmý", "devátý", "desátý", "jedenáctý", "dvanáctý"];
export const ordinal = (count: number) => ORDINALS[count - 1] ?? `${count}.`;

/** 959 → "960" */
export const tens = (people: number) => fmtInt(Math.round(people / 10) * 10);
export const pct = (value: number) => fmtNum(value);
export const seatsWord = (count: number) => plural(count, "mandát", "mandáty", "mandátů");

/** "v 73", "ve 14": the preposition follows how the number is read */
export function inCount(count: number): string {
  const first = count < 20 ? count : Math.floor(count / 10) * 10;
  return `${[2, 3, 4, 12, 13, 14, 20, 30, 40].includes(first) ? "ve" : "v"} ${fmtInt(count)}`;
}

/** The same list, or its closest counterpart, on the ballot of the district and on that of the city */
export interface BallotPair {
  key: string;
  name: string;
  /** Name on the ballot of the city, where it differs */
  cityName?: string;
  local: string[];
  city: string[];
  /** Keys of the two lists in the previous election, where they can be compared */
  previous?: [string, string];
}

export interface BallotRow {
  key: string;
  name: string;
  cityName?: string;
  local: number;
  city: number | null;
  previousGap: number | null;
}

export function ballotRows(district: Area, pairs: BallotPair[]): BallotRow[] {
  const total = (shares: Record<string, number | null>, keys: string[]) =>
    keys.reduce((sum, key) => sum + (shares[key] ?? 0), 0);
  return pairs.map((pair) => ({
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
export function TwoBallots({ rows, ballots, years, colorOf }: TwoBallotsProps) {
  const top = Math.max(...rows.flatMap((row) => [row.local, row.city ?? 0])) * 1.04;
  const at = (value: number) => `${(value / top) * 100}%`;
  return (
    <>
      <div className="ballot-key">
        <span>
          <span className="mark" /> do zastupitelstva městské části
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
              <th className="col">Do městské části</th>
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

interface Column {
  key: string;
  head: string;
  value: (precinct: Precinct) => number | string | null;
  format?: (value: number) => string;
}

/** Every precinct with the numbers the article works with; a click on a heading sorts by it. */
interface PrecinctListProps {
  precincts: Precinct[];
  years: { current: string; previous: string };
  /** Address of the map of the council's results */
  mapPath: string;
  /** Lists with a column of their own, besides the Pirates */
  lists: string[];
  /** Name of the downloaded file */
  fileName: string;
}

export function PrecinctList({ precincts, years, mapPath, lists, fileName }: PrecinctListProps) {
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
    ...lists.map((key) => ({ key, head: label(key), value: share(key), format: pct })),
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
          downloadCsv(fileName, [
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

