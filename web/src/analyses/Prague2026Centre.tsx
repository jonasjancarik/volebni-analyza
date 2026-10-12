import { Link } from "react-router-dom";
import type { Summary } from "../api";
import { fmtNum, fmtPct } from "../format";
import { useWidth } from "../hooks";
import { Figure, groupColors, type HeatColumn, HeatTable, label, thousands } from "./blocks";
import type { FollowedList, VoterGroup } from "./types";

type When = "then" | "mid" | "now";
type Place = VoterGroup & { turnout: Partial<Record<When, number>> };
type Band = Place & { from: number; to: number | null };
type Housing = Place & { perAddress: [number, number] };

export interface CentreAnalysis {
  council: { election: string; code: string; name: string };
  years: { current: string; previous: string; parliamentary: string };
  summary: Summary;
  lists: FollowedList[];
  city: Place;
  /** Precincts by kilometres from the centre, from the nearest */
  bands: Band[];
  /** From how many kilometres a precinct counts as the outer city */
  outerFrom: number;
  /** Thirds of the outer and the inner precincts by voters per address, from family houses to housing estates */
  outer: Housing[];
  inner: Housing[];
}

const HOUSING = ["Rodinné domy", "Smíšená zástavba", "Sídliště"];

const voters = (group: VoterGroup, key: string, when: When) => group.voters[key]?.[when] ?? 0;
const share = (group: VoterGroup, key: string, when: When = "now") =>
  (voters(group, key, when) / group.voted[when]) * 100;
const camp = (group: VoterGroup) => voters(group, "pirati", "now") + voters(group, "prahaSobe", "now");
/** Both lists' voters now against the Pirates' votes in the parliamentary election, in percent */
const campOverPirati = (group: VoterGroup) => (camp(group) / voters(group, "pirati", "mid")) * 100;
const bandName = (band: Band) => (band.to == null ? `${band.from} a víc` : `${band.from}–${band.to}`);
const pct = (value: number) => fmtNum(value);
const inThousands = (value: number) => fmtNum(value / 1000, 0);

interface Series {
  name: string;
  color: string;
  values: number[];
  dashed?: boolean;
}

/** Shares along an ordered row of places, a line for each list. */
function BandLines({ labels, series, axis }: { labels: string[]; series: Series[]; axis: string }) {
  const [ref, width] = useWidth<HTMLDivElement>(720);
  const height = 280;
  const [left, right, top, bottom] = [34, 14, 10, 46];
  const highest = Math.ceil(Math.max(...series.flatMap((item) => item.values)) / 5) * 5;
  const x = (index: number) => left + (index / (labels.length - 1)) * (width - left - right);
  const y = (value: number) => top + (1 - value / highest) * (height - top - bottom);
  const ticks = Array.from({ length: highest / 5 + 1 }, (_, index) => index * 5).filter((tick) => tick % 10 === 0);
  return (
    <div ref={ref}>
      <div className="legend" style={{ marginBottom: 10 }}>
        {series.map((item) => (
          <span className="legend-item" key={item.name}>
            <span
              style={{
                width: 18,
                borderTop: `3px ${item.dashed ? "dashed" : "solid"} ${item.color}`,
              }}
            />
            {item.name}
          </span>
        ))}
      </div>
      <svg className="chart" width={width} height={height} role="img" aria-label="Podíl hlasů podle vzdálenosti od centra">
        {ticks.map((tick) => (
          <g key={tick}>
            <line className={tick === 0 ? "axis-line" : "grid-line"} x1={left} x2={width - right} y1={y(tick)} y2={y(tick)} />
            <text x={left - 8} y={y(tick)} dy="0.35em" textAnchor="end">
              {tick} %
            </text>
          </g>
        ))}
        {labels.map((name, index) => (
          <text key={name} className="label" x={x(index)} y={height - bottom + 18} textAnchor="middle">
            {name}
          </text>
        ))}
        <text x={(left + width - right) / 2} y={height - 6} textAnchor="middle">
          {axis}
        </text>
        {series.map((item) => (
          <g key={item.name}>
            <polyline
              fill="none"
              stroke={item.color}
              strokeWidth={2.5}
              strokeDasharray={item.dashed ? "6 5" : undefined}
              strokeLinejoin="round"
              points={item.values.map((value, index) => `${x(index)},${y(value)}`).join(" ")}
            />
            {item.values.map((value, index) => (
              <circle key={index} cx={x(index)} cy={y(value)} r={3.5} fill={item.color}>
                <title>{`${item.name}, ${labels[index]} km: ${fmtPct(value)}`}</title>
              </circle>
            ))}
          </g>
        ))}
      </svg>
    </div>
  );
}

