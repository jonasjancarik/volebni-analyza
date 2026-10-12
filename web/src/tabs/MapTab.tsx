import { type ExpressionSpecification, type GeoJSONSource, Map as MapLibre, NavigationControl } from "maplibre-gl";
import type { FeatureCollection, Point, Polygon } from "geojson";
import { useEffect, useMemo, useRef, useState } from "react";
import { type Boundaries, useAddresses, useBoundaries, useComparison } from "../api";
import { NO_DATA, RAMPS, SEQUENTIAL, type Scale, divergingScale, resolveColor, sequentialScale } from "../colors";
import type { TabProps } from "../Council";
import { circleShapes } from "../components/cartogram";
import { type DotGroup, dotPoints, dotSteps } from "../components/dots";
import { Dropdown } from "../components/Dropdown";
import { bounds, STYLES } from "../components/mapBase";
import { PrecinctDetail } from "../components/PrecinctDetail";
import { Loading, Problem } from "../components/State";
import { fmtInt, fmtNum, fmtPct, fmtPp, listName, plural, truncate } from "../format";
import { useParam, useTooltip } from "../hooks";

type Metric = "ucast" | "podil" | "vitez" | "zmena";

const METRICS: { id: Metric; label: string }[] = [
  { id: "podil", label: "Podíl kandidátky" },
  { id: "ucast", label: "Volební účast" },
  { id: "vitez", label: "Vítěz v okrsku" },
  { id: "zmena", label: "Změna účasti" },
];

const TURNOUT = "__turnout";
const DOTS = "tecky";
const CIRCLES = "kruhy";
/** Colours the dots by the list their votes went to, in place of a scale */
const BY_LIST = "strana";

interface Painted {
  /** Colour and tooltip text of each precinct that has a value */
  values: Map<string, { color: string; text: string; sub?: string }>;
  legend: React.ReactNode;
}

function RampLegend({ title, scale, format }: { title: string; scale: Scale; format: (edge: number) => string }) {
  return (
    <>
      <div className="title">{title}</div>
      <div className="ramp">
        {scale.colors.map((color) => (
          <span key={color} style={{ background: color }} />
        ))}
      </div>
      <div className="ramp-labels">
        {scale.colors.map((color, i) => (
          <span key={color}>{i < scale.edges.length ? format(scale.edges[i]) : ""}</span>
        ))}
      </div>
    </>
  );
}

/** A small preview of the colours a choice puts on the map */
function Strip({ colors }: { colors: string[] }) {
  return (
    <span className="ramp-strip" aria-hidden>
      {colors.map((color, i) => (
        <span key={i} style={{ background: color }} />
      ))}
    </span>
  );
}

