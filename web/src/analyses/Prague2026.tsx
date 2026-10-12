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
  const [stan, spolu, prahaSobe, ano, pirati, spd, sen] = ["stan", "spolu", "prahaSobe", "ano", "pirati", "spd", "sen"].map(
    list,
  );
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
  const fromSpolu = cell(flows, "spolu", "pirati").people + cell(flows, "spolu", "prahaSobe").people;
  const toSpolu = cell(flows, "pirati", "spolu").people + cell(flows, "prahaSobe", "spolu").people;
  const newToPirati = cell(flows, "nevolici", "pirati");
  const prahaSobeKept = cell(flows, "prahaSobe", "prahaSobe");
  const prahaSobeToSen = cell(data.flowsSmallLists, "prahaSobe", "sen");

  const nextPrahaSobe = data.nextInLine.find((item) => item.key === "prahaSobe");
  const closest = data.nextInLine[0];

  const weakest = precincts.fifths[0];

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
          Piráti a Praha Sobě mají dohromady {fmtPct(camp.share)} hlasů a {camp.seats} z {seats} mandátů, o{" "}
          {camp.previousSeats - camp.seats} méně než před čtyřmi lety. STAN a Spolu jich mají {rivals.seats}, o{" "}
          {rivals.seats - majority} víc, než potřebují k většině.
        </p>
        <p>
          Do stavu, kdy by potřebovaly třetího partnera, {plural(missing, "chyběl", "chyběly", "chybělo")} {missing}{" "}
          {plural(missing, "mandát", "mandáty", "mandátů")}: zhruba {hundreds(toPrahaSobe.voters ?? 0)} až{" "}
          {hundreds(toPirati.voters ?? 0)} lidí, kteří by místo STAN volili Prahu Sobě nebo Piráty. Společná
          kandidátka ani hlasy kandidátky SEN by nestačily.
        </p>
        <p>
          Z voličů Pirátů z roku {years.previous} zůstalo straně {fmtPct(kept.share, 0)}.{" "}
          {fmtPct(leftForPrahaSobe.share, 0)} přešlo k Praze Sobě, což společný součet nezměnilo, a{" "}
          {fmtPct(leftForStan.share, 0)}, asi {thousands(leftForStan.people)} lidí, ke STAN.
        </p>
        <p>
          Loni do Sněmovny přitom Piráty v Praze volilo {thousands(piratiVotes)} lidí.{" "}
          {fmtRange(stayedHome.low, stayedHome.high)} z nich podle odhadu letos nepřišlo.
        </p>
      </section>

      <section className="prose">
        <h2>Výsledek v číslech</h2>
        <p>
          Před čtyřmi lety měli Piráti s Prahou Sobě {camp.previousSeats} mandátů a STAN se Spolu{" "}
          {rivals.previousSeats}. Mandáty, o které od té doby přišly ANO, SPD i Piráti s Prahou Sobě, připadly
          všechny dvojici STAN a Spolu.
        </p>
      </section>

      <Figure title="Mandáty podle táborů" sub={`Zastupitelstvo hlavního města, ${seats} mandátů`}>
        <CampSeats rows={[seatRow(true), seatRow(false)]} seats={seats} majority={majority} colorOf={colorOf} />
      </Figure>

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
          Poslední mandát připadl kandidátce {label(data.lastSeat)}.
          {nextPrahaSobe && <> Praze Sobě k němu scházelo asi {hundreds(nextPrahaSobe.missingVoters)} voličů.</>}
          {closest && closest.key !== "prahaSobe" && <> {label(closest.key)} byl ještě blíž.</>} Druhý potřebný
          mandát byl mnohem dál.
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
          První čtyři úpravy jen jinak sčítají stejné hlasy a většinu nemění. Změnilo by ji až jiné rozhodnutí{" "}
          {fmtNum(ofVoters(toPrahaSobe))} až {fmtPct(ofVoters(toPirati))} zúčastněných, nebo asi{" "}
          {thousands(newPirati.voters ?? 0)} nových voličů Pirátů.
        </p>
      </section>

      <section className="prose">
        <h2>Kam odešli voliči Pirátů</h2>
      </section>

      <Figure
        title={`Jak letos volili voliči Pirátů z roku ${years.previous}`}
        sub="Odhad přesunů voličů. Šedě je rozmezí, ve kterém se odhad pohybuje."
      >
        <SplitBar parts={destinations(flows, "pirati")} colorOf={colorOf} peopleLabel="lidí" />
      </Figure>

      <section className="prose">
        <p>
          Odchod k Praze Sobě společný výsledek nezhoršil. Rozhodl odchod ke STAN: {thousands(leftForStan.people)}{" "}
          lidí je asi {fmtPct((leftForStan.people / data.summary.ballots) * 100, 0)} všech, kdo letos volili, skoro
          přesně tolik, o kolik Piráti a Praha Sobě dohromady klesli. Kdyby{" "}
          {fmtPct(((toPirati.voters ?? 0) / leftForStan.people) * 100, 0)} z nich zůstalo u Pirátů, STAN a Spolu by
          většinu neměly.
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
          STAN posílil na úkor obou partnerů z magistrátní koalice: {fmtPct(cell(flows, "spolu", "stan").origin, 0)}{" "}
          jeho voličů přišlo od Spolu a {fmtPct(leftForStan.origin, 0)} od Pirátů. Piráti přivedli asi{" "}
          {thousands(newToPirati.people)} lidí, kteří minule nevolili; ztrátu to nevyrovnalo.
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
          nejvíc tam, kde bývali nejsilnější.
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
          STAN rostl ve všech pětinách stejně, Praha Sobě nejvíc v někdejších pirátských baštách. Před čtyřmi lety
          měli Piráti víc hlasů než Praha Sobě v {fmtInt(precincts.piratiAhead.then)} z{" "}
          {fmtInt(precincts.precincts.then)} okrsků, letos v {fmtInt(precincts.piratiAhead.now)}.
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
          Největší ztráty mají dvě vysvětlení. V Praze 9, kde je starostou lídr Spolu Tomáš Portlík, a v sousední
          Praze 14 posílilo Spolu. V Praze 5 a 13 uspěla kandidátka SEN.
        </p>
      </section>

      <section className="prose">
        <h2>Praha Sobě a kandidátka SEN</h2>
        <p>
          Praha Sobě vyrostla skoro výhradně z bývalých voličů Pirátů. Ti a její vlastní voliči z roku{" "}
          {years.previous} tvoří {fmtPct(prahaSobeKept.origin + leftForPrahaSobe.origin, 0)} jejího elektorátu.
          Výměna se Spolu byla vyrovnaná, asi {thousands(fromSpolu)} lidí tam a {thousands(toSpolu)} zpět, a od ANO
          podle odhadu nepřišel nikdo.
        </p>
        <p>
          Asi {fmtPct(prahaSobeToSen.share, 0)} jejích voličů z roku {years.previous} (rozmezí{" "}
          {fmtRange(prahaSobeToSen.low, prahaSobeToSen.high)}) přešlo ke kandidátce SEN pro Prahu s Václavem Láskou.
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
          SEN dostal {fmtPct(sen.share)} hlasů a do zastupitelstva se nedostal. Podporu má soustředěnou:{" "}
          {senStrongholds.map((district) => `${district.name} ${fmtPct(district.shares.sen ?? 0)}`).join(", ")}.
          V prvních dvou Praha Sobě skoro nerostla (
          {senStrongholds
            .slice(0, 2)
            .map((district) => points(districtChange(district, "prahaSobe")))
            .join(" a ")}
          ), ačkoli v celém městě přidala {fmtNum(prahaSobe.share - (prahaSobe.previousShare ?? 0))} bodu.
        </p>
      </section>

      <section className="prose">
        <h2>Loňští sněmovní voliči Pirátů</h2>
        <p>
          V říjnu {years.parliamentary} dostali Piráti v Praze do Sněmovny {fmtPct(earlierList("pirati").share)}{" "}
          a {thousands(piratiVotes)} hlasů. Letos je volilo asi {thousands(pirati.voters)} lidí.
        </p>
      </section>

      <div className="banner">
        <strong>Méně spolehlivý odhad.</strong> Sněmovní a komunální volby se liší účastí (
        {fmtPct(parliamentary.summary.turnout, 0)} a {fmtPct(data.summary.turnout, 0)}) i nabídkou, Praha Sobě do
        Sněmovny nekandiduje. Rozmezí proto zahrnují i různá nastavení výpočtu. Věřte směru a pořadí, ne přesným
        číslům.
      </div>

      <Figure
        title={`Jak letos volili ti, kdo v roce ${years.parliamentary} volili do Sněmovny Piráty`}
        sub="Odhad přesunů voličů. Šedě je rozmezí, ve kterém se odhad pohybuje."
      >
        <SplitBar parts={destinations(earlier, "pirati")} colorOf={colorOf} peopleLabel="lidí" />
      </Figure>

      <Figure
        title="Kolik loňských voličů letos k volbám nepřišlo"
        sub={`Voliči stran ze sněmovních voleb ${years.parliamentary}, kteří v komunálních volbách ${years.current} nevolili. Celkem letos přišlo o ${fmtPct(turnoutDrop, 0)} méně lidí.`}
      >
        <StayedHomeTable flows={earlier} parties={parliamentary.lists} colorOf={colorOf} />
      </Figure>

      <section className="prose">
        <p>
          Podle odhadu chodí voliči Spolu a STAN ke komunálním volbám skoro všichni, voliči Pirátů, ANO a SPD
          z velké části ne. Rozdíl je nejspíš přehnaný, protože model část
          neúčasti voličů Spolu připisuje jiným stranám, jeho směr se ale nemění.
        </p>
        <p>
          Lidi, kteří loni v Praze hlasovali na voličský průkaz a komunálně tu volit nemohou, odhad neodliší od těch,
          kdo nepřišli.
        </p>
      </section>

      <section className="prose">
        <p>
          Ti, kdo přišli, volili častěji Prahu Sobě ({fmtRange(earlierToPrahaSobe.low, earlierToPrahaSobe.high)}) než
          Piráty ({fmtRange(earlierKept.low, earlierKept.high)}). Podíl pro Piráty je nejméně jistý údaj analýzy
          a skoro jistě je podhodnocený: znamenal by, že většina letošních voličů Pirátů loni volila Spolu nebo STAN.
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
          Mezi letošními voliči STAN model loňské voliče Pirátů nenachází. Ke STAN tedy zřejmě odešli ti voliči
          Pirátů z roku {years.previous}, kteří je nevolili už loni do Sněmovny.
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
          O většině STAN a Spolu rozhodl hlavně jeden proud voličů, od Pirátů ke STAN. Stačilo udržet necelou
          polovinu z nich.
        </p>
        <p>
          Piráti a Praha Sobě se dělí o stejný okruh voličů a ten se zmenšil. Praha Sobě mimo něj neuspěla u voličů
          Spolu, ANO ani u těch, kdo minule nevolili.
        </p>
        <p>
          Největší rezerva je v účasti. Z {thousands(piratiVotes)} loňských sněmovních voličů Pirátů jich podle
          odhadu {fmtInt(Math.round((piratiVotes * stayedHome.low) / 100000))} až{" "}
          {thousands((piratiVotes * stayedHome.high) / 100)} nepřišlo; k jinému výsledku by stačilo asi{" "}
          {thousands(newPirati.voters ?? 0)}.
        </p>
        <p>Proč voliči přecházeli nebo zůstali doma, z výsledků vyčíst nejde.</p>
      </section>

      <section className="card method-notes">
        <h3>Jak se to počítalo</h3>
        <p className="note">
          Mandáty jsou přepočítané d&apos;Hondtovou metodou s pětiprocentní klauzulí a scénáře mění jen uvedené
          hlasy. Počty voličů jsou přepočtené z hlasů: podíl kandidátky krát počet odevzdaných obálek.
        </p>
        <p className="note">
          Přesuny voličů jsou odhad z {fmtInt(flows.matched)} srovnatelných okrsků, ne měření. Rozmezí (
          {fmtNum(flows.interval, 0)} %) říkají, jak moc odhad závisí na výběru okrsků, ne jak moc se může mýlit
          model. Nové voliče model neodliší od těch, kdo minule nevolili.
        </p>
        <p className="note">
          Odhad od sněmovních voleb pracuje s {fmtInt(earlier.matched)} okrsky a jeho rozmezí pokrývají i různý počet
          skupin, do kterých se okrsky před výpočtem dělí.
        </p>
        <Link className="button" style={{ marginTop: 16, display: "inline-block" }} to={`${councilPath}/presuny?pohled=metoda`}>
          Projít si krok za krokem, jak odhad vzniká
        </Link>
      </section>
    </>
  );
}
