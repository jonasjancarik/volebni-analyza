import { Link } from "react-router-dom";
import { fmtInt, fmtPct, plural } from "../format";
import {
  cell,
  Figure,
  groupColors,
  hundreds,
  origins,
  SeatGrid,
  SplitBar,
  thousands,
  TransferSteps,
} from "./blocks";
import type { NextTimeAnalysis, Scenario } from "./types";

const LAW = "https://www.zakonyprolidi.cz/cs/2001-491";

const WHERE: Record<string, string> = {
  pirati: "SEN na kandidátce Pirátů",
  prahaSobe: "SEN na kandidátce Prahy Sobě",
  joint: "Piráti, Praha Sobě a SEN společně",
};

const LEVERS: Record<string, string> = {
  "new-pirati": "Noví voliči Pirátů",
  "new-praha-sobe": "Noví voliči Prahy Sobě",
  "stan-to-pirati": "Voliči STAN, kteří by volili Piráty",
  "stan-to-praha-sobe": "Voliči STAN, kteří by volili Prahu Sobě",
};

const camp = (item: Scenario) => item.seats.joint ?? (item.seats.prahaSobe ?? 0) + (item.seats.pirati ?? 0);
const people = (item: Scenario | null) => (item ? hundreds(item.voters ?? 0) : "");

