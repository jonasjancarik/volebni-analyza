import { lazy, Suspense, useState } from "react";
import { Loading } from "../components/State";
import { fmtInt, fmtNum, fmtPct } from "../format";
import { useTooltip, useWidth } from "../hooks";
import { Figure, groupColors, type HeatColumn, HeatTable, label, thousands } from "./blocks";
import {
  bandName,
  type CentreAnalysis,
  kindColor,
  type KindGroup,
  kindName,
  KINDS,
  type Estimate,
  type Metric,
  type Place,
  type PrecinctPoint,
  type ShareModel,
  SHARES,
  type TimeBand,
  type When,
} from "./centreShared";
import type { VoterGroup } from "./types";
import "./centre.css";

// The map library is large; it loads only when the article is opened
const CentreMap = lazy(() => import("./CentreMap"));

const voters = (group: VoterGroup, key: string, when: When) => group.voters[key]?.[when] ?? 0;
const share = (group: VoterGroup, key: string, when: When = "now") =>
  (voters(group, key, when) / group.voted[when]) * 100;
const camp = (group: VoterGroup) => voters(group, "pirati", "now") + voters(group, "prahaSobe", "now");
const campShare = (group: VoterGroup) => (camp(group) / group.voted.now) * 100;
/** Both lists' voters now against the Pirates' votes in the parliamentary election, in percent */
const campOverPirati = (group: VoterGroup) => (camp(group) / voters(group, "pirati", "mid")) * 100;
/** The Pirates' part of both lists' voters, in percent */
const piratiOfCamp = (group: VoterGroup, when: When = "now") =>
  (voters(group, "pirati", when) / (voters(group, "pirati", when) + voters(group, "prahaSobe", when))) * 100;
const pct = (value: number) => fmtNum(value);
/** A number with its sign, such as "−0,51"; no sign where it rounds to zero */
const signed = (value: number, decimals = 2) => {
  const rounded = Math.round(value * 10 ** decimals);
  return `${rounded < 0 ? "−" : rounded > 0 ? "+" : ""}${fmtNum(Math.abs(rounded) / 10 ** decimals, decimals)}`;
};
const fmtR = (value: number) => signed(value);
/** Percentage points, without the sign */
const percentagePoints = (value: number, decimals = 1) => fmtNum(Math.abs(value), decimals);
/** What each correlated measure is, in the order of the table */
const MEASURES: Record<string, string> = {
  minutes: "Doba cesty do centra",
  km: "Vzdálenost od centra vzdušnou čarou",
  older: "Podíl bytů ve starších bytových domech",
  panel: "Podíl bytů v panelových domech",
  newer: "Podíl bytů v novějších bytových domech",
  houses: "Podíl bytů v rodinných domech",
};
const inThousands = (value: number) => fmtNum(value / 1000, 0);

interface Series {
  name: string;
  color: string;
  values: number[];
  /** A stroke pattern for a line that is not this year's council election */
  dash?: string;
}

const DOTS = "2 4";
const stroke = (item: Series) => (item.dash === DOTS ? "dotted" : item.dash ? "dashed" : "solid");

/** Shares along an ordered row of places, a line for each list. Lines can be hidden in the legend. */
function BandLines({ labels, series, axis }: { labels: string[]; series: Series[]; axis: string }) {
  const [ref, width] = useWidth<HTMLDivElement>(720);
  const [hidden, setHidden] = useState<string[]>([]);
  const [focused, setFocused] = useState<string | null>(null);
  const [band, setBand] = useState<number | null>(null);
  const tooltip = useTooltip();
  const height = 300;
  const [left, right, top, bottom] = [34, 14, 10, 46];
  const shown = series.filter((item) => !hidden.includes(item.name));
  const highest = Math.max(5, Math.ceil(Math.max(0, ...shown.flatMap((item) => item.values)) / 5) * 5);
  const step = (width - left - right) / (labels.length - 1);
  const x = (index: number) => left + index * step;
  const y = (value: number) => top + (1 - value / highest) * (height - top - bottom);
  const ticks = Array.from({ length: highest / 5 + 1 }, (_, index) => index * 5).filter(
    (tick) => highest <= 15 || tick % 10 === 0,
  );
  const toggle = (name: string) =>
    setHidden(hidden.includes(name) ? hidden.filter((item) => item !== name) : [...hidden, name]);
  const leave = () => {
    setBand(null);
    tooltip.hide();
  };
  return (
    <div ref={ref}>
      <div className="legend" style={{ marginBottom: 10 }}>
        {series.map((item) => {
          const off = hidden.includes(item.name);
          return (
            <button
              key={item.name}
              className="legend-item text-button line-key"
              aria-pressed={!off}
              style={{ opacity: off ? 0.4 : 1 }}
              onClick={() => toggle(item.name)}
              onMouseEnter={() => setFocused(off ? null : item.name)}
              onMouseLeave={() => setFocused(null)}
            >
              <span style={{ width: 18, borderTop: `3px ${stroke(item)} ${item.color}` }} />
              {item.name}
            </button>
          );
        })}
      </div>
      <svg
        className="chart"
        width={width}
        height={height}
        role="img"
        aria-label="Podíl hlasů podle doby cesty do centra"
        onMouseLeave={leave}
      >
        {ticks.map((tick) => (
          <g key={tick}>
            <line className={tick === 0 ? "axis-line" : "grid-line"} x1={left} x2={width - right} y1={y(tick)} y2={y(tick)} />
            <text x={left - 8} y={y(tick)} dy="0.35em" textAnchor="end">
              {tick} %
            </text>
          </g>
        ))}
        {labels.map((name, index) => (
          <text
            key={name}
            className="label"
            x={x(index)}
            y={height - bottom + 18}
            textAnchor="middle"
            fontWeight={band === index ? 650 : undefined}
          >
            {name}
          </text>
        ))}
        <text x={(left + width - right) / 2} y={height - 6} textAnchor="middle">
          {axis}
        </text>
        {band != null && <line className="axis-line" x1={x(band)} x2={x(band)} y1={top} y2={height - bottom} />}
        {shown.map((item) => (
          <g key={item.name} opacity={focused && focused !== item.name ? 0.2 : 1}>
            <polyline
              fill="none"
              stroke={item.color}
              strokeWidth={focused === item.name ? 3.5 : 2.5}
              strokeDasharray={item.dash}
              strokeLinejoin="round"
              points={item.values.map((value, index) => `${x(index)},${y(value)}`).join(" ")}
            />
            {item.values.map((value, index) => (
              <circle key={index} cx={x(index)} cy={y(value)} r={band === index ? 5 : 3.5} fill={item.color} />
            ))}
          </g>
        ))}
        {labels.map((name, index) => (
          <rect
            key={name}
            x={x(index) - step / 2}
            y={0}
            width={step}
            height={height}
            fill="transparent"
            onMouseMove={(event) => {
              setBand(index);
              tooltip.show(
                event,
                <>
                  <div className="t-title">{name} minut do centra</div>
                  {[...shown]
                    .sort((a, b) => b.values[index] - a.values[index])
                    .map((item) => (
                      <div className="t-line" key={item.name}>
                        <span style={{ width: 14, borderTop: `3px ${stroke(item)} ${item.color}` }} />
                        <span>{item.name}</span>
                        <span className="num">{fmtPct(item.values[index])}</span>
                      </div>
                    ))}
                </>,
              );
            }}
          />
        ))}
      </svg>
      {tooltip.element}
    </div>
  );
}

