import { Link } from "react-router-dom";
import { FlowBars } from "../components/FlowBars";
import { fmtInt, fmtNum, fmtPct, fmtRange } from "../format";
import {
  cell,
  destinations,
  ElectionBars,
  Figure,
  groupColors,
  type HeatColumn,
  HeatTable,
  hundreds,
  origins,
  ScenarioTable,
  SplitBar,
  StayedHomeTable,
  thousands,
} from "./blocks";
import type { Scenario, SpoluStanAnalysis, VoterGroup } from "./types";

type When = "then" | "mid" | "now";

const FIFTHS = [
  "kde si Spolu udrželo nejméně",
  "druhá pětina",
  "prostřední pětina",
  "čtvrtá pětina",
  "kde si Spolu udrželo nejvíc",
];

const voters = (group: VoterGroup, key: string, when: When) => group.voters[key]?.[when] ?? 0;
/** Share of those who voted, in percent */
const share = (group: VoterGroup, key: string, when: When) => (voters(group, key, when) / group.voted[when]) * 100;
/** How many of its parliamentary voters a list had in the municipal election a year later, in percent */
const kept = (group: VoterGroup, key: string) => (voters(group, key, "now") / voters(group, key, "mid")) * 100;
const camp = (group: VoterGroup, when: When) => voters(group, "pirati", when) + voters(group, "prahaSobe", when);

const pct = (value: number) => fmtNum(value);
const whole = (value: number) => fmtNum(value, 0);
const signed = (value: number) => `${value > 0 ? "+" : value < 0 ? "−" : ""}${fmtNum(Math.abs(value))}`;
const inThousands = (value: number) => fmtNum(value / 1000);

