import type { Feature, FeatureCollection, Point, Position } from "geojson";

/** Votes of one precinct that are drawn as dots of one colour */
export interface DotGroup {
  count: number;
  color: string;
}

/** Round numbers a dot can stand for */
const STEPS = [1, 2, 5, 10, 20, 50, 100, 200, 500, 1000, 2000, 5000, 10000, 20000, 50000, 100000];

/** The choices of how much one dot stands for, and the one that keeps the map readable. */
export function dotSteps(total: number): { options: number[]; auto: number } {
  const found = STEPS.findIndex((step) => total / step <= 12000);
  const index = found === -1 ? STEPS.length - 1 : found;
  return { options: STEPS.slice(Math.max(index - 2, 0), index + 4), auto: STEPS[index] };
}

function hash(text: string): number {
  let value = 2166136261;
  for (let i = 0; i < text.length; i++) value = Math.imul(value ^ text.charCodeAt(i), 16777619);
  return value >>> 0;
}

/** Seeded, so that the dots of a precinct stay where they are between redraws */
function generator(seed: number): () => number {
  let state = seed;
  return () => {
    state = (state + 0x6d2b79f5) | 0;
    let t = Math.imul(state ^ (state >>> 15), 1 | state);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

function ringsOf(feature: Feature): Position[][] {
  const geometry = feature.geometry;
  if (geometry?.type === "Polygon") return geometry.coordinates;
  if (geometry?.type === "MultiPolygon") return geometry.coordinates.flat();
  return [];
}

/** Even-odd rule over all rings, which also leaves out holes */
function inside(x: number, y: number, rings: Position[][]): boolean {
  let within = false;
  for (const ring of rings) {
    for (let i = 0, j = ring.length - 1; i < ring.length; j = i++) {
      const [xi, yi] = ring[i];
      const [xj, yj] = ring[j];
      if (yi > y !== yj > y && x < ((xj - xi) * (y - yi)) / (yj - yi) + xi) within = !within;
    }
  }
  return within;
}

/**
 * Dots placed at random inside each precinct, one for every `perDot` votes.
 * What is left after dividing becomes a dot with the matching probability,
 * so that small precincts are not lost and totals stay right on average.
 */
export function dotPoints(
  features: Feature[],
  groups: Map<string, DotGroup[]>,
  perDot: number,
  focusIds: Set<string> | null,
): FeatureCollection<Point> {
  const shapes = new Map<string, Position[][]>();
  for (const feature of features) {
    const id = String(feature.properties?.id);
    shapes.set(id, [...(shapes.get(id) ?? []), ...ringsOf(feature)]);
  }

  const points: Feature<Point>[] = [];
  for (const [id, rings] of shapes) {
    const parts = groups.get(id);
    if (!parts || !rings.length) continue;
    let west = Infinity;
    let south = Infinity;
    let east = -Infinity;
    let north = -Infinity;
    for (const ring of rings) {
      for (const [x, y] of ring) {
        west = Math.min(west, x);
        east = Math.max(east, x);
        south = Math.min(south, y);
        north = Math.max(north, y);
      }
    }
    const rounding = generator(hash(`${id}#`));
    const place = generator(hash(id));
    const dim = focusIds ? !focusIds.has(id) : false;
    for (const part of parts) {
      const exact = part.count / perDot;
      const wanted = Math.floor(exact) + (rounding() < exact % 1 ? 1 : 0);
      // A sliver of a precinct must not stall the page
      let tries = wanted * 40 + 100;
      for (let made = 0; made < wanted && tries > 0; tries--) {
        const x = west + place() * (east - west);
        const y = south + place() * (north - south);
        if (!inside(x, y, rings)) continue;
        made++;
        points.push({
          type: "Feature",
          geometry: { type: "Point", coordinates: [x, y] },
          properties: { color: part.color, dim },
        });
      }
    }
  }
  return { type: "FeatureCollection", features: points };
}