export function Prague2026Centre({ data }: { data: CentreAnalysis }) {
  const { years, bands, outer, city } = data;
  const colorOf = groupColors(data.lists);
  const [nearest, farthest] = [bands[0], bands[bands.length - 1]];
  const beyond = bands.filter((band) => band.from >= 4);
  const total = (rows: VoterGroup[], value: (row: VoterGroup) => number) => rows.reduce((sum, row) => sum + value(row), 0);
  const livingBeyond = (total(beyond, (row) => row.registered) / city.registered) * 100;
  const votesBeyond = (total(beyond, camp) / camp(city)) * 100;
  const ratios = bands.map(campOverPirati);
  const [houses, estates] = [outer[0], outer[outer.length - 1]];
  const denseInner = data.inner[data.inner.length - 1];
  const councilPath = `/${data.council.election}/${data.council.code}`;

  const lists = ["prahaSobe", "pirati", "stan", "spolu", "ano"];
  const shareColumns = <Row extends VoterGroup>(group: string): HeatColumn<Row>[] =>
    lists.map((key) => ({
      group,
      head: label(key),
      value: (row: Row) => share(row, key),
      format: pct,
      tint: colorOf(key),
    }));

  const bandColumns: HeatColumn<Band>[] = [
    { head: "Zapsaní voliči (tis.)", value: (row) => row.registered, format: inThousands },
    ...shareColumns<Band>(`Podíl hlasů ${years.current}`),
    {
      group: `Sněmovna ${years.parliamentary}`,
      head: "Piráti",
      value: (row) => share(row, "pirati", "mid"),
      format: pct,
      tint: colorOf("pirati"),
    },
    {
      head: "Obě proti sněmovním hlasům Pirátů",
      value: campOverPirati,
      format: (value) => fmtPct(value, 0),
    },
  ];

  const housingColumns: HeatColumn<Housing>[] = [
    { head: "Zapsaní voliči (tis.)", value: (row) => row.registered, format: inThousands },
    { group: "Účast", head: years.parliamentary, value: (row) => row.turnout.mid ?? 0, format: pct },
    { group: "Účast", head: years.current, value: (row) => row.turnout.now ?? 0, format: pct, tint: "var(--series-1)" },
    ...shareColumns<Housing>(`Podíl hlasů ${years.current}`),
  ];

  return (
    <>
      <div className="tiles article-tiles">
        <div className="tile">
          <div className="value num">
            {fmtNum(share(nearest, "prahaSobe"), 0)} → {fmtPct(share(farthest, "prahaSobe"), 0)}
          </div>
          <div className="label">Praha Sobě od centra k okraji města</div>
        </div>
        <div className="tile">
          <div className="value num">
            {fmtNum(share(nearest, "pirati"), 0)} → {fmtPct(share(farthest, "pirati"), 0)}
          </div>
          <div className="label">
            Piráti; ve sněmovních volbách {fmtNum(share(nearest, "pirati", "mid"), 0)} →{" "}
            {fmtPct(share(farthest, "pirati", "mid"), 0)}
          </div>
        </div>
        <div className="tile">
          <div className="value num">{fmtPct(livingBeyond, 0)}</div>
          <div className="label">voličů žije dál než 4 km od centra</div>
        </div>
        {estates && houses && (
          <div className="tile">
            <div className="value num">{fmtPct(estates.turnout.now ?? 0, 0)}</div>
            <div className="label">
              účast na okrajových sídlištích; ve čtvrtích rodinných domů {fmtPct(houses.turnout.now ?? 0, 0)}
            </div>
          </div>
        )}
      </div>

      <section className="prose">
        <h2>Shrnutí</h2>
        <p>
          Podpora Prahy Sobě klesá od centra k okraji na polovinu. U Pirátů je pokles v komunálních volbách mírný, ve
          sněmovních strmý.
        </p>
        <p>
          Většina hlasů je přesto mimo centrum. Dál než 4 km žije {fmtPct(livingBeyond, 0)} voličů a obě kandidátky
          tam berou {fmtPct(votesBeyond, 0)} svých hlasů.
        </p>
        {estates && houses && (
          <p>
            Okraj ale není jeden. Na sídlištích je nízká účast, slabý STAN i Spolu a silné ANO. Ve čtvrtích rodinných
            domů je účast vysoká a STAN se Spolu mají {fmtPct(share(houses, "stan") + share(houses, "spolu"), 0)}{" "}
            hlasů. Prostor je hlavně na sídlištích, a to v účasti.
          </p>
        )}
      </section>

      <section className="prose">
        <h2>Od centra k okraji</h2>
      </section>

      <Figure
        title="Podíl hlasů podle vzdálenosti od centra"
        sub={`Volby do zastupitelstva ${years.current}; přerušovaně výsledek Pirátů ve sněmovních volbách ${years.parliamentary}`}
      >
        <BandLines
          labels={bands.map(bandName)}
          axis="kilometrů od Můstku"
          series={[
            ...lists.map((key) => ({ name: label(key), color: colorOf(key), values: bands.map((band) => share(band, key)) })),
            {
              name: `Piráti do Sněmovny ${years.parliamentary}`,
              color: colorOf("pirati"),
              values: bands.map((band) => share(band, "pirati", "mid")),
              dashed: true,
            },
          ]}
        />
      </Figure>

      <section className="prose">
        <p>
          Proti sněmovnímu výsledku ztrácejí Piráti nejvíc v centru, kde je nejsilnější Praha Sobě. STAN a Spolu mají
          všude zhruba stejně, ANO k okraji roste.
        </p>
      </section>

      <Figure
        title="Pásma podle vzdálenosti od centra"
        sub="Kilometry vzdušnou čarou od Můstku. Podíly jsou v procentech hlasů."
        note={
          <>
            Poslední sloupec říká, kolik procent loňských sněmovních hlasů Pirátů představují letošní voliči Pirátů
            a Prahy Sobě dohromady.{" "}
            <Link className="inline-link" to={`${councilPath}/mapa`}>
              Podívat se na mapu okrsků
            </Link>
          </>
        }
      >
        <HeatTable rows={bands} rowHead="Km od centra" rowLabel={bandName} columns={bandColumns} />
      </Figure>

      <section className="prose">
        <p>
          Obě kandidátky mají dohromady v každém pásmu {fmtNum(Math.min(...ratios), 0)} až{" "}
          {fmtPct(Math.max(...ratios), 0)} loňských sněmovních hlasů Pirátů. Slabší výsledek na okraji tedy není
          zvláštnost komunálních voleb: bydlí tam méně lidí, kteří je volí i celostátně.
        </p>
      </section>

      {estates && houses && (
        <>
          <section className="prose">
            <h2>Sídliště a rodinné domy</h2>
            <p>
              Okrsky dál než {data.outerFrom} km od centra jsou rozdělené do třetin podle počtu voličů na jednu
              adresu. V rodinných domech připadá na adresu nejvýš {fmtNum(houses.perAddress[1], 0)} voličů, na
              sídlištích aspoň {fmtNum(estates.perAddress[0], 0)}.
            </p>
          </section>

          <Figure
            title={`Okrajové okrsky podle zástavby`}
            sub={`Okrsky ${data.outerFrom} a víc km od centra. Účast a podíly v procentech.`}
          >
            <HeatTable
              rows={outer}
              rowHead="Zástavba"
              rowLabel={(row) => HOUSING[outer.indexOf(row)]}
              columns={housingColumns}
            />
          </Figure>

          <section className="prose">
            <p>
              Na sídlištích nejsou Piráti slabší než v rodinných domech ({fmtNum(share(estates, "pirati"))}{" "}
              a {fmtPct(share(houses, "pirati"))}). Liší se účast: mezi sněmovními a komunálními volbami tam klesá
              z {fmtNum(estates.turnout.mid ?? 0, 0)} na {fmtPct(estates.turnout.now ?? 0, 0)}. Piráti tam loni dostali{" "}
              {thousands(voters(estates, "pirati", "mid"))} hlasů, letos je volilo {thousands(voters(estates, "pirati", "now"))}{" "}
              lidí.
            </p>
            <p>
              Ve čtvrtích rodinných domů přišlo {fmtPct(houses.turnout.now ?? 0, 0)} voličů a většinu hlasů mají STAN
              se Spolu.
              {denseInner && (
                <>
                  {" "}
                  Nízká účast jde s hustou zástavbou i blíž k centru ({fmtPct(denseInner.turnout.now ?? 0, 0)}).
                </>
              )}
            </p>
          </section>
        </>
      )}

      <section className="prose">
        <h2>Co z toho plyne</h2>
        <p>
          Na sídlištích jde o účast vlastních sněmovních voličů, ne o přesvědčování cizích. Růst nad to by znamenal
          získávat voliče ANO a lidi, kteří nevolí vůbec.
        </p>
        <p>Čtvrti rodinných domů jsou nejtěžší: účast je tam vysoká a volí se hlavně STAN a Spolu.</p>
        <p>Jde o průměry za okrsky, ne o jednotlivé voliče.</p>
      </section>

      <section className="card method-notes">
        <h3>Jak se to počítalo</h3>
        <p className="note">
          Vzdálenost je vzdušná čára od Můstku ke středu adres okrsku. Doba cesty MHD by některé okrsky zařadila
          jinak, hlavně ty u metra a železnice.
        </p>
        <p className="note">
          Zástavbu zastupuje počet zapsaných voličů na jednu adresu z registru adres. Je to hrubý znak: bytový dům
          s jedním vchodem se počítá jako jedna adresa stejně jako rodinný dům.
        </p>
        <p className="note">
          Hlasy v komunálních volbách jsou přepočtené na voliče: podíl kandidátky krát počet odevzdaných obálek.
        </p>
      </section>
    </>
  );
}
