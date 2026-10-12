import { useMemo, useState } from "react";
import { useComparison } from "../api";
import type { TabProps } from "../Council";
import { PrecinctDetail } from "../components/PrecinctDetail";
import { Scatter } from "../components/Scatter";
import { fmtInt, fmtPct, fmtPp, listName, plural, truncate } from "../format";
import { MapLink } from "../components/MapLink";
import { useParam } from "../hooks";

const TURNOUT = "__turnout";
const PAGE = 50;

type SortKey = "number" | "registered" | "turnout" | "turnoutChange" | "share" | "shareChange";

interface Row {
  id: string;
  number: string;
  area: string;
  registered: number;
  turnout: number;
  turnoutChange: number | null;
  share: number;
  shareChange: number | null;
  winner: number;
}

export function PrecinctsTab({ council, colors, focus }: TabProps) {
  const { election, lists, precincts, areas, previous } = council;
  const comparison = useComparison(election.id, council.code, null, !!previous);
  const [selected, setSelected] = useParam("okrsek");
  const [areaParam, setArea] = useParam("uzemi");
  const [metricParam, setMetric] = useParam("zm");
  const [query, setQuery] = useState("");
  const [sort, setSort] = useState<{ key: SortKey; descending: boolean }>({ key: "share", descending: true });
  const [shown, setShown] = useState(PAGE);
  const area = areas.some((item) => item.code === areaParam) ? areaParam : null;
  const parliamentary = election.type === "parliamentary";
  const focusList = lists[focus];
  const data = comparison.data;
  const focusInBoth = data ? data.sameLists.indexOf(focusList.name) : -1;

  const areaNames = useMemo(() => new Map(areas.map((item) => [item.code, item.name])), [areas]);
  const rows = useMemo<Row[]>(() => {
    const compared = new Map((data?.precincts ?? []).map((precinct) => [precinct.id, precinct]));
    return precincts.map((precinct) => {
      const total = precinct.votes.reduce((sum, votes) => sum + votes, 0);
      const match = compared.get(precinct.id);
      return {
        id: precinct.id,
        number: precinct.number,
        area: precinct.area,
        registered: precinct.registered,
        turnout: precinct.turnout,
        turnoutChange: match ? match.turnout[1] - match.turnout[0] : null,
        share: total ? (precinct.votes[focus] / total) * 100 : 0,
        shareChange: match && focusInBoth !== -1 ? match.current[focusInBoth] - match.previous[focusInBoth] : null,
        winner: total ? precinct.votes.indexOf(Math.max(...precinct.votes)) : -1,
      };
    });
  }, [precincts, data, focus, focusInBoth]);

  const filtered = useMemo(() => {
    const needle = query.trim();
    const list = rows.filter((row) => (!area || row.area === area) && (!needle || row.number.startsWith(needle)));
    const direction = sort.descending ? -1 : 1;
    return list.sort((a, b) => {
      if (sort.key === "number") return a.number.localeCompare(b.number, "cs", { numeric: true }) * direction;
      return ((a[sort.key] ?? -Infinity) - (b[sort.key] ?? -Infinity)) * direction;
    });
  }, [rows, area, query, sort]);

  const sortBy = (key: SortKey) => {
    setSort((current) => ({ key, descending: current.key === key ? !current.descending : key !== "number" }));
    setShown(PAGE);
  };
  const header = (key: SortKey, label: string, right = true) => (
    <th
      className={`sortable${right ? " r" : ""}`}
      onClick={() => sortBy(key)}
      aria-sort={sort.key === key ? (sort.descending ? "descending" : "ascending") : undefined}
    >
      {label}
      {sort.key === key ? (sort.descending ? " ↓" : " ↑") : ""}
    </th>
  );

  // What the scatter compares: turnout or a list that ran in both elections
  const metric =
    metricParam && data?.sameLists.includes(metricParam)
      ? metricParam
      : metricParam === TURNOUT || focusInBoth === -1
        ? TURNOUT
        : focusList.name;
  const metricIndex = data ? data.sameLists.indexOf(metric) : -1;
  const points = useMemo(
    () =>
      (data?.precincts ?? [])
        .filter((precinct) => !area || precincts.find((item) => item.id === precinct.id)?.area === area)
        .map((precinct) => ({
          id: precinct.id,
          label: `Okrsek ${precinct.id}`,
          previous: metricIndex === -1 ? precinct.turnout[0] : precinct.previous[metricIndex],
          current: metricIndex === -1 ? precinct.turnout[1] : precinct.current[metricIndex],
          size: precinct.registered,
        })),
    [data, metricIndex, area, precincts],
  );
  const improved = points.filter((point) => point.current > point.previous).length;

  const maxShare = Math.max(...rows.map((row) => row.share), 1);
  const selectedPrecinct = precincts.find((precinct) => precinct.id === selected);

  return (
    <div className="stack">
      {data && points.length >= 3 && (
        <section className="card">
          <div className="card-head">
            <div>
              <h2>
                Změna v okrscích mezi roky {data.previousYear} a {data.currentYear}
              </h2>
              <div className="card-sub">
                {metric === TURNOUT ? "Účast" : "Podíl hlasů"} vzrostl{metric === TURNOUT ? "a" : ""} v {fmtInt(improved)} z{" "}
                {fmtInt(points.length)} okrsků. Body nad čarou jsou okrsky, kde je výsledek vyšší než minule; velikost
                bodu odpovídá počtu voličů.
              </div>
            </div>
            <select className="select" aria-label="Co porovnat" value={metric} onChange={(event) => setMetric(event.target.value)}>
              <option value={TURNOUT}>Volební účast</option>
              {data.sameLists.map((name) => (
                <option key={name} value={name}>
                  {truncate(listName(name), 40)}
                </option>
              ))}
            </select>
          </div>
          <Scatter
            points={points}
            previousYear={data.previousYear}
            currentYear={data.currentYear}
            selected={selected}
            onSelect={setSelected}
          />
          {data.skipped > 0 && (
            <p className="note">
              {fmtInt(data.skipped)} {plural(data.skipped, "okrsek chybí", "okrsky chybí", "okrsků chybí")}, protože v roce{" "}
              {data.previousYear} {plural(data.skipped, "neexistoval nebo se mu", "neexistovaly nebo se jim", "neexistovalo nebo se jim")}{" "}
              výrazně změnil počet voličů.
            </p>
          )}
        </section>
      )}

      <section className="card">
        <div className="card-head">
          <div>
            <h2>Všechny okrsky</h2>
            <div className="card-sub">
              {fmtInt(filtered.length)} {plural(filtered.length, "okrsek", "okrsky", "okrsků")}. Kliknutím na řádek
              zobrazíte výsledky okrsku, kliknutím na záhlaví tabulku seřadíte.
            </div>
          </div>
          <div className="toolbar">
            {areas.length > 1 && (
              <select
                className="select"
                aria-label={parliamentary ? "Obec" : "Městská část"}
                value={area ?? ""}
                onChange={(event) => {
                  setArea(event.target.value || null);
                  setShown(PAGE);
                }}
              >
                <option value="">{parliamentary ? "Všechny obce" : "Všechny městské části"}</option>
                {areas.map((item) => (
                  <option key={item.code} value={item.code}>
                    {item.name}
                  </option>
                ))}
              </select>
            )}
            <input
              className="input"
              style={{ width: 150 }}
              placeholder="Číslo okrsku"
              aria-label="Hledat podle čísla okrsku"
              inputMode="numeric"
              value={query}
              onChange={(event) => {
                setQuery(event.target.value);
                setShown(PAGE);
              }}
            />
          </div>
        </div>
        <div className="table-wrap">
          <table className="data">
            <thead>
              <tr>
                {header("number", "Okrsek", false)}
                {areas.length > 1 && <th>{parliamentary ? "Obec" : "Městská část"}</th>}
                {header("registered", "Zapsaní voliči")}
                {header("turnout", "Účast")}
                {data && header("turnoutChange", `Proti ${data.previousYear}`)}
                {header("share", truncate(listName(focusList.name), 26), false)}
                {data && focusInBoth !== -1 && header("shareChange", `Proti ${data.previousYear}`)}
                <th>Vítěz v okrsku</th>
                <th aria-label="Mapa" />
              </tr>
            </thead>
            <tbody>
              {filtered.slice(0, shown).map((row) => (
                <tr
                  key={row.id}
                  className={`clickable${row.id === selected ? " selected" : ""}`}
                  onClick={() => setSelected(row.id)}
                >
                  <td className="num" style={{ fontWeight: 600 }}>
                    {row.number}
                  </td>
                  {areas.length > 1 && <td className="muted">{areaNames.get(row.area)}</td>}
                  <td className="r">{fmtInt(row.registered)}</td>
                  <td className="r">{fmtPct(row.turnout)}</td>
                  {data && <Change value={row.turnoutChange} />}
                  <td className="num" style={{ whiteSpace: "nowrap" }}>
                    <span className="cell-bar" style={{ width: Math.max(2, (row.share / maxShare) * 90), background: colors[focus] }} />
                    {fmtPct(row.share)}
                  </td>
                  {data && focusInBoth !== -1 && <Change value={row.shareChange} />}
                  <td>
                    {row.winner === -1 ? (
                      <span className="muted">–</span>
                    ) : (
                      <span className="legend-item">
                        <span className="swatch" style={{ background: colors[row.winner] }} />
                        {truncate(listName(lists[row.winner].name), 30)}
                      </span>
                    )}
                  </td>
                  <td className="r">
                    <MapLink precinct={row.id} label="Mapa" />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {filtered.length === 0 && <p className="note" style={{ marginTop: 14 }}>Žádný okrsek neodpovídá tomu, co hledáte.</p>}
        {filtered.length > shown && (
          <button className="text-button" style={{ marginTop: 10 }} onClick={() => setShown(shown + PAGE * 4)}>
            Zobrazit další ({fmtInt(filtered.length - shown)} zbývá)
          </button>
        )}
      </section>

      {selectedPrecinct && (
        <>
          <div className="drawer-backdrop" onClick={() => setSelected(null)} />
          <aside className="drawer" aria-label="Detail okrsku">
            <PrecinctDetail
              council={council}
              precinct={selectedPrecinct}
              colors={colors}
              focus={focus}
              compared={data?.precincts.find((item) => item.id === selectedPrecinct.id)}
              previousYear={previous?.year}
              map
              onClose={() => setSelected(null)}
            />
          </aside>
        </>
      )}
    </div>
  );
}

function Change({ value }: { value: number | null }) {
  if (value == null) return <td className="r muted">–</td>;
  return <td className={`r delta ${value >= 0 ? "up" : "down"}`}>{fmtPp(value)}</td>;
}