interface Spoke {
  name: string;
  /** Percent of the city's value; 100 is the same as the whole city */
  value: number;
  text: string;
}

/** One kind of place against the whole city: the further a corner reaches past the ring, the more it has of that. */
function Radar({ spokes, color }: { spokes: Spoke[]; color: string }) {
  // Wider than tall, so that the names beside it have room
  const [width, height] = [290, 210];
  const reach = 70;
  // The middle of the chart is half the city's value and the edge one and a half
  const radius = (value: number) => (Math.max(50, Math.min(150, value)) - 50) / 100 * reach;
  const point = (index: number, distance: number) => {
    const angle = (index / spokes.length) * 2 * Math.PI - Math.PI / 2;
    return [width / 2 + Math.cos(angle) * distance, height / 2 + Math.sin(angle) * distance];
  };
  const ring = (value: number) => spokes.map((_, index) => point(index, radius(value)).join(",")).join(" ");
  return (
    <svg className="chart" viewBox={`0 0 ${width} ${height}`} role="img" aria-label="Srovnání s celým městem">
      <polygon points={ring(150)} fill="none" className="grid-line" />
      <polygon points={ring(50 + 100 / 3)} fill="none" className="grid-line" />
      {spokes.map((spoke, index) => {
        const [x, y] = point(index, reach);
        const [labelX, labelY] = point(index, reach + 14);
        return (
          <g key={spoke.name}>
            <line className="grid-line" x1={width / 2} y1={height / 2} x2={x} y2={y} />
            <text
              className="label"
              x={labelX}
              y={labelY}
              dy="0.35em"
              textAnchor={Math.abs(labelX - width / 2) < 8 ? "middle" : labelX > width / 2 ? "start" : "end"}
            >
              {spoke.name}
              <title>{spoke.text}</title>
            </text>
          </g>
        );
      })}
      <polygon points={ring(100)} fill="none" stroke="var(--ink-3)" strokeWidth={1.2} strokeDasharray="4 3" />
      <polygon
        points={spokes.map((spoke, index) => point(index, radius(spoke.value)).join(",")).join(" ")}
        fill={color}
        fillOpacity={0.28}
        stroke={color}
        strokeWidth={2}
        strokeLinejoin="round"
      />
      {spokes.map((spoke, index) => {
        const [x, y] = point(index, radius(spoke.value));
        return (
          <circle key={spoke.name} cx={x} cy={y} r={3} fill={color}>
            <title>{spoke.text}</title>
          </circle>
        );
      })}
    </svg>
  );
}

/** Every precinct by travel time and a share the reader picks, coloured by its housing. */
function PrecinctScatter({ precincts }: { precincts: PrecinctPoint[] }) {
  const [ref, width] = useWidth<HTMLDivElement>(720);
  const [picked, setPicked] = useState(SHARES[0].key);
  const [only, setOnly] = useState<string | null>(null);
  const tooltip = useTooltip();
  const metric: Metric = SHARES.find((item) => item.key === picked) ?? SHARES[0];
  const height = 380;
  const [left, right, top, bottom] = [40, 12, 10, 42];
  const points = precincts
    .map((precinct) => ({ precinct, value: metric.value(precinct) }))
    .filter((point): point is { precinct: PrecinctPoint; value: number } => point.value != null);
  const farthest = 60;
  const highest = Math.ceil(Math.max(...points.map((point) => point.value)) / 10) * 10;
  const x = (minutes: number) => left + (Math.min(minutes, farthest) / farthest) * (width - left - right);
  const y = (value: number) => top + (1 - value / highest) * (height - top - bottom);
  const largest = Math.max(...precincts.map((precinct) => precinct.registered));
  return (
    <div ref={ref}>
      <div className="toolbar" style={{ marginBottom: 12 }}>
        <div className="segmented" role="group" aria-label="Co má graf ukazovat">
          {SHARES.map((item) => (
            <button key={item.key} aria-pressed={picked === item.key} onClick={() => setPicked(item.key)}>
              {item.label}
            </button>
          ))}
        </div>
      </div>
      <div className="legend" style={{ marginBottom: 6 }}>
        {Object.entries(KINDS).map(([kind, item]) => (
          <button
            key={kind}
            className="legend-item text-button"
            style={{ padding: 0, fontWeight: 500, color: "var(--ink-2)", opacity: only && only !== kind ? 0.45 : 1 }}
            onClick={() => setOnly(only === kind ? null : kind)}
            aria-pressed={only === kind}
          >
            <span className="swatch" style={{ background: item.color }} />
            {item.name}
          </button>
        ))}
      </div>
      <svg className="chart" width={width} height={height} role="img" aria-label={`Okrsky podle doby cesty a ${metric.label}`}>
        {Array.from({ length: highest / 10 + 1 }, (_, index) => index * 10).map((tick) => (
          <g key={tick}>
            <line className={tick === 0 ? "axis-line" : "grid-line"} x1={left} x2={width - right} y1={y(tick)} y2={y(tick)} />
            <text x={left - 8} y={y(tick)} dy="0.35em" textAnchor="end">
              {tick} %
            </text>
          </g>
        ))}
        {[0, 10, 20, 30, 40, 50, 60].map((tick) => (
          <text key={tick} x={x(tick)} y={height - bottom + 16} textAnchor="middle">
            {tick === farthest ? `${tick}+` : tick}
          </text>
        ))}
        <text x={(left + width - right) / 2} y={height - 6} textAnchor="middle">
          minut do centra MHD
        </text>
        {points.map(({ precinct, value }) => (
          <circle
            key={precinct.id}
            className="scatter-dot"
            cx={x(precinct.minutes)}
            cy={y(value)}
            r={2 + Math.sqrt(precinct.registered / largest) * 3.5}
            fill={kindColor(precinct.kind)}
            opacity={only ? (only === precinct.kind ? 0.85 : 0.06) : 0.6}
            onMouseMove={(event) =>
              tooltip.show(
                event,
                <>
                  <div className="t-sub">Okrsek {precinct.id}</div>
                  <div className="t-title">
                    {metric.label} {metric.format(value)}
                  </div>
                  <div className="t-sub">
                    {kindName(precinct.kind)}, {fmtNum(precinct.minutes, 0)} minut do centra
                  </div>
                </>,
              )
            }
            onMouseLeave={tooltip.hide}
          />
        ))}
      </svg>
      {tooltip.element}
    </div>
  );
}

