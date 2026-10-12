import { Link } from "react-router-dom";
import { fmtInt, fmtNum, fmtPct, fmtRange, plural } from "../format";
import {
  CampSeats,
  cell,
  DistrictTable,
  destinations,
  FifthsTable,
  Figure,
  FlowMatrix,
  groupColors,
  hundreds,
  label,
  origins,
  points,
  ResultsTable,
  ScenarioTable,
  SplitBar,
  StayedHomeTable,
  thousands,
} from "./blocks";
import type { District, PragueAnalysis, Scenario } from "./types";

export function Prague2026({ data }: { data: PragueAnalysis }) {
  const { years, seats, majority, flows, precincts, districts, parliamentary } = data;
  const colorOf = groupColors(data.lists);
  const list = (key: string) => data.lists.find((item) => item.key === key)!;
  const [stan, spolu, prahaSobe, ano, pirati, spd, motoriste, sen] = [
    "stan",
    "spolu",
    "prahaSobe",
    "ano",
    "pirati",
    "spd",
    "motoriste",
    "sen",
  ].map(list);
  const scenario = (key: string) => data.scenarios.find((item) => item.key === key)!;

  const camp = {
    share: pirati.share + prahaSobe.share,
    previousShare: (pirati.previousShare ?? 0) + (prahaSobe.previousShare ?? 0),
    seats: pirati.seats + prahaSobe.seats,
    previousSeats: (pirati.previousSeats ?? 0) + (prahaSobe.previousSeats ?? 0),
  };
  const rivals = {
    share: stan.share + spolu.share,
    previousShare: (stan.previousShare ?? 0) + (spolu.previousShare ?? 0),
    seats: stan.seats + spolu.seats,
    previousSeats: (stan.previousSeats ?? 0) + (spolu.previousSeats ?? 0),
  };
  const missing = rivals.seats - (majority - 1);
  const toPrahaSobe = scenario("stan-to-praha-sobe");
  const toPirati = scenario("stan-to-pirati");
  const newPirati = scenario("new-pirati");
  const ofVoters = (item: Scenario) => ((item.voters ?? 0) / data.summary.ballots) * 100;

  const kept = cell(flows, "pirati", "pirati");
  const leftForStan = cell(flows, "pirati", "stan");
  const leftForPrahaSobe = cell(flows, "pirati", "prahaSobe");
  const backFromStan = cell(flows, "stan", "pirati").people + cell(flows, "stan", "prahaSobe").people;
  const fromSpolu = cell(flows, "spolu", "pirati").people + cell(flows, "spolu", "prahaSobe").people;
  const toSpolu = cell(flows, "pirati", "spolu").people + cell(flows, "prahaSobe", "spolu").people;
  const newToPirati = cell(flows, "nevolici", "pirati");
  const newToRivals = cell(flows, "nevolici", "stan").people + cell(flows, "nevolici", "spolu").people;
  const anoToRivals = cell(flows, "ano", "stan").people + cell(flows, "ano", "spolu").people;
  const prahaSobeKept = cell(flows, "prahaSobe", "prahaSobe");
  const prahaSobeToSmall = cell(flows, "prahaSobe", "ostatni");
  const prahaSobeToSen = cell(data.flowsSmallLists, "prahaSobe", "sen");

  const nextPrahaSobe = data.nextInLine.find((item) => item.key === "prahaSobe");
  const closest = data.nextInLine[0];

  const weakest = precincts.fifths[0];
  const strongest = precincts.fifths[precincts.fifths.length - 1];
  const fifthChange = (key: string) => precincts.fifths.map((fifth) => fifth.shares[key] - fifth.previousShares[key]);
  const stanGains = fifthChange("stan");
  const prahaSobeGains = fifthChange("prahaSobe");

  const districtChange = (district: District, key: string) =>
    (district.shares[key] ?? 0) - (district.previousShares[key] ?? 0);
  const campAhead = (shares: District["shares"]) =>
    (shares.pirati ?? 0) + (shares.prahaSobe ?? 0) > (shares.stan ?? 0) + (shares.spolu ?? 0);
  const aheadNow = districts.filter((district) => campAhead(district.shares));
  const aheadThen = districts.filter((district) => campAhead(district.previousShares));
  const senStrongholds = [...districts.slice(0, 15)].sort((a, b) => (b.shares.sen ?? 0) - (a.shares.sen ?? 0)).slice(0, 3);

  const earlier = parliamentary.flows;
  const earlierList = (key: string) => parliamentary.lists.find((item) => item.key === key)!;
  const stayedHome = cell(earlier, "pirati", "nevolici");
  const earlierKept = cell(earlier, "pirati", "pirati");
  const earlierToPrahaSobe = cell(earlier, "pirati", "prahaSobe");
  const piratiVotes = earlierList("pirati").votes;
  const turnoutDrop = (1 - data.summary.ballots / parliamentary.summary.ballots) * 100;
  const councilPath = `/${data.council.election}/${data.council.code}`;

  const describe = (item: Scenario): { title: string; detail?: string } => {
    const share = item.votes ? `${fmtPct(ofVoters(item))} těch, kdo přišli volit` : undefined;
    switch (item.key) {
      case "actual":
        return { title: "Skutečný výsledek" };
      case "joint":
        return { title: "Společná kandidátka Pirátů a Prahy Sobě", detail: "prostý součet jejich hlasů" };
      case "sen-pirati":
        return { title: "Všechny hlasy SEN pro Piráty" };
      case "sen-praha-sobe":
        return { title: "Všechny hlasy SEN pro Prahu Sobě" };
      case "joint-sen":
        return { title: "Společná kandidátka včetně hlasů SEN" };
      case "stan-to-praha-sobe":
        return { title: `${hundreds(item.voters ?? 0)} voličů STAN volí Prahu Sobě`, detail: share };
      case "stan-to-pirati":
        return { title: `${hundreds(item.voters ?? 0)} voličů STAN volí Piráty`, detail: share };
      default:
        return { title: `${hundreds(item.voters ?? 0)} nových voličů Pirátů`, detail: share };
    }
  };

  const seatRow = (previous: boolean) => {
    const count = (item: typeof stan) => (previous ? (item.previousSeats ?? 0) : item.seats);
    const group = (title: string, items: (typeof stan)[]) => ({
      label: title,
      parts: items.map((item) => ({ key: item.key, seats: count(item) })),
    });
    return {
      year: previous ? years.previous : years.current,
      groups: [
        group("STAN + Spolu", [stan, spolu]),
        group(count(spd) > 0 ? "ANO a SPD" : "ANO", [ano, spd]),
        group("Praha Sobě + Piráti", [prahaSobe, pirati]),
      ],
    };
  };

  return (
    <>
      <div className="tiles article-tiles">
        <div className="tile">
          <div className="value num">
            {camp.seats} z {seats}
          </div>
          <div className="label">
            mandátů mají Piráti a Praha Sobě, v roce {years.previous} jich bylo {camp.previousSeats}
          </div>
        </div>
        <div className="tile">
          <div className="value num">{rivals.seats}</div>
          <div className="label">mandátů mají STAN a Spolu, k většině stačí {majority}</div>
        </div>
        <div className="tile">
          <div className="value num">
            {hundreds(toPrahaSobe.voters ?? 0)}–{hundreds(toPirati.voters ?? 0)}
          </div>
          <div className="label">voličů STAN by muselo volit Prahu Sobě nebo Piráty, aby ta většina nevznikla</div>
        </div>
        <div className="tile">
          <div className="value num">{fmtPct(leftForStan.share, 0)}</div>
          <div className="label">
            voličů Pirátů z roku {years.previous} letos volilo STAN, asi {thousands(leftForStan.people)} lidí
          </div>
        </div>
      </div>

      <section className="prose">
        <h2>Shrnutí</h2>
        <p>
          Piráti a Praha Sobě získali v Praze dohromady {fmtPct(camp.share)} hlasů a {camp.seats} z {seats} mandátů, o{" "}
          {camp.previousSeats - camp.seats} méně než před čtyřmi lety. STAN a Spolu mají {rivals.seats} mandátů, o{" "}
          {rivals.seats - majority} víc, než je potřeba k většině, a mohou tedy vládnout samy.
        </p>
        <p>
          K tomu, aby se bez třetího partnera neobešly, {plural(missing, "chyběl", "chyběly", "chybělo")} {missing}{" "}
          {plural(missing, "mandát", "mandáty", "mandátů")}. Odpovídá to zhruba {hundreds(toPrahaSobe.voters ?? 0)} až{" "}
          {hundreds(toPirati.voters ?? 0)} lidem, kteří by místo STAN volili Prahu Sobě nebo Piráty. Společná
          kandidátka ani hlasy, které propadly u kandidátky SEN, by samy nestačily.
        </p>
        <p>
          Hlavní příčinu ukazuje odhad přesunů voličů. Z těch, kdo v roce {years.previous} volili Piráty, zůstalo
          straně {fmtPct(kept.share, 0)}. Dalších {fmtPct(leftForPrahaSobe.share, 0)} přešlo k Praze Sobě, což na
          společném součtu nic nezměnilo, a {fmtPct(leftForStan.share, 0)}, přibližně {thousands(leftForStan.people)}{" "}
          lidí, ke STAN. Praha Sobě přitom téměř nezískala voliče odjinud než od Pirátů.
        </p>
        <p>
          Voliči, o které by se dalo opřít, přitom v Praze jsou. Loni do Sněmovny tu Piráty volilo{" "}
          {thousands(piratiVotes)} lidí a podle odhadu jich {fmtRange(stayedHome.low, stayedHome.high)} k letošním
          komunálním volbám nepřišlo.
        </p>
      </section>

      <section className="prose">
        <h2>Výsledek v číslech</h2>
        <p>
          Volby vyhrálo hnutí STAN s {fmtPct(stan.share)} hlasů těsně před koalicí Spolu ({fmtPct(spolu.share)}).
          Praha Sobě skončila třetí se {fmtPct(prahaSobe.share)}, Piráti pátí s {fmtPct(pirati.share)}. Volit přišlo{" "}
          {fmtPct(data.summary.turnout)} oprávněných, o {fmtNum(data.summary.turnout - data.previousSummary.turnout)}{" "}
          procentního bodu víc než v roce {years.previous}.
        </p>
      </section>

      <Figure title="Mandáty podle táborů" sub={`Zastupitelstvo hlavního města, ${seats} mandátů`}>
        <CampSeats rows={[seatRow(true), seatRow(false)]} seats={seats} majority={majority} colorOf={colorOf} />
      </Figure>

      <section className="prose">
        <p>
          Před čtyřmi lety měli Piráti s Prahou Sobě {camp.previousSeats} mandátů a STAN se Spolu{" "}
          {rivals.previousSeats}. Zbylých {(ano.previousSeats ?? 0) + (spd.previousSeats ?? 0)} tehdy držely ANO a
          SPD, letos jim zůstalo {ano.seats + spd.seats}. Mandáty, o které přišly ANO, SPD i Piráti s Prahou Sobě,
          připadly všechny dvojici STAN a Spolu.
        </p>
      </section>

      <Figure
        title="Výsledky kandidátek"
        sub="Podíl ze všech platných hlasů; kandidátky, které dostaly aspoň 2 %"
        note={`Spolu letos kandidovalo jako koalice ODS a TOP 09, bez KDU-ČSL, která byla její součástí v roce ${years.previous}. Odcházející koalici na magistrátu tvořily Spolu, Piráti a STAN, Praha Sobě byla v opozici.`}
      >
        <ResultsTable lists={data.lists} years={years} colorOf={colorOf} />
      </Figure>

      <section className="prose">
        <h2>Kolik chybělo</h2>
        <p>
          Většina v zastupitelstvu je {majority} hlasů a STAN se Spolu jich mají {rivals.seats}. Aby potřebovaly
          třetího partnera, musely by přijít o {missing} {plural(missing, "mandát", "mandáty", "mandátů")}
          {missing === 2 ? ", jeden by nestačil" : ""}.
        </p>
        <p>
          Poslední, {seats}. mandát připadl kandidátce {label(data.lastSeat)}.
          {nextPrahaSobe && (
            <>
              {" "}
              Praze Sobě k němu scházelo asi {thousands(nextPrahaSobe.missingVotes)} hlasů, tedy zhruba{" "}
              {hundreds(nextPrahaSobe.missingVoters)} voličů, protože každý měl {seats} hlasů a průměrně jich využil{" "}
              {fmtNum(data.votesPerBallot, 0)}.
            </>
          )}
          {closest && closest.key !== "prahaSobe" && (
            <>
              {" "}
              Ještě blíž mu ale byl {label(closest.key)} se svým {closest.seat}. mandátem a druhý potřebný mandát byl
              mnohem dál.
            </>
          )}
        </p>
      </section>

      <Figure
        title="Co by většinu STAN a Spolu změnilo"
        sub="Přepočet mandátů podle stejných pravidel; všechno, co řádek nezmiňuje, zůstává jako ve skutečnosti"
      >
        <ScenarioTable scenarios={data.scenarios} majority={majority} describe={describe} />
      </Figure>

      <section className="prose">
        <p>
          První čtyři úpravy počítají se stejnými hlasy, jen jinak sečtenými, a většinu STAN a Spolu ponechávají.
          Změnilo by ji teprve jiné rozhodnutí voličů: {fmtNum(ofVoters(toPrahaSobe))} až {fmtPct(ofVoters(toPirati))}{" "}
          zúčastněných by muselo dát hlasy Praze Sobě nebo Pirátům místo STAN. Samotná mobilizace by byla dražší,
          Piráti by potřebovali asi {thousands(newPirati.voters ?? 0)} nových voličů navíc.
        </p>
        <p>Výsledek tedy nebyl těsný. Nerozhodla ho roztříštěnost kandidátek ani přepočet hlasů na mandáty.</p>
      </section>

      <section className="prose">
        <h2>Kam odešli voliči Pirátů</h2>
        <p>
          Z lidí, kteří v roce {years.previous} volili Piráty, jich straně podle odhadu zůstala necelá třetina.
          Ostatní se rozdělili téměř rovným dílem mezi STAN a Prahu Sobě.
        </p>
      </section>

      <Figure
        title={`Jak letos volili voliči Pirátů z roku ${years.previous}`}
        sub="Odhad přesunů voličů. Šedě je rozmezí, ve kterém se odhad pohybuje."
      >
        <SplitBar parts={destinations(flows, "pirati")} colorOf={colorOf} peopleLabel="lidí" />
      </Figure>

      <section className="prose">
        <p>
          Odchod k Praze Sobě společný výsledek nezhoršil, hlasy zůstaly ve stejném táboře. Rozhodující byl odchod ke
          STAN. Těch {thousands(leftForStan.people)} lidí představuje asi{" "}
          {fmtPct((leftForStan.people / data.summary.ballots) * 100, 0)} všech, kdo letos volili, tedy skoro přesně
          tolik, o kolik Piráti a Praha Sobě dohromady klesli ({fmtNum(camp.previousShare - camp.share)} bodu).
          Opačným směrem, od STAN k Pirátům nebo Praze Sobě, přešly asi {thousands(backFromStan)} voličů.
        </p>
        <p>
          Srovnání s tabulkou scénářů je přímočaré: kdyby {fmtPct(((toPirati.voters ?? 0) / leftForStan.people) * 100, 0)}{" "}
          z těch, kdo odešli ke STAN, zůstalo u Pirátů, STAN a Spolu by většinu neměly.
        </p>
      </section>

      <Figure
        title="Z koho se skládají letošní voliči"
        sub={`Podle toho, koho volili v roce ${years.previous}`}
      >
        <div className="grid three">
          {["stan", "prahaSobe", "pirati"].map((key) => (
            <div key={key}>
              <h4 className="split-title">{label(key)}</h4>
              <SplitBar parts={origins(flows, key).map(({ people: _, ...part }) => part)} colorOf={colorOf} />
            </div>
          ))}
        </div>
      </Figure>

      <section className="prose">
        <p>
          STAN bral i jinde. Tři největší skupiny jeho letošních voličů tvoří bývalí voliči Spolu (
          {fmtPct(cell(flows, "spolu", "stan").origin, 0)}), jeho vlastní voliči z roku {years.previous} (
          {fmtPct(cell(flows, "stan", "stan").origin, 0)}) a bývalí voliči Pirátů ({fmtPct(leftForStan.origin, 0)}).
          Posílil tedy na úkor obou svých partnerů z magistrátní koalice.
        </p>
        <p>
          Piráti naopak oslovili lidi, kteří před čtyřmi lety nevolili. Tvoří asi {fmtPct(newToPirati.origin, 0)}{" "}
          jejich letošních voličů (rozmezí {fmtRange(newToPirati.originLow, newToPirati.originHigh)}), přibližně{" "}
          {thousands(newToPirati.people)} lidí, což je nejvyšší podíl mezi kandidátkami v zastupitelstvu. Ztrátu to
          nevyrovnalo.
        </p>
      </section>

      <section className="card">
        <details className="more">
          <summary>
            Celá tabulka přesunů mezi roky {years.previous} a {years.current}
          </summary>
          <div className="more-body">
            <FlowMatrix
              flows={flows}
              sourceYear={years.previous}
              targetYear={years.current}
              colorOf={colorOf}
              highlight="pirati"
            />
            <p className="note" style={{ marginTop: 12 }}>
              Řádky jsou skupiny voličů z roku {years.previous}. Sloupce říkají, kolik procent z nich letos volilo
              kterou kandidátku; čísla v řádku dávají dohromady 100. Rozmezí odhadu se ukáže po najetí myší na buňku.{" "}
              <Link className="inline-link" to={`${councilPath}/presuny`}>
                Otevřít přesuny voličů v plném zobrazení
              </Link>
            </p>
          </div>
        </details>
      </section>

      <section className="prose">
        <h2>Kde Piráti ztráceli</h2>
        <p>
          Podíl Pirátů klesl v {fmtInt(precincts.fell.pirati)} z {fmtInt(precincts.compared)} srovnatelných okrsků,
          nejvíc tam, kde bývali nejsilnější. V pětině okrsků s jejich nejlepším výsledkem z roku {years.previous}{" "}
          spadli z {fmtPct(strongest.previousShares.pirati)} na {fmtPct(strongest.shares.pirati)}, v pětině
          nejslabších z {fmtPct(weakest.previousShares.pirati)} na {fmtPct(weakest.shares.pirati)}.
        </p>
      </section>

      <Figure
        title={`Okrsky podle toho, jak silní v nich byli Piráti v roce ${years.previous}`}
        sub={`V každé pětině je asi ${weakest.precincts} okrsků. Změny jsou v procentních bodech, modrá znamená zisk a červená ztrátu.`}
      >
        <FifthsTable fifths={precincts.fifths} years={years} colorOf={colorOf} />
      </Figure>

      <section className="prose">
        <p>
          STAN rostl všude stejně, ve všech pětinách okrsků o {fmtNum(Math.min(...stanGains))} až{" "}
          {fmtNum(Math.max(...stanGains))} procentního bodu. Praha Sobě získávala víc v někdejších pirátských baštách (
          {points(prahaSobeGains[prahaSobeGains.length - 1])}) než tam, kde byli Piráti slabí ({points(prahaSobeGains[0])}
          ).
        </p>
        <p>
          Před čtyřmi lety měli Piráti víc hlasů než Praha Sobě v {fmtInt(precincts.piratiAhead.then)} z{" "}
          {fmtInt(precincts.precincts.then)} okrsků, letos v {fmtInt(precincts.piratiAhead.now)} z{" "}
          {fmtInt(precincts.precincts.now)}.{" "}
          {precincts.winners.now.pirati === 0
            ? "Letos nezvítězili v žádném okrsku"
            : `Letos zvítězili v ${fmtInt(precincts.winners.now.pirati)} okrscích`}
          , v roce {years.previous} jich bylo {fmtInt(precincts.winners.then.pirati)}.
        </p>
      </section>

      <Figure
        title="Městské části podle společné ztráty Pirátů a Prahy Sobě"
        sub="Hlasování do zastupitelstva hlavního města. Podíly v procentech, změny v procentních bodech."
        note={
          <>
            Sytější barva ve sloupcích s podíly znamená silnější výsledek, u změn modrá zisk a červená ztrátu.{" "}
            <Link className="inline-link" to={`${councilPath}/mapa`}>
              Podívat se na mapu okrsků
            </Link>
          </>
        }
      >
        <DistrictTable districts={districts} years={years} colorOf={colorOf} />
      </Figure>

      <section className="prose">
        <p>
          V roce {years.previous} měli Piráti s Prahou Sobě víc hlasů než STAN se Spolu v {aheadThen.length} z{" "}
          {districts.length} městských částí, letos{" "}
          {aheadNow.length === 1 ? `jen v části ${aheadNow[0].name}` : `v ${aheadNow.length}`}.
        </p>
        <p>
          Čtyři velké městské části s největší ztrátou mají dvě různá vysvětlení. V Praze 9, kde je starostou lídr
          Spolu Tomáš Portlík, a v sousední Praze 14 posílilo Spolu, ačkoli v celém městě oslabilo. V Praze 5 a Praze
          13 uspěla kandidátka SEN.
        </p>
      </section>

      <section className="prose">
        <h2>Praha Sobě a kandidátka SEN</h2>
        <p>
          Praha Sobě vyrostla skoro výhradně z bývalých voličů Pirátů. Udržela si asi {fmtPct(prahaSobeKept.share, 0)}{" "}
          svých voličů z roku {years.previous} a ti spolu s bývalými voliči Pirátů tvoří{" "}
          {fmtPct(prahaSobeKept.origin + leftForPrahaSobe.origin, 0)} jejího letošního elektorátu. Od Spolu přišla asi{" "}
          {fmtPct(cell(flows, "spolu", "prahaSobe").origin, 0)}, od ostatních kandidátek a z řad nevoličů jen jednotky
          procent.
        </p>
        <p>
          Součet obou kandidátek se proto pohyboval v uzavřeném okruhu. Od Spolu k nim přešlo asi {thousands(fromSpolu)}{" "}
          lidí a opačným směrem asi {thousands(toSpolu)}, od ANO podle odhadu nikdo. Z voličů, které ztratilo ANO, část
          letos nepřišla a část přešla ke Spolu a STAN.
        </p>
        <p>
          Praha Sobě zároveň asi {fmtPct(prahaSobeToSmall.share, 0)} svých voličů z roku {years.previous} (rozmezí{" "}
          {fmtRange(prahaSobeToSmall.low, prahaSobeToSmall.high)}) ztratila ve prospěch malých kandidátek. Když se
          odhad spočítá znovu se samostatnou kandidátkou SEN pro Prahu s Václavem Láskou, vychází, že k ní přešlo asi{" "}
          {fmtPct(prahaSobeToSen.share, 0)} někdejších voličů Prahy Sobě (rozmezí{" "}
          {fmtRange(prahaSobeToSen.low, prahaSobeToSen.high)}).
        </p>
      </section>

      <Figure
        title="Odkud přišli voliči kandidátky SEN"
        sub={`Podle toho, koho volili v roce ${years.previous}. U malé kandidátky je odhad méně jistý, jak ukazují široká rozmezí.`}
      >
        <SplitBar parts={origins(data.flowsSmallLists, "sen")} colorOf={colorOf} peopleLabel="lidí" />
      </Figure>

      <section className="prose">
        <p>
          SEN dostal {fmtPct(sen.share)} hlasů a do zastupitelstva se nedostal. Podporu měl soustředěnou v několika
          městských částech:{" "}
          {senStrongholds.map((district) => `${district.name} ${fmtPct(district.shares.sen ?? 0)}`).join(", ")}. Jinde
          se držel kolem 2 %. V prvních dvou z nich Praha Sobě skoro nerostla (
          {senStrongholds
            .slice(0, 2)
            .map((district) => points(districtChange(district, "prahaSobe")))
            .join(" a ")}
          ), i když v celém městě přidala {fmtNum(prahaSobe.share - (prahaSobe.previousShare ?? 0))} bodu.
        </p>
        <p>
          Pod pětiprocentní klauzulí skončilo celkem {fmtPct(data.belowThreshold)} hlasů, vedle SEN hlavně SPD
          s partnery ({fmtPct(spd.share)}) a Motoristé ({fmtPct(motoriste.share)}).
        </p>
      </section>

      <section className="prose">
        <h2>Loňští sněmovní voliči Pirátů</h2>
        <p>
          Ve volbách do Sněmovny v říjnu {years.parliamentary} dostali Piráti v Praze{" "}
          {fmtPct(earlierList("pirati").share)} a {thousands(piratiVotes)} hlasů. O rok později je v komunálních
          volbách volilo asi {thousands(pirati.voters)} lidí. I kdyby všichni letošní voliči Pirátů byli jejich
          loňskými voliči, bylo by to jen {fmtPct((pirati.voters / piratiVotes) * 100, 0)} z nich.
        </p>
        <p>
          Kam se poděl zbytek, se dá odhadnout stejným postupem jako přesuny od roku {years.previous}. Výsledek je ale
          hrubší, proto ho ukazujeme s širšími rozmezími.
        </p>
      </section>

      <div className="banner">
        <strong>Méně spolehlivý odhad.</strong> Sněmovní a komunální volby se liší účastí (
        {fmtPct(parliamentary.summary.turnout, 0)} a {fmtPct(data.summary.turnout, 0)}) i nabídkou: Praha Sobě do
        Sněmovny nekandiduje a na voličský průkaz tu loni hlasovali i lidé, kteří v Praze komunálně volit nemohou.
        Model proto vystihuje {fmtPct(earlier.explained, 0)} rozdílů mezi okrsky, u srovnání s rokem {years.previous}{" "}
        {fmtPct(flows.explained, 0)}. Rozmezí zahrnují i to, jak se odhad mění s nastavením výpočtu. Věřte směru
        a pořadí, ne přesným číslům.
      </div>

      <Figure
        title={`Jak letos volili ti, kdo v roce ${years.parliamentary} volili do Sněmovny Piráty`}
        sub="Odhad přesunů voličů. Šedě je rozmezí, ve kterém se odhad pohybuje."
      >
        <SplitBar parts={destinations(earlier, "pirati")} colorOf={colorOf} peopleLabel="lidí" />
      </Figure>

      <section className="prose">
        <p>
          Při každém nastavení výpočtu vychází, že velká část loňských voličů Pirátů k letošním volbám nepřišla: podle
          odhadu {fmtRange(stayedHome.low, stayedHome.high)}. U voličů Spolu to je{" "}
          {fmtRange(cell(earlier, "spolu", "nevolici").low, cell(earlier, "spolu", "nevolici").high)}, u voličů STAN{" "}
          {fmtRange(cell(earlier, "stan", "nevolici").low, cell(earlier, "stan", "nevolici").high)}. Srovnání
          všech stran je v tabulce.
        </p>
      </section>

      <Figure
        title="Kolik loňských voličů letos k volbám nepřišlo"
        sub={`Voliči stran ze sněmovních voleb ${years.parliamentary}, kteří v komunálních volbách ${years.current} nevolili. Celkem letos přišlo o ${fmtPct(turnoutDrop, 0)} méně lidí.`}
      >
        <StayedHomeTable flows={earlier} parties={parliamentary.lists} colorOf={colorOf} />
      </Figure>

      <section className="prose">
        <p>
          Kdyby se všechny strany chovaly stejně, nepřišla by od každé asi třetina voličů. Odhad místo toho říká, že
          voliči Spolu a STAN chodí ke komunálním volbám skoro všichni, kdežto voliči Pirátů, ANO a SPD z velké části
          ne. Odpovídá tomu i to, že komunální účast je vyšší v okrscích, kde je silné Spolu, a nižší tam, kde jsou
          silní Piráti.
        </p>
        <p>
          Velikost rozdílu je ale nejspíš přehnaná. Že by ke komunálním volbám přišli skoro všichni voliči Spolu, když
          celkem volila necelá polovina zapsaných, není věrohodné. Model nejspíš část jejich neúčasti připisuje jiným
          stranám, hlavně Pirátům. Skutečné rozdíly budou menší, ale stejným směrem.
        </p>
        <p>
          Jednu skupinu odhad oddělit neumí. Loni se v Praze hlasovalo i na voličský průkaz a tito lidé tu komunálně
          volit nemohou. V datech vypadají stejně jako ti, kdo zůstali doma.
        </p>
      </section>

      <section className="prose">
        <p>
          Ti, kdo volit přišli, dali podle odhadu častěji hlas Praze Sobě ({fmtRange(earlierToPrahaSobe.low, earlierToPrahaSobe.high)}{" "}
          loňských voličů Pirátů) než Pirátům ({fmtRange(earlierKept.low, earlierKept.high)}). Loňští voliči Pirátů
          tak tvoří největší část letošních voličů Prahy Sobě, {fmtPct(earlierToPrahaSobe.origin, 0)}.
        </p>
        <p>
          Podíl, který zůstal u Pirátů, je nejméně jistý údaj celé analýzy a je skoro jistě podhodnocený. Znamenal by
          totiž, že většina letošních voličů Pirátů loni volila Spolu nebo STAN, což je málo pravděpodobné.
        </p>
      </section>

      <Figure
        title="Koho loni volili do Sněmovny letošní voliči STAN a Prahy Sobě"
        sub="Odhad; šedě rozmezí, ve kterém se pohybuje"
      >
        <div className="grid half">
          {["stan", "prahaSobe"].map((key) => (
            <div key={key}>
              <h4 className="split-title">{label(key)}</h4>
              <SplitBar parts={origins(earlier, key).map(({ people: _, ...part }) => part)} colorOf={colorOf} />
            </div>
          ))}
        </div>
      </Figure>

      <section className="prose">
        <p>
          Mezi letošními voliči STAN model loňské voliče Pirátů nenachází. Podle odhadu loni volili Spolu (
          {fmtPct(cell(earlier, "spolu", "stan").origin, 0)}) nebo STAN ({fmtPct(cell(earlier, "stan", "stan").origin, 0)}
          ). Dohromady s přesuny od roku {years.previous} to naznačuje, že ke STAN odešli hlavně ti voliči Pirátů
          z minulých komunálních voleb, kteří Piráty nevolili už loni do Sněmovny.
        </p>
      </section>

      <section className="card">
        <details className="more">
          <summary>
            Celá tabulka přesunů od sněmovních voleb {years.parliamentary}
          </summary>
          <div className="more-body">
            <FlowMatrix
              flows={earlier}
              sourceYear={years.parliamentary}
              targetYear={years.current}
              colorOf={colorOf}
              highlight="pirati"
            />
            <p className="note" style={{ marginTop: 12 }}>
              Řádky jsou voliči stran ze sněmovních voleb {years.parliamentary}, sloupce jejich volba v komunálních
              volbách {years.current}. Nuly u malých přesunů znamenají, že je model neumí odlišit od nuly, ne že
              nikdo takový nebyl.
            </p>
          </div>
        </details>
      </section>

      <section className="prose">
        <h2>Co z toho plyne</h2>
        <p>
          O většině STAN a Spolu rozhodl hlavně jeden proud voličů, od Pirátů ke STAN. K jinému výsledku by stačilo
          udržet necelou polovinu z nich, kdežto žádné spojení kandidátek Pirátů, Prahy Sobě a SEN by na něm nic
          nezměnilo.
        </p>
        <p>
          Piráti a Praha Sobě se dělí o stejný okruh voličů a ten se letos zmenšil. Praha Sobě v něm posílila, mimo
          něj ale neuspěla u bývalých voličů Spolu a ANO ani u lidí, kteří minule nevolili. Z obou kandidátek přivedli
          nové voliče jen Piráti, asi {thousands(newToPirati.people)}. STAN a Spolu jich dohromady získaly zhruba{" "}
          {thousands(newToRivals)} a dalších {thousands(anoToRivals)} od ANO.
        </p>
        <p>
          Největší rezerva je v účasti. Z {thousands(piratiVotes)} lidí, kteří loni volili Piráty do Sněmovny, jich
          letos podle odhadu {fmtInt(Math.round((piratiVotes * stayedHome.low) / 100000))} až{" "}
          {thousands((piratiVotes * stayedHome.high) / 100)} k volbám nepřišlo. K tomu, aby STAN a Spolu většinu
          neměly, by přitom stačilo asi {thousands(newPirati.voters ?? 0)} voličů Pirátů navíc.
        </p>
        <p>
          STAN je naopak v Praze silnější v komunální volbě než ve sněmovní. Loni dostal{" "}
          {fmtPct(earlierList("stan").share)} a {thousands(earlierList("stan").votes)} hlasů. Letos volilo o{" "}
          {fmtPct(turnoutDrop, 0)} méně lidí, a přesto oslovil asi {thousands(stan.voters)} voličů.
        </p>
        <p>
          Proč voliči přecházeli nebo zůstali doma, z výsledků vyčíst nejde. Na to jsou potřeba průzkumy.
        </p>
      </section>

      <section className="card method-notes">
        <h3>Jak se to počítalo</h3>
        <p className="note">
          Výsledky pocházejí z otevřených dat ČSÚ. Rozdělení mandátů je přepočítané d&apos;Hondtovou metodou
          s pětiprocentní klauzulí a shoduje se s oficiálním. Scénáře mění jen uvedené hlasy, všechno ostatní
          nechávají beze změny.
        </p>
        <p className="note">
          Přesuny voličů jsou odhad, ne měření. Model porovnává {fmtInt(flows.matched)} okrsků, které jdou mezi oběma
          volbami srovnat, a hledá tabulku přechodů, která nejlépe vysvětluje změnu výsledků v nich. Vystihuje{" "}
          {fmtPct(flows.explained, 0)} rozdílů mezi okrsky.
        </p>
        <p className="note">
          Rozmezí jsou {fmtNum(flows.interval, 0)}% a říkají, jak moc odhad závisí na výběru okrsků, ne jak moc se
          může mýlit model sám. Lidi, kteří se přistěhovali nebo dosáhli volebního věku, model neodlišuje od těch, kdo
          minule nevolili, a výměnu mezi voliči a nevoliči spíš podhodnocuje.
        </p>
        <p className="note">
          Odhad od sněmovních voleb pracuje s {fmtInt(earlier.matched)} okrsky. Jeho rozmezí navíc pokrývají výsledky
          pro různý počet skupin, do kterých se okrsky před výpočtem dělí
          {earlier.settings ? ` (${earlier.settings.join(", ")})` : ""}.
        </p>
        <p className="note">
          Počty voličů jsou přepočtené z hlasů: podíl kandidátky na hlasech krát počet odevzdaných obálek.
        </p>
        <Link className="button" style={{ marginTop: 16, display: "inline-block" }} to={`${councilPath}/presuny?pohled=metoda`}>
          Projít si krok za krokem, jak odhad vzniká
        </Link>
      </section>
    </>
  );
}