export function MapTab({ council, colors, focus, combo }: TabProps) {
  const { election, lists, precincts, areas, previous } = council;
  const boundaries = useBoundaries(election.id, council.code);
  const [metricParam, setMetric] = useParam("m");
  const [areaParam, setArea] = useParam("uzemi");
  const [selected, setSelected] = useParam("okrsek");
  const [changeOf, setChangeOf] = useParam("zm");
  const [view, setView] = useParam("z");
  const [perDotParam, setPerDot] = useParam("tecka");
  const [rampParam, setRamp] = useParam("barvy");
  const [apartParam, setApart] = useParam("odsun");
  const asDots = view === DOTS;
  const asCircles = view === CIRCLES;
  const apart = apartParam === "1";
  const addresses = useAddresses(election.id, council.code, asDots);
  const metric: Metric = METRICS.some((item) => item.id === metricParam) ? (metricParam as Metric) : "podil";
  const comparison = useComparison(election.id, council.code, null, metric === "zmena" && !!previous);
  // The change follows the list picked at the top, unless turnout is asked for or the list ran under another name before
  const comboNames = combo.map((index) => lists[index]?.name);
  const changeLists =
    changeOf !== TURNOUT && comparison.data && comboNames.every((name) => name && comparison.data.sameLists.includes(name))
      ? comboNames
      : null;
  const area = areas.some((item) => item.code === areaParam) ? areaParam : null;
  const parliamentary = election.type === "parliamentary";
  const listWord = parliamentary ? "strany" : "kandidátky";

  const comboName =
    combo.length === 1
      ? listName(lists[focus].name)
      : `${combo.length} ${parliamentary ? plural(combo.length, "strana", "strany", "stran") : plural(combo.length, "kandidátka", "kandidátky", "kandidátek")} dohromady`;

  const scaled = metric === "podil" || metric === "ucast";
  const byList = asDots && metric === "podil" && rampParam === BY_LIST;
  const ramp = rampParam && RAMPS[rampParam] ? rampParam : null;

  const painted = useMemo<Painted>(() => {
    const values: Painted["values"] = new Map();
    const inArea = precincts.filter((precinct) => precinct.registered > 0);
    const total = (votes: number[]) => votes.reduce((sum, value) => sum + value, 0);
    const rampColors = ramp ? RAMPS[ramp].colors : undefined;

    if (metric === "ucast") {
      const scale = sequentialScale(inArea.map((precinct) => precinct.turnout), rampColors);
      for (const precinct of inArea) {
        values.set(precinct.id, { color: scale.color(precinct.turnout), text: `Účast ${fmtPct(precinct.turnout)}` });
      }
      return { values, legend: <RampLegend title="Volební účast (%)" scale={scale} format={(edge) => fmtNum(edge, 0)} /> };
    }

    if (metric === "podil") {
      const shares = inArea.map((precinct) => {
        const all = total(precinct.votes);
        return all ? (combo.reduce((sum, index) => sum + precinct.votes[index], 0) / all) * 100 : 0;
      });
      const scale = sequentialScale(shares, rampColors);
      inArea.forEach((precinct, i) =>
        values.set(precinct.id, {
          color: scale.color(shares[i]),
          text: `${fmtPct(shares[i])} hlasů`,
          sub: truncate(comboName, 40),
        }),
      );
      return {
        values,
        legend: (
          <RampLegend title={`${truncate(comboName, 34)} (% hlasů)`} scale={scale} format={(edge) => fmtNum(edge, edge % 1 ? 1 : 0)} />
        ),
      };
    }

    if (metric === "vitez") {
      const wins = new Map<number, number>();
      for (const precinct of inArea) {
        const all = total(precinct.votes);
        if (!all) continue;
        const winner = precinct.votes.indexOf(Math.max(...precinct.votes));
        wins.set(winner, (wins.get(winner) ?? 0) + 1);
        values.set(precinct.id, {
          color: resolveColor(colors[winner]),
          text: truncate(listName(lists[winner].name), 40),
          sub: `${fmtPct((precinct.votes[winner] / all) * 100)} hlasů`,
        });
      }
      const ranked = [...wins.entries()].sort((a, b) => b[1] - a[1]);
      return {
        values,
        legend: (
          <>
            <div className="title">Kdo v okrsku získal nejvíc hlasů</div>
            <div style={{ display: "grid", gap: 4 }}>
              {ranked.slice(0, 8).map(([index, count]) => (
                <span className="legend-item" key={index}>
                  <span className="swatch" style={{ background: colors[index] }} />
                  <span style={{ flex: 1 }}>{truncate(listName(lists[index].name), 26)}</span>
                  <span className="num muted">{fmtInt(count)}</span>
                </span>
              ))}
            </div>
          </>
        ),
      };
    }

    // Change against the previous election, for precincts that exist in both
    const data = comparison.data;
    if (!data) return { values, legend: null };
    const listIndexes = changeLists ? changeLists.map((name) => data.sameLists.indexOf(name)) : [];
    const changes = data.precincts.map((precinct) =>
      listIndexes.length === 0
        ? precinct.turnout[1] - precinct.turnout[0]
        : listIndexes.reduce((sum, index) => sum + precinct.current[index] - precinct.previous[index], 0),
    );
    const scale = divergingScale(changes);
    data.precincts.forEach((precinct, i) =>
      values.set(precinct.id, {
        color: scale.color(changes[i]),
        text: fmtPp(changes[i]),
        sub: !changeLists ? `účast proti roku ${data.previousYear}` : `podíl hlasů proti roku ${data.previousYear}`,
      }),
    );
    return {
      values,
      legend: (
        <RampLegend
          title={`Změna proti roku ${data.previousYear} (p. b.)`}
          scale={scale}
          format={(edge) => `${edge > 0 ? "+" : edge < 0 ? "−" : ""}${fmtNum(Math.abs(edge), edge % 1 ? 1 : 0)}`}
        />
      ),
    };
  }, [metric, precincts, combo, comboName, ramp, lists, colors, comparison.data, changeLists]);

  const precinctById = useMemo(() => new Map(precincts.map((precinct) => [precinct.id, precinct])), [precincts]);
  const selectedPrecinct = selected ? precinctById.get(selected) : undefined;
  const compared = comparison.data?.precincts.find((item) => item.id === selected);
  const focusIds = useMemo(
    () => (area ? new Set(precincts.filter((precinct) => precinct.area === area).map((precinct) => precinct.id)) : null),
    [area, precincts],
  );

  // What the dots and circles count in each precinct
  const sized = useMemo(() => {
    if (!asDots && !asCircles) return null;
    // Turnout is about people who came to vote, everything else about votes
    const ofTurnout =
      metric === "ucast" ||
      (metric === "zmena" && !changeLists);
    const chosen =
      metric === "podil"
        ? combo
        : metric === "zmena" && !ofTurnout
          ? combo
          : [];
    const people = metric !== "vitez" && chosen.length === 0;
    const listColor = metric === "vitez" || byList ? colors.map(resolveColor) : [];
    const groups = new Map<string, DotGroup[]>();
    const counts = new Map<string, number>();
    const perList = lists.map(() => 0);
    let total = 0;
    for (const precinct of precincts) {
      if (precinct.registered <= 0) continue;
      const color = painted.values.get(precinct.id)?.color ?? NO_DATA;
      let parts: DotGroup[];
      if (metric === "vitez") {
        parts = precinct.votes.map((count, i) => ({ count, color: listColor[i] }));
        precinct.votes.forEach((count, i) => (perList[i] += count));
      } else if (people) {
        parts = [{ count: precinct.ballots, color }];
      } else if (byList) {
        parts = chosen.map((index) => ({ count: precinct.votes[index], color: listColor[index] }));
      } else {
        parts = [{ count: chosen.reduce((sum, index) => sum + precinct.votes[index], 0), color }];
      }
      const count = parts.reduce((sum, part) => sum + part.count, 0);
      groups.set(precinct.id, parts);
      counts.set(precinct.id, count);
      total += count;
    }
    const one = parliamentary ? "tuto stranu" : "tuto kandidátku";
    const more = parliamentary ? "vybrané strany" : "vybrané kandidátky";
    return {
      groups,
      counts,
      total,
      perList,
      people,
      /** Whose votes are counted, to finish a sentence in the legend */
      target: people || metric === "vitez" ? "" : ` pro ${chosen.length > 1 ? more : one}`,
    };
  }, [asDots, asCircles, metric, changeLists, combo, byList, lists, colors, precincts, painted, parliamentary]);

  const dots = useMemo(() => {
    const features = boundaries.data?.features;
    if (!asDots || !sized || !features || addresses.isLoading) return null;
    const homes = addresses.data?.points ?? {};
    const steps = dotSteps(sized.total);
    const perDot = steps.options.includes(Number(perDotParam)) ? Number(perDotParam) : steps.auto;
    return {
      points: dotPoints(features, sized.groups, perDot, focusIds, homes),
      atHomes: Object.keys(homes).length > 0,
      perDot,
      steps,
    };
  }, [asDots, sized, boundaries.data, perDotParam, focusIds, addresses.isLoading, addresses.data]);

  const circles = useMemo(() => {
    const features = boundaries.data?.features;
    return asCircles && sized && features ? circleShapes(features, sized.counts, apart) : null;
  }, [asCircles, sized, boundaries.data, apart]);

  const unit = (count: number) =>
    sized?.people ? plural(count, "hlasující", "hlasující", "hlasujících") : plural(count, "hlas", "hlasy", "hlasů");
  // With dots or circles on the map, the tooltip also says how many they stand for
  const described = useMemo(() => {
    if (!sized) return painted.values;
    const values: Painted["values"] = new Map();
    for (const [id, count] of sized.counts) {
      const value = painted.values.get(id);
      const amount = `${fmtInt(count)} ${sized.people ? plural(count, "hlasující", "hlasující", "hlasujících") : plural(count, "hlas", "hlasy", "hlasů")}`;
      values.set(id, {
        color: value?.color ?? NO_DATA,
        text: value?.text ?? amount,
        sub: value ? [value.sub, amount].filter(Boolean).join(" · ") : undefined,
      });
    }
    return values;
  }, [sized, painted]);

  if (boundaries.isPending) return <Loading text="Načítám hranice okrsků…" />;
  if (boundaries.error) return <Problem error={boundaries.error} />;
  if (boundaries.data.features.length === 0) {
    return <div className="banner neutral">Pro toto území nemáme hranice okrsků, mapu proto nejde zobrazit.</div>;
  }

  const rampOptions = [
    { id: "", label: "Světle až tmavě modrá", colors: SEQUENTIAL },
    ...Object.entries(RAMPS).map(([id, item]) => ({ id, ...item })),
  ];
  const ownColorLabel =
    combo.length > 1 ? `Každá ${parliamentary ? "strana" : "kandidátka"} svou barvou` : `Barva ${listWord}`;
  // Lists shown in the legend when each dot has the colour of its list
  const legendLists =
    sized && asDots && metric === "vitez"
      ? sized.perList
          .map((votes, index) => ({ votes, index }))
          .sort((a, b) => b.votes - a.votes)
          .slice(0, 8)
      : byList
        ? combo.map((index) => ({ votes: null, index }))
        : null;

  return (
    <div className="map-layout">
      <aside className="map-side">
        <div className="field">
          <div className="field-label">
            Co mapa ukazuje
          </div>
          <div className="segmented vertical" role="group" aria-label="Co mapa ukazuje">
            {METRICS.filter((item) => item.id !== "zmena" || previous).map((item) => (
              <button key={item.id} aria-pressed={metric === item.id} onClick={() => setMetric(item.id)}>
                {item.id === "podil"
                  ? `Podíl ${listWord}`
                  : item.id === "zmena" && metric === "zmena" && changeLists
                    ? "Změna podílu hlasů"
                    : item.label}
              </button>
            ))}
          </div>
        </div>
        <div className="field">
          <div className="field-label">
            Jak to mapa ukazuje
          </div>
          <div className="segmented vertical" role="group" aria-label="Jak to mapa ukazuje">
            <button aria-pressed={!asDots && !asCircles} onClick={() => setView(null)}>
              Vybarvené okrsky
            </button>
            <button aria-pressed={asDots} onClick={() => setView(DOTS)}>
              Tečky podle počtu hlasů
            </button>
            <button aria-pressed={asCircles} onClick={() => setView(CIRCLES)}>
              Kruhy podle počtu hlasů
            </button>
          </div>
        </div>
        {dots && (
          <label className="field">
            <span className="field-label">Jedna tečka je</span>
            <select
              className="select block"
              value={dots.perDot}
              onChange={(event) => setPerDot(Number(event.target.value) === dots.steps.auto ? null : event.target.value)}
            >
              {dots.steps.options.map((step) => (
                <option key={step} value={step}>
                  {fmtInt(step)} {unit(step)}
                </option>
              ))}
            </select>
            <span className="note">
              {dots.atHomes
                ? "Tečky leží u náhodně vybraných adres v okrsku, lesy, parky a pole proto zůstávají prázdné. Kde přesně voliči bydlí, ale neukazují."
                : "Tečky jsou uvnitř okrsku rozmístěné náhodně, neukazují tedy, kde přesně voliči bydlí."}{" "}
              Díky nim je vidět, kde je hlasů hodně a kde málo, i když je okrsek velký.
            </span>
          </label>
        )}
        {asCircles && (
          <div className="field">
            <p className="note">
              Každý okrsek je kruh, jehož plocha odpovídá počtu hlasů. Velký okrsek s málo voliči tak na mapě nezabere víc
              místa než malý okrsek, kde jich je hodně.
            </p>
            <label className="toggle">
              <input type="checkbox" checked={apart} onChange={(event) => setApart(event.target.checked ? "1" : null)} />
              Odsunout kruhy, které se překrývají
            </label>
            <p className="note">
              {apart
                ? "Kruhy se nepřekrývají, ale neleží přesně na místě svého okrsku."
                : "Kruhy leží na místě svého okrsku, v hustě obydlených částech se proto překrývají."}
            </p>
          </div>
        )}
        {scaled && (
          <div className="field">
            <span className="field-label">Barvy</span>
            <Dropdown
              label="Barvy mapy"
              button={
                <>
                  <Strip colors={byList ? combo.map((index) => colors[index]) : rampOptions.find((item) => item.id === (ramp ?? ""))!.colors} />
                  <span className="dropdown-text">
                    {byList ? ownColorLabel : rampOptions.find((item) => item.id === (ramp ?? ""))!.label}
                  </span>
                </>
              }
            >
              {(close) => (
                <>
                  {rampOptions.map((item) => (
                    <div key={item.id} className="dropdown-option" role="option" aria-selected={!byList && (ramp ?? "") === item.id}>
                      <button
                        type="button"
                        onClick={() => {
                          setRamp(item.id || null);
                          close();
                        }}
                      >
                        <Strip colors={item.colors} />
                        <span className="dropdown-text">{item.label}</span>
                      </button>
                    </div>
                  ))}
                  {asDots && metric === "podil" && (
                    <div className="dropdown-option" role="option" aria-selected={byList}>
                      <button
                        type="button"
                        onClick={() => {
                          setRamp(BY_LIST);
                          close();
                        }}
                      >
                        <Strip colors={combo.map((index) => colors[index])} />
                        <span className="dropdown-text">{ownColorLabel}</span>
                      </button>
                    </div>
                  )}
                </>
              )}
            </Dropdown>
          </div>
        )}
        {metric === "podil" && (
          <p className="note">
            {combo.length === 1 ? (
              <>
                Mapa ukazuje sledovanou {parliamentary ? "stranu" : "kandidátku"},{" "}
                <strong style={{ color: "var(--ink)" }}>{listName(lists[focus].name)}</strong>. Nahoře vedle názvu
                vyberete jinou, nebo jich zaškrtnete víc najednou.
              </>
            ) : (
              <>
                Mapa sčítá hlasy {parliamentary ? "stran" : "kandidátek"}, které jste vybrali nahoře vedle názvu:{" "}
                <strong style={{ color: "var(--ink)" }}>
                  {combo.map((index) => truncate(listName(lists[index].name), 30)).join(", ")}
                </strong>
                .
              </>
            )}
          </p>
        )}
        {metric !== "podil" && metric !== "zmena" && combo.length > 1 && (
          <p className="note">
            Víc vybraných {parliamentary ? "stran" : "kandidátek"} mapa sčítá jen v pohledu „Podíl {listWord}“.
          </p>
        )}
        {metric === "zmena" && (
          <label className="field">
            <span className="field-label">Co porovnat</span>
            <select className="select block" value={changeOf === TURNOUT ? TURNOUT : ""} onChange={(event) => setChangeOf(event.target.value || null)}>
              <option value="">{truncate(comboName, 40)}</option>
              <option value={TURNOUT}>Volební účast</option>
            </select>
            <span className="note">
              {changeOf !== TURNOUT && !changeLists
                ? `Ne všechny vybrané ${parliamentary ? "strany" : "kandidátky"} kandidovaly v minulých volbách pod stejným názvem, mapa proto ukazuje změnu účasti. `
                : ""}
              Kandidátku změníte nahoře vedle názvu.
            </span>
          </label>
        )}
        {areas.length > 1 && (
          <label className="field">
            <span className="field-label">{parliamentary ? "Obec" : "Městská část"}</span>
            <select className="select block" value={area ?? ""} onChange={(event) => setArea(event.target.value || null)}>
              <option value="">{parliamentary ? "Celý kraj" : "Celé město"}</option>
              {areas.map((item) => (
                <option key={item.code} value={item.code}>
                  {item.name}
                </option>
              ))}
            </select>
          </label>
        )}
        <p className="note">
          Kliknutím na {asCircles ? "kruh" : "okrsek"} zobrazíte {asCircles ? "výsledky jeho okrsku" : "jeho výsledky"}.
          {boundaries.data.boundariesYear !== election.year &&
            ` Hranice okrsků jsou z roku ${boundaries.data.boundariesYear}, novější zatím nejsou zveřejněné.`}
          {boundaries.data.missing > 0 &&
            ` ${fmtInt(boundaries.data.missing)} ${plural(boundaries.data.missing, "okrsek v mapě chybí, protože vznikl nebo změnil", "okrsky v mapě chybí, protože vznikly nebo změnily", "okrsků v mapě chybí, protože vznikly nebo změnily")} číslo později.`}
        </p>
      </aside>

      <div className="map-frame">
        <PrecinctMap
          geojson={boundaries.data}
          painted={described}
          dots={dots?.points ?? null}
          circles={circles}
          selected={selectedPrecinct?.id ?? null}
          onSelect={setSelected}
          focusIds={focusIds}
          label={(id) => {
            const precinct = precinctById.get(id);
            const areaName = areas.find((item) => item.code === precinct?.area)?.name;
            return `Okrsek ${precinct?.number ?? id}${areaName ? ` · ${areaName}` : ""}`;
          }}
        />
        {metric === "zmena" && comparison.isPending ? (
          <div className="map-legend">Porovnávám s minulými volbami…</div>
        ) : (
          (painted.legend || sized) && (
            <div className="map-legend">
              {legendLists ? (
                <>
                  <div className="title">Barva tečky říká, komu hlasy patří</div>
                  <div style={{ display: "grid", gap: 4 }}>
                    {legendLists.map(({ votes, index }) => (
                      <span className="legend-item" key={index}>
                        <span className="swatch" style={{ background: colors[index] }} />
                        <span style={{ flex: 1 }}>{truncate(listName(lists[index].name), 26)}</span>
                        {votes != null && sized && (
                          <span className="num muted">{fmtPct(sized.total ? (votes / sized.total) * 100 : 0)}</span>
                        )}
                      </span>
                    ))}
                  </div>
                </>
              ) : (
                painted.legend
              )}
              {dots && sized && (
                <div className="dot-key">
                  Jedna tečka = {fmtInt(dots.perDot)} {unit(dots.perDot)}
                  {sized.target}
                </div>
              )}
              {circles && sized && (
                <div className="dot-key">
                  Čím větší kruh, tím víc {sized.people ? "hlasujících" : "hlasů"}
                  {sized.target} v okrsku
                </div>
              )}
            </div>
          )
        )}
        {selectedPrecinct && (
          <div className="map-detail">
            <PrecinctDetail
              council={council}
              precinct={selectedPrecinct}
              colors={colors}
              focus={focus}
              compared={compared}
              previousYear={previous?.year}
              onClose={() => setSelected(null)}
            />
          </div>
        )}
      </div>
    </div>
  );
}

