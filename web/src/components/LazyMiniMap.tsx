import { lazy, Suspense } from "react";

// The map library is large; it loads only when a precinct is shown
const PrecinctMiniMap = lazy(() => import("./PrecinctMiniMap").then((module) => ({ default: module.PrecinctMiniMap })));

/** The small map of one precinct, with an empty frame in its place until the map library arrives. */
export function LazyMiniMap({ precinct }: { precinct: string }) {
  return (
    <Suspense fallback={<div className="mini-map" />}>
      <PrecinctMiniMap precinct={precinct} />
    </Suspense>
  );
}
