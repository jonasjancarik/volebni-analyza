import type { Feature } from "geojson";
import { type LngLatBoundsLike, setWorkerUrl } from "maplibre-gl";
import workerUrl from "maplibre-gl/dist/maplibre-gl-worker.mjs?worker&url";

// Without this the production build would not include the map's worker file
setWorkerUrl(workerUrl);

export const STYLES = {
  light: "https://tiles.openfreemap.org/styles/positron",
  dark: "https://tiles.openfreemap.org/styles/dark",
};

export function bounds(features: Feature[]): LngLatBoundsLike | null {
  let west = Infinity;
  let south = Infinity;
  let east = -Infinity;
  let north = -Infinity;
  const visit = (coordinates: unknown) => {
    const list = coordinates as unknown[];
    if (typeof list[0] === "number") {
      const [lng, lat] = list as number[];
      west = Math.min(west, lng);
      east = Math.max(east, lng);
      south = Math.min(south, lat);
      north = Math.max(north, lat);
    } else list.forEach(visit);
  };
  for (const feature of features) {
    if (feature.geometry && "coordinates" in feature.geometry) visit(feature.geometry.coordinates);
  }
  return Number.isFinite(west) ? [west, south, east, north] : null;
}
