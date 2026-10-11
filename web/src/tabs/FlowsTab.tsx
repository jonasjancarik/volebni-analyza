import { useState } from "react";
import { type Comparison, useComparison } from "../api";
import { NON_VOTER, REST, SERIES } from "../colors";
import type { TabProps } from "../Council";
import { FlowBars } from "../components/FlowBars";
import { Sankey } from "../components/Sankey";
import { Loading, Problem } from "../components/State";
import { fmtInt, fmtNum, fmtPct, fmtRange, listName, plural } from "../format";
import { useParam } from "../hooks";

export function FlowsTab({ council, colorByName, focus }: TabProps) {
  const [area, setArea] = useParam("uzemi");
  const comparison = useComparison(council.election.id, council.code, area);
  const areaName = council.areas.find((item) => item.code === area)?.name;

  return (
    <div className="stack">
      {council.areas.length > 1 && (
        <div className="toolbar">
          <label className="field-label" htmlFor="flows-area">
            Území
          </label>
          <select
            id="flows-area"
            className="select"
            value={area ?? ""}
            onChange={(event) => setArea(event.target.value || null)}
          >
            <option value="">Celé město</option>
            {council.areas.map((item) => (
              <option key={item.code} value={item.code}>
                {item.name} ({item.precincts} {plural(item.precincts, "okrsek", "okrsky", "okrsků")})
              </option>
            ))}
          </select>
          {areaName && (
            <span className="small muted">
              Jak se ve volbách do zastupitelstva celého města přesouvali voliči, kteří bydlí v části {areaName}.
            </span>
          )}
        </div>
      )}
      {comparison.isPending && (
        <Loading text="Počítám odhad přesunů voličů. U velkých měst to trvá několik sekund." />
      )}
      {comparison.error && <Problem error={comparison.error} />}
      {comparison.data && (
        <FlowsBody
          key={area ?? ""}
          comparison={comparison.data}
          colorByName={colorByName}
          focusName={council.lists[focus]?.name}
        />
      )}
    </div>
  );
}

interface BodyProps {
  comparison: Comparison;
  colorByName: Map<string, string>;
  focusName: string | undefined;
}

