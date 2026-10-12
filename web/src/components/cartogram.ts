import type { Feature, FeatureCollection, Polygon, Position } from "geojson";

/** Share of the territory's area that all circles cover together */
const COVERAGE = 0.3;
const CORNERS = 40;

interface Circle {
  id: string;
  x: number;
  y: number;
  homeX: number;
  homeY: number;
  radius: number;
}

function outerRings(feature: Feature): Position[][] {
  const geometry = feature.geometry;
  if (geometry?.type === "Polygon") return geometry.coordinates.slice(0, 1);
  if (geometry?.type === "MultiPolygon") return geometry.coordinates.map((polygon) => polygon[0]);
  return [];
}

/** Moves overlapping circles apart while keeping them near their precincts. */
function separate(circles: Circle[]) {
  const widest = Math.max(...circles.map((circle) => circle.radius));
  for (let round = 0; round < 160; round++) {
    // Only circles close on the x axis can touch, which spares comparing every pair
    circles.sort((a, b) => a.x - b.x);
    let worst = 0;
    for (let i = 0; i < circles.length; i++) {
      const a = circles[i];
      for (let j = i + 1; j < circles.length && circles[j].x - a.x < a.radius + widest; j++) {
        const b = circles[j];
        const reach = a.radius + b.radius;
        let dx = b.x - a.x;
        let dy = b.y - a.y;
        let distance = Math.hypot(dx, dy);
        if (distance >= reach) continue;
        if (distance < reach * 1e-6) {
          // Two circles on one spot have no direction to part in; pick one that stays the same
          dx = reach * Math.cos(i + j);
          dy = reach * Math.sin(i + j);
          distance = reach;
        }
        const overlap = reach - distance;
        worst = Math.max(worst, overlap / reach);
        // The smaller circle gives way more
        const shareA = b.radius / reach;
        a.x -= (dx / distance) * overlap * shareA;
        a.y -= (dy / distance) * overlap * shareA;
        b.x += (dx / distance) * overlap * (1 - shareA);
        b.y += (dy / distance) * overlap * (1 - shareA);
      }
    }
    if (worst < 0.01) break;
    // The pull home stops for the last rounds, so that they end without overlaps
    if (round < 120) {
      for (const circle of circles) {
        circle.x += (circle.homeX - circle.x) * 0.03;
        circle.y += (circle.homeY - circle.y) * 0.03;
      }
    }
  }
}

/**
 * A circle for every precinct, with an area that matches its `counts` value,
 * at the precinct's centre or, with `apart`, pushed aside so that no two overlap.
 */
export function circleShapes(features: Feature[], counts: Map<string, number>, apart: boolean): FeatureCollection<Polygon> {
  let south = Infinity;
  let north = -Infinity;
  for (const feature of features) {
    for (const ring of outerRings(feature)) {
      for (const [, lat] of ring) {
        south = Math.min(south, lat);
        north = Math.max(north, lat);
      }
    }
  }
  // Degrees of longitude are shorter than degrees of latitude; this makes the circles round
  const squeeze = Math.cos((((south + north) / 2) * Math.PI) / 180);

  const centres = new Map<string, { area: number; x: number; y: number }>();
  for (const feature of features) {
    const id = String(feature.properties?.id);
    const centre = centres.get(id) ?? { area: 0, x: 0, y: 0 };
    for (const ring of outerRings(feature)) {
      let area = 0;
      let x = 0;
      let y = 0;
      for (let i = 0, j = ring.length - 1; i < ring.length; j = i++) {
        const cross = ring[j][0] * squeeze * ring[i][1] - ring[i][0] * squeeze * ring[j][1];
        area += cross;
        x += (ring[j][0] + ring[i][0]) * squeeze * cross;
        y += (ring[j][1] + ring[i][1]) * cross;
      }
      if (!area) continue;
      centre.x += x / 6;
      centre.y += y / 6;
      centre.area += area / 2;
    }
    centres.set(id, centre);
  }

  let territory = 0;
  let total = 0;
  for (const [id, centre] of centres) {
    territory += Math.abs(centre.area);
    total += centre.area ? (counts.get(id) ?? 0) : 0;
  }
  const circles: Circle[] = [];
  for (const [id, centre] of centres) {
    const count = counts.get(id) ?? 0;
    if (!centre.area || count <= 0 || !total) continue;
    const x = centre.x / centre.area;
    const y = centre.y / centre.area;
    const radius = Math.sqrt((COVERAGE * territory * (count / total)) / Math.PI);
    circles.push({ id, x, y, homeX: x, homeY: y, radius });
  }
  if (apart && circles.length > 1) separate(circles);
  // Large circles first, so that small ones are drawn on top of them
  circles.sort((a, b) => b.radius - a.radius);

  return {
    type: "FeatureCollection",
    features: circles.map((circle) => ({
      type: "Feature",
      properties: { id: circle.id },
      geometry: {
        type: "Polygon",
        coordinates: [
          Array.from({ length: CORNERS + 1 }, (_, corner) => {
            const angle = ((corner % CORNERS) / CORNERS) * 2 * Math.PI;
            return [(circle.x + Math.cos(angle) * circle.radius) / squeeze, circle.y + Math.sin(angle) * circle.radius];
          }),
        ],
      },
    })),
  };
}
