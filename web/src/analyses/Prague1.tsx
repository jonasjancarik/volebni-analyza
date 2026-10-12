import { lazy, Suspense } from "react";
import { Loading } from "../components/State";
import { fmtInt, fmtNum, fmtPct } from "../format";
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
  type BallotPair,
  ballotRows,
  inCount,
  ordinal,
  pct,
  PrecinctList,
  seatsWord,
  tens,
  TwoBallots,
} from "./districtBlocks";
import { type Area, change, type DistrictAnalysis, localOverCity, together } from "./districtShared";
import "./district.css";

// The map library is large; it loads only when the article is opened
const DistrictMap = lazy(() => import("./DistrictMap"));

export interface Prague1Analysis extends DistrictAnalysis {
  /** For every list, the fewest extra votes for one more seat and the list that would lose it; from the closest */
  margins: { key: string; seats: number; votes: number; voters: number; from: string }[];
}

/** The lists in three groups, in the order the chart of seats shows them */
const GROUPS = [
  { key: "townHall", name: "Radniční koalice bez Pirátů", lists: ["ods", "top09", "nasePraha1", "rezidenti", "nezavisli"] },
  { key: "pirati", name: "Piráti", lists: ["pirati"] },
  { key: "others", name: "Praha 1 Sobě, STAN a KDU-ČSL", lists: ["praha1Sobe", "stanKdu"] },
];

const GROUP_COLORS: Record<string, string> = {
  malaStrana: "#7d9a35",
  stareMesto: "#a4573c",
  noveMesto: "#62788f",
};

/** Lists that have no colour of their own in Praha 1 take that of their closest relative */
const SAME_COLOR: Record<string, string> = { prahaSobe: "praha1Sobe", spolu: "ods", odsTop: "ods", stan: "stanKdu", ano: "nasePraha1" };

const PAIRS: BallotPair[] = [
  { key: "praha1Sobe", name: "Praha 1 Sobě", cityName: "Praha Sobě", local: ["praha1Sobe"], city: ["prahaSobe"], previous: ["praha1Sobe", "prahaSobe"] },
  { key: "ods", name: "ODS a TOP 09", cityName: "Spolu (ODS a TOP 09)", local: ["ods", "top09"], city: ["spolu"] },
  { key: "stanKdu", name: "STAN a KDU-ČSL", cityName: "STAN", local: ["stanKdu"], city: ["stan"], previous: ["stanKdu", "stan"] },
  { key: "pirati", name: "Piráti", local: ["pirati"], city: ["pirati"], previous: ["pirati", "pirati"] },
  { key: "nasePraha1", name: "Naše Praha 1 (ANO)", cityName: "ANO", local: ["nasePraha1"], city: ["ano"], previous: ["nasePraha1", "ano"] },
  { key: "nezavisli", name: "Nezávislí z Jedničky", local: ["nezavisli"], city: [] },
  { key: "modra", name: "Modrá pro jedničku", local: ["modra"], city: [] },
  { key: "rezidenti", name: "Rezidenti 1", local: ["rezidenti"], city: [] },
  { key: "motoriste", name: "Motoristé a Svobodní", cityName: "Motoristé", local: ["motoriste"], city: ["motoriste"] },
  { key: "spd", name: "SPD", local: ["spd"], city: ["spd"] },
];

const SHARES = ["praha1Sobe", "ods", "stanKdu", "top09", "pirati", "nasePraha1"];

