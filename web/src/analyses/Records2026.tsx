import { fmtInt, fmtPct, fmtSignedInt, plural } from "../format";
import { Figure } from "./blocks";
import "./records.css";

interface RecordExample {
  place: number;
  name: string;
  votes: number;
  usual: number;
  /** Votes of the candidates around, the one in question in square brackets */
  around: string;
}

interface Evidence {
  precinct: string;
  list: string;
  kind: "missing" | "extra";
  candidates: number;
  votes: number;
  mostlyEmpty: boolean;
  /** Whether the recomputed seats count it as an error */
  counted: boolean;
  example: RecordExample;
}

interface ListRow {
  number: number;
  name: string;
  votes: number;
  share: number;
  seats: number;
  seatsAfter: number;
  overThreshold: number;
  toNextSeat: number | null;
  toLoseSeat: number | null;
  missing: number;
  slips: number;
}

interface CouncilCase {
  code: string;
  name: string;
  city: string | null;
  seats: number;
  precincts: number;
  closestSeat: number | null;
  candidatesWithErrors: number;
  seatsChange: boolean;
  lists: ListRow[];
  people: { list: string; seated: string[]; unseated: string[]; corrected: number }[];
  evidence: Evidence[];
}

export interface RecordsAnalysis {
  totals: {
    councils: number;
    checked: number;
    decidedByLot: number;
    seatsDiffer: number;
    orderDiffers: number;
    missing: number;
    missingVotes: number;
    slips: number;
    slipVotes: number;
    councilsWithErrors: number;
    precinctsWithErrors: number;
  };
  changed: CouncilCase[];
  tight: { council: string; list: string; seats: number; before: string; after: string; votes: number; corrected: number }[];
  /** `reason` says in the reader's words why the count reads as a slip of the pen */
  slips: ({ council: string; precinct: string; list: string; reason: string } & RecordExample)[];
  pirates: {
    council: string;
    list: string;
    seats: number;
    seatsAfter: number;
    toNextSeat: number | null;
    toLoseSeat: number | null;
    missing: number;
    slips: number;
    closestPerson: string;
    closestPersonVotes: number | null;
    seated: string;
    unseated: string;
  }[];
  checked: { name: string; city: string | null; precincts: number; errors: number }[];
}

const LAW = "https://www.zakonyprolidi.cz/cs/2001-491";
const SOURCE = "https://www.volby.cz/opendata/kv2026/kv2026_opendata.htm";

/** What a closer look at the records of one council showed */
const NOTES: Record<string, React.ReactNode> = {
  Karviná: (
    <>
      SPD skončila dva hlasy pod pětiprocentní hranicí. V okrsku 40 má její kandidát č. 19 zapsanou nulu, ačkoli
      všichni kolem něj mají 13 hlasů; už tento jediný údaj by na překročení hranice stačil. V okrsku 29 mají
      poslední kandidáti SPD (č. 34 až 41) jen 3 až 4 hlasy místo dvanácti. Takový pokles ke konci kandidátky se může
      stát i bez chyby, a proto se do přepočtu nepočítá. S mandáty pro SPD by o jeden přišli Žijeme pro Karvinou a o jeden
      společná kandidátka STAN, ODS, Pirátů a TOP 09.
    </>
  ),
  Most: (
    <>
      Kandidátka Pirátů, Zelených a Starostů je sedm hlasů nad pětiprocentní hranicí. V okrsku 30 má VIZE pro Most
      hlasy zapsané jen u dvanácti kandidátů, každý kolem čtyřiceti, a zbylých 33 má nulu. Po doplnění by vzrostl
      celkový počet hlasů ve městě a s ním i hranice; stačilo by k tomu asi 150 hlasů, chybí jich přes tisíc.
      Kandidátka Pirátů, Zelených a Starostů by pak hranici nepřekročila a o oba mandáty by přišla.
    </>
  ),
  "Praha 10": (
    <>
      Naše Praha 10 je 99 hlasů nad pětiprocentní hranicí. V okrsku 10043 má její kandidát č. 24 zapsáno 165 hlasů,
      kandidáti kolem něj 15 až 17 a lídr kandidátky 29. S patnácti hlasy místo 165 by kandidátka hranici
      nepřekročila a její dva mandáty by připadly kandidátkám JSME PRAHA 10 a SPD.
    </>
  ),
  Havířov: (
    <>
      Hnutí pro Havířov chybí k pátému mandátu 103 hlasů. V okrsku 28 mají jeho kandidáti č. 21 až 24 zapsáno 5, 2,
      2 a 3 hlasy, sousedé před nimi i za nimi 34 až 40. Chybí tak asi 136 hlasů. Rezerva je malá, kolem třiceti
      hlasů, takže výsledek závisí na tom, kolik hlasů tito čtyři kandidáti skutečně dostali.
    </>
  ),
  Olomouc: (
    <>
      Počet mandátů se nemění, mění se, kdo je získal. Lídr ODS má v okrsku 91 zapsáno 150 hlasů, ostatní kandidáti
      tam 15 až 23; bez tohoto údaje by ho na kandidátce předstihli čtyři kandidáti s více hlasy. Na kandidátce
      MILUJEME OLOMOUC má zvolená kandidátka v okrsku 59 zapsáno 221 hlasů mezi sousedy s dvaceti. Stejný vzor,
      číslice připsaná navíc, je na téže kandidátce ještě ve dvou dalších okrscích.
    </>
  ),
};

