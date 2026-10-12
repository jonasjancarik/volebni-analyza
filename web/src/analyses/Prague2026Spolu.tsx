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

  const [loosest, firmest] = [fifths[0], fifths[fifths.length - 1]];
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
  const fromStanToPrahaSobe = scenario("stan-to-praha-sobe");
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
        <p>
          Nejsnáze se získávají hlasy, které strana nemá jisté, a těch má v Praze víc STAN než Spolu. Jádro Spolu
          drží: z jeho voličů z roku {years.previous} mu zůstalo {fmtPct(spoluKept.share, 0)} a k Praze Sobě nebo
          Pirátům odešlo jen asi {thousands(spoluToCamp)} lidí, zhruba stejně jako opačným směrem.
        </p>
        <p>
          Volní jsou hlavně lidé, kteří volí Spolu do Sněmovny, ale ne do zastupitelstva. Loni dostalo Spolu v Praze{" "}
          {thousands(spoluVotes)} hlasů, letos mělo {thousands(spolu.voters)} voličů. Největší část těch ostatních
          letos podle odhadu volila STAN.
        </p>
        <p>
          STAN má proto nejméně ukotvené voliče ze všech. {fmtPct(100 - stanOwn.origin, 0)} z nich ho před čtyřmi
          lety nevolilo a asi {thousands(stanFromPirati.people)} tvoří bývalí voliči Pirátů. Pro většinu STAN a Spolu
          je přitom jedno, které z obou kandidátek hlasy ubudou.
        </p>
        <p>
          Místně jsou voliči Spolu nejvolnější v okrscích, kde je silná Praha Sobě a Piráti a kde je nízká účast.
          Nejpevnější jsou v městských částech {names(byKept.slice(-2).reverse())}.
        </p>
      </section>

      <section className="prose">
        <h2>Jádro Spolu drží</h2>
        <p>
          Z lidí, kteří v roce {years.previous} volili Spolu, ho {fmtPct(spoluKept.share, 0)} volilo znovu. Skoro
          všichni ostatní přešli ke STAN ({fmtPct(spoluToStan.share, 0)}, asi {thousands(spoluToStan.people)}).
          K Praze Sobě a Pirátům jich odešlo {fmtPct(cell(flows, "spolu", "prahaSobe").share, 0)} a{" "}
          {fmtPct(cell(flows, "spolu", "pirati").share, 0)}, dohromady asi {thousands(spoluToCamp)}, a přibližně{" "}
          {thousands(campToSpolu)} lidí přišlo od nich ke Spolu.
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
          Místo těch, kdo odešli, získalo Spolu voliče jinde. Asi {fmtPct(cell(flows, "ano", "spolu").origin, 0)}{" "}
          jeho letošních voličů volilo v roce {years.previous} ANO a dalších{" "}
          {fmtPct(cell(flows, "nevolici", "spolu").origin, 0)} tehdy nevolilo. Přímá výměna voličů mezi Spolu
          a dvojicí Praha Sobě a Piráti je malá a vyrovnaná, takže z tohoto jádra se v minulých čtyřech letech
          získat nedalo.
        </p>
      </section>

      <section className="prose">
        <h2>Voliči, kteří volí Spolu jen do Sněmovny</h2>
        <p>
          Mnohem větší skupinu tvoří lidé, kteří Spolu volí ve sněmovních volbách, ale v komunálních ne. Loni v říjnu
          dostalo Spolu v Praze {thousands(spoluVotes)} hlasů. Letos mělo {thousands(spolu.voters)} voličů, tedy
          nanejvýš {fmtPct(keptAtMost, 0)} z nich, i kdyby žádný jeho letošní volič nebyl nový. Nejméně{" "}
          {thousands(elsewhere)} lidí, kteří loni volili Spolu, letos volilo někoho jiného nebo nepřišlo.
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
          U STAN je to obráceně. Letos ho volilo asi {thousands(stan.voters)} lidí, víc než loni do Sněmovny (
          {thousands(stanVotes)}), přestože k volbám přišlo o {fmtPct(turnoutDrop, 0)} méně voličů.
        </p>
        <p>
          Kam loňští voliči Spolu šli, ukazuje odhad přesunů od sněmovních voleb. Je hrubší než odhad mezi dvojími
          komunálními volbami, u velké skupiny, jako jsou voliči Spolu, je ale stabilnější než u menších stran.
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
          Podle odhadu jich {fmtPct(earlierSpolu("spolu").share, 0)} volilo Spolu a{" "}
          {fmtPct(earlierSpolu("stan").share, 0)} STAN (rozmezí{" "}
          {fmtRange(earlierSpolu("stan").low, earlierSpolu("stan").high)}). Zbylá třetina se dělí mezi Prahu Sobě,
          Piráty, malé kandidátky a ty, kdo nepřišli. Jak přesně, je nejisté: podíl pro Piráty je spíš nadsazený, ze
          stejného důvodu, z jakého{" "}
          <Link className="inline-link" to="/analyzy/praha-2026-pirati-praha-sobe">
            první analýza
          </Link>{" "}
          podhodnocuje věrnost loňských voličů Pirátů.
        </p>
        <p>
          Jisté je to hlavní. Většina sněmovních voličů Spolu v komunálních volbách Spolu nevolí a největší díl z nich
          letos připadl STAN.
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
          Rozdíl mezi sněmovním a komunálním výsledkem Spolu tedy není v účasti. Jeho voliči ke komunálním volbám
          chodí, podle odhadu nejvíc ze všech stran, jen v nich často volí jinou kandidátku. U Pirátů, ANO a SPD je
          to naopak: velká část jejich sněmovních voličů zůstává doma.
        </p>
        <p>
          Velikost rozdílu mezi stranami model nejspíš přehání, pořadí je ale při každém nastavení výpočtu stejné.
          Lidi, kteří loni v Praze hlasovali na voličský průkaz a komunálně tu volit nemohou, odhad neodliší od těch,
          kdo nepřišli.
        </p>
      </section>

      <section className="prose">
        <h2>STAN má nové voliče</h2>
        <p>
          Z letošních voličů STAN ho v roce {years.previous} volilo jen {fmtPct(stanOwn.origin, 0)}. Ostatní přišli od
          Spolu ({fmtPct(stanFromSpolu.origin, 0)}), od Pirátů ({fmtPct(stanFromPirati.origin, 0)}, asi{" "}
          {thousands(stanFromPirati.people)} lidí) a v menší míře odjinud.
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
          Ani sněmovní voliči STAN mu nejsou v komunálních volbách věrní. Z těch, kdo ho volili loni, mu letos dalo
          hlas {fmtPct(earlierStan("stan").share, 0)} (rozmezí{" "}
          {fmtRange(earlierStan("stan").low, earlierStan("stan").high)}),{" "}
          {fmtPct(earlierStan("prahaSobe").share, 0)} volilo Prahu Sobě a {fmtPct(earlierStan("pirati").share, 0)}{" "}
          Piráty.
        </p>
        <p>
          STAN navíc posílil všude stejně. Ve všech pětinách okrsků v tabulce níže má {fmtNum(Math.min(...stanShares))}{" "}
          až {fmtPct(Math.max(...stanShares))} hlasů, ať je tam Spolu, Praha Sobě nebo Piráti silní, nebo slabí.
          Takto rovnoměrný zisk naznačuje, že voliče přivedla celoměstská kampaň, ne vazba na konkrétní místo.
        </p>
      </section>

      <section className="prose">
        <h2>Kde jsou voliči Spolu nejvolnější</h2>
        <p>
          Rozdíly se nejlépe ukážou na okrscích seřazených podle toho, kolik svých loňských sněmovních voličů si
          v nich Spolu letos udrželo.
        </p>
      </section>

      <Figure
        title="Okrsky podle toho, kolik sněmovních voličů si v nich Spolu udrželo"
        sub={`V každé pětině je asi ${loosest.precincts} okrsků. Podíly jsou v procentech hlasů, změna v procentních bodech.`}
      >
        <HeatTable rows={fifths} rowHead="Okrsky" rowLabel={(row) => FIFTHS[fifths.indexOf(row)]} columns={fifthColumns} />
      </Figure>

      <section className="prose">
        <p>
          V pětině okrsků, kde si Spolu udrželo nejméně ({fmtPct(kept(loosest, "spolu"), 0)}), má Praha Sobě{" "}
          {fmtPct(share(loosest, "prahaSobe", "now"))} a Piráti {fmtPct(share(loosest, "pirati", "now"))}, účast je
          tam nejnižší a Spolu od roku {years.previous} ztratilo{" "}
          {fmtNum(share(loosest, "spolu", "then") - share(loosest, "spolu", "now"))} bodu. V pětině, kde si udrželo
          nejvíc ({fmtPct(kept(firmest, "spolu"), 0)}), má Praha Sobě {fmtPct(share(firmest, "prahaSobe", "now"))}{" "}
          a Spolu neoslabilo.
        </p>
        <p>
          Voliči Spolu tedy odcházejí ke STAN všude, a kde je silná Praha Sobě a Piráti, odcházejí navíc i k nim.
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
          Mezi městskými částmi jsou rozdíly menší než mezi okrsky. Nejméně loňských voličů si Spolu udrželo
          v částech {names(byKept.slice(0, 3))}, nejvíc v částech {names(byKept.slice(-2).reverse())}. V Praze 9 je
          starostou lídr Spolu Tomáš Portlík.
        </p>
        <p>
          Kam až to může dojít, ukazuje {campBest.name}. Praha Sobě s Piráty tam mají o{" "}
          {fmtPct(campOverPirati(campBest), 0)} víc voličů, než kolik hlasů dostali Piráti loni do Sněmovny, a Spolu
          si udrželo {fmtPct(kept(campBest, "spolu"), 0)} svých.
        </p>
      </section>

      <section className="prose">
        <h2>Kde voliči Pirátů odešli ke STAN</h2>
        <p>
          Asi {thousands(stanFromPirati.people)} letošních voličů STAN volilo v roce {years.previous} Piráty. Odhad
          pro jednotlivé městské části je hrubý, protože se opírá o desítky okrsků místo tisíce, a jde jen pro{" "}
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
        <p>
          K tomu, aby STAN a Spolu neměly většinu {majority} mandátů, by stačilo{" "}
          {hundreds(fromSpoluToPrahaSobe.voters ?? 0)} voličů Spolu, kteří by volili Prahu Sobě, nebo{" "}
          {hundreds(fromSpoluToPirati.voters ?? 0)}, kteří by volili Piráty. U voličů STAN vycházejí skoro stejná
          čísla, {hundreds(fromStanToPrahaSobe.voters ?? 0)} a {hundreds(fromStanToPirati.voters ?? 0)}.
        </p>
      </section>

      <Figure
        title="Nejmenší přesun voličů, po kterém STAN a Spolu nemají většinu"
        sub="Přepočet mandátů podle stejných pravidel; všechno, co řádek nezmiňuje, zůstává jako ve skutečnosti"
      >
        <ScenarioTable scenarios={data.scenarios} majority={majority} describe={describe} />
      </Figure>

      <section className="prose">
        <p>
          Je to {fmtNum(((fromSpoluToPrahaSobe.voters ?? 0) / elsewhere) * 100, 0)} až{" "}
          {fmtPct(((fromSpoluToPirati.voters ?? 0) / elsewhere) * 100, 0)} z lidí, kteří loni volili Spolu do Sněmovny
          a letos do zastupitelstva ne. U STAN by stačilo, aby se k Pirátům vrátilo{" "}
          {fmtPct(((fromStanToPirati.voters ?? 0) / stanFromPirati.people) * 100, 0)} jejich bývalých voličů, kteří
          letos volili STAN.
        </p>
      </section>

      <section className="prose">
        <h2>Co z toho plyne</h2>
        <p>
          U Spolu nejsou volné hlasy jeho voličů z komunálních voleb, ti drží. Volní jsou lidé, kteří ho volí jen do
          Sněmovny, a největší část z nich letos získal STAN.
        </p>
        <p>
          O tyto voliče se proto soupeří hlavně se STAN. Jeho elektorát je ze tří čtvrtin nový, rovnoměrně rozložený
          po městě a zčásti složený z bývalých voličů Pirátů. Hlas, který STAN ztratí, zmenšuje většinu STAN a Spolu
          stejně jako hlas, který ztratí Spolu.
        </p>
        <p>
          Nejvíc voličů Spolu, kteří v komunálních volbách volí jinak, je v okrscích se silnou Prahou Sobě a Piráty
          a s nízkou účastí. Tam, kde má Spolu vlastní místní oporu, jako v Praze 9, se drží nejlépe.
        </p>
        <p>
          Výsledky ukazují, kde se voliči přesouvali, ne proč a za jakých podmínek by to udělali znovu. Na to jsou
          potřeba průzkumy.
        </p>
      </section>

      <section className="card method-notes">
        <h3>Jak se to počítalo</h3>
        <p className="note">
          Počty voličů v komunálních volbách jsou přepočtené z hlasů: podíl kandidátky na hlasech krát počet
          odevzdaných obálek. Podíl, který si Spolu udrželo, je poměr jeho letošních voličů k loňským sněmovním
          hlasům. Je to horní odhad, protože mezi letošními voliči Spolu jsou i lidé, kteří ho loni nevolili.
        </p>
        <p className="note">
          Přesuny voličů jsou odhad, ne měření. Odhad mezi roky {years.previous} a {years.current} pracuje s{" "}
          {fmtInt(flows.matched)} okrsky a vystihuje {fmtPct(flows.explained, 0)} rozdílů mezi nimi. Odhad od
          sněmovních voleb vystihuje {fmtPct(earlier.explained, 0)} a jeho rozmezí pokrývají i různá nastavení výpočtu.
        </p>
        <p className="note">
          Odhady pro městské části používají jen jejich okrsky, {fmtInt(Math.min(...districtFlows.map((item) => item.flows.matched)))}{" "}
          až {fmtInt(Math.max(...districtFlows.map((item) => item.flows.matched)))}, a u těch s méně než stovkou
          okrsků se mohou lišit o desítky procentních bodů.
        </p>
        <Link className="button" style={{ marginTop: 16, display: "inline-block" }} to={`${councilPath}/presuny`}>
          Otevřít přesuny voličů v aplikaci
        </Link>
      </section>
    </>
  );
}