export function Prague2026Spolu({ data }: { data: SpoluStanAnalysis }) {
  const { years, majority, flows, city, fifths, districts, districtFlows } = data;
  const earlier = data.parliamentary.flows;
  const colorOf = groupColors(data.lists);
  const list = (key: string) => data.lists.find((item) => item.key === key)!;
  const earlierList = (key: string) => data.parliamentary.lists.find((item) => item.key === key)!;
  const scenario = (key: string) => data.scenarios.find((item) => item.key === key)!;
  const [spolu, stan] = [list("spolu"), list("stan")];
  const councilPath = `/${data.council.election}/${data.council.code}`;

  const spoluKept = cell(flows, "spolu", "spolu");
  const spoluToStan = cell(flows, "spolu", "stan");
  const spoluToCamp = cell(flows, "spolu", "prahaSobe").people + cell(flows, "spolu", "pirati").people;
  const campToSpolu = cell(flows, "prahaSobe", "spolu").people + cell(flows, "pirati", "spolu").people;
  const stanOwn = cell(flows, "stan", "stan");
  const stanFromPirati = cell(flows, "pirati", "stan");
  const stanFromSpolu = cell(flows, "spolu", "stan");

  const spoluVotes = earlierList("spolu").votes;
  const stanVotes = earlierList("stan").votes;
  const keptAtMost = (spolu.voters / spoluVotes) * 100;
  const elsewhere = spoluVotes - spolu.voters;
  const turnoutDrop = (1 - data.summary.ballots / data.parliamentary.summary.ballots) * 100;
  const earlierSpolu = (target: string) => cell(earlier, "spolu", target);
  const earlierStan = (target: string) => cell(earlier, "stan", target);

  const loosest = fifths[0];
  const stanShares = fifths.map((fifth) => share(fifth, "stan", "now"));
  const large = districts.slice(0, 15);
  const byKept = [...large].sort((a, b) => kept(a, "spolu") - kept(b, "spolu"));
  // "Praha 1, Praha 5 a Praha 7"
  const names = (rows: typeof large) =>
    rows.map((row, index) => (index === 0 ? "" : index === rows.length - 1 ? " a " : ", ") + row.name).join("");
  const campOverPirati = (group: VoterGroup) => (camp(group, "now") / voters(group, "pirati", "mid") - 1) * 100;
  const campBest = [...large].sort((a, b) => campOverPirati(b) - campOverPirati(a))[0];

  const fromSpoluToPrahaSobe = scenario("spolu-to-praha-sobe");
  const fromSpoluToPirati = scenario("spolu-to-pirati");
  const fromStanToPirati = scenario("stan-to-pirati");
  const describe = (item: Scenario): { title: string; detail?: string } => {
    const people = hundreds(item.voters ?? 0);
    const detail = item.voters
      ? `${fmtPct((item.voters / data.summary.ballots) * 100)} těch, kdo přišli volit`
      : undefined;
    switch (item.key) {
      case "actual":
        return { title: "Skutečný výsledek" };
      case "spolu-to-praha-sobe":
        return { title: `${people} voličů Spolu volí Prahu Sobě`, detail };
      case "spolu-to-pirati":
        return { title: `${people} voličů Spolu volí Piráty`, detail };
      case "stan-to-praha-sobe":
        return { title: `${people} voličů STAN volí Prahu Sobě`, detail };
      default:
        return { title: `${people} voličů STAN volí Piráty`, detail };
    }
  };

  const fifthColumns: HeatColumn<VoterGroup>[] = [
    { group: "Spolu", head: "udrželo", value: (row) => kept(row, "spolu"), format: (value) => `${whole(value)} %`, tint: colorOf("spolu") },
    { group: "Spolu", head: years.previous, value: (row) => share(row, "spolu", "then"), format: pct },
    { group: "Spolu", head: years.current, value: (row) => share(row, "spolu", "now"), format: pct },
    { group: "Spolu", head: "změna", value: (row) => share(row, "spolu", "now") - share(row, "spolu", "then"), format: signed, tint: "change" },
    { group: "Praha Sobě", head: years.current, value: (row) => share(row, "prahaSobe", "now"), format: pct, tint: colorOf("prahaSobe") },
    { group: "Piráti", head: years.current, value: (row) => share(row, "pirati", "now"), format: pct, tint: colorOf("pirati") },
    { group: "STAN", head: years.current, value: (row) => share(row, "stan", "now"), format: pct, tint: colorOf("stan") },
    { group: "ANO", head: years.current, value: (row) => share(row, "ano", "now"), format: pct, tint: colorOf("ano") },
    { group: "Účast", head: years.current, value: (row) => (row.voted.now / row.registered) * 100, format: pct },
  ];

  const districtColumns: HeatColumn<(typeof districts)[number]>[] = [
    { group: "Spolu, tisíce voličů", head: `Sněmovna ${years.parliamentary}`, value: (row) => voters(row, "spolu", "mid"), format: inThousands },
    { group: "Spolu, tisíce voličů", head: `město ${years.current}`, value: (row) => voters(row, "spolu", "now"), format: inThousands },
    { group: "Spolu, tisíce voličů", head: "jinde nebo doma", value: (row) => voters(row, "spolu", "mid") - voters(row, "spolu", "now"), format: inThousands, tint: colorOf("spolu") },
    { group: "Spolu", head: "udrželo", value: (row) => kept(row, "spolu"), format: (value) => `${whole(value)} %` },
    { group: "Spolu", head: `změna od ${years.previous}`, value: (row) => share(row, "spolu", "now") - share(row, "spolu", "then"), format: signed, tint: "change" },
    { group: "STAN", head: "proti Sněmovně", value: (row) => kept(row, "stan"), format: (value) => `${whole(value)} %`, tint: colorOf("stan") },
    { group: "Praha Sobě + Piráti", head: years.current, value: (row) => share(row, "prahaSobe", "now") + share(row, "pirati", "now"), format: pct, tint: colorOf("prahaSobe") },
  ];

  return (
    <>
      <div className="tiles article-tiles">
        <div className="tile">
          <div className="value num">{fmtPct(spoluKept.share, 0)}</div>
          <div className="label">voličů Spolu z roku {years.previous} ho letos volilo znovu</div>
        </div>
        <div className="tile">
          <div className="value num">{fmtPct(keptAtMost, 0)}</div>
          <div className="label">
            loňských sněmovních voličů Spolu ho nanejvýš volilo i do zastupitelstva
          </div>
        </div>
        <div className="tile">
          <div className="value num">{fmtPct(100 - stanOwn.origin, 0)}</div>
          <div className="label">letošních voličů STAN ho v roce {years.previous} nevolilo</div>
        </div>
        <div className="tile">
          <div className="value num">
            {hundreds(fromSpoluToPrahaSobe.voters ?? 0)}–{hundreds(fromSpoluToPirati.voters ?? 0)}
          </div>
          <div className="label">voličů Spolu by muselo volit Prahu Sobě nebo Piráty, aby STAN a Spolu neměly většinu</div>
        </div>
      </div>

      <section className="prose">
        <h2>Shrnutí</h2>
        <ul className="takeaways">
          <li>
            Komunální voliči Spolu drží. Z těch z roku {years.previous} mu zůstalo {fmtPct(spoluKept.share, 0)}{" "}
            a výměna s Prahou Sobě a Piráty je vyrovnaná, asi {thousands(spoluToCamp)} lidí každým směrem.
          </li>
          <li>
            Volní jsou lidé, kteří volí Spolu jen do Sněmovny. Loni dostalo v Praze {thousands(spoluVotes)} hlasů,
            letos mělo {thousands(spolu.voters)} voličů, a největší část těch ostatních letos volila STAN. Nejvíc
            jich je v okrscích, kde je silná Praha Sobě a Piráti a nízká účast.
          </li>
          <li>
            STAN má proto nejméně ukotvené voliče: {fmtPct(100 - stanOwn.origin, 0)} z nich ho před čtyřmi lety
            nevolilo a asi {thousands(stanFromPirati.people)} jsou bývalí voliči Pirátů.
          </li>
          <li>
            O volné voliče se tedy soupeří hlavně se STAN. Hlas, který ztratí STAN, zmenšuje většinu STAN a Spolu
            stejně jako hlas, který ztratí Spolu.
          </li>
        </ul>
      </section>

      <section className="prose">
        <h2>Jádro Spolu drží</h2>
        <p>
          Z voličů Spolu z roku {years.previous} ho {fmtPct(spoluKept.share, 0)} volilo znovu a{" "}
          {fmtPct(spoluToStan.share, 0)}, asi {thousands(spoluToStan.people)}, přešlo ke STAN. K Praze Sobě
          a Pirátům odešlo asi {thousands(spoluToCamp)} lidí a {thousands(campToSpolu)} přišlo opačným směrem.
        </p>
      </section>

      <Figure
        title={`Voliči Spolu mezi roky ${years.previous} a ${years.current}`}
        sub="Odhad přesunů voličů. Šedě je rozmezí, ve kterém se odhad pohybuje."
      >
        <div className="grid half">
          <div>
            <h4 className="split-title">Jak letos volili voliči Spolu z roku {years.previous}</h4>
            <SplitBar parts={destinations(flows, "spolu").map(({ people: _, ...part }) => part)} colorOf={colorOf} />
          </div>
          <div>
            <h4 className="split-title">Koho v roce {years.previous} volili letošní voliči Spolu</h4>
            <SplitBar parts={origins(flows, "spolu").map(({ people: _, ...part }) => part)} colorOf={colorOf} />
          </div>
        </div>
      </Figure>

      <section className="prose">
        <p>
          Místo odešlých získalo Spolu voliče ANO ({fmtPct(cell(flows, "ano", "spolu").origin, 0)} jeho letošních
          voličů) a lidi, kteří minule nevolili ({fmtPct(cell(flows, "nevolici", "spolu").origin, 0)}).
        </p>
      </section>

      <section className="prose">
        <h2>Voliči, kteří volí Spolu jen do Sněmovny</h2>
        <p>
          Loni v říjnu dostalo Spolu v Praze {thousands(spoluVotes)} hlasů. Letos mělo {thousands(spolu.voters)}{" "}
          voličů, tedy nanejvýš {fmtPct(keptAtMost, 0)} z nich. Nejméně {thousands(elsewhere)} lidí, kteří loni volili
          Spolu, letos volilo někoho jiného nebo nepřišlo.
        </p>
      </section>

      <Figure
        title="Kolik lidí volilo kandidátku ve třech volbách"
        sub="Hlasy v komunálních volbách jsou přepočtené na voliče. Sněmovní volby jsou světlejší, volí se v nich jinak a přijde víc lidí."
      >
        <ElectionBars
          elections={[`město ${years.previous}`, `Sněmovna ${years.parliamentary}`, `město ${years.current}`]}
          rows={["spolu", "stan", "prahaSobe", "pirati"].map((key) => ({
            key,
            // Parliamentary votes are counted, not converted, so they match the official result
            values: (["then", "mid", "now"] as When[]).map((when) =>
              when === "mid"
                ? (data.parliamentary.lists.find((item) => item.key === key)?.votes ?? null)
                : (city.voters[key]?.[when] ?? null),
            ),
          }))}
          colorOf={colorOf}
        />
      </Figure>

      <section className="prose">
        <p>
          U STAN je to obráceně: letos ho volilo víc lidí ({thousands(stan.voters)}) než loni do Sněmovny (
          {thousands(stanVotes)}), přestože k volbám přišlo o {fmtPct(turnoutDrop, 0)} méně voličů.
        </p>
      </section>

      <Figure
        title={`Jak letos volili ti, kdo v roce ${years.parliamentary} volili do Sněmovny Spolu`}
        sub="Odhad přesunů voličů. Rozmezí zahrnují i různá nastavení výpočtu."
      >
        <SplitBar parts={destinations(earlier, "spolu")} colorOf={colorOf} peopleLabel="lidí" />
      </Figure>

      <section className="prose">
        <p>
          Podle odhadu {fmtPct(earlierSpolu("spolu").share, 0)} loňských voličů Spolu volilo Spolu a{" "}
          {fmtPct(earlierSpolu("stan").share, 0)} STAN (rozmezí{" "}
          {fmtRange(earlierSpolu("stan").low, earlierSpolu("stan").high)}). Jak se dělí zbylá třetina, je nejisté;
          podíl pro Piráty je spíš nadsazený, ze stejného důvodu, z jakého{" "}
          <Link className="inline-link" to="/analyzy/praha-2026-pirati-praha-sobe">
            první analýza
          </Link>{" "}
          podhodnocuje věrnost loňských voličů Pirátů.
        </p>
      </section>

      <Figure
        title="Kolik loňských voličů letos k volbám nepřišlo"
        sub={`Voliči stran ze sněmovních voleb ${years.parliamentary}, kteří v komunálních volbách ${years.current} nevolili. Celkem letos přišlo o ${fmtPct(turnoutDrop, 0)} méně lidí.`}
      >
        <StayedHomeTable flows={earlier} parties={data.parliamentary.lists} colorOf={colorOf} />
      </Figure>

      <section className="prose">
        <p>
          Rozdíl mezi oběma výsledky Spolu tedy není v účasti. Jeho voliči ke komunálním volbám chodí, jen v nich
          často volí jinou kandidátku. Velikost rozdílu mezi stranami model nejspíš přehání, pořadí se ale nemění.
        </p>
      </section>

      <section className="prose">
        <h2>STAN má nové voliče</h2>
        <p>
          Z letošních voličů STAN ho v roce {years.previous} volilo jen {fmtPct(stanOwn.origin, 0)}.{" "}
          {fmtPct(stanFromSpolu.origin, 0)} přišlo od Spolu a {fmtPct(stanFromPirati.origin, 0)}, asi{" "}
          {thousands(stanFromPirati.people)} lidí, od Pirátů.
        </p>
      </section>

      <Figure title="Z koho se skládají letošní voliči STAN" sub="Odhad; šedě rozmezí, ve kterém se pohybuje">
        <div className="grid half">
          <div>
            <h4 className="split-title">Podle volby do zastupitelstva v roce {years.previous}</h4>
            <SplitBar parts={origins(flows, "stan").map(({ people: _, ...part }) => part)} colorOf={colorOf} />
          </div>
          <div>
            <h4 className="split-title">Podle volby do Sněmovny v roce {years.parliamentary}</h4>
            <SplitBar parts={origins(earlier, "stan").map(({ people: _, ...part }) => part)} colorOf={colorOf} />
          </div>
        </div>
      </Figure>

      <section className="prose">
        <p>
          Ani sněmovní voliči STAN mu nejsou věrní. Z těch loňských ho letos volilo{" "}
          {fmtPct(earlierStan("stan").share, 0)} (rozmezí {fmtRange(earlierStan("stan").low, earlierStan("stan").high)}
          ), {fmtPct(earlierStan("prahaSobe").share, 0)} volilo Prahu Sobě a {fmtPct(earlierStan("pirati").share, 0)}{" "}
          Piráty.
        </p>
        <p>
          STAN navíc posílil všude stejně: ve všech pětinách okrsků v tabulce níže má {fmtNum(Math.min(...stanShares))}{" "}
          až {fmtPct(Math.max(...stanShares))} hlasů. Takto rovnoměrný zisk naznačuje celoměstskou vlnu, ne vazbu na
          konkrétní místo.
        </p>
      </section>

      <section className="prose">
        <h2>Kde jsou voliči Spolu nejvolnější</h2>
      </section>

      <Figure
        title="Okrsky podle toho, kolik sněmovních voličů si v nich Spolu udrželo"
        sub={`V každé pětině je asi ${loosest.precincts} okrsků. Podíly jsou v procentech hlasů, změna v procentních bodech.`}
      >
        <HeatTable rows={fifths} rowHead="Okrsky" rowLabel={(row) => FIFTHS[fifths.indexOf(row)]} columns={fifthColumns} />
      </Figure>

      <section className="prose">
        <p>
          Kde si Spolu udrželo nejméně sněmovních voličů, je silná Praha Sobě a Piráti, nízká účast a Spolu tam od
          roku {years.previous} ztratilo {fmtNum(share(loosest, "spolu", "then") - share(loosest, "spolu", "now"))}{" "}
          bodu. Voliči Spolu tedy odcházejí ke STAN všude, a kde je silná Praha Sobě a Piráti, i k nim.
        </p>
      </section>

      <Figure
        title="Městské části podle toho, kolik sněmovních voličů si Spolu udrželo"
        sub="Patnáct největších městských částí, od nejnižšího podílu"
        note={
          <>
            „Jinde nebo doma“ je rozdíl mezi loňskými hlasy pro Spolu a jeho letošními voliči. U STAN je uvedeno,
            kolik procent loňských sněmovních hlasů představují jeho letošní voliči.{" "}
            <Link className="inline-link" to={`${councilPath}/mapa?m=zmena&zm=${encodeURIComponent(spolu.name)}`}>
              Podívat se na mapu změny Spolu po okrscích
            </Link>
          </>
        }
      >
        <HeatTable rows={byKept} rowHead="Městská část" rowLabel={(row) => row.name} columns={districtColumns} />
      </Figure>

      <section className="prose">
        <p>
          Mezi městskými částmi jsou rozdíly menší. Nejméně si Spolu udrželo v částech {names(byKept.slice(0, 3))},
          nejvíc v částech {names(byKept.slice(-2).reverse())}; v Praze 9 je starostou jeho lídr Tomáš Portlík.
        </p>
        <p>
          Kam až to může dojít, ukazuje {campBest.name}: Praha Sobě s Piráty tam mají o{" "}
          {fmtPct(campOverPirati(campBest), 0)} víc voličů, než kolik hlasů dostali Piráti loni do Sněmovny.
        </p>
      </section>

      <section className="prose">
        <h2>Kde voliči Pirátů odešli ke STAN</h2>
        <p>
          Odhad pro městské části je hrubý, opírá se o desítky okrsků místo tisíce a jde jen pro{" "}
          {districtFlows.length} největších.
        </p>
      </section>

      <Figure
        title={`Kolik voličů Pirátů z roku ${years.previous} letos volilo STAN`}
        sub="Podíl v městské části. Šedě a čárou je rozmezí odhadu; čím je širší, tím méně se dá číslu věřit."
      >
        <FlowBars
          bars={districtFlows.map((district) => {
            const moved = cell(district.flows, "pirati", "stan");
            return {
              name: district.name,
              label: `${district.name}, asi ${fmtInt(Math.round(moved.people / 100) * 100)} lidí`,
              color: colorOf("stan"),
              value: moved.share,
              low: moved.low,
              high: moved.high,
            };
          })}
        />
      </Figure>

      <section className="prose">
        <h2>Kolik by stačilo</h2>
      </section>

      <Figure
        title="Nejmenší přesun voličů, po kterém STAN a Spolu nemají většinu"
        sub="Přepočet mandátů podle stejných pravidel; všechno, co řádek nezmiňuje, zůstává jako ve skutečnosti"
      >
        <ScenarioTable scenarios={data.scenarios} majority={majority} describe={describe} />
      </Figure>

      <section className="prose">
        <p>
          U Spolu je to {fmtNum(((fromSpoluToPrahaSobe.voters ?? 0) / elsewhere) * 100, 0)} až{" "}
          {fmtPct(((fromSpoluToPirati.voters ?? 0) / elsewhere) * 100, 0)} z lidí, kteří ho loni volili do Sněmovny
          a letos do zastupitelstva ne. U STAN by stačilo, aby se k Pirátům vrátilo{" "}
          {fmtPct(((fromStanToPirati.voters ?? 0) / stanFromPirati.people) * 100, 0)} jejich bývalých voličů.
        </p>
      </section>

      <section className="prose">
        <h2>Co z toho plyne</h2>
        <p>
          Komunální voliči Spolu drží. Volní jsou lidé, kteří ho volí jen do Sněmovny, a největší část z nich letos
          získal STAN.
        </p>
        <p>
          O ně se proto soupeří hlavně se STAN, jehož elektorát je ze tří čtvrtin nový. Hlas, který ztratí STAN,
          zmenšuje většinu STAN a Spolu stejně jako hlas, který ztratí Spolu.
        </p>
        <p>
          Výsledky ukazují, kde se voliči přesouvali, ne proč a jestli by to udělali znovu.
        </p>
      </section>

      <section className="card method-notes">
        <h3>Jak se to počítalo</h3>
        <p className="note">
          Počty voličů v komunálních volbách jsou přepočtené z hlasů. Podíl, který si Spolu udrželo, je poměr jeho
          letošních voličů k loňským sněmovním hlasům; je to horní odhad, protože část letošních voličů ho loni
          nevolila.
        </p>
        <p className="note">
          Přesuny voličů jsou odhad, ne měření. Odhad od sněmovních voleb je hrubší a jeho rozmezí pokrývají i různá
          nastavení výpočtu. Odhady pro městské části se u těch s méně než stovkou okrsků mohou lišit o desítky
          procentních bodů.
        </p>
        <Link className="button" style={{ marginTop: 16, display: "inline-block" }} to={`${councilPath}/presuny`}>
          Otevřít přesuny voličů v aplikaci
        </Link>
      </section>
    </>
  );
}