function FlowsBody({ comparison, colorByName, focusName }: BodyProps) {
  const { flows, previousYear, currentYear, matched, skipped, nonVoters, otherLists } = comparison;
  const [showStayedHome, setShowStayedHome] = useState(false);
  const [picked, setPicked] = useState<{ side: "source" | "target"; name: string } | null>(null);

  const preferred = (groups: string[]) =>
    (focusName && groups.includes(focusName) ? focusName : undefined) ??
    groups.find((group) => /pirát/i.test(group)) ??
    groups[0];
  const [source, setSource] = useState(() => (flows ? preferred(flows.sources) : ""));
  const [target, setTarget] = useState(() => (flows ? preferred(flows.targets) : ""));

  if (matched === 0) {
    return (
      <div className="banner neutral">
        Okrsky se mezi roky {previousYear} a {currentYear} nepodařilo spárovat, takže přesuny voličů odhadnout nejde.
      </div>
    );
  }
  if (!flows) {
    return (
      <div className="banner neutral">
        Odhad přesunů voličů potřebuje aspoň {comparison.minPrecincts} okrsků, tady {plural(matched, "je", "jsou", "je")}{" "}
        {fmtInt(matched)}. Změny v jednotlivých okrscích najdete na kartě Okrsky.
      </div>
    );
  }

  // Lists of the previous election that did not run again take the colours that are left
  const groups = [...flows.targets, ...flows.sources].filter((group) => group !== nonVoters && group !== otherLists);
  const taken = new Set(groups.map((group) => colorByName.get(group)));
  const free = SERIES.filter((color) => !taken.has(color));
  const extra = new Map<string, string>();
  for (const group of groups) {
    if (!colorByName.has(group) && !extra.has(group)) extra.set(group, free.shift() ?? REST);
  }
  const colorOf = (group: string) =>
    group === nonVoters ? NON_VOTER : group === otherLists ? REST : (colorByName.get(group) ?? extra.get(group) ?? REST);

  const sourceIndex = Math.max(0, flows.sources.indexOf(source));
  const targetIndex = Math.max(0, flows.targets.indexOf(target));
  const groupLabel = (name: string, year: string) => (name === nonVoters ? `Nevoliči ${year}` : name);

  const pick = (side: "source" | "target", name: string) => {
    if (side === "source") setSource(name);
    else setTarget(name);
    setPicked((current) => (current?.side === side && current.name === name ? null : { side, name }));
  };

  return (
    <>
      {comparison.rough && (
        <div className="banner">
          <strong>Hrubý odhad.</strong> K dispozici je jen {fmtInt(matched)} okrsků. U takto malých obvodů dávají různé
          metody výpočtu znatelně odlišné výsledky, u jednotlivých kandidátek i o desítky procentních bodů. Věřte jen
          velkým přesunům s úzkým rozpětím.
        </div>
      )}

      <section className="card">
        <div className="card-head">
          <div>
            <h2>
              Kam se voliči přesunuli mezi roky {previousYear} a {currentYear}
            </h2>
            <div className="card-sub">
              Šířka pruhu odpovídá počtu voličů. Kliknutím na kandidátku zvýrazníte její pruhy.
            </div>
          </div>
          <label className="toggle">
            <input type="checkbox" checked={showStayedHome} onChange={(event) => setShowStayedHome(event.target.checked)} />
            I ti, kdo nevolili ani jednou
          </label>
        </div>
        <Sankey
          flows={flows}
          previousYear={previousYear}
          currentYear={currentYear}
          nonVoters={nonVoters}
          colorOf={colorOf}
          showStayedHome={showStayedHome}
          highlight={picked}
          onPick={pick}
        />
      </section>

      <section className="card">
        <div className="flow-facts num">
          <div className="fact">
            <div className="value">{fmtPct(flows.stayedHome)}</div>
            <div className="label">zapsaných voličů nevolilo ani v jednom roce</div>
          </div>
          <div className="fact">
            <div className="value">
              {fmtPct(flows.newlyVoted.value)} <span className="range">{fmtRange(flows.newlyVoted.low, flows.newlyVoted.high)}</span>
            </div>
            <div className="label">přišlo nově</div>
          </div>
          <div className="fact">
            <div className="value">
              {fmtPct(flows.stoppedVoting.value)}{" "}
              <span className="range">{fmtRange(flows.stoppedVoting.low, flows.stoppedVoting.high)}</span>
            </div>
            <div className="label">volit přestalo</div>
          </div>
        </div>
        <p className="note" style={{ marginTop: 14 }}>
          Poslední dvě čísla jsou spodní odhad. Z výsledků v okrscích se dá spolehlivě určit jen to, o kolik se účast
          změnila celkem, ne kolik lidí se mezi voliči a nevoliči ve skutečnosti vyměnilo.
        </p>
      </section>

      <div className="grid half">
        <section className="card">
          <div className="card-head" style={{ display: "block" }}>
            <h2>Kam odešli voliči z roku {previousYear}</h2>
            <select
              className="select block"
              style={{ marginTop: 10 }}
              aria-label={`Skupina voličů z roku ${previousYear}`}
              value={flows.sources[sourceIndex]}
              onChange={(event) => setSource(event.target.value)}
            >
              {flows.sources.map((name) => (
                <option key={name} value={name}>
                  {listName(name)}
                </option>
              ))}
            </select>
          </div>
          <FlowBars
            bars={flows.targets.map((name, column) => ({
              name,
              label: groupLabel(name, currentYear),
              color: colorOf(name),
              value: flows.transitions[sourceIndex][column],
              low: flows.transitionsLow[sourceIndex][column],
              high: flows.transitionsHigh[sourceIndex][column],
            }))}
          />
        </section>
        <section className="card">
          <div className="card-head" style={{ display: "block" }}>
            <h2>Odkud přišli voliči v roce {currentYear}</h2>
            <select
              className="select block"
              style={{ marginTop: 10 }}
              aria-label={`Skupina voličů v roce ${currentYear}`}
              value={flows.targets[targetIndex]}
              onChange={(event) => setTarget(event.target.value)}
            >
              {flows.targets.map((name) => (
                <option key={name} value={name}>
                  {listName(name)}
                </option>
              ))}
            </select>
          </div>
          <FlowBars
            bars={flows.sources.map((name, row) => ({
              name,
              label: groupLabel(name, previousYear),
              color: colorOf(name),
              value: flows.origin[row][targetIndex],
              low: flows.originLow[row][targetIndex],
              high: flows.originHigh[row][targetIndex],
            }))}
          />
        </section>
      </div>
      <p className="note">
        Tučně je odhad, šedě a čárkou v grafu rozpětí, ve kterém se odhad pohybuje, když se počítá z různých náhodných
        výběrů okrsků. Čím je rozpětí širší, tím méně se dá číslu věřit.
      </p>

      <section className="card">
        <details className="more">
          <summary>Celá tabulka přesunů</summary>
          <div className="more-body">
            <div className="table-wrap">
              <table className="data matrix">
                <thead>
                  <tr>
                    <th>Skupina {previousYear}</th>
                    <th className="r">Podíl voličů</th>
                    {flows.targets.map((name) => (
                      <th key={name} className="col" title={name}>
                        {listName(name)}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {flows.sources.map((name, row) => (
                    <tr key={name}>
                      <td>{listName(name)}</td>
                      <td className="r">{fmtPct(flows.sourceSize[row])}</td>
                      {flows.targets.map((targetName, column) => {
                        const value = flows.transitions[row][column];
                        return (
                          <td
                            key={targetName}
                            className="heat"
                            title={`Rozpětí odhadu ${fmtRange(flows.transitionsLow[row][column], flows.transitionsHigh[row][column])}`}
                            style={{
                              background: `color-mix(in srgb, var(--series-1) ${Math.round(Math.min(value, 100) * 0.75)}%, var(--surface-2))`,
                              color: value > 55 ? "#fff" : "var(--ink)",
                            }}
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
            <p className="note" style={{ marginTop: 12 }}>
              Řádky jsou skupiny voličů z roku {previousYear}. Sloupce říkají, kolik procent z nich skončilo u které
              kandidátky v roce {currentYear}; čísla v řádku dávají dohromady 100. Rozpětí odhadu se ukáže po najetí
              myší na buňku.
            </p>
          </div>
        </details>
      </section>

      <section className="card">
        <h2>Jak tomu rozumět</h2>
        <div style={{ marginTop: 10, maxWidth: "78ch" }}>
          <p className="note">
            Jde o modelový odhad, ne o měření. Vychází z výsledků v okrscích a předpokládá, že se voliči stejné
            kandidátky chovali v podobných okrscích podobně. Malé přesuny v řádu jednotek procent proto berte jako
            orientační.
          </p>
          <p className="note">
            Model vysvětluje {fmtPct(flows.explained, 0)} rozdílů mezi okrsky a pracuje s {fmtInt(matched)} okrsky.
            {flows.precinctTypes > 1 &&
              ` Okrsky jsou rozdělené do ${flows.precinctTypes} skupin podle toho, jak se v nich volilo v roce ${previousYear}, a přesuny se odhadují v každé skupině zvlášť, protože voliči stejné kandidátky se v různých částech města nemusí chovat stejně.`}
          </p>
          <p className="note">
            Rozpětí je {fmtNum(flows.interval, 0)}% interval z opakovaných výpočtů na náhodně vybraných okrscích.
            Ukazuje, jak moc odhad závisí na konkrétních okrscích, ne celkovou chybu modelu.
          </p>
          <p className="note">
            {skipped > 0 &&
              `${fmtInt(skipped)} ${plural(skipped, "okrsek je vynechaný", "okrsky jsou vynechané", "okrsků je vynecháno")}, protože v roce ${previousYear} ${plural(skipped, "neexistoval nebo se mu", "neexistovaly nebo se jim", "neexistovalo nebo se jim")} výrazně změnil počet voličů. `}
            Hlasy jsou přepočtené na voliče a kandidátky pod 3 % jsou sloučené do skupiny Ostatní kandidátky.
          </p>
        </div>
      </section>
    </>
  );
}
