import { Map as MapLibre, NavigationControl } from "maplibre-gl";
import { useEffect, useMemo, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useBoundaries } from "../api";
import { NO_DATA, sequentialScale } from "../colors";
import { bounds, STYLES } from "../components/mapBase";
import { Loading, Problem } from "../components/State";
import { fmtNum, fmtPct } from "../format";
import { useTooltip } from "../hooks";
import { KINDS, kindColor, kindName, type Metric, MINUTES, type PrecinctPoint, SHARES } from "./centreShared";

const KIND = "kind";
// Pale near the centre, dark far from it
const FAR = ["#fbe9c6", "#f6cf8f", "#eeae5e", "#e2893c", "#c9652a", "#a14a22", "#73341b"];

interface Props {
  election: string;
  code: string;
  precincts: PrecinctPoint[];
}

/** The precincts of the city coloured by what the reader picks: housing, travel time, a list's share or turnout. */
export default function CentreMap({ election, code, precincts }: Props) {
  const boundaries = useBoundaries(election, code);
  const [picked, setPicked] = useState(KIND);
  const navigate = useNavigate();
  const container = useRef<HTMLDivElement>(null);
  const map = useRef<MapLibre | null>(null);
  const [ready, setReady] = useState(false);
  const tooltip = useTooltip();
  const byId = useMemo(() => new Map(precincts.map((precinct) => [precinct.id, precinct])), [precincts]);
  const metrics: Metric[] = [MINUTES, ...SHARES];
  const metric = metrics.find((item) => item.key === picked);

  const scale = useMemo(() => {
    if (!metric) return null;
    const values = precincts.map(metric.value).filter((value): value is number => value != null);
    return sequentialScale(values, metric.key === MINUTES.key ? FAR : undefined);
  }, [metric, precincts]);

  // Handlers registered once read the latest state through a ref
  const latest = useRef({ byId, metric });
  latest.current = { byId, metric };
  const geojson = boundaries.data;

  useEffect(() => {
    if (!container.current || !geojson) return;
    const dark = window.matchMedia("(prefers-color-scheme: dark)").matches;
    const instance = new MapLibre({
      container: container.current,
      style: dark ? STYLES.dark : STYLES.light,
      bounds: bounds(geojson.features) ?? undefined,
      fitBoundsOptions: { padding: 24 },
      attributionControl: { compact: true },
      dragRotate: false,
      pitchWithRotate: false,
      // The page scrolls past the map; zooming it takes the buttons or two fingers
      cooperativeGestures: true,
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
          paint: { "fill-color": ["coalesce", ["feature-state", "color"], NO_DATA], "fill-opacity": 0.82 },
        },
        firstLabel,
      );
      instance.addLayer(
        {
          id: "precinct-line",
          type: "line",
          source: "precincts",
          paint: {
            "line-color": [
              "case",
              ["boolean", ["feature-state", "hover"], false],
              dark ? "#ffffff" : "#0b0b0b",
              dark ? "#1a1a19" : "#ffffff",
            ],
            "line-width": ["case", ["boolean", ["feature-state", "hover"], false], 1.8, 0.4],
          },
        },
        firstLabel,
      );
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
      const precinct = latest.current.byId.get(String(id));
      tooltip.show(
        event.originalEvent,
        precinct ? (
          <>
            <div className="t-sub">Okrsek {precinct.id}</div>
            <div className="t-title">{kindName(precinct.kind)}</div>
            <div>{fmtNum(precinct.minutes, 0)} minut do centra</div>
            <div className="t-sub">
              Praha Sobě {fmtPct(precinct.prahaSobe ?? 0)}, Piráti {fmtPct(precinct.pirati ?? 0)}, účast{" "}
              {fmtPct(precinct.turnout, 0)}
            </div>
          </>
        ) : (
          <div className="t-sub">Okrsek {String(id)}: bez údajů o zástavbě</div>
        ),
      );
    });
    instance.on("mouseleave", "precinct-fill", () => {
      setHover(null);
      tooltip.hide();
    });
    instance.on("click", "precinct-fill", (event) => {
      const id = event.features?.[0]?.id;
      if (id != null) navigate(`/${election}/${code}/mapa?okrsek=${id}`);
    });

    return () => {
      map.current = null;
      setReady(false);
      instance.remove();
    };
    // The map is built once for the outlines it shows
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [geojson]);

  useEffect(() => {
    const instance = map.current;
    if (!ready || !instance || !geojson) return;
    for (const feature of geojson.features) {
      const id = String(feature.properties?.id);
      const precinct = byId.get(id);
      const value = precinct && metric ? metric.value(precinct) : null;
      const color = !precinct ? null : metric ? (value != null && scale ? scale.color(value) : null) : kindColor(precinct.kind);
      instance.setFeatureState({ source: "precincts", id }, { color });
    }
  }, [ready, geojson, byId, metric, scale]);

  if (boundaries.isPending) return <Loading text="Načítám mapu…" />;
  if (boundaries.error) return <Problem error={boundaries.error} />;

  return (
    <div>
      <div className="segmented" role="group" aria-label="Co má mapa ukazovat" style={{ marginBottom: 12 }}>
        <button aria-pressed={picked === KIND} onClick={() => setPicked(KIND)}>
          Zástavba
        </button>
        {metrics.map((item) => (
          <button key={item.key} aria-pressed={picked === item.key} onClick={() => setPicked(item.key)}>
            {item.label}
          </button>
        ))}
      </div>
      <div className="map-frame centre-map">
        <div ref={container} className="map-canvas" />
        <div className="map-legend">
          {metric && scale ? (
            <>
              <div className="title">
                {metric.key === MINUTES.key
                  ? "Minut do centra MHD"
                  : metric.key === "turnout"
                    ? "Účast, % zapsaných voličů"
                    : `${metric.label}, % hlasů`}
              </div>
              <div className="ramp">
                {scale.colors.map((color) => (
                  <span key={color} style={{ background: color }} />
                ))}
              </div>
              <div className="ramp-labels">
                {scale.edges.map((edge) => (
                  <span key={edge}>{fmtNum(edge, 0)}</span>
                ))}
                <span />
              </div>
            </>
          ) : (
            <>
              <div className="title">Převažující zástavba</div>
              <div style={{ display: "grid", gap: 4 }}>
                {Object.entries(KINDS).map(([kind, item]) => (
                  <span className="legend-item" key={kind}>
                    <span className="swatch" style={{ background: item.color }} />
                    {item.name}
                  </span>
                ))}
              </div>
            </>
          )}
        </div>
      </div>
      {tooltip.element}
    </div>
  );
}
