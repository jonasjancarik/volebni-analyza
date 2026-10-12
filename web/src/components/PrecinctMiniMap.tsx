import { Map as MapLibre, NavigationControl } from "maplibre-gl";
import { useEffect, useRef, useState } from "react";
import { useParams } from "react-router-dom";
import { useBoundaries } from "../api";
import { resolveColor } from "../colors";
import { bounds, STYLES } from "./mapBase";
import { isDark } from "../theme";

/** A small map of where one precinct of the council being viewed lies. */
export function PrecinctMiniMap({ precinct }: { precinct: string }) {
  const { electionId = "", code = "" } = useParams();
  const boundaries = useBoundaries(electionId, code);
  const container = useRef<HTMLDivElement>(null);
  const map = useRef<MapLibre | null>(null);
  const [ready, setReady] = useState(false);
  const geojson = boundaries.data;
  const known = geojson?.features.some((feature) => String(feature.properties?.id) === precinct);

  useEffect(() => {
    if (!container.current || !geojson) return;
    const dark = isDark();
    const instance = new MapLibre({
      container: container.current,
      style: dark ? STYLES.dark : STYLES.light,
      bounds: bounds(geojson.features) ?? undefined,
      attributionControl: { compact: true },
      dragRotate: false,
      pitchWithRotate: false,
      // The panel around the map scrolls, so the wheel must not zoom
      scrollZoom: false,
    });
    instance.addControl(new NavigationControl({ showCompass: false }), "top-left");
    instance.touchZoomRotate.disableRotation();
    map.current = instance;
    instance.on("load", () => {
      const firstLabel = instance.getStyle().layers?.find((layer) => layer.type === "symbol")?.id;
      const nobody = ["==", ["get", "id"], ""] as ["==", ["get", string], string];
      instance.addSource("precincts", { type: "geojson", data: geojson });
      instance.addLayer(
        {
          id: "others",
          type: "line",
          source: "precincts",
          paint: { "line-color": dark ? "#8d8b84" : "#85837c", "line-width": 0.6, "line-opacity": 0.7 },
        },
        firstLabel,
      );
      instance.addLayer(
        {
          id: "picked-fill",
          type: "fill",
          source: "precincts",
          filter: nobody,
          paint: { "fill-color": resolveColor("var(--series-1)"), "fill-opacity": 0.35 },
        },
        firstLabel,
      );
      instance.addLayer({
        id: "picked-line",
        type: "line",
        source: "precincts",
        filter: nobody,
        paint: { "line-color": dark ? "#ffffff" : "#0b0b0b", "line-width": 2.5 },
      });
      // The source note opens by itself and would cover a third of a map this small; its button stays
      const note = instance.getContainer().querySelector(".maplibregl-ctrl-attrib");
      note?.classList.remove("maplibregl-compact-show");
      note?.removeAttribute("open");
      setReady(true);
    });
    return () => {
      map.current = null;
      setReady(false);
      instance.remove();
    };
  }, [geojson]);

  useEffect(() => {
    const instance = map.current;
    if (!ready || !instance || !geojson) return;
    const picked = geojson.features.filter((feature) => String(feature.properties?.id) === precinct);
    const filter = ["==", ["to-string", ["get", "id"]], precinct] as unknown as ["==", ["get", string], string];
    instance.setFilter("picked-fill", filter);
    instance.setFilter("picked-line", filter);
    const box = bounds(picked);
    if (box) instance.fitBounds(box, { padding: 44, maxZoom: 15, duration: 0 });
  }, [ready, geojson, precinct]);

  // A precinct without a boundary has nothing to show
  if (boundaries.error || (geojson && !known)) return null;
  return (
    <div className="mini-map" aria-label={`Mapa okrsku ${precinct}`}>
      <div ref={container} className="map-canvas" />
    </div>
  );
}
