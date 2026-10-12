import { type ExpressionSpecification, type GeoJSONSource, Map as MapLibre, NavigationControl } from "maplibre-gl";
import type { FeatureCollection, Point } from "geojson";
import { useEffect, useMemo, useRef, useState } from "react";
import { type Boundaries, useBoundaries, useComparison } from "../api";
import { NO_DATA, type Scale, divergingScale, resolveColor, sequentialScale } from "../colors";
import type { TabProps } from "../Council";
import { type DotGroup, dotPoints, dotSteps } from "../components/dots";
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
  { id: "zmena", label: "Změna proti minulým volbám" },
];

const TURNOUT = "__turnout";
const DOTS = "tecky";
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

export function MapTab({ council, colors, focus }: TabProps) {
  const { election, lists, precincts, areas, previous } = council;
  const boundaries = useBoundaries(election.id, council.code);
  const [metricParam, setMetric] = useParam("m");
  const [areaParam, setArea] = useParam("uzemi");
  const [selected, setSelected] = useParam("okrsek");
  const [changeOf, setChangeOf] = useParam("zm");
  const [view, setView] = useParam("z");
  const [perDotParam, setPerDot] = useParam("tecka");
  const asDots = view === DOTS;
  const metric: Metric = METRICS.some((item) => item.id === metricParam) ? (metricParam as Metric) : "podil";
  const comparison = useComparison(election.id, council.code, null, metric === "zmena" && !!previous);
  const area = areas.some((item) => item.code === areaParam) ? areaParam : null;
  const parliamentary = election.type === "parliamentary";
  const listWord = parliamentary ? "strany" : "kandidátky";

  const painted = useMemo<Painted>(() => {
    const values: Painted["values"] = new Map();
    const inArea = precincts.filter((precinct) => precinct.registered > 0);
    const total = (votes: number[]) => votes.reduce((sum, value) => sum + value, 0);

    if (metric === "ucast") {
      const scale = sequentialScale(inArea.map((precinct) => precinct.turnout));
      for (const precinct of inArea) {
        values.set(precinct.id, { color: scale.color(precinct.turnout), text: `Účast ${fmtPct(precinct.turnout)}` });
      }
      return { values, legend: <RampLegend title="Volební účast (%)" scale={scale} format={(edge) => fmtNum(edge, 0)} /> };
    }

    if (metric === "podil") {
      const shares = inArea.map((precinct) => {
        const all = total(precinct.votes);
        return all ? (precinct.votes[focus] / all) * 100 : 0;
      });
      const scale = sequentialScale(shares);
      inArea.forEach((precinct, i) =>
        values.set(precinct.id, {
          color: scale.color(shares[i]),
          text: `${fmtPct(shares[i])} hlasů`,
          sub: truncate(listName(lists[focus].name), 40),
        }),
      );
      return {
        values,
        legend: (
          <RampLegend
            title={`${truncate(listName(lists[focus].name), 34)} (% hlasů)`}
            scale={scale}
            format={(edge) => fmtNum(edge, edge % 1 ? 1 : 0)}
          />
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
    const listIndex = changeOf && changeOf !== TURNOUT ? data.sameLists.indexOf(changeOf) : -1;
    const changes = data.precincts.map((precinct) =>
      listIndex === -1 ? precinct.turnout[1] - precinct.turnout[0] : precinct.current[listIndex] - precinct.previous[listIndex],
    );
    const scale = divergingScale(changes);
    data.precincts.forEach((precinct, i) =>
      values.set(precinct.id, {
        color: scale.color(changes[i]),
        text: fmtPp(changes[i]),
        sub: listIndex === -1 ? `účast proti roku ${data.previousYear}` : `podíl hlasů proti roku ${data.previousYear}`,
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
  }, [metric, precincts, focus, lists, colors, comparison.data, changeOf]);

  const precinctById = useMemo(() => new Map(precincts.map((precinct) => [precinct.id, precinct])), [precincts]);
  const selectedPrecinct = selected ? precinctById.get(selected) : undefined;
  const compared = comparison.data?.precincts.find((item) => item.id === selected);
  const focusIds = useMemo(
    () => (area ? new Set(precincts.filter((precinct) => precinct.area === area).map((precinct) => precinct.id)) : null),
    [area, precincts],
  );

  const dots = useMemo(() => {
    const features = boundaries.data?.features;
    if (!asDots || !features) return null;
    // Turnout is about people who came to vote, everything else about votes
    const ofTurnout =
      metric === "ucast" ||
      (metric === "zmena" && (!changeOf || changeOf === TURNOUT || !comparison.data?.sameLists.includes(changeOf)));
    const list = metric === "podil" ? focus : metric === "zmena" ? lists.findIndex((item) => item.name === changeOf) : -1;
    const listColor = metric === "vitez" ? colors.map(resolveColor) : [];
    const groups = new Map<string, DotGroup[]>();
    const counts = new Map<string, number>();
    const perList = lists.map(() => 0);
    let total = 0;
    for (const precinct of precincts) {
      if (precinct.registered <= 0) continue;
      let parts: DotGroup[];
      if (metric === "vitez") {
        parts = precinct.votes.map((count, i) => ({ count, color: listColor[i] }));
        precinct.votes.forEach((count, i) => (perList[i] += count));
      } else {
        const count = ofTurnout || list === -1 ? precinct.ballots : precinct.votes[list];
        parts = [{ count, color: painted.values.get(precinct.id)?.color ?? NO_DATA }];
      }
      const count = parts.reduce((sum, part) => sum + part.count, 0);
      groups.set(precinct.id, parts);
      counts.set(precinct.id, count);
      total += count;
    }
    const steps = dotSteps(total);
    const perDot = steps.options.includes(Number(perDotParam)) ? Number(perDotParam) : steps.auto;
    return {
      points: dotPoints(features, groups, perDot, focusIds),
      perDot,
      steps,
      counts,
      total,
      perList,
      people: ofTurnout || (metric !== "vitez" && list === -1),
    };
  }, [asDots, boundaries.data, metric, changeOf, comparison.data, focus, lists, colors, precincts, painted, perDotParam, focusIds]);

  const unit = (count: number) =>
    dots?.people ? plural(count, "hlasující", "hlasující", "hlasujících") : plural(count, "hlas", "hlasy", "hlasů");
  // With dots on the map, the tooltip also says how many they stand for
  const described = useMemo(() => {
    if (!dots) return painted.values;
    const values: Painted["values"] = new Map();
    for (const [id, count] of dots.counts) {
      const value = painted.values.get(id);
      const amount = `${fmtInt(count)} ${dots.people ? plural(count, "hlasující", "hlasující", "hlasujících") : plural(count, "hlas", "hlasy", "hlasů")}`;
      values.set(id, {
        color: value?.color ?? NO_DATA,
        text: value?.text ?? amount,
        sub: value ? [value.sub, amount].filter(Boolean).join(" · ") : undefined,
      });
    }
    return values;
  }, [dots, painted]);

  if (boundaries.isPending) return <Loading text="Načítám hranice okrsků…" />;
  if (boundaries.error) return <Problem error={boundaries.error} />;
  if (boundaries.data.features.length === 0) {
    return <div className="banner neutral">Pro toto území nemáme hranice okrsků, mapu proto nejde zobrazit.</div>;
  }

  const sameLists = comparison.data?.sameLists ?? [];

  return (
    <div className="map-layout">
      <aside className="map-side">
        <div>
          <div className="field-label" style={{ marginBottom: 6 }}>
            Co mapa ukazuje
          </div>
          <div className="segmented vertical" role="group" aria-label="Co mapa ukazuje">
            {METRICS.filter((item) => item.id !== "zmena" || previous).map((item) => (
              <button key={item.id} aria-pressed={metric === item.id} onClick={() => setMetric(item.id)}>
                {item.id === "podil" ? `Podíl ${listWord}` : item.label}
              </button>
            ))}
          </div>
        </div>
        <div>
          <div className="field-label" style={{ marginBottom: 6 }}>
            Jak to mapa ukazuje
          </div>
          <div className="segmented vertical" role="group" aria-label="Jak to mapa ukazuje">
            <button aria-pressed={!asDots} onClick={() => setView(null)}>
              Vybarvené okrsky
            </button>
            <button aria-pressed={asDots} onClick={() => setView(DOTS)}>
              Tečky podle počtu hlasů
            </button>
          </div>
        </div>
        {dots && (
          <label style={{ display: "grid", gap: 4 }}>
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
              Tečky jsou uvnitř okrsku rozmístěné náhodně, neukazují tedy, kde přesně voliči bydlí. Díky nim je ale vidět,
              kde je hlasů hodně a kde málo, i když je okrsek velký.
            </span>
          </label>
        )}
        {metric === "podil" && (
          <p className="note">
            Mapa ukazuje sledovanou {parliamentary ? "stranu" : "kandidátku"},{" "}
            <strong style={{ color: "var(--ink)" }}>{listName(lists[focus].name)}</strong>. Jinou vyberete nahoře vedle
            názvu.
          </p>
        )}
        {metric === "zmena" && (
          <label style={{ display: "grid", gap: 4 }}>
            <span className="field-label">Co porovnat</span>
            <select className="select block" value={changeOf ?? TURNOUT} onChange={(event) => setChangeOf(event.target.value === TURNOUT ? null : event.target.value)}>
              <option value={TURNOUT}>Volební účast</option>
              {sameLists.map((name) => (
                <option key={name} value={name}>
                  {truncate(listName(name), 40)}
                </option>
              ))}
            </select>
            <span className="note">Nabízí se kandidátky, které kandidovaly v obou volbách pod stejným názvem.</span>
          </label>
        )}
        {areas.length > 1 && (
          <label style={{ display: "grid", gap: 4 }}>
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
          Kliknutím na okrsek zobrazíte jeho výsledky.
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
          (painted.legend || dots) && (
            <div className="map-legend">
              {dots && metric === "vitez" ? (
                <>
                  <div className="title">Barva tečky říká, komu hlasy patří</div>
                  <div style={{ display: "grid", gap: 4 }}>
                    {dots.perList
                      .map((votes, index) => ({ votes, index }))
                      .sort((a, b) => b.votes - a.votes)
                      .slice(0, 8)
                      .map(({ votes, index }) => (
                        <span className="legend-item" key={index}>
                          <span className="swatch" style={{ background: colors[index] }} />
                          <span style={{ flex: 1 }}>{truncate(listName(lists[index].name), 26)}</span>
                          <span className="num muted">{fmtPct(dots.total ? (votes / dots.total) * 100 : 0)}</span>
                        </span>
                      ))}
                  </div>
                </>
              ) : (
                painted.legend
              )}
              {dots && (
                <div className="dot-key">
                  Jedna tečka = {fmtInt(dots.perDot)} {unit(dots.perDot)}
                  {!dots.people && metric !== "vitez" && ` pro ${parliamentary ? "tuto stranu" : "tuto kandidátku"}`}
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

function PrecinctMap({ geojson, painted, dots, selected, focusIds, onSelect, label }: MapProps) {
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
