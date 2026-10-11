import { useMemo, useState } from "react";
import { useCandidates } from "../api";
import type { TabProps } from "../Council";
import { Loading, Problem } from "../components/State";
import { fmtInt, fmtPct, fold, listName, plural, truncate } from "../format";

const PAGE = 60;

export function CandidatesTab({ council, focus }: TabProps) {
  const candidates = useCandidates(council.election.id, council.code);
  const [list, setList] = useState(council.lists[focus]?.name ?? "");
  const [query, setQuery] = useState("");
  const [shown, setShown] = useState(PAGE);

  const filtered = useMemo(() => {
    const needle = fold(query.trim());
    return (candidates.data ?? [])
      .filter((candidate) => (!list || candidate.list === list) && (!needle || fold(candidate.name).includes(needle)))
      .sort((a, b) => (list ? a.position - b.position : b.votes - a.votes));
  }, [candidates.data, list, query]);

  if (candidates.isPending) return <Loading text="Načítám kandidáty…" />;
  if (candidates.error) return <Problem error={candidates.error} />;

  return (
    <section className="card">
      <div className="card-head">
        <div>
          <h2>Kandidáti</h2>
          <div className="card-sub">
            {fmtInt(filtered.length)} {plural(filtered.length, "kandidát", "kandidáti", "kandidátů")},{" "}
            {list ? "v pořadí na kandidátce" : "od nejvíce přednostních hlasů"}
          </div>
        </div>
        <div className="toolbar">
          <select
            className="select"
            aria-label="Strana"
            value={list}
            style={{ maxWidth: 300 }}
            onChange={(event) => {
              setList(event.target.value);
              setShown(PAGE);
            }}
          >
            <option value="">Všechny strany</option>
            {council.lists.map((item) => (
              <option key={item.number} value={item.name}>
                {truncate(listName(item.name), 40)}
              </option>
            ))}
          </select>
          <input
            className="input"
            placeholder="Jméno kandidáta"
            aria-label="Hledat podle jména"
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
              <th className="r">Pořadí</th>
              <th>Jméno</th>
              {!list && <th>Strana</th>}
              <th className="r">Věk</th>
              <th>Bydliště</th>
              <th className="r">Přednostní hlasy</th>
              <th className="r">Podíl</th>
            </tr>
          </thead>
          <tbody>
            {filtered.slice(0, shown).map((candidate) => (
              <tr key={`${candidate.list}-${candidate.position}`}>
                <td className="r muted">{candidate.position}</td>
                <td>
                  <div style={{ fontWeight: 580 }}>
                    {candidate.name}
                    {candidate.elected && <span className="small delta up"> · zvolen(a)</span>}
                  </div>
                  <div className="small muted">{truncate(candidate.occupation, 80)}</div>
                </td>
                {!list && <td className="muted">{truncate(listName(candidate.list), 32)}</td>}
                <td className="r">{candidate.age}</td>
                <td>{candidate.residence}</td>
                <td className="r">{fmtInt(candidate.votes)}</td>
                <td className="r">{fmtPct(candidate.share)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {filtered.length > shown && (
        <button className="text-button" style={{ marginTop: 10 }} onClick={() => setShown(shown + PAGE * 4)}>
          Zobrazit další ({fmtInt(filtered.length - shown)} zbývá)
        </button>
      )}
      <p className="note" style={{ marginTop: 14 }}>
        Podíl říká, kolik procent voličů strany dalo kandidátovi přednostní hlas.
      </p>
    </section>
  );
}