interface MapProps {
  geojson: Boundaries;
  painted: Painted["values"];
  /** One point for every so many votes, drawn in place of the coloured precincts */
  dots: FeatureCollection<Point> | null;
  /** A circle per precinct, drawn in place of its real shape */
  circles: FeatureCollection<Polygon> | null;
  selected: string | null;
  /** Precincts to zoom to; the others are dimmed */
  focusIds: Set<string> | null;
  onSelect: (id: string | null) => void;
  label: (id: string) => string;
}

const NO_DOTS: FeatureCollection<Point> = { type: "FeatureCollection", features: [] };
const fillOpacity = (dotted: boolean): ExpressionSpecification => [
  "case",
  ["boolean", ["feature-state", "dim"], false],
  dotted ? 0.03 : 0.12,
  dotted ? 0.08 : 0.82,
];

function PrecinctMap({ geojson, painted, dots, circles, selected, focusIds, onSelect, label }: MapProps) {
  const container = useRef<HTMLDivElement>(null);
  const map = useRef<MapLibre | null>(null);
  const [ready, setReady] = useState(false);
  const tooltip = useTooltip();
  // Handlers registered once read the latest props through refs
  const latest = useRef({ painted, onSelect, label });
  latest.current = { painted, onSelect, label };
  const ids = useMemo(() => geojson.features.map((feature) => String(feature.properties?.id)), [geojson]);

  useEffect(() => {
    if (!container.current) return;
    const dark = window.matchMedia("(prefers-color-scheme: dark)").matches;
    const instance = new MapLibre({
      container: container.current,
      style: dark ? STYLES.dark : STYLES.light,
      bounds: bounds(geojson.features) ?? undefined,
      fitBoundsOptions: { padding: 36 },
      attributionControl: { compact: true },
      dragRotate: false,
      pitchWithRotate: false,
    });
    instance.addControl(new NavigationControl({ showCompass: false }), "top-left");
    instance.touchZoomRotate.disableRotation();
    map.current = instance;
    let hovered: string | null = null;

    instance.on("load", () => {
      // Below the place names of the base map, so that they stay readable
      const firstLabel = instance.getStyle().layers?.find((layer) => layer.type === "symbol")?.id;
      instance.addSource("precincts", { type: "geojson", data: geojson, promoteId: "id" });
      instance.addLayer(
        {
          id: "precinct-fill",
          type: "fill",
          source: "precincts",
          paint: {
            "fill-color": ["coalesce", ["feature-state", "color"], NO_DATA],
            "fill-opacity": fillOpacity(false),
          },
        },
        firstLabel,
      );
      instance.addLayer(
        {
          id: "precinct-line",
          type: "line",
          source: "precincts",
          paint: { "line-color": dark ? "#1a1a19" : "#ffffff", "line-width": ["interpolate", ["linear"], ["zoom"], 9, 0.2, 13, 0.9] },
        },
        firstLabel,
      );
      instance.addSource("dots", { type: "geojson", data: NO_DOTS });
      instance.addLayer(
        {
          id: "precinct-dots",
          type: "circle",
          source: "dots",
          paint: {
            "circle-color": ["get", "color"],
            "circle-radius": ["interpolate", ["linear"], ["zoom"], 8, 1.1, 11, 1.9, 14, 3.2, 16, 4.5],
            "circle-opacity": ["case", ["get", "dim"], 0.12, 0.9],
            // Keeps the palest and the darkest dots visible on the base map
            "circle-stroke-color": dark ? "rgba(255, 255, 255, 0.35)" : "rgba(11, 11, 11, 0.3)",
            "circle-stroke-width": ["case", ["get", "dim"], 0, 0.5],
          },
        },
        firstLabel,
      );
      instance.addLayer({
        id: "precinct-outline",
        type: "line",
        source: "precincts",
        paint: {
          "line-color": dark ? "#ffffff" : "#0b0b0b",
          "line-width": [
            "case",
            ["boolean", ["feature-state", "selected"], false],
            3,
            ["boolean", ["feature-state", "hover"], false],
            1.5,
            0,
          ],
        },
      });
      setReady(true);
    });

    const setHover = (id: string | null) => {
      if (hovered === id) return;
      if (hovered) instance.setFeatureState({ source: "precincts", id: hovered }, { hover: false });
      hovered = id;
      if (id) instance.setFeatureState({ source: "precincts", id }, { hover: true });
      instance.getCanvas().style.cursor = id ? "pointer" : "";
    };
    instance.on("mousemove", "precinct-fill", (event) => {
      const id = event.features?.[0]?.id;
      if (id == null) return;
      setHover(String(id));
      const value = latest.current.painted.get(String(id));
      tooltip.show(
        event.originalEvent,
        <>
          <div className="t-sub">{latest.current.label(String(id))}</div>
          <div className="t-title">{value?.text ?? "Bez dat"}</div>
          {value?.sub && <div className="t-sub">{value.sub}</div>}
        </>,
      );
    });
    instance.on("mouseleave", "precinct-fill", () => {
      setHover(null);
      tooltip.hide();
    });
    instance.on("click", (event) => {
      const feature = instance.queryRenderedFeatures(event.point, { layers: ["precinct-fill"] })[0];
      latest.current.onSelect(feature?.id != null ? String(feature.id) : null);
    });

    return () => {
      map.current = null;
      setReady(false);
      instance.remove();
    };
    // The map is rebuilt only when it shows a different council
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [geojson]);

  useEffect(() => {
    const instance = map.current;
    if (!ready || !instance) return;
    (instance.getSource("precincts") as GeoJSONSource).setData(circles ?? geojson);
  }, [ready, circles, geojson]);

  useEffect(() => {
    const instance = map.current;
    if (!ready || !instance) return;
    for (const id of ids) {
      instance.setFeatureState(
        { source: "precincts", id },
        { color: painted.get(id)?.color ?? null, dim: focusIds ? !focusIds.has(id) : false },
      );
    }
  }, [ready, ids, painted, focusIds]);

  useEffect(() => {
    const instance = map.current;
    if (!ready || !instance) return;
    const dark = window.matchMedia("(prefers-color-scheme: dark)").matches;
    (instance.getSource("dots") as GeoJSONSource).setData(dots ?? NO_DOTS);
    instance.setPaintProperty("precinct-fill", "fill-opacity", fillOpacity(!!dots));
    // Without the fill, the outlines have to stand out against the base map by themselves
    const outline = dots ? (dark ? "#6b6b66" : "#a3a29b") : dark ? "#1a1a19" : "#ffffff";
    instance.setPaintProperty("precinct-line", "line-color", outline);
  }, [ready, dots]);

  const opening = useRef(selected);
  useEffect(() => {
    const instance = map.current;
    if (!ready || !instance) return;
    const features = focusIds
      ? geojson.features.filter((feature) => focusIds.has(String(feature.properties?.id)))
      : geojson.features;
    // A map opened for one precinct starts on it, with some of its surroundings
    const asked = opening.current
      ? geojson.features.filter((feature) => String(feature.properties?.id) === opening.current)
      : [];
    opening.current = null;
    const box = bounds(asked.length ? asked : features);
    if (!box) return;
    if (asked.length) {
      // On a wide map the precinct's results cover the right side
      const right = instance.getContainer().clientWidth > 760 ? 400 : 60;
      instance.fitBounds(box, { padding: { top: 60, bottom: 60, left: 60, right }, maxZoom: 15, duration: 0 });
    } else instance.fitBounds(box, { padding: 36, duration: 600 });
  }, [ready, focusIds, geojson]);

  const previous = useRef<string | null>(null);
  useEffect(() => {
    const instance = map.current;
    if (!ready || !instance) return;
    if (previous.current) instance.setFeatureState({ source: "precincts", id: previous.current }, { selected: false });
    if (selected) instance.setFeatureState({ source: "precincts", id: selected }, { selected: true });
    previous.current = selected;
  }, [ready, selected]);

  return (
    <>
      <div ref={container} className="map-canvas" />
      {tooltip.element}
    </>
  );
}
