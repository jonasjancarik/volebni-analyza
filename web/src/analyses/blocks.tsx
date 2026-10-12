import { useState } from "react";
import { NON_VOTER, REST, listColors } from "../colors";
import { fmtCompact, fmtInt, fmtNum, fmtPct, fmtPp, fmtRange, plural } from "../format";
import type { District, FollowedList, KeyedFlows, PrecinctFifth, Scenario } from "./types";

const LABELS: Record<string, string> = {
  stan: "STAN",
  spolu: "Spolu",
  prahaSobe: "Praha Sobě",
  ano: "ANO",
  pirati: "Piráti",
  spd: "SPD",
  motoriste: "Motoristé",
  sen: "SEN",
  praha5Sobe: "Praha 5 Sobě",
  ods: "ODS",
  top: "TOP 09 a lidovci",
  odsTop: "ODS a TOP 09",
  odsTopKdu: "ODS, TOP 09 a KDU-ČSL",
  kduZeleni: "KDU-ČSL a Zelení",
  nasePraha5: "Naše Praha 5",
  ostatni: "Ostatní kandidátky",
  nevolici: "Nevolili",
};

export const label = (key: string) => LABELS[key] ?? key;

/** The colours the lists have on the council's own pages */
export function groupColors(lists: FollowedList[]): (key: string) => string {
  const byName = listColors(lists.map((list) => list.name));
  const byKey = new Map(lists.map((list) => [list.key, byName.get(list.name) ?? REST]));
  return (key) => (key === "nevolici" ? NON_VOTER : (byKey.get(key) ?? REST));
}

/** 21 400 → "21 tisíc" */
export function thousands(people: number): string {
  const count = Math.round(people / 1000);
  return `${fmtInt(count)} ${plural(count, "tisíc", "tisíce", "tisíc")}`;
}

/** 6 557 → "6 600" */
export const hundreds = (people: number) => fmtInt(Math.round(people / 100) * 100);

/** "+5,4 bodu" */
export const points = (value: number) => fmtPp(value).replace(/p\.\s*b\.$/, "bodu");

/** One flow of an estimate: what share of the source group it is, of the target group, and how many people */
export function cell(flows: KeyedFlows, source: string, target: string) {
  const row = flows.sources.indexOf(source);
  const column = flows.targets.indexOf(target);
  return {
    share: flows.transitions[row][column],
    low: flows.transitionsLow[row][column],
    high: flows.transitionsHigh[row][column],
    origin: flows.origin[row][column],
    originLow: flows.originLow[row][column],
    originHigh: flows.originHigh[row][column],
    people: (flows.electorate[row][column] / 100) * flows.previousRegistered,
  };
}

const GAIN = "#2a78d6";
const LOSS = "#e34948";

/**
 * Cell background: the stronger the value, the more of the colour. Only the
 * dark colours of gains and losses can carry white text when strong; the
 * lists' own colours are too light for it.
 */
function tint(color: string, strength: number, whenStrong = "var(--ink)"): React.CSSProperties {
  const share = Math.max(0, Math.min(1, strength));
  return {
    background: `color-mix(in srgb, ${color} ${Math.round(share * 80)}%, var(--surface-2))`,
    color: share > 0.8 ? whenStrong : "var(--ink)",
  };
}

const changeTint = (value: number, reach: number) =>
  tint(value >= 0 ? GAIN : LOSS, Math.abs(value) / reach, "#fff");

/** "+5,4": the unit is in the column heading */
export const bare = (value: number) => fmtPp(value).replace(/\s*p\.\s*b\.$/, "");

interface FigureProps {
  title: string;
  sub?: React.ReactNode;
  note?: React.ReactNode;
  children: React.ReactNode;
}

export function Figure({ title, sub, note, children }: FigureProps) {
  return (
    <figure className="card figure">
      <figcaption className="card-head">
        <div>
          <h3>{title}</h3>
          {sub && <div className="card-sub">{sub}</div>}
        </div>
      </figcaption>
      {children}
      {note && (
        <p className="note" style={{ marginTop: 14 }}>
          {note}
        </p>
      )}
    </figure>
  );
}

