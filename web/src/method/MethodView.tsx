import { useMemo, useState } from "react";
import { type Comparison, useFlowInputs } from "../api";
import { Loading, Problem } from "../components/State";
import { fmtInt, listName, plural } from "../format";
import { buildModel, trajectory } from "./model";
import { OnePrecinct } from "./OnePrecinct";
import { PrecinctCloud } from "./PrecinctCloud";
import { Resampling } from "./Resampling";
import { Step, type StepProps } from "./Step";
import { TableSearch } from "./TableSearch";
import { wording } from "./wording";

interface Props {
  election: string;
  code: string;
  area: string | null;
  placeName: string;
  comparison: Comparison;
  colorOf: (name: string) => string;
  focusName: string | undefined;
  onBack: () => void;
}

/** The voter-flow estimate explained step by step on the precincts of this council. */
export function MethodView({ election, code, area, placeName, comparison, colorOf, focusName, onBack }: Props) {
  const inputs = useFlowInputs(election, code, area);
  const flows = comparison.flows!;
  const { previousYear, currentYear, nonVoters, otherLists } = comparison;

  const preferred = (groups: string[]) =>
    Math.max(
      0,
      focusName && groups.includes(focusName) ? groups.indexOf(focusName) : groups.findIndex((group) => /pirát/i.test(group)),
    );
  const [source, setSource] = useState(() => preferred(flows.sources));
  const [target, setTarget] = useState(() => {
    const same = flows.targets.indexOf(flows.sources[preferred(flows.sources)]);
    return same === -1 ? preferred(flows.targets) : same;
  });
  const [pickedPrecinct, setPickedPrecinct] = useState<number | null>(null);

  const data = inputs.data;
  const model = useMemo(() => (data ? buildModel(data) : null), [data]);
  const snapshots = useMemo(() => (model ? trajectory(model) : null), [model]);
  // The precinct with the most people in both followed groups shows the most
  const clearest = useMemo(() => {
    if (!data) return 0;
    let best = 0;
    data.precincts.forEach((precinct, index) => {
      const strength = (item: typeof precinct) => Math.min(item.previous[source], item.current[target]) * item.registered;
      if (strength(precinct) > strength(data.precincts[best])) best = index;
    });
    return best;
  }, [data, source, target]);

  if (inputs.isPending) return <Loading text="Načítám výsledky okrsků…" />;
  if (inputs.error) return <Problem error={inputs.error} />;
  if (!data || !model || !snapshots) return null;

  const precinct = pickedPrecinct ?? clearest;
  const count = data.precincts.length;
  const pick = (nextSource: number, nextTarget: number) => {
    setSource(nextSource);
    setTarget(nextTarget);
    setPickedPrecinct(null);
  };
  const step: StepProps = {
    inputs: data,
    flows,
    source,
    target,
    previousYear,
    currentYear,
    colorOf,
    words: wording(nonVoters, otherLists, colorOf),
  };

  return (
    <>
      <section className="card method-intro">
        <h2>Jak odhad přesunů vzniká</h2>
        <p className="method-text">
          Volby jsou tajné. Nikdo neví, koho konkrétní člověk volil minule a koho letos; známé jsou jen výsledky
          jednotlivých okrsků z obou voleb. Na {fmtInt(count)} {plural(count, "okrsku", "okrscích", "okrscích")}, které má{" "}
          {placeName}, si můžete projít, jak se z nich dá odhadnout, kam se voliči přesunuli.
        </p>
        <div className="method-pickers">
          <label>
            <span className="field-label">Skupina voličů z roku {previousYear}</span>
            <select className="select block" value={source} onChange={(event) => pick(Number(event.target.value), target)}>
              {data.sources.map((name, index) => (
                <option key={name} value={index}>
                  {listName(name)}
                </option>
              ))}
            </select>
          </label>
          <span className="method-arrow" aria-hidden>
            →
          </span>
          <label>
            <span className="field-label">Kde mohli skončit v roce {currentYear}</span>
            <select className="select block" value={target} onChange={(event) => pick(source, Number(event.target.value))}>
              {data.targets.map((name, index) => (
                <option key={name} value={index}>
                  {listName(name)}
                </option>
              ))}
            </select>
          </label>
        </div>
      </section>

      <Step number={1} title="Z jednoho okrsku se to poznat nedá">
        <p className="method-text">
          O každém okrsku jsou známá dvě sčítání: kolik lidí koho volilo v roce {previousYear} a kolik v roce{" "}
          {currentYear}. Co se dělo mezi nimi, vidět není. Zkuste jezdcem měnit, kolik lidí z první skupiny skončilo ve
          druhé.
        </p>
        <OnePrecinct
          {...step}
          precinct={precinct}
          onAnother={() => setPickedPrecinct(Math.floor(Math.random() * count))}
        />
      </Step>

      <Step number={2} title={`Okrsků je ale ${fmtInt(count)} a každý je jiný`}>
        <p className="method-text">
          Každý bod je jeden okrsek. Vpravo jsou okrsky, kde hodně lidí{" "}
          {step.words.voted(5, data.sources[source], previousYear)}, vlevo ty, kde jich bylo málo. Čím je bod výš, tím
          víc lidí v tomtéž okrsku {step.words.voted(5, data.targets[target], currentYear)}. Když body směrem doprava
          stoupají, je těch druhých nejvíc tam, kde bylo hodně těch prvních. To napovídá, že jde z velké části o tytéž
          lidi.
        </p>
        <PrecinctCloud {...step} precinct={precinct} onPick={setPickedPrecinct} />
      </Step>

      <Step number={3} title="Hledá se tabulka přesunů, která sedí na všechny okrsky najednou">
        <p className="method-text">
          Tabulka říká, kolik procent každé skupiny z roku {previousYear} skončilo u které kandidátky nebo zůstalo
          doma. Použije se na každý okrsek zvlášť: z jeho výsledků v roce {previousYear} vyjde, jak by měl dopadnout v
          roce {currentYear}, a to se porovná se skutečností.
        </p>
        <p className="method-text">
          Hledání začíná u tabulky, která každou skupinu rozdělí rovnoměrně, a postupně ji upravuje, aby se body v grafu
          co nejvíc přimkly k čáře přesné shody. Žádný podíl přitom nesmí klesnout pod nulu a každý řádek musí dát
          dohromady 100 %.
        </p>
        <TableSearch key={`${election}-${code}-${area}`} {...step} model={model} snapshots={snapshots} onPick={pick} />
        <p className="note" style={{ marginTop: 14 }}>
          Kliknutím na políčko tabulky si vyberete jinou dvojici skupin.
          {flows.precinctTypes > 1 &&
            ` Okrsky jsou tu rozdělené do ${flows.precinctTypes} skupin podle toho, jak volily v roce ${previousYear}, a každá skupina má vlastní tabulku, protože voliči stejné kandidátky se v různých částech města nemusí chovat stejně. Vidíte jejich průměr za celé město.`}
        </p>
      </Step>

      <Step number={4} title="Nakolik se dá výsledku věřit">
        <p className="method-text">
          Kdyby odhad stál na několika málo okrscích, stačilo by je vynechat a vyšel by jinak. Celý výpočet se proto
          opakuje stokrát, pokaždé s jinak vylosovanými okrsky: některé se do losování dostanou víckrát, jiné vůbec.
          Každá tečka je výsledek jednoho opakování.
        </p>
        <Resampling
          key={`${election}-${code}-${area}`}
          {...step}
          model={model}
          result={snapshots[snapshots.length - 1].matrices}
        />
      </Step>

      <section className="card">
        <h2>Co odhad neumí</h2>
        <p className="method-text" style={{ marginTop: 10 }}>
          Celý postup stojí na předpokladu, že se voliči stejné kandidátky chovali v podobných okrscích podobně. Kde to
          neplatí, může se odhad mýlit, a rozpětí z losování takovou chybu nezachytí. Velkým přesunům se proto dá věřit
          víc než malým.
        </p>
        <button className="button" style={{ marginTop: 16 }} onClick={onBack}>
          Zpět na odhad přesunů
        </button>
      </section>
    </>
  );
}