export function Prague2026Centre({ data }: { data: CentreAnalysis }) {
  const { years, times, kinds, city } = data;
  const colorOf = groupColors(data.lists);
  const [nearest, farthest] = [times[0], times[times.length - 1]];
  const kind = (key: string) => kinds.find((item) => item.kind === key);
  const [older, panel, houses] = [kind("older"), kind("panel"), kind("houses")];
  const apartments = kinds.filter((item) => item.kind !== "houses" && item.kind !== "mixed");
  const ratios = times.map(campOverPirati);
  // How the Pirates' parliamentary share compares with both lists' share now, band by band
  const midOverCamp = times.map((band) => share(band, "pirati", "mid") / campShare(band));
  const kept = times.map((band) => (share(band, "pirati") / share(band, "pirati", "then")) * 100);
  const campColor = "var(--ink-2)";

  // Districts where Praha Sobě is strong in the district council, as "1, 2, 5, 6 a 7"
  const { localBase } = data;
  const strongNumbers = localBase.districts.map((district) => Number(district.name.replace(/\D/g, ""))).sort((a, b) => a - b);
  const strongNames = strongNumbers.map((number, index) => (index === 0 ? "" : index === strongNumbers.length - 1 ? " a " : ", ") + number).join("");
  const weakestLocal = Math.min(...localBase.districts.map((district) => district.share));
  const restSplit = localBase.times.flatMap((band) => (band.rest ? [piratiOfCamp(band.rest)] : []));
  const splitColumns: { head: string; group: (band: (typeof localBase.times)[number], index: number) => VoterGroup | null }[] = [
    { head: "Celá Praha", group: (_, index) => times[index] },
    { head: `Praha ${strongNames}`, group: (band) => band.strong },
    { head: "Zbytek Prahy", group: (band) => band.rest },
  ];
  const lists = ["prahaSobe", "pirati", "stan", "spolu", "ano"];

  // The same travel time, another kind of housing
  const rings = [...new Map(data.kindsByTime.map((item) => [`${item.from}`, item])).values()].sort((a, b) => a.from - b.from);
  const atTime = (key: string, from: number) => data.kindsByTime.find((item) => item.kind === key && item.from === from);
  const middleRing = rings[Math.min(1, rings.length - 1)];
  const olderMiddle = middleRing && atTime("older", middleRing.from);
  const panelMiddle = middleRing && atTime("panel", middleRing.from);

  const shareColumns = <Row extends VoterGroup>(group: string): HeatColumn<Row>[] =>
    lists.map((key) => ({ group, head: label(key), value: (row: Row) => share(row, key), format: pct, tint: colorOf(key) }));

  const timeColumns: HeatColumn<TimeBand>[] = [
    { head: "Zapsaní voliči (tis.)", value: (row) => row.registered, format: inThousands },
    ...shareColumns<TimeBand>(`Zastupitelstvo ${years.current}`),
    {
      group: `Sněmovna ${years.parliamentary}`,
      head: "Piráti",
      value: (row) => share(row, "pirati", "mid"),
      format: pct,
      tint: colorOf("pirati"),
    },
    { head: "Obě proti sněmovním hlasům Pirátů", value: campOverPirati, format: (value) => fmtPct(value, 0) },
  ];

  const campColumns: HeatColumn<TimeBand>[] = [
    {
      group: `Sněmovna ${years.parliamentary}`,
      head: "Piráti",
      value: (row) => share(row, "pirati", "mid"),
      format: pct,
      tint: colorOf("pirati"),
    },
    { group: `Zastupitelstvo ${years.current}`, head: "Obě dohromady", value: campShare, format: pct, tint: campColor },
    {
      group: `Zastupitelstvo ${years.current}`,
      head: label("prahaSobe"),
      value: (row) => share(row, "prahaSobe"),
      format: pct,
      tint: colorOf("prahaSobe"),
    },
    {
      group: `Zastupitelstvo ${years.current}`,
      head: label("pirati"),
      value: (row) => share(row, "pirati"),
      format: pct,
      tint: colorOf("pirati"),
    },
    {
      group: "Kolik z hlasů obou kandidátek mají Piráti",
      head: years.previous,
      value: (row) => piratiOfCamp(row, "then"),
      format: (value) => fmtPct(value, 0),
    },
    {
      group: "Kolik z hlasů obou kandidátek mají Piráti",
      head: years.current,
      value: (row) => piratiOfCamp(row),
      format: (value) => fmtPct(value, 0),
    },
  ];

  const kindColumns: HeatColumn<KindGroup>[] = [
    { head: "Zapsaní voliči (tis.)", value: (row) => row.registered, format: inThousands },
    { head: "Minut do centra", value: (row) => row.minutes, format: (value) => fmtNum(value, 0) },
    { group: "Účast", head: years.parliamentary, value: (row) => row.turnout.mid ?? 0, format: pct },
    { group: "Účast", head: years.current, value: (row) => row.turnout.now ?? 0, format: pct, tint: "var(--series-1)" },
    ...shareColumns<KindGroup>(`Zastupitelstvo ${years.current}`),
  ];

  // How closely single precincts follow travel time and housing
  const { links } = data;
  const correlation = (measure: string) => links.correlations.find((row) => row.measure === measure);
  const [byMinutes, byOlder] = [correlation("minutes"), correlation("older")];
  const { minutes: alone, both, districts: inside } = links.models;
  // Within a city district the effect of travel time may not differ from none
  const minutesUnclear = inside.minutes != null && Math.abs(inside.minutes.value) < 2 * inside.minutes.error;
  const panelClear = inside.panel != null && Math.abs(inside.panel.value) > 2 * inside.panel.error;
  type Correlation = (typeof links.correlations)[number];
  const pearson = "Pearsonův r";
  const correlationColumns: HeatColumn<Correlation>[] = [
    { group: pearson, head: label("prahaSobe"), value: (row) => row.prahaSobe, format: fmtR, tint: "change" },
    { group: pearson, head: label("pirati"), value: (row) => row.pirati, format: fmtR, tint: "change" },
    { group: pearson, head: "Obě dohromady", value: (row) => row.camp, format: fmtR, tint: "change" },
    {
      group: "Spearmanův ρ",
      head: label("prahaSobe"),
      value: (row) => row.prahaSobeRank,
      format: fmtR,
      tint: "change",
    },
  ];
  const modelRows: { name: string; model: ShareModel }[] = [
    { name: "Jen doba cesty", model: links.models.minutes },
    { name: "Jen zástavba", model: links.models.housing },
    { name: "Doba cesty a zástavba", model: both },
    { name: "Totéž uvnitř městských částí", model: inside },
  ];
  const modelColumns: { head: string; pick: (model: ShareModel) => Estimate | undefined; decimals: number }[] = [
    { head: "Doba cesty (za minutu)", pick: (model) => model.minutes, decimals: 2 },
    { head: "Panelové domy", pick: (model) => model.panel, decimals: 1 },
    { head: "Novější bytové domy", pick: (model) => model.newer, decimals: 1 },
    { head: "Rodinné domy", pick: (model) => model.houses, decimals: 1 },
  ];

  const spokes = (group: Place) => [
    { name: "Účast", now: group.turnout.now ?? 0, all: city.turnout.now ?? 1 },
    ...lists.map((key) => ({ name: label(key), now: share(group, key), all: share(city, key) })),
  ].map((item) => ({
    name: item.name,
    value: (item.now / item.all) * 100,
    text: `${item.name}: ${fmtPct(item.now)}, v celém městě ${fmtPct(item.all)}`,
  }));

  return (
    <>
      <div className="tiles article-tiles">
        <div className="tile">
          <div className="value num">
            {fmtNum(share(nearest, "prahaSobe"), 0)} → {fmtPct(share(farthest, "prahaSobe"), 0)}
          </div>
          <div className="label">
            Praha Sobě v okrscích do {nearest.to} minut od centra a v těch nad {farthest.from} minut
          </div>
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
        {panel && (
          <div className="tile">
            <div className="value num">{fmtPct((panel.registered / city.registered) * 100, 0)}</div>
            <div className="label">
              voličů bydlí v okrscích panelových domů; Praha Sobě tam má {fmtPct(share(panel, "prahaSobe"))}
            </div>
          </div>
        )}
        {houses && (
          <div className="tile">
            <div className="value num">{fmtPct(houses.turnout.now ?? 0, 0)}</div>
            <div className="label">
              účast ve čtvrtích rodinných domů; v bytových domech{" "}
              {fmtNum(Math.min(...apartments.map((item) => item.turnout.now ?? 0)), 0)}–
              {fmtPct(Math.max(...apartments.map((item) => item.turnout.now ?? 0)), 0)}
            </div>
          </div>
        )}
      </div>

      <section className="prose">
        <h2>Shrnutí</h2>
        <ul className="takeaways">
          <li>
            Podpora Prahy Sobě klesá s dobou cesty do centra skoro na polovinu, u Pirátů jen mírně.
          </li>
          <li>
            Do Sněmovny mají Piráti křivku stejně strmou jako letos obě kandidátky dohromady. V komunálních volbách
            se o tyto hlasy dělí a Praha Sobě z nich má víc v Praze {strongNames}, kde má silnou kandidátku i do
            zastupitelstva městské části. Stejné to bylo už v roce {years.previous}.
          </li>
          {olderMiddle && panelMiddle && (
            <li>
              Víc než vzdálenost rozhoduje, v čem lidé bydlí. Při stejném dojezdu {bandName(middleRing)} minut má Praha
              Sobě ve starších bytových domech {fmtPct(share(olderMiddle, "prahaSobe"), 0)} a na sídlištích{" "}
              {fmtPct(share(panelMiddle, "prahaSobe"), 0)}, Piráti v obou kolem{" "}
              {fmtPct((share(olderMiddle, "pirati") + share(panelMiddle, "pirati")) / 2, 0)}.
            </li>
          )}
          <li>
            Hlasy navíc v Praze {strongNames} by Piráti brali hlavně Praze Sobě. Nejméně si obě kandidátky konkurují
            na sídlištích{panel && <>, kde žije {fmtPct((panel.registered / city.registered) * 100, 0)} voličů</>}.
          </li>
        </ul>
      </section>

      <Figure
        title="Okrsky na mapě"
        sub="Vyberte, co má mapa ukazovat. Najetím na okrsek uvidíte jeho údaje, kliknutím ho otevřete v mapě výsledků."
      >
        <Suspense fallback={<Loading text="Načítám mapu…" />}>
          <CentreMap election={data.council.election} code={data.council.code} precincts={data.precincts} />
        </Suspense>
      </Figure>

      <section className="prose">
        <h2>Doba cesty do centra</h2>
      </section>

      <Figure
        title="Podíl hlasů podle doby cesty do centra"
        sub={`Volby do zastupitelstva ${years.current}; přerušovaně výsledek Pirátů ve sněmovních volbách ${years.parliamentary}. Najetím na graf uvidíte čísla za jedno pásmo, kliknutím v legendě čáru skryjete.`}
      >
        <BandLines
          labels={times.map(bandName)}
          axis="minut do centra MHD v ranní špičce"
          series={[
            ...lists.map((key) => ({ name: label(key), color: colorOf(key), values: times.map((band) => share(band, key)) })),
            {
              name: `Piráti do Sněmovny ${years.parliamentary}`,
              color: colorOf("pirati"),
              values: times.map((band) => share(band, "pirati", "mid")),
              dash: "6 5",
            },
          ]}
        />
      </Figure>

      <section className="prose">
        <p>
          Proti sněmovnímu výsledku ztrácejí Piráti nejvíc blízko centra, kde je nejsilnější Praha Sobě; proč, je
          v další kapitole. STAN a Spolu
          mají všude zhruba stejně, ANO se vzdáleností roste.
        </p>
      </section>

      <Figure
        title="Pásma podle doby cesty"
        sub="Minuty ode dveří na Můstek pěšky a MHD. Podíly jsou v procentech hlasů."
        note="Poslední sloupec říká, kolik procent loňských sněmovních hlasů Pirátů představují letošní voliči Pirátů a Prahy Sobě dohromady."
      >
        <HeatTable rows={times} rowHead="Minut do centra" rowLabel={bandName} columns={timeColumns} />
      </Figure>

      <section className="prose">
        <p>
          Obě kandidátky mají dohromady v každém pásmu {fmtNum(Math.min(...ratios), 0)} až{" "}
          {fmtPct(Math.max(...ratios), 0)} loňských sněmovních hlasů Pirátů. Slabší výsledek daleko od centra tedy
          není zvláštnost komunálních voleb: bydlí tam méně lidí, kteří je volí i celostátně.
        </p>
      </section>

      <section className="prose">
        <h2>Proč je křivka Pirátů v komunálních volbách plošší</h2>
        <p>
          Do Sněmovny Praha Sobě nekandiduje a Piráti dostávají i hlasy lidí, kteří ji volí do zastupitelstva.
          V komunálních volbách se o ně obě kandidátky dělí a Praha Sobě z nich má blízko centra víc: do {nearest.to}{" "}
          minut připadá na Piráty {fmtPct(piratiOfCamp(nearest), 0)} hlasů obou kandidátek, nad {farthest.from} minut{" "}
          {fmtPct(piratiOfCamp(farthest), 0)}. Proti sněmovním volbám tak Pirátům u centra ubude víc než na okraji
          a jejich křivka se narovná. Níž je vidět, že za tím stojí několik městských částí, ne vzdálenost sama.
        </p>
      </section>

      <Figure
        title="Piráti do Sněmovny a obě kandidátky do zastupitelstva"
        sub={`Podíl hlasů podle doby cesty do centra. Tečkovaně výsledek Pirátů v komunálních volbách ${years.previous}.`}
      >
        <BandLines
          labels={times.map(bandName)}
          axis="minut do centra MHD v ranní špičce"
          series={[
            { name: `Obě dohromady ${years.current}`, color: campColor, values: times.map(campShare) },
            {
              name: `${label("prahaSobe")} ${years.current}`,
              color: colorOf("prahaSobe"),
              values: times.map((band) => share(band, "prahaSobe")),
            },
            {
              name: `Piráti do Sněmovny ${years.parliamentary}`,
              color: colorOf("pirati"),
              values: times.map((band) => share(band, "pirati", "mid")),
              dash: "6 5",
            },
            {
              name: `Piráti ${years.previous}`,
              color: colorOf("pirati"),
              values: times.map((band) => share(band, "pirati", "then")),
              dash: DOTS,
            },
            { name: `Piráti ${years.current}`, color: colorOf("pirati"), values: times.map((band) => share(band, "pirati")) },
          ]}
        />
      </Figure>

      <section className="prose">
        <p>
          Že jde o stejný okruh voličů, je vidět na součtu. Sněmovní křivka Pirátů má tvar letošního výsledku obou
          kandidátek dohromady: v každém pásmu měli Piráti do Sněmovny {fmtNum(Math.min(...midOverCamp) * 100, 0)} až{" "}
          {fmtPct(Math.max(...midOverCamp) * 100, 0)} toho, co letos Praha Sobě a Piráti společně.
        </p>
        <p>
          Stejně to vypadalo už v roce {years.previous}: Piráti tehdy měli {fmtNum(share(nearest, "pirati", "then"), 0)}{" "}
          → {fmtPct(share(farthest, "pirati", "then"), 0)} a na hlasech obou kandidátek se podíleli{" "}
          {fmtNum(piratiOfCamp(nearest, "then"), 0)} a {fmtPct(piratiOfCamp(farthest, "then"), 0)}. Od té doby ztratili
          všude podobně, v každém pásmu jim zůstalo {fmtNum(Math.min(...kept), 0)} až {fmtPct(Math.max(...kept), 0)}{" "}
          tehdejšího podílu. Tvar křivky se nezměnil, jen je celá níž.
        </p>
      </section>

      <Figure
        title="Jak se hlasy obou kandidátek dělí"
        sub="Podíly v procentech hlasů podle doby cesty do centra"
      >
        <HeatTable rows={times} rowHead="Minut do centra" rowLabel={bandName} columns={campColumns} />
      </Figure>

      {localBase.districts.length > 0 && (
        <>
          <section className="prose">
            <p>
              Vzdálenost sama to nevysvětluje. Větší díl má Praha Sobě v Praze {strongNames}, kde její kandidátka
              do zastupitelstva městské části dostala aspoň {fmtNum(Math.floor(weakestLocal), 0)} % hlasů. Tyto části
              leží blízko centra a žije v nich {fmtPct((localBase.strong.registered / city.registered) * 100, 0)}{" "}
              voličů. Piráti tam mají {fmtPct(piratiOfCamp(localBase.strong), 0)} hlasů obou kandidátek, ve zbytku
              Prahy {fmtPct(piratiOfCamp(localBase.rest), 0)}.
            </p>
          </section>

          <Figure
            title="Podíl Pirátů tam, kde je Praha Sobě místně silná, a jinde"
            sub={`Kolik procent z hlasů obou kandidátek do pražského zastupitelstva ${years.current} mají Piráti. Prázdné pole znamená méně než deset okrsků.`}
          >
            <div className="table-wrap">
              <table className="data matrix kind-matrix">
                <thead>
                  <tr>
                    <th>Minut do centra</th>
                    {splitColumns.map((column) => (
                      <th key={column.head} className="col">
                        {column.head}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {localBase.times.map((band, index) => (
                    <tr key={band.from}>
                      <td>{bandName(band)}</td>
                      {splitColumns.map((column) => {
                        const group = column.group(band, index);
                        return group ? (
                          <td
                            key={column.head}
                            className="heat"
                            title={`${fmtInt(group.precincts)} okrsků`}
                            style={{
                              background: `color-mix(in srgb, ${colorOf("pirati")} ${Math.round(piratiOfCamp(group))}%, var(--surface-2))`,
                            }}
                          >
                            {fmtPct(piratiOfCamp(group), 0)}
                          </td>
                        ) : (
                          <td key={column.head} className="empty">
                            –
                          </td>
                        );
                      })}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Figure>

          <section className="prose">
            <p>
              Mimo tyto městské části připadá na Piráty v každém pásmu {fmtNum(Math.min(...restSplit), 0)} až{" "}
              {fmtPct(Math.max(...restSplit), 0)} hlasů obou kandidátek, ať je to do centra čtvrt hodiny, nebo přes
              čtyřicet minut. V celopražském průměru to vypadá jako vliv vzdálenosti jen proto, že části se silnou
              místní Prahou Sobě jsou u centra.
            </p>
            <p>
              Z výsledků nejde poznat, jestli silná místní kandidátka přivádí Praze Sobě hlasy i do pražského
              zastupitelstva, nebo jestli obojí jen ukazuje, kde má nejvíc voličů.
            </p>
          </section>
        </>
      )}

      <section className="prose">
        <h2>V čem lidé bydlí</h2>
        <p>
          Okrsek patří k tomu druhu zástavby, ve kterém je aspoň polovina jeho bytů. Panelové domy jsou sídliště.
          Starší bytové domy jsou činžovní a zděná zástavba do roku 1989, novější jsou bytové domy postavené od roku
          1990.
        </p>
      </section>

      <Figure title="Okrsky podle převažující zástavby" sub="Účast a podíly v procentech">
        <HeatTable rows={kinds} rowHead="Zástavba" rowLabel={(row) => kindName(row.kind)} columns={kindColumns} />
      </Figure>

      <Figure
        title="Každá zástavba proti celému městu"
        sub="Přerušovaný kruh je průměr Prahy. Kam obrazec sahá za něj, tam je hodnota vyšší než v celém městě; střed je polovina průměru, okraj jeho jedenapůlnásobek."
      >
        <div className="radars">
          {kinds.map((group) => (
            <div className="radar" key={group.kind}>
              <h4>
                <span className="swatch" style={{ background: kindColor(group.kind) }} />
                {kindName(group.kind)}
              </h4>
              <div className="small muted">{thousands(group.registered)} voličů</div>
              <Radar spokes={spokes(group)} color={kindColor(group.kind)} />
            </div>
          ))}
        </div>
      </Figure>

      {panel && older && houses && (
        <section className="prose">
          <p>
            Sídliště jsou slabým místem Prahy Sobě ({fmtPct(share(panel, "prahaSobe"))} proti{" "}
            {fmtPct(share(older, "prahaSobe"))} ve starší zástavbě), ne Pirátů, kteří tam mají{" "}
            {fmtPct(share(panel, "pirati"))}, skoro svůj průměr. STAN i Spolu jsou tam nejslabší a ANO nejsilnější (
            {fmtPct(share(panel, "ano"))}).
          </p>
          <p>
            Nízká účast není zvláštnost sídlišť. Ve všech bytových domech přišlo{" "}
            {fmtNum(Math.min(...apartments.map((item) => item.turnout.now ?? 0)), 0)} až{" "}
            {fmtPct(Math.max(...apartments.map((item) => item.turnout.now ?? 0)), 0)} voličů, v rodinných domech{" "}
            {fmtPct(houses.turnout.now ?? 0, 0)}. Tam mají STAN se Spolu{" "}
            {fmtPct(share(houses, "stan") + share(houses, "spolu"), 0)} hlasů.
          </p>
        </section>
      )}

      <section className="prose">
        <h2>Zástavba při stejné době cesty</h2>
      </section>

      <Figure
        title="Praha Sobě a Piráti podle zástavby a doby cesty"
        sub="Podíl hlasů v procentech. Prázdné pole znamená méně než deset okrsků."
      >
        <div className="grid half">
          {["prahaSobe", "pirati"].map((key) => {
            const top = Math.max(...data.kindsByTime.map((item) => share(item, key)));
            return (
              <div key={key}>
                <h4 className="split-title">{label(key)}</h4>
                <div className="table-wrap">
                  <table className="data matrix kind-matrix">
                    <thead>
                      <tr>
                        <th>Zástavba</th>
                        {rings.map((ring) => (
                          <th key={ring.from} className="col">
                            {bandName(ring)} min
                          </th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {kinds.map((group) => (
                        <tr key={group.kind}>
                          <td>{kindName(group.kind)}</td>
                          {rings.map((ring) => {
                            const cell = atTime(group.kind, ring.from);
                            return cell ? (
                              <td
                                key={ring.from}
                                className="heat"
                                title={`${fmtInt(cell.precincts)} okrsků`}
                                style={{
                                  background: `color-mix(in srgb, ${colorOf(key)} ${Math.round((share(cell, key) / top) * 60)}%, var(--surface-2))`,
                                }}
                              >
                                {pct(share(cell, key))}
                              </td>
                            ) : (
                              <td key={ring.from} className="empty">
                                –
                              </td>
                            );
                          })}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            );
          })}
        </div>
      </Figure>

      <section className="prose">
        <p>
          U Prahy Sobě rozhoduje zástavba i doba cesty
          {olderMiddle && panelMiddle && (
            <>
              : při dojezdu {bandName(middleRing)} minut má ve starších domech{" "}
              {fmtPct(share(olderMiddle, "prahaSobe"), 0)} a na sídlištích {fmtPct(share(panelMiddle, "prahaSobe"), 0)}
            </>
          )}
          . Dál než půl hodiny od centra je slabá v každé zástavbě. U Pirátů jsou rozdíly malé v obou směrech.
        </p>
      </section>

      <Figure
        title="Jednotlivé okrsky"
        sub="Každá tečka je okrsek, velikost odpovídá počtu voličů. Kliknutím na druh zástavby v legendě zvýrazníte jen ten."
      >
        <PrecinctScatter precincts={data.precincts} />
      </Figure>

      <section className="prose">
        <h2>Jak těsně to spolu souvisí</h2>
        <p>
          Sílu souvislosti měříme Pearsonovým korelačním koeficientem r, spočítaným přes{" "}
          {fmtInt(links.precincts)} pražských okrsků. Ukazuje, jak těsně leží body z grafu výše na přímce: +1
          znamená, že podíl s danou veličinou roste přesně lineárně, −1, že stejně přesně klesá, a 0, že mezi nimi
          žádná lineární souvislost není. Druhá mocnina r je podíl rozptylu mezi okrsky, který by vysvětlila
          samotná tato veličina
          {byMinutes && (
            <>
              ; u doby cesty a Prahy Sobě je r = {fmtR(byMinutes.prahaSobe)}, tedy r² ≈{" "}
              {fmtPct(byMinutes.prahaSobe ** 2 * 100, 0)}
            </>
          )}
          .
        </p>
        <p>
          Pearsonův koeficient může zkreslit pár neobvyklých okrsků nebo zakřivený tvar vztahu. U Prahy Sobě proto
          uvádíme i Spearmanův pořadový koeficient ρ, tedy stejný výpočet nad pořadím okrsků místo nad samotnými
          hodnotami
          {byMinutes && <> (u doby cesty ρ = {fmtR(byMinutes.prahaSobeRank)})</>}. Vychází podobně, takže výsledek
          nestojí na několika odlehlých okrscích.
        </p>
      </section>

      <Figure
        title="Korelace s podílem hlasů v okrscích"
        sub={`Volby do zastupitelstva ${years.current}, ${fmtInt(links.precincts)} okrsků, každý se stejnou váhou. Modře: čím víc toho okrsek má, tím vyšší podíl. Červeně: tím nižší.`}
      >
        <HeatTable
          rows={links.correlations}
          rowHead="V okrsku"
          rowLabel={(row) => MEASURES[row.measure] ?? row.measure}
          columns={correlationColumns}
        />
      </Figure>

      <section className="prose">
        <p>
          {byMinutes && byOlder && (
            <>
              Praha Sobě souvisí s dobou cesty ({fmtR(byMinutes.prahaSobe)}) zhruba stejně těsně jako se starší
              zástavbou ({fmtR(byOlder.prahaSobe)}), Piráti s obojím slaběji.{" "}
            </>
          )}
          Doba cesty a zástavba se ale navzájem překrývají: doba cesty koreluje s podílem bytů ve starší zástavbě{" "}
          {fmtR(links.minutesWith.older)} a s podílem bytů v panelových domech {fmtR(links.minutesWith.panel)}. Z párových
          korelací proto nejde oddělit, kolik z rozdílů vysvětluje vzdálenost a kolik to, v čem lidé bydlí.
        </p>
        <p>
          K tomu slouží lineární regrese podílu Prahy Sobě v okrsku (v procentech), vážená počtem hlasujících, aby
          velké okrsky vážily víc než malé. Zástavba v ní vystupuje jako podíl bytů v panelových, novějších
          a rodinných domech a srovnávací skupinou je starší zástavba. Koeficient u panelových domů tak říká, o kolik
          bodů se liší okrsek se všemi byty v panelových domech od okrsku se všemi byty ve starší zástavbě při stejné
          době cesty. Poslední model přidává každé z {fmtInt(links.districts)} městských částí vlastní konstantu
          (fixní efekty), takže porovnává jen okrsky uvnitř stejné části. Okrsky jedné městské části si jsou podobné
          a nejsou nezávislá pozorování, proto jsou intervaly spolehlivosti spočítané se shlukováním po městských
          částech.
        </p>
      </section>

      <Figure
        title="Regrese podílu Prahy Sobě v okrscích"
        sub="Koeficienty v procentních bodech, pod nimi 95% interval spolehlivosti. Zástavba je proti okrsku, kde jsou všechny byty ve starších bytových domech. R² je podíl rozptylu mezi okrsky, který model vysvětluje."
      >
        <div className="table-wrap">
          <table className="data regression">
            <thead>
              <tr>
                <th>Model</th>
                {modelColumns.map((column) => (
                  <th key={column.head} className="r">
                    {column.head}
                  </th>
                ))}
                <th className="r">R²</th>
              </tr>
            </thead>
            <tbody>
              {modelRows.map(({ name, model }) => (
                <tr key={name}>
                  <td>{name}</td>
                  {modelColumns.map((column) => {
                    const estimate = column.pick(model);
                    if (!estimate) {
                      return (
                        <td key={column.head} className="r muted">
                          –
                        </td>
                      );
                    }
                    const [low, high] = [estimate.value - 1.96 * estimate.error, estimate.value + 1.96 * estimate.error];
                    return (
                      <td key={column.head} className={`r num${low < 0 && high > 0 ? " unclear" : ""}`}>
                        <div className="estimate">{signed(estimate.value, column.decimals)}</div>
                        <div className="interval">
                          {signed(low, column.decimals)} až {signed(high, column.decimals)}
                        </div>
                      </td>
                    );
                  })}
                  <td className="r num">{fmtPct(model.fit * 100, 0)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Figure>

      <section className="prose">
        {alone.minutes && both.minutes && both.panel && inside.minutes && inside.panel && (
          <>
            <p>
              Samotná doba cesty vysvětluje {fmtPct(alone.fit * 100, 0)} rozptylu: každá minuta navíc znamená
              v průměru o {percentagePoints(alone.minutes.value, 2)} bodu nižší podíl. Se zástavbou v modelu klesne
              na {percentagePoints(both.minutes.value, 2)} bodu za minutu a okrsek, kde jsou všechny byty v panelových
              domech, má o {percentagePoints(both.panel.value, 0)} bodů méně než okrsek starší zástavby se stejnou
              dobou cesty. Uvnitř městských částí je to {percentagePoints(inside.minutes.value, 2)} bodu za minutu
              {minutesUnclear && <>, a interval spolehlivosti tak zahrnuje nulu</>}, zatímco rozdíl mezi sídlištěm
              a starší zástavbou zůstává {percentagePoints(inside.panel.value, 0)} bodů
              {panelClear && <> a od nuly se jasně liší</>}. Vysoké R² posledního modelu (
              {fmtPct(inside.fit * 100, 0)}) jde hlavně na vrub samotných městských částí.
            </p>
            <p>
              {minutesUnclear
                ? "Rozdíly mezi centrem a okrajem jsou tedy hlavně rozdíly mezi celými městskými částmi. Uvnitř jedné části víc než minuty do centra rozhoduje, v jakých domech lidé bydlí."
                : "Rozdíly mezi centrem a okrajem jsou tedy z velké části rozdíly mezi celými městskými částmi. Doba cesty hraje roli i uvnitř nich, ale menší než zástavba."}
            </p>
          </>
        )}
        <p>
          Jde o ekologickou korelaci: popisuje okrsky, ne jednotlivé voliče, a sama o sobě nedokazuje příčinu.
          Sídliště a starší zástavba se liší i věkem, vzděláním a příjmy obyvatel, které model nezná, takže koeficient
          zástavby zachycuje i je.
        </p>
      </section>

      <section className="prose">
        <h2>Co z toho plyne</h2>
        {panel && older && (
          <p>
            Sídliště jsou největší skupina voličů a Praha Sobě s Piráty tam mají o{" "}
            {fmtNum(campShare(older) - campShare(panel), 0)} bodů méně než ve starší zástavbě. Rozdíl dělá Praha
            Sobě; Piráti jsou tam stejně silní jako jinde.
          </p>
        )}
        <p>
          Proti sněmovním volbám ztrácejí Piráti nejvíc u centra: do {nearest.to} minut mají{" "}
          {fmtNum(share(nearest, "pirati"), 0)} % místo {fmtPct(share(nearest, "pirati", "mid"), 0)}, nad{" "}
          {farthest.from} minut {fmtNum(share(farthest, "pirati"), 0)} % místo{" "}
          {fmtPct(share(farthest, "pirati", "mid"), 0)}. Rozdíl dělá hlavně Praha {strongNames}, kde má Praha Sobě
          silnou místní kandidátku a kde na Piráty připadá {fmtPct(piratiOfCamp(localBase.strong), 0)} hlasů obou
          kandidátek místo {fmtPct(piratiOfCamp(localBase.rest), 0)} jinde. Součet obou přitom sněmovní křivku
          Pirátů kopíruje. Z toho usuzujeme, že hlasy, které by Piráti v těchto částech získali navíc, by z velké
          části ubyly Praze Sobě a společný výsledek by se nezměnil. Ve zbytku Prahy se hlasy dělí všude podobně
          a na sídlištích je Praha Sobě slabá, zatímco Piráti tam drží skoro svůj průměr; tam si obě kandidátky
          konkurují nejméně.
        </p>
        {panel && older && (
          <p>
            Piráti dostali loni do Sněmovny v okrscích starší zástavby {thousands(voters(older, "pirati", "mid"))}{" "}
            hlasů a na sídlištích {thousands(voters(panel, "pirati", "mid"))}; letos je tam volilo{" "}
            {thousands(voters(older, "pirati", "now"))} a {thousands(voters(panel, "pirati", "now"))} lidí. Ten rozdíl
            ale nezůstal celý doma. Obě kandidátky dohromady mají v každém pásmu {fmtNum(Math.min(...ratios), 0)} až{" "}
            {fmtPct(Math.max(...ratios), 0)} loňských sněmovních hlasů Pirátů, přestože k volbám přišlo{" "}
            {fmtPct(city.turnout.now ?? 0, 0)} lidí místo {fmtPct(city.turnout.mid ?? 0, 0)}. Rezerva v účasti tu je,
            a to ve všech bytových domech, ne jen na sídlištích. Kolik z ní připadá na Piráty a kolik na Prahu Sobě,
            z výsledků za okrsky poznat nejde.
          </p>
        )}
        <p>
          Čtvrti rodinných domů jsou nejtěžší: účast je tam vysoká a volí se hlavně STAN a Spolu. Jde o průměry za
          okrsky, ne o jednotlivé voliče.
        </p>
      </section>

      <section className="card method-notes">
        <h3>Jak se to počítalo</h3>
        <p className="note">
          Doba cesty je z jízdních řádů PID pro ranní špičku pracovního dne: jak dlouho před časem příchodu na Můstek
          je potřeba vyjít z domu, v průměru pro příchody mezi 7.30 a 9.00. Zahrnuje chůzi na zastávku, čekání
          a přestupy. Chůze se počítá vzdušnou čarou rychlostí 3,6 km/h.
        </p>
        <p className="note">
          Zástavba je z registru budov (RÚIAN): druh budovy, počet bytů, konstrukce a rok dokončení. Okrsek se řadí
          podle bytů, ne podle počtu domů, a jeho doba cesty je doba z bytu uprostřed pořadí.
        </p>
        <p className="note">
          Korelace jsou nevážené, přes všechny okrsky s dobou cesty i výsledkem. Regrese je metodou vážených
          nejmenších čtverců s váhou počtu hlasujících; standardní chyby jsou robustní vůči shlukování po městských
          částech (sendvičový odhad bez korekce na malý počet shluků) a 95% interval je odhad ± 1,96 standardní
          chyby.
        </p>
        <p className="note">
          Hlasy v komunálních volbách jsou přepočtené na voliče: podíl kandidátky krát počet odevzdaných obálek.
        </p>
      </section>
    </>
  );
}