/** Neighbouring candidates' votes with the one in question marked */
function RecordRow({ around }: { around: string }) {
  return (
    <span className="record-row num">
      {around.split(" ").map((token, index) => {
        const marked = token.startsWith("[");
        const text = token.replace(/[[\]]/g, "");
        return (
          <span key={index}>
            {index > 0 && " "}
            {marked ? <mark>{text}</mark> : text}
          </span>
        );
      })}
    </span>
  );
}

const candidatesWord = (count: number) => plural(count, "kandidát", "kandidáti", "kandidátů");
const votesWord = (count: number) => plural(count, "hlas", "hlasy", "hlasů");

function describe(item: Evidence): string {
  const votes = `${fmtInt(Math.abs(item.votes))} ${votesWord(Math.abs(item.votes))}`;
  if (item.kind === "extra") return `asi ${votes} navíc`;
  if (item.mostlyEmpty) return `většina kandidátky bez hlasů, chybí asi ${votes}`;
  return item.candidates === 1 ? `chybí asi ${votes}` : `${item.candidates} ${candidatesWord(item.candidates)}, chybí asi ${votes}`;
}

function Case({ item }: { item: CouncilCase }) {
  const moved = item.lists.filter((list) => list.seats !== list.seatsAfter);
  const shown = item.lists.filter((list) => list.seats > 0 || list.seatsAfter > 0 || list.missing > 0 || list.slips > 0 || Math.abs(list.overThreshold) < 2000);
  return (
    <Figure
      title={item.city ? `${item.name} (${item.city})` : item.name}
      sub={
        item.seatsChange ? (
          <span className="seat-change">
            {moved.map((list) => `${list.name} ${fmtSignedInt(list.seatsAfter - list.seats)}`).join(", ")}
          </span>
        ) : (
          "Stejný počet mandátů, jiní zvolení"
        )
      }
      note={NOTES[item.name] ?? "Záznamy tohoto zastupitelstva jsme zatím neprocházeli jednotlivě; tabulky ukazují, co je v oficiálních datech."}
    >
      <div className="record-case">
        {item.seatsChange && (
          <div className="table-wrap">
            <table className="data">
              <thead>
                <tr>
                  <th>Kandidátka</th>
                  <th className="r">Hlasy</th>
                  <th className="r">Podíl</th>
                  <th className="r">Mandáty</th>
                  <th className="r">Po opravě</th>
                  <th className="r">Chybí u kandidátů</th>
                  <th className="r">Navíc překlepem</th>
                </tr>
              </thead>
              <tbody>
                {shown.map((list) => (
                  <tr key={list.number}>
                    <td>{list.name}</td>
                    <td className="r num">{fmtInt(list.votes)}</td>
                    <td className="r num">{fmtPct(list.share, 2)}</td>
                    <td className="r num">{list.seats}</td>
                    <td className="r num">
                      <span className={list.seats === list.seatsAfter ? "" : "share"}>{list.seatsAfter}</span>
                    </td>
                    <td className="r num">{list.missing ? fmtInt(list.missing) : ""}</td>
                    <td className="r num">{list.slips ? fmtInt(list.slips) : ""}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        {item.people.length > 0 && (
          <ul className="people">
            {item.people.map((row) => (
              <li key={row.list}>
                <strong>{row.list}:</strong>{" "}
                {[
                  row.seated.length > 0 && `nově s mandátem ${row.seated.join(", ")}`,
                  row.unseated.length > 0 && `bez mandátu ${row.unseated.join(", ")}`,
                ]
                  .filter(Boolean)
                  .join("; ")}
              </li>
            ))}
          </ul>
        )}
        <h4>Co je v zápisech</h4>
        <div className="table-wrap">
          <table className="data">
            <thead>
              <tr>
                <th>Okrsek</th>
                <th>Kandidátka</th>
                <th>Hlasy sousedních kandidátů</th>
                <th>Odhad</th>
              </tr>
            </thead>
            <tbody>
              {item.evidence.map((row, index) => (
                <tr key={index}>
                  <td className="num">{row.precinct}</td>
                  <td>
                    <div>{row.list}</div>
                    <div className="small muted">
                      č. {row.example.place} {row.example.name}
                    </div>
                  </td>
                  <td>
                    <RecordRow around={row.example.around} />
                  </td>
                  <td>
                    <div>{describe(row)}</div>
                    {!row.counted && <div className="small muted">do přepočtu se nepočítá, může jít o místní podporu</div>}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </Figure>
  );
}

export function Records2026({ data }: { data: RecordsAnalysis }) {
  const { totals } = data;
  const withSeats = data.changed.filter((item) => item.seatsChange);
  const withPeople = data.changed.filter((item) => !item.seatsChange);
  const names = (items: CouncilCase[]) => items.map((item) => item.name).join(", ");
  const cities = new Map<string, number>();
  for (const item of data.checked) cities.set(item.city ?? "", (cities.get(item.city ?? "") ?? 0) + 1);
  const districts = [...cities.entries()].filter(([city]) => city !== "");

  return (
    <>
      <div className="article-tiles">
        <div className="tile">
          <div className="value num">{fmtInt(totals.missing + totals.slips)}</div>
          <div className="label">údajů u kandidátů, které zjevně neodpovídají ostatním údajům téhož zápisu</div>
        </div>
        <div className="tile">
          <div className="value num">{fmtInt(totals.precinctsWithErrors)}</div>
          <div className="label">okrsků v {totals.councilsWithErrors} městech a městských částech, kterých se týkají</div>
        </div>
        <div className="tile">
          <div className="value num">{withSeats.length}</div>
          <div className="label">zastupitelstva, kde by jejich oprava změnila počet mandátů</div>
        </div>
        <div className="tile">
          <div className="value num">{withPeople.length}</div>
          <div className="label">další, kde by při stejném počtu mandátů byli zvoleni jiní lidé</div>
        </div>
      </div>

      <section className="prose">
        <h2>Shrnutí</h2>
        <ul className="takeaways">
          <li>
            Oficiální výsledky obsahují hlasy každého kandidáta v každém okrsku. V{" "}
            {fmtInt(totals.precinctsWithErrors)} okrscích je v nich údaj, který nemůže odpovídat odevzdaným lístkům:
            kandidát s nulou mezi sousedy s desítkami hlasů, nebo s desetinásobkem toho, co mají ostatní.
          </li>
          <li>
            Ve většině případů jde o desítky hlasů a na výsledku se nic nemění. Ve městech {names(withSeats)} by ale
            oprava změnila rozdělení mandátů, protože tam některá kandidátka skončila těsně u pětiprocentní hranice
            nebo těsně pod dalším mandátem.
          </li>
          <li>
            V zastupitelstvech {names(withPeople)} by zůstal počet mandátů stejný, ale na některé kandidátce by
            mandát získal jiný kandidát.
          </li>
          <li>
            Nic z toho není oprava výsledku. Je to výpočet z údajů, které v zápisech jsou, a z odhadu těch, které
            v nich chybí. Skutečný stav ukáže jen přepočet lístků, o kterém může rozhodnout soud.
          </li>
        </ul>
      </section>

      <section className="prose">
        <h2>Jak se chyba pozná</h2>
        <p>
          Kdo na lístku zakřížkuje celou kandidátku, dává hlas každému jejímu kandidátovi. Ve městech tak hlasuje
          většina voličů, a kandidáti jedné kandidátky proto mají v okrsku skoro stejný počet hlasů: lídr o něco víc,
          poslední místa o něco méně. Když má jeden kandidát nulu a jeho sousedé 45, nebo 165 a jeho sousedé 15,
          neodpovídá to žádnému způsobu, jak mohli lidé hlasovat. Nejčastěji zůstaly prázdné poslední řádky kandidátky
          nebo je v čísle číslice navíc.
        </p>
        <p>
          Chybějící hlasy se dají odhadnout podle sousedních kandidátů. S takto opravenými součty jsou tu znovu
          spočítané mandáty podle stejných pravidel, jaká používá{" "}
          <a href={LAW} target="_blank" rel="noreferrer">
            zákon o volbách do zastupitelstev obcí
          </a>
          : pětiprocentní hranice, dělení mandátů mezi kandidátky i pořadí kandidátů uvnitř kandidátky.
        </p>
      </section>

      <section className="prose">
        <h2>Kde by se změnily mandáty</h2>
        <p>
          U každého zastupitelstva je nejdřív výsledek kandidátek a pak záznamy, ze kterých změna vychází. V řádku
          hlasů je zvýrazněný kandidát, o kterého jde; čísla kolem jsou hlasy kandidátů před ním a za ním na téže
          kandidátce v tomtéž okrsku.
        </p>
      </section>
      {withSeats.map((item) => (
        <Case key={item.code} item={item} />
      ))}

      <section className="prose">
        <h2>Kde by byli zvoleni jiní lidé</h2>
        <p>
          Mandáty kandidátky dostanou nejdřív kandidáti, kteří mají aspoň o desetinu víc hlasů, než je průměr jejich
          kandidátky, a to v pořadí podle hlasů. Zbylé mandáty se obsazují podle pořadí na lístku. Jediný chybný údaj
          tak může rozhodnout, kdo z kandidátky do zastupitelstva půjde, a to i nepřímo: nadsazený počet hlasů
          jednoho kandidáta zvedá průměr, který musí překonat ostatní.
        </p>
      </section>
      {withPeople.map((item) => (
        <Case key={item.code} item={item} />
      ))}

      <section className="prose">
        <h2>Kde po opravě rozhoduje pár hlasů</h2>
        <p>
          V těchto případech oprava zvolené nemění, ale rozdíl mezi posledním zvoleným a prvním nezvoleným kandidátem
          je tak malý, že o něm může rozhodnout jakákoli další drobná chyba.
        </p>
      </section>
      <Figure
        title="Kandidátky, kde by stačilo několik hlasů u jednoho kandidáta"
        sub="Jen kandidátky, u kterých je v zápisech aspoň jeden chybný údaj; plus znamená hlasy, které kandidátovi chybí k mandátu, minus hlasy, o které by ho ztratil"
      >
        <div className="table-wrap">
          <table className="data">
            <thead>
              <tr>
                <th>Zastupitelstvo</th>
                <th>Kandidátka</th>
                <th>Podle oficiálního výsledku</th>
                <th>Po opravě</th>
                <th className="r">Opraveno hlasů</th>
              </tr>
            </thead>
            <tbody>
              {data.tight.map((row, index) => (
                <tr key={index}>
                  <td>{row.council}</td>
                  <td>{row.list}</td>
                  <td>{row.before}</td>
                  <td>{row.after}</td>
                  <td className="r num">{fmtInt(row.corrected)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Figure>

      <Figure
        title="Největší zjevné překlepy"
        sub="Kandidát, který má v jediném okrsku několikanásobek hlasů svých sousedů na kandidátce"
        note={`Celkem je takových údajů ${fmtInt(totals.slips)} a kandidátům přidávají asi ${fmtInt(totals.slipVotes)} hlasů. Údajů, kde hlasy naopak chybějí, je ${fmtInt(totals.missing)} a jde asi o ${fmtInt(totals.missingVotes)} hlasů.`}
      >
        <div className="table-wrap">
          <table className="data">
            <thead>
              <tr>
                <th>Zastupitelstvo</th>
                <th>Okrsek</th>
                <th>Kandidát</th>
                <th>Hlasy sousedních kandidátů</th>
              </tr>
            </thead>
            <tbody>
              {data.slips.map((row, index) => (
                <tr key={index}>
                  <td>{row.council}</td>
                  <td className="num">{row.precinct}</td>
                  <td>
                    <div>
                      č. {row.place} {row.name}
                    </div>
                    <div className="small muted">{row.list}</div>
                  </td>
                  <td>
                    <RecordRow around={row.around} />
                    <div className="small muted">{row.reason}</div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Figure>

      <section className="prose">
        <h2>Kandidátky s Piráty</h2>
        <p>
          Přehled všech kandidátek, na kterých Piráti kandidovali samostatně nebo v koalici, ve městech, kde se dají
          hlasy kandidátů kontrolovat.
        </p>
      </section>
      <Figure title="Jak blízko mají k zisku nebo ztrátě mandátu" sub="Hlasy potřebné k dalšímu mandátu a hlasy, při jejichž ztrátě by kandidátka o mandát přišla">
        <div className="table-wrap">
          <table className="data">
            <thead>
              <tr>
                <th>Zastupitelstvo</th>
                <th>Kandidátka</th>
                <th className="r">Mandáty</th>
                <th className="r">Po opravě</th>
                <th className="r">K dalšímu</th>
                <th className="r">Ke ztrátě</th>
                <th className="r">Chybí u kandidátů</th>
                <th>Nejtěsnější pořadí</th>
              </tr>
            </thead>
            <tbody>
              {data.pirates.map((row, index) => (
                <tr key={index}>
                  <td>{row.council}</td>
                  <td>{row.list}</td>
                  <td className="r num">{row.seats}</td>
                  <td className="r num">
                    <span className={row.seats === row.seatsAfter ? "" : "share"}>{row.seatsAfter}</span>
                  </td>
                  <td className="r num">{row.toNextSeat == null ? "" : fmtInt(row.toNextSeat)}</td>
                  <td className="r num">{row.toLoseSeat == null ? "" : fmtInt(row.toLoseSeat)}</td>
                  <td className="r num">{row.missing ? fmtInt(row.missing) : ""}</td>
                  <td>{row.closestPerson}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Figure>

      <section className="prose">
        <h2>Co tahle kontrola umí a co ne</h2>
        <p>
          Přepočet mandátů a pořadí kandidátů je spočítaný pro všech {fmtInt(totals.councils)} zastupitelstev a
          s oficiálním výsledkem se shoduje všude
          {totals.decidedByLot > 0 && (
            <>
              {" "}
              kromě {totals.decidedByLot} obcí, kde o posledním mandátu při rovnosti hlasů rozhodl los
            </>
          )}
          .
        </p>
        <p>
          Chyby u kandidátů se dají hledat jen tam, kde voliči křížkují celé kandidátky a kde je dost okrsků na
          srovnání: v {totals.checked} zastupitelstvech, z toho {data.checked.length - districts.reduce((sum, [, count]) => sum + count, 0)}{" "}
          samostatných městech a {districts.reduce((sum, [, count]) => sum + count, 0)} městských částech a obvodech (
          {districts.map(([city, count]) => `${city} ${count}`).join(", ")}). V menších obcích lidé vybírají jména
          napříč kandidátkami a nula u kandidáta tam je běžný výsledek, ne chyba.
        </p>
        <p>
          Kontrola vidí jen chyby, které porušují vzor uvnitř jedné kandidátky. Nevidí celou hromádku lístků
          započtenou jiné straně ani lístky neprávem vyřazené jako neplatné. Odhad chybějících hlasů vychází ze
          sousedních kandidátů.
        </p>
        <p>
          Dva druhy nálezů se dají splést se skutečným hlasováním, a proto se počítají jen za přísnějších
          podmínek. Kandidátka, kde má hlasy jen několik kandidátů, může být neúplný zápis, ale také pár voličů,
          kteří zakroužkovali stejná jména, třeba své sousedy. Jako chyba se bere, jen když počet hlasů odpovídá
          tomu, kolik lístků by strana v tak velkém okrsku měla dostat, když by stejná jména muselo zakroužkovat
          sedm a více voličů, nebo když táž komise prokazatelně nechala neúplné i jiné kandidátky. Údaj
          několikanásobně vyšší než u sousedů může patřit kandidátovi, kterého v okrsku lidé znají. Jako překlep
          se počítá, jen když se u kandidáta objevuje v jediném okrsku a zároveň vypadá jako číslice napsaná
          dvakrát nebo navíc (22 mezi dvojkami, 165 mezi patnáctkami), shoduje se s pořadovým číslem kandidáta,
          nebo by kandidáta muselo jmenovitě zakroužkovat víc než 15 % voličů okrsku.
        </p>
        <p className="small muted">
          Data:{" "}
          <a href={SOURCE} target="_blank" rel="noreferrer">
            otevřená data ČSÚ k volbám do zastupitelstev obcí 2026
          </a>
          , stav z 11. října 2026.
        </p>
      </section>

      <details className="more">
        <summary>Všech {totals.checked} zastupitelstev, kde se hlasy kandidátů kontrolovaly</summary>
        <div className="more-body">
          <div className="table-wrap">
            <table className="data">
              <thead>
                <tr>
                  <th>Zastupitelstvo</th>
                  <th>Město</th>
                  <th className="r">Okrsků</th>
                  <th className="r">Chybných údajů</th>
                </tr>
              </thead>
              <tbody>
                {data.checked.map((row) => (
                  <tr key={`${row.city}-${row.name}`}>
                    <td>{row.name}</td>
                    <td>{row.city ?? ""}</td>
                    <td className="r num">{row.precincts}</td>
                    <td className="r num">{row.errors || ""}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </details>
    </>
  );
}