export function Prague1({ data }: { data: Prague1Analysis }) {
  const { years, seats, majority, district, precincts, groups, counts, turnout } = data;
  const ownColor = groupColors(data.lists);
  const colorOf = (key: string) => ownColor(SAME_COLOR[key] ?? key);
  const councilPath = `/${data.council.election}/${data.council.code}`;

  const list = (key: string) => data.lists.find((item) => item.key === key)!;
  const pirati = list("pirati");
  const previousList = (key: string) => data.previousLists.find((item) => item.key === key);
  const bloc = (key: string) => data.blocs.find((item) => item.key === key)!;
  const [townHall, piratiSeats, others] = [bloc("townHall"), bloc("pirati"), bloc("others")];
  const margin = (key: string) => data.margins.find((item) => item.key === key);
  const closest = data.margins[0];
  const piratiMargin = margin("pirati");
  const sameLoser = data.margins.filter((item) => item.from === data.lastSeat.key).length;
  const eitherWithPirati = [townHall, others].every((side) => side.seats.now + piratiSeats.seats.now >= majority);

  const seatRow = (previous: boolean) => ({
    year: previous ? years.previous : years.current,
    groups: GROUPS.map((group) => ({
      label: group.name,
      parts: group.lists.map((key) => ({
        key,
        seats: previous ? (previousList(key)?.seats ?? 0) : (data.lists.find((entry) => entry.key === key)?.seats ?? 0),
      })),
    })),
  });

  // The two ballots of the same voters
  const ballots = ballotRows(district, PAIRS).sort((a, b) => b.local - a.local);
  const ballot = (key: string) => ballots.find((row) => row.key === key)!;
  const gap = (key: string) => ballot(key).local - (ballot(key).city ?? 0);
  const inVoters = (pointsOfShare: number) => (Math.abs(pointsOfShare) / 100) * data.summary.ballots;
  const lowerLocally = (local: string, city: string, previous = false) =>
    precincts.filter((precinct) => localOverCity(precinct, local, city, previous) < 0).length;

  // Precincts and neighbourhoods
  const winners = Object.entries(counts.winners.now).sort((a, b) => b[1] - a[1]);
  const byShare = (key: string) => [...groups].sort((a, b) => (b.local[key] ?? 0) - (a.local[key] ?? 0));
  const byTurnout = [...groups].sort((a, b) => (b.turnout.now ?? 0) - (a.turnout.now ?? 0));
  const piratiBest = byShare("pirati")[0];

  // Voters in three elections
  const voters = (share: number | null | undefined, when: "then" | "now") =>
    share != null ? (share / 100) * district.ballots[when] : null;
  const inElections = (key: string, mid: number | null, keys: string[] = [key]) => ({
    key,
    values: [voters(together(district, keys, true), "then"), mid, voters(together(district, keys), "now")],
  });
  const electionRows = [
    inElections("praha1Sobe", null),
    inElections("odsTop", data.parliamentaryVotes.spolu, ["ods", "top09"]),
    inElections("stanKdu", data.parliamentaryVotes.stan),
    inElections("pirati", data.parliamentaryVotes.pirati),
    inElections("nasePraha1", data.parliamentaryVotes.ano),
  ];
  const piratiRow = electionRows.find((row) => row.key === "pirati")!;
  const [piratiThen, piratiNow] = [piratiRow.values[0] ?? 0, piratiRow.values[2] ?? 0];
  const moreBallots = district.ballots.now - district.ballots.then;
  const [lowTurnout, highTurnout] = [turnout.byLevel[0], turnout.byLevel[turnout.byLevel.length - 1]];

  const shareColumns = <Row extends Area>(): HeatColumn<Row>[] =>
    SHARES.map((key) => ({
      group: `Podíl hlasů ${years.current}`,
      head: label(key),
      value: (row: Row) => row.local[key] ?? 0,
      format: pct,
      tint: colorOf(key),
    }));
  const groupColumns: HeatColumn<(typeof groups)[number]>[] = [
    { head: "Zapsaní voliči", value: (row) => row.registered, format: fmtInt },
    { head: `Účast ${years.current}`, value: (row) => row.turnout.now ?? 0, format: pct },
    ...shareColumns<(typeof groups)[number]>(),
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
  const levelColumns: HeatColumn<Area>[] = [
    { group: "Účast", head: years.current, value: (row) => row.turnout.now ?? 0, format: pct },
    { group: "Účast", head: `Sněmovna ${years.parliamentary}`, value: (row) => row.turnout.mid ?? 0, format: pct },
    ...shareColumns<Area>(),
  ];

  return (
    <>
      <div className="tiles article-tiles">
        <div className="tile">
          <div className="value num">
            {pirati.seats} z {seats}
          </div>
          <div className="label">
            {seatsWord(pirati.seats)} mají Piráti, v roce {years.previous} jich jejich kandidátka získala{" "}
            {pirati.previousSeats}
          </div>
        </div>
        <div className="tile">
          <div className="value num">{townHall.seats.now}</div>
          <div className="label">
            mandátů mají kandidátky radniční koalice bez Pirátů; většina je {majority}
          </div>
        </div>
        <div className="tile">
          <div className="value num">{fmtInt(closest.voters)}</div>
          <div className="label">
            voličů chybělo kandidátce {label(closest.key)}, aby překročila pět procent a získala mandát
          </div>
        </div>
        <div className="tile">
          <div className="value num">{fmtPct(data.withoutSeats, 0)}</div>
          <div className="label">
            hlasů dostaly kandidátky, které mandát nezískaly; před čtyřmi lety {fmtPct(data.previousWithoutSeats, 0)}
          </div>
        </div>
      </div>

      <section className="prose">
        <h2>Shrnutí</h2>
        <p>
          Piráti mají v zastupitelstvu první městské části {pirati.seats} {seatsWord(pirati.seats)} místo{" "}
          {pirati.previousSeats}. Jejich podíl klesl z {fmtNum(pirati.previousShare ?? 0)} na {fmtPct(pirati.share)}{" "}
          a nižší je {inCount(counts.fell.pirati)} z {precincts.length} okrsků. Do pražského zastupitelstva klesli
          v týchž okrscích stejně, z {fmtNum(district.previousCity.pirati ?? 0)} na {fmtPct(district.city.pirati ?? 0)}.
        </p>
        <p>
          Kandidátky, které po volbách {years.previous} složily radu, mají bez Pirátů {townHall.seats.now} mandátů
          z {seats}, o {majority - townHall.seats.now === 1 ? "jeden" : majority - townHall.seats.now} méně než
          většina. Praha 1 Sobě a STAN s KDU-ČSL jich mají {others.seats.now}.
          {eitherWithPirati && <> S mandáty Pirátů by většinu měla kterákoli z obou stran.</>}
        </p>
        <p>
          O posledním mandátu rozhodlo {fmtInt(closest.voters)} voličů: tolik chybělo kandidátce {label(closest.key)}{" "}
          k pěti procentům. Kandidátky bez mandátu dostaly dohromady {fmtPct(data.withoutSeats)} hlasů.
        </p>
        <p>
          STAN s KDU-ČSL dostal do místního zastupitelstva {fmtPct(ballot("stanKdu").local)}, STAN do pražského od
          stejných voličů {fmtPct(ballot("stanKdu").city ?? 0)}. Praha 1 Sobě má místně{" "}
          {fmtPct(ballot("praha1Sobe").local)}, Praha Sobě do pražského {fmtPct(ballot("praha1Sobe").city ?? 0)}.
        </p>
      </section>

      <section className="prose">
        <h2>Výsledek</h2>
        <p>
          Po volbách v roce {years.previous} složily radu ODS, TOP 09, Naše Praha 1 (ANO), Rezidenti 1 a zastupitelé
          zvolení za kandidátku Piráti a občané z Prahy 1; starostkou se stala Terezie Radoměřská z TOP 09. Dva
          místostarostové té koalice, Kateřina Klasnová z Rezidentů 1 a David Bodeček, zvolený za pirátskou
          kandidátku, letos kandidovali společně jako Nezávislí z Jedničky. Graf je proto počítá ke koalici a Piráty
          vede zvlášť.
        </p>
      </section>

      <Figure title="Mandáty podle skupin" sub={`Zastupitelstvo městské části Praha 1, ${seats} mandátů`}>
        <CampSeats rows={[seatRow(true), seatRow(false)]} seats={seats} majority={majority} colorOf={colorOf} />
      </Figure>

      <Figure
        title="Výsledky kandidátek"
        sub="Podíl ze všech platných hlasů; kandidátky, které dostaly aspoň 2 %"
        note={`STAN a KDU-ČSL kandidovaly v obou volbách společně, v roce ${years.previous} pod názvem My, co tady žijeme. Naše Praha 1 je kandidátka ANO s nezávislými. Piráti kandidovali v roce ${years.previous} jako Piráti a občané z Prahy 1, letos jako Piráti a nezávislí pro Prahu 1.`}
      >
        <ResultsTable lists={data.lists} years={years} colorOf={colorOf} />
      </Figure>

      <section className="prose">
        <h2>Poslední mandát a pět procent</h2>
        <p>
          Poslední, {seats}. mandát připadl kandidátce {label(data.lastSeat.key)} jako její {ordinal(data.lastSeat.seat)}.
          Nejblíž k němu měla {label(closest.key)}: s {fmtPct(list(closest.key).share, 2)} hlasů jí k pěti procentům
          chybělo {fmtInt(closest.votes)} hlasů, tedy asi {fmtInt(closest.voters)} voličů. Vede ji Filip Dvořák,
          původně lídr ODS, kterého strana před volbami vyloučila.
        </p>
      </section>

      <Figure
        title="Kolik chybělo k dalšímu mandátu"
        sub="Nejmenší počet hlasů navíc, se kterým by kandidátka získala o mandát víc; všechno ostatní zůstává jako ve skutečnosti"
        note={
          sameLoser === data.margins.length - 1
            ? `Ve všech případech by mandát ztratila kandidátka ${label(data.lastSeat.key)}. Kandidátkám pod pěti procenty chybí hlasy k této hranici.`
            : undefined
        }
      >
        <HeatTable
          rows={data.margins.filter((item) => item.key !== data.lastSeat.key)}
          rowHead="Kandidátka"
          rowLabel={(row) => label(row.key)}
          columns={[
            { head: "Mandáty", value: (row) => row.seats, format: fmtInt },
            { head: "Chybělo hlasů", value: (row) => row.votes, format: fmtInt },
            { head: "Asi voličů", value: (row) => row.voters, format: fmtInt },
          ]}
        />
      </Figure>

      <section className="prose">
        <p>
          {piratiMargin && (
            <>
              Pirátům chybělo ke čtvrtému mandátu asi {tens(piratiMargin.voters)} voličů.{" "}
            </>
          )}
          Na kandidátky, které mandát nezískaly, připadlo {fmtPct(data.withoutSeats)} hlasů; v roce{" "}
          {years.previous} to bylo {fmtPct(data.previousWithoutSeats)}.
        </p>
      </section>

      <section className="prose">
        <h2>Dvoje volby, stejní voliči</h2>
        <p>
          Každý volič dostal dva hlasovací lístky: do zastupitelstva Prahy 1 a do zastupitelstva hlavního města.
          Jde tak srovnat, jak titíž lidé hlasovali o radnici a o magistrátu.
        </p>
      </section>

      <Figure
        title="Podíl hlasů v obojích volbách"
        sub={`Podíl hlasů v Praze 1 v roce ${years.current}. Rozdíl říká, o kolik víc dostala kandidátka do zastupitelstva Prahy 1 než do pražského.`}
        note={`Rozdíl ve voličích je rozdíl podílů krát počet odevzdaných obálek. ODS a TOP 09 šly v roce ${years.previous} do pražských voleb společně s KDU-ČSL, proto u nich srovnání chybí.`}
      >
        <TwoBallots rows={ballots} ballots={data.summary.ballots} years={years} colorOf={colorOf} />
      </Figure>

      <section className="prose">
        <p>
          STAN volilo do pražského zastupitelstva asi o {tens(inVoters(gap("stanKdu")))} lidí víc než společnou
          kandidátku STAN a KDU-ČSL do místního, Prahu Sobě asi o {tens(inVoters(gap("praha1Sobe")))} víc než Prahu 1
          Sobě. Před čtyřmi lety to bylo naopak: obě místní kandidátky tehdy dostaly víc než jejich pražské
          protějšky, Praha 1 Sobě o {fmtNum(ballot("praha1Sobe").previousGap ?? 0)} bodu a STAN s KDU-ČSL o{" "}
          {fmtNum(ballot("stanKdu").previousGap ?? 0)}.
        </p>
        <p>
          Praha 1 Sobě má místně méně než Praha Sobě do pražského zastupitelstva {inCount(lowerLocally("praha1Sobe", "prahaSobe"))}{" "}
          z {precincts.length} okrsků; v roce {years.previous} měla místně víc{" "}
          {inCount(precincts.length - lowerLocally("praha1Sobe", "prahaSobe", true))}. Místně naopak získávají ODS
          s TOP 09 ({points(gap("ods"))} proti Spolu) a kandidátky, které do pražského zastupitelstva nešly.
        </p>
        <p>
          Piráti mají v obojích volbách skoro stejně, letos i před čtyřmi lety. Jsou to rozdíly součtů; neříkají, kdo
          komu hlas dal.
        </p>
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
          . Praha 1 má jen {precincts.length} okrsků, proto jsou níž v tabulce všechny.
        </p>
      </section>

      <Figure
        title="Okrsky na mapě"
        sub="Vyberte, co má mapa ukazovat. Najetím na okrsek uvidíte jeho údaje, kliknutím ho otevřete v mapě výsledků."
      >
        <Suspense fallback={<Loading text="Načítám mapu…" />}>
          <DistrictMap data={data} colorOf={colorOf} shares={SHARES} groupColors={GROUP_COLORS} />
        </Suspense>
      </Figure>

      <Figure
        title={`Všech ${precincts.length} okrsků`}
        sub="Podíly v procentech hlasů do zastupitelstva Prahy 1. Kliknutím na záhlaví sloupce tabulku seřadíte, číslo okrsku ho otevře v mapě výsledků."
      >
        <PrecinctList
          precincts={precincts}
          years={years}
          mapPath={`${councilPath}/mapa`}
          lists={["praha1Sobe", "ods", "stanKdu", "top09"]}
          fileName="praha-1-okrsky-2026.csv"
        />
      </Figure>

      <section className="prose">
        <h2>Čtvrti</h2>
      </section>

      <Figure
        title="Čtvrti Prahy 1"
        sub="Volby do zastupitelstva Prahy 1. Podíly v procentech hlasů, změna v procentních bodech."
        note={
          data.unusual.length > 0
            ? `Účast je bez okrsku ${data.unusual[0].id}, kde je zapsáno ${fmtInt(data.unusual[0].registered)} voličů a přišlo jich ${fmtPct(data.unusual[0].turnout)}. S ním vychází účast celé Prahy 1 na ${fmtPct(data.summary.turnout)}.`
            : undefined
        }
      >
        <HeatTable rows={groups} rowHead="Čtvrť" rowLabel={(row) => row.name} columns={groupColumns} />
      </Figure>

      <section className="prose">
        <p>
          Nejvíc se volí v celku {byTurnout[0].name}, kde jsou nejsilnější Praha 1 Sobě, STAN s KDU-ČSL a TOP 09. ODS
          má nejvíc v celku {byShare("ods")[0].name}. Piráti jsou nejsilnější v celku {piratiBest.name} (
          {fmtPct(piratiBest.local.pirati ?? 0)}), kde zároveň ztratili nejvíc, z{" "}
          {fmtPct(piratiBest.previousLocal.pirati ?? 0)}.
        </p>
      </section>

      <section className="prose">
        <h2>Volební účast</h2>
        <p>
          Účast stoupla z {fmtNum(data.previousSummary.turnout)} na {fmtPct(data.summary.turnout)}, k volbám přišlo
          o {fmtInt(moreBallots)} lidí víc než před čtyřmi lety.
        </p>
      </section>

      <Figure
        title="Kolik lidí volilo kterou kandidátku"
        sub={`Volby do zastupitelstva Prahy 1 v letech ${years.previous} a ${years.current} a sněmovní volby ${years.parliamentary} ve stejných okrscích`}
        note="Hlasy v komunálních volbách jsou přepočtené na voliče. Ve sněmovních volbách jsou u ODS a TOP 09 hlasy koalice Spolu, ve které byla i KDU-ČSL, u STAN a KDU-ČSL jen hlasy STAN a u Naší Prahy 1 hlasy ANO."
      >
        <ElectionBars
          rows={electionRows}
          elections={[`Praha 1, ${years.previous}`, `Sněmovna ${years.parliamentary}`, `Praha 1, ${years.current}`]}
          colorOf={colorOf}
          format={hundreds}
        />
      </Figure>

      <section className="prose">
        <p>
          Piráti ztratili asi {tens(piratiThen - piratiNow)} voličů, {fmtPct((1 - piratiNow / piratiThen) * 100, 0)}{" "}
          těch z roku {years.previous}, přestože k urnám přišlo víc lidí. Do Sněmovny je loni v Praze 1 volilo{" "}
          {hundreds(data.parliamentaryVotes.pirati)} lidí.
        </p>
      </section>

      <Figure
        title="Okrsky podle výše účasti"
        sub={`Třetiny okrsků od nejnižší účasti v roce ${years.current} po nejvyšší. Podíly hlasů do zastupitelstva Prahy 1 v procentech.`}
      >
        <HeatTable
          rows={turnout.byLevel}
          rowHead="Účast"
          rowLabel={(row) => ["nízká", "střední", "vysoká"][turnout.byLevel.indexOf(row)]}
          columns={levelColumns}
        />
      </Figure>

      <section className="prose">
        <p>
          Praha 1 Sobě je silnější tam, kde se volí víc ({fmtNum(lowTurnout.local.praha1Sobe ?? 0)} a{" "}
          {fmtPct(highTurnout.local.praha1Sobe ?? 0)}), ODS a Piráti tam, kde méně. V každé třetině je jen{" "}
          {lowTurnout.precincts} okrsků, takže jde o hrubý obrázek.
        </p>
      </section>

      <section className="prose">
        <h2>Co z toho plyne</h2>
        <p>
          Piráti ztratili v Praze 1 do místního i do pražského zastupitelstva stejně. Jejich místní výsledek tedy odpovídá
          tomu, jak strana v centru dopadla celkově.
        </p>
        <p>
          Jejich {piratiSeats.seats.now} {seatsWord(piratiSeats.seats.now)} jsou přitom potřeba k většině na obě
          strany: bez nich ji nemá ani dosavadní koalice ({townHall.seats.now}), ani Praha 1 Sobě se STAN
          a KDU-ČSL ({others.seats.now}).
        </p>
        <p>
          Propadlo {fmtPct(data.withoutSeats, 0)} hlasů a o složení zastupitelstva rozhodovaly desítky voličů:{" "}
          {label(closest.key)} zůstala {fmtInt(closest.voters)} voličů pod hranicí a Praze 1 Sobě chybělo k dalšímu mandátu{" "}
          {fmtInt(margin("praha1Sobe")?.voters ?? 0)}.
        </p>
        <p>
          Prahu Sobě i STAN volí v centru do pražského zastupitelstva výrazně víc lidí než jejich místní
          kandidátky. Proč, z výsledků vyčíst nejde.
        </p>
      </section>

      <section className="card method-notes">
        <h3>Jak se to počítalo</h3>
        <p className="note">
          Mandáty jsou přepočítané d&apos;Hondtovou metodou s pětiprocentní klauzulí. Volič má v Praze 1 až {seats}{" "}
          hlasů; počty voličů jsou přepočtené z hlasů průměrem {fmtNum(data.votesPerBallot)} platného hlasu na
          odevzdanou obálku.
        </p>
        <p className="note">
          Čtvrti jsou části obce z registru adres (RÚIAN): okrsek patří tam, kde má nejvíc adres. Okrsek 1006 leží
          napůl na Starém a napůl na Novém Městě a je počítaný k Novému.
        </p>
        {data.unusual.length > 0 && (
          <p className="note">
            Okrsek {data.unusual[0].id} má {fmtInt(data.unusual[0].registered)} zapsaných voličů a účast{" "}
            {fmtPct(data.unusual[0].turnout)}, méně než polovinu účasti celé městské části. Do účasti čtvrtí a třetin
            se proto nepočítá, do podílů hlasů ano.
          </p>
        )}
        <p className="note">
          Odhad přesunů voličů mezi kandidátkami tu chybí: {precincts.length} okrsků na něj nestačí.
        </p>
      </section>
    </>
  );
}
