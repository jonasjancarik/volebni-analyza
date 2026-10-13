import { Map as MapLibre, NavigationControl } from "maplibre-gl";
import { useEffect, useMemo, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useBoundaries } from "../api";
import { divergingScale, NO_DATA, resolveColor, sequentialScale } from "../colors";
import { bounds, STYLES, firstLabelLayer } from "../components/mapBase";
import { Loading, Problem } from "../components/State";
import { fmtNum } from "../format";
import { useTooltip } from "../hooks";
import { isDark } from "../theme";

/** One thing the map can show: a number on a colour scale, or a kind with a colour of its own */
export interface MapLayer<Row> {
  key: string;
  label: string;
  /** Heading of the legend */
  legend: string;
  value?: (row: Row) => number | null;
  /** "change" puts zero in the middle of the scale: red below, blue above */
  scale?: "share" | "change";
  kind?: (row: Row) => { name: string; color: string } | null;
  /** What the layer says about one precinct, for the tooltip: the numbers its colour stands for */
  describe?: (row: Row) => React.ReactNode;
}

interface Props<Row> {
  election: string;
  code: string;
  rows: Row[];
  /** Layers in named rows of buttons */
  layers: { title: string; items: MapLayer<Row>[] }[];
  /** Layer shown first */
  initial: string;
  /** The tooltip of a precinct; it is given the layer on show, so that it can explain the colour under the pointer */
  tooltip: (row: Row, layer: MapLayer<Row>) => React.ReactNode;
}

/** The precincts of a council coloured by what the reader picks. */
export function PrecinctMap<Row extends { id: string }>({ election, code, rows, layers, initial, tooltip }: Props<Row>) {
  const boundaries = useBoundaries(election, code);
  const [picked, setPicked] = useState(initial);
  const navigate = useNavigate();
  const container = useRef<HTMLDivElement>(null);
  const map = useRef<MapLibre | null>(null);
  const [ready, setReady] = useState(false);
  const pointer = useTooltip();
  const byId = useMemo(() => new Map(rows.map((row) => [row.id, row])), [rows]);
  const layer = layers.flatMap((group) => group.items).find((item) => item.key === picked)!;

  const scale = useMemo(() => {
    if (!layer.value) return null;
    const values = rows.map(layer.value).filter((value): value is number => value != null);
    // A few dozen precincts: finer steps than the map of a whole city needs
    return layer.scale === "change" ? divergingScale(values, 0.8) : sequentialScale(values);
  }, [layer, rows]);

  // The kinds a layer has, in the order of the precincts' numbers
  const kinds = useMemo(() => {
    const found = new Map<string, string>();
    for (const row of rows) {
      const kind = layer.kind?.(row);
      if (kind && !found.has(kind.name)) found.set(kind.name, resolveColor(kind.color));
    }
    return [...found];
  }, [layer, rows]);

  // Handlers registered once read the latest state through a ref
  const latest = useRef({ byId, tooltip, layer });
  latest.current = { byId, tooltip, layer };
  const geojson = boundaries.data;

  useEffect(() => {
    if (!container.current || !geojson) return;
    const dark = isDark();
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
      const firstLabel = firstLabelLayer(instance);
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
      const row = latest.current.byId.get(String(id));
      pointer.show(
        event.originalEvent,
        row ? latest.current.tooltip(row, latest.current.layer) : <div className="t-sub">Okrsek {String(id)}: bez údajů</div>,
      );
    });
    instance.on("mouseleave", "precinct-fill", () => {
      setHover(null);
      pointer.hide();
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
      const row = byId.get(id);
      const value = row ? layer.value?.(row) : null;
      const kind = row ? layer.kind?.(row) : null;
      const color = kind ? resolveColor(kind.color) : value != null && scale ? scale.color(value) : null;
      instance.setFeatureState({ source: "precincts", id }, { color });
    }
  }, [ready, geojson, byId, layer, scale]);

  if (boundaries.isPending) return <Loading text="Načítám mapu…" />;
  if (boundaries.error) return <Problem error={boundaries.error} />;

  return (
    <div>
      <div className="map-layers">
        {layers.map((group) => (
          <div className="map-layer-row" key={group.title}>
            <span className="small muted">{group.title}</span>
            <div className="segmented" role="group" aria-label={group.title}>
              {group.items.map((item) => (
                <button key={item.key} aria-pressed={picked === item.key} onClick={() => setPicked(item.key)}>
                  {item.label}
                </button>
              ))}
            </div>
          </div>
        ))}
      </div>
      <div className="map-frame article-map">
        <div ref={container} className="map-canvas" />
        <div className="map-legend">
          <div className="title">{layer.legend}</div>
          {scale ? (
            <>
              <div className="ramp">
                {scale.colors.map((color) => (
                  <span key={color} style={{ background: color }} />
                ))}
              </div>
              <div className="ramp-labels">
                {scale.edges.map((edge) => (
                  <span key={edge}>{fmtNum(edge, Number.isInteger(edge) ? 0 : 1)}</span>
                ))}
                <span />
              </div>
            </>
          ) : (
            <div style={{ display: "grid", gap: 4 }}>
              {kinds.map(([name, color]) => (
                <span className="legend-item" key={name}>
                  <span className="swatch" style={{ background: color }} />
                  {name}
                </span>
              ))}
            </div>
          )}
        </div>
      </div>
      {pointer.element}
    </div>
  );
}