export interface Part {
  key: string;
  value: number;
  low?: number;
  high?: number;
  people?: number;
}

interface SplitBarProps {
  parts: Part[];
  colorOf: (key: string) => string;
  /** Heading of the column with the number of people */
  peopleLabel?: string;
}

/** One group of voters split by where they went or came from: a bar of the whole and a row for each part. */
export function SplitBar({ parts, colorOf, peopleLabel }: SplitBarProps) {
  const last = (key: string) => (key === "nevolici" ? 2 : key === "ostatni" ? 1 : 0);
  const shown = parts
    .filter((part) => part.value >= 0.5 || (part.high ?? 0) >= 3)
    .sort((a, b) => last(a.key) - last(b.key) || b.value - a.value);
  const total = shown.reduce((sum, part) => sum + part.value, 0) || 1;
  const hasRange = shown.some((part) => part.low != null);
  const hasPeople = shown.some((part) => part.people != null);
  return (
    <div>
      <div className="split-bar" aria-hidden>
        {shown.map((part) => (
          <span
            key={part.key}
            className={part.key === "nevolici" ? "on-light" : undefined}
            style={{ width: `${(part.value / total) * 100}%`, background: colorOf(part.key) }}
            title={`${label(part.key)}: ${fmtPct(part.value)}`}
          >
            {part.value / total >= 0.09 && fmtPct(part.value, 0)}
          </span>
        ))}
      </div>
      <div className="split-rows num">
        {shown.map((part) => (
          <div
            className="split-row"
            key={part.key}
            style={{ gridTemplateColumns: `minmax(0, 1fr) 58px${hasRange ? " 74px" : ""}${hasPeople ? " 128px" : ""}` }}
          >
            <span className="split-name">
              <span className="swatch" style={{ background: colorOf(part.key) }} />
              {label(part.key)}
            </span>
            <span className="share">{fmtPct(part.value)}</span>
            {hasRange && (
              <span className="small muted">
                {part.low != null && part.high != null ? fmtRange(part.low, part.high) : ""}
              </span>
            )}
            {hasPeople && (
              <span className="small muted">
                {part.people != null && part.people >= 500
                  ? `asi ${thousands(part.people)}${peopleLabel ? ` ${peopleLabel}` : ""}`
                  : ""}
              </span>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}

/** Where the voters of one earlier group went, ready for SplitBar */
export function destinations(flows: KeyedFlows, source: string): Part[] {
  const row = flows.sources.indexOf(source);
  return flows.targets.map((key, column) => ({
    key,
    value: flows.transitions[row][column],
    low: flows.transitionsLow[row][column],
    high: flows.transitionsHigh[row][column],
    people: (flows.electorate[row][column] / 100) * flows.previousRegistered,
  }));
}

/** Where the voters of one current group came from, ready for SplitBar */
export function origins(flows: KeyedFlows, target: string): Part[] {
  const column = flows.targets.indexOf(target);
  return flows.sources.map((key, row) => ({
    key,
    value: flows.origin[row][column],
    low: flows.originLow[row][column],
    high: flows.originHigh[row][column],
    people: (flows.electorate[row][column] / 100) * flows.previousRegistered,
  }));
}

interface SeatGroup {
  label: string;
  parts: { key: string; seats: number }[];
}

interface CampSeatsProps {
  rows: { year: string; groups: SeatGroup[] }[];
  seats: number;
  majority: number;
  colorOf: (key: string) => string;
}

/** All seats as one strip per election, lists grouped into camps, with the line a majority has to cross. */
export function CampSeats({ rows, seats, majority, colorOf }: CampSeatsProps) {
  const columns = { gridTemplateColumns: `repeat(${seats}, minmax(0, 1fr))` };
  // A little room between the camps; the labels above leave the same room
  const gap = (index: number, groups: SeatGroup[]) => (index < groups.length - 1 ? 6 : 0);
  return (
    <div className="camps">
      {rows.map((row) => (
        <div className="camp-row" key={row.year}>
          <div className="camp-year num">{row.year}</div>
          <div>
            <div className="camp-grid camp-labels" style={columns}>
              {row.groups.map((group, index) => {
                const count = group.parts.reduce((sum, part) => sum + part.seats, 0);
                return (
                  <span key={group.label} style={{ gridColumn: `span ${count}`, marginRight: gap(index, row.groups) }}>
                    {group.label} <strong className="num">{count}</strong>
                  </span>
                );
              })}
            </div>
            <div className="camp-bar">
              <div className="camp-grid camp-seats" style={columns}>
                {row.groups.flatMap((group, index) => {
                  const parts = group.parts.filter((part) => part.seats > 0);
                  return parts.map((part, position) => (
                    <span
                      key={part.key}
                      className="num"
                      style={{
                        gridColumn: `span ${part.seats}`,
                        background: colorOf(part.key),
                        marginRight: position === parts.length - 1 ? gap(index, row.groups) : 0,
                      }}
                      title={`${label(part.key)}: ${part.seats} ${plural(part.seats, "mandát", "mandáty", "mandátů")}`}
                    >
                      {part.seats}
                    </span>
                  ));
                })}
              </div>
              <div
                className="camp-majority"
                data-label={`většina ${majority}`}
                style={{ left: `${((majority - 1) / seats) * 100}%` }}
              />
            </div>
          </div>
        </div>
      ))}
      <p className="note">
        Skupina, která zleva přesáhne přerušovanou čáru, má většinu {majority} z {seats} mandátů.
      </p>
    </div>
  );
}

function Name({ group, colorOf }: { group: string; colorOf: (key: string) => string }) {
  return (
    <span className="split-name">
      <span className="swatch" style={{ background: colorOf(group) }} />
      {label(group)}
    </span>
  );
}

interface ResultsTableProps {
  lists: FollowedList[];
  years: { current: string; previous: string };
  colorOf: (key: string) => string;
  /** What to say in place of a change for a list with no result to compare with; a new list unless said otherwise */
  withoutPrevious?: Record<string, string>;
}

export function ResultsTable({ lists, years, colorOf, withoutPrevious = {} }: ResultsTableProps) {
  const scale = Math.max(...lists.map((list) => Math.max(list.share, list.previousShare ?? 0)));
  const reach = Math.max(...lists.map((list) => Math.abs(list.share - (list.previousShare ?? list.share))), 1);
  return (
    <div className="table-wrap">
      <table className="data matrix">
        <thead>
          <tr>
            <th>Kandidátka</th>
            <th className="r">{years.previous}</th>
            <th>{years.current}</th>
            <th className="col">Změna</th>
            <th className="r">Mandáty {years.previous}</th>
            <th className="r">Mandáty {years.current}</th>
          </tr>
        </thead>
        <tbody>
          {lists.map((list) => {
            const change = list.previousShare != null ? list.share - list.previousShare : null;
            const seatChange = list.previousSeats != null ? list.seats - list.previousSeats : null;
            return (
              <tr key={list.key}>
                <td>
                  <Name group={list.key} colorOf={colorOf} />
                </td>
                <td className="r muted">{list.previousShare != null ? fmtPct(list.previousShare) : "–"}</td>
                <td className="num" style={{ whiteSpace: "nowrap" }}>
                  <span
                    className="cell-bar"
                    style={{ width: `${(list.share / scale) * 90}px`, background: colorOf(list.key) }}
                  />
                  <span className="share">{fmtPct(list.share)}</span>
                </td>
                {change != null ? (
                  <td className="heat" style={changeTint(change, reach)}>
                    {fmtPp(change)}
                  </td>
                ) : (
                  <td className="heat muted">{withoutPrevious[list.key] ?? "nová"}</td>
                )}
                <td className="r muted">{list.previousSeats ?? "–"}</td>
                <td className="r">
                  <span className="share">{list.seats}</span>{" "}
                  {seatChange != null && seatChange !== 0 && (
                    <span className={`small delta ${seatChange > 0 ? "up" : "down"}`}>
                      {seatChange > 0 ? `+${seatChange}` : `−${Math.abs(seatChange)}`}
                    </span>
                  )}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

interface ScenarioTableProps {
  scenarios: Scenario[];
  majority: number;
  describe: (scenario: Scenario) => { title: string; detail?: string };
}

export function ScenarioTable({ scenarios, majority, describe }: ScenarioTableProps) {
  const actual = scenarios[0];
  const camp = (scenario: Scenario) =>
    scenario.seats.joint ?? (scenario.seats.prahaSobe ?? 0) + (scenario.seats.pirati ?? 0);
  const cell = (value: number, base: number) => (
    <td className="r">
      <span className={value === base ? "" : "share"}>{value}</span>
    </td>
  );
  return (
    <div className="table-wrap">
      <table className="data scenarios">
        <thead>
          <tr>
            <th>Co by se změnilo</th>
            <th className="r">STAN</th>
            <th className="r">Spolu</th>
            <th className="r">Praha Sobě + Piráti</th>
            <th className="r">ANO</th>
            <th className="r">STAN + Spolu</th>
          </tr>
        </thead>
        <tbody>
          {scenarios.map((scenario) => {
            const text = describe(scenario);
            const enough = scenario.stanSpolu >= majority;
            return (
              <tr key={scenario.key} className={scenario === actual ? "is-actual" : undefined}>
                <td>
                  <div>{text.title}</div>
                  {text.detail && <div className="small muted">{text.detail}</div>}
                </td>
                {cell(scenario.seats.stan, actual.seats.stan)}
                {cell(scenario.seats.spolu, actual.seats.spolu)}
                <td className="r" style={{ whiteSpace: "nowrap" }}>
                  <span className={camp(scenario) === camp(actual) ? "" : "share"}>{camp(scenario)}</span>
                  {scenario.seats.joint == null && (
                    <span className="small muted">
                      {" "}
                      ({scenario.seats.prahaSobe} + {scenario.seats.pirati})
                    </span>
                  )}
                </td>
                {cell(scenario.seats.ano, actual.seats.ano)}
                <td className="r">
                  <span className={`verdict ${enough ? "has-majority" : "no-majority"}`}>
                    <strong className="num">{scenario.stanSpolu}</strong> {enough ? "většina" : "bez většiny"}
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

interface FlowMatrixProps {
  flows: KeyedFlows;
  sourceYear: string;
  targetYear: string;
  colorOf: (key: string) => string;
  /** Row the text is about */
  highlight?: string;
}

/** The whole transition table: each row is a group of earlier voters, split by what they did now. */
export function FlowMatrix({ flows, sourceYear, targetYear, colorOf, highlight }: FlowMatrixProps) {
  return (
    <div className="table-wrap">
      <table className="data matrix">
        <thead>
          <tr>
            <th>Volba {sourceYear}</th>
            <th className="r">Voličů</th>
            {flows.targets.map((key) => (
              <th key={key} className="col">
                {key === "nevolici" ? `Nevolili ${targetYear}` : label(key)}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {flows.sources.map((key, row) => (
            <tr key={key} className={key === highlight ? "is-highlight" : undefined}>
              <td>
                <Name group={key} colorOf={colorOf} />
              </td>
              <td className="r muted">{fmtCompact((flows.sourceSize[row] / 100) * flows.previousRegistered)}</td>
              {flows.targets.map((target, column) => {
                const value = flows.transitions[row][column];
                return (
                  <td
                    key={target}
                    className="heat"
                    title={`Rozmezí odhadu ${fmtRange(flows.transitionsLow[row][column], flows.transitionsHigh[row][column])}`}
                    style={tint("var(--series-1)", value / 100, "#fff")}
                  >
                    {fmtNum(value, 0)}
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

const FIFTHS = ["nejslabší pětina", "druhá pětina", "prostřední pětina", "čtvrtá pětina", "nejsilnější pětina"];

interface FifthsTableProps {
  fifths: PrecinctFifth[];
  years: { current: string; previous: string };
  colorOf: (key: string) => string;
}

/** Precincts in fifths by the Pirates' earlier result: their share then and now and what the others gained there. */
export function FifthsTable({ fifths, years, colorOf }: FifthsTableProps) {
  const others = ["prahaSobe", "stan", "spolu", "ano"];
  const change = (fifth: PrecinctFifth, key: string) => fifth.shares[key] - fifth.previousShares[key];
  const reach = Math.max(...fifths.flatMap((fifth) => ["pirati", ...others].map((key) => Math.abs(change(fifth, key)))));
  const top = Math.max(...fifths.map((fifth) => fifth.previousShares.pirati));
  return (
    <div className="table-wrap">
      <table className="data matrix">
        <thead>
          <tr>
            <th rowSpan={2}>Okrsky</th>
            <th className="group" colSpan={3}>
              Piráti
            </th>
            {others.map((key) => (
              <th key={key} className="group">
                {label(key)}
              </th>
            ))}
          </tr>
          <tr>
            <th className="col">{years.previous}</th>
            <th className="col">{years.current}</th>
            <th className="col">změna</th>
            {others.map((key) => (
              <th key={key} className="col">
                změna
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {fifths.map((fifth, index) => (
            <tr key={index}>
              <td>{FIFTHS[index]}</td>
              <td className="heat" style={tint(colorOf("pirati"), fifth.previousShares.pirati / top)}>
                {fmtPct(fifth.previousShares.pirati)}
              </td>
              <td className="heat" style={tint(colorOf("pirati"), fifth.shares.pirati / top)}>
                {fmtPct(fifth.shares.pirati)}
              </td>
              {["pirati", ...others].map((key) => (
                <td key={key} className="heat" style={changeTint(change(fifth, key), reach)}>
                  {bare(change(fifth, key))}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

interface DistrictTableProps {
  districts: District[];
  years: { current: string; previous: string };
  colorOf: (key: string) => string;
  /** How many of the largest districts show before the reader asks for all */
  initial?: number;
}

export function DistrictTable({ districts, years, colorOf, initial = 15 }: DistrictTableProps) {
  const [all, setAll] = useState(false);
  const share = (district: District, key: string) => district.shares[key] ?? 0;
  const before = (district: District, key: string) => district.previousShares[key] ?? 0;
  const change = (district: District, key: string) => share(district, key) - before(district, key);
  const camp = (district: District) => change(district, "pirati") + change(district, "prahaSobe");
  const rows = [...(all ? districts : districts.slice(0, initial))].sort((a, b) => camp(a) - camp(b));

  // The colours keep one meaning in every row, whether fifteen districts show or all
  const largest = districts.slice(0, initial);
  const top = (key: string) => Math.max(...largest.map((district) => Math.max(share(district, key), before(district, key))));
  const reach = Math.max(
    ...largest.flatMap((district) => [camp(district), change(district, "stan"), change(district, "spolu")].map(Math.abs)),
  );
  const shareCell = (value: number, key: string) => (
    <td className="heat" style={tint(colorOf(key), (value / top(key)) * 0.75)}>
      {fmtNum(value)}
    </td>
  );
  const changeCell = (value: number) => (
    <td className="heat" style={changeTint(value, reach)}>
      {bare(value)}
    </td>
  );

  return (
    <>
      <div className="table-wrap">
        <table className="data matrix">
          <thead>
            <tr>
              <th rowSpan={2}>Městská část</th>
              <th className="group" colSpan={2}>
                Piráti
              </th>
              <th className="group" colSpan={2}>
                Praha Sobě
              </th>
              <th className="group">Obě dohromady</th>
              <th className="group">STAN</th>
              <th className="group">Spolu</th>
              <th className="group">SEN</th>
            </tr>
            <tr>
              <th className="col">{years.previous}</th>
              <th className="col">{years.current}</th>
              <th className="col">{years.previous}</th>
              <th className="col">{years.current}</th>
              <th className="col">změna</th>
              <th className="col">změna</th>
              <th className="col">změna</th>
              <th className="col">{years.current}</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((district) => (
              <tr key={district.code}>
                <td style={{ whiteSpace: "nowrap" }}>{district.name}</td>
                {shareCell(before(district, "pirati"), "pirati")}
                {shareCell(share(district, "pirati"), "pirati")}
                {shareCell(before(district, "prahaSobe"), "prahaSobe")}
                {shareCell(share(district, "prahaSobe"), "prahaSobe")}
                {changeCell(camp(district))}
                {changeCell(change(district, "stan"))}
                {changeCell(change(district, "spolu"))}
                {shareCell(share(district, "sen"), "sen")}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {districts.length > initial && (
        <button className="text-button" onClick={() => setAll(!all)}>
          {all ? `Zobrazit jen ${initial} největších` : `Zobrazit všech ${districts.length} městských částí`}
        </button>
      )}
    </>
  );
}

export interface HeatColumn<Row> {
  head: string;
  /** Heading shared by neighbouring columns of the same group */
  group?: string;
  value: (row: Row) => number;
  format: (value: number) => string;
  /** A colour for values where more means stronger, or "change" for blue gains and red losses */
  tint?: string;
}

interface HeatTableProps<Row> {
  rows: Row[];
  rowHead: string;
  rowLabel: (row: Row) => string;
  columns: HeatColumn<Row>[];
}

/** A table of numbers with cells tinted by value, each column on its own scale; changes share one. */
export function HeatTable<Row>({ rows, rowHead, rowLabel, columns }: HeatTableProps<Row>) {
  const grouped = columns.some((column) => column.group);
  const groups: { name: string; span: number }[] = [];
  for (const column of columns) {
    const previous = groups[groups.length - 1];
    if (previous && column.group && previous.name === column.group) previous.span += 1;
    else groups.push({ name: column.group ?? "", span: 1 });
  }
  const top = columns.map((column) => Math.max(...rows.map((row) => Math.abs(column.value(row))), 1e-9));
  const reach = Math.max(...columns.flatMap((column, index) => (column.tint === "change" ? [top[index]] : [])), 1e-9);
  const style = (column: HeatColumn<Row>, index: number, value: number) =>
    column.tint === "change" ? changeTint(value, reach) : tint(column.tint!, (value / top[index]) * 0.75);

  return (
    <div className="table-wrap">
      <table className="data matrix">
        <thead>
          {grouped && (
            <tr>
              <th rowSpan={2}>{rowHead}</th>
              {groups.map((group, index) => (
                <th key={index} className="group" colSpan={group.span > 1 ? group.span : undefined}>
                  {group.name}
                </th>
              ))}
            </tr>
          )}
          <tr>
            {!grouped && <th>{rowHead}</th>}
            {columns.map((column, index) => (
              <th key={index} className="col">
                {column.head}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, position) => (
            <tr key={position}>
              <td>{rowLabel(row)}</td>
              {columns.map((column, index) => {
                const value = column.value(row);
                return (
                  <td
                    key={index}
                    className={column.tint ? "heat" : "heat plain"}
                    style={column.tint ? style(column, index, value) : undefined}
                  >
                    {column.format(value)}
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

interface ElectionBarsProps {
  rows: { key: string; values: (number | null)[] }[];
  /** Name of each election, in the order of the values */
  elections: string[];
  colorOf: (key: string) => string;
  /** How to write a number of voters; whole thousands unless said otherwise */
  format?: (voters: number) => string;
}

const inThousands = (voters: number) => `${fmtInt(Math.round(voters / 1000))} tis.`;

/** How many people voted for each list in several elections, as bars on one scale. */
export function ElectionBars({ rows, elections, colorOf, format = inThousands }: ElectionBarsProps) {
  const scale = Math.max(...rows.flatMap((row) => row.values.map((value) => value ?? 0)), 1);
  return (
    <div className="election-bars">
      {rows.map((row) => (
        <div className="election-row" key={row.key}>
          <div className="election-name">
            <Name group={row.key} colorOf={colorOf} />
          </div>
          <div className="election-values num">
            {row.values.map((value, index) => (
              <div className="election-value" key={elections[index]}>
                <span className="small muted">{elections[index]}</span>
                <span className="election-track">
                  {value != null && (
                    <span
                      style={{
                        width: `${(value / scale) * 100}%`,
                        background: colorOf(row.key),
                        // The parliamentary election is another kind of vote; it reads as lighter
                        opacity: index === 1 ? 0.45 : 1,
                      }}
                    />
                  )}
                </span>
                <span className={value != null ? "share" : "muted"}>
                  {value != null ? format(value) : "nekandidovala"}
                </span>
              </div>
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}

interface StayedHomeTableProps {
  /** Estimate from the parliamentary election to the municipal one */
  flows: KeyedFlows;
  /** Votes of the parties in the parliamentary election */
  parties: { key: string; votes: number }[];
  colorOf: (key: string) => string;
}

/** How many voters of each party in the parliamentary election did not vote in the municipal one. */
export function StayedHomeTable({ flows, parties, colorOf }: StayedHomeTableProps) {
  const rows = parties
    .filter((party) => flows.sources.includes(party.key))
    .map((party) => ({ ...party, home: cell(flows, party.key, "nevolici") }))
    .sort((a, b) => b.home.share - a.home.share);
  return (
    <div className="table-wrap">
      <table className="data matrix">
        <thead>
          <tr>
            <th>Strana ve sněmovních volbách</th>
            <th className="col">Hlasů v Praze</th>
            <th className="col">Letos nepřišlo</th>
            <th className="col">Rozmezí odhadu</th>
            <th className="col">Asi lidí</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.key}>
              <td>
                <Name group={row.key} colorOf={colorOf} />
              </td>
              <td className="heat plain">{fmtInt(Math.round(row.votes / 1000))} tis.</td>
              <td className="heat" style={changeTint(-row.home.share, 100)}>
                {fmtPct(row.home.share, 0)}
              </td>
              <td className="heat plain muted">{fmtRange(row.home.low, row.home.high)}</td>
              <td className="heat plain">{fmtInt(Math.round((row.votes * row.home.share) / 100000))} tis.</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

interface SeatGridProps {
  title: string;
  rowHead: string;
  rows: number[];
  columnHead: string;
  columns: number[];
  cells: number[][];
  /** Seats that are a majority; fewer is the outcome the grid looks for */
  majority: number;
}

/** Seats of two lists together for every combination of two changes; the cells without a majority stand out. */
export function SeatGrid({ title, rowHead, rows, columnHead, columns, cells, majority }: SeatGridProps) {
  const level = (value: number) => (value < majority ? "none" : value === majority ? "bare" : "safe");
  return (
    <div>
      <h4 className="split-title">{title}</h4>
      <div className="table-wrap">
        <table className="data seat-grid">
          <thead>
            <tr>
              <th rowSpan={2}>{rowHead}</th>
              <th colSpan={columns.length} className="seat-grid-head">
                {columnHead}
              </th>
            </tr>
            <tr>
              {columns.map((column) => (
                <th key={column} className="r">
                  {fmtInt(column)}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((row, index) => (
              <tr key={row}>
                <td className="num">{fmtPct(row, 0)}</td>
                {columns.map((column, position) => (
                  <td key={column} className={`seat-cell ${level(cells[index][position])}`}>
                    {cells[index][position]}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