export function Prague2026Next({ data }: { data: NextTimeAnalysis }) {
  const { years, majority, actual, sen, combined, flows } = data;
  const colorOf = groupColors(data.lists);
  const missing = actual.stanSpolu - (majority - 1);
  const senShare = data.lists.find((item) => item.key === "sen")?.share ?? 0;
  const senVoters = (share: number) => (sen.voters * share) / 100;

  const transfer = (recipient: string) => data.transfers.find((item) => item.recipient === recipient)!;
  // The percent of SEN's voters from which the camp has `gain` seats more than today
  const neededFor = (recipient: string, gain: number) =>
    transfer(recipient).steps.find((step) => camp(step) - camp(actual) >= gain)?.share ?? null;
  const gainAt = (recipient: string, share: number) => {
    const reached = transfer(recipient).steps.filter((step) => step.share <= share);
    return camp(reached[reached.length - 1]) - camp(actual);
  };
  const withAllOfSen = transfer("pirati").steps[transfer("pirati").steps.length - 1];

  const remaining = (share: number) => combined.remaining.find((item) => item.share === share)!;
  const [none, half, all] = [remaining(0), remaining(50), remaining(100)];

  const senOrigins = origins(data.flowsSmallLists, "sen");
  const fromCamp = senOrigins
    .filter((part) => part.key === "prahaSobe" || part.key === "pirati")
    .reduce((sum, part) => sum + part.value, 0);
  const gains = ["pirati", "prahaSobe", "joint"].map((recipient) => gainAt(recipient, fromCamp));

  const backFromStan = cell(flows, "pirati", "stan").people;
  const earlier = data.parliamentary.flows;
  const piratiVotes = data.parliamentary.lists.find((item) => item.key === "pirati")?.votes ?? 0;
  const stayedHome = cell(earlier, "pirati", "nevolici");
  const ofBack = (item: Scenario | null) => fmtPct((((item?.voters ?? 0) as number) / backFromStan) * 100, 0);

  const pirati1 = neededFor("pirati", 1) ?? 0;
  const pirati2 = neededFor("pirati", 2);

  return (
    <>
      <div className="tiles article-tiles">
        <div className="tile">
          <div className="value num">{missing}</div>
          <div className="label">
            {plural(missing, "mandát dělí", "mandáty dělí", "mandátů dělí")} STAN a Spolu od ztráty většiny
          </div>
        </div>
        <div className="tile">
          <div className="value num">{fmtPct(pirati1, 0)}</div>
          <div className="label">
            voličů SEN by Pirátům stačilo na jeden mandát navíc, asi {hundreds(senVoters(pirati1))} lidí
          </div>
        </div>
        <div className="tile">
          <div className="value num">{withAllOfSen.stanSpolu}</div>
          <div className="label">
            mandátů by STAN a Spolu měly, i kdyby SEN přivedl všechny své voliče; k většině stačí {majority}
          </div>
        </div>
        <div className="tile">
          <div className="value num">{people(half.back)}</div>
          <div className="label">
            voličů zpět od STAN by pak stačilo s polovinou voličů SEN; bez SEN jich je potřeba {people(none.back)}
          </div>
        </div>
      </div>

      <section className="prose">
        <h2>Shrnutí</h2>
        <p>
          Koalice se SEN by podle letošních hlasů přinesla jeden mandát snadno a druhý obtížně. S Piráty by na první
          stačilo {fmtPct(pirati1, 0)} voličů SEN, asi {hundreds(senVoters(pirati1))} lidí
          {pirati2 != null && <>, na druhý {fmtPct(pirati2, 0)}</>}.
        </p>
        <p>
          Většinu STAN a Spolu by ale sama nezrušila. První mandát by ubral Spolu, druhý ANO, takže i se všemi hlasy
          SEN by STAN a Spolu měly {withAllOfSen.stanSpolu} mandátů z {data.seats}.
        </p>
        <p>
          Smysl dává jako polovina cesty. S polovinou voličů SEN by ke zbytku stačilo {people(half.back)} voličů zpět
          od STAN místo {people(none.back)}, nebo {people(half.new)} nových voličů Pirátů místo {people(none.new)}.
        </p>
      </section>

      <section className="prose">
        <h2>Každá cesta zvlášť</h2>
        <p>
          STAN a Spolu mají {actual.stanSpolu} mandátů a k většině jim stačí {majority}. První mandát, o který by
          přišly, na tom nic nemění. Rozhoduje až druhý.
        </p>
      </section>

      <Figure
        title="Kolik lidí je potřeba na první a na druhý mandát"
        sub="Přepočet letošních hlasů podle stejných pravidel; všechno, co řádek nezmiňuje, zůstává jako ve skutečnosti"
      >
        <div className="table-wrap">
          <table className="data levers">
            <thead>
              <tr>
                <th>Co by se změnilo</th>
                <th className="r">První mandát</th>
                <th className="r">Druhý mandát, STAN a Spolu bez většiny</th>
              </tr>
            </thead>
            <tbody>
              {data.levers.map((item) => (
                <tr key={item.key}>
                  <td>{LEVERS[item.key] ?? item.key}</td>
                  <td className="r">{people(item.first)}</td>
                  <td className="r">
                    <span className="verdict no-majority">
                      <strong className="num">{people(item.second)}</strong>
                    </span>
                  </td>
                </tr>
              ))}
              {(["pirati", "prahaSobe"] as const).map((recipient) => {
                const first = neededFor(recipient, 1) ?? 0;
                return (
                  <tr key={recipient}>
                    <td>
                      <div>{WHERE[recipient]}</div>
                      <div className="small muted">z jeho {hundreds(sen.voters)} voličů</div>
                    </td>
                    <td className="r">
                      {hundreds(senVoters(first))} <span className="small muted">({fmtPct(first, 0)})</span>
                    </td>
                    <td className="r out">nestačí ani všichni</td>
                  </tr>
                );
              })}
              <tr>
                <td>Společná kandidátka Pirátů a Prahy Sobě</td>
                <td className="r">bez dalších hlasů</td>
                <td className="r out">nestačí</td>
              </tr>
            </tbody>
          </table>
        </div>
      </Figure>

      <section className="prose">
        <p>
          První mandát je blízko každou cestou. Druhý mohou přinést jen voliči STAN nebo vyšší účast; spojení
          kandidátek ani hlasy SEN na něj nestačí.
        </p>
        <p>
          Pro srovnání: bývalých voličů Pirátů u STAN je asi {thousands(backFromStan)} a loňských sněmovních voličů
          Pirátů, kteří letos nepřišli, {fmtInt(Math.round((piratiVotes * stayedHome.low) / 100000))} až{" "}
          {thousands((piratiVotes * stayedHome.high) / 100)}.
        </p>
      </section>

      <section className="prose">
        <h2>Koalice se SEN</h2>
        <p>
          SEN pro Prahu s Václavem Láskou dostal {fmtPct(senShare)} hlasů, asi {hundreds(sen.voters)} voličů,
          a všechny propadly. Záleží na tom, kolik z nich by společnou kandidátku volilo a ke komu by se SEN přidal.
        </p>
      </section>

      <Figure
        title="Kolik mandátů by měli Piráti a Praha Sobě podle toho, kolik voličů SEN by přešlo"
        sub={`Dnes jich mají ${camp(actual)}. Čára ukazuje, kolik voličů SEN podle odhadu dřív volilo Prahu Sobě nebo Piráty.`}
      >
        <TransferSteps
          rows={(["pirati", "prahaSobe", "joint"] as const).map((recipient) => ({
            label: WHERE[recipient],
            steps: transfer(recipient).steps.map((step) => ({
              share: step.share,
              value: camp(step),
              gain: camp(step) - camp(actual),
            })),
          }))}
          mark={{ share: fromCamp, label: `${fmtPct(fromCamp, 0)} voličů SEN` }}
        />
      </Figure>

      <section className="prose">
        <p>
          Praha Sobě potřebuje méně než Piráti, protože jí k dalšímu mandátu chybělo nejméně. Vodítkem, kolik voličů
          by přešlo, je to, že asi {fmtPct(fromCamp, 0)} z nich v roce {years.previous} volilo Prahu Sobě nebo
          Piráty. Kdyby společnou kandidátku volili jen oni,{" "}
          {gains.every((gain) => gain === gains[0])
            ? `znamená to ve všech třech variantách o ${gains[0]} ${plural(gains[0], "mandát", "mandáty", "mandátů")} víc než dnes`
            : `znamená to o ${gains.join(", ")} mandátů víc než dnes podle varianty`}
          .
        </p>
      </section>

      <Figure
        title="Odkud přišli voliči kandidátky SEN"
        sub={`Podle toho, koho volili v roce ${years.previous}. U malé kandidátky je odhad méně jistý, jak ukazují široká rozmezí.`}
      >
        <SplitBar parts={senOrigins} colorOf={colorOf} peopleLabel="lidí" />
      </Figure>

      <section className="prose">
        <p>
          Druhý mandát by šel na úkor ANO, ne STAN nebo Spolu. Proto ani všechny hlasy SEN jejich většinu nemění.
        </p>
        <p>
          Podporu má SEN soustředěnou:{" "}
          {sen.strongholds.map((district) => `${district.name} ${fmtPct(district.share)}`).join(", ")}, jinde kolem
          2 %. Stojí tedy na místních kandidátech a z celoměstských čísel nejde odhadnout, kolik jejich voličů by
          volilo společnou kandidátku.
        </p>
        <p>
          Koalice nemá vyšší práh než samostatná kandidátka; pětiprocentní klauzule platí pro všechny stejně (
          <a className="inline-link" href={LAW} target="_blank" rel="noreferrer">
            § 45 zákona o volbách do zastupitelstev obcí
          </a>
          ).
        </p>
      </section>

      <section className="prose">
        <h2>Dohromady</h2>
      </section>

      <Figure
        title="Mandáty STAN a Spolu při kombinaci dvou změn"
        sub={`Řádky jsou podíl voličů SEN, kteří by volili kandidátku Pirátů. Modře jsou kombinace, při kterých STAN a Spolu nemají většinu ${majority} mandátů.`}
      >
        <div className="grid half">
          <SeatGrid
            title="Voliči SEN a noví voliči Pirátů"
            rowHead="Voliči SEN"
            rows={combined.shares}
            columnHead="Noví voliči Pirátů"
            columns={combined.new.columns}
            cells={combined.new.cells}
            majority={majority}
          />
          <SeatGrid
            title="Voliči SEN a návrat od STAN"
            rowHead="Voliči SEN"
            rows={combined.shares}
            columnHead="Voliči, kteří se vrátí od STAN k Pirátům"
            columns={combined.back.columns}
            cells={combined.back.cells}
            majority={majority}
          />
        </div>
      </Figure>

      <section className="prose">
        <p>
          Bez SEN je potřeba {people(none.new)} nových voličů Pirátů nebo {people(none.back)} voličů zpět od STAN.
          S polovinou voličů SEN {people(half.new)} nebo {people(half.back)}, se všemi {people(all.new)} nebo{" "}
          {people(all.back)}. U návratu od STAN to je {ofBack(half.back)} bývalých voličů Pirátů místo{" "}
          {ofBack(none.back)}.
        </p>
      </section>

      <section className="prose">
        <h2>Co z toho plyne</h2>
        <p>
          Koalice se SEN by přinesla jeden mandát už při přechodu třetiny jeho voličů. O většině STAN a Spolu ale
          rozhoduje druhý mandát a ten musí přijít od voličů STAN nebo z vyšší účasti; SEN potřebný počet zhruba půlí.
        </p>
        <p>
          Přepočty mění jen to, co je uvedeno. Neříkají, jestli by voliči SEN společnou kandidátku volili, ani co by
          spojení udělalo s dosavadními voliči Pirátů a Prahy Sobě.
        </p>
      </section>

      <section className="card method-notes">
        <h3>Jak se to počítalo</h3>
        <p className="note">
          Mandáty jsou přepočítané d&apos;Hondtovou metodou s pětiprocentní klauzulí. Voliči jsou přepočtení z hlasů:
          každý měl {data.seats} hlasů a průměrně jich využil {fmtInt(Math.round(data.votesPerBallot))}.
        </p>
        <p className="note">
          Odkud přišli voliči SEN a kolik bývalých voličů Pirátů volilo STAN, jsou odhady, ne měření.
        </p>
        <Link
          className="button"
          style={{ marginTop: 16, display: "inline-block" }}
          to="/analyzy/praha-2026-pirati-praha-sobe"
        >
          Přečíst si analýzu výsledku Pirátů a Prahy Sobě
        </Link>
      </section>
    </>
  );
}
